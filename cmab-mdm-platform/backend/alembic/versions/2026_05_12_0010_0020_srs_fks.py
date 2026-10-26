"""SRS *_by FK to auth.user + GIN(extra) index per §7.2 (offset notes §2.1.5/§2.1.6)

Revision ID: 0020_srs_fks
Revises: 0019_xref_v2
Create Date: 2026-05-12 00:10:00.000000

M3.0.3 第 3 步：

  - srs.substance.created_by / updated_by / registered_by / deleted_by 加 FK auth.user
  - srs.substance.extra 加 GIN 索引
  - srs.substance_xref.created_by / updated_by / deleted_by 加 FK auth.user
  - srs.substance_alias.created_by 加 FK auth.user
  - prs.project 同步加 FK auth.user（M3.0.2 漏了的）

FK 用 ALTER TABLE ... ADD CONSTRAINT FOREIGN KEY 直接加，dev 库 seed 数据保证不违反约束
（所有 *_by 都是 admin user_id=1 创建的）。
"""
from collections.abc import Sequence

from alembic import op

revision: str = "0020_srs_fks"
down_revision: str | None = "0019_xref_v2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # ============== srs.substance ==============
    op.create_foreign_key(
        "fk_substance_created_by", "substance", "user",
        ["created_by"], ["user_id"],
        source_schema="srs", referent_schema="auth",
    )
    op.create_foreign_key(
        "fk_substance_updated_by", "substance", "user",
        ["updated_by"], ["user_id"],
        source_schema="srs", referent_schema="auth",
    )
    op.create_foreign_key(
        "fk_substance_registered_by", "substance", "user",
        ["registered_by"], ["user_id"],
        source_schema="srs", referent_schema="auth",
    )
    op.create_foreign_key(
        "fk_substance_deleted_by", "substance", "user",
        ["deleted_by"], ["user_id"],
        source_schema="srs", referent_schema="auth",
    )
    op.execute(
        "CREATE INDEX ix_substance_extra ON srs.substance USING gin(extra)"
    )

    # ============== srs.substance_xref ==============
    op.create_foreign_key(
        "fk_substance_xref_created_by", "substance_xref", "user",
        ["created_by"], ["user_id"],
        source_schema="srs", referent_schema="auth",
    )
    op.create_foreign_key(
        "fk_substance_xref_updated_by", "substance_xref", "user",
        ["updated_by"], ["user_id"],
        source_schema="srs", referent_schema="auth",
    )
    op.create_foreign_key(
        "fk_substance_xref_deleted_by", "substance_xref", "user",
        ["deleted_by"], ["user_id"],
        source_schema="srs", referent_schema="auth",
    )

    # ============== srs.substance_alias ==============
    op.create_foreign_key(
        "fk_substance_alias_created_by", "substance_alias", "user",
        ["created_by"], ["user_id"],
        source_schema="srs", referent_schema="auth",
    )

    # ============== prs.project（M3.0.2 漏了的 FK）==============
    op.create_foreign_key(
        "fk_project_created_by", "project", "user",
        ["created_by"], ["user_id"],
        source_schema="prs", referent_schema="auth",
    )
    op.create_foreign_key(
        "fk_project_updated_by", "project", "user",
        ["updated_by"], ["user_id"],
        source_schema="prs", referent_schema="auth",
    )
    op.create_foreign_key(
        "fk_project_deleted_by", "project", "user",
        ["deleted_by"], ["user_id"],
        source_schema="prs", referent_schema="auth",
    )
    op.create_foreign_key(
        "fk_project_manager", "project", "user",
        ["project_manager_id"], ["user_id"],
        source_schema="prs", referent_schema="auth",
    )


def downgrade() -> None:
    op.drop_constraint("fk_project_manager", "project", schema="prs", type_="foreignkey")
    op.drop_constraint("fk_project_deleted_by", "project", schema="prs", type_="foreignkey")
    op.drop_constraint("fk_project_updated_by", "project", schema="prs", type_="foreignkey")
    op.drop_constraint("fk_project_created_by", "project", schema="prs", type_="foreignkey")

    op.drop_constraint("fk_substance_alias_created_by", "substance_alias", schema="srs", type_="foreignkey")

    op.drop_constraint("fk_substance_xref_deleted_by", "substance_xref", schema="srs", type_="foreignkey")
    op.drop_constraint("fk_substance_xref_updated_by", "substance_xref", schema="srs", type_="foreignkey")
    op.drop_constraint("fk_substance_xref_created_by", "substance_xref", schema="srs", type_="foreignkey")

    op.execute("DROP INDEX IF EXISTS srs.ix_substance_extra")
    op.drop_constraint("fk_substance_deleted_by", "substance", schema="srs", type_="foreignkey")
    op.drop_constraint("fk_substance_registered_by", "substance", schema="srs", type_="foreignkey")
    op.drop_constraint("fk_substance_updated_by", "substance", schema="srs", type_="foreignkey")
    op.drop_constraint("fk_substance_created_by", "substance", schema="srs", type_="foreignkey")
