"""mm.material_batch sub-table per DM-MDM-001 V1.1 §10.2

Revision ID: 0033_mm_material_batch
Revises: 0032_mm_material
Create Date: 2026-05-13 05:00:00.000000

Phase 4.A 物料域 M4.2：建 mm.material_batch 子表 + 接入审计。

字段集严格按 V1.1 §10.2 DDL：
  - PK: batch_id BIGINT identity
  - UNIQUE (material_id, batch_number) — 同物料下批号唯一
  - status ∈ in_stock/in_use/depleted/expired/recalled (5 值)
  - 时间：manufacture_date / expiry_date / receive_date
  - 数量：quantity_value NUMERIC(18,4) + quantity_unit
  - 来源：source_batch_ref / coa_url
  - 存储：storage_location

注意点：
  - V1.1 §10.2 字段集 **无 deleted_by**（只有 deleted_at），但与 0027 软删除 _by 统一原则保持，
    仍补 deleted_by（FK auth.user）— 对齐 Phase 1-3 全表统一惯例
  - V1.1 §10.2 **未列 audit trigger** — 但为支持详情页"审计 Tab"展示批次变更，本实施侧
    挂上 audit v2 第 3 参 parent_ref 回填 material_code（与 prs.project_milestone 同模式）
  - 接 BEFORE UPDATE 触发器维护 updated_at（与 prs.fn_touch_updated_at 同模式）
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0033_mm_material_batch"
down_revision: str | None = "0032_mm_material"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "material_batch",
        sa.Column("batch_id", sa.BigInteger, sa.Identity(always=True), primary_key=True),
        sa.Column(
            "material_id",
            sa.BigInteger,
            sa.ForeignKey("mm.material.material_id"),
            nullable=False,
        ),
        sa.Column("batch_number", sa.String(64), nullable=False),
        # 数量
        sa.Column("quantity_value", sa.Numeric(18, 4)),
        sa.Column("quantity_unit", sa.String(16)),
        # 时间
        sa.Column("manufacture_date", sa.Date),
        sa.Column("expiry_date", sa.Date),
        sa.Column("receive_date", sa.Date),
        # 状态
        sa.Column("status", sa.String(32), nullable=False, server_default="in_stock"),
        # 来源
        sa.Column("source_batch_ref", sa.String(128)),
        sa.Column("coa_url", sa.Text),
        # 存储
        sa.Column("storage_location", sa.String(128)),
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
        sa.UniqueConstraint("material_id", "batch_number", name="uq_material_batch"),
        sa.CheckConstraint(
            "status IN ('in_stock','in_use','depleted','expired','recalled')",
            name="ck_material_batch_status",
        ),
        schema="mm",
    )

    # 索引（§10.2）
    op.create_index(
        "ix_material_batch_material", "material_batch", ["material_id"],
        schema="mm",
    )
    op.create_index(
        "ix_material_batch_expiry", "material_batch", ["expiry_date"],
        postgresql_where=sa.text("deleted_at IS NULL"), schema="mm",
    )

    # ============== BEFORE UPDATE: updated_at ==============
    op.execute("""
        CREATE OR REPLACE FUNCTION mm.fn_material_batch_before_update()
        RETURNS TRIGGER AS $$
        BEGIN
            NEW.updated_at := NOW();
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
    """)
    op.execute("""
        CREATE TRIGGER trg_material_batch_before_update
        BEFORE UPDATE ON mm.material_batch
        FOR EACH ROW EXECUTE FUNCTION mm.fn_material_batch_before_update();
    """)

    # ============== 接入审计（v2 三参 parent_ref 回填 material_code） ==============
    # V1.1 §10.2 未列；实施侧补齐以支持详情页"审计 Tab"完整变更链
    op.execute("""
        CREATE TRIGGER trg_material_batch_audit
        AFTER INSERT OR UPDATE OR DELETE ON mm.material_batch
        FOR EACH ROW EXECUTE FUNCTION audit.fn_audit_trigger(
            'batch_id', '', 'mm.material:material_id:material_code:material_id'
        );
    """)


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_material_batch_audit ON mm.material_batch")
    op.execute("DROP TRIGGER IF EXISTS trg_material_batch_before_update ON mm.material_batch")
    op.execute("DROP FUNCTION IF EXISTS mm.fn_material_batch_before_update()")
    op.drop_table("material_batch", schema="mm")
