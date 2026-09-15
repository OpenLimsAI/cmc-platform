"""新增独立设备状态字段：启用 / 封存 / 报废

Revision ID: 0060_eqp_device_status
Revises: 0059_eqp_alias
Create Date: 2026-09-15 01:00:00.000000

保留原 status（主数据状态：active / retired），新增 equipment_status，
由 MDM 设备专员维护。历史设备默认启用，迁移不根据主数据状态猜测设备状态。
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0060_eqp_device_status"
down_revision: str | None = "0059_eqp_alias"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "equipment",
        sa.Column(
            "equipment_status",
            sa.String(length=32),
            nullable=False,
            server_default="enabled",
            comment="设备状态（由 MDM 设备专员维护）：enabled=启用，sealed=封存，scrapped=报废",
        ),
        schema="eqp",
    )
    op.create_check_constraint(
        "ck_equipment_operational_status",
        "equipment",
        "equipment_status IN ('enabled','sealed','scrapped')",
        schema="eqp",
    )
    op.create_index(
        "ix_eqp_equipment_operational_status",
        "equipment",
        ["equipment_status"],
        schema="eqp",
    )


def downgrade() -> None:
    op.drop_index(
        "ix_eqp_equipment_operational_status",
        table_name="equipment",
        schema="eqp",
    )
    op.drop_constraint(
        "ck_equipment_operational_status",
        "equipment",
        schema="eqp",
        type_="check",
    )
    op.drop_column("equipment", "equipment_status", schema="eqp")
