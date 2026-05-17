# 统计/健康检查相关接口的响应 schema
from datetime import date, datetime

from pydantic import BaseModel


class HealthResponse(BaseModel):
    status: str
    db: str
    sample_count: int


class DataFreshnessResponse(BaseModel):
    db_name: str
    last_etl_at: datetime | None = None


class KPIResponse(BaseModel):
    sample_n: int        # 样品数（到样口径）
    test_n: int          # 检项数（到样口径）
    done_test_n: int     # 已完成检项（完结口径）
    pending_test_n: int  # 截止 end_date 未完成检项数
    start_date: date
    end_date: date


class MonthlyTrendItem(BaseModel):
    ym: str              # 月份，格式 YYYY-MM
    month_end: date      # 当月统计截止日（当前月为今天，历史月为月末）
    sample_n: int        # 到样样品数
    test_n: int          # 到样检项数
    pending_test_n: int  # 截止该月末未完成检项数


class MonthlyTrendResponse(BaseModel):
    months: int
    items: list[MonthlyTrendItem]


# ---------- 检验周期 ----------

class CycleTimeByMethodItem(BaseModel):
    method_name: str
    method_code: str | None = None
    completed_n: int
    avg_cycle_days: float | None = None
    median_cycle_days: float | None = None
    max_cycle_days: int | None = None


class CycleTimeByMethodResponse(BaseModel):
    start_date: date
    end_date: date
    items: list[CycleTimeByMethodItem]


class CycleTimeMonthlyTrendItem(BaseModel):
    ym: str
    completed_n: int
    avg_cycle_days: float | None = None
    median_cycle_days: float | None = None


class CycleTimeMonthlyTrendResponse(BaseModel):
    months: int
    items: list[CycleTimeMonthlyTrendItem]


class CycleTimeTrendByMethodItem(BaseModel):
    ym: str
    method_name: str
    completed_n: int
    avg_cycle_days: float | None = None
    median_cycle_days: float | None = None


class CycleTimeTrendByMethodResponse(BaseModel):
    months: int
    items: list[CycleTimeTrendByMethodItem]


# ---------- 超期未检 ----------

class OverdueSummary(BaseModel):
    unsubmitted: int   # 请验未送样（test_status='U'）
    unassigned: int    # 收样未分配（status='V'，无 tester）
    inprogress: int    # 分配未完成（status='V'，有 tester，未完成）
    unauthorized: int  # 检毕未授权（test_status='C'）


class OverdueMethodItem(BaseModel):
    method_name: str | None = None
    test_count: int


class OverdueResponse(BaseModel):
    as_of: date
    summary: OverdueSummary
    incomplete_distribution: list[OverdueMethodItem]   # 未完成检项按方法分布
    unsubmitted_distribution: list[OverdueMethodItem]  # 未送样检项按方法分布


# ---------- 员工工时汇总 ----------

class WorkloadItem(BaseModel):
    tester: str
    employee_name: str | None = None
    department: str | None = None
    test_n: int
    total_minutes: int
    total_hours: float


class WorkloadResponse(BaseModel):
    start_date: date
    end_date: date
    scope: str  # submitted / completed / pending
    items: list[WorkloadItem]


class WorkloadKPIResponse(BaseModel):
    start_date: date
    end_date: date
    submitted_hours: float
    completed_hours: float
    pending_hours: float
    efficiency: float | None = None  # completed / submitted
    missing_methods: list[str] = []  # method_codes with no std_minutes in dim_method


class WorkloadByMethodItem(BaseModel):
    method_name: str
    method_code: str | None = None
    test_n: int
    total_hours: float


class WorkloadByMethodResponse(BaseModel):
    start_date: date
    end_date: date
    items: list[WorkloadByMethodItem]


# ---------- 项目分布 ----------

class ProjectDistributionItem(BaseModel):
    project_id: str
    sample_n: int
    test_n: int
    std_hours: float


class ProjectDistributionResponse(BaseModel):
    start_date: date
    end_date: date
    items: list[ProjectDistributionItem]


# ---------- 方法分布 ----------

class MethodDistributionItem(BaseModel):
    method_name: str
    method_code: str | None = None
    test_count: int


class MethodDistributionResponse(BaseModel):
    start_date: date
    end_date: date
    items: list[MethodDistributionItem]


# ---------- 样本总览 ----------

class SampleListItem(BaseModel):
    sample_id: str
    project_id: str | None = None
    sample_name: str | None = None
    batch_number: str | None = None
    sample_type: str | None = None
    received_dt: date | None = None
    completed_dt: date | None = None
    authorised_dt: date | None = None
    tester: str | None = None
    group_id: str | None = None
    status: str | None = None


class SampleListResponse(BaseModel):
    total: int
    page: int
    page_size: int
    items: list[SampleListItem]


# ---------- 方法月度报表 ----------

class MethodMonthlyItem(BaseModel):
    ym: str         # YYYY-MM
    method_name: str
    method_code: str | None = None
    test_n: int
    std_hours: float


class MethodMonthlyResponse(BaseModel):
    months: int
    items: list[MethodMonthlyItem]
