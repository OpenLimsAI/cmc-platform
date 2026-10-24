"""add standard fields project_no originator_batch_no aliquot_date to batch

Revision ID: 546734e2d5e6
Revises: 1fb3dc036b56
Create Date: 2026-06-09 23:24:41.385120
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = '546734e2d5e6'
down_revision = '1fb3dc036b56'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 标准品入库表单新增三字段(均可空, 不影响其它 intake_type)
    op.add_column("batch", sa.Column("project_no", sa.String(length=100), nullable=True),
                  schema="material_mgmt")
    op.add_column("batch", sa.Column("originator_batch_no", sa.String(length=100), nullable=True),
                  schema="material_mgmt")
    op.add_column("batch", sa.Column("aliquot_date", sa.Date(), nullable=True),
                  schema="material_mgmt")


def downgrade() -> None:
    op.drop_column("batch", "aliquot_date", schema="material_mgmt")
    op.drop_column("batch", "originator_batch_no", schema="material_mgmt")
    op.drop_column("batch", "project_no", schema="material_mgmt")
