"""cmc_analytics: 给只读账号 lims_reader 授权读 Vi-CELL 视图（2026-07-04）

看板项目 cmc-rd-usp-dashboard 新增「细胞生长曲线」模块，需只读 mart.fact_vicell。
基线 04_grants.sql 已把 cmc_analytics 各 schema 的 SELECT 授给 lims_reader，但
mart.fact_vicell 是后建的视图，未自动带上授权（实测 has_table_privilege=false）。
这里显式、幂等补上 mart（含 fact_vicell）与 staging 的读权限，并设默认权限覆盖后续新表。

只读账号，绝不给写权限；写入点仍是 vicell_etl（见 cmc_analytics_vicell_grant）。

Revision ID: cmc_analytics_vicell_reader_grant
Revises: cmc_analytics_process_daily
Create Date: 2026-07-04
"""

from __future__ import annotations

from alembic import op

revision = "cmc_analytics_vicell_reader_grant"
down_revision = "cmc_analytics_process_daily"
branch_labels = None
depends_on = None

# 报表/看板只读账号（与读 cmc_rd 用的是同一个角色）。
_READERS = "lims_reader, quality_user"
_SCHEMAS = ("mart", "staging")


def upgrade() -> None:
    op.execute(f"GRANT CONNECT ON DATABASE cmc_analytics TO {_READERS}")
    for schema in _SCHEMAS:
        op.execute(f"GRANT USAGE ON SCHEMA {schema} TO {_READERS}")
        op.execute(f"GRANT SELECT ON ALL TABLES IN SCHEMA {schema} TO {_READERS}")
        # 覆盖后续在该 schema 新建的表/视图（由 postgres 建）
        op.execute(
            f"ALTER DEFAULT PRIVILEGES FOR ROLE postgres IN SCHEMA {schema} "
            f"GRANT SELECT ON TABLES TO {_READERS}"
        )


def downgrade() -> None:
    for schema in _SCHEMAS:
        op.execute(
            f"ALTER DEFAULT PRIVILEGES FOR ROLE postgres IN SCHEMA {schema} "
            f"REVOKE SELECT ON TABLES FROM {_READERS}"
        )
        op.execute(f"REVOKE SELECT ON ALL TABLES IN SCHEMA {schema} FROM {_READERS}")
        op.execute(f"REVOKE USAGE ON SCHEMA {schema} FROM {_READERS}")
    # 不 REVOKE CONNECT：其它只读用途仍需连库。
