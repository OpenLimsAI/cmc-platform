"""eqp.equipment 增字段：附带专用工作站标志 + 工作站配置

Revision ID: 0043_eqp_workstation
Revises: 0042_eqp_category_5class
Create Date: 2026-06-05 01:00:00.000000

- has_workstation BOOLEAN：是否附带专用工作站（如 HPLC 自带控制电脑）
- workstation_info JSONB：勾选后填写的工作站/本机硬件配置，键：
    brand/model/serial（电脑身份；IT 类设备复用主字段不填）
    os/cpu/gpu/ram/disk
    monitor_brand/monitor_model/monitor_serial
  IT/自动化与数据系统 分类的设备本身即电脑，前端自动展开 spec 子集填本机配置。
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0043_eqp_workstation"
down_revision: str | None = "0042_eqp_category_5class"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "equipment",
        sa.Column(
            "has_workstation", sa.Boolean(), nullable=False, server_default=sa.false()
        ),
        schema="eqp",
    )
    op.add_column(
        "equipment",
        sa.Column("workstation_info", postgresql.JSONB),
        schema="eqp",
    )
    op.execute("COMMENT ON COLUMN eqp.equipment.has_workstation IS '是否附带专用工作站'")
    op.execute(
        "COMMENT ON COLUMN eqp.equipment.workstation_info IS "
        "'工作站/本机硬件配置 JSONB：brand/model/serial/os/cpu/gpu/ram/disk/monitor_*'"
    )


def downgrade() -> None:
    op.drop_column("equipment", "workstation_info", schema="eqp")
    op.drop_column("equipment", "has_workstation", schema="eqp")
