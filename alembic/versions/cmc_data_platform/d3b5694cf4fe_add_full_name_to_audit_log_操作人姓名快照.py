"""add full_name to audit_log (操作人姓名快照)

Revision ID: d3b5694cf4fe
Revises: a1bba318f3a8
Create Date: 2026-06-16 13:54:29.156066
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = 'd3b5694cf4fe'
down_revision = 'a1bba318f3a8'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 操作人姓名快照(审计日志可读性;写入时从 MDM 令牌 full_name 取)
    op.add_column(
        "audit_log",
        sa.Column("full_name", sa.String(length=128), nullable=True),
        schema="material_mgmt",
    )


def downgrade() -> None:
    op.drop_column("audit_log", "full_name", schema="material_mgmt")
