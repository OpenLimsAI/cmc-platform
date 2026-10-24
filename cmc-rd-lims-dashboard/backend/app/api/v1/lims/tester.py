# 检验员工作台路由：薄路由，SQL 在 services/lims/tester_service.py；鉴权在 router.py 统一挂 require_view
from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_analytics_db
from app.schemas.lims.tester import (
    TesterMonthlyResponse,
    TesterOption,
    TesterSummaryResponse,
    TesterTasksResponse,
)
from app.services.lims.tester_service import (
    get_tester_monthly,
    get_tester_summary,
    get_tester_tasks,
    list_testers,
)

router = APIRouter()


@router.get("/lims/tester/list", response_model=list[TesterOption], summary="检验员名单（有在手或近 12 月有完成）")
async def tester_list(
    groups: list[str] | None = Query(default=None, description="检验组过滤（按检项 group_id）"),
    db: AsyncSession = Depends(get_analytics_db),
):
    return await list_testers(db, groups=groups)


@router.get("/lims/tester/summary", response_model=TesterSummaryResponse, summary="检验员汇总卡：在手/超时限/即将超时限/本月产出")
async def tester_summary(
    tester: str = Query(..., min_length=1, description="工号（= v_test_task_monitor.tester）"),
    as_of: date = Query(default=None, description="基准日，默认今天"),
    default_target: int = Query(default=14, ge=1, description="方法无 target_days 时的默认时限（工作日）"),
    soon_days: int = Query(default=2, ge=0, description="剩余工作日 ≤ 此值算「即将超时限」"),
    db: AsyncSession = Depends(get_analytics_db),
):
    return await get_tester_summary(
        db, tester=tester, as_of=as_of or date.today(), default_target=default_target, soon_days=soon_days
    )


@router.get("/lims/tester/tasks", response_model=TesterTasksResponse, summary="检验员在手检项明细（最老收样在前）")
async def tester_tasks(
    tester: str = Query(..., min_length=1),
    as_of: date = Query(default=None),
    default_target: int = Query(default=14, ge=1),
    soon_days: int = Query(default=2, ge=0),
    db: AsyncSession = Depends(get_analytics_db),
):
    target = as_of or date.today()
    items = await get_tester_tasks(db, tester=tester, as_of=target, default_target=default_target, soon_days=soon_days)
    return {"tester": tester, "as_of": target, "items": items}


@router.get("/lims/tester/monthly", response_model=TesterMonthlyResponse, summary="检验员近 N 月完成趋势")
async def tester_monthly(
    tester: str = Query(..., min_length=1),
    months: int = Query(default=6, ge=1, le=24),
    db: AsyncSession = Depends(get_analytics_db),
):
    items = await get_tester_monthly(db, tester=tester, months=months)
    return {"tester": tester, "months": months, "items": items}
