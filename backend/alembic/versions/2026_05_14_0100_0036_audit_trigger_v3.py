"""audit.fn_audit_trigger v3：CREATE / DELETE 也写 change_history

Revision ID: 0036_audit_trigger_v3
Revises: 0035_protein_ext_coef_float
Create Date: 2026-05-14 01:00:00.000000

V1.2 修订十二决议：把 CREATE 和 DELETE 也展开到 change_history，提供完整字段级
审计链。

v2 行为：
  - INSERT / DELETE → 仅写 audit_log 一行
  - UPDATE → audit_log 一行 + change_history 每变化字段一行
  - 前端审计 Tab 看 CREATE 行只能看到"无字段级变更"提示，业务感受差

v3 行为（本 migration）：
  - INSERT  → audit_log + change_history（old=NULL, new=NEW 全字段，
              过滤 created_at / updated_at / updated_by / version 自动维护字段）
  - UPDATE  → 保持原行为（diff 后写）
  - DELETE  → audit_log + change_history（old=OLD 全字段，new=NULL，
              过滤 deleted_at / deleted_by / updated_at / updated_by / version）
  - 软删除（UPDATE 设 deleted_at）→ action='DELETE'，但保持 UPDATE 的 diff 写法
              （只写实际变化的字段，含 deleted_at / deleted_by 状态翻转）

合规考虑：21 CFR Part 11 §11.10(e) "提供已记录的数据的副本"；v3 更接近"创建/删除
时的完整记录"语义。21 CFR Part 11 §11.10(b) 系统验证：本变更通过 pytest 全套验证。

性能考虑：v3 会让 change_history 行数显著增加（每次 CREATE 写 ~10-30 行，每次
DELETE 同）。当前 dev 数据量（~200 个业务实体）下增量 < 10000 行；生产监控
`audit.change_history` 表大小，超 100M 时考虑分区。
"""
from collections.abc import Sequence

from alembic import op

revision: str = "0036_audit_trigger_v3"
down_revision: str | None = "0035_protein_ext_coef_float"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


# ============== v3 触发器函数 ==============
_FN_V3 = """
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

    -- 子表 entity_code 回溯到父表 code（v2 起；保持不变）
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

    -- ============== v3 字段级展开：INSERT / UPDATE / DELETE 全覆盖 ==============
    IF TG_OP = 'INSERT' THEN
        -- 创建：每个非 NULL 字段写一行（old=NULL）；过滤自动维护字段
        FOR v_field IN
            SELECT key,
                   NULL::jsonb AS old_val,
                   v_new_jsonb -> key AS new_val
              FROM jsonb_object_keys(v_new_jsonb) AS key
             WHERE (v_new_jsonb -> key) IS NOT NULL
               AND (v_new_jsonb -> key)::TEXT <> 'null'
               AND key NOT IN ('created_at', 'updated_at', 'updated_by', 'version')
        LOOP
            INSERT INTO audit.change_history (audit_log_id, field_name, old_value, new_value)
            VALUES (v_log_id, v_field.key, v_field.old_val, v_field.new_val);
        END LOOP;

    ELSIF TG_OP = 'UPDATE' THEN
        -- 更新：保持 v2 行为（仅写变化字段）
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

    ELSIF TG_OP = 'DELETE' THEN
        -- 硬删除（极少见）：写完整 OLD 字段（new=NULL）
        FOR v_field IN
            SELECT key,
                   v_old_jsonb -> key AS old_val,
                   NULL::jsonb AS new_val
              FROM jsonb_object_keys(v_old_jsonb) AS key
             WHERE (v_old_jsonb -> key) IS NOT NULL
               AND (v_old_jsonb -> key)::TEXT <> 'null'
               AND key NOT IN ('created_at', 'updated_at', 'updated_by', 'version')
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

# ============== v2 触发器函数（用于 downgrade 还原）==============
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


def upgrade() -> None:
    op.execute(_FN_V3)


def downgrade() -> None:
    op.execute(_FN_V2)
