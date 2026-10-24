# 元数据路由：返回筛选器所需的枚举值（检验组列表等）
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select, distinct, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_analytics_db
from app.models.lims.views import TestTaskMonitor

router = APIRouter()


@router.get("/lims/meta/groups", response_model=list[str], summary="获取全部检验组列表")
async def list_groups(db: AsyncSession = Depends(get_analytics_db)):
    result = await db.execute(
        select(distinct(TestTaskMonitor.group_id))
        .where(TestTaskMonitor.group_id.isnot(None))
        .where(TestTaskMonitor.group_id != "")
        .order_by(TestTaskMonitor.group_id)
    )
    return [r for (r,) in result.all()]


class MethodTargetItem(BaseModel):
    method_code: str
    method_name: str | None = None
    target_days: int | None = None


@router.get("/lims/meta/method-targets", response_model=list[MethodTargetItem], summary="获取各检验方法的目标检验期限")
async def list_method_targets(db: AsyncSession = Depends(get_analytics_db)):
    result = await db.execute(
        text("SELECT method_code, method_name, target_days FROM mart.dim_method ORDER BY method_code")
    )
    return [MethodTargetItem(method_code=r.method_code, method_name=r.method_name, target_days=r.target_days)
            for r in result.mappings()]
