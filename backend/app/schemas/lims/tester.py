# 检验员工作台响应模型（口径见 docs/tester_workbench.md）
from datetime import date, datetime

from pydantic import BaseModel


class TesterOption(BaseModel):
    """下拉框一项：有在手检项或近 12 个月有完成记录的检验员"""
    employee_id: str
    employee_name: str | None = None   # dim_employee 无记录时为 None，前端回落工号
    group_ids: list[str] = []          # 该员工检项涉及的检验组（来自检项 group_id，非 dim_employee）
    pending_n: int = 0                 # 当前在手检项数


class TesterSummaryResponse(BaseModel):
    tester: str
    employee_name: str | None = None
    as_of: date
    default_target: int
    soon_days: int
    # 当前在手
    pending_n: int                     # 在手检项（结存口径 V+C）
    over_target_n: int                 # 已超时限（收样至今工作日 > 检验时限）
    due_soon_n: int                    # 即将超时限（未超且剩余工作日 ≤ soon_days）
    unauthorized_n: int                # 其中检完待授权（C）
    oldest_received_dt: date | None = None  # 在手里最老一条的收样日
    # 本月（1 日 ~ as_of）
    month_completed_n: int
    month_std_hours: float
    month_avg_cycle_days: float | None = None
    # 上月整月，用于"较上月"
    prev_month_completed_n: int
    prev_month_avg_cycle_days: float | None = None


class TesterTaskItem(BaseModel):
    test_id: str
    sample_id: str | None = None
    project_id: str | None = None
    sample_name: str | None = None
    batch_number: str | None = None
    group_id: str | None = None
    method_code: str | None = None
    method_name: str | None = None
    sample_received_dt: datetime | None = None
    assigned_dt: datetime | None = None
    test_completed_dt: datetime | None = None
    test_status: str | None = None
    bucket: str                        # inprogress（进行中）/ unauthorized（检完待授权）
    elapsed_biz_days: int              # 收样日 → as_of 工作日
    target_days: int                   # 该方法检验时限（无则 default_target）
    target_is_default: bool            # True = 方法没填时限，用的兜底值
    remaining_biz_days: int            # target - elapsed，负数即已超
    is_over_target: bool
    is_due_soon: bool


class TesterTasksResponse(BaseModel):
    tester: str
    as_of: date
    items: list[TesterTaskItem]


class TesterMonthlyItem(BaseModel):
    ym: str
    completed_n: int
    std_hours: float
    avg_cycle_days: float | None = None


class TesterMonthlyResponse(BaseModel):
    tester: str
    months: int
    items: list[TesterMonthlyItem]
