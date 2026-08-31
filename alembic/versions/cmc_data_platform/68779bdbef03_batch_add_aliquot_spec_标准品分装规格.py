"""batch add aliquot_spec 标准品分装规格

Revision ID: 68779bdbef03
Revises: a83f06b00adb
Create Date: 2026-08-31 19:32:17.144271
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = '68779bdbef03'
down_revision = 'a83f06b00adb'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 标准品批次的分装规格,与 concentration 同样存"数值+单位"组合字符串(例 "100 uL/支"),
    # 单位当前前端固定 uL/支,将来若放开单位老数据仍可自解释。其他类型批次为 NULL。
    op.add_column(
        "batch",
        sa.Column("aliquot_spec", sa.String(length=50), nullable=True),
        schema="material_mgmt",
    )


def downgrade() -> None:
    op.drop_column("batch", "aliquot_spec", schema="material_mgmt")
