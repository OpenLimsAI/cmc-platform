"""cmc_analytics: batch 项目号 MDM 快照表（2026-07-11）

批号系统对项目只做「引用」：从 MDM (prs.project) 取项目号时，按 EQP→LabOps 先例
在本地落快照（mdm_project_id + project_code + data_source='mdm'），降低对 MDM 实时可用性
的耦合。手工输入项目号则不入此表。

Revision ID: cmc_analytics_batch_mdm_snap
Revises: cmc_analytics_batch_status_trig
Create Date: 2026-07-11
"""
from __future__ import annotations

from alembic import op

revision = "cmc_analytics_batch_mdm_snap"
down_revision = "cmc_analytics_batch_status_trig"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE batch.mdm_project_snapshot (
            project_code varchar(64) PRIMARY KEY,   -- MDM prs.project.project_code，如 PRJ-2026-0123
            project_id   bigint,                    -- MDM 侧 project_id
            project_name text,
            status       varchar(32),
            data_source  varchar(16) NOT NULL DEFAULT 'mdm',
            synced_at    timestamptz NOT NULL DEFAULT now()
        )
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS batch.mdm_project_snapshot")
