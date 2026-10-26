"""
Project Registration System ORM 模型
对齐 DM-MDM-001 V1.0 §9
"""
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class Project(Base):
    """§9.2 项目主表"""

    __tablename__ = "project"
    __table_args__ = (
        UniqueConstraint("project_code", name="uq_project_code"),
        # SMP-RD-NUM-001 V2.1 §7.4(c)：执行类型集合（migration 0047）
        CheckConstraint(
            "project_type IN ('discovery','nonclinical','cmc','clinical',"
            "'regulatory','translational','mixed')",
            name="ck_project_type",
        ),
        # SMP V2.1 §11.3：补 cancelled（migration 0047）
        CheckConstraint(
            "status IN ('proposed','initiated','active','on_hold',"
            "'completed','terminated','cancelled')",
            name="ck_project_status",
        ),
        # SMP V2.1 §7.4 项目分类三维度 + §10.3 归属/阶段（migration 0048）
        CheckConstraint(
            "project_category IN ('asset_related','non_asset')",
            name="ck_project_category",
        ),
        CheckConstraint(
            "project_nature IN ('nme','indication_expansion','geographic_expansion',"
            "'lcm','regulatory_commitment','cmc_change','bd_evaluation','platform','discovery')",
            name="ck_project_nature",
        ),
        CheckConstraint(
            "owning_function IN ('rd','clinical','cmc','regulatory','qa','it',"
            "'bd','finance','pmo','other')",
            name="ck_owning_function",
        ),
        CheckConstraint(
            "project_phase IS NULL OR project_phase IN ('discovery','lead_opt',"
            "'ind_enabling','p1','p2','p3','filed','post_marketing')",
            name="ck_project_phase",
        ),
        # SMP V2.1 §7A 上市后变更级别（migration 0049）
        CheckConstraint(
            "regulatory_change_level IS NULL OR "
            "regulatory_change_level IN ('minor','moderate','major')",
            name="ck_regulatory_change_level",
        ),
        CheckConstraint(
            "confidentiality IN ('public','internal','restricted')",
            name="ck_project_conf",
        ),
        CheckConstraint(
            "planned_end_date IS NULL OR planned_start_date IS NULL "
            "OR planned_end_date >= planned_start_date",
            name="ck_project_dates",
        ),
        {"schema": "prs"},
    )

    project_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    project_code: Mapped[str] = mapped_column(String(32), nullable=False)

    # 基本信息
    project_name: Mapped[str] = mapped_column(String(255), nullable=False)
    project_name_en: Mapped[str | None] = mapped_column(String(255))
    project_type: Mapped[str] = mapped_column(String(32), nullable=False)
    project_phase: Mapped[str | None] = mapped_column(String(32))

    # SMP V2.1 §7.4 项目分类三维度（migration 0048）
    project_category: Mapped[str] = mapped_column(
        String(16), nullable=False, server_default="non_asset"
    )
    project_nature: Mapped[str] = mapped_column(
        String(32), nullable=False, server_default="discovery"
    )

    # SMP V2.1 §7.5 项目→资产 1:N 权威绑定（asset_related 时 service 层强制必填）
    asset_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("ars.asset.asset_id")
    )

    # 层级
    parent_project_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("prs.project.project_id")
    )
    program_name: Mapped[str | None] = mapped_column(String(128))

    # 时间
    planned_start_date: Mapped[date | None] = mapped_column(Date)
    planned_end_date: Mapped[date | None] = mapped_column(Date)
    actual_start_date: Mapped[date | None] = mapped_column(Date)
    actual_end_date: Mapped[date | None] = mapped_column(Date)

    # 资源
    project_manager_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("auth.user.user_id")
    )
    sponsor_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("auth.user.user_id")
    )
    department: Mapped[str | None] = mapped_column(String(64))
    # SMP V2.1 §10.3 受控归属（department 降级为可选自由文本）+ 参与部门（migration 0048）
    owning_function: Mapped[str] = mapped_column(
        String(32), nullable=False, server_default="rd"
    )
    participating_functions: Mapped[list | None] = mapped_column(JSONB)

    # 预算
    budget_total: Mapped[Decimal | None] = mapped_column(Numeric(18, 2))
    budget_currency: Mapped[str | None] = mapped_column(String(8), default="CNY")
    budget_actual: Mapped[Decimal | None] = mapped_column(Numeric(18, 2))

    # SMP V2.1 §10.3 审批与治理（approve 动作回填 date/year；ref 由前端提交）（migration 0048）
    approval_date: Mapped[date | None] = mapped_column(Date)
    approval_reference: Mapped[str | None] = mapped_column(String(50))
    approval_year: Mapped[int | None] = mapped_column(Integer)
    governance_approval_ref: Mapped[str | None] = mapped_column(String(50))
    status_reason: Mapped[str | None] = mapped_column(Text)

    # SMP V2.1 §10.3 外部对接（migration 0048）
    sap_wbs_mapping: Mapped[str | None] = mapped_column(String(50))
    external_contract_refs: Mapped[list | None] = mapped_column(JSONB)
    partner_reference: Mapped[str | None] = mapped_column(String(200))

    # SMP V2.1 §7A 上市后变更合规字段（migration 0049）
    regulatory_change_level: Mapped[str | None] = mapped_column(String(16))
    pre_approval_required: Mapped[bool | None] = mapped_column(Boolean)
    comparability_study_ref: Mapped[str | None] = mapped_column(String(50))
    regulatory_submission_refs: Mapped[list | None] = mapped_column(JSONB)

    # SMP V2.1 §11.8 历史遗留编号（migration 0049）
    legacy_project_id: Mapped[str | None] = mapped_column(String(32))

    # 目标与范围
    objective: Mapped[str | None] = mapped_column(Text)
    scope: Mapped[str | None] = mapped_column(Text)
    deliverables: Mapped[str | None] = mapped_column(Text)
    success_criteria: Mapped[str | None] = mapped_column(Text)

    # 状态
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="proposed")
    priority: Mapped[str | None] = mapped_column(String(16))

    # 保密
    confidentiality: Mapped[str] = mapped_column(String(16), nullable=False, default="internal")

    # 描述
    description: Mapped[str | None] = mapped_column(Text)
    notes: Mapped[str | None] = mapped_column(Text)
    extra: Mapped[dict | None] = mapped_column(JSONB)

    # 审计
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    created_by: Mapped[int] = mapped_column(BigInteger, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_by: Mapped[int] = mapped_column(BigInteger, nullable=False)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    deleted_by: Mapped[int | None] = mapped_column(BigInteger)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)


