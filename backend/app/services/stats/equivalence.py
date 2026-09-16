# -*- coding: utf-8 -*-
"""等效性检验与方差齐性（移植自旧工具 analytics/stat_core.py、analytics/equivalence_test.py）。

逐函数移植，函数名/参数/返回结构与 doctest 保持不变。
"""
import warnings
from typing import Dict, Iterable, Optional

import numpy as np
import pandas as pd
from scipy import stats


def perform_tost(x1, x2, delta, alpha=0.05, return_detail=False):
    """
    双样本 TOST 等效性检验（原始单位 Δ 版本）

    参数:
        x1, x2 : array-like  两组样本数据（数值型）。
        delta : float        等效性界限（原始单位），判定区间为 [-delta, +delta]。
        alpha : float        显著性水平（默认 0.05 → 对应 90% CI）。
        return_detail : bool 是否返回详细计算结构。

    返回:
        dict: mean_diff / p_tost / equivalent / ci_low / ci_high / t1 / t2 / df / sd_pooled
    """
    # 数据清洗
    x1 = np.array(x1, dtype=float)
    x2 = np.array(x2, dtype=float)
    x1 = x1[~np.isnan(x1)]
    x2 = x2[~np.isnan(x2)]

    if len(x1) < 2 or len(x2) < 2:
        return {"p_tost": np.nan, "equivalent": False}

    # 统计量
    nx, ny = len(x1), len(x2)
    mean_diff = np.mean(x1) - np.mean(x2)
    sd1, sd2 = np.var(x1, ddof=1), np.var(x2, ddof=1)
    sd_pooled = np.sqrt(((nx - 1) * sd1 + (ny - 1) * sd2) / (nx + ny - 2))
    se = sd_pooled * np.sqrt(1 / nx + 1 / ny)
    df = nx + ny - 2

    # TOST 两个单侧检验
    t1 = (mean_diff + delta) / se
    t2 = (mean_diff - delta) / se

    # 单边 p 值
    p1 = 1 - stats.t.cdf(t1, df)   # 对应 H1
    p2 = stats.t.cdf(t2, df)       # 对应 H2

    # TOST p 值 = 两个单侧检验中较大的那个
    p_tost = max(p1, p2)

    # 90% CI（由 alpha=0.05 推导）
    ci_low, ci_high = stats.t.interval(1 - 2 * alpha, df, loc=mean_diff, scale=se)

    equivalent = (p_tost < alpha)

    res = {
        "mean_diff": round(mean_diff, 4),
        "p_tost": round(p_tost, 5),
        "equivalent": bool(equivalent),
        "ci_low": round(ci_low, 4),
        "ci_high": round(ci_high, 4),
        "t1": round(t1, 3),
        "t2": round(t2, 3),
        "df": int(df),
        "sd_pooled": round(sd_pooled, 4),
    }

    return res if return_detail else {"p_tost": res["p_tost"], "equivalent": res["equivalent"]}


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
        if delta is None or not np.isfinite(delta):
            return "不确定(未设Δ)"
        if ci_low is None or ci_high is None:
            return "不确定"
        ci_low = float(ci_low)
        ci_high = float(ci_high)
        delta = float(delta)
        if np.isnan(ci_low) or np.isnan(ci_high):
            return "不确定"
        if (-delta <= ci_low) and (ci_high <= delta):
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
        g = pd.to_numeric(pd.Series(g), errors="coerce").dropna().values
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


def levene_test(ref_data, test_data):
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
    ref_data = np.asarray(ref_data, dtype=float)
    test_data = np.asarray(test_data, dtype=float)
    ref_data = ref_data[~np.isnan(ref_data)]
    test_data = test_data[~np.isnan(test_data)]

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

    advice = "TOST2" if (np.isfinite(bf_p) and bf_p > 0.05) else "TOST1"
    return bf_p, levene_p, advice
