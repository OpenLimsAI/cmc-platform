"""prs init: project / project_milestone / project_team / project_status_history

Revision ID: 0006_prs_init
Revises: 0005_audit_trigger_v2
Create Date: 2026-05-11 17:00:00.000000

PRS（Project Registration System）4 张表，对齐 DM-MDM-001 §8。
schema `prs` 已由 deploy/postgres/init/01-init.sql 创建。

枚举设计：
  project.project_type: discovery / preclinical / clinical / cmc / tech_transfer / lifecycle / other
  project.phase:        discovery / preclinical / phase_1 / phase_2 / phase_3 / submission /
                        approved / marketed / discontinued / na
  project.status:       draft / planned / active / on_hold / completed / terminated
  milestone.type:       gate / deliverable / regulatory / clinical / cmc / other
  milestone.status:     pending / achieved / missed / cancelled
  team.role_in_project: pm / cmc_lead / qa_lead / regulatory_lead / clinical_lead /
                        research / member / observer

project_team 用独立自增 team_id（M2.1 设计决策：便于审计 entity_id 唯一可指，便于成员"重新加入"二次记录）。
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0006_prs_init"
down_revision: str | None = "0005_audit_trigger_v2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # ============== meta.code_sequence 增加 project 序列 ==============
    op.execute("""
        INSERT INTO meta.code_sequence (sequence_name, prefix, padding_length, description)
        VALUES ('project', 'PRJ-', 7, 'Project 编码序列：PRJ-0000001 ...')
        ON CONFLICT (sequence_name) DO NOTHING;
    """)

    # ============== prs.project ==============
    op.create_table(
        "project",
        sa.Column("project_id", sa.BigInteger, sa.Identity(always=True), primary_key=True),
        sa.Column("project_code", sa.String(32), nullable=False),
        sa.Column("project_name", sa.String(255), nullable=False),
        sa.Column("project_name_en", sa.String(255)),
        sa.Column("project_type", sa.String(32), nullable=False),
        sa.Column("phase", sa.String(32)),
        sa.Column("therapeutic_area", sa.String(128)),
        sa.Column("indication", sa.String(255)),
        sa.Column("planned_start_date", sa.Date),
        sa.Column("planned_end_date", sa.Date),
        sa.Column("actual_start_date", sa.Date),
        sa.Column("actual_end_date", sa.Date),
        sa.Column("status", sa.String(32), nullable=False, server_default="draft"),
        sa.Column("project_owner_id", sa.BigInteger),
        sa.Column("program_director_id", sa.BigInteger),
        sa.Column("description", sa.Text),
        sa.Column("notes", sa.Text),
        sa.Column("extra", postgresql.JSONB),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.Column("created_by", sa.BigInteger, nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.Column("updated_by", sa.BigInteger, nullable=False),
        sa.Column("approved_at", sa.DateTime(timezone=True)),
        sa.Column("approved_by", sa.BigInteger),
        sa.Column("deleted_at", sa.DateTime(timezone=True)),
        sa.Column("deleted_by", sa.BigInteger),
        sa.Column("version", sa.Integer, nullable=False, server_default="1"),
        sa.UniqueConstraint("project_code", name="uq_project_project_code"),
        sa.CheckConstraint(
            "project_type IN ('discovery','preclinical','clinical','cmc','tech_transfer',"
            "'lifecycle','other')",
            name="ck_project_project_type",
        ),
        sa.CheckConstraint(
            "phase IS NULL OR phase IN ('discovery','preclinical','phase_1','phase_2','phase_3',"
            "'submission','approved','marketed','discontinued','na')",
            name="ck_project_phase",
        ),
        sa.CheckConstraint(
            "status IN ('draft','planned','active','on_hold','completed','terminated')",
            name="ck_project_status",
        ),
        schema="prs",
    )
    op.create_index(
        "ix_project_project_type", "project", ["project_type"],
        postgresql_where=sa.text("deleted_at IS NULL"), schema="prs",
    )
    op.create_index(
        "ix_project_status", "project", ["status"],
        postgresql_where=sa.text("deleted_at IS NULL"), schema="prs",
    )
    op.create_index(
        "ix_project_phase", "project", ["phase"],
        postgresql_where=sa.text("deleted_at IS NULL"), schema="prs",
    )
    op.create_index(
        "ix_project_owner", "project", ["project_owner_id"],
        postgresql_where=sa.text("deleted_at IS NULL"), schema="prs",
    )
    op.execute(
        "CREATE INDEX ix_project_project_name "
        "ON prs.project USING gin(project_name gin_trgm_ops)"
    )

    # ============== prs.project_milestone ==============
    op.create_table(
        "project_milestone",
        sa.Column("milestone_id", sa.BigInteger, sa.Identity(always=True), primary_key=True),
        sa.Column("project_id", sa.BigInteger,
                  sa.ForeignKey("prs.project.project_id"), nullable=False),
        sa.Column("milestone_name", sa.String(255), nullable=False),
        sa.Column("milestone_type", sa.String(32), nullable=False),
        sa.Column("planned_date", sa.Date),
        sa.Column("actual_date", sa.Date),
        sa.Column("status", sa.String(16), nullable=False, server_default="pending"),
        sa.Column("description", sa.Text),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.Column("created_by", sa.BigInteger, nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.Column("updated_by", sa.BigInteger, nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True)),
        sa.Column("deleted_by", sa.BigInteger),
        sa.CheckConstraint(
            "milestone_type IN ('gate','deliverable','regulatory','clinical','cmc','other')",
            name="ck_project_milestone_milestone_type",
        ),
        sa.CheckConstraint(
            "status IN ('pending','achieved','missed','cancelled')",
            name="ck_project_milestone_status",
        ),
        schema="prs",
    )
    op.create_index(
        "ix_project_milestone_project", "project_milestone", ["project_id"],
        postgresql_where=sa.text("deleted_at IS NULL"), schema="prs",
    )

    # ============== prs.project_team ==============
    op.create_table(
        "project_team",
        sa.Column("team_id", sa.BigInteger, sa.Identity(always=True), primary_key=True),
        sa.Column("project_id", sa.BigInteger,
                  sa.ForeignKey("prs.project.project_id"), nullable=False),
        sa.Column("user_id", sa.BigInteger,
                  sa.ForeignKey("auth.user.user_id"), nullable=False),
        sa.Column("role_in_project", sa.String(32), nullable=False),
        sa.Column("joined_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.Column("left_at", sa.DateTime(timezone=True)),
        sa.Column("notes", sa.Text),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.Column("created_by", sa.BigInteger, nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.Column("updated_by", sa.BigInteger, nullable=False),
        sa.CheckConstraint(
            "role_in_project IN ('pm','cmc_lead','qa_lead','regulatory_lead','clinical_lead',"
            "'research','member','observer')",
            name="ck_project_team_role",
        ),
        schema="prs",
    )
    op.create_index(
        "ix_project_team_project", "project_team", ["project_id"],
        schema="prs",
    )
    op.create_index(
        "ix_project_team_user", "project_team", ["user_id"],
        schema="prs",
    )
    # 当前在岗成员 (project, user, role) 唯一；离开后可再加入（重新建一条新记录）
    op.execute("""
        CREATE UNIQUE INDEX uq_project_team_active
        ON prs.project_team (project_id, user_id, role_in_project)
        WHERE left_at IS NULL
    """)

    # ============== prs.project_status_history ==============
    op.create_table(
        "project_status_history",
        sa.Column("history_id", sa.BigInteger, sa.Identity(always=True), primary_key=True),
        sa.Column("project_id", sa.BigInteger,
                  sa.ForeignKey("prs.project.project_id"), nullable=False),
        sa.Column("old_status", sa.String(32)),
        sa.Column("new_status", sa.String(32), nullable=False),
        sa.Column("change_reason", sa.Text, nullable=False),
        sa.Column("changed_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.Column("changed_by", sa.BigInteger, sa.ForeignKey("auth.user.user_id"), nullable=False),
        sa.Column("e_signature_id", sa.BigInteger, sa.ForeignKey("audit.e_signature.signature_id")),
        schema="prs",
    )
    op.create_index(
        "ix_project_status_history_project", "project_status_history",
        ["project_id", sa.text("changed_at DESC")], schema="prs",
    )


def downgrade() -> None:
    op.drop_table("project_status_history", schema="prs")
    op.execute("DROP INDEX IF EXISTS prs.uq_project_team_active")
    op.drop_table("project_team", schema="prs")
    op.drop_table("project_milestone", schema="prs")
    op.drop_table("project", schema="prs")
    op.execute("DELETE FROM meta.code_sequence WHERE sequence_name = 'project'")
