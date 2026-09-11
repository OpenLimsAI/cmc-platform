"""周期表补三列身份信息：序列号 / 别名 / 固资编号（2026-09-11 晚）

设备验证档案改成「搜一台设备 → 看这一台」之后，搜索要能认序列号和老叫法：
- `serial_no` 出厂序列号 —— 验证报告和设备铭牌上写的就是它，验证部常按这个找
- `alias` 别名 / 曾用名（MDM 0059 加的，多个用 ; 分隔）—— 老员工习惯叫旧称（BR1-1、发酵线1）
- `fixed_asset_no` 固资编号 —— 财务那边的号，偶尔拿着它来问

三列都是 MDM `eqp.equipment` 的**快照**（同步覆盖），本表仍然不是设备台账。
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "qv_cycle_identity_fields"
down_revision = "qv_equipment_cycle"
branch_labels = None
depends_on = None

SCHEMA = "validation"
COLUMNS = {
    "serial_no": (sa.String(100), "出厂序列号（MDM 快照）"),
    "alias": (sa.String(255), "别名 / 曾用名，多个用 ; 分隔（MDM 快照）"),
    "fixed_asset_no": (sa.String(64), "固资编号（MDM 快照）"),
}


def upgrade() -> None:
    for name, (type_, comment) in COLUMNS.items():
        op.add_column("equipment_cycle", sa.Column(name, type_, comment=comment), schema=SCHEMA)
    # 搜序列号是档案页的主路径之一，给一个索引（别名/固资号量小，走顺序扫够了）
    op.create_index("ix_equipment_cycle_serial_no", "equipment_cycle", ["serial_no"], schema=SCHEMA)


def downgrade() -> None:
    op.drop_index("ix_equipment_cycle_serial_no", "equipment_cycle", schema=SCHEMA)
    for name in COLUMNS:
        op.drop_column("equipment_cycle", name, schema=SCHEMA)
