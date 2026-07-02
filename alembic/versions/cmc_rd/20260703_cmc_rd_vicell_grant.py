"""cmc_rd: 建 vicell_etl 账号并授权 raw 层读写（2026-07-03）

vicell ETL 的写账号（对应 rd-vicell-etl 的 database.user=vicell_etl）。
raw 层 append-only，只需 SELECT（去重查询）+ INSERT，不给 UPDATE/DELETE。
角色以 LOGIN 无密码建出（幂等）；密码由运维单独 ALTER ROLE 设置（与 lucullus_etl 相同）。

Revision ID: cmc_rd_vicell_grant
Revises: cmc_rd_vicell
Create Date: 2026-07-03
"""

from __future__ import annotations

from alembic import op

revision = "cmc_rd_vicell_grant"
down_revision = "cmc_rd_vicell"
branch_labels = None
depends_on = None

_SCHEMA = "raw_rd_usp_vicell"


def upgrade() -> None:
    op.execute(
        """
        DO $$ BEGIN
          IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname='vicell_etl') THEN
            CREATE ROLE vicell_etl LOGIN;  -- 密码由运维 ALTER ROLE 设置
          END IF;
        END $$;
        """
    )
    op.execute("GRANT CONNECT ON DATABASE cmc_rd TO vicell_etl")
    op.execute(f"GRANT USAGE ON SCHEMA {_SCHEMA} TO vicell_etl")
    op.execute(f"GRANT SELECT, INSERT ON ALL TABLES IN SCHEMA {_SCHEMA} TO vicell_etl")
    op.execute(f"GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA {_SCHEMA} TO vicell_etl")
    # 将来该 schema 新建的表/序列自动带上同样授权
    op.execute(
        f"ALTER DEFAULT PRIVILEGES IN SCHEMA {_SCHEMA} "
        "GRANT SELECT, INSERT ON TABLES TO vicell_etl"
    )
    op.execute(
        f"ALTER DEFAULT PRIVILEGES IN SCHEMA {_SCHEMA} "
        "GRANT USAGE, SELECT ON SEQUENCES TO vicell_etl"
    )


def downgrade() -> None:
    op.execute(
        f"ALTER DEFAULT PRIVILEGES IN SCHEMA {_SCHEMA} "
        "REVOKE SELECT, INSERT ON TABLES FROM vicell_etl"
    )
    op.execute(
        f"ALTER DEFAULT PRIVILEGES IN SCHEMA {_SCHEMA} "
        "REVOKE USAGE, SELECT ON SEQUENCES FROM vicell_etl"
    )
    op.execute(f"REVOKE ALL ON ALL SEQUENCES IN SCHEMA {_SCHEMA} FROM vicell_etl")
    op.execute(f"REVOKE ALL ON ALL TABLES IN SCHEMA {_SCHEMA} FROM vicell_etl")
    op.execute(f"REVOKE USAGE ON SCHEMA {_SCHEMA} FROM vicell_etl")
    op.execute("REVOKE CONNECT ON DATABASE cmc_rd FROM vicell_etl")
    # 不 DROP ROLE（cmc_analytics 授权迁移也引用它）
