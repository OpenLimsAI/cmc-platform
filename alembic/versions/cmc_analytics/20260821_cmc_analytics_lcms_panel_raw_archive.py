"""cmc_analytics: lcms_panel.upload_batch 补 raw_archive_path / blank_sample

背景:上传的原始 MultiQuant txt 此前不存档,reparse 必须重新上传原文件。
现在入库成功时按 sha256 存到项目 data/raw/(gitignored),批次记录存档
相对路径;blank_sample(培养基空白样品名,默认 BM)一并落库,保证 reparse
能完整还原当次解析参数。

Revision ID: cmc_analytics_lcms_panel_rawarc
Revises: cmc_analytics_lcms_panel_wr2
Create Date: 2026-08-21
"""
from __future__ import annotations

from alembic import op

revision = "cmc_analytics_lcms_panel_rawarc"
down_revision = "cmc_analytics_lcms_panel_wr2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE lcms_panel.upload_batch ADD COLUMN raw_archive_path TEXT")
    op.execute("ALTER TABLE lcms_panel.upload_batch "
               "ADD COLUMN blank_sample TEXT NOT NULL DEFAULT 'BM'")


def downgrade() -> None:
    op.execute("ALTER TABLE lcms_panel.upload_batch DROP COLUMN IF EXISTS blank_sample")
    op.execute("ALTER TABLE lcms_panel.upload_batch DROP COLUMN IF EXISTS raw_archive_path")
