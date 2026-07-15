"""
PRS Pydantic schemas
对齐 DM-MDM-001 V1.0 §9
"""
from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.domains.audit.schemas import SignatureBlock

# SMP-RD-NUM-001 V2.1 §7.4(c) 执行类型（migration 0047）
ProjectType = Literal[
    "discovery", "nonclinical", "cmc", "clinical",
    "regulatory", "translational", "mixed",
]

# SMP V2.1 §11.3 status（补 cancelled，migration 0047）
ProjectStatus = Literal[
    "proposed", "initiated", "active", "on_hold",
    "completed", "terminated", "cancelled",
]

# SMP V2.1 §7.4(a) 是否关联资产（migration 0048）
ProjectCategory = Literal["asset_related", "non_asset"]

# SMP V2.1 §7.4(b) portfolio 性质
ProjectNature = Literal[
    "nme", "indication_expansion", "geographic_expansion", "lcm",
    "regulatory_commitment", "cmc_change", "bd_evaluation", "platform", "discovery",
]

# SMP V2.1 §10.3 受控归属
OwningFunction = Literal[
    "rd", "clinical", "cmc", "regulatory", "qa", "it", "bd", "finance", "pmo", "other",
]

# SMP V2.1 §10.3 临床阶段（由自由文本改受控）
ProjectPhase = Literal[
    "discovery", "lead_opt", "ind_enabling", "p1", "p2", "p3", "filed", "post_marketing",
]

# SMP V2.1 §7A / 附录E 上市后变更级别（migration 0049）
RegulatoryChangeLevel = Literal["minor", "moderate", "major"]

# §9.2 priority（文档允许任意 VARCHAR(16)；按惯例限三档便于前端展示）
ProjectPriority = Literal["high", "medium", "low"]

# §9.2 confidentiality
ProjectConfidentiality = Literal["public", "internal", "restricted"]


class ProjectBase(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    project_name: str = Field(..., max_length=255)
    project_name_en: str | None = Field(None, max_length=255)
    project_type: ProjectType
    project_phase: ProjectPhase | None = None

    # SMP V2.1 §7.4 分类三维度。API 层给 SMP-有效默认值（与 DB server_default 一致），
    # "显式选择"由前端表单必填强制；避免打穿大量既有创建方（测试/seed）。
    project_category: ProjectCategory = "non_asset"
    project_nature: ProjectNature = "discovery"
    owning_function: OwningFunction = "rd"
    participating_functions: list[OwningFunction] | None = None
    # §7.5 资产绑定（asset_related 时 service 层强制必填）
    asset_id: int | None = None

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

    # SMP V2.1 §10.3 审批/治理编号（approval_date/year 系统回填，见 Detail）+ 外部对接
    approval_reference: str | None = Field(None, max_length=50)
    governance_approval_ref: str | None = Field(None, max_length=50)
    status_reason: str | None = None
    sap_wbs_mapping: str | None = Field(None, max_length=50)
    external_contract_refs: list[str] | None = None
    partner_reference: str | None = Field(None, max_length=200)

    # SMP V2.1 §7A 上市后变更（nature=cmc_change/lcm 时 service 强制变更级别）
    regulatory_change_level: RegulatoryChangeLevel | None = None
    pre_approval_required: bool | None = None
    comparability_study_ref: str | None = Field(None, max_length=50)
    regulatory_submission_refs: list[str] | None = None
    # SMP V2.1 §11.8 历史遗留编号
    legacy_project_id: str | None = Field(None, max_length=32)

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
    project_phase: ProjectPhase | None = None
    project_category: ProjectCategory | None = None
    project_nature: ProjectNature | None = None
    owning_function: OwningFunction | None = None
    participating_functions: list[OwningFunction] | None = None
    asset_id: int | None = None
    approval_reference: str | None = Field(None, max_length=50)
    governance_approval_ref: str | None = Field(None, max_length=50)
    status_reason: str | None = None
    sap_wbs_mapping: str | None = Field(None, max_length=50)
    external_contract_refs: list[str] | None = None
    partner_reference: str | None = Field(None, max_length=200)
    regulatory_change_level: RegulatoryChangeLevel | None = None
    pre_approval_required: bool | None = None
    comparability_study_ref: str | None = Field(None, max_length=50)
    regulatory_submission_refs: list[str] | None = None
    legacy_project_id: str | None = Field(None, max_length=32)
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
    project_phase: ProjectPhase | None = None
    project_category: ProjectCategory
    project_nature: ProjectNature
    owning_function: OwningFunction
    asset_id: int | None = None
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

    # SMP V2.1 §10.3 系统回填字段（approve 动作写入，只读）
    approval_date: date | None = None
    approval_year: int | None = None

    created_at: datetime
    created_by: int
    updated_at: datetime
    updated_by: int


class ProjectFilter(BaseModel):
    """列表查询过滤"""

    q: str | None = None
    project_type: str | None = None
    project_phase: str | None = None
    project_category: str | None = None
    project_nature: str | None = None
    owning_function: str | None = None
    asset_id: int | None = None
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
    """状态机端点请求体（API-MDM-001 V1.1 §7.4）

    GxP 关键动作（approve / complete / terminate）必传 signature 嵌套对象。
    """

    comment: str = Field(..., min_length=5, max_length=2000)
    signature: SignatureBlock | None = None


# ============== 里程碑（§9.3）==============
MilestoneType = Literal["gate", "deliverable", "decision"]
MilestoneStatus = Literal["planned", "in_progress", "completed", "delayed", "cancelled"]


class ProjectMilestoneBase(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    milestone_name: str = Field(..., max_length=128)
    milestone_type: MilestoneType  # §9.3 NOT NULL，三值 gate/deliverable/decision
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

    @field_validator("milestone_type")
    @classmethod
    def _milestone_type_not_null(cls, v: str | None) -> str | None:
        # DB 列 NOT NULL：Optional 仅表示"不修改该字段"，显式置空拒绝（防 500）
        if v is None:
            raise ValueError("milestone_type 不可置空")
        return v


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


# ============== 项目关系（§9.5 / SMP §11.4-11.6，migration 0031 建表）==============
RelationshipType = Literal[
    "merged_into", "split_from", "derived_from", "depends_on", "blocks",
]


class ProjectRelationshipCreate(BaseModel):
    to_project_code: str = Field(..., max_length=32)
    relationship_type: RelationshipType
    notes: str | None = None


class ProjectRelationshipItem(BaseModel):
    """关系项：direction 标明当前项目在关系中是主动方(out)还是被动方(in)"""

    relationship_id: int
    relationship_type: RelationshipType
    direction: Literal["outgoing", "incoming"]
    other_project_code: str
    other_project_name: str
    notes: str | None = None
    created_at: datetime


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
