"""eqp.equipment 设备分类改为 5 类体系

Revision ID: 0042_eqp_category_5class
Revises: 0041_eqp_add_fields
Create Date: 2026-06-04 03:00:00.000000

分类从旧 4 类（分析仪器/实验设备/辅助设备/其他）改为新 5 类：
  分析仪器 / 工艺/制备设备 / 通用实验室设备 / 公用工程/环境与支持系统 / IT/自动化与数据系统

旧值重映射（防御性，保护各机已录数据；干净环境影响 0 行）：
  实验设备 → 通用实验室设备
  其他     → 通用实验室设备
  辅助设备 → 公用工程/环境与支持系统
  分析仪器 → 分析仪器（不变）
重映射期间关闭审计触发器（migration 无 session 用户上下文，且这是 schema 级数据校准）。
"""
from collections.abc import Sequence

from alembic import op

revision: str = "0042_eqp_category_5class"
down_revision: str | None = "0041_eqp_add_fields"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

NEW_CATEGORIES = (
    "分析仪器",
    "工艺/制备设备",
    "通用实验室设备",
    "公用工程/环境与支持系统",
    "IT/自动化与数据系统",
)
OLD_CATEGORIES = ("分析仪器", "实验设备", "辅助设备", "其他")


def _in_list(values) -> str:
    return ", ".join("'" + v.replace("'", "''") + "'" for v in values)


# 按 category 列发现旧约束名后删除（不写死名字）。
# 背景：metadata naming_convention(ck_%(table)s_%(constraint_name)s) 会对既有约束名
# 二次套前缀——0040 实际产出的是 ck_equipment_ck_equipment_category（双重前缀）；
# 各机当前名可能不一致（双重前缀 / 已手工规整），故 DROP 按列发现。
def _drop_category_constraint() -> None:
    op.execute(
        """
        DO $$
        DECLARE c text;
        BEGIN
            SELECT conname INTO c FROM pg_constraint
             WHERE conrelid = 'eqp.equipment'::regclass AND contype = 'c'
               AND pg_get_constraintdef(oid) LIKE '%(category)%';
            IF c IS NOT NULL THEN
                EXECUTE format('ALTER TABLE eqp.equipment DROP CONSTRAINT %I', c);
            END IF;
        END $$;
        """
    )


def _add_category_constraint(values) -> None:
    op.execute(
        "ALTER TABLE eqp.equipment ADD CONSTRAINT ck_equipment_category "
        f"CHECK (category IN ({_in_list(values)}))"
    )


# 关键顺序：先删旧约束 → 再 UPDATE 重映射到新值 → 最后加新约束。
# 否则把 category 改成新值时旧约束仍生效会 CheckViolation（表非空时必现）。
def upgrade() -> None:
    op.execute("ALTER TABLE eqp.equipment DISABLE TRIGGER trg_equipment_audit")
    _drop_category_constraint()
    op.execute("UPDATE eqp.equipment SET category='通用实验室设备' WHERE category IN ('实验设备','其他')")
    op.execute("UPDATE eqp.equipment SET category='公用工程/环境与支持系统' WHERE category='辅助设备'")
    _add_category_constraint(NEW_CATEGORIES)
    op.execute("ALTER TABLE eqp.equipment ENABLE TRIGGER trg_equipment_audit")


def downgrade() -> None:
    op.execute("ALTER TABLE eqp.equipment DISABLE TRIGGER trg_equipment_audit")
    _drop_category_constraint()
    op.execute("UPDATE eqp.equipment SET category='实验设备' WHERE category IN ('工艺/制备设备','通用实验室设备')")
    op.execute("UPDATE eqp.equipment SET category='辅助设备' WHERE category='公用工程/环境与支持系统'")
    op.execute("UPDATE eqp.equipment SET category='其他' WHERE category='IT/自动化与数据系统'")
    _add_category_constraint(OLD_CATEGORIES)
    op.execute("ALTER TABLE eqp.equipment ENABLE TRIGGER trg_equipment_audit")
