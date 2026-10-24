# -*- coding: utf-8 -*-
"""相似性/等效边界（移植自旧工具 analytics/stat_core.py、equivalence_test.py、components/utils.py）。

相似性判定已修正；主表和 Tier1 共用一次 TOST，不沿用旧版独立重算。
"""
from typing import Dict, Optional, Tuple
import statistics

import numpy as np
import pandas as pd

from app.services.stats.equivalence import compare_equivalence, finite_sample, resolve_tost_alpha


def _per_batch_baseline_and_slope(
    df: pd.DataFrame,
    cqa: str,
    col_group: str,
    ctrl_name: str,
    col_time: str,
    col_batch: str,
) -> Tuple[pd.Series, pd.Series]:
    """
    计算控制组中每个批次的"基线（首个时间点的 y）"与"斜率（最小二乘）"。

    Examples
    --------
    >>> df = pd.DataFrame({
    ...     "grp":["ctrl","ctrl","ctrl"], "t":[0,1,2], "batch":["b1","b1","b1"], "val":[1,2,3]
    ... })
    >>> base, slp = _per_batch_baseline_and_slope(df, "val", "grp", "ctrl", "t", "batch")
    >>> base.tolist()
    [1]
    >>> round(float(slp.iloc[0]), 2)
    1.0
    """
    d = df.copy()
    d = d[d[col_group].astype(str) == str(ctrl_name)]
    d = d.dropna(subset=[col_time, cqa, col_batch])

    d[col_time] = pd.to_numeric(d[col_time], errors="coerce")
    d[cqa] = pd.to_numeric(d[cqa], errors="coerce")
    d = d.dropna(subset=[col_time, cqa])
    if d.empty:
        return pd.Series(dtype=float), pd.Series(dtype=float)

    d = d.sort_values([col_batch, col_time])
    baseline = d.groupby(col_batch)[cqa].nth(0)

    def _slope(g: pd.DataFrame) -> float:
        x = g[col_time].values
        y = g[cqa].values
        if len(x) < 2 or len(np.unique(x)) < 2:
            return np.nan
        x_mean = x.mean()
        y_mean = y.mean()
        denom = ((x - x_mean) ** 2).sum()
        if denom == 0:
            return np.nan
        return float(((x - x_mean) * (y - y_mean)).sum() / denom)

    slope = d.groupby(col_batch, group_keys=False).apply(_slope)
    slope.name = "slope"
    return baseline, slope


def compute_auto_margins(
    df: pd.DataFrame,
    cqa: str,
    ctrl_name: str,
    col_group: str,
    col_time: str,
    col_batch: str,
    k: float = 1.5,
) -> Dict[str, Optional[float]]:
    """
    自动计算 Δ0（截距容差）与 Δslope（斜率容差）。
    - Δ0 = k * std(控制组各批次基线)
    - Δslope = k * std(控制组各批次斜率)

    Examples
    --------
    >>> df = pd.DataFrame({
    ...     "grp":["ctrl","ctrl","ctrl","ctrl","ctrl","ctrl"],
    ...     "t":[0,1,2,0,1,2],
    ...     "batch":["b1","b1","b1","b2","b2","b2"],
    ...     "val":[1,2,3, 1.2, 2.2, 2.9]
    ... })
    >>> compute_auto_margins(df, "val", "ctrl", "grp", "t", "batch", k=1.5)["k"]
    1.5
    """
    baseline, slope = _per_batch_baseline_and_slope(df, cqa, col_group, ctrl_name, col_time, col_batch)
    out = {"delta0": None, "deltaslope": None, "k": float(k), "source": "auto"}

    if baseline.size >= 2 and baseline.std(ddof=1) > 0:
        out["delta0"] = float(k * baseline.std(ddof=1))

    slope_num = pd.to_numeric(slope, errors="coerce")
    if slope_num.size >= 2 and np.isfinite(slope_num).sum() >= 2:
        s = np.nanstd(slope_num.astype(float), ddof=1)
        if s > 0:
            out["deltaslope"] = float(k * s)
    return out


def get_delta(value_column, ref_std, tier1_fields, delta_multiplier):
    """
    计算等效边界 Δ：Tier1 字段 Δ = 1.5×SD；Tier2 字段 Δ = delta_multiplier×SD。
    """
    if value_column in tier1_fields:
        return 1.5 * ref_std
    else:
        return delta_multiplier * ref_std


