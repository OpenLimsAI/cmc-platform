"""Archive immutable, numbered annual validation plan Excel exports."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "qv_annual_plan_export"
down_revision = "qv_cycle_identity_fields"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "annual_plan_export",
        sa.Column("export_id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column("plan_year", sa.SmallInteger(), nullable=False),
        sa.Column("version_no", sa.Integer(), nullable=False),
        sa.Column("item_count", sa.Integer(), nullable=False),
        sa.Column("sha256", sa.String(64), nullable=False),
        sa.Column("workbook", sa.LargeBinary(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("created_by", sa.String(64), nullable=False),
        sa.UniqueConstraint("plan_year", "version_no", name="uq_annual_plan_export_year_version"),
        schema="validation",
    )
    op.create_index("ix_annual_plan_export_year", "annual_plan_export", ["plan_year"], schema="validation")
    # 导出版本只追加，业务角色不得更新/删除归档文件。
    op.execute("REVOKE UPDATE, DELETE ON validation.annual_plan_export FROM qv_app")


def downgrade() -> None:
    op.drop_index("ix_annual_plan_export_year", "annual_plan_export", schema="validation")
    op.drop_table("annual_plan_export", schema="validation")
