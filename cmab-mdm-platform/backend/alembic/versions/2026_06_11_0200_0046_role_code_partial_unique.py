"""auth.role.role_code 软删唯一约束改 partial unique（H-03）

Revision ID: 0046_role_code_partial_unique
Revises: 0045_softdelete_partial_unique
Create Date: 2026-06-11 02:00:00.000000

与 0045（H-08/H-10）同族同口径（策略 B）：软删后允许同 role_code 重建，
唯一性仅约束未删行。

- 0001 的 uq_role_role_code 为全表唯一（含软删行），create_role 预检
  active-only 口径放行后 INSERT 撞约束 → IntegrityError 500
- drop 全量约束，建 partial UNIQUE（WHERE deleted_at IS NULL）
- 系统角色不可删（SystemRoleProtectedError），仅影响自定义角色删除→重建路径

安全性：原全量约束保证存量无重复，partial（子集）口径必然可满足，无需数据预检。
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0046_role_code_partial_unique"
down_revision: str | None = "0045_softdelete_partial_unique"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_constraint("uq_role_role_code", "role", schema="auth", type_="unique")
    op.create_index(
        "uq_role_code_active", "role", ["role_code"],
        unique=True,
        postgresql_where=sa.text("deleted_at IS NULL"),
        schema="auth",
    )


def downgrade() -> None:
    # 注意：若 upgrade 后已产生「软删行与未删行同 code」数据，恢复全量约束会失败，需先人工清理
    op.drop_index("uq_role_code_active", table_name="role", schema="auth")
    op.create_unique_constraint("uq_role_role_code", "role", ["role_code"], schema="auth")
