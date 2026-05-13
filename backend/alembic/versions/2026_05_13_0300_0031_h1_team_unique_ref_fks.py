"""H1 评审决议落地：P3 team partial UNIQUE + R8 ref 三表 created/updated_by FK

Revision ID: 0031_h1_team_unique_ref_fks
Revises: 0030_meta_lookup_config
Create Date: 2026-05-13 03:00:00.000000

V1.2 评审会决议（REV-MDM-001 V1.2 §1）：

P3: A — prs.project_team 唯一约束改 partial WHERE left_at IS NULL
   设计：V1.1 §9.4 写 UNIQUE (project_id, user_id, role) 绝对唯一
   实施侧 V1.0 曾用 partial（M3.0.2 migration 0015 改成绝对唯一对齐 V1.1 字面）
   评审决议：业务上"离职后再加入"是合理诉求 → 改回 partial unique
   迁移：drop uq_project_team；新建 partial unique index uq_project_team_active
       WHERE left_at IS NULL。"已离职"的历史行不参与去重。

R8: A — ref 三表 created_by / updated_by 加 FK 到 auth.user
   设计：V1.1 §11.2/§11.3/§11.4 字段定义有 created_by/updated_by BIGINT NOT NULL，
       但 DDL 未显式列 fk_*_created/updated_by 约束（评审决议 A：显式补 FK 让
       语义 FK 在 DB 层强制，与 deleted_by 一致）。
   三表 × 2 列 = 6 个 FK：
       fk_ref_ps_created_by / fk_ref_ps_updated_by
       fk_ref_as_created_by / fk_ref_as_updated_by
       fk_ref_pa_created_by / fk_ref_pa_updated_by
   预检：所有 created_by / updated_by 值都来自 service 层 current_user.user_id，
       不存在孤儿 — 0 行违反 FK。
"""
from collections.abc import Sequence

from alembic import op

revision: str = "0031_h1_team_unique_ref_fks"
down_revision: str | None = "0030_meta_lookup_config"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # ============== P3: project_team UNIQUE → partial ==============
    op.drop_constraint("uq_project_team", "project_team", schema="prs", type_="unique")
    op.execute(
        """
        CREATE UNIQUE INDEX uq_project_team_active
        ON prs.project_team (project_id, user_id, role)
        WHERE left_at IS NULL
        """
    )

    # ============== R8: ref 三表 created_by + updated_by FK ==============
    for table_short, schema_short in [
        ("project_substance", "ps"),
        ("asset_substance", "as"),
        ("project_asset", "pa"),
    ]:
        op.create_foreign_key(
            f"fk_ref_{schema_short}_created_by", table_short, "user",
            ["created_by"], ["user_id"],
            source_schema="ref", referent_schema="auth",
        )
        op.create_foreign_key(
            f"fk_ref_{schema_short}_updated_by", table_short, "user",
            ["updated_by"], ["user_id"],
            source_schema="ref", referent_schema="auth",
        )


def downgrade() -> None:
    for table_short, schema_short in [
        ("project_substance", "ps"),
        ("asset_substance", "as"),
        ("project_asset", "pa"),
    ]:
        op.drop_constraint(
            f"fk_ref_{schema_short}_updated_by", table_short,
            schema="ref", type_="foreignkey",
        )
        op.drop_constraint(
            f"fk_ref_{schema_short}_created_by", table_short,
            schema="ref", type_="foreignkey",
        )

    op.execute("DROP INDEX IF EXISTS prs.uq_project_team_active")
    op.create_unique_constraint(
        "uq_project_team", "project_team", ["project_id", "user_id", "role"],
        schema="prs",
    )
