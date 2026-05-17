# 样品相关路由：参数校验 + 调用 service，不含业务逻辑
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.schemas.lims.sample import PaginatedSampleOverview
from app.services.lims.sample_service import get_sample_overview

router = APIRouter()


@router.get("/overview", response_model=PaginatedSampleOverview, summary="样品总览（分页）")
async def sample_overview(
    page: int = Query(default=1, ge=1, description="页码"),
    size: int = Query(default=20, ge=1, le=200, description="每页条数"),
    db: AsyncSession = Depends(get_db),
):
    total, items = await get_sample_overview(db, page=page, size=size)
    return PaginatedSampleOverview(total=total, page=page, size=size, items=items)
