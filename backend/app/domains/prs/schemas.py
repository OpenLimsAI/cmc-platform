"""
PRS Pydantic schemas
对齐 DM-MDM-001 V1.0 §9
"""
from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

# §9.2 ck_project_type
ProjectType = Literal[
    "cmc", "preclinical", "clinical", "regulatory",
    "commercial", "platform", "other",
]

# §9.2 status
ProjectStatus = Literal[
    "proposed", "initiated", "active", "on_hold", "completed", "terminated",
]

# §9.2 priority（文档允许任意 VARCHAR(16)；按惯例限三档便于前端展示）
ProjectPriority = Literal["high", "medium", "low"]

# §9.2 confidentiality
ProjectConfidentiality = Literal["public", "internal", "restricted"]


class ProjectBase(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    project_name: str = Field(..., max_length=255)
    project_name_en: str | None = Field(None, max_length=255)
    project_type: ProjectType
    project_phase: str | None = Field(None, max_length=32)

    parent_project_id: int | None = None
    program_name: str | None = Field(None, max_length=128)

    planned_start_date: date | None = None
    planned_end_date: date | None = None
    actual_start_date: date | None = None
    actual_end_date: date | None = None

    project_manager_id: int | None = None
    sponsor_id: int | None = None
    department: str | None = Field(None, max_length=64)

    budget_total: Decimal | None = None
    budget_currency: str | None = Field(None, max_length=8)
    budget_actual: Decimal | None = None

    objective: str | None = None
    scope: str | None = None
    deliverables: str | None = None
    success_criteria: str | None = None

    priority: ProjectPriority | None = None
    confidentiality: ProjectConfidentiality = "internal"

    description: str | None = None
    notes: str | None = None
    extra: dict | None = None


class ProjectCreate(ProjectBase):
    """POST 请求体（status 起始固定为 proposed，由 service 写入）"""
    pass


class ProjectUpdate(BaseModel):
    """PUT 请求体（乐观锁 + change_reason）

    status 不在此处变更，走状态机端点。
    """

    version: int = Field(..., description="乐观锁版本号")
    change_reason: str | None = None

    project_name: str | None = Field(None, max_length=255)
    project_name_en: str | None = Field(None, max_length=255)
    project_type: ProjectType | None = None
    project_phase: str | None = Field(None, max_length=32)
    parent_project_id: int | None = None
    program_name: str | None = Field(None, max_length=128)
    planned_start_date: date | None = None
    planned_end_date: date | None = None
    actual_start_date: date | None = None
    actual_end_date: date | None = None
    project_manager_id: int | None = None
    sponsor_id: int | None = None
    department: str | None = Field(None, max_length=64)
    budget_total: Decimal | None = None
    budget_currency: str | None = Field(None, max_length=8)
    budget_actual: Decimal | None = None
    objective: str | None = None
    scope: str | None = None
    deliverables: str | None = None
    success_criteria: str | None = None
    priority: ProjectPriority | None = None
    confidentiality: ProjectConfidentiality | None = None
    description: str | None = None
    notes: str | None = None
    extra: dict | None = None


class ProjectDelete(BaseModel):
    change_reason: str = Field(..., min_length=5, max_length=2000)


class ProjectBrief(BaseModel):
    """列表项精简字段"""

    model_config = ConfigDict(from_attributes=True)

    project_code: str
    project_name: str
    project_name_en: str | None = None
    project_type: ProjectType
    project_phase: str | None = None
    department: str | None = None
    priority: str | None = None
    status: ProjectStatus
    project_manager_id: int | None = None
    sponsor_id: int | None = None
    parent_project_id: int | None = None
    program_name: str | None = None
    confidentiality: ProjectConfidentiality | None = None
    planned_start_date: date | None = None
    planned_end_date: date | None = None
    created_at: datetime
    updated_at: datetime


class ProjectDetail(ProjectBase):
    """详情响应"""

    project_id: int
    project_code: str
    status: ProjectStatus
    version: int

    created_at: datetime
    created_by: int
    updated_at: datetime
    updated_by: int


class ProjectFilter(BaseModel):
    """列表查询过滤"""

    q: str | None = None
    project_type: str | None = None
    project_phase: str | None = None
    status: str | None = None
    department: str | None = None
    project_manager_id: int | None = None
    priority: str | None = None
    program_name: str | None = None
    parent_project_id: int | None = None
    confidentiality: str | None = None
    budget_currency: str | None = None


# ============== 状态机 ==============
class ProjectStatusChange(BaseModel):
    change_reason: str = Field(..., min_length=5, max_length=2000)
    password: str | None = Field(
        None, min_length=1, max_length=128,
        description="当前用户密码；仅 GxP 关键动作要求",
    )
    signature_reason: str | None = Field(
        None, min_length=1, max_length=2000,
        description="电子签名理由（21 CFR Part 11 §11.50，独立于 change_reason）；"
                    "未传则 fallback 到 change_reason",
    )


# ============== 里程碑（§9.3）==============
MilestoneType = Literal["gate", "deliverable", "decision"]
MilestoneStatus = Literal["planned", "in_progress", "completed", "delayed", "cancelled"]


class ProjectMilestoneBase(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    milestone_name: str = Field(..., max_length=128)
    milestone_type: MilestoneType | None = None
    planned_date: date  # §9.3 NOT NULL
    actual_date: date | None = None
    status: MilestoneStatus = "planned"
    description: str | None = None


class ProjectMilestoneCreate(ProjectMilestoneBase):
    pass


class ProjectMilestoneUpdate(BaseModel):
    change_reason: str | None = None

    milestone_name: str | None = Field(None, max_length=128)
    milestone_type: MilestoneType | None = None
    planned_date: date | None = None
    actual_date: date | None = None
    status: MilestoneStatus | None = None
    description: str | None = None


class ProjectMilestoneDelete(BaseModel):
    """DELETE 里程碑请求体（要求 change_reason 写入审计）"""

    change_reason: str = Field(..., min_length=5, max_length=2000)


class ProjectMilestone(ProjectMilestoneBase):
    milestone_id: int
    project_id: int
    created_at: datetime
    created_by: int
    updated_at: datetime
    updated_by: int


# ============== 团队（§9.4：role 任意字符串，无 CHECK）==============
class ProjectTeamMemberCreate(BaseModel):
    user_id: int
    role: str = Field(..., max_length=64)
    function_area: str | None = Field(None, max_length=64)
    allocation_pct: int | None = Field(None, ge=0, le=100)
    notes: str | None = None


class ProjectTeamMemberRemove(BaseModel):
    change_reason: str | None = Field(None, max_length=2000)


class ProjectTeamMember(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    team_id: int
    project_id: int
    user_id: int
    role: str
    function_area: str | None = None
    allocation_pct: int | None = None
    joined_at: date
    left_at: date | None = None
    notes: str | None = None
    created_at: datetime
