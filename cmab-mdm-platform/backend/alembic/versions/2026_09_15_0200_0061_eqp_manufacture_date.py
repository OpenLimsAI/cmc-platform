"""设备购入日期改为出厂日期，并转正历史台账数据

Revision ID: 0061_eqp_manufacture_date
Revises: 0060_eqp_device_status
Create Date: 2026-09-15 02:00:00.000000

生产库现有 purchase_date 均为空；设备部台账的出厂日期此前保存在 extra.出厂日期。
为兼容其他环境，本迁移仍会先把非空购入日期保存到 extra.历史购入日期，再删除旧列。
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0061_eqp_manufacture_date"
down_revision: str | None = "0060_eqp_device_status"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "equipment",
        sa.Column("manufacture_date", sa.Date(), comment="出厂日期"),
        schema="eqp",
    )

    # 台账只有年月，统一取当月 1 日；只迁移明确符合 YYYY.M(M) 的值。
    op.execute(r"""
        UPDATE eqp.equipment
           SET manufacture_date = make_date(
                   split_part(extra->>'出厂日期', '.', 1)::integer,
                   split_part(extra->>'出厂日期', '.', 2)::integer,
                   1
               )
         WHERE jsonb_typeof(extra) = 'object'
           AND extra->>'出厂日期' ~ '^\d{4}\.\d{1,2}$'
    """)

    # 防止非生产环境中已有的真实购入日期在删列时丢失。
    op.execute("""
        UPDATE eqp.equipment
           SET extra = coalesce(extra, '{}'::jsonb)
                       || jsonb_build_object('历史购入日期', to_char(purchase_date, 'YYYY-MM-DD'))
         WHERE purchase_date IS NOT NULL
    """)
    # 已转正的值不再在 extra 中重复保存；无法解析的原值保留供人工处理。
    op.execute("""
        UPDATE eqp.equipment
           SET extra = extra - '出厂日期'
         WHERE manufacture_date IS NOT NULL
           AND jsonb_typeof(extra) = 'object'
           AND extra ? '出厂日期'
    """)
    op.drop_column("equipment", "purchase_date", schema="eqp")


def downgrade() -> None:
    op.add_column(
        "equipment",
        sa.Column("purchase_date", sa.Date(), comment="购入日期"),
        schema="eqp",
    )
    op.execute(r"""
        UPDATE eqp.equipment
           SET purchase_date = (extra->>'历史购入日期')::date
         WHERE jsonb_typeof(extra) = 'object'
           AND extra->>'历史购入日期' ~ '^\d{4}-\d{2}-\d{2}$'
    """)
    op.execute("""
        UPDATE eqp.equipment
           SET extra = (coalesce(extra, '{}'::jsonb) - '历史购入日期')
                       || jsonb_build_object('出厂日期', to_char(manufacture_date, 'YYYY.MM'))
         WHERE manufacture_date IS NOT NULL
    """)
    op.drop_column("equipment", "manufacture_date", schema="eqp")
