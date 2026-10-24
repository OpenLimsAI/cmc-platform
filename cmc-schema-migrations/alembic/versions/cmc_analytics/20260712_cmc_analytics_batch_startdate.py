"""cmc_analytics: batch 实验开始日期 start_date（2026-07-12）

给实验批号加一个"实验开始日期"，把每个容器的拟定天数锚定到真实日历，
从而支持"按日期跨批号汇总当天该取样的样品并打印"。start_date 是每个
实验（批号）一个，容器的实际日期由 start_date + 上游各阶段拟定天数累加推算。

Revision ID: cmc_analytics_batch_startdate
Revises: cmc_analytics_batch_bioreactor
Create Date: 2026-07-12
"""
from __future__ import annotations

from alembic import op

revision = "cmc_analytics_batch_startdate"
down_revision = "cmc_analytics_batch_bioreactor"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE batch.batch_register ADD COLUMN start_date date")


def downgrade() -> None:
    op.execute("ALTER TABLE batch.batch_register DROP COLUMN IF EXISTS start_date")
