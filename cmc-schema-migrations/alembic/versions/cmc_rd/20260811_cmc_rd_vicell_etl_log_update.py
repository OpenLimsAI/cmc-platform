"""cmc_rd: vicell_etl 补授 etl_log 的 UPDATE（2026-08-11）

rd-vicell-etl 改为「开跑先登记 running、结束 UPDATE 成终态」（总纲 7.1 铁律：
运行登记要放在一切校验之前，中途被杀台账留痕）。etl_log 是运维台账（meta 性质），
不是 raw 数据——append-only 铁律不适用于它；raw 数据表继续只有 SELECT + INSERT。

Revision ID: cmc_rd_vicell_log_upd
Revises: cmc_rd_lims_newcols
Create Date: 2026-08-11
"""

from __future__ import annotations

from alembic import op

revision = "cmc_rd_vicell_log_upd"
down_revision = "cmc_rd_lims_newcols"
branch_labels = None
depends_on = None

_SCHEMA = "raw_rd_usp_vicell"


def upgrade() -> None:
    op.execute(f"GRANT UPDATE ON {_SCHEMA}.etl_log TO vicell_etl")


def downgrade() -> None:
    op.execute(f"REVOKE UPDATE ON {_SCHEMA}.etl_log FROM vicell_etl")
