"""ars.asset main table per DM-MDM-001 V1.0 §8.2

Revision ID: 0022_ars_asset
Revises: 0021_protein_hash
Create Date: 2026-05-12 00:30:00.000000

M3.1 第 1 步：建 ars.asset 主表 + 关联触发器。

字段集严格按 §8.2 DDL，含两套独立维度：
  - current_phase：业务进度（discovery → marketed 9 值），通过 PUT 直接更新
  - status：管控状态（active/on_hold/terminated 3 值），通过状态机端点（M3.2）

编码：AST-XXXXXXX 全局序列（不按年，asset 长生命周期年度复位无意义）。
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0022_ars_asset"
down_revision: str | None = "0021_protein_hash"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # ============== 注册 asset 编码序列 ==============
    op.execute("""
        INSERT INTO meta.code_sequence (sequence_name, prefix, padding_length, description)
        VALUES ('asset', 'AST-', 7, 'Asset 编码序列：AST-0000001 ...')
        ON CONFLICT (sequence_name) DO NOTHING;
    """)

    # ============== ars.asset ==============
    op.create_table(
        "asset",
        sa.Column("asset_id", sa.BigInteger, sa.Identity(always=True), primary_key=True),
        sa.Column("asset_code", sa.String(32), nullable=False),
        # 基本信息
        sa.Column("internal_name", sa.String(255), nullable=False),
        sa.Column("trade_name", sa.String(255)),
        sa.Column("inn_name", sa.String(255)),
        # 资产属性
        sa.Column("asset_type", sa.String(32), nullable=False),
        sa.Column("therapeutic_area", sa.String(64)),
        sa.Column("indication", sa.Text),
        sa.Column("dosage_form", sa.String(64)),
        sa.Column("strength", sa.String(64)),
        sa.Column("route_of_administration", sa.String(32)),
        # 阶段
        sa.Column("current_phase", sa.String(32), nullable=False, server_default="discovery"),
        sa.Column("phase_change_at", sa.DateTime(timezone=True)),
        # 状态
        sa.Column("status", sa.String(32), nullable=False, server_default="active"),
        # 商业属性
        sa.Column("is_commercial", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("first_approval_date", sa.Date),
        sa.Column("first_launch_date", sa.Date),
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
        sa.Column("version", sa.Integer, nullable=False, server_default="1"),
        # 约束
        sa.UniqueConstraint("asset_code", name="uq_asset_code"),
        sa.CheckConstraint(
            "asset_type IN ('mab','bispecific','adc','fusion','small_molecule','combination','other')",
            name="ck_asset_type",
        ),
        sa.CheckConstraint(
            "current_phase IN ('discovery','preclinical','phase_1','phase_2','phase_3',"
            "'submission','approved','marketed','discontinued')",
            name="ck_asset_phase",
        ),
        sa.CheckConstraint(
            "status IN ('active','on_hold','terminated')",
            name="ck_asset_status",
        ),
        schema="ars",
    )

    # 索引
    op.create_index(
        "ix_asset_type", "asset", ["asset_type"],
        postgresql_where=sa.text("deleted_at IS NULL"), schema="ars",
    )
    op.create_index(
        "ix_asset_phase", "asset", ["current_phase"],
        postgresql_where=sa.text("deleted_at IS NULL"), schema="ars",
    )
    op.create_index(
        "ix_asset_status", "asset", ["status"],
        postgresql_where=sa.text("deleted_at IS NULL"), schema="ars",
    )
    op.execute(
        "CREATE INDEX ix_asset_name "
        "ON ars.asset USING gin(internal_name gin_trgm_ops)"
    )
    op.execute(
        "CREATE INDEX ix_asset_trade "
        "ON ars.asset USING gin(trade_name gin_trgm_ops)"
    )

    # ============== BEFORE UPDATE: updated_at + version+1 ==============
    op.execute("""
        CREATE OR REPLACE FUNCTION ars.fn_asset_before_update()
        RETURNS TRIGGER AS $$
        BEGIN
            NEW.updated_at := NOW();
            NEW.version    := OLD.version + 1;
            -- current_phase 变化时记 phase_change_at
            IF OLD.current_phase IS DISTINCT FROM NEW.current_phase THEN
                NEW.phase_change_at := NOW();
            END IF;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
    """)
    op.execute("""
        CREATE TRIGGER trg_asset_before_update
        BEFORE UPDATE ON ars.asset
        FOR EACH ROW EXECUTE FUNCTION ars.fn_asset_before_update();
    """)

    # ============== BEFORE INSERT: 自动分配 asset_code ==============
    op.execute("""
        CREATE OR REPLACE FUNCTION ars.fn_asset_assign_code()
        RETURNS TRIGGER AS $$
        BEGIN
            IF NEW.asset_code IS NULL OR NEW.asset_code = '' THEN
                NEW.asset_code := meta.fn_next_code('asset');
            END IF;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
    """)
    op.execute("""
        CREATE TRIGGER trg_asset_assign_code
        BEFORE INSERT ON ars.asset
        FOR EACH ROW EXECUTE FUNCTION ars.fn_asset_assign_code();
    """)

    # ============== 接入审计 ==============
    op.execute("""
        CREATE TRIGGER trg_asset_audit
        AFTER INSERT OR UPDATE OR DELETE ON ars.asset
        FOR EACH ROW EXECUTE FUNCTION audit.fn_audit_trigger('asset_id', 'asset_code');
    """)


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_asset_audit ON ars.asset")
    op.execute("DROP TRIGGER IF EXISTS trg_asset_assign_code ON ars.asset")
    op.execute("DROP FUNCTION IF EXISTS ars.fn_asset_assign_code()")
    op.execute("DROP TRIGGER IF EXISTS trg_asset_before_update ON ars.asset")
    op.execute("DROP FUNCTION IF EXISTS ars.fn_asset_before_update()")
    op.drop_table("asset", schema="ars")
    op.execute("DELETE FROM meta.code_sequence WHERE sequence_name = 'asset'")
