# -*- coding: utf-8 -*-
"""双侧置信水平解析与 t 分位（移植自旧工具 analytics/stat_core.py，逻辑不变）。"""
from typing import Optional

from scipy import stats

# ===== 默认常量（保留：用于回退与向后兼容） =====
ALPHA = 0.05                 # 历史常量：若未显式传入 ci_level / alpha_tost，推导双侧CI时回退（→ 90% CI）
ALPHA_SLOPE_EQUALITY = 0.25  # 斜率相等/可合并的常用阈值（池化判断）
DEFAULT_ALPHA_TOST = 0.05    # TOST 常用显著性水平（→ 每侧 5%）
DEFAULT_CI_LEVEL = 0.90      # 等效性常用双侧置信水平（90%）
DEFAULT_LEVENE_CENTER = "median"  # 'median' → Brown-Forsythe；'mean' → 传统 Levene


def _resolve_ci_level(alpha_tost: Optional[float], ci_level: Optional[float]) -> float:
    """
    解析双侧置信水平（two-sided CI level）。

    Examples
    --------
    >>> _resolve_ci_level(alpha_tost=0.05, ci_level=None)
    0.9
    >>> _resolve_ci_level(alpha_tost=None, ci_level=0.95)
    0.95
    """
    if ci_level is not None:
        return float(ci_level)
    if alpha_tost is not None:
        return float(max(0.0, min(1.0, 1.0 - 2.0 * alpha_tost)))
    if ALPHA is not None:
        return float(max(0.0, min(1.0, 1.0 - 2.0 * ALPHA)))
    return DEFAULT_CI_LEVEL


def _t_quantile_for_ci(df: int, ci_level: float) -> float:
    """
    根据双侧置信水平计算 t 分位数。

    Examples
    --------
    >>> round(float(_t_quantile_for_ci(10, 0.90)), 3)
    1.812
    """
    q = 0.5 + ci_level / 2.0
    q = max(0.5, min(0.999999, q))  # 简单范围保护
    return stats.t.ppf(q, df)
