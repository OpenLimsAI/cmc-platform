"""三表统一补 deleted_by 字段 (DEV-MDM-001 V1.2 #A/#B 决议)

Revision ID: 0027_softdel_by
Revises: 0026_ref_pa
Create Date: 2026-05-12 09:00:00.000000

V1.1 评审决议（DEV-MDM-001 V1.2 §6.2.3 / §6.5.4 / 附录 A）：
  - ars.asset_market_id 补 deleted_by
  - ref.asset_substance  补 deleted_by
  - ref.project_asset    补 deleted_by

理由：与 §11.2 ref.project_substance 已有的 `deleted_by` 对齐；
让 ref 三表 + 资产子表 soft-delete 模式完全统一；
配合 service 层 unlink 路径补 `deleted_by = current_user.user_id` 赋值。
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0027_softdel_by"
down_revision: str | None = "0026_ref_pa"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1) ars.asset_market_id
    op.add_column(
        "asset_market_id",
        sa.Column("deleted_by", sa.BigInteger, nullable=True),
        schema="ars",
    )
    op.create_foreign_key(
        "fk_asset_market_id_deleted_by",
        "asset_market_id", "user",
        ["deleted_by"], ["user_id"],
        source_schema="ars", referent_schema="auth",
    )

    # 2) ref.asset_substance
    op.add_column(
        "asset_substance",
        sa.Column("deleted_by", sa.BigInteger, nullable=True),
        schema="ref",
    )
    op.create_foreign_key(
        "fk_ref_as_deleted_by",
        "asset_substance", "user",
        ["deleted_by"], ["user_id"],
        source_schema="ref", referent_schema="auth",
    )

    # 3) ref.project_asset
    op.add_column(
        "project_asset",
        sa.Column("deleted_by", sa.BigInteger, nullable=True),
        schema="ref",
    )
    op.create_foreign_key(
        "fk_ref_pa_deleted_by",
        "project_asset", "user",
        ["deleted_by"], ["user_id"],
        source_schema="ref", referent_schema="auth",
    )


def downgrade() -> None:
    op.drop_constraint(
        "fk_ref_pa_deleted_by", "project_asset",
        schema="ref", type_="foreignkey",
    )
    op.drop_column("project_asset", "deleted_by", schema="ref")

    op.drop_constraint(
        "fk_ref_as_deleted_by", "asset_substance",
        schema="ref", type_="foreignkey",
    )
    op.drop_column("asset_substance", "deleted_by", schema="ref")

    op.drop_constraint(
        "fk_asset_market_id_deleted_by", "asset_market_id",
        schema="ars", type_="foreignkey",
    )
    op.drop_column("asset_market_id", "deleted_by", schema="ars")
