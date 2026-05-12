"""ref init: cross-domain link tables (project_substance first)

Revision ID: 0007_ref_init
Revises: 0006_prs_init
Create Date: 2026-05-11 17:30:00.000000

ref schema 用于跨域引用。M2.1 先建 ref.project_substance 一张表（Phase 2 §1），
M2.3 起在 service 层做 link/unlink 操作。其余 ref.project_asset / ref.substance_asset
等留到 ARS / MM 域开工时再建。

schema `ref` 已由 deploy/postgres/init/01-init.sql 创建。
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0007_ref_init"
down_revision: str | None = "0006_prs_init"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "project_substance",
        sa.Column("link_id", sa.BigInteger, sa.Identity(always=True), primary_key=True),
        sa.Column("project_id", sa.BigInteger,
                  sa.ForeignKey("prs.project.project_id"), nullable=False),
        sa.Column("substance_id", sa.BigInteger,
                  sa.ForeignKey("srs.substance.substance_id"), nullable=False),
        sa.Column("role", sa.String(32), nullable=False),
        sa.Column("priority", sa.Integer),  # 越小优先级越高，nullable
        sa.Column("linked_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.Column("linked_by", sa.BigInteger,
                  sa.ForeignKey("auth.user.user_id"), nullable=False),
        sa.Column("unlinked_at", sa.DateTime(timezone=True)),
        sa.Column("unlinked_by", sa.BigInteger,
                  sa.ForeignKey("auth.user.user_id")),
        sa.Column("notes", sa.Text),
        sa.CheckConstraint(
            "role IN ('primary_target','candidate','backup','excluded','reference')",
            name="ck_project_substance_role",
        ),
        sa.CheckConstraint(
            "(unlinked_at IS NULL AND unlinked_by IS NULL) "
            "OR (unlinked_at IS NOT NULL AND unlinked_by IS NOT NULL)",
            name="ck_project_substance_unlink_consistency",
        ),
        schema="ref",
    )
    op.create_index(
        "ix_project_substance_project", "project_substance",
        ["project_id"], schema="ref",
    )
    op.create_index(
        "ix_project_substance_substance", "project_substance",
        ["substance_id"], schema="ref",
    )
    # 有效关联（unlinked_at IS NULL）下，同一 project+substance+role 唯一
    op.execute("""
        CREATE UNIQUE INDEX uq_project_substance_active
        ON ref.project_substance (project_id, substance_id, role)
        WHERE unlinked_at IS NULL
    """)


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ref.uq_project_substance_active")
    op.drop_table("project_substance", schema="ref")
