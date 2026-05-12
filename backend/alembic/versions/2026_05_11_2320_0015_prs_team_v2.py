"""prs.project_team schema realignment to DM-MDM-001 V1.0 §9.4

Revision ID: 0015_prs_team_v2
Revises: 0014_prs_milestone_v2
Create Date: 2026-05-11 23:20:00.000000

M3.0.2 第 3 步：

  - 字段名 role_in_project → role；去除 8 值 CHECK 约束（§9.4 允许任意字符串）
  - 加 function_area VARCHAR(64) / allocation_pct INT 0-100
  - joined_at / left_at: TIMESTAMPTZ → DATE
  - 唯一约束改：partial unique WHERE left_at IS NULL → UNIQUE(project_id, user_id, role) 绝对唯一
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0015_prs_team_v2"
down_revision: str | None = "0014_prs_milestone_v2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1) 去除旧 CHECK + 旧 partial unique（SQLAlchemy naming convention 双前缀）
    op.execute("ALTER TABLE prs.project_team DROP CONSTRAINT IF EXISTS ck_project_team_ck_project_team_role")
    op.execute("ALTER TABLE prs.project_team DROP CONSTRAINT IF EXISTS ck_project_team_role")
    op.execute("DROP INDEX IF EXISTS prs.uq_project_team_active")

    # 2) 重命名 role_in_project → role
    op.alter_column("project_team", "role_in_project", new_column_name="role", schema="prs")

    # 3) 数据映射：把 partial unique 时代允许的"先离开再加入"重复（如果有的话）
    #    现在要绝对唯一。dev demo 数据没冲突，但生产部署前需迁移演练。
    #    保险起见删除完全相同 (project_id, user_id, role) 且 left_at IS NOT NULL 的旧行
    op.execute("""
        DELETE FROM prs.project_team t1
         WHERE t1.left_at IS NOT NULL
           AND EXISTS (
               SELECT 1 FROM prs.project_team t2
                WHERE t2.project_id = t1.project_id
                  AND t2.user_id    = t1.user_id
                  AND t2.role       = t1.role
                  AND t2.team_id   != t1.team_id
           );
    """)

    # 4) 加新字段
    op.add_column("project_team", sa.Column("function_area", sa.String(64)), schema="prs")
    op.add_column("project_team", sa.Column("allocation_pct", sa.Integer), schema="prs")

    # 5) joined_at / left_at 类型 TIMESTAMPTZ → DATE
    op.alter_column(
        "project_team", "joined_at",
        existing_type=sa.DateTime(timezone=True),
        type_=sa.Date(),
        existing_nullable=False,
        existing_server_default=sa.text("NOW()"),
        server_default=sa.text("CURRENT_DATE"),
        postgresql_using="joined_at::date",
        schema="prs",
    )
    op.alter_column(
        "project_team", "left_at",
        existing_type=sa.DateTime(timezone=True),
        type_=sa.Date(),
        existing_nullable=True,
        postgresql_using="left_at::date",
        schema="prs",
    )

    # 6) 加绝对唯一约束
    op.create_unique_constraint(
        "uq_project_team", "project_team",
        ["project_id", "user_id", "role"],
        schema="prs",
    )

    # 7) 加 allocation_pct 范围 CHECK
    op.create_check_constraint(
        "ck_project_team_alloc", "project_team",
        "allocation_pct IS NULL OR (allocation_pct BETWEEN 0 AND 100)",
        schema="prs",
    )

    # 8) 重建索引（§9.4：partial WHERE left_at IS NULL，但是是索引不是约束）
    op.drop_index("ix_project_team_project", table_name="project_team", schema="prs")
    op.drop_index("ix_project_team_user", table_name="project_team", schema="prs")
    op.create_index(
        "ix_project_team_project", "project_team", ["project_id"],
        postgresql_where=sa.text("left_at IS NULL"), schema="prs",
    )
    op.create_index(
        "ix_project_team_user", "project_team", ["user_id"],
        postgresql_where=sa.text("left_at IS NULL"), schema="prs",
    )


def downgrade() -> None:
    op.drop_index("ix_project_team_user", table_name="project_team", schema="prs")
    op.drop_index("ix_project_team_project", table_name="project_team", schema="prs")
    op.create_index("ix_project_team_project", "project_team", ["project_id"], schema="prs")
    op.create_index("ix_project_team_user", "project_team", ["user_id"], schema="prs")

    op.drop_constraint("ck_project_team_alloc", "project_team", schema="prs", type_="check")
    op.drop_constraint("uq_project_team", "project_team", schema="prs", type_="unique")

    op.alter_column(
        "project_team", "left_at",
        existing_type=sa.Date(),
        type_=sa.DateTime(timezone=True),
        existing_nullable=True,
        postgresql_using="left_at::timestamptz",
        schema="prs",
    )
    op.alter_column(
        "project_team", "joined_at",
        existing_type=sa.Date(),
        type_=sa.DateTime(timezone=True),
        existing_nullable=False,
        server_default=sa.text("NOW()"),
        postgresql_using="joined_at::timestamptz",
        schema="prs",
    )

    op.drop_column("project_team", "allocation_pct", schema="prs")
    op.drop_column("project_team", "function_area", schema="prs")

    op.alter_column("project_team", "role", new_column_name="role_in_project", schema="prs")

    op.execute("""
        CREATE UNIQUE INDEX uq_project_team_active
        ON prs.project_team (project_id, user_id, role_in_project)
        WHERE left_at IS NULL
    """)
    op.create_check_constraint(
        "ck_project_team_role",
        "project_team",
        "role_in_project IN ('pm','cmc_lead','qa_lead','regulatory_lead',"
        "'clinical_lead','research','member','observer')",
        schema="prs",
    )
