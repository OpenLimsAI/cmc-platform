"""storage_node add equipment_no/equipment_code (bind MDM device)

Revision ID: a83f06b00adb
Revises: d3b5694cf4fe
Create Date: 2026-06-30 08:55:16.678965
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = 'a83f06b00adb'
down_revision = 'd3b5694cf4fe'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 冰箱(FRIDGE)节点绑定 MDM 设备:equipment_no 业务编号(绑定/显示 join 键)+
    # equipment_code MDM 内部码(EQP-...)快照。其余节点(房间/试剂柜/层/盒/孔)为 NULL。
    op.add_column(
        "storage_node",
        sa.Column("equipment_no", sa.String(length=64), nullable=True),
        schema="material_mgmt",
    )
    op.add_column(
        "storage_node",
        sa.Column("equipment_code", sa.String(length=32), nullable=True),
        schema="material_mgmt",
    )


def downgrade() -> None:
    op.drop_column("storage_node", "equipment_code", schema="material_mgmt")
    op.drop_column("storage_node", "equipment_no", schema="material_mgmt")
