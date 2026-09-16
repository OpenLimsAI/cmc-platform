from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.core.database import get_session
from app.core.envelope import envelope
from app.repositories.quality_repository import QualityFilter, StagingQualityRepository
from app.schemas.similarity import SimilarityRequest
from app.schemas.data_source import DATA_SOURCE_MAP, source_meta
from app.services.dashboards.similarity_service import analyze_similarity

router = APIRouter(prefix="/analysis", tags=["analysis"])


@router.post("/similarity")
def similarity(req: SimilarityRequest, session: Session = Depends(get_session)) -> dict:
    df = StagingQualityRepository(session).fetch_long_table(QualityFilter(
        project_id=req.project_id, data_types=["Release"], source_systems=DATA_SOURCE_MAP[req.data_source],
        sample_type=req.sample_type, attribute_names=req.attribute_names,
        production_line_ids=req.reference_lines + req.comparison_lines, only_mapped=False,
    ))
    return envelope(data=analyze_similarity(df, req), meta={**source_meta(req.data_source),
        "applied_filters": req.model_dump(), "analysis_scope": "descriptive_raw_values",
        "judgement": "not_evaluated", "difference_direction": "comparison_minus_reference"})
