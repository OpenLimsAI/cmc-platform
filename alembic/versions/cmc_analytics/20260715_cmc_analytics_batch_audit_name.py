"""cmc_analytics: 审计表加操作人姓名 full_name（2026-07-15）

审计原只记 username（工号）；补记操作当时的姓名（取自 MDM JWT 的 full_name），
审计页多一列「姓名」，更易读、更合规。历史行 full_name 为空。

Revision ID: cmc_analytics_batch_audit_name
Revises: cmc_analytics_batch_audit_log
Create Date: 2026-07-15
"""
from __future__ import annotations

from alembic import op

revision = "cmc_analytics_batch_audit_name"
down_revision = "cmc_analytics_batch_audit_log"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE batch.audit_log ADD COLUMN full_name varchar(128)")


def downgrade() -> None:
    op.execute("ALTER TABLE batch.audit_log DROP COLUMN IF EXISTS full_name")
