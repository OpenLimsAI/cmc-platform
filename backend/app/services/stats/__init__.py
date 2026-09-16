# -*- coding: utf-8 -*-
"""纯统计函数包：旧算法移植及经过独立验证的缺陷修正。

约束：
- 不依赖 FastAPI / SQLAlchemy / streamlit；只用 numpy/pandas/scipy/statsmodels。
- 已修正的相似性算法按独立算例验收，不要求复制旧缺陷。
"""
from app.services.stats._ci import (
    ALPHA,
    ALPHA_SLOPE_EQUALITY,
    DEFAULT_ALPHA_TOST,
    DEFAULT_CI_LEVEL,
    DEFAULT_LEVENE_CENTER,
)
from app.services.stats.descriptive import (
    clean_numeric,
    compute_capability,
    compute_rsd,
    compute_stats,
)
from app.services.stats.equivalence import (
    compare_equivalence,
    resolve_tost_alpha,
    decide_equivalence,
    levene_test,
    levene_tests,
    perform_tost,
)
from app.services.stats.mixed_models import (
    linear_regression_summary,
    run_lme_for_pair,
    within_group_slope_pool_test,
)
from app.services.stats.similarity import (
    compute_auto_margins,
    get_delta,
    tier_similarity_judge,
    evaluate_similarity_pair,
)

__all__ = [
    # 描述统计 / 能力指数
    "clean_numeric", "compute_stats", "compute_rsd", "compute_capability",
    # 等效性 / 方差齐性
    "perform_tost", "compare_equivalence", "resolve_tost_alpha", "decide_equivalence", "levene_test", "levene_tests",
    # 相似性 / 边界
    "tier_similarity_judge", "evaluate_similarity_pair", "get_delta", "compute_auto_margins",
    # 混合模型 / 回归
    "run_lme_for_pair", "within_group_slope_pool_test", "linear_regression_summary",
    # 常量
    "ALPHA", "ALPHA_SLOPE_EQUALITY", "DEFAULT_ALPHA_TOST", "DEFAULT_CI_LEVEL", "DEFAULT_LEVENE_CENTER",
]
