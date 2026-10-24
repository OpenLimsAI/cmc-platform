"""cmc_analytics：dim.equipment_master 补 equipment_no，指向 MDM 设备台账；表定位改为「数据采集映射表」（2026-09-10）

白皮书 V0.4 决策 D9 / 待落地项 L13：设备台账的权威源是 cmab_mdm.eqp.equipment（全公司 463 台，
设备编号 equipment_no、名称、型号、厂家、资产信息都在那）；本表只登记「有数据接入的设备」的
source_instance → 产线 / 工艺段 / 厂商 / 型号映射，并通过 equipment_no 指向 MDM 那一行。

跨库不能建外键，用可空列 + 部分唯一索引：填了就必须唯一，没填（尚未对上 MDM）允许为空。
现有唯一一行（Nova FLEX2）暂不填，等负责人在 MDM 里确认对应设备后再补。

Revision ID: cmc_analytics_equipment_no
Revises: cmc_analytics_mdm_to_dim
Create Date: 2026-09-10
"""
from __future__ import annotations

from alembic import op

revision = "cmc_analytics_equipment_no"
down_revision = "cmc_analytics_mdm_to_dim"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE dim.equipment_master ADD COLUMN equipment_no text")
    op.execute(
        "COMMENT ON COLUMN dim.equipment_master.equipment_no IS "
        "'MDM 设备台账编号 = cmab_mdm.eqp.equipment.equipment_no（设备主数据权威源，白皮书 D9）。"
        "跨库无外键，靠此列对齐；未对上 MDM 前允许为空。'"
    )
    op.execute(
        "CREATE UNIQUE INDEX uq_equipment_master_equipment_no ON dim.equipment_master (equipment_no) "
        "WHERE equipment_no IS NOT NULL"
    )
    op.execute(
        "COMMENT ON TABLE dim.equipment_master IS "
        "'数据采集映射表（白皮书 D9，2026-09-10）：只登记有数据接入的设备，记录 source_instance 与产线/工艺段/厂商/型号的对应，"
        "并以 equipment_no 指向 MDM 设备台账 cmab_mdm.eqp.equipment。设备本身的编号/名称/资产信息以 MDM 为准。"
        "ETL 写入前 source_instance 须先在此注册；下游 join 本表取业务属性，禁止字符串解析。'"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS dim.uq_equipment_master_equipment_no")
    op.execute("ALTER TABLE dim.equipment_master DROP COLUMN equipment_no")
    op.execute(
        "COMMENT ON TABLE dim.equipment_master IS '设备维度权威表：每个 source_instance 先在此注册，下游 join 取业务属性'"
    )
