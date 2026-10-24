from io import BytesIO
from datetime import datetime, timezone
from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from openpyxl import Workbook
from sqlalchemy.orm import Session
from app.core.database import get_session
from app.core.envelope import envelope
from app.repositories.quality_repository import QualityFilter, StagingQualityRepository
from app.schemas.similarity import SimilarityRequest
from app.schemas.data_source import DATA_SOURCE_MAP, source_meta
from app.services.dashboards.similarity_service import analyze_similarity

router = APIRouter(prefix="/analysis", tags=["analysis"])

OLD_REPORT_COLUMNS = [
    "Project", "Attribute", "Tier_Level", "Tier_Judgement", "Reference", "Test_Group",
    "Brown-Forsythe p-value", "Levene p-value", "TOST Method", "Mean_Diff",
    "ci_lower", "ci_upper", "Equivalent", "Ref_Mean", "Test_Mean",
    "Ref_Var", "Test_Var", "SE", "DF", "alpha", "conf_level", "pTOST",
]
EXTRA_REPORT_COLUMNS = [
    "Delta", "N_Ref", "N_Test", "Sample_Type", "Test_Type", "Method_Code", "Unit",
    "Placement_Status", "Sub_Lot", "Calculation_Status", "Calculation_Reason", "Approval_Status",
]


def _analyze(req: SimilarityRequest, session: Session) -> list[dict]:
    df = StagingQualityRepository(session).fetch_long_table(QualityFilter(
        project_id=req.project_id, data_types=["Release"], source_systems=DATA_SOURCE_MAP[req.data_source],
        sample_type=req.sample_type, attribute_names=req.attribute_names,
        production_line_ids=req.reference_lines + req.comparison_lines, only_mapped=False,
    ))
    return analyze_similarity(df, req)


@router.post("/similarity")
def similarity(req: SimilarityRequest, session: Session = Depends(get_session)) -> dict:
    return envelope(data=_analyze(req, session), meta={**source_meta(req.data_source),
        "applied_filters": req.model_dump(), "analysis_scope": "exploratory_raw_values",
        "judgement": "not_evaluated", "difference_direction": "comparison_minus_reference",
        "approval_status": "not_approved"})


@router.post("/similarity/report.xlsx")
def similarity_report(req: SimilarityRequest, session: Session = Depends(get_session)) -> StreamingResponse:
    """Read-only export of the exact applied filters; never a release decision."""
    panels = _analyze(req, session)
    wb = Workbook()
    ws = wb.active
    ws.title = "Equivalence Result"
    ws.append(OLD_REPORT_COLUMNS + EXTRA_REPORT_COLUMNS)
    for panel in panels:
        for group in panel["comparisons"]:
            row = group["exploratory_statistics"]
            values = [("探索：" + row[key] if key in {"Tier_Judgement", "Equivalent"} else row.get(key))
                      for key in OLD_REPORT_COLUMNS + EXTRA_REPORT_COLUMNS]
            ws.append(["'" + value if isinstance(value, str) and value.startswith(("=", "+", "-", "@")) else value for value in values])
    ws.freeze_panes = "A2"
    ws.auto_filter.ref = f"A1:AH{max(1, ws.max_row)}"
    info = wb.create_sheet("Export Info")
    info.append(["Project Code", req.project_id])
    info.append(["Export Time UTC", datetime.now(timezone.utc).isoformat(timespec="seconds")])
    info.append(["Rows", ws.max_row - 1])
    info.append(["Columns", len(OLD_REPORT_COLUMNS + EXTRA_REPORT_COLUMNS)])
    info.append(["Data Source", req.data_source])
    info.append(["Confidence Level", req.confidence_level])
    info.append(["BF Threshold", req.bf_threshold])
    info.append(["Tier2 Hit Ratio", req.tier2_hit_ratio])
    info.append(["Delta Mode", req.delta_mode])
    info.append(["Tier2 k", req.reference_sd_multiplier])
    info.append(["Manual Delta", req.manual_delta])
    info.append(["Tier1 Attributes", ", ".join(req.tier1_attribute_names)])
    info.append(["Result Status", "探索性计算，未经批准，不用于质量放行"])
    info.append(["Population", "当前来源提供的结果行；按业务约定，上游仅提供调查完成后的最终有效结果"])
    info.append(["Difference", "比较组均值 − 参比组均值"])
    info.append(["Equivalent=Not Equivalent", "仅表示当前 TOST 未证实等效，不表示已经证实不等效"])
    info.append(["Tier_Judgement=Not Similar", "仅表示当前 Tier 规则未满足，不表示已经证实产品不相似"])
    stream = BytesIO()
    wb.save(stream)
    stream.seek(0)
    return StreamingResponse(stream, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": 'attachment; filename="similarity-exploratory.xlsx"'})
