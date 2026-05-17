"""dim_method.std_minutes int -> numeric(6,2)

Revision ID: 002
Revises: 001
Create Date: 2026-04-27
"""
from alembic import op


revision = "002"
down_revision = "001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE meta.dim_method "
        "ALTER COLUMN std_minutes TYPE numeric(6,2) USING std_minutes::numeric(6,2)"
    )


def downgrade() -> None:
    op.execute(
        "ALTER TABLE meta.dim_method "
        "ALTER COLUMN std_minutes TYPE integer USING ROUND(std_minutes)::integer"
    )
