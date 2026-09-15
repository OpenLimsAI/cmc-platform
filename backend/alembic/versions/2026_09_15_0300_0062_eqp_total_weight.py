"""新增设备总重正式字段并转正历史台账数据

Revision ID: 0062_eqp_total_weight
Revises: 0061_eqp_manufacture_date
Create Date: 2026-09-15 03:00:00.000000

总重以 kg 为单位；历史 kg/g 值统一换算，迁移后删除 extra.总重。
负责人确认忽略台账错值：CC1-SC-013 的 2015.11 是重复填入的出厂年月，
CC1-JC-028 仅填了 kg；这些记录的正式总重留空，不再保存到 extra。
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0062_eqp_total_weight"
down_revision: str | None = "0061_eqp_manufacture_date"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "equipment",
        sa.Column(
            "total_weight",
            sa.Float(),
            comment="设备总重（kg）",
        ),
        schema="eqp",
    )
    op.execute(r"""
        WITH parsed AS (
            SELECT equipment_id,
                   regexp_match(
                       btrim(extra->>'总重'),
                       '^([0-9]+([.][0-9]+)?)[[:space:]]*(kg|g)$',
                       'i'
                   ) AS weight_parts
              FROM eqp.equipment
             WHERE jsonb_typeof(extra) = 'object'
               AND extra ? '总重'
               AND length(btrim(extra->>'总重')) <= 32
        )
        UPDATE eqp.equipment AS e
           SET total_weight = p.weight_parts[1]::double precision
                   / CASE WHEN lower(p.weight_parts[3]) = 'g' THEN 1000 ELSE 1 END
          FROM parsed AS p
         WHERE e.equipment_id = p.equipment_id
           AND p.weight_parts IS NOT NULL
    """)
    # 总重仅由正式字段管理；错误值忽略，一并清除旧键，其他 extra 信息保留。
    op.execute("""
        UPDATE eqp.equipment
           SET extra = extra - '总重'
         WHERE jsonb_typeof(extra) = 'object'
           AND extra ? '总重'
    """)
    op.create_check_constraint(
        "ck_equipment_total_weight_nonnegative",
        "equipment",
        "total_weight IS NULL OR total_weight >= 0",
        schema="eqp",
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_equipment_total_weight_nonnegative",
        "equipment",
        type_="check",
        schema="eqp",
    )
    op.execute("""
        UPDATE eqp.equipment
           SET extra = coalesce(extra, '{}'::jsonb)
                       || jsonb_build_object('总重', total_weight::text || 'kg')
         WHERE total_weight IS NOT NULL
    """)
    op.drop_column("equipment", "total_weight", schema="eqp")
