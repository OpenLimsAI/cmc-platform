# -*- coding: utf-8 -*-
"""维度/元数据端点：驱动前端筛选器，并透明暴露分类/映射覆盖率。"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_session, ping
from app.core.envelope import envelope
from app.repositories.quality_repository import StagingQualityRepository
from app.schemas.data_source import DATA_SOURCE_MAP, DataSource, source_meta

router = APIRouter(prefix="/meta", tags=["meta"])


def _repo(session: Session = Depends(get_session)) -> StagingQualityRepository:
    return StagingQualityRepository(session)


@router.get("/projects")
def projects(data_source: DataSource = "RD", repo: StagingQualityRepository = Depends(_repo)) -> dict:
    return envelope(data=repo.list_projects(DATA_SOURCE_MAP[data_source]), meta=source_meta(data_source))


@router.get("/lines")
def lines(project_id: str | None = None, data_source: DataSource = "RD", repo: StagingQualityRepository = Depends(_repo)) -> dict:
    return envelope(data=repo.list_lines(project_id, DATA_SOURCE_MAP[data_source]))


@router.get("/attributes")
def attributes(project_id: str, data_type: str | None = None, data_source: DataSource = "RD",
               repo: StagingQualityRepository = Depends(_repo)) -> dict:
    dts = [data_type] if data_type else None
    return envelope(data=repo.list_attributes(project_id, dts, DATA_SOURCE_MAP[data_source]))


@router.get("/coverage")
def coverage(project_id: str | None = None, data_source: DataSource = "RD", repo: StagingQualityRepository = Depends(_repo)) -> dict:
    """data_type 分类 + attribute 映射的覆盖率（未分类/未映射计数对用户透明）。"""
    return envelope(data=repo.coverage_report(project_id, DATA_SOURCE_MAP[data_source]), meta=source_meta(data_source))


@router.get("/database-health")
def database_health() -> dict:
    """受 require_read 保护的连接检查，不泄露异常/账号/业务表计数。"""
    try:
        return envelope(data={"db_ok": ping()})
    except Exception:
        return envelope(data={"db_ok": False}, errors=[{
            "code": "db_unavailable", "message": "分析数据库暂不可用", "detail": None,
        }])
