"""audit trigger v2: child entity_code via parent lookup + filter updated_by

Revision ID: 0005_audit_trigger_v2
Revises: 0004_backfill_sequence_hash
Create Date: 2026-05-11 16:00:00.000000

升级 audit.fn_audit_trigger（M2.0 技术债前置清理 #3 + #4）：
  1. 新增第三个 TG_ARG（parent 引用串 'schema.table:pk:code:fk_on_this_table'）
     使 substance_protein / substance_xref 等子表 audit_log.entity_code 关联回父
     substance_code，让"按业务编码筛选审计历史"对子对象事件也生效
  2. change_history 字段过滤列表新增 updated_by（与 audit_log.user_id 重复，写入即噪音）

向后兼容：TG_NARGS < 3 时 parent_ref 为 NULL，旧 2-arg 触发器无需改动即可继续工作；
本迁移仅把已有的 substance_protein / substance_xref 触发器升级为 3-arg 形式。
"""
from collections.abc import Sequence

from alembic import op

revision: str = "0005_audit_trigger_v2"
down_revision: str | None = "0004_backfill_sequence_hash"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


# ============== v2 触发器函数 ==============
_FN_V2 = """
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
    v_parent_ref    VARCHAR;
    v_entity_id     BIGINT;
    v_entity_code   VARCHAR;
    v_old_jsonb     JSONB;
    v_new_jsonb     JSONB;
    v_target_jsonb  JSONB;
    v_field         RECORD;
    v_parent_parts  TEXT[];
    v_parent_schema VARCHAR;
    v_parent_table  VARCHAR;
    v_parent_pk     VARCHAR;
    v_parent_code   VARCHAR;
    v_parent_fk     VARCHAR;
    v_parent_fk_val BIGINT;
BEGIN
    v_user_id    := NULLIF(current_setting('app.user_id',    TRUE), '')::BIGINT;
    v_username   := COALESCE(NULLIF(current_setting('app.username',   TRUE), ''), 'system');
    v_session_id := NULLIF(current_setting('app.session_id', TRUE), '');
    v_request_id := NULLIF(current_setting('app.request_id', TRUE), '');
    v_ip         := NULLIF(current_setting('app.ip_address', TRUE), '')::INET;
    v_reason     := NULLIF(current_setting('app.change_reason', TRUE), '');

    v_pk_field   := TG_ARGV[0];
    v_code_field := NULLIF(TG_ARGV[1], '');
    v_parent_ref := CASE WHEN TG_NARGS >= 3 THEN NULLIF(TG_ARGV[2], '') END;

    IF TG_OP = 'INSERT' THEN
        v_action       := 'CREATE';
        v_new_jsonb    := to_jsonb(NEW);
        v_target_jsonb := v_new_jsonb;
    ELSIF TG_OP = 'UPDATE' THEN
        v_action       := 'UPDATE';
        v_old_jsonb    := to_jsonb(OLD);
        v_new_jsonb    := to_jsonb(NEW);
        v_target_jsonb := v_new_jsonb;
        IF (v_old_jsonb ->> 'deleted_at') IS NULL
           AND (v_new_jsonb ->> 'deleted_at') IS NOT NULL THEN
            v_action := 'DELETE';
        END IF;
    ELSIF TG_OP = 'DELETE' THEN
        v_action       := 'DELETE';
        v_old_jsonb    := to_jsonb(OLD);
        v_target_jsonb := v_old_jsonb;
    END IF;

    v_entity_id := (v_target_jsonb ->> v_pk_field)::BIGINT;

    IF v_code_field IS NOT NULL THEN
        v_entity_code := v_target_jsonb ->> v_code_field;
    END IF;

    -- 子表 entity_code 回溯到父表 code：
    --   parent_ref 格式：'parent_schema.parent_table:parent_pk:parent_code_field:fk_on_this_table'
    IF v_entity_code IS NULL AND v_parent_ref IS NOT NULL THEN
        v_parent_parts := string_to_array(v_parent_ref, ':');
        IF array_length(v_parent_parts, 1) = 4 THEN
            v_parent_schema := split_part(v_parent_parts[1], '.', 1);
            v_parent_table  := split_part(v_parent_parts[1], '.', 2);
            v_parent_pk     := v_parent_parts[2];
            v_parent_code   := v_parent_parts[3];
            v_parent_fk     := v_parent_parts[4];
            v_parent_fk_val := (v_target_jsonb ->> v_parent_fk)::BIGINT;
            IF v_parent_fk_val IS NOT NULL THEN
                EXECUTE format(
                    'SELECT %I FROM %I.%I WHERE %I = $1',
                    v_parent_code, v_parent_schema, v_parent_table, v_parent_pk
                ) USING v_parent_fk_val INTO v_entity_code;
            END IF;
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
               AND key NOT IN ('updated_at', 'updated_by', 'version')
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
"""

# ============== v1 触发器函数（用于 downgrade 还原）==============
_FN_V1 = """
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
"""


def upgrade() -> None:
    op.execute(_FN_V2)

    op.execute("DROP TRIGGER IF EXISTS trg_substance_protein_audit ON srs.substance_protein")
    op.execute("""
        CREATE TRIGGER trg_substance_protein_audit
        AFTER INSERT OR UPDATE OR DELETE ON srs.substance_protein
        FOR EACH ROW EXECUTE FUNCTION audit.fn_audit_trigger(
            'substance_id', '', 'srs.substance:substance_id:substance_code:substance_id'
        );
    """)
    op.execute("DROP TRIGGER IF EXISTS trg_substance_xref_audit ON srs.substance_xref")
    op.execute("""
        CREATE TRIGGER trg_substance_xref_audit
        AFTER INSERT OR UPDATE OR DELETE ON srs.substance_xref
        FOR EACH ROW EXECUTE FUNCTION audit.fn_audit_trigger(
            'xref_id', '', 'srs.substance:substance_id:substance_code:substance_id'
        );
    """)


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_substance_xref_audit ON srs.substance_xref")
    op.execute("""
        CREATE TRIGGER trg_substance_xref_audit
        AFTER INSERT OR UPDATE OR DELETE ON srs.substance_xref
        FOR EACH ROW EXECUTE FUNCTION audit.fn_audit_trigger('xref_id', '');
    """)
    op.execute("DROP TRIGGER IF EXISTS trg_substance_protein_audit ON srs.substance_protein")
    op.execute("""
        CREATE TRIGGER trg_substance_protein_audit
        AFTER INSERT OR UPDATE OR DELETE ON srs.substance_protein
        FOR EACH ROW EXECUTE FUNCTION audit.fn_audit_trigger('substance_id', '');
    """)
    op.execute(_FN_V1)
