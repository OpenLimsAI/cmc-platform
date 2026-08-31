"""location room_no cabinet_no 放宽到 80 name 200

Revision ID: 29b4dfac6278
Revises: 68779bdbef03
Create Date: 2026-08-31 20:47:10.844879
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = '29b4dfac6278'
down_revision = '68779bdbef03'
branch_labels = None
depends_on = None


_NAME_EXPR = "(room_no || '-' || cabinet_no || '-L' || layer_no)"


def _readd_name(length: int) -> None:
    # name 是 STORED 生成列;Postgres 不允许直接改它依赖列的类型,只能先删后建
    op.execute(
        f"ALTER TABLE material_mgmt.location ADD COLUMN name VARCHAR({length}) "
        f"GENERATED ALWAYS AS {_NAME_EXPR} STORED"
    )


def upgrade() -> None:
    # 位置树节点改名(storage_node.label ≤ 80)会把新名字同步写进 location.room_no/cabinet_no,
    # 原 VARCHAR(20) 比 label 窄,超过 20 字的名字直接报错。放宽到同宽;生成列 name 随之放宽。
    op.drop_column("location", "name", schema="material_mgmt")
    op.alter_column("location", "room_no", type_=sa.String(80), existing_type=sa.String(20),
                    existing_nullable=False, schema="material_mgmt")
    op.alter_column("location", "cabinet_no", type_=sa.String(80), existing_type=sa.String(20),
                    existing_nullable=False, schema="material_mgmt")
    _readd_name(200)


def downgrade() -> None:
    # 若已有超过 20 字的值,收窄会失败——属预期(先清理数据再回退)
    op.drop_column("location", "name", schema="material_mgmt")
    op.alter_column("location", "cabinet_no", type_=sa.String(20), existing_type=sa.String(80),
                    existing_nullable=False, schema="material_mgmt")
    op.alter_column("location", "room_no", type_=sa.String(20), existing_type=sa.String(80),
                    existing_nullable=False, schema="material_mgmt")
    _readd_name(80)