class ProjectPMLink(Base):
    """Immutable, MDM-owned one-to-one execution project association."""

    __tablename__ = "project_pm_link"
    __table_args__ = (
        UniqueConstraint("project_id", name="uq_project_pm_link_project_id"),
        UniqueConstraint("pm_project_id", name="uq_project_pm_link_pm_project_id"),
        {"schema": "prs"},
    )

    link_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("prs.project.project_id"), nullable=False)
    pm_project_id: Mapped[str] = mapped_column(String(64), nullable=False)
    pm_project_code: Mapped[str] = mapped_column(String(40), nullable=False)
    pm_project_name: Mapped[str] = mapped_column(String(200), nullable=False)
    verified_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    created_by: Mapped[int] = mapped_column(BigInteger, ForeignKey("auth.user.user_id"), nullable=False)
    change_reason: Mapped[str] = mapped_column(Text, nullable=False)


class ProjectMilestone(Base):
    """§9.3 项目里程碑"""

    __tablename__ = "project_milestone"
    __table_args__ = (
        CheckConstraint(
            "milestone_type IN ('gate','deliverable','decision')",
            name="ck_project_milestone_type",
        ),
        CheckConstraint(
            "status IN ('planned','in_progress','completed','delayed','cancelled')",
            name="ck_project_milestone_status",
        ),
        {"schema": "prs"},
    )

    milestone_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("prs.project.project_id", ondelete="CASCADE"),
        nullable=False,
    )
    milestone_name: Mapped[str] = mapped_column(String(128), nullable=False)
    milestone_type: Mapped[str] = mapped_column(String(32), nullable=False)
    planned_date: Mapped[date] = mapped_column(Date, nullable=False)
    actual_date: Mapped[date | None] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="planned")
    description: Mapped[str | None] = mapped_column(Text)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    created_by: Mapped[int] = mapped_column(BigInteger, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_by: Mapped[int] = mapped_column(BigInteger, nullable=False)


class ProjectTeam(Base):
    """§9.4 项目团队（role 为任意字符串，无 CHECK 约束）

    V1.2 评审 P3:A 决议（migration 0031）：
    唯一性约束改为 partial unique index uq_project_team_active
    WHERE left_at IS NULL（DB 层独立 index，不在 ORM 层声明）。
    业务上允许离职后用同角色再加入。
    """

    __tablename__ = "project_team"
    __table_args__ = (
        # 注：DB 实际为 partial unique index uq_project_team_active WHERE left_at IS NULL
        # ORM 不声明 UniqueConstraint，由 service 层 + DB index 双重保证
        CheckConstraint(
            "allocation_pct IS NULL OR (allocation_pct BETWEEN 0 AND 100)",
            name="ck_project_team_alloc",
        ),
        {"schema": "prs"},
    )

    team_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("prs.project.project_id", ondelete="CASCADE"),
        nullable=False,
    )
    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("auth.user.user_id"), nullable=False
    )
    role: Mapped[str] = mapped_column(String(64), nullable=False)
    function_area: Mapped[str | None] = mapped_column(String(64))
    allocation_pct: Mapped[int | None] = mapped_column(Integer)
    joined_at: Mapped[date] = mapped_column(
        Date, nullable=False, server_default=func.current_date()
    )
    left_at: Mapped[date | None] = mapped_column(Date)
    notes: Mapped[str | None] = mapped_column(Text)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    created_by: Mapped[int] = mapped_column(BigInteger, nullable=False)


