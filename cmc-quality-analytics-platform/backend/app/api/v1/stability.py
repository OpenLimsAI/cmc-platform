"""稳定性查看接口，无持久化操作。"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_session
from app.core.envelope import envelope
from app.repositories.quality_repository import QualityFilter, StagingQualityRepository
from app.schemas.stability import StabilityRequest
from app.schemas.data_source import DATA_SOURCE_MAP, source_meta
from app.services.dashboards.stability_service import analyze_stability, stability_options

router = APIRouter(prefix="/analysis", tags=["analysis"])


def _fetch(req, session):
    return StagingQualityRepository(session).fetch_long_table(QualityFilter(
        project_id=req.project_id, data_types=["Stability"], source_systems=DATA_SOURCE_MAP[req.data_source],
    ))


@router.post("/stability/options")
def options(req: StabilityRequest, session: Session = Depends(get_session)) -> dict:
    return envelope(data=stability_options(_fetch(req, session), req), meta=source_meta(req.data_source))


@router.post("/stability")
def stability(req: StabilityRequest, session: Session = Depends(get_session)) -> dict:
    panels = analyze_stability(_fetch(req, session), req)
    return envelope(data=panels, meta={
        "applied_filters": req.model_dump(), "row_count": sum(panel["n"] for panel in panels),
        "plotted_row_count": sum(panel["plotted_n"] for panel in panels), "panel_count": len(panels),
        **source_meta(req.data_source), "release_day0_included": False,
        "analysis_scope": "descriptive_observations_only", "approval_state": "not_evaluated",
    })
