# 统计/健康检查路由
import csv
import io
from datetime import date, timedelta

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.schemas.lims.stats import (
    CycleTimeByMethodResponse,
    CycleTimeMonthlyTrendResponse,
    CycleTimeTrendByMethodResponse,
    DataFreshnessResponse,
    HealthResponse,
    KPIResponse,
    MethodDistributionResponse,
    MethodMonthlyResponse,
    MonthlyTrendResponse,
    OverdueResponse,
    ProjectDistributionResponse,
    SampleListResponse,
    WorkloadByMethodResponse,
    WorkloadKPIResponse,
    WorkloadResponse,
)
from app.services.lims.stats_service import (
    get_cycle_time_by_method,
    get_cycle_time_monthly_trend,
    get_cycle_time_trend_by_method,
    get_data_freshness,
    get_health_stats,
    get_kpi,
    get_method_distribution,
    get_method_monthly,
    get_monthly_trend,
    get_overdue,
    get_pending_tests,
    get_project_distribution,
    get_sample_list,
    get_workload_by_method,
    get_workload_kpi,
    get_workload_summary,
)

router = APIRouter()


@router.get("/health", response_model=HealthResponse, summary="健康检查（含数据库连通性）")
async def health_check(db: AsyncSession = Depends(get_db)):
    return await get_health_stats(db)


@router.get(
    "/lims/stats/data-freshness",
    response_model=DataFreshnessResponse,
    summary="数据新鲜度：库名 + 最后一次 ETL 写入（以 raw_rd_lims autoanalyze 为近似）",
)
async def data_freshness(db: AsyncSession = Depends(get_db)):
    return await get_data_freshness(db)


@router.get("/lims/stats/kpi", response_model=KPIResponse, summary="KPI 概览（到样/完结/未完成）")
async def kpi_overview(
    start_date: date = Query(
        default=None,
        description="起始日期，默认为今天往前 30 天",
    ),
    end_date: date = Query(
        default=None,
        description="截止日期，默认为今天",
    ),
    groups: list[str] | None = Query(
        default=None,
        description="检验组过滤，可多选，不传则查全部",
    ),
    db: AsyncSession = Depends(get_db),
):
    today = date.today()
    start = start_date or (today - timedelta(days=30))
    end = end_date or today
    return await get_kpi(db, start=start, end_date=end, groups=groups)


@router.get("/lims/stats/monthly-trend", response_model=MonthlyTrendResponse, summary="近N月趋势（样品/检项/未完成）")
async def monthly_trend(
    months: int = Query(default=12, ge=1, le=36, description="显示月数，默认12个月"),
    groups: list[str] | None = Query(default=None, description="检验组过滤，不传则查全部"),
    db: AsyncSession = Depends(get_db),
):
    items = await get_monthly_trend(db, months=months, groups=groups)
    return MonthlyTrendResponse(months=months, items=items)


@router.get(
    "/lims/stats/cycle-time/by-method",
    response_model=CycleTimeByMethodResponse,
    summary="检验周期按方法汇总（avg/median/max）",
)
async def cycle_time_by_method(
    start_date: date = Query(default=None, description="起始日期，默认今天往前30天"),
    end_date: date = Query(default=None, description="截止日期，默认今天"),
    groups: list[str] | None = Query(default=None, description="检验组过滤"),
    db: AsyncSession = Depends(get_db),
):
    today = date.today()
    start = start_date or (today - timedelta(days=30))
    end = end_date or today
    items = await get_cycle_time_by_method(db, start=start, end_date=end, groups=groups)
    return CycleTimeByMethodResponse(start_date=start, end_date=end, items=items)


@router.get(
    "/lims/stats/cycle-time/monthly-trend",
    response_model=CycleTimeMonthlyTrendResponse,
    summary="检验周期月度整体趋势",
)
async def cycle_time_monthly_trend(
    months: int = Query(default=12, ge=1, le=36, description="显示月数，默认12"),
    groups: list[str] | None = Query(default=None, description="检验组过滤"),
    db: AsyncSession = Depends(get_db),
):
    items = await get_cycle_time_monthly_trend(db, months=months, groups=groups)
    return CycleTimeMonthlyTrendResponse(months=months, items=items)