def evaluate_similarity_pair(reference, comparison, *, tier, delta, confidence_level,
                             variance_method, prop_thresh=None, bf_threshold=0.05):
    """显式规则下的统一结果，不推断已批准状态或独立样本资格。

    Tier1 的 equivalent/CI/p 和 judgement 来自同一次 TOST。
    Tier2 使用显式 delta 作为参考带半宽；不能暗中忽略手动界值。
    调用方必须先核定独立样本、单位、参比资格和规则，本函数不去重/换算。
    """
    if tier not in {"Tier1", "Tier2"}:
        raise ValueError("tier 必须为 Tier1 或 Tier2")
    if tier == "Tier1":
        result = compare_equivalence(reference, comparison, delta=delta,
                                     confidence_level=confidence_level,
                                     variance_method=variance_method, bf_threshold=bf_threshold)
        judgement = "Unknown" if result["equivalent"] is None else (
            "Similar" if result["equivalent"] else "Not Similar")
        return {**result, "tier": tier, "judgement": judgement}
    resolve_tost_alpha(confidence_level=confidence_level)
    if not np.isfinite(delta) or delta <= 0:
        raise ValueError("delta 必须为有限正数")
    if prop_thresh is None or not np.isfinite(prop_thresh) or not 0 < prop_thresh <= 1:
        raise ValueError("Tier2 必须指定 0 到 1 之间的命中比例阈值")
    ref, test = finite_sample(reference), finite_sample(comparison)
    result = dict(tier=tier, judgement="Unknown", status="not_evaluable", reason=None,
                  method="reference_band", delta=float(delta), prop_thresh=float(prop_thresh),
                  lower=None, upper=None, band_hits=None, band_ratio=None,
                  reference_n=len(ref), comparison_n=len(test))
    if len(ref) < 2 or len(test) < 2:
        return {**result, "reason": "insufficient_samples"}
    with np.errstate(over="ignore", invalid="ignore"):
        # Match the dashboard's reference mean exactly; a one-ulp difference can
        # change whether an observation on an inclusive band boundary is counted.
        mean = float(statistics.mean(ref))
        lower, upper = mean-delta, mean+delta
    if not np.isfinite(lower) or not np.isfinite(upper):
        return {**result, "reason": "non_finite_statistics"}
    hits = int(((test >= lower) & (test <= upper)).sum())
    proportion = hits / len(test)
    return {**result, "status": "ok", "lower": lower, "upper": upper,
            "band_hits": hits, "band_ratio": proportion,
            "judgement": "Similar" if proportion >= prop_thresh else "Not Similar"}


def tier_similarity_judge(
    value_column, tier1_fields, ref_mean, ref_std, ref_data, test_data, *,
    k_tier1: float = 1.5, k_tier2: float = 3.0, alpha=None, prop_thresh: float = 0.90,
    confidence_level=None, delta=None, variance_method="pooled", bf_threshold=0.05,
):
    """旧调用兼容入口；正式新调用应使用显式配置的 evaluate_similarity_pair。

    ref_mean/ref_std 仅保留位置兼容，统计量从有效原始参比重新计算。
    显式 delta 优先；confidence_level 与 alpha 互斥。单点不再冒充相似判定。

    >>> ref = [100, 102, 98, 101]
    >>> tst = [99, 101, 100]
    >>> tier_similarity_judge("SEC", ["SEC"], np.mean(ref), np.std(ref, ddof=1), ref, tst)
    'Similar'
    >>> tier_similarity_judge("IEX", [], 51, 1, [50, 51, 52], [60])
    'Unknown'
    """
    alpha = resolve_tost_alpha(alpha=alpha, confidence_level=confidence_level)
    tier = "Tier1" if value_column in tier1_fields else "Tier2"
    if delta is None:
        k = k_tier1 if tier == "Tier1" else k_tier2
        if not np.isfinite(k) or k <= 0:
            raise ValueError("参考 SD 倍数必须为有限正数")
        ref = finite_sample(ref_data)
        if len(ref) < 2:
            return "Unknown"
        with np.errstate(over="ignore", invalid="ignore"):
            delta = float(k * np.std(ref, ddof=1))
        if not np.isfinite(delta) or delta <= 0:
            return "Unknown"
    result = evaluate_similarity_pair(
        ref_data, test_data, tier=tier, delta=delta, confidence_level=1-2*alpha,
        variance_method=variance_method, prop_thresh=prop_thresh, bf_threshold=bf_threshold,
    )
    return result["judgement"]
