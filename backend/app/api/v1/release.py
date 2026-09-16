# -*- coding: utf-8 -*-
"""放行趋势分析端点。"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_session
from app.core.envelope import envelope
from app.repositories.quality_repository import QualityFilter, StagingQualityRepository
from app.schemas.release import DATA_SOURCE_MAP, ReleaseRequest
from app.schemas.data_source import DataSource, source_meta
from app.services.dashboards.release_service import analyze_release, analyze_qc_release
from app.services.dashboards.excel_release_service import analyze_excel_release
from app.services.dashboards.release_filters import filter_release_rows, release_options

router = APIRouter(prefix="/analysis", tags=["analysis"])


@router.get("/release/options")
def options(project_id: str, data_source: DataSource = "RD", session: Session = Depends(get_session)) -> dict:
    df = StagingQualityRepository(session).fetch_long_table(QualityFilter(
        project_id=project_id, data_types=["Release"], source_systems=DATA_SOURCE_MAP[data_source],
    ))
    return envelope(data=release_options(df), meta=source_meta(data_source))


@router.post("/release")
def release(req: ReleaseRequest, session: Session = Depends(get_session)) -> dict:
    repo = StagingQualityRepository(session)
    flt = QualityFilter(
        project_id=req.project_id,
        sample_type=req.sample_type,
        production_line_ids=req.production_line_ids,
        attribute_names=req.attribute_names,
        data_types=["Release"],
        source_systems=DATA_SOURCE_MAP[req.data_source],
        only_mapped=False,  # 未映射的检测项用原始名展示，保证 RD 数据能完整提取
    )
    df = repo.fetch_long_table(flt)
    if req.data_source == "EXCEL":
        results, row_count = analyze_excel_release(df, req)
    else:
        df = filter_release_rows(df, req)
        analyze = analyze_qc_release if req.data_source == "QC" else analyze_release
        results = analyze(df, project_id=req.project_id, sample_type=req.sample_type,
                          capability_mode=req.capability_mode)
        row_count = len(df)
    return envelope(
        data=results,
        meta={
            "project_id": req.project_id,
            **source_meta(req.data_source),
            "attribute_count": len(results),
            "row_count": row_count,
            "applied_filters": req.model_dump(),
            "year_basis": "legacy_batch_number_inference",
            "reference_scope": req.sd_reference_mode if req.data_source == "EXCEL" else "current_filtered_rows",
        },
    )
