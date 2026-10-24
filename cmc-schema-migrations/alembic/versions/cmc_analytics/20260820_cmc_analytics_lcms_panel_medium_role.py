"""cmc_analytics: lcms_panel.compound 补 medium_role(培养基角色,每批重算)

brief §3.3:第三维度「培养基角色」(A 高本底主成分 / B 次要成分 / C 本底<LLOQ /
D BM 峰识别错误 / E 无 BM 数据)必须由程序对每批数据重新计算,不能沿用分类表旧值。
初版迁移漏了落库列,补上。NULL = 尚未计算(如上传未提供 BM 样品名)。

Revision ID: cmc_analytics_lcms_panel_mrole
Revises: cmc_analytics_lcms_panel_init
Create Date: 2026-08-20
"""
from __future__ import annotations

from alembic import op

revision = "cmc_analytics_lcms_panel_mrole"
down_revision = "cmc_analytics_lcms_panel_init"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        ALTER TABLE lcms_panel.compound
          ADD COLUMN medium_role VARCHAR(4)
          CHECK (medium_role IN ('A', 'B', 'C', 'D', 'E'))
    """)


def downgrade() -> None:
    op.execute("ALTER TABLE lcms_panel.compound DROP COLUMN IF EXISTS medium_role")
