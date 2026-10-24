"""cmc_data_platform baseline — 全量结构快照（2026-06-04）

由 `pg_dump --schema-only` 生成（baselines/cmc_data_platform.sql），含
material_mgmt + cost_accounting + equipment_mgmt 全部表。**取代**旧的
001→004 链（已归档至 versions/_legacy/）——旧链是补丁拼凑、无法从空库重建，
本 baseline 可从空库一把建出当前全量结构。

已有环境（Mac/Linux 均已在结构上一致）用
`alembic -n cmc_data_platform stamp cmc_data_platform_baseline` 打标，不重跑。
"""
from __future__ import annotations

from pathlib import Path

from alembic import op

revision = "cmc_data_platform_baseline"
down_revision = None
branch_labels = None
depends_on = None

_SQL = Path(__file__).resolve().parent.parent.parent / "baselines" / "cmc_data_platform.sql"


def upgrade() -> None:
    op.get_bind().exec_driver_sql(_SQL.read_text(encoding="utf-8"))


def downgrade() -> None:
    raise NotImplementedError("baseline 不支持 downgrade")
