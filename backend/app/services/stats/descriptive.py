# -*- coding: utf-8 -*-
"""描述性统计与能力指数（移植自旧工具 components/utils.py、analytics/stat_core.py）。

逐函数移植，函数名/参数/返回结构保持不变。仅去除 streamlit 依赖。
"""
import re

import numpy as np
import pandas as pd

_SCI_RE = re.compile(r'^\s*([+-]?\d*\.?\d+(?:[eE][+-]?\d+)?)(\s*%)?\s*$')


def clean_numeric(values):
    """
    将字符串序列清理为数值:
    - 支持科学计数法 (e.g., '1.2e-6', '-3E+05')
    - 支持百分号 (e.g., '12%', '3.5E-2%')
    - 其他非法输入返回 NaN
    """
    ser = pd.Series(values, copy=False)
    out = []
    for x in ser.astype(str).fillna(""):
        m = _SCI_RE.match(x)
        if not m:
            out.append(np.nan)
            continue
        val = float(m.group(1))
        if m.group(2):  # 含百分号
            val = val / 100.0
        out.append(val)
    return pd.to_numeric(out, errors="coerce")


def compute_rsd(series: pd.Series):
    """计算相对标准差 (%)"""
    if len(series.dropna()) < 2:
        return np.nan
    mean_val = np.mean(series)
    std_val = np.std(series, ddof=1)
    return round((std_val / abs(mean_val)) * 100, 2) if mean_val != 0 else np.nan


def compute_capability(lsl, usl, mean, sd_sample, sd_population, mode):
    """
    统一能力指数计算（支持 sample / population）
    mode: 'population' → Ppk / PPU / PPL
          'sample'     → Cpk / CPU / CPL
    """
    # ---- 选择 SD ----
    if mode == "population":     # 使用总体标准差
        sd = sd_population
        upper_label = "PPU"
        lower_label = "PPL"
        both_label = "Ppk"
    else:                         # 使用样本标准差
        sd = sd_sample
        upper_label = "CPU"
        lower_label = "CPL"
        both_label = "Cpk"

    # ---- SD 不合法 ----
    if sd is None or sd <= 0 or np.isnan(sd):
        return None, None

    results = []

    # ===== 单侧上限（若 usl 存在）=====
    if usl is not None:
        cpu = (usl - mean) / (3 * sd)
        results.append((cpu, upper_label))

    # ===== 单侧下限（若 lsl 存在）=====
    if lsl is not None:
        cpl = (mean - lsl) / (3 * sd)
        results.append((cpl, lower_label))

    # ===== 无规格 =====
    if not results:
        return None, None

    # ===== 双侧规格：取更小（更差）的那个 =====
    value, label = sorted(results, key=lambda x: x[0])[0]

    return value, label


def compute_stats(df: pd.DataFrame, is_pct: bool = False) -> dict:
    """
    统一统计函数（趋势图、柱图、表格、SD线、Capability 统一入口）。
    返回 n / mean_raw / sd_sample_raw / sd_population_raw / min_raw / max_raw / rsd_raw
    及绘图用 *_plot 版本（百分比字段乘 100，RSD% 不乘）。
    """
    # 空数据返回默认值
    if df is None or df.empty or "value" not in df.columns:
        return {
            "n": 0, "mean_raw": None, "sd_sample_raw": None, "sd_population_raw": None,
            "min_raw": None, "max_raw": None, "rsd_raw": None,
            "mean_plot": None, "sd_plot": None, "min_plot": None, "max_plot": None, "rsd_plot": None,
        }

    vals = pd.to_numeric(df["value"], errors="coerce").dropna()

    if len(vals) == 0:
        return {
            "n": 0, "mean_raw": None, "sd_sample_raw": None, "sd_population_raw": None,
            "min_raw": None, "max_raw": None, "rsd_raw": None,
            "mean_plot": None, "sd_plot": None, "min_plot": None, "max_plot": None, "rsd_plot": None,
        }

    # -------- 原始统计值（未乘100）--------
    n = len(vals)
    mean_raw = vals.mean()
    sd_sample_raw = vals.std(ddof=1) if n >= 2 else 0
    sd_population_raw = vals.std(ddof=0) if n >= 2 else 0
    min_raw = vals.min()
    max_raw = vals.max()
    rsd_raw = (sd_sample_raw / mean_raw * 100) if mean_raw != 0 else None

    # -------- 绘图使用值（百分比字段乘100）--------
    factor = 100 if is_pct else 1

    mean_plot = mean_raw * factor
    sd_plot = sd_sample_raw * factor
    min_plot = min_raw * factor
    max_plot = max_raw * factor
    rsd_plot = rsd_raw  # RSD% 不乘

    return {
        "n": n,
        "mean_raw": mean_raw,
        "sd_sample_raw": sd_sample_raw,
        "sd_population_raw": sd_population_raw,
        "min_raw": min_raw,
        "max_raw": max_raw,
        "rsd_raw": rsd_raw,
        "mean_plot": mean_plot,
        "sd_plot": sd_plot,
        "min_plot": min_plot,
        "max_plot": max_plot,
        "rsd_plot": rsd_plot,
    }
