"""cmc_rd: 建 nova_etl 账号并授权 raw 层读写（2026-07-23）

Nova FLEX2 ETL 的写账号（对应 rd-nova-etl 的 database.user=nova_etl）。
raw 层 append-only，只需 SELECT（去重查询）+ INSERT，**不给 UPDATE/DELETE**。
角色以 LOGIN 无密码建出（幂等）；密码由运维单独 ALTER ROLE 设置，
与 vicell_etl / lucullus_etl 的做法一致。

Revision ID: cmc_rd_nova_grant
Revises: cmc_rd_nova
Create Date: 2026-07-23
"""

from __future__ import annotations

from alembic import op

revision = "cmc_rd_nova_grant"
down_revision = "cmc_rd_nova"
branch_labels = None
depends_on = None

_SCHEMA = "raw_rd_usp_nova"
_ROLE = "nova_etl"


def upgrade() -> None:
    op.execute(
        f"""
        DO $$ BEGIN
          IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname='{_ROLE}') THEN
            CREATE ROLE {_ROLE} LOGIN;  -- 密码由运维 ALTER ROLE 设置
          END IF;
        END $$;
        """
    )
    op.execute(f"GRANT CONNECT ON DATABASE cmc_rd TO {_ROLE}")
    op.execute(f"GRANT USAGE ON SCHEMA {_SCHEMA} TO {_ROLE}")
    op.execute(f"GRANT SELECT, INSERT ON ALL TABLES IN SCHEMA {_SCHEMA} TO {_ROLE}")
    op.execute(f"GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA {_SCHEMA} TO {_ROLE}")
    # 将来该 schema 新建的表/序列自动带上同样授权
    op.execute(
        f"ALTER DEFAULT PRIVILEGES IN SCHEMA {_SCHEMA} GRANT SELECT, INSERT ON TABLES TO {_ROLE}"
    )
    op.execute(
        f"ALTER DEFAULT PRIVILEGES IN SCHEMA {_SCHEMA} "
        f"GRANT USAGE, SELECT ON SEQUENCES TO {_ROLE}"
    )


def downgrade() -> None:
    op.execute(
        f"ALTER DEFAULT PRIVILEGES IN SCHEMA {_SCHEMA} REVOKE SELECT, INSERT ON TABLES FROM {_ROLE}"
    )
    op.execute(
        f"ALTER DEFAULT PRIVILEGES IN SCHEMA {_SCHEMA} "
        f"REVOKE USAGE, SELECT ON SEQUENCES FROM {_ROLE}"
    )
    op.execute(f"REVOKE ALL ON ALL SEQUENCES IN SCHEMA {_SCHEMA} FROM {_ROLE}")
    op.execute(f"REVOKE ALL ON ALL TABLES IN SCHEMA {_SCHEMA} FROM {_ROLE}")
    op.execute(f"REVOKE USAGE ON SCHEMA {_SCHEMA} FROM {_ROLE}")
    op.execute(f"REVOKE CONNECT ON DATABASE cmc_rd FROM {_ROLE}")
    # 不 DROP ROLE：将来 cmc_analytics 侧的授权迁移也会引用它
