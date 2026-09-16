"""Read-only raw-value comparisons. No inferred equivalence or unit conversion."""
from collections import defaultdict
import statistics
import numpy as np
import pandas as pd
from app.schemas.similarity import SimilarityRequest
from app.schemas.data_source import DATA_SOURCE_MAP
from app.services.dashboards.stability_service import raw_text, finite, _id

SCOPE = ("attribute_name", "attribute_raw", "sample_type", "test_type", "method_code", "unit", "placement_status", "sub_lot")


def analyze_similarity(df: pd.DataFrame, req: SimilarityRequest) -> list[dict]:
    if df.empty:
        return []
    df = df[(df.project_id == req.project_id) & (df.data_type == "Release") & df.source_system.isin(DATA_SOURCE_MAP[req.data_source])]
    for field, selected in (("production_line_id", req.reference_lines + req.comparison_lines),
                            ("attribute_name", req.attribute_names), ("batch_number", req.batch_numbers),
                            ("test_type", req.test_types), ("placement_status", req.placement_statuses),
                            ("sample_type", [req.sample_type] if req.sample_type is not None else [])):
        if selected:
            df = df[df.get(field, pd.Series(None, index=df.index, dtype=object)).isin(selected)]
    scopes = defaultdict(list)
    for row in df.to_dict("records"):
        scopes[tuple(raw_text(row.get(field)) for field in SCOPE)].append(row)
    panels = []
    for key, rows in sorted(scopes.items(), key=lambda item: tuple(value or "" for value in item[0])):
        groups = {}
        for line in req.reference_lines + req.comparison_lines:
            selected = [row for row in rows if row.get("production_line_id") == line]
            observations = [{"batch_number": raw_text(row.get("batch_number")), "value": finite(row.get("value")),
                             "source_result_id": raw_text(row.get("source_result_id")), "group_id": raw_text(row.get("group_id"))}
                            for row in selected if finite(row.get("value")) is not None]
            values = [point["value"] for point in observations]
            mean = finite(statistics.mean(values)) if values else None
            with np.errstate(over="ignore", invalid="ignore"):
                sd = finite(np.std(values, ddof=1)) if len(values) > 1 else None
            groups[line] = {"line": line, "n": len(values), "mean": mean, "sd": sd,
                            "min": min(values) if values else None, "max": max(values) if values else None,
                            "excluded_n": len(selected) - len(values), "points": observations}
        for ref in req.reference_lines:
            reference = groups[ref]
            mean, sd = reference["mean"], reference["sd"]
            lower = finite(mean - req.reference_sd_multiplier * sd) if mean is not None and sd is not None and sd > 0 else None
            upper = finite(mean + req.reference_sd_multiplier * sd) if mean is not None and sd is not None and sd > 0 else None
            comparisons = []
            for line in req.comparison_lines:
                group = groups[line]
                differences = [finite(point["value"] - mean) for point in group["points"]] if mean is not None else []
                hits = sum(lower <= point["value"] <= upper for point in group["points"]) if lower is not None and upper is not None else None
                comparisons.append({**group, "mean_difference": finite(group["mean"] - mean) if group["mean"] is not None and mean is not None else None,
                                    "differences": differences, "band_hits": hits,
                                    "band_ratio": hits / group["n"] if hits is not None and group["n"] else None})
            warnings = []
            if not reference["n"]:
                warnings.append("当前条件下参比产线没有有效观察，不能计算差值或参考带")
            elif lower is None or upper is None:
                warnings.append("参比样本SD不足、为零或不可计算，不显示参考带及落入比例")
            if not (dict(zip(SCOPE, key))["unit"] or "").strip():
                warnings.append("结果单位未提供，仅比较存储原值；不作百分比或单位换算")
            if any(group["n"] == 0 for group in comparisons):
                warnings.append("部分比较产线在此条件下无有效观察，汇总保留空项")
            panels.append({"panel_id": _id((*key, ref)), "scope": dict(zip(SCOPE, key)), "reference": reference,
                           "comparisons": comparisons, "band": {"lower": lower, "upper": upper, "k": req.reference_sd_multiplier},
                           "warnings": warnings, "judgement": "not_evaluated"})
    return panels
