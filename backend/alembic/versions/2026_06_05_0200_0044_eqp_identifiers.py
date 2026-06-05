"""eqp.equipment 三标识体系：设备ID(系统) + 设备编号(业务) + 固资编号(财务)

Revision ID: 0044_eqp_identifiers
Revises: 0043_eqp_workstation
Create Date: 2026-06-05 02:00:00.000000

对齐大厂设备主数据实践：主键用系统生成的不可变唯一标识，业务/财务编号作属性。
  - equipment_code 既有：定位为「设备ID」，系统自动生成 EQP-yyyy-NNNNNN，全局唯一、不可改
    （创建端不再接受手填；行为变化，无需改列）
  - 新增 equipment_no(设备编号)：业务/历史号(如 QC001)，沿用现有标签，可不规范、非唯一
  - 新增 fixed_asset_no(固资编号)：财务/ERP 固定资产编号
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0044_eqp_identifiers"
down_revision: str | None = "0043_eqp_workstation"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("equipment", sa.Column("equipment_no", sa.String(64)), schema="eqp")
    op.add_column("equipment", sa.Column("fixed_asset_no", sa.String(64)), schema="eqp")
    op.execute("COMMENT ON COLUMN eqp.equipment.equipment_code IS '设备ID（系统生成 EQP-yyyy-NNNNNN，全局唯一不可改）'")
    op.execute("COMMENT ON COLUMN eqp.equipment.equipment_no IS '设备编号（业务/历史号，如 QC001，沿用现场标签，可非唯一）'")
    op.execute("COMMENT ON COLUMN eqp.equipment.fixed_asset_no IS '固资编号（财务/ERP 固定资产编号）'")
    # 业务号查询用（非唯一，软删过滤）
    op.create_index(
        "ix_eqp_equipment_no", "equipment", ["equipment_no"],
        postgresql_where=sa.text("deleted_at IS NULL"), schema="eqp",
    )


def downgrade() -> None:
    op.drop_index("ix_eqp_equipment_no", table_name="equipment", schema="eqp")
    op.execute("COMMENT ON COLUMN eqp.equipment.equipment_code IS NULL")
    op.drop_column("equipment", "fixed_asset_no", schema="eqp")
    op.drop_column("equipment", "equipment_no", schema="eqp")
