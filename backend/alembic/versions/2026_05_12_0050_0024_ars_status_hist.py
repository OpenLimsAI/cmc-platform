"""ars.asset_status_history (implementation gap fill; see V1.1 draft §5.4 + §8.1)

Revision ID: 0024_ars_status_hist
Revises: 0023_ars_market_id
Create Date: 2026-05-12 00:50:00.000000

M3.1 第 3 步：实施侧补齐 ars.asset_status_history。

设计文档 §8.1 表清单列出此表，但 §8 未给出 DDL（文档 V1.0 已知遗漏）。本迁移
与 §7.7 substance_status_history / §9.5 project_status_history 同构建立，含 e_signature_id
关联到 audit.e_signature（M2.5.1 实施侧加强模式）。
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0024_ars_status_hist"
down_revision: str | None = "0023_ars_market_id"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "asset_status_history",
        sa.Column("history_id", sa.BigInteger, sa.Identity(always=True), primary_key=True),
        sa.Column("asset_id", sa.BigInteger,
                  sa.ForeignKey("ars.asset.asset_id"), nullable=False),
        sa.Column("old_status", sa.String(32)),
        sa.Column("new_status", sa.String(32), nullable=False),
        sa.Column("change_reason", sa.Text, nullable=False),
        sa.Column("changed_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.Column("changed_by", sa.BigInteger,
                  sa.ForeignKey("auth.user.user_id"), nullable=False),
        sa.Column("e_signature_id", sa.BigInteger,
                  sa.ForeignKey("audit.e_signature.signature_id")),
        schema="ars",
    )
    op.create_index(
        "ix_asset_status_history_asset", "asset_status_history",
        ["asset_id", sa.text("changed_at DESC")], schema="ars",
    )

    # ============== asset 状态变更自动写历史（与 M3.0.1 ref 一样，service 后置 UPDATE sig_id）==============
    # 避免 SET LOCAL e_signature_id 异步泄漏问题（feedback_fastapi_yield_commit_timing.md / signature memory）
    op.execute("""
        CREATE OR REPLACE FUNCTION ars.fn_asset_status_change()
        RETURNS TRIGGER AS $$
        BEGIN
            IF OLD.status IS DISTINCT FROM NEW.status THEN
                INSERT INTO ars.asset_status_history (
                    asset_id, old_status, new_status, change_reason, changed_by
                ) VALUES (
                    NEW.asset_id,
                    OLD.status,
                    NEW.status,
                    COALESCE(NULLIF(current_setting('app.change_reason', TRUE), ''), 'status changed'),
                    NEW.updated_by
                );
            END IF;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
    """)
    op.execute("""
        CREATE TRIGGER trg_asset_status_change
        AFTER UPDATE ON ars.asset
        FOR EACH ROW EXECUTE FUNCTION ars.fn_asset_status_change();
    """)


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_asset_status_change ON ars.asset")
    op.execute("DROP FUNCTION IF EXISTS ars.fn_asset_status_change()")
    op.drop_table("asset_status_history", schema="ars")
