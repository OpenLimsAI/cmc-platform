"""cmc_analytics: 给 vicell_etl 授权写 staging.stg_vicell_run（2026-07-03）

配合 rd-vicell-etl 的 stage 步骤（写 staging）。cmc_analytics 原则只读，
staging 表为 ETL 例外写入点（同 stg_batch 之于 lucullus_etl）。
角色若不存在则幂等建出（LOGIN 无密码，密码由运维设置）。

Revision ID: cmc_analytics_vicell_grant
Revises: cmc_analytics_fact_vicell
Create Date: 2026-07-03
"""

from __future__ import annotations

from alembic import op

revision = "cmc_analytics_vicell_grant"
down_revision = "cmc_analytics_fact_vicell"
branch_labels = None
depends_on = None


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
    op.execute("GRANT CONNECT ON DATABASE cmc_analytics TO vicell_etl")
    op.execute("GRANT USAGE ON SCHEMA staging TO vicell_etl")
    op.execute("GRANT SELECT, INSERT, UPDATE ON staging.stg_vicell_run TO vicell_etl")


def downgrade() -> None:
    op.execute("REVOKE ALL ON staging.stg_vicell_run FROM vicell_etl")
    op.execute("REVOKE USAGE ON SCHEMA staging FROM vicell_etl")
    op.execute("REVOKE CONNECT ON DATABASE cmc_analytics FROM vicell_etl")
