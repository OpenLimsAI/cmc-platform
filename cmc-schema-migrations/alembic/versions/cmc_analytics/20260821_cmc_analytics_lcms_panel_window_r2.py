"""cmc_analytics: lcms_panel.calibration 补 window_r2(可用窗口内点的加权 r²)

背景:此前展示的「重算 r²」是解析自检值(与厂商同点集同公式的复现),数值上
与厂商 r² 注定一致,无增量信息。窗口 r² 才是重拟合质量的可比指标。

Revision ID: cmc_analytics_lcms_panel_wr2
Revises: cmc_analytics_lcms_panel_mrole
Create Date: 2026-08-21
"""
from __future__ import annotations

from alembic import op

revision = "cmc_analytics_lcms_panel_wr2"
down_revision = "cmc_analytics_lcms_panel_mrole"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE lcms_panel.calibration ADD COLUMN window_r2 DOUBLE PRECISION")


def downgrade() -> None:
    op.execute("ALTER TABLE lcms_panel.calibration DROP COLUMN IF EXISTS window_r2")
