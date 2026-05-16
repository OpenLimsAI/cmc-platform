"""/api/v1/dashboard 路由（Phase 5.B 真实部件）

- GET /api/v1/dashboard/summary  — 4 域 totals + 分布 + 30 天趋势
- GET /api/v1/dashboard/gantt    — 项目甘特数据（含里程碑）

权限：仅需登录（信息聚合，不暴露具体记录）；普通用户可看。
"""
from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.responses import success
from app.domains.auth.models import User
from app.shared.dashboard_service import DashboardService
from app.shared.permissions import get_current_user

router = APIRouter()


@router.get("/summary", summary="仪表盘聚合统计（totals + 分布 + 趋势）")
async def get_summary(
    request: Request,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = DashboardService(db)
    data = await service.get_summary()
    return success(
        data=data,
        request_id=getattr(request.state, "request_id", None),
    )


@router.get("/gantt", summary="项目甘特数据（含里程碑）")
async def get_gantt(
    request: Request,
    project_status: str | None = Query(None),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = DashboardService(db)
    items = await service.get_gantt(project_status=project_status)
    return success(
        data=items,
        request_id=getattr(request.state, "request_id", None),
    )
