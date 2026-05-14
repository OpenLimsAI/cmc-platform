"""mm.material main table per DM-MDM-001 V1.1 §10.1

Revision ID: 0032_mm_material
Revises: 0031_h1_team_unique_ref_fks
Create Date: 2026-05-13 04:00:00.000000

Phase 4.A 物料域 M4.1 第 1 步：建 mm.material 主表 + 关联触发器。

字段集严格按 V1.1 §10.1 DDL：
  - material_type ∈ candidate/reference/stability/buffer/raw/intermediate/other (7 值)
  - status ∈ active/quarantine/released/rejected/retired (5 值，**无状态机**，PUT 直接改)
  - grade ∈ RUO/GMP/Reference Standard/Working Standard (4 值，可空)
  - substance_id 可空 FK → srs.substance（直接关联，无 ref.substance_material）

编码：MAT-yyyyXXXXXX 年度序列（与 §10.1 一致；MAT 类似 PRJ 走 fn_ensure_year_sequence 6 位 padding）。

注意与 SRS/ARS/PRS 的关键差异：
  - 无 status_history 表（V1.1 §10 未列）
  - 无 e_signature_id（无状态机即无 GxP 关键转移）
  - 无 phase_change_at / version 字段（不走乐观锁，§10.1 无 version 列）
  - 接入审计 v2（id_col='material_id', code_col='material_code'）
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0032_mm_material"
down_revision: str | None = "0031_h1_team_unique_ref_fks"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # ============== mm.material ==============
    op.create_table(
        "material",
        sa.Column("material_id", sa.BigInteger, sa.Identity(always=True), primary_key=True),
        sa.Column("material_code", sa.String(32), nullable=False),
        # 基本信息
        sa.Column("material_name", sa.String(255), nullable=False),
        sa.Column("material_name_en", sa.String(255)),
        sa.Column("material_type", sa.String(32), nullable=False),
        # 物质引用
        sa.Column(
            "substance_id",
            sa.BigInteger,
            sa.ForeignKey("srs.substance.substance_id"),
        ),
        # 物理属性
        sa.Column("physical_form", sa.String(64)),
        sa.Column("storage_condition", sa.String(64)),
        # 来源
        sa.Column("source_type", sa.String(32)),
        sa.Column("source_name", sa.String(128)),
        # 级别
        sa.Column("grade", sa.String(32)),
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
        sa.UniqueConstraint("material_code", name="uq_material_code"),
        sa.CheckConstraint(
            "material_type IN ('candidate','reference','stability','buffer','raw',"
            "'intermediate','other')",
            name="ck_material_type",
        ),
        sa.CheckConstraint(
            "grade IS NULL OR grade IN "
            "('RUO','GMP','Reference Standard','Working Standard')",
            name="ck_material_grade",
        ),
        sa.CheckConstraint(
            "status IN ('active','quarantine','released','rejected','retired')",
            name="ck_material_status",
        ),
        schema="mm",
    )

    # 索引（§10.1）
    op.create_index(
        "ix_material_type", "material", ["material_type"],
        postgresql_where=sa.text("deleted_at IS NULL"), schema="mm",
    )
    op.create_index(
        "ix_material_substance", "material", ["substance_id"],
        schema="mm",
    )
    op.create_index(
        "ix_material_status", "material", ["status"],
        postgresql_where=sa.text("deleted_at IS NULL"), schema="mm",
    )
    op.execute(
        "CREATE INDEX ix_material_name "
        "ON mm.material USING gin(material_name gin_trgm_ops)"
    )

    # ============== BEFORE UPDATE: 维护 updated_at ==============
    # mm.material 无 version 字段（V1.1 §10.1 未列），仅触发 updated_at 刷新
    op.execute("""
        CREATE OR REPLACE FUNCTION mm.fn_material_before_update()
        RETURNS TRIGGER AS $$
        BEGIN
            NEW.updated_at := NOW();
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
    """)
    op.execute("""
        CREATE TRIGGER trg_material_before_update
        BEFORE UPDATE ON mm.material
        FOR EACH ROW EXECUTE FUNCTION mm.fn_material_before_update();
    """)

    # ============== BEFORE INSERT: 自动分配 material_code MAT-yyyyXXXXXX ==============
    op.execute("""
        CREATE OR REPLACE FUNCTION mm.fn_material_assign_code()
        RETURNS TRIGGER AS $$
        DECLARE
            v_year     INT;
            v_seq_name VARCHAR;
        BEGIN
            IF NEW.material_code IS NULL OR NEW.material_code = '' THEN
                v_year := EXTRACT(YEAR FROM NOW())::INT;
                v_seq_name := meta.fn_ensure_year_sequence('material', 'MAT-', v_year, 6);
                NEW.material_code := meta.fn_next_code(v_seq_name);
            END IF;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
    """)
    op.execute("""
        CREATE TRIGGER trg_material_assign_code
        BEFORE INSERT ON mm.material
        FOR EACH ROW EXECUTE FUNCTION mm.fn_material_assign_code();
    """)

    # ============== 接入审计（v2 双参签名） ==============
    op.execute("""
        CREATE TRIGGER trg_material_audit
        AFTER INSERT OR UPDATE OR DELETE ON mm.material
        FOR EACH ROW EXECUTE FUNCTION audit.fn_audit_trigger('material_id', 'material_code');
    """)


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_material_audit ON mm.material")
    op.execute("DROP TRIGGER IF EXISTS trg_material_assign_code ON mm.material")
    op.execute("DROP FUNCTION IF EXISTS mm.fn_material_assign_code()")
    op.execute("DROP TRIGGER IF EXISTS trg_material_before_update ON mm.material")
    op.execute("DROP FUNCTION IF EXISTS mm.fn_material_before_update()")
    op.drop_table("material", schema="mm")
    # 年度序列 meta.material_yyyy 由 fn_ensure_year_sequence 动态创建，
    # 这里清掉本年度可能已创建的序列（与 PRS 0013 模式一致）
    op.execute("""
        DO $$
        DECLARE
            r RECORD;
        BEGIN
            FOR r IN
                SELECT sequence_name FROM meta.code_sequence WHERE sequence_name LIKE 'material_%'
            LOOP
                DELETE FROM meta.code_sequence WHERE sequence_name = r.sequence_name;
            END LOOP;
        END $$;
    """)
