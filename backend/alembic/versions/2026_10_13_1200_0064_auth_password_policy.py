"""密码最低 8 位、历史记录基线、无到期日期账号过渡。

Revision ID: 0064_auth_password_policy
Revises: 0063_mm_batch_partial_unique
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0064_auth_password_policy"
down_revision: str | None = "0063_mm_batch_partial_unique"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "password_history",
        sa.Column("history_id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column("user_id", sa.BigInteger(), sa.ForeignKey("auth.user.user_id"), nullable=False),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("recorded_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        schema="auth",
    )
    op.create_index("ix_password_history_user", "password_history",
                    ["user_id", "recorded_at", "history_id"], schema="auth")
    # 是当前值的采集基线，不声称知道既往改密时间；该表不挂应用审计触发器。
    op.execute('INSERT INTO auth.password_history(user_id,password_hash) '
               'SELECT user_id,password_hash FROM auth."user"')
    op.execute("""
        WITH old AS (
            SELECT config_key,config_value FROM meta.system_config
            WHERE config_key='password.min_length' AND config_value <> '8'
        ), changed AS (
            UPDATE meta.system_config SET config_value='8',updated_at=now()
            WHERE config_key IN (SELECT config_key FROM old) RETURNING config_key
        ), logs AS (
            INSERT INTO audit.audit_log(username,action,entity_schema,entity_table,entity_code,change_summary)
            SELECT 'migration:0064','UPDATE','meta','system_config',old.config_key,
                   '负责人确认密码最低长度改为8位' FROM old JOIN changed USING(config_key)
            RETURNING log_id,entity_code
        )
        INSERT INTO audit.change_history(audit_log_id,field_name,old_value,new_value)
        SELECT logs.log_id,'config_value',to_jsonb(old.config_value),'"8"'::jsonb
        FROM logs JOIN old ON logs.entity_code=old.config_key
    """)
    op.execute("""
        INSERT INTO meta.system_config(config_key,config_value,value_type,description)
        VALUES ('password.min_length','8','int','密码最小长度') ON CONFLICT(config_key) DO NOTHING
    """)
    op.execute("""
        WITH changed AS (
            UPDATE auth."user" SET password_expires_at=now()+interval '90 days'
            WHERE password_expires_at IS NULL RETURNING user_id,username,password_expires_at
        ), logs AS (
            INSERT INTO audit.audit_log(username,action,entity_schema,entity_table,entity_id,entity_code,change_summary)
            SELECT 'migration:0064','UPDATE','auth','user',user_id,username,
                   '启用密码有效期：原到期日为空，从迁移日起算90天' FROM changed
            RETURNING log_id,entity_id
        )
        INSERT INTO audit.change_history(audit_log_id,field_name,old_value,new_value)
        SELECT logs.log_id,'password_expires_at',NULL,to_jsonb(changed.password_expires_at)
        FROM logs JOIN changed ON logs.entity_id=changed.user_id
    """)


def downgrade() -> None:
    raise RuntimeError("密码策略迁移含历史校验记录和账号日期过渡，拒绝自动降级；须评估备份与配套代码回退")
