"""软删唯一约束修复：internal_code / market_id 改 partial unique（H-08 / H-10）

Revision ID: 0045_softdelete_partial_unique
Revises: 0044_eqp_identifiers
Create Date: 2026-06-11 01:00:00.000000

决策口径（2026-06-11，策略 B）：软删后唯一标识允许复用，唯一性仅约束未删行。

H-08 srs.substance.internal_code：
  - 0001 的全量 uq_substance_internal_code 与 0028 的 partial 普通索引
    ix_substance_internal_code（漏 unique=True）并存，预检 active-only 口径
    放行后撞全量约束 → IntegrityError 500
  - drop 全量约束 + 旧普通索引，重建 partial UNIQUE
  - internal_code 可 NULL：PG 默认 NULLS DISTINCT，多行 NULL 不冲突（预期行为）

H-10 ars.asset_market_id 四元组：
  - 0023 的 uq_asset_market_id 为全量约束，同模式 500
  - drop 全量约束，建 partial UNIQUE

安全性：原全量约束保证存量数据无重复，partial（子集）口径必然可满足，无需数据预检。
H-13 mm.uq_material_batch 同模式问题暂不处理（批号复用口径待负责人确认）。
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0045_softdelete_partial_unique"
down_revision: str | None = "0044_eqp_identifiers"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # H-08 srs.substance.internal_code
    op.drop_constraint("uq_substance_internal_code", "substance", schema="srs", type_="unique")
    op.drop_index("ix_substance_internal_code", table_name="substance", schema="srs")
    op.create_index(
        "uq_substance_internal_code_active", "substance", ["internal_code"],
        unique=True,
        postgresql_where=sa.text("deleted_at IS NULL"),
        schema="srs",
    )

    # H-10 ars.asset_market_id (asset_id, market_code, id_type, id_value)
    op.drop_constraint("uq_asset_market_id", "asset_market_id", schema="ars", type_="unique")
    op.create_index(
        "uq_asset_market_id_active", "asset_market_id",
        ["asset_id", "market_code", "id_type", "id_value"],
        unique=True,
        postgresql_where=sa.text("deleted_at IS NULL"),
        schema="ars",
    )


def downgrade() -> None:
    # 注意：若 upgrade 后已产生「软删行与未删行同值」数据，恢复全量约束会失败，需先人工清理
    op.drop_index("uq_asset_market_id_active", table_name="asset_market_id", schema="ars")
    op.create_unique_constraint(
        "uq_asset_market_id", "asset_market_id",
        ["asset_id", "market_code", "id_type", "id_value"],
        schema="ars",
    )

    op.drop_index("uq_substance_internal_code_active", table_name="substance", schema="srs")
    op.create_index(
        "ix_substance_internal_code", "substance", ["internal_code"],
        postgresql_where=sa.text("deleted_at IS NULL"),
        schema="srs",
    )
    op.create_unique_constraint(
        "uq_substance_internal_code", "substance", ["internal_code"], schema="srs"
    )
