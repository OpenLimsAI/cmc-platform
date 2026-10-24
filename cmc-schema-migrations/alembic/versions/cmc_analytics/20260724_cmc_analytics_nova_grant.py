"""cmc_analytics: 给 nova_etl 授权写 staging.stg_nova_run + 读 dim（2026-07-24）

配合 rd-nova-etl 的 stage 步骤（读 raw → 写 staging）。cmc_analytics 原则只读，
staging 表是 ETL 的例外写入点（同 vicell_etl 之于 stg_vicell_run）。
另给 dim 只读，供将来 stage 需要 join 设备维度时用。
角色由 cmc_rd 侧迁移 cmc_rd_nova_grant 建出，这里不重复建。

Revision ID: cmc_analytics_nova_grant
Revises: cmc_analytics_stg_nova
Create Date: 2026-07-24
"""

from __future__ import annotations

from alembic import op

revision = "cmc_analytics_nova_grant"
down_revision = "cmc_analytics_stg_nova"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        DO $$ BEGIN
          IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname='nova_etl') THEN
            CREATE ROLE nova_etl LOGIN;  -- 一般已由 cmc_rd_nova_grant 建出；这里兜底
          END IF;
        END $$;
        """
    )
    op.execute("GRANT CONNECT ON DATABASE cmc_analytics TO nova_etl")
    op.execute("GRANT USAGE ON SCHEMA staging TO nova_etl")
    op.execute("GRANT SELECT, INSERT, UPDATE, DELETE ON staging.stg_nova_run TO nova_etl")
    # dim 只读：stage 目前不 join，但给上读权限，方便将来按设备维度过滤
    op.execute("GRANT USAGE ON SCHEMA dim TO nova_etl")
    op.execute("GRANT SELECT ON dim.equipment_master TO nova_etl")


def downgrade() -> None:
    op.execute("REVOKE SELECT ON dim.equipment_master FROM nova_etl")
    op.execute("REVOKE USAGE ON SCHEMA dim FROM nova_etl")
    op.execute("REVOKE ALL ON staging.stg_nova_run FROM nova_etl")
    op.execute("REVOKE USAGE ON SCHEMA staging FROM nova_etl")
    op.execute("REVOKE CONNECT ON DATABASE cmc_analytics FROM nova_etl")
