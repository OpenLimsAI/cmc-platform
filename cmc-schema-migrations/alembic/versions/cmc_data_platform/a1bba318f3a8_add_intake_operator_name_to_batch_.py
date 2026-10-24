"""add intake_operator_name to batch (入库人姓名快照)

Revision ID: a1bba318f3a8
Revises: 08941b314a8f
Create Date: 2026-06-16 13:28:16.289094
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = 'a1bba318f3a8'
down_revision = '08941b314a8f'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 入库登记操作人姓名快照(从 MDM 令牌 full_name 取,入库时固化)
    op.add_column(
        "batch",
        sa.Column("intake_operator_name", sa.String(length=128), nullable=True),
        schema="material_mgmt",
    )


def downgrade() -> None:
    op.drop_column("batch", "intake_operator_name", schema="material_mgmt")
