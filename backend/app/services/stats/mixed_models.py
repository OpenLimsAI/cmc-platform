# -*- coding: utf-8 -*-
"""混合效应模型与斜率检验（移植自旧工具 analytics/stat_core.py）。

逐函数移植，函数名/参数/返回 dict 的 key（含中文）保持不变。
"""
import re
from typing import Dict, Optional

import numpy as np
import pandas as pd
import statsmodels.api as sm
import statsmodels.formula.api as smf
from scipy import stats

from app.services.stats._ci import ALPHA_SLOPE_EQUALITY, _resolve_ci_level, _t_quantile_for_ci


def within_group_slope_pool_test(
    df: pd.DataFrame,
    group_name: str,
    col_time: str,
    col_group_base: str,
    col_batch: str,
    pool_alpha: float = ALPHA_SLOPE_EQUALITY,
) -> Dict[str, float]:
    """
    在一个给定组（如对照组）内部，检验不同批次的斜率是否"相等/可池化"（ICH Q1E）。

    Examples
    --------
    >>> df = pd.DataFrame({
    ...     "grp":["ctrl","ctrl","ctrl","ctrl"],
    ...     "t":[0,1,0,1],
    ...     "batch":["b1","b1","b2","b2"],
    ...     "y":[1.0, 2.0, 1.1, 2.1]
    ... })
    >>> within_group_slope_pool_test(df, "ctrl", "t", "grp", "batch")["n_batch"]
    2
    """
    SAFE_TIME = "__TIME__"
    TC = "__TC__"

    d = df[df[col_group_base].astype(str) == str(group_name)].copy()
    if d.empty:
        return {"p_interaction": np.nan, "poolable": False, "n_batch": 0}

    nb = d[col_batch].astype(str).nunique()
    if nb < 2:
        return {"p_interaction": np.nan, "poolable": False, "n_batch": nb}

    if "y" not in d.columns:
        return {"p_interaction": np.nan, "poolable": False, "n_batch": nb}

    d[col_time] = pd.to_numeric(d[col_time], errors="coerce")
    d["y"] = pd.to_numeric(d["y"], errors="coerce")
    d = d.dropna(subset=[col_time, col_batch, "y"]).sort_values([col_batch, col_time])

    d["y0"] = d.groupby(col_batch)["y"].transform("first")
    d["delta"] = d["y"] - d["y0"]

    tcounts = d.groupby(col_batch)[col_time].nunique()
    if (tcounts < 2).any():
        return {"p_interaction": np.nan, "poolable": False, "n_batch": nb}

    d = d.rename(columns={col_time: SAFE_TIME})
    t_mean = d[SAFE_TIME].mean(skipna=True)
    d[TC] = d[SAFE_TIME] - t_mean

    try:
        fit = smf.ols(f"delta ~ {TC} * C({col_batch})", data=d).fit()
        anova = sm.stats.anova_lm(fit, typ=2)
        row = [r for r in anova.index if f"{TC}:" in r or f":{TC}" in r]
        pval = anova.loc[row[0], "PR(>F)"] if row else np.nan
    except Exception:
        return {"p_interaction": np.nan, "poolable": False, "n_batch": nb}

    poolable = (pval >= pool_alpha) if pd.notna(pval) else False
    return {
        "p_interaction": float(pval) if np.isfinite(pval) else np.nan,
        "poolable": bool(poolable),
        "n_batch": int(nb),
    }


