"""ref.asset_substance per DM-MDM-001 V1.0 §11.3

Revision ID: 0025_ref_as
Revises: 0024_ars_status_hist
Create Date: 2026-05-12 01:00:00.000000

M3.3 第 1 步：建 ref.asset_substance（资产-物质组件关系）。

§11.3 实际设计：
  - 复合 PK (asset_id, substance_id, component_role)
  - component_role ∈ {main_component, antibody, linker, payload, excipient, impurity}
  - is_active_ingredient BOOLEAN 默认 TRUE
  - 软删除 deleted_at（与 §11.2 同模式）

audit trigger 接入：v2 第 3 参数 parent_ref 回填 asset_code。
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0025_ref_as"
down_revision: str | None = "0024_ars_status_hist"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "asset_substance",
        sa.Column("asset_id", sa.BigInteger,
                  sa.ForeignKey("ars.asset.asset_id"), nullable=False),
        sa.Column("substance_id", sa.BigInteger,
                  sa.ForeignKey("srs.substance.substance_id"), nullable=False),
        sa.Column("component_role", sa.String(32), nullable=False),
        sa.Column("is_active_ingredient", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("notes", sa.Text),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.Column("created_by", sa.BigInteger, nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.Column("updated_by", sa.BigInteger, nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True)),
        sa.PrimaryKeyConstraint(
            "asset_id", "substance_id", "component_role",
            name="pk_ref_asset_substance",
        ),
        sa.CheckConstraint(
            "component_role IN ('main_component','antibody','linker','payload','excipient','impurity')",
            name="ck_ref_as_role",
        ),
        schema="ref",
    )
    op.create_index(
        "ix_ref_as_asset", "asset_substance", ["asset_id"],
        postgresql_where=sa.text("deleted_at IS NULL"), schema="ref",
    )
    op.create_index(
        "ix_ref_as_substance", "asset_substance", ["substance_id"],
        postgresql_where=sa.text("deleted_at IS NULL"), schema="ref",
    )

    # 接入审计：trigger 第 1 参数按 §11.3 用 asset_id（无单一 ID）；
    # 第 3 参数 parent_ref 让 entity_code 回填 asset_code（实施侧加强）
    op.execute("""
        CREATE TRIGGER trg_ref_as_audit
        AFTER INSERT OR UPDATE OR DELETE ON ref.asset_substance
        FOR EACH ROW EXECUTE FUNCTION audit.fn_audit_trigger(
            'asset_id', '', 'ars.asset:asset_id:asset_code:asset_id'
        );
    """)


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_ref_as_audit ON ref.asset_substance")
    op.drop_table("asset_substance", schema="ref")
