"""主记录版本、可靠重复提交结果与项目关系保留审计。

Revision ID: 0065_master_write_protection
Revises: 0064_auth_password_policy
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0065_master_write_protection"
down_revision = "0064_auth_password_policy"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ADD DEFAULT 给原记录版本基线，不 UPDATE 原业务字段或补造修改审计。
    for schema, table in (("mm", "material"), ("eqp", "equipment"), ("tgt", "target")):
        op.add_column(table, sa.Column("version", sa.Integer(), nullable=False, server_default="1"), schema=schema)
        op.execute(f"""
            CREATE OR REPLACE FUNCTION {schema}.fn_{table}_before_update()
            RETURNS TRIGGER AS $$ BEGIN
                NEW.updated_at := NOW();
                NEW.version := OLD.version + 1;
                RETURN NEW;
            END; $$ LANGUAGE plpgsql;
        """)

    op.create_table(
        "idempotency_result",
        sa.Column("user_id", sa.BigInteger(), sa.ForeignKey("auth.user.user_id"), primary_key=True),
        sa.Column("request_key", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("operation", sa.String(64), nullable=False),
        sa.Column("body_hash", sa.String(64), nullable=False),
        sa.Column("status_code", sa.Integer(), nullable=False),
        sa.Column("response_body", postgresql.JSONB(), nullable=False),
        sa.Column("headers", postgresql.JSONB(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        schema="meta",
    )
    op.add_column("project_relationship", sa.Column("deleted_at", sa.DateTime(timezone=True)), schema="prs")
    op.add_column("project_relationship", sa.Column("deleted_by", sa.BigInteger(), sa.ForeignKey("auth.user.user_id")), schema="prs")
    op.drop_constraint("uq_project_relationship", "project_relationship", schema="prs", type_="unique")
    op.create_index("uq_project_relationship_active", "project_relationship",
                    ["from_project_id", "to_project_id", "relationship_type"], unique=True,
                    schema="prs", postgresql_where=sa.text("deleted_at IS NULL"))
    # 一份事件保存两端编码快照；两项目详情都通过关系 ID 查询这份事件。
    op.execute("""
        CREATE FUNCTION audit.fn_project_relationship_audit() RETURNS TRIGGER AS $$
        DECLARE
            v_new JSONB := to_jsonb(NEW);
            v_old JSONB;
            v_action TEXT;
            v_reason TEXT := NULLIF(current_setting('app.change_reason', true), '');
            v_from TEXT;
            v_to TEXT;
            v_log BIGINT;
            v_key TEXT;
        BEGIN
            IF length(trim(coalesce(v_reason, ''))) < 5 THEN
                RAISE EXCEPTION '项目关系建立或取消必须填写至少5个字符的原因';
            END IF;
            SELECT project_code INTO v_from FROM prs.project WHERE project_id=NEW.from_project_id;
            SELECT project_code INTO v_to FROM prs.project WHERE project_id=NEW.to_project_id;
            v_new := v_new || jsonb_build_object('from_project_code', v_from, 'to_project_code', v_to);
            IF TG_OP='INSERT' THEN
                v_action := 'CREATE';
                v_old := '{}'::jsonb;
            ELSE
                v_old := to_jsonb(OLD) || jsonb_build_object('from_project_code', v_from, 'to_project_code', v_to);
                v_action := CASE WHEN OLD.deleted_at IS NULL AND NEW.deleted_at IS NOT NULL THEN 'DELETE' ELSE 'UPDATE' END;
            END IF;
            INSERT INTO audit.audit_log(user_id,username,action,entity_schema,entity_table,entity_id,entity_code,
                reason,change_summary,ip_address,request_id,extra)
            VALUES (NULLIF(current_setting('app.user_id',true),'')::bigint,
                coalesce(NULLIF(current_setting('app.username',true),''),'system'),v_action,
                'prs','project_relationship',NEW.relationship_id,v_from,v_reason,
                v_from || ' → ' || v_to || ' (' || NEW.relationship_type || ')',
                NULLIF(current_setting('app.ip_address',true),'')::inet,
                NULLIF(current_setting('app.request_id',true),''),
                jsonb_build_object('project_codes',jsonb_build_array(v_from,v_to)) ) RETURNING log_id INTO v_log;
            FOR v_key IN SELECT jsonb_object_keys(v_new) LOOP
                IF v_key='created_at' THEN CONTINUE; END IF;
                IF (v_old->v_key) IS DISTINCT FROM (v_new->v_key) THEN
                    INSERT INTO audit.change_history(audit_log_id,field_name,old_value,new_value)
                    VALUES(v_log,v_key,v_old->v_key,v_new->v_key);
                END IF;
            END LOOP;
            RETURN NEW;
        END; $$ LANGUAGE plpgsql;
        CREATE TRIGGER trg_project_relationship_audit AFTER INSERT OR UPDATE ON prs.project_relationship
        FOR EACH ROW EXECUTE FUNCTION audit.fn_project_relationship_audit();
    """)


def downgrade() -> None:
    raise RuntimeError("不自动删除重复提交结果或项目关系历史；回退须单独评估备份与配套代码")
