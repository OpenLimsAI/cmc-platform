"""eqp.equipment 增字段：额定功率 / 产地 + 字段语义校准

Revision ID: 0041_eqp_add_fields
Revises: 0040_eqp_equipment
Create Date: 2026-06-04 02:00:00.000000

按设备主数据整理结论调整：
  - 新增 rated_power(额定功率，自由文本如 '1500W'、'220V/50Hz/2kW')
  - 新增 origin(产地)
  - 列注释校准：
      equipment_name     → 设备名称（中文）
      equipment_name_en  → 设备名称（英文）
      description        → 主要性能参数描述
  审计 v3 通用触发器动态读全列，新增列自动纳入，无需改触发器。
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0041_eqp_add_fields"
down_revision: str | None = "0040_eqp_equipment"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "equipment",
        sa.Column("rated_power", sa.String(64)),
        schema="eqp",
    )
    op.add_column(
        "equipment",
        sa.Column("origin", sa.String(100)),
        schema="eqp",
    )

    # 列注释（语义校准 + 新字段说明）
    op.execute("COMMENT ON COLUMN eqp.equipment.equipment_name IS '设备名称（中文）'")
    op.execute("COMMENT ON COLUMN eqp.equipment.equipment_name_en IS '设备名称（英文）'")
    op.execute("COMMENT ON COLUMN eqp.equipment.description IS '主要性能参数描述'")
    op.execute("COMMENT ON COLUMN eqp.equipment.rated_power IS '额定功率（自由文本，如 1500W / 220V 50Hz 2kW）'")
    op.execute("COMMENT ON COLUMN eqp.equipment.origin IS '产地'")


def downgrade() -> None:
    op.execute("COMMENT ON COLUMN eqp.equipment.description IS NULL")
    op.execute("COMMENT ON COLUMN eqp.equipment.equipment_name_en IS NULL")
    op.execute("COMMENT ON COLUMN eqp.equipment.equipment_name IS NULL")
    op.drop_column("equipment", "origin", schema="eqp")
    op.drop_column("equipment", "rated_power", schema="eqp")
