"""srs triggers: before_update / assign_code / status_history + audit hooks

Revision ID: 0003_srs_triggers
Revises: 0002_audit_baseline
Create Date: 2026-05-11 14:30:00.000000

把 substance / substance_protein / substance_xref 接入审计底座：
  - 通用 BEFORE UPDATE 触发器维护 updated_at；substance 额外自增 version（移除 service 层手动逻辑）
  - substance BEFORE INSERT 自动分配 SUB-XXXXXXX（service 层保留显式调用作为兜底，不冲突）
  - srs.substance_status_history 表 + fn_substance_status_change 触发器（M1.2 状态机端点上线即生效）
  - audit.fn_audit_trigger 挂到三张表

设计依据 DM-MDM-001 §7.2 / §7.7 / §7.6。
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0003_srs_triggers"
down_revision: str | None = "0002_audit_baseline"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # ============== 通用 updated_at 触发器（仅 updated_at，无 version）==============
    op.execute("""
        CREATE OR REPLACE FUNCTION srs.fn_touch_updated_at()
        RETURNS TRIGGER AS $$
        BEGIN
            NEW.updated_at := NOW();
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
    """)

    # ============== substance BEFORE UPDATE：updated_at + version+1 ==============
    # 取代 service 层手动维护，杜绝 raw SQL 绕过 ORM 时的乐观锁逃逸
    op.execute("""
        CREATE OR REPLACE FUNCTION srs.fn_substance_before_update()
        RETURNS TRIGGER AS $$
        BEGIN
            NEW.updated_at := NOW();
            NEW.version    := OLD.version + 1;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
    """)
    op.execute("""
        CREATE TRIGGER trg_substance_before_update
        BEFORE UPDATE ON srs.substance
        FOR EACH ROW EXECUTE FUNCTION srs.fn_substance_before_update();
    """)

    # ============== substance BEFORE INSERT：自动分配 substance_code（兜底）==============
    # service 层目前显式调用 meta.fn_next_code，这里作为最后防线；触发器内只在为空时才分配
    op.execute("""
        CREATE OR REPLACE FUNCTION srs.fn_substance_assign_code()
        RETURNS TRIGGER AS $$
        BEGIN
            IF NEW.substance_code IS NULL OR NEW.substance_code = '' THEN
                NEW.substance_code := meta.fn_next_code('substance');
            END IF;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
    """)
    op.execute("""
        CREATE TRIGGER trg_substance_assign_code
        BEFORE INSERT ON srs.substance
        FOR EACH ROW EXECUTE FUNCTION srs.fn_substance_assign_code();
    """)

    # ============== substance_protein / substance_xref BEFORE UPDATE ==============
    op.execute("""
        CREATE TRIGGER trg_substance_protein_touch
        BEFORE UPDATE ON srs.substance_protein
        FOR EACH ROW EXECUTE FUNCTION srs.fn_touch_updated_at();
    """)
    op.execute("""
        CREATE TRIGGER trg_substance_xref_touch
        BEFORE UPDATE ON srs.substance_xref
        FOR EACH ROW EXECUTE FUNCTION srs.fn_touch_updated_at();
    """)

    # ============== srs.substance_status_history ==============
    op.create_table(
        "substance_status_history",
        sa.Column("history_id", sa.BigInteger, sa.Identity(always=True), primary_key=True),
        sa.Column("substance_id", sa.BigInteger,
                  sa.ForeignKey("srs.substance.substance_id"), nullable=False),
        sa.Column("old_status", sa.String(32)),
        sa.Column("new_status", sa.String(32), nullable=False),
        sa.Column("change_reason", sa.Text, nullable=False),
        sa.Column("changed_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.Column("changed_by", sa.BigInteger, sa.ForeignKey("auth.user.user_id"), nullable=False),
        sa.Column("e_signature_id", sa.BigInteger, sa.ForeignKey("audit.e_signature.signature_id")),
        sa.Column("merged_to_substance_id", sa.BigInteger,
                  sa.ForeignKey("srs.substance.substance_id")),
        schema="srs",
    )
    op.create_index(
        "ix_substance_status_history_sub", "substance_status_history",
        ["substance_id", sa.text("changed_at DESC")], schema="srs",
    )

    # ============== substance 状态变更自动写历史 ==============
    # change_reason 从 PG session 变量 app.change_reason 取，service 层在状态机端点上 SET LOCAL
    op.execute("""
        CREATE OR REPLACE FUNCTION srs.fn_substance_status_change()
        RETURNS TRIGGER AS $$
        BEGIN
            IF OLD.status IS DISTINCT FROM NEW.status THEN
                INSERT INTO srs.substance_status_history (
                    substance_id, old_status, new_status, change_reason, changed_by
                ) VALUES (
                    NEW.substance_id,
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
        CREATE TRIGGER trg_substance_status_change
        AFTER UPDATE ON srs.substance
        FOR EACH ROW EXECUTE FUNCTION srs.fn_substance_status_change();
    """)

    # ============== 接入审计 ==============
    op.execute("""
        CREATE TRIGGER trg_substance_audit
        AFTER INSERT OR UPDATE OR DELETE ON srs.substance
        FOR EACH ROW EXECUTE FUNCTION audit.fn_audit_trigger('substance_id', 'substance_code');
    """)
    op.execute("""
        CREATE TRIGGER trg_substance_protein_audit
        AFTER INSERT OR UPDATE OR DELETE ON srs.substance_protein
        FOR EACH ROW EXECUTE FUNCTION audit.fn_audit_trigger('substance_id', '');
    """)
    op.execute("""
        CREATE TRIGGER trg_substance_xref_audit
        AFTER INSERT OR UPDATE OR DELETE ON srs.substance_xref
        FOR EACH ROW EXECUTE FUNCTION audit.fn_audit_trigger('xref_id', '');
    """)


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_substance_xref_audit ON srs.substance_xref")
    op.execute("DROP TRIGGER IF EXISTS trg_substance_protein_audit ON srs.substance_protein")
    op.execute("DROP TRIGGER IF EXISTS trg_substance_audit ON srs.substance")
    op.execute("DROP TRIGGER IF EXISTS trg_substance_status_change ON srs.substance")
    op.execute("DROP FUNCTION IF EXISTS srs.fn_substance_status_change()")
    op.drop_table("substance_status_history", schema="srs")
    op.execute("DROP TRIGGER IF EXISTS trg_substance_xref_touch ON srs.substance_xref")
    op.execute("DROP TRIGGER IF EXISTS trg_substance_protein_touch ON srs.substance_protein")
    op.execute("DROP TRIGGER IF EXISTS trg_substance_assign_code ON srs.substance")
    op.execute("DROP FUNCTION IF EXISTS srs.fn_substance_assign_code()")
    op.execute("DROP TRIGGER IF EXISTS trg_substance_before_update ON srs.substance")
    op.execute("DROP FUNCTION IF EXISTS srs.fn_substance_before_update()")
    op.execute("DROP FUNCTION IF EXISTS srs.fn_touch_updated_at()")