@router.get(
    "/lims/stats/cycle-time/trend-by-method",
    response_model=CycleTimeTrendByMethodResponse,
    summary="检验周期月度分方法趋势（重点方法）",
)
async def cycle_time_trend_by_method(
    months: int = Query(default=12, ge=1, le=36, description="显示月数，默认12"),
    groups: list[str] | None = Query(default=None, description="检验组过滤"),
    db: AsyncSession = Depends(get_db),
):
    items = await get_cycle_time_trend_by_method(db, months=months, groups=groups)
    return CycleTimeTrendByMethodResponse(months=months, items=items)


@router.get(
    "/lims/stats/method-distribution",
    response_model=MethodDistributionResponse,
    summary="检项方法分布（到样口径，按检项数降序）",
)
async def method_distribution(
    start_date: date = Query(default=None, description="起始日期，默认今天往前30天"),
    end_date: date = Query(default=None, description="截止日期，默认今天"),
    groups: list[str] | None = Query(default=None, description="检验组过滤，不传则查全部"),
    db: AsyncSession = Depends(get_db),
):
    today = date.today()
    start = start_date or (today - timedelta(days=30))
    end = end_date or today
    items = await get_method_distribution(db, start=start, end_date=end, groups=groups)
    return MethodDistributionResponse(start_date=start, end_date=end, items=items)


@router.get(
    "/lims/stats/project-distribution",
    response_model=ProjectDistributionResponse,
    summary="项目样品/检项分布（到样口径）",
)
async def project_distribution(
    start_date: date = Query(default=None, description="起始日期，默认今天往前30天"),
    end_date: date = Query(default=None, description="截止日期，默认今天"),
    groups: list[str] | None = Query(default=None, description="检验组过滤，不传则查全部"),
    db: AsyncSession = Depends(get_db),
):
    today = date.today()
    start = start_date or (today - timedelta(days=30))
    end = end_date or today
    items = await get_project_distribution(db, start=start, end_date=end, groups=groups)
    return ProjectDistributionResponse(start_date=start, end_date=end, items=items)


@router.get(
    "/lims/stats/workload",
    response_model=WorkloadResponse,
    summary="员工工时汇总（支持三口径：submitted/completed/pending）",
)
async def workload_summary(
    start_date: date = Query(default=None, description="起始日期，默认今天往前30天"),
    end_date: date = Query(default=None, description="截止日期，默认今天"),
    groups: list[str] | None = Query(default=None, description="检验组过滤，不传则查全部"),
    scope: str = Query(default="completed", description="口径：submitted/completed/pending"),
    db: AsyncSession = Depends(get_db),
):
    today = date.today()
    start = start_date or (today - timedelta(days=30))
    end = end_date or today
    items = await get_workload_summary(db, start=start, end_date=end, groups=groups, scope=scope)
    return WorkloadResponse(start_date=start, end_date=end, scope=scope, items=items)


@router.get(
    "/lims/stats/workload-kpi",
    response_model=WorkloadKPIResponse,
    summary="员工工时 KPI（三口径汇总：送检/已完成/未完成工时）",
)
async def workload_kpi(
    start_date: date = Query(default=None, description="起始日期，默认今天往前30天"),
    end_date: date = Query(default=None, description="截止日期，默认今天"),
    groups: list[str] | None = Query(default=None, description="检验组过滤，不传则查全部"),
    db: AsyncSession = Depends(get_db),
):
    today = date.today()
    start = start_date or (today - timedelta(days=30))
    end = end_date or today
    return await get_workload_kpi(db, start=start, end_date=end, groups=groups)