def run_lme_for_pair(
    d: pd.DataFrame,
    cqa: str,
    ctrl_name: str,
    cmp_name: str,
    col_time: str,
    col_group: str,
    col_batch: str,
    prefer_random_slope: bool = False,
    alpha_tost: Optional[float] = None,
    ci_level: Optional[float] = None,
) -> Optional[Dict[str, float]]:
    """
    线性混合模型（MixedLM）：比较两组（cmp - ctrl）的截距差与斜率差，给出双侧 CI。

    返回字段（约定保持不变）：
      斜率差(BI-RLD) / 斜率差90%CI下限 / 斜率差90%CI上限 /
      截距差(BI-RLD) / 截距差90%CI下限 / 截距差90%CI上限 /
      ctrl斜率(/月) / cmp斜率(/月) / 交互项p值(双侧) / 近似自由度

    Examples
    --------
    >>> df = pd.DataFrame({
    ...   "group":["ctrl","ctrl","cmp","cmp","ctrl","ctrl","cmp","cmp"],
    ...   "time":[0,1,0,1, 0,2,0,2],
    ...   "batch":["b1","b1","b1","b1","b2","b2","b2","b2"],
    ...   "val":[1.0,2.0,1.0,3.0, 1.2,2.2,1.2,3.3]
    ... })
    >>> res = run_lme_for_pair(df, "val", "ctrl", "cmp", "time", "group", "batch")
    >>> (res is None) or isinstance(res, dict)
    True
    """
    ds = d[d[col_group].isin([ctrl_name, cmp_name])].copy()
    if ds.empty:
        return None

    if "y" not in ds.columns:
        if cqa in ds.columns:
            ds["y"] = ds[cqa]
        else:
            return None

    ds[col_time] = pd.to_numeric(ds[col_time], errors="coerce")
    ds["y"] = pd.to_numeric(ds["y"], errors="coerce")
    ds = ds.dropna(subset=[col_time, "y"])
    if ds[col_time].nunique() < 2:
        return None

    ds = ds.sort_values([col_batch, col_group, col_time])
    ds["y0"] = ds.groupby([col_batch, col_group])["y"].transform("first")
    ds["delta"] = ds["y"] - ds["y0"]

    SAFE_TIME = "__TIME__"
    TC = "__TC__"
    ds = ds.rename(columns={col_time: SAFE_TIME})
    t_mean = ds[SAFE_TIME].mean(skipna=True)
    ds[TC] = ds[SAFE_TIME] - t_mean

    order = ([dict(re_formula=f"~{TC}", reml=True)] if prefer_random_slope
             else [dict(re_formula="~1", reml=True)])
    order = order + [dict(re_formula="~1", reml=False)]

    fit = None
    for cfg in order:
        try:
            fit = smf.mixedlm(
                f"delta ~ {TC}*C({col_group})",
                data=ds,
                groups=ds[col_batch],
                re_formula=cfg["re_formula"],
            ).fit(method="lbfgs", reml=cfg["reml"])
            break
        except Exception:
            continue
    if fit is None:
        return None

    # 斜率差（交互项）：est 与 se
    term = None
    pattern = rf"{TC}.*{cmp_name}|{cmp_name}.*{TC}"
    for ix in fit.params.index:
        if re.search(pattern, ix):
            term = ix
            break

    est = float(fit.params.get(term, np.nan))
    se = float(fit.bse.get(term, np.nan))

    # 自动识别 baseline group（reference group）
    param_groups = []
    for ix in fit.params.index:
        if ix.startswith(f"C({col_group})[T."):
            g = ix.split("[T.")[1].rstrip("]")
            param_groups.append(g)

    all_groups = list(ds[col_group].dropna().unique())

    reference_group = None
    for g in all_groups:
        if g not in param_groups:
            reference_group = g
            break
    if reference_group is None:
        reference_group = ctrl_name

    def get_group_intercept(g):
        intercept = float(fit.params.get("Intercept", np.nan))
        if g == reference_group:
            return intercept
        for ix in fit.params.index:
            if ix.startswith(f"C({col_group})[T.{g}]"):
                return intercept + float(fit.params[ix])
        return np.nan

    ctrl_int = get_group_intercept(ctrl_name)
    cmp_int = get_group_intercept(cmp_name)

    est0 = cmp_int - ctrl_int  # 截距差(BI - RLD)

    try:
        nbatch = int(ds[col_batch].nunique())
    except Exception:
        nbatch = 2
    df_approx = max(3, nbatch * 2)

    se0 = np.nan
    try:
        cov = fit.cov_params()
        param_index = list(fit.params.index)

        def _intercept_grad(group: str) -> np.ndarray:
            g = np.zeros(len(param_index), dtype=float)
            for i, name in enumerate(param_index):
                if name == "Intercept":
                    g[i] = 1.0
                elif name.startswith(f"C({col_group})[T.{group}]"):
                    g[i] = 1.0
            return g

        grad_ctrl = _intercept_grad(ctrl_name)
        grad_cmp = _intercept_grad(cmp_name)
        L = grad_cmp - grad_ctrl

        se0_val = float(np.sqrt(L @ cov.values @ L))
        if np.isfinite(se0_val) and se0_val > 0:
            se0 = se0_val
        else:
            se0 = np.nan
    except Exception:
        se0 = np.nan

    ci = _resolve_ci_level(alpha_tost=alpha_tost, ci_level=ci_level)
    t_q = _t_quantile_for_ci(df_approx, ci)

    ci_low, ci_high = (np.nan, np.nan)
    ci0_low, ci0_high = (np.nan, np.nan)

    if np.isfinite(est) and np.isfinite(se) and se > 0:
        ci_low = est - t_q * se
        ci_high = est + t_q * se
    if np.isfinite(est0) and np.isfinite(se0) and se0 > 0:
        ci0_low = est0 - t_q * se0
        ci0_high = est0 + t_q * se0

    if np.isfinite(est) and np.isfinite(se) and se > 0:
        tval = est / se
        p_two_sided = 2 * (1 - stats.t.cdf(abs(tval), df_approx))
    else:
        p_two_sided = np.nan

    def get_group_slope(g):
        beta_time = float(fit.params.get(TC, np.nan))
        if not np.isfinite(beta_time):
            return np.nan
        if g == reference_group:
            return beta_time
        for ix in fit.params.index:
            if ix.startswith(f"{TC}:C({col_group})[T.{g}]"):
                return beta_time + float(fit.params[ix])
            if ix.startswith(f"C({col_group})[T.{g}]:{TC}"):
                return beta_time + float(fit.params[ix])
        return np.nan

    ctrl_slope = get_group_slope(ctrl_name)
    cmp_slope = get_group_slope(cmp_name)

    return {
        "斜率差(BI-RLD)": float(est) if np.isfinite(est) else np.nan,
        "斜率差90%CI下限": float(ci_low) if np.isfinite(ci_low) else np.nan,
        "斜率差90%CI上限": float(ci_high) if np.isfinite(ci_high) else np.nan,
        "截距差(BI-RLD)": float(est0) if np.isfinite(est0) else np.nan,
        "截距差90%CI下限": float(ci0_low) if np.isfinite(ci0_low) else np.nan,
        "截距差90%CI上限": float(ci0_high) if np.isfinite(ci0_high) else np.nan,
        "ctrl斜率(/月)": float(ctrl_slope) if np.isfinite(ctrl_slope) else np.nan,
        "cmp斜率(/月)": float(cmp_slope) if np.isfinite(cmp_slope) else np.nan,
        "交互项p值(双侧)": float(p_two_sided) if np.isfinite(p_two_sided) else np.nan,
        "近似自由度": int(df_approx),
    }


def linear_regression_summary(df: pd.DataFrame, attr: str):
    """返回回归系数、R²、P值等概要（按 group_id 分组，对 time_numeric ~ value 做 OLS）。"""
    if df.empty or len(df) < 2:
        return pd.DataFrame()
    res = []
    for name, sub in df.groupby("group_id"):
        sub = sub.sort_values("time_numeric")
        X = sm.add_constant(sub["time_numeric"])
        model = sm.OLS(sub["value"], X).fit()
        res.append({
            "Group": name,
            "N": len(sub),
            "Slope": model.params["time_numeric"],
            "Intercept": model.params["const"],
            "R²": model.rsquared,
            "p-value": model.pvalues["time_numeric"],
        })
    return pd.DataFrame(res).round(4)
