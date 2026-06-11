"""add name_en to material

Revision ID: cad3b5fb876b
Revises: c39f7d07b08a
Create Date: 2026-06-11 11:45:55.410570
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = 'cad3b5fb876b'
down_revision = 'c39f7d07b08a'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 物料英文名(MDM mm.material_name_en 快照, 入库/刷新时覆盖)
    op.add_column("material", sa.Column("name_en", sa.String(length=255), nullable=True),
                  schema="material_mgmt")


def downgrade() -> None:
    op.drop_column("material", "name_en", schema="material_mgmt")