class ProjectStatusHistory(Base):
    """§9.5 项目状态变更历史（保留 e_signature_id 字段为实施侧加强）"""

    __tablename__ = "project_status_history"
    __table_args__ = ({"schema": "prs"},)

    history_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("prs.project.project_id"), nullable=False
    )
    old_status: Mapped[str | None] = mapped_column(String(32))
    new_status: Mapped[str] = mapped_column(String(32), nullable=False)
    change_reason: Mapped[str] = mapped_column(Text, nullable=False)
    changed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    changed_by: Mapped[int] = mapped_column(BigInteger, nullable=False)
    e_signature_id: Mapped[int | None] = mapped_column(BigInteger)


class ProjectRelationship(Base):
    """§9.5 项目衍生/合并关系（建立/取消保留历史，双端可查询审计）"""

    __tablename__ = "project_relationship"
    __table_args__ = (
        Index(
            "uq_project_relationship_active", "from_project_id", "to_project_id", "relationship_type",
            unique=True, postgresql_where=text("deleted_at IS NULL"),
        ),
        CheckConstraint("from_project_id != to_project_id", name="ck_project_rel_self"),
        CheckConstraint(
            "relationship_type IN ('merged_into','split_from','derived_from','depends_on','blocks')",
            name="ck_project_rel_type",
        ),
        {"schema": "prs"},
    )

    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    deleted_by: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("auth.user.user_id"))

    relationship_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    from_project_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("prs.project.project_id"), nullable=False
    )
    to_project_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("prs.project.project_id"), nullable=False
    )
    relationship_type: Mapped[str] = mapped_column(String(32), nullable=False)
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    created_by: Mapped[int] = mapped_column(BigInteger, nullable=False)
