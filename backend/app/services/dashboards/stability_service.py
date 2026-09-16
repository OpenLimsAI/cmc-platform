"""稳定性原始观察与描述统计：按来源维度分面，不融合放行、不换算单位。"""
from collections import defaultdict
import hashlib
import json
import math

import numpy as np
import pandas as pd

from app.schemas.stability import StabilityRequest
from app.schemas.data_source import DATA_SOURCE_MAP


FILTERS = {
    "placement_statuses": "placement_status", "sample_types": "sample_type", "test_types": "test_type",
    "production_line_ids": "production_line_id", "group_ids": "group_id",
    "batch_numbers": "batch_number", "attribute_names": "attribute_name",
}
PANEL_FIELDS = ("attribute_name", "attribute_raw", "sample_type", "test_type", "method_code", "unit", "timepoint_unit", "placement_status", "sub_lot")


def raw_text(value) -> str | None:
    return None if value is None or pd.isna(value) else str(value)


def finite(value) -> float | None:
    try:
        number = float(value)
        return number if math.isfinite(number) else None
    except (ValueError, TypeError, OverflowError):
        return None


def _id(values) -> str:
    return hashlib.sha256(json.dumps(values, ensure_ascii=False).encode()).hexdigest()


def filter_stability(df: pd.DataFrame, req: StabilityRequest, fields=None) -> pd.DataFrame:
    result = df.copy()
    if result.empty:
        return result
    result = result[(result["project_id"] == req.project_id) & (result["data_type"] == "Stability") & result["source_system"].isin(DATA_SOURCE_MAP[req.data_source])]
    for field in FILTERS if fields is None else fields:
        selected = getattr(req, field)
        if selected:
            result = result[result.get(FILTERS[field], pd.Series(None, index=result.index, dtype=object)).isin(selected)]
    return result.reset_index(drop=True)


def stability_options(df: pd.DataFrame, req: StabilityRequest) -> dict:
    def values(frame, column):
        return sorted(str(value) for value in frame[column].dropna().unique()) if column in frame else []

    project = filter_stability(df, req, [])
    sample = filter_stability(project, req, ["sample_types"])
    test = filter_stability(sample, req, ["test_types"])
    line_group = filter_stability(test, req, ["production_line_ids", "group_ids", "placement_statuses"])
    batches = filter_stability(line_group, req, ["batch_numbers"])
    attributes = []
    if not batches.empty:
        for name, group in batches.groupby("attribute_name", sort=True):
            attributes.append({"attribute_name": name, "attribute_raws": values(group, "attribute_raw"), "n": len(group)})
    return {
        "placement_statuses": values(test, "placement_status"), "sample_types": values(project, "sample_type"), "test_types": values(sample, "test_type"),
        "production_line_ids": values(test, "production_line_id"), "group_ids": values(test, "group_id"),
        "batch_numbers": values(line_group, "batch_number"), "attributes": attributes,
        "row_count": len(batches), "project_row_count": len(project),
    }


def _fit(points: list[dict]) -> dict:
    """带截距的观察值OLS，仅返回观察范围端点；不计算推断/有效期。"""
    x = np.array([p["timepoint"] for p in points], dtype=float)
    y = np.array([p["value"] for p in points], dtype=float)
    if len(set(x)) < 2:
        return {"available": False, "reason": "至少需要两个不同时间点"}
    with np.errstate(over="ignore", invalid="ignore", divide="ignore"):
        dx, dy = x - x.mean(), y - y.mean()
        slope = float(np.dot(dx, dy) / np.dot(dx, dx))
        intercept = float(y.mean() - slope * x.mean())
        fitted = intercept + slope * x
        residual = float(np.sum((y - fitted) ** 2))
        total = float(np.sum(dy ** 2))
        r_squared = finite(1 - residual / total) if total > 0 else None
        xs = [float(x.min()), float(x.max())]
        ys = [finite(intercept + slope * time) for time in xs]
    if finite(slope) is None or finite(intercept) is None or None in ys:
        return {"available": False, "reason": "数值范围无法稳定计算"}
    return {"available": True, "n": len(points), "slope": slope, "intercept": intercept, "r_squared": r_squared, "x": xs, "y": ys}


