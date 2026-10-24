"""cmc_gmp baseline — 全量结构快照（2026-06-04）

由 `pg_dump --schema-only` 生成（baselines/cmc_gmp.sql），含 raw_gmp_lims_labvantage
+ meta。该库在 gmp_pg 实例（端口 5434）。
已有环境用 `alembic -n cmc_gmp stamp cmc_gmp_baseline` 打标。
"""
from __future__ import annotations

from pathlib import Path

from alembic import op

revision = "cmc_gmp_baseline"
down_revision = None
branch_labels = None
depends_on = None

_SQL = Path(__file__).resolve().parent.parent.parent / "baselines" / "cmc_gmp.sql"


def upgrade() -> None:
    op.get_bind().exec_driver_sql(_SQL.read_text(encoding="utf-8"))


def downgrade() -> None:
    raise NotImplementedError("baseline 不支持 downgrade")
