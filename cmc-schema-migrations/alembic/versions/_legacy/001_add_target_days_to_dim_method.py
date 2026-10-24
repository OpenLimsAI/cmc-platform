"""add target_days to dim_method

Revision ID: 001
Revises:
Create Date: 2026-04-21
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "dim_method",
        sa.Column("target_days", sa.Integer(), nullable=True),
        schema="meta",
    )


def downgrade() -> None:
    op.drop_column("dim_method", "target_days", schema="meta")
