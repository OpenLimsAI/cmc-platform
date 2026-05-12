"""audit baseline: audit_log / change_history / e_signature + fn_audit_trigger

Revision ID: 0002_audit_baseline
Revises: 0001_init_schemas
Create Date: 2026-05-11 14:00:00.000000

落地 21 CFR Part 11 / EMA Annex 11 / ICH ALCOA+ 要求的审计底座：
  - audit.audit_log         操作主表（who/what/when/where/why）
  - audit.change_history    字段级 old/new 值
  - audit.e_signature       电子签名（Phase 3 起填充，此处先建结构）
  - audit.fn_audit_trigger  通用触发器函数，业务表只需 CREATE TRIGGER 即可接入
  - cmab_audit_reader 角色获得 audit schema 只读权限（含 default privileges）

设计依据 DM-MDM-001 §6。retention 策略与 partition by month 留到运维侧/Phase 2 处理。
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0002_audit_baseline"
down_revision: str | None = "0001_init_schemas"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # ============== audit.audit_log ==============
    op.create_table(
        "audit_log",
        sa.Column("log_id", sa.BigInteger, sa.Identity(always=True), primary_key=True),
        sa.Column("user_id", sa.BigInteger),
        sa.Column("username", sa.String(64), nullable=False),
        sa.Column("session_id", sa.String(64)),
        sa.Column("action", sa.String(32), nullable=False),
        sa.Column("entity_schema", sa.String(32)),
        sa.Column("entity_table", sa.String(64)),
        sa.Column("entity_id", sa.BigInteger),
        sa.Column("entity_code", sa.String(64)),
        sa.Column("change_summary", sa.Text),
        sa.Column("reason", sa.Text),
        sa.Column("ip_address", postgresql.INET),
        sa.Column("user_agent", sa.Text),
        sa.Column("request_id", sa.String(64)),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.Column("extra", postgresql.JSONB),
        sa.CheckConstraint(
            "action IN ('CREATE','READ','UPDATE','DELETE','RESTORE',"
            "'APPROVE','REJECT','SIGN','LOGIN','LOGOUT','LOGIN_FAILED',"
            "'EXPORT','IMPORT','PERMISSION_CHANGE')",
            name="ck_audit_log_action",
        ),
        schema="audit",
    )
    op.create_index("ix_audit_log_user_time", "audit_log", ["user_id", sa.text("timestamp DESC")], schema="audit")
    op.create_index("ix_audit_log_entity", "audit_log", ["entity_schema", "entity_table", "entity_id"], schema="audit")
    op.create_index("ix_audit_log_entity_code", "audit_log", ["entity_code"], schema="audit")
    op.create_index("ix_audit_log_timestamp", "audit_log", [sa.text("timestamp DESC")], schema="audit")
    op.create_index("ix_audit_log_action", "audit_log", ["action"], schema="audit")

    # ============== audit.change_history ==============
    op.create_table(
        "change_history",
        sa.Column("history_id", sa.BigInteger, sa.Identity(always=True), primary_key=True),
        sa.Column("audit_log_id", sa.BigInteger, sa.ForeignKey("audit.audit_log.log_id"), nullable=False),
        sa.Column("field_name", sa.String(64), nullable=False),
        sa.Column("old_value", postgresql.JSONB),
        sa.Column("new_value", postgresql.JSONB),
        schema="audit",
    )
    op.create_index("ix_change_history_log", "change_history", ["audit_log_id"], schema="audit")

    # ============== audit.e_signature ==============
    op.create_table(
        "e_signature",
        sa.Column("signature_id", sa.BigInteger, sa.Identity(always=True), primary_key=True),
        sa.Column("user_id", sa.BigInteger, sa.ForeignKey("auth.user.user_id"), nullable=False),
        sa.Column("username", sa.String(64), nullable=False),
        sa.Column("full_name", sa.String(128), nullable=False),
        sa.Column("entity_schema", sa.String(32), nullable=False),
        sa.Column("entity_table", sa.String(64), nullable=False),
        sa.Column("entity_id", sa.BigInteger, nullable=False),
        sa.Column("entity_code", sa.String(64)),
        sa.Column("signature_meaning", sa.String(64), nullable=False),
        sa.Column("signature_reason", sa.Text, nullable=False),
        sa.Column("signed_content_hash", sa.String(64), nullable=False),
        sa.Column("signature_hash", sa.String(64), nullable=False),
        sa.Column("ip_address", postgresql.INET),
        sa.Column("user_agent", sa.Text),
        sa.Column("signed_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.Column("audit_log_id", sa.BigInteger, sa.ForeignKey("audit.audit_log.log_id")),
        sa.CheckConstraint(
            "signature_meaning IN ('approve','review','release','witness','reject')",
            name="ck_e_signature_meaning",
        ),
        schema="audit",
    )
    op.create_index("ix_e_signature_user", "e_signature", ["user_id", sa.text("signed_at DESC")], schema="audit")
    op.create_index("ix_e_signature_entity", "e_signature", ["entity_schema", "entity_table", "entity_id"], schema="audit")

    # ============== audit.fn_audit_trigger ==============
    # 业务表挂 trigger 时传两个参数：
    #   TG_ARGV[0] = 主键字段名（如 'substance_id'）
    #   TG_ARGV[1] = 业务编码字段名（如 'substance_code'），无业务编码时传 NULL
    #
    # 软删除识别：UPDATE 时 OLD.deleted_at IS NULL AND NEW.deleted_at IS NOT NULL → action='DELETE'
    # change_history 过滤掉触发器自维护的元数据字段（updated_at / version），避免噪音
    op.execute("""
        CREATE OR REPLACE FUNCTION audit.fn_audit_trigger()
        RETURNS TRIGGER AS $$
        DECLARE
            v_log_id        BIGINT;
            v_user_id       BIGINT;
            v_username      VARCHAR;
            v_session_id    VARCHAR;
            v_request_id    VARCHAR;
            v_ip            INET;
            v_reason        TEXT;
            v_action        VARCHAR;
            v_pk_field      VARCHAR;
            v_code_field    VARCHAR;
            v_entity_id     BIGINT;
            v_entity_code   VARCHAR;
            v_old_jsonb     JSONB;
            v_new_jsonb     JSONB;
            v_field         RECORD;
        BEGIN
            v_user_id    := NULLIF(current_setting('app.user_id',    TRUE), '')::BIGINT;
            v_username   := COALESCE(NULLIF(current_setting('app.username',   TRUE), ''), 'system');
            v_session_id := NULLIF(current_setting('app.session_id', TRUE), '');
            v_request_id := NULLIF(current_setting('app.request_id', TRUE), '');
            v_ip         := NULLIF(current_setting('app.ip_address', TRUE), '')::INET;
            v_reason     := NULLIF(current_setting('app.change_reason', TRUE), '');

            v_pk_field   := TG_ARGV[0];
            v_code_field := NULLIF(TG_ARGV[1], '');

            IF TG_OP = 'INSERT' THEN
                v_action    := 'CREATE';
                v_new_jsonb := to_jsonb(NEW);
                v_entity_id := (v_new_jsonb ->> v_pk_field)::BIGINT;
                IF v_code_field IS NOT NULL THEN
                    v_entity_code := v_new_jsonb ->> v_code_field;
                END IF;
            ELSIF TG_OP = 'UPDATE' THEN
                v_action    := 'UPDATE';
                v_old_jsonb := to_jsonb(OLD);
                v_new_jsonb := to_jsonb(NEW);
                v_entity_id := (v_new_jsonb ->> v_pk_field)::BIGINT;
                IF v_code_field IS NOT NULL THEN
                    v_entity_code := v_new_jsonb ->> v_code_field;
                END IF;
                IF (v_old_jsonb ->> 'deleted_at') IS NULL
                   AND (v_new_jsonb ->> 'deleted_at') IS NOT NULL THEN
                    v_action := 'DELETE';
                END IF;
            ELSIF TG_OP = 'DELETE' THEN
                v_action    := 'DELETE';
                v_old_jsonb := to_jsonb(OLD);
                v_entity_id := (v_old_jsonb ->> v_pk_field)::BIGINT;
                IF v_code_field IS NOT NULL THEN
                    v_entity_code := v_old_jsonb ->> v_code_field;
                END IF;
            END IF;

            INSERT INTO audit.audit_log (
                user_id, username, session_id, action,
                entity_schema, entity_table, entity_id, entity_code,
                reason, ip_address, request_id, timestamp
            ) VALUES (
                v_user_id, v_username, v_session_id, v_action,
                TG_TABLE_SCHEMA, TG_TABLE_NAME, v_entity_id, v_entity_code,
                v_reason, v_ip, v_request_id, NOW()
            ) RETURNING log_id INTO v_log_id;

            IF TG_OP = 'UPDATE' THEN
                FOR v_field IN
                    SELECT key,
                           v_old_jsonb -> key AS old_val,
                           v_new_jsonb -> key AS new_val
                      FROM jsonb_object_keys(v_new_jsonb) AS key
                     WHERE (v_new_jsonb -> key) IS DISTINCT FROM (v_old_jsonb -> key)
                       AND key NOT IN ('updated_at', 'version')
                LOOP
                    INSERT INTO audit.change_history (audit_log_id, field_name, old_value, new_value)
                    VALUES (v_log_id, v_field.key, v_field.old_val, v_field.new_val);
                END LOOP;
            END IF;

            IF TG_OP = 'DELETE' THEN
                RETURN OLD;
            END IF;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
    """)

    op.execute("COMMENT ON FUNCTION audit.fn_audit_trigger IS '通用审计触发器，业务表挂 AFTER INSERT/UPDATE/DELETE 即接入'")

    # ============== cmab_audit_reader 只读权限 ==============
    # 当前已建表 + 未来在 audit schema 新增的表都自动获得 SELECT
    op.execute("GRANT SELECT ON ALL TABLES IN SCHEMA audit TO cmab_audit_reader")
    op.execute("GRANT USAGE ON ALL SEQUENCES IN SCHEMA audit TO cmab_audit_reader")
    op.execute(
        "ALTER DEFAULT PRIVILEGES FOR ROLE cmab_app IN SCHEMA audit "
        "GRANT SELECT ON TABLES TO cmab_audit_reader"
    )


def downgrade() -> None:
    op.execute("ALTER DEFAULT PRIVILEGES FOR ROLE cmab_app IN SCHEMA audit REVOKE SELECT ON TABLES FROM cmab_audit_reader")
    op.execute("REVOKE ALL ON ALL TABLES IN SCHEMA audit FROM cmab_audit_reader")
    op.execute("REVOKE ALL ON ALL SEQUENCES IN SCHEMA audit FROM cmab_audit_reader")
    op.execute("DROP FUNCTION IF EXISTS audit.fn_audit_trigger() CASCADE")
    op.drop_table("e_signature", schema="audit")
    op.drop_table("change_history", schema="audit")
    op.drop_table("audit_log", schema="audit")
