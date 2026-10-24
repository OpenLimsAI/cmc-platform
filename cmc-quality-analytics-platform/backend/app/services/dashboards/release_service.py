# -*- coding: utf-8 -*-
"""放行趋势看板服务：取数 → 按批号排序 → 调统计引擎 → 拼装前端 JSON。

单位约定：staging 的百分比指标值已是百分数(0–100)。本服务统一在"百分数"口径工作：
- 统计/显示不再 ×100（compute_stats(is_pct=False)）；
- 规格限度来自旧 spec（小数口径），对 is_pct 属性 ×100 换算到百分数后再用；
- 能力指数 Cpk/Ppk 对线性缩放不变，spec 与 value 同单位即正确。
"""
import math
import hashlib
import json

import numpy as np
import pandas as pd

from app.services.mapping.batch import attach_sort_key, attach_year
from app.services.specs import get_spec_limit
from app.services.stats import compute_capability, compute_stats


def _f(x):
    """把 numpy/NaN 转成 JSON 友好的 float/None。"""
    if x is None:
        return None
    try:
        v = float(x)
    except (TypeError, ValueError):
        return None
    return v if math.isfinite(v) else None


def _scale_spec(limit, is_pct):
    if limit is None:
        return None
    return float(limit) * 100.0 if is_pct else float(limit)


def analyze_release(df: pd.DataFrame, *, project_id: str, sample_type: str | None,
                    capability_mode: str = "population", legacy_specs: bool = True) -> list[dict]:
    """对已过滤好的放行长表 df（含 attribute_name/value/batch_number/group_id/is_pct）逐属性分析。"""
    if df is None or df.empty:
        return []

    df = attach_sort_key(df, "batch_number")
    df = attach_year(df, "batch_number")

    out: list[dict] = []
    for attr, sub in df.groupby("attribute_name"):
        is_pct = bool(sub["is_pct"].iloc[0]) if "is_pct" in sub else False
        sub = sub.copy()
        sub["value"] = pd.to_numeric(sub["value"], errors="coerce")
        sub["value"] = sub["value"].where(np.isfinite(sub["value"]))
        sub = sub.dropna(subset=["value"])
        if sub.empty:
            continue

        stats = compute_stats(sub[["value"]], is_pct=False)  # 已是百分数，不再 ×100
        mean = stats["mean_raw"]
        sd_sample = stats["sd_sample_raw"]
        sd_pop = stats["sd_population_raw"]

        # 规格（小数→百分数 if is_pct）
        lsl_raw, usl_raw = get_spec_limit(project_id, attr, sample_type) if legacy_specs else (None, None)
        lsl, usl = _scale_spec(lsl_raw, is_pct), _scale_spec(usl_raw, is_pct)

        cap_value, cap_label = compute_capability(lsl, usl, mean, sd_sample, sd_pop, capability_mode)

        # 趋势点（按批号排序键升序）
        sub = sub.sort_values("lot_sort_key", kind="stable")
        points = [
            {
                "batch_number": None if pd.isna(r.batch_number) else str(r.batch_number),
                "lot_sort_key": int(r.lot_sort_key),
                "year": None if pd.isna(r.year) else int(r.year),
                "group_id": None if pd.isna(r.group_id) else str(r.group_id),
                "value": _f(r.value),
            }
            for r in sub.itertuples(index=False)
        ]

        # 按组别(group_id)聚合（分组柱图）
        grouped = []
        for gid, g in sub.groupby("group_id", dropna=False):
            gv = g["value"]
            grouped.append({
                "group_id": None if pd.isna(gid) else str(gid),
                "n": int(gv.count()),
                "mean": _f(gv.mean()),
                "sd": _f(gv.std(ddof=1)) if gv.count() >= 2 else 0.0,
            })

        out.append({
            "attribute_name": attr,
            "units": sorted(str(u) for u in sub["unit"].dropna().unique()) if "unit" in sub else [],
            "is_pct": is_pct,
            "n": int(stats["n"]),
            "mean": _f(mean),
            "sd_sample": _f(sd_sample),
            "sd_population": _f(sd_pop),
            "min": _f(stats["min_raw"]),
            "max": _f(stats["max_raw"]),
            "rsd_pct": _f(stats["rsd_raw"]),
            "spec": {"lsl": _f(lsl), "usl": _f(usl)},
            "capability": {"value": _f(cap_value), "label": cap_label, "mode": capability_mode},
            "sd_lines": {
                "mean": _f(mean),
                "plus_1_5sd": _f(mean + 1.5 * sd_sample) if mean is not None else None,
                "minus_1_5sd": _f(mean - 1.5 * sd_sample) if mean is not None else None,
                "plus_3sd": _f(mean + 3 * sd_sample) if mean is not None else None,
                "minus_3sd": _f(mean - 3 * sd_sample) if mean is not None else None,
            },
            "groups": grouped,
            "points": points,
        })

    # 按属性名排序，稳定输出
    out.sort(key=lambda d: d["attribute_name"])
    return out


def analyze_qc_release(df: pd.DataFrame, *, project_id: str, sample_type: str | None,
                       capability_mode: str = "population", raw_statistics: bool = False) -> list[dict]:
    """旧 QC 只读预览：原指标/方法/样品/类别/单位/产线分面，绝不引用 RD 规格。"""
    if df.empty:
        return []
    fields = ["attribute_name", "attribute_raw", "method_code", "sample_type", "test_type", "unit", "production_line_id"]
    fields += [field for field in ("placement_status", "sub_lot", "timepoint", "timepoint_unit") if field in df]
    output = []
    for scope, frame in df.groupby(fields, dropna=False, sort=True):
        context = {field: None if pd.isna(value) else str(value) for field, value in zip(fields, scope)}
        for panel in analyze_release(frame, project_id=project_id, sample_type=sample_type,
                                     capability_mode=capability_mode, legacy_specs=False):
            panel["scope"] = context
            panel["panel_id"] = hashlib.sha256(json.dumps(context, ensure_ascii=False, sort_keys=True).encode()).hexdigest()
            panel["statistics_available"] = raw_statistics or bool((context["unit"] or "").strip())
            panel["observations_only"] = True
            # 一个观察不足以估算样本标准差；不把旧引擎的 0 当作无波动。
            if panel["n"] < 2:
                panel["sd_sample"] = None
                panel["rsd_pct"] = None
                panel["sd_lines"] = {key: value if key == "mean" else None for key, value in panel["sd_lines"].items()}
            for group in panel["groups"]:
                if group["n"] < 2:
                    group["sd"] = None
            if not panel["statistics_available"]:
                for field in ("mean", "sd_sample", "sd_population", "min", "max", "rsd_pct"):
                    panel[field] = None
                panel["sd_lines"] = {key: None for key in panel["sd_lines"]}
                panel["groups"] = []
            output.append(panel)
    return output
