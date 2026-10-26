"""ars.asset_market_id per DM-MDM-001 V1.0 §8.3

Revision ID: 0023_ars_market_id
Revises: 0022_ars_asset
Create Date: 2026-05-12 00:40:00.000000

M3.1 第 2 步：建 ars.asset_market_id 多市场注册号子表。
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0023_ars_market_id"
down_revision: str | None = "0022_ars_asset"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "asset_market_id",
        sa.Column("market_id_pk", sa.BigInteger, sa.Identity(always=True), primary_key=True),
        sa.Column("asset_id", sa.BigInteger,
                  sa.ForeignKey("ars.asset.asset_id"), nullable=False),
        sa.Column("market_code", sa.String(8), nullable=False),
        sa.Column("id_type", sa.String(32), nullable=False),
        sa.Column("id_value", sa.String(128), nullable=False),
        sa.Column("issuing_authority", sa.String(128)),
        sa.Column("application_date", sa.Date),
        sa.Column("approval_date", sa.Date),
        sa.Column("expiry_date", sa.Date),
        sa.Column("status", sa.String(32)),
        sa.Column("notes", sa.Text),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.Column("created_by", sa.BigInteger, sa.ForeignKey("auth.user.user_id"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.Column("updated_by", sa.BigInteger, sa.ForeignKey("auth.user.user_id"), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True)),
        sa.UniqueConstraint(
            "asset_id", "market_code", "id_type", "id_value",
            name="uq_asset_market_id",
        ),
        schema="ars",
    )
    op.create_index(
        "ix_asset_market_id_asset", "asset_market_id",
        ["asset_id"], schema="ars",
    )

    # 接入审计：用 v2 第 3 参数 parent_ref 让 entity_code 自动回填 asset_code
    op.execute("""
        CREATE TRIGGER trg_asset_market_id_audit
        AFTER INSERT OR UPDATE OR DELETE ON ars.asset_market_id
        FOR EACH ROW EXECUTE FUNCTION audit.fn_audit_trigger(
            'market_id_pk', '', 'ars.asset:asset_id:asset_code:asset_id'
        );
    """)

    # BEFORE UPDATE 维护 updated_at（asset_market_id 无 version 字段，简单 touch）
    op.execute("""
        CREATE OR REPLACE FUNCTION ars.fn_touch_updated_at()
        RETURNS TRIGGER AS $$
        BEGIN
            NEW.updated_at := NOW();
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
    """)
    op.execute("""
        CREATE TRIGGER trg_asset_market_id_touch
        BEFORE UPDATE ON ars.asset_market_id
        FOR EACH ROW EXECUTE FUNCTION ars.fn_touch_updated_at();
    """)


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_asset_market_id_touch ON ars.asset_market_id")
    op.execute("DROP TRIGGER IF EXISTS trg_asset_market_id_audit ON ars.asset_market_id")
    op.execute("DROP FUNCTION IF EXISTS ars.fn_touch_updated_at()")
    op.drop_table("asset_market_id", schema="ars")
