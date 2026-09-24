# -*- coding: utf-8 -*-
"""等效性检验与方差齐性；保留通用 x1-x2 方向，修正旧版统计缺陷。"""
import warnings
import statistics
from typing import Dict, Iterable, Optional

import numpy as np
import pandas as pd
from scipy import stats


def finite_sample(values):
    """单组一维数值样本；排除 NaN/Inf，拒绝误传二维数据。"""
    values = np.asarray(values, dtype=float)
    if values.ndim != 1:
        raise ValueError("样本必须是一维数值数组")
    return values[np.isfinite(values)]


def resolve_tost_alpha(*, alpha=None, confidence_level=None):
    """TOST 单侧 alpha 与差值双侧置信度 C 的关系：alpha=(1-C)/2。"""
    if alpha is not None and confidence_level is not None:
        raise ValueError("alpha 与 confidence_level 只能指定一个")
    if confidence_level is not None:
        if not np.isfinite(confidence_level) or not 0 < confidence_level < 1:
            raise ValueError("confidence_level 必须在 0 与 1 之间")
        alpha = (1.0 - float(confidence_level)) / 2.0
    if alpha is None:
        alpha = 0.05  # 保留通用函数的历史默认；不表示批准参数。
    if not np.isfinite(alpha) or not 0 < alpha < 0.5:
        raise ValueError("TOST 单侧 alpha 必须在 0 与 0.5 之间")
    return float(alpha)


def perform_tost(x1, x2, delta, alpha=None, return_detail=False, *,
                 confidence_level=None, variance_method="pooled", bf_threshold=0.05):
    """双样本 TOST，通用差值始终为 mean(x1)-mean(x2)，不提前舍入。

    variance_method: pooled（合并方差）、welch（不等方差），或
    brown_forsythe（按显式 BF 阈值选择实际公式；不是批准的方法选择规则）。
    样本不足/标准误为零/不可计算返回 not_evaluable，equivalent=None。
    新相似性业务调用使用 compare_equivalence，明确参比与比较的角色。
    """
    alpha = resolve_tost_alpha(alpha=alpha, confidence_level=confidence_level)
    if not np.isfinite(delta) or delta <= 0:
        raise ValueError("delta 必须为有限正数")
    if variance_method not in {"pooled", "welch", "brown_forsythe"}:
        raise ValueError("未知方差方法")
    if not np.isfinite(bf_threshold) or not 0 < bf_threshold < 1:
        raise ValueError("BF 阈值必须在 0 与 1 之间")
    first, second = finite_sample(x1), finite_sample(x2)
    nx, ny = len(first), len(second)
    actual_method = variance_method
    bf_p = lev_p = None
    if variance_method == "brown_forsythe":
        bf, lev, advice = levene_test(first, second, bf_threshold=bf_threshold)
        bf_p = float(bf) if np.isfinite(bf) else None
        lev_p = float(lev) if np.isfinite(lev) else None
        actual_method = "pooled" if advice == "TOST2" else "welch"
    result = dict(mean_diff=None, p_tost=None, equivalent=None, ci_low=None, ci_high=None,
                  t1=None, t2=None, df=None, sd_pooled=None, se=None,
                  status="not_evaluable", reason=None, alpha=alpha,
                  confidence_level=1-2*alpha, delta=float(delta), n1=nx, n2=ny,
                  excluded_n1=len(x1)-nx, excluded_n2=len(x2)-ny,
                  variance_method=actual_method, requested_variance_method=variance_method,
                  bf_threshold=float(bf_threshold), bf_p_value=bf_p, levene_p_value=lev_p)

    def output(reason=None):
        result["reason"] = reason
        return result if return_detail else {key: result[key] for key in
                                            ("p_tost", "equivalent", "status", "reason")}

    if nx < 2 or ny < 2:
        return output("insufficient_samples")
    with np.errstate(over="ignore", invalid="ignore", divide="ignore"):
        difference = float(statistics.mean(first) - statistics.mean(second))
        v1, v2 = float(first.var(ddof=1)), float(second.var(ddof=1))
        pooled = ((nx-1)*v1 + (ny-1)*v2) / (nx+ny-2)
        se2 = pooled*(1/nx+1/ny) if actual_method == "pooled" else v1/nx+v2/ny
    if not all(np.isfinite(v) for v in (difference, v1, v2, se2)):
        return output("non_finite_statistics")
    result["mean_diff"] = difference
    if se2 <= 0:
        return output("zero_standard_error")
    se = float(np.sqrt(se2))
    df = float(nx+ny-2) if actual_method == "pooled" else float(
        1 / ((v1/nx/se2)**2/(nx-1) + (v2/ny/se2)**2/(ny-1)))
    t1, t2 = (difference+delta)/se, (difference-delta)/se
    p = float(max(stats.t.sf(t1, df), stats.t.cdf(t2, df)))
    half_width = float(stats.t.ppf(1-alpha, df)*se)
    low, high = difference-half_width, difference+half_width
    if not all(np.isfinite(v) for v in (df, t1, t2, p, low, high)):
        return output("non_finite_statistics")
    result.update(mean_diff=difference, p_tost=p, equivalent=bool(p < alpha),
                  ci_low=low, ci_high=high, t1=float(t1), t2=float(t2), df=df,
                  se=se, sd_pooled=float(np.sqrt(pooled)) if actual_method == "pooled" else None,
                  status="ok")
    return output()


