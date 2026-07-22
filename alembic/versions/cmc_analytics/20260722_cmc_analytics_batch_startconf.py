"""cmc_analytics: 实验开始确认——batch_register 加确认标记（2026-07-22）

实验开始日期改为"计划开始日"，另加一步"确认实际开始"（设计见 rd-batch-registry
docs/实验开始确认设计_计划实际分离与容器状态派生.md）。给 batch.batch_register 增 2 列：

  - start_confirmed_at   确认实际开始的时间；NULL=待开始/未确认，非空=进行中
  - start_confirmed_by   确认人工号（审计快照）

严格改期下不加"实际开始日"列（= start_date）。既有行两列均 NULL（=待开始），
纯加列、无约束。

Revision ID: cmc_analytics_batch_startconf
Revises: cmc_analytics_batch_seedhold
Create Date: 2026-07-22
"""
from __future__ import annotations

from alembic import op

revision = "cmc_analytics_batch_startconf"
down_revision = "cmc_analytics_batch_seedhold"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE batch.batch_register
          ADD COLUMN start_confirmed_at timestamptz,
          ADD COLUMN start_confirmed_by varchar(64)
        """
    )


def downgrade() -> None:
    op.execute(
        """
        ALTER TABLE batch.batch_register
          DROP COLUMN IF EXISTS start_confirmed_by,
          DROP COLUMN IF EXISTS start_confirmed_at
        """
    )
