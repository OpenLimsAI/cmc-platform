"""prs.project_milestone schema realignment to DM-MDM-001 V1.0 §9.3

Revision ID: 0014_prs_milestone_v2
Revises: 0013_prs_proj_v2
Create Date: 2026-05-11 23:10:00.000000

M3.0.2 第 2 步：

  - status 枚举映射：pending→planned, achieved→completed, missed→delayed, cancelled→cancelled
  - milestone_type 收敛到 §9.3 三值：regulatory/clinical/cmc → decision；other → decision
  - planned_date 改 NOT NULL
  - 移除 deleted_at / deleted_by 与软删除字段；改 ON DELETE CASCADE（§9.3 设计）
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0014_prs_milestone_v2"
down_revision: str | None = "0013_prs_proj_v2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1) 临时去除旧 CHECK（SQLAlchemy naming convention 给加了 ck_<table>_ 双前缀）
    op.execute("ALTER TABLE prs.project_milestone DROP CONSTRAINT IF EXISTS ck_project_milestone_ck_project_milestone_status")
    op.execute("ALTER TABLE prs.project_milestone DROP CONSTRAINT IF EXISTS ck_project_milestone_ck_project_milestone_milestone_type")
    op.execute("ALTER TABLE prs.project_milestone DROP CONSTRAINT IF EXISTS ck_project_milestone_status")
    op.execute("ALTER TABLE prs.project_milestone DROP CONSTRAINT IF EXISTS ck_project_milestone_milestone_type")

    # 2) 数据映射
    op.execute("""
        UPDATE prs.project_milestone SET status = 'planned'   WHERE status = 'pending';
        UPDATE prs.project_milestone SET status = 'completed' WHERE status = 'achieved';
        UPDATE prs.project_milestone SET status = 'delayed'   WHERE status = 'missed';
    """)
    op.execute("""
        UPDATE prs.project_milestone SET milestone_type = 'decision'
         WHERE milestone_type IN ('regulatory','clinical','cmc','other');
    """)

    # 3) 旧软删除行：直接物理删除（设计文档要求 ON DELETE CASCADE，无 deleted_at 字段）
    op.execute("DELETE FROM prs.project_milestone WHERE deleted_at IS NOT NULL")

    # 4) planned_date 改 NOT NULL（dev demo 都填了；若 NULL 设为 today）
    op.execute(
        "UPDATE prs.project_milestone SET planned_date = CURRENT_DATE WHERE planned_date IS NULL"
    )
    op.alter_column(
        "project_milestone", "planned_date",
        existing_type=sa.Date(), nullable=False, schema="prs",
    )

    # 5) 移除 deleted_at / deleted_by + 索引
    op.drop_index(
        "ix_project_milestone_project", table_name="project_milestone", schema="prs"
    )
    op.drop_column("project_milestone", "deleted_at", schema="prs")
    op.drop_column("project_milestone", "deleted_by", schema="prs")

    # 6) 重建索引（§9.3：(project_id, planned_date)）
    op.create_index(
        "ix_project_milestone_project", "project_milestone",
        ["project_id", "planned_date"], schema="prs",
    )

    # 7) 改 FK 为 ON DELETE CASCADE（先 drop 再加）
    # 真实 FK 名（SQLAlchemy 命名）：fk_project_milestone_project_project_id
    op.execute("ALTER TABLE prs.project_milestone "
               "DROP CONSTRAINT IF EXISTS fk_project_milestone_project_project_id")
    op.execute("ALTER TABLE prs.project_milestone "
               "DROP CONSTRAINT IF EXISTS project_milestone_project_id_fkey")
    op.create_foreign_key(
        "fk_project_milestone_project", "project_milestone", "project",
        ["project_id"], ["project_id"],
        source_schema="prs", referent_schema="prs",
        ondelete="CASCADE",
    )

    # 8) 加新 CHECK 约束
    op.create_check_constraint(
        "ck_project_milestone_status",
        "project_milestone",
        "status IN ('planned','in_progress','completed','delayed','cancelled')",
        schema="prs",
    )
    op.create_check_constraint(
        "ck_project_milestone_type",
        "project_milestone",
        "milestone_type IN ('gate','deliverable','decision')",
        schema="prs",
    )

    # 9) 改默认 status
    op.alter_column(
        "project_milestone", "status",
        server_default="planned",
        schema="prs",
    )


def downgrade() -> None:
    op.alter_column("project_milestone", "status", server_default="pending", schema="prs")
    op.drop_constraint("ck_project_milestone_type", "project_milestone", schema="prs", type_="check")
    op.drop_constraint("ck_project_milestone_status", "project_milestone", schema="prs", type_="check")

    op.drop_constraint(
        "fk_project_milestone_project", "project_milestone",
        schema="prs", type_="foreignkey",
    )
    op.create_foreign_key(
        "project_milestone_project_id_fkey", "project_milestone", "project",
        ["project_id"], ["project_id"],
        source_schema="prs", referent_schema="prs",
    )

    op.drop_index("ix_project_milestone_project", table_name="project_milestone", schema="prs")
    op.add_column("project_milestone", sa.Column("deleted_by", sa.BigInteger), schema="prs")
    op.add_column(
        "project_milestone", sa.Column("deleted_at", sa.DateTime(timezone=True)), schema="prs"
    )
    op.create_index(
        "ix_project_milestone_project", "project_milestone", ["project_id"],
        postgresql_where=sa.text("deleted_at IS NULL"), schema="prs",
    )

    op.alter_column(
        "project_milestone", "planned_date",
        existing_type=sa.Date(), nullable=True, schema="prs",
    )

    op.execute("""
        UPDATE prs.project_milestone SET status = 'missed'   WHERE status = 'delayed';
        UPDATE prs.project_milestone SET status = 'achieved' WHERE status = 'completed';
        UPDATE prs.project_milestone SET status = 'pending'  WHERE status = 'planned';
    """)
    op.create_check_constraint(
        "ck_project_milestone_status",
        "project_milestone",
        "status IN ('pending','achieved','missed','cancelled')",
        schema="prs",
    )
    op.create_check_constraint(
        "ck_project_milestone_milestone_type",
        "project_milestone",
        "milestone_type IN ('gate','deliverable','regulatory','clinical','cmc','other')",
        schema="prs",
    )