def analyze_stability(df: pd.DataFrame, req: StabilityRequest) -> list[dict]:
    selected = filter_stability(df, req)
    panels: dict[tuple, list[dict]] = defaultdict(list)
    for index, row in enumerate(selected.to_dict("records")):
        key = tuple(raw_text(row.get(field)) for field in PANEL_FIELDS)
        timepoint, value = finite(row.get("timepoint")), finite(row.get("value"))
        issues = []
        if timepoint is None:
            issues.append("时间点缺失或非有限数值")
        elif timepoint < 0:
            issues.append("时间点为负，待核对")
        if value is None:
            issues.append("结果缺失或非有限数值")
        point = {field: raw_text(row.get(field)) for field in (
            "batch_number", "production_line_id", "group_id", "source_system", "sample_id", "source_test_id", "source_result_id", "value_str", "received_dt", "source_file", "sample_submission_date", "placement_status", "sub_lot",
        )}
        point.update({"observation_id": f"observation_{index}", "timepoint": timepoint, "timepoint_raw": raw_text(row.get("timepoint")),
                      "value": value, "value_raw": raw_text(row.get("value")), "issues": issues, "plottable": not issues})
        panels[key].append(point)

    result = []
    for key, points in panels.items():
        scope = dict(zip(PANEL_FIELDS, key))
        units_known = all(scope[field] is not None and scope[field].strip() for field in ("unit", "timepoint_unit"))
        valid = [point for point in points if point["plottable"]]
        batch_series: dict[tuple, list[dict]] = defaultdict(list)
        group_series: dict[tuple, list[dict]] = defaultdict(list)
        for point in valid:
            group_key = (point["source_system"], point["production_line_id"], point["group_id"])
            # 缺失批号不建立虚假的共同批次。
            batch_key = (*group_key, point["batch_number"], point["observation_id"] if not (point["batch_number"] or "").strip() else None)
            batch_series[batch_key].append(point)
            group_series[group_key].append(point)

        batches = []
        for batch_key, rows in batch_series.items():
            rows = sorted(rows, key=lambda point: point["timepoint"])
            can_connect = len({point["timepoint"] for point in rows}) == len(rows) and bool((rows[0]["batch_number"] or "").strip())
            batches.append({"series_id": _id(batch_key), "batch_number": rows[0]["batch_number"], "production_line_id": rows[0]["production_line_id"], "group_id": rows[0]["group_id"],
                            "points": rows, "connect_points": can_connect,
                            "fit": _fit(rows) if units_known else {"available": False, "reason": "时间或结果单位未提供"}})
        groups = []
        if units_known:
            for group_key, rows in group_series.items():
                times: dict[float, list[float]] = defaultdict(list)
                for point in rows:
                    times[point["timepoint"]].append(point["value"])
                summaries = []
                for timepoint, values in sorted(times.items()):
                    with np.errstate(over="ignore", invalid="ignore"):
                        summaries.append({"timepoint": timepoint, "n": len(values), "mean": finite(np.mean(values)), "sd": finite(np.std(values, ddof=1)) if len(values) > 1 else None})
                groups.append({"series_id": _id(group_key), "production_line_id": group_key[1], "group_id": group_key[2], "points": summaries, "fit": _fit(rows)})
        warnings = []
        if not units_known:
            warnings.append("时间或结果单位未提供：仅显示原始观察，均值SD与拟合未开放")
        if len(valid) != len(points):
            warnings.append(f"{len(points) - len(valid)}条记录无法进入数值时间图，原记录保留在明细")
        if any(not series["connect_points"] for series in batches):
            warnings.append("部分批次同一时间点有多个观察或批号缺失，使用散点保留全部记录")
        result.append({"panel_id": _id(key), **scope, "n": len(points), "plotted_n": len(valid), "statistics_available": bool(units_known),
                       "timepoint_count": len({point["timepoint"] for point in valid}), "warnings": warnings,
                       "observations": points, "batches": batches, "groups": groups})
    return sorted(result, key=lambda panel: tuple(panel[field] or "" for field in PANEL_FIELDS))
