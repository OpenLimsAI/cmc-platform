# -*- coding: utf-8 -*-
"""相似性/等效边界（移植自旧工具 analytics/stat_core.py、equivalence_test.py、components/utils.py）。

逐函数移植，函数名/参数/返回结构与 doctest 保持不变。
"""
from typing import Dict, Optional, Tuple

import numpy as np
import pandas as pd

from app.services.stats.equivalence import levene_test, perform_tost


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


def tier_similarity_judge(
    value_column,
    tier1_fields,
    ref_mean,
    ref_std,
    ref_data,
    test_data,
    *,
    k_tier1: float = 1.5,
    k_tier2: float = 3.0,
    alpha: float = 0.05,
    prop_thresh: float = 0.90,
):
    """
    基于 FDA / PQRI Tier 方法对质量属性(CQA)进行相似性判定。

    - Tier1（高风险）：TOST，Δ = k_tier1 × SD_ref，p_TOST < alpha → 相似
    - Tier2（中风险）：范围比例法，≥ prop_thresh 的点落入 ±k_tier2×SD_ref → 相似
    - 单点：|x_test − mean_ref| ≤ k × SD_ref（k 按 Tier1/Tier2 切换）

    返回: "Similar" / "Not Similar" / "Similar (Single Point)" /
          "Not Similar (Single Point)" / "Unknown"

    Examples
    --------
    >>> ref = [100, 102, 98, 101]
    >>> tst = [99, 101, 100]
    >>> tier_similarity_judge("SEC", ["SEC"], np.mean(ref), np.std(ref, ddof=1), ref, tst)
    'Similar'

    >>> ref = [50, 51, 52]
    >>> tst = [60]  # 单点
    >>> tier_similarity_judge("IEX", [], np.mean(ref), np.std(ref, ddof=1), ref, tst)
    'Not Similar (Single Point)'
    """
    # 安全清洗
    ref_data = np.asarray(ref_data, dtype=float)
    test_data = np.asarray(test_data, dtype=float)
    ref_data = ref_data[~np.isnan(ref_data)]
    test_data = test_data[~np.isnan(test_data)]

    # 基本健壮性
    if len(test_data) == 0 or not np.isfinite(ref_mean) or not np.isfinite(ref_std):
        return "Unknown"

    # ===== 单点场景（统一用可调 k）=====
    if len(test_data) == 1:
        k = k_tier1 if value_column in tier1_fields else k_tier2
        threshold = k * ref_std
        if not np.isfinite(threshold):
            return "Unknown"
        diff = abs(float(test_data[0]) - ref_mean)
        return "Similar (Single Point)" if diff <= threshold else "Not Similar (Single Point)"

    # ===== 多点场景 =====
    if value_column in tier1_fields:
        # Tier1：TOST
        delta = k_tier1 * ref_std
        if not np.isfinite(delta):
            return "Unknown"

        # 方差齐性判断（不影响 TOST 逻辑，只用于方法记录）
        try:
            bf_p, _, method = levene_test(ref_data, test_data)
        except Exception:
            method = "TOST1"

        res = perform_tost(ref_data, test_data, delta=delta, alpha=alpha, return_detail=True)

        if res is None or "equivalent" not in res:
            return "Unknown"

        return "Similar" if res["equivalent"] else "Not Similar"

    else:
        # Tier2：范围比例法（± k_tier2 × SD_ref）
        if not np.isfinite(ref_std):
            return "Unknown"
        lower = ref_mean - k_tier2 * ref_std
        upper = ref_mean + k_tier2 * ref_std
        within = ((test_data >= lower) & (test_data <= upper)).sum()
        proportion = within / len(test_data)
        return "Similar" if proportion >= prop_thresh else "Not Similar"
