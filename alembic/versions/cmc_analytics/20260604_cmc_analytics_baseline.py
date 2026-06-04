"""cmc_analytics baseline — 全量结构快照（2026-06-04）

由 `pg_dump --schema-only` 生成（baselines/cmc_analytics.sql），含 dim/staging/
mart/ml_features/reporting/ext_*/snap_*/meta 等 schema 与视图、postgres_fdw 扩展。
已有环境用 `alembic -n cmc_analytics stamp cmc_analytics_baseline` 打标。
"""
from __future__ import annotations

from pathlib import Path

from alembic import op

revision = "cmc_analytics_baseline"
down_revision = None
branch_labels = None
depends_on = None

_SQL = Path(__file__).resolve().parent.parent.parent / "baselines" / "cmc_analytics.sql"


def upgrade() -> None:
    op.get_bind().exec_driver_sql(_SQL.read_text(encoding="utf-8"))


def downgrade() -> None:
    raise NotImplementedError("baseline 不支持 downgrade")
