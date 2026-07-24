"""cmc_analytics: stg_nova_run.parse_status 增加 production 类（2026-07-24）

生产批号（P5X…/P3S…/WNP2P… 前缀+日期）此前被归入 non_standard，
但它们是**合法的生产批号**（只是不同于研发的 R/B 批号），应照原样写入 batch_number。
本迁移只更新 parse_status 的列注释，说明新增的 'production' 取值；
数据侧由 rd-nova-etl 的 stage 步骤重建时自动归类，无需改表结构。

Revision ID: cmc_analytics_stg_nova_prod
Revises: cmc_analytics_nova_grant
Create Date: 2026-07-24
"""

from __future__ import annotations

from alembic import op

revision = "cmc_analytics_stg_nova_prod"
down_revision = "cmc_analytics_nova_grant"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "COMMENT ON COLUMN staging.stg_nova_run.parse_status IS "
        "'ok(研发批号,项目+批号+罐齐全) / suspect(研发批号,缺项目或罐) / "
        "production(生产批号 P5X…,整串即批号,通常无罐,batch_key 空) / "
        "non_standard(既非研发也非生产批号) / unparseable(没填 batch_id)'"
    )


def downgrade() -> None:
    op.execute(
        "COMMENT ON COLUMN staging.stg_nova_run.parse_status IS "
        "'ok(全解出) / suspect(解出但格式存疑) / unparseable(缺关键段) / "
        "non_standard(非标批号,非时程样)'"
    )