@router.get(
    "/lims/stats/workload-by-method",
    response_model=WorkloadByMethodResponse,
    summary="工时按检验方法分布（支持三口径：submitted/completed/pending）",
)
async def workload_by_method(
    start_date: date = Query(default=None, description="起始日期，默认今天往前30天"),
    end_date: date = Query(default=None, description="截止日期，默认今天"),
    groups: list[str] | None = Query(default=None, description="检验组过滤，不传则查全部"),
    scope: str = Query(default="completed", description="口径：submitted/completed/pending"),
    db: AsyncSession = Depends(get_db),
):
    today = date.today()
    start = start_date or (today - timedelta(days=30))
    end = end_date or today
    items = await get_workload_by_method(db, start=start, end_date=end, groups=groups, scope=scope)
    return WorkloadByMethodResponse(start_date=start, end_date=end, items=items)


@router.get(
    "/lims/stats/overdue",
    response_model=OverdueResponse,
    summary="超期未检情况汇总（4类计数 + 方法分布）",
)
async def overdue_summary(
    as_of: date = Query(
        default=None,
        description="统计截止日期，默认今天",
    ),
    groups: list[str] | None = Query(default=None, description="检验组过滤"),
    db: AsyncSession = Depends(get_db),
):
    target = as_of or date.today()
    return await get_overdue(db, as_of=target, groups=groups)


@router.get(
    "/lims/stats/pending-tests-csv",
    summary="导出待检测检项清单（CSV，口径与原版 export_pending_tests_to_excel 一致）",
)
async def pending_tests_csv(
    groups: list[str] | None = Query(default=None, description="检验组过滤"),
    db: AsyncSession = Depends(get_db),
):
    rows = await get_pending_tests(db, groups=groups)
    if not rows:
        buf = io.StringIO()
        buf.write("暂无待检测检项\n")
        buf.seek(0)
        return StreamingResponse(
            iter([buf.getvalue().encode("utf-8-sig")]),
            media_type="text/csv; charset=utf-8",
            headers={"Content-Disposition": "attachment; filename=\"pending_tests.csv\""},
        )

    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=list(rows[0].keys()))
    writer.writeheader()
    writer.writerows(rows)
    buf.seek(0)
    content = buf.getvalue().encode("utf-8-sig")  # BOM for Excel compatibility

    from datetime import datetime
    filename = f"pending_tests_{datetime.today().strftime('%Y%m%d')}.csv"
    return StreamingResponse(
        iter([content]),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f"attachment; filename=\"{filename}\""},
    )


@router.get(
    "/lims/stats/sample-list",
    response_model=SampleListResponse,
    summary="样本总览（分页列表，支持状态/项目筛选）",
)
async def sample_list(
    start_date: date = Query(default=None, description="到样起始日期，默认 30 天前"),
    end_date: date = Query(default=None, description="到样截止日期，默认今天"),
    groups: list[str] | None = Query(default=None, description="检验组过滤"),
    status_filter: str | None = Query(default=None, description="状态筛选：completed/inprogress/unsubmitted"),
    project_search: str | None = Query(default=None, description="项目编号/样品编号模糊搜索"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
):
    today = date.today()
    start = start_date or today - timedelta(days=30)
    end = end_date or today
    return await get_sample_list(
        db,
        start=start,
        end_date=end,
        groups=groups,
        status_filter=status_filter,
        project_search=project_search,
        page=page,
        page_size=page_size,
    )


@router.get(
    "/lims/stats/method-monthly",
    response_model=MethodMonthlyResponse,
    summary="方法月度报表（近N月按方法统计完结检项数和标准工时）",
)
async def method_monthly(
    months: int = Query(default=12, ge=1, le=36, description="统计月数"),
    groups: list[str] | None = Query(default=None, description="检验组过滤"),
    db: AsyncSession = Depends(get_db),
):
    items = await get_method_monthly(db, months=months, groups=groups)
    return MethodMonthlyResponse(months=months, items=items)
