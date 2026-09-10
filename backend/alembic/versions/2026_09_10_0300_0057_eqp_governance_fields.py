"""eqp.equipment 公司级设备清单治理字段：使用部门 / 厂区 / 房间 / 分级 / 分级依据 / 启用日期

Revision ID: 0057_eqp_governance_fields
Revises: 0056_audit_indexes
Create Date: 2026-09-10 03:00:00.000000

背景（负责人 2026-09-10 拍板）：MDM 设备表升级为**全公司设备清单**，由设备部维护；
计量归计量专员、验证归验证部平台（cmab_qv）、LabOps 只留研发运营数据。
验证主计划 / 看板要按部门、厂区看设备，分级决定验证周期，所以这几项进主数据：

  - department        使用部门（自由文本，与 auth.user.department 同口径；现有 463 台全是研发设备 → 回填「研发部」）
  - site              厂区（南楼 / 北楼 / 祥泰路 …）
  - room              房间 / 存放位置（如 3129培养间）
  - criticality       设备分级。字典按分类走：
                        分析仪器（检验设备）→ USP 口径 A / B / C
                        其他分类（生产/公用/通用/IT）→ 关键 / 一般
                      DB CHECK 约束兜底，服务层同样校验
  - criticality_basis 分级依据（自由文本）
  - commission_date   首次启用日期（与 purchase_date 购入日期分开；设备部台账只有年月，取当月 1 日）

不加「用途类型」字段：保留现有 5 分类，冰箱等归通用/公用，分级规则按分类区分即可。
出厂日期 / 总重 / 别名等台账杂项进 extra，不占正式列。
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0057_eqp_governance_fields"
down_revision: str | None = "0056_audit_indexes"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

CK_CRITICALITY = (
    "criticality IS NULL "
    "OR (category = '分析仪器' AND criticality IN ('A','B','C')) "
    "OR (category <> '分析仪器' AND criticality IN ('关键','一般'))"
)


def upgrade() -> None:
    op.add_column("equipment", sa.Column("department", sa.String(64)), schema="eqp")
    op.add_column("equipment", sa.Column("site", sa.String(64)), schema="eqp")
    op.add_column("equipment", sa.Column("room", sa.String(100)), schema="eqp")
    op.add_column("equipment", sa.Column("criticality", sa.String(16)), schema="eqp")
    op.add_column("equipment", sa.Column("criticality_basis", sa.Text()), schema="eqp")
    op.add_column("equipment", sa.Column("commission_date", sa.Date()), schema="eqp")

    op.create_check_constraint(
        "ck_equipment_criticality", "equipment", CK_CRITICALITY, schema="eqp"
    )
    op.create_index(
        "ix_eqp_equipment_department", "equipment", ["department"],
        postgresql_where=sa.text("deleted_at IS NULL"), schema="eqp",
    )

    op.execute("COMMENT ON COLUMN eqp.equipment.department IS '使用部门（与 auth.user.department 同口径的部门名/代码）'")
    op.execute("COMMENT ON COLUMN eqp.equipment.site IS '厂区（南楼 / 北楼 / 祥泰路 …）'")
    op.execute("COMMENT ON COLUMN eqp.equipment.room IS '房间 / 存放位置（如 3129培养间）'")
    op.execute("COMMENT ON COLUMN eqp.equipment.criticality IS '设备分级：分析仪器 → A/B/C（USP）；其他分类 → 关键/一般'")
    op.execute("COMMENT ON COLUMN eqp.equipment.criticality_basis IS '分级依据'")
    op.execute("COMMENT ON COLUMN eqp.equipment.commission_date IS '首次启用日期（台账仅年月时取当月 1 日）'")

    # 现有设备全部是研发部门的（负责人 2026-09-10），统一回填
    op.execute(
        "UPDATE eqp.equipment SET department = '研发部' "
        "WHERE department IS NULL AND deleted_at IS NULL"
    )


def downgrade() -> None:
    op.drop_index("ix_eqp_equipment_department", table_name="equipment", schema="eqp")
    op.drop_constraint("ck_equipment_criticality", "equipment", schema="eqp", type_="check")
    for col in ("commission_date", "criticality_basis", "criticality", "room", "site", "department"):
        op.drop_column("equipment", col, schema="eqp")
