"""eqp.equipment 设备主数据表

Revision ID: 0040_eqp_equipment
Revises: 0039_mm_category_add_waibao
Create Date: 2026-06-04 01:00:00.000000

EQP 设备主数据域第 1 步：建 eqp schema + equipment 主表 + 关联触发器。

定位：全公司仪器设备身份注册表，下游 CMC LabOps Portal(cmc-inventory) 的数据上游。
仅管主数据(身份/采购属性)；运营数据(在用状态/位置/负责人/校验/维护/维修/保修/附件)
在 LabOps 的 equipment_mgmt schema(独立 PG 实例)，通过 API 按需拉取，不跨库外键。

设计对标 mm.material：
  - 无状态机(status ∈ active/retired，PUT 直接改)、无 version、无 e_signature
  - 编码 EQP-yyyyXXXXXX 年度序列(留空自动分配)，也允许手动传入沿用历史编号
  - 接入审计 v3(id_col='equipment_id', code_col='equipment_code')
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0040_eqp_equipment"
down_revision: str | None = "0039_mm_category_add_waibao"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # ============== eqp schema ==============
    op.execute("CREATE SCHEMA IF NOT EXISTS eqp")

    # ============== eqp.equipment ==============
    op.create_table(
        "equipment",
        sa.Column("equipment_id", sa.BigInteger, sa.Identity(always=True), primary_key=True),
        sa.Column("equipment_code", sa.String(32), nullable=False),
        # 基本信息
        sa.Column("equipment_name", sa.String(255), nullable=False),
        sa.Column("equipment_name_en", sa.String(255)),
        sa.Column("category", sa.String(64), nullable=False),
        # 厂商 & 规格(身份属性)
        sa.Column("model", sa.String(200)),
        sa.Column("manufacturer", sa.String(100)),
        sa.Column("serial_no", sa.String(100)),
        # 采购属性
        sa.Column("purchase_date", sa.Date),
        sa.Column("asset_value", sa.Numeric(12, 2)),
        sa.Column("supplier", sa.String(200)),
        # 状态
        sa.Column("status", sa.String(32), nullable=False, server_default="active"),
        # 描述
        sa.Column("description", sa.Text),
        sa.Column("notes", sa.Text),
        sa.Column("extra", postgresql.JSONB),
        # 审计
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.Column("created_by", sa.BigInteger, sa.ForeignKey("auth.user.user_id"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.Column("updated_by", sa.BigInteger, sa.ForeignKey("auth.user.user_id"), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True)),
        sa.Column("deleted_by", sa.BigInteger, sa.ForeignKey("auth.user.user_id")),
        # 约束
        sa.UniqueConstraint("equipment_code", name="uq_eqp_equipment_code"),
        sa.CheckConstraint(
            "category IN ('分析仪器','实验设备','辅助设备','其他')",
            name="ck_equipment_category",
        ),
        sa.CheckConstraint(
            "status IN ('active','retired')",
            name="ck_equipment_status",
        ),
        schema="eqp",
    )

    # 索引
    op.create_index(
        "ix_eqp_equipment_category", "equipment", ["category"],
        postgresql_where=sa.text("deleted_at IS NULL"), schema="eqp",
    )
    op.create_index(
        "ix_eqp_equipment_status", "equipment", ["status"],
        postgresql_where=sa.text("deleted_at IS NULL"), schema="eqp",
    )
    op.create_index(
        "ix_eqp_equipment_manufacturer", "equipment", ["manufacturer"],
        schema="eqp",
    )
    op.execute(
        "CREATE INDEX ix_eqp_equipment_name "
        "ON eqp.equipment USING gin(equipment_name gin_trgm_ops)"
    )

    # ============== BEFORE UPDATE: 维护 updated_at ==============
    op.execute("""
        CREATE OR REPLACE FUNCTION eqp.fn_equipment_before_update()
        RETURNS TRIGGER AS $$
        BEGIN
            NEW.updated_at := NOW();
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
    """)
    op.execute("""
        CREATE TRIGGER trg_equipment_before_update
        BEFORE UPDATE ON eqp.equipment
        FOR EACH ROW EXECUTE FUNCTION eqp.fn_equipment_before_update();
    """)

    # ============== BEFORE INSERT: 自动分配 equipment_code EQP-yyyyXXXXXX ==============
    op.execute("""
        CREATE OR REPLACE FUNCTION eqp.fn_equipment_assign_code()
        RETURNS TRIGGER AS $$
        DECLARE
            v_year     INT;
            v_seq_name VARCHAR;
        BEGIN
            IF NEW.equipment_code IS NULL OR NEW.equipment_code = '' THEN
                v_year := EXTRACT(YEAR FROM NOW())::INT;
                v_seq_name := meta.fn_ensure_year_sequence('equipment', 'EQP-', v_year, 6);
                NEW.equipment_code := meta.fn_next_code(v_seq_name);
            END IF;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
    """)
    op.execute("""
        CREATE TRIGGER trg_equipment_assign_code
        BEFORE INSERT ON eqp.equipment
        FOR EACH ROW EXECUTE FUNCTION eqp.fn_equipment_assign_code();
    """)

    # ============== 接入审计 v3 ==============
    op.execute("""
        CREATE TRIGGER trg_equipment_audit
        AFTER INSERT OR UPDATE OR DELETE ON eqp.equipment
        FOR EACH ROW EXECUTE FUNCTION audit.fn_audit_trigger('equipment_id', 'equipment_code');
    """)


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_equipment_audit ON eqp.equipment")
    op.execute("DROP TRIGGER IF EXISTS trg_equipment_assign_code ON eqp.equipment")
    op.execute("DROP FUNCTION IF EXISTS eqp.fn_equipment_assign_code()")
    op.execute("DROP TRIGGER IF EXISTS trg_equipment_before_update ON eqp.equipment")
    op.execute("DROP FUNCTION IF EXISTS eqp.fn_equipment_before_update()")
    op.drop_table("equipment", schema="eqp")
    op.execute("DELETE FROM meta.code_sequence WHERE sequence_name LIKE 'equipment_%'")
    op.execute("DROP SCHEMA IF EXISTS eqp")
