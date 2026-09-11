"""cmc_analytics: manual.sample_result 放开指标白名单，加人工葡萄糖 gluc（2026-09-11）

背景（负责人 2026-09-11）：摇瓶 / 摇管有时不做生化分析，只用试剂盒单测葡萄糖浓度，
仪器不联网、系统采不到，只能人工录。USP 看板的「渗透压录入」页因此改名「数据录入」，
每行样品在渗透压之外再加一格葡萄糖。

规则：同一批次同一培养天，生化仪（Nova）有葡萄糖就用仪器值，没有才用人工录入值；
曲线与数据表都按这个优先级取数（在看板后端做，不在库里做）。

单位与量程：g/L，0.00–20.00（与 fact_nova.gluc 同单位，才能画在同一条线上；
量程也刻意和渗透压 100–1000 mOsm/kg 岔开，填错格子能当场发现）。

Revision ID: cmc_analytics_manual_metric_gluc
Revises: cmc_analytics_equipment_no
Create Date: 2026-09-11
"""
from __future__ import annotations

from alembic import op

revision = "cmc_analytics_manual_metric_gluc"
down_revision = "cmc_analytics_equipment_no"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE manual.sample_result DROP CONSTRAINT IF EXISTS ck_manual_sample_result_metric")
    op.execute(
        "ALTER TABLE manual.sample_result ADD CONSTRAINT ck_manual_sample_result_metric "
        "CHECK (metric_code IN ('osmolality', 'gluc'))"
    )
    op.execute(
        "COMMENT ON COLUMN manual.sample_result.metric_code IS "
        "'人工录入的指标：osmolality 渗透压(mOsm/kg)、gluc 葡萄糖(g/L，试剂盒法；"
        "当天有 Nova 生化结果时以仪器值为准)。加新指标 = 改本 CHECK + 看板后端 routers/manual.py 的 METRICS 登记'"
    )


def downgrade() -> None:
    op.execute("DELETE FROM manual.sample_result WHERE metric_code <> 'osmolality'")
    op.execute("ALTER TABLE manual.sample_result DROP CONSTRAINT IF EXISTS ck_manual_sample_result_metric")
    op.execute(
        "ALTER TABLE manual.sample_result ADD CONSTRAINT ck_manual_sample_result_metric "
        "CHECK (metric_code IN ('osmolality'))"
    )
