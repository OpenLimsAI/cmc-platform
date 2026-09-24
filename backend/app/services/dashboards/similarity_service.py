"""Read-only comparisons of upstream final results; OOS/OOT resolution belongs upstream.

The current repositories do not independently verify final-result eligibility.
No inferred equivalence or unit conversion is performed here.
"""
from collections import defaultdict
import statistics
import numpy as np
import pandas as pd
from scipy import stats
from app.schemas.similarity import SimilarityRequest
from app.schemas.data_source import DATA_SOURCE_MAP
from app.services.dashboards.stability_service import raw_text, finite, _id
from app.services.stats.equivalence import compare_equivalence, levene_test
from app.services.stats.similarity import evaluate_similarity_pair

SCOPE = ("attribute_name", "attribute_raw", "sample_type", "test_type", "method_code", "unit", "placement_status", "sub_lot")


def _exploratory_row(req: SimilarityRequest, scope: dict, ref: dict, group: dict) -> dict:
    """Old report columns, using corrected statistics and the current isolated scope.

    These inputs are user-selected exploratory limits, not approved specifications.
    """
    reference = [point["value"] for point in ref["points"]]
    comparison = [point["value"] for point in group["points"]]
    tier = "Tier1" if scope["attribute_name"] in req.tier1_attribute_names else "Tier2"
    multiplier = 1.5 if tier == "Tier1" else req.reference_sd_multiplier
    delta = req.manual_delta if req.delta_mode == "manual" else finite(multiplier * ref["sd"]) if ref["sd"] is not None else None
    valid_delta = delta is not None and delta > 0
    tier_result = evaluate_similarity_pair(
        reference, comparison, tier=tier, delta=delta, confidence_level=req.confidence_level,
        variance_method="brown_forsythe", prop_thresh=req.tier2_hit_ratio,
        bf_threshold=req.bf_threshold,
    ) if valid_delta else None
    tost = (tier_result if tier == "Tier1" else compare_equivalence(
        reference, comparison, delta=delta, confidence_level=req.confidence_level,
        variance_method="brown_forsythe", bf_threshold=req.bf_threshold,
    )) if valid_delta else None
    if tost:
        bf_p, lev_p = tost["bf_p_value"], tost["levene_p_value"]
    else:
        bf_p, lev_p, _ = levene_test(reference, comparison, bf_threshold=req.bf_threshold)
    equivalent = tost["equivalent"] if tost else None
    method = tost["variance_method"] if tost else None
    calculation = tier_result if tier == "Tier2" else tost
    return {
        "Project": req.project_id, "Attribute": scope["attribute_name"], "Tier_Level": tier,
        "Tier_Judgement": tier_result["judgement"] if tier_result else "Unknown",
        "Reference": ref["line"], "Test_Group": group["line"],
        "Brown-Forsythe p-value": finite(bf_p), "Levene p-value": finite(lev_p),
        "TOST Method": ("TOST2 (pooled)" if method == "pooled" else "TOST1 (Welch)" if method == "welch" else None),
        "Mean_Diff": tost["mean_diff"] if tost else group["mean_difference"],
        "ci_lower": tost["ci_low"] if tost else None, "ci_upper": tost["ci_high"] if tost else None,
        "Equivalent": "Equivalent" if equivalent is True else "Not Equivalent" if equivalent is False else "Unknown",
        "Ref_Mean": ref["mean"], "Test_Mean": group["mean"],
        "Ref_Var": finite(ref["sd"] ** 2) if ref["sd"] is not None else None,
        "Test_Var": finite(group["sd"] ** 2) if group["sd"] is not None else None,
        "SE": tost["se"] if tost else None, "DF": tost["df"] if tost else None,
        "alpha": (1 - req.confidence_level) / 2, "conf_level": req.confidence_level,
        "pTOST": tost["p_tost"] if tost else None,
        "Delta": delta if valid_delta else None, "N_Ref": ref["n"], "N_Test": group["n"],
        "Sample_Type": scope["sample_type"], "Test_Type": scope["test_type"],
        "Method_Code": scope["method_code"], "Unit": scope["unit"],
        "Placement_Status": scope["placement_status"], "Sub_Lot": scope["sub_lot"],
        "Calculation_Status": calculation["status"] if calculation else "not_evaluable",
        "Calculation_Reason": calculation["reason"] if calculation else "delta_unavailable",
        "Approval_Status": "探索性计算，未批准",
    }


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
                half_width = finite(stats.t.ppf((1 + req.confidence_level) / 2, len(values) - 1) * sd / np.sqrt(len(values))) if sd is not None else None
            groups[line] = {"line": line, "n": len(values), "mean": mean, "sd": sd,
                            "mean_ci_lower": finite(mean - half_width) if mean is not None and half_width is not None else None,
                            "mean_ci_upper": finite(mean + half_width) if mean is not None and half_width is not None else None,
                            "min": min(values) if values else None, "max": max(values) if values else None,
                            "excluded_n": len(selected) - len(values), "points": observations}
        for ref in req.reference_lines:
            reference = groups[ref]
            mean, sd = reference["mean"], reference["sd"]
            scope = dict(zip(SCOPE, key))
            tier = "Tier1" if scope["attribute_name"] in req.tier1_attribute_names else "Tier2"
            band_basis = "manual_delta" if tier == "Tier2" and req.delta_mode == "manual" else "reference_sd"
            half_width = (req.manual_delta if band_basis == "manual_delta" else
                          finite(req.reference_sd_multiplier * sd) if sd is not None and sd > 0 else None)
            if reference["n"] < 2 or mean is None or half_width is None:
                half_width = None
            lower = finite(mean - half_width) if half_width is not None else None
            upper = finite(mean + half_width) if half_width is not None else None
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
                warnings.append("参比样本不足或参考带界值不可计算，不显示参考带及落入比例")
            if not (scope["unit"] or "").strip():
                warnings.append("结果单位未提供，仅比较存储原值；不作百分比或单位换算")
            if any(group["n"] == 0 for group in comparisons):
                warnings.append("部分比较产线在此条件下无有效观察，汇总保留空项")
            for group in comparisons:
                group["exploratory_statistics"] = _exploratory_row(req, scope, reference, group)
            panels.append({"panel_id": _id((*key, ref)), "scope": scope, "reference": reference,
                           "comparisons": comparisons, "band": {"lower": lower, "upper": upper,
                           "half_width": half_width, "basis": band_basis, "k": req.reference_sd_multiplier},
                           "warnings": warnings, "judgement": "not_evaluated"})
    return panels