def compare_equivalence(reference, comparison, *, delta, confidence_level,
                        variance_method, bf_threshold=0.05):
    """相似性统一入口：显式配置，方向固定为比较−参比；返回图/表共用结果。"""
    result = perform_tost(comparison, reference, delta, confidence_level=confidence_level,
                          variance_method=variance_method, bf_threshold=bf_threshold,
                          return_detail=True)
    return {**result, "difference_direction": "comparison_minus_reference"}


def decide_equivalence(ci_low: Optional[float], ci_high: Optional[float], delta: Optional[float]) -> str:
    """
    基于置信区间与等效性阈值（Δ）做结论。

    Examples
    --------
    >>> decide_equivalence(-0.1, 0.1, 0.2)
    '等效'
    >>> decide_equivalence(-0.5, 0.5, 0.2)
    '不等效'
    >>> decide_equivalence(None, 0.1, 0.2)
    '不确定'
    >>> decide_equivalence(-0.1, 0.1, None)
    '不确定(未设Δ)'
    """
    try:
        if delta is None or not np.isfinite(delta) or delta <= 0:
            return "不确定(未设Δ)"
        if ci_low is None or ci_high is None:
            return "不确定"
        ci_low = float(ci_low)
        ci_high = float(ci_high)
        delta = float(delta)
        if not np.isfinite(ci_low) or not np.isfinite(ci_high) or ci_low > ci_high:
            return "不确定"
        if (-delta < ci_low) and (ci_high < delta):
            return "等效"
        return "不等效"
    except Exception:
        return "不确定"


def levene_tests(groups: Iterable) -> Dict[str, float]:
    """
    多组方差齐性检验：同时返回 Brown-Forsythe 与传统 Levene 的 p 值。

    Examples
    --------
    >>> g1, g2 = [1,2,3,4], [1.1,1.9,3.2,4.1]
    >>> res = levene_tests([g1, g2])
    >>> set(res.keys()) == {"bf_p_value","levene_p_value"}
    True
    """
    data = []
    for g in groups:
        if g is None:
            g = []
        g = finite_sample(pd.to_numeric(pd.Series(g, dtype=object), errors="coerce").values)
        data.append(g)

    try:
        bf_stat, bf_p = stats.levene(*data, center="median")
    except Exception:
        bf_p = np.nan

    try:
        lv_stat, lv_p = stats.levene(*data, center="mean")
    except Exception:
        lv_p = np.nan

    return {
        "bf_p_value": float(bf_p) if np.isfinite(bf_p) else np.nan,
        "levene_p_value": float(lv_p) if np.isfinite(lv_p) else np.nan,
    }


def levene_test(ref_data, test_data, *, bf_threshold=0.05):
    """
    执行方差齐性检验，输出 Brown-Forsythe 和 Levene 检验的 p 值。

    Returns
    -------
    bf_p, levene_p, advice  （advice: "TOST2" 齐方差 / "TOST1" 不齐方差或异常）

    Examples
    --------
    >>> ref = [1.0, 1.1, 0.9, 1.2]
    >>> tst = [1.05, 1.15, 1.00, 1.10]
    >>> bf_p, lev_p, advice = levene_test(ref, tst)
    >>> round(float(bf_p), 3), round(float(lev_p), 3), advice
    (0.172, 0.172, 'TOST2')
    """
    if not np.isfinite(bf_threshold) or not 0 < bf_threshold < 1:
        raise ValueError("BF 阈值必须在 0 与 1 之间")
    ref_data = finite_sample(ref_data)
    test_data = finite_sample(test_data)

    # 早退：任一组样本量 < 2 时，不跑 Levene，按不齐方差建议 TOST1
    if ref_data.size < 2 or test_data.size < 2:
        return np.nan, np.nan, "TOST1"

    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        try:
            from scipy.stats import SmallSampleWarning
            warnings.simplefilter("ignore", SmallSampleWarning)
        except Exception:
            warnings.filterwarnings(
                "ignore",
                message=r"^One or more sample arguments is too small;.*",
            )

        # Brown–Forsythe（median）
        _, bf_p = stats.levene(ref_data, test_data, center="median")
        # 传统 Levene（mean）
        _, levene_p = stats.levene(ref_data, test_data, center="mean")

    advice = "TOST2" if (np.isfinite(bf_p) and bf_p > bf_threshold) else "TOST1"
    return bf_p, levene_p, advice
