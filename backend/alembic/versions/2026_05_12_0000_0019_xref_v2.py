"""substance_xref add effective_date / expiry_date + partial unique (§7.6)

Revision ID: 0019_xref_v2
Revises: 0018_srs_subtables
Create Date: 2026-05-12 00:00:00.000000

M3.0.3 第 2 步：substance_xref 对齐 §7.6（偏离说明 §2.1.4）

  - 加 effective_date / expiry_date 字段
  - 加 UNIQUE INDEX uq_substance_xref_type_value (xref_type, xref_value) WHERE deleted_at IS NULL
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0019_xref_v2"
down_revision: str | None = "0018_srs_subtables"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "substance_xref",
        sa.Column("effective_date", sa.Date()),
        schema="srs",
    )
    op.add_column(
        "substance_xref",
        sa.Column("expiry_date", sa.Date()),
        schema="srs",
    )
    # 部分唯一索引：同一 (type, value) 在活动状态下唯一；已软删除的不参与去重
    op.execute("""
        CREATE UNIQUE INDEX uq_substance_xref_type_value
        ON srs.substance_xref (xref_type, xref_value)
        WHERE deleted_at IS NULL
    """)


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS srs.uq_substance_xref_type_value")
    op.drop_column("substance_xref", "expiry_date", schema="srs")
    op.drop_column("substance_xref", "effective_date", schema="srs")
