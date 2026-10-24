"""cmc_rd baseline — 全量结构快照（2026-06-04）

由 `pg_dump --schema-only` 生成（baselines/cmc_rd.sql），可从空库一把建出
当前全部结构。已有该库的环境（Mac/Linux）用
`alembic -n cmc_rd stamp cmc_rd_baseline` 打标，不重跑此 SQL。

这是 cmc_rd 纳入 alembic 的起点；今后所有结构变更在本环境写增量迁移。
"""
from __future__ import annotations

from pathlib import Path

from alembic import op

revision = "cmc_rd_baseline"
down_revision = None
branch_labels = None
depends_on = None

_SQL = Path(__file__).resolve().parent.parent.parent / "baselines" / "cmc_rd.sql"


def upgrade() -> None:
    op.get_bind().exec_driver_sql(_SQL.read_text(encoding="utf-8"))


def downgrade() -> None:
    raise NotImplementedError("baseline 不支持 downgrade")
