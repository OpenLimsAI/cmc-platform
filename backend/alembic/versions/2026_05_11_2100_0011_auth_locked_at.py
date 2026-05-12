"""auth.user.locked_at column (for auto-unlock after lockout)

Revision ID: 0011_auth_locked_at
Revises: 0010_revert_sig_sessionvar
Create Date: 2026-05-11 21:00:00.000000

M2.5.2a 安全收尾：
  - 新增 auth.user.locked_at（用户被自动锁定的时间戳）
  - login service 之后会基于 (now() - locked_at) > LOGIN_LOCK_DURATION_MINUTES 自动解锁

字段为 nullable，已有未锁定用户的行保持 NULL。
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0011_auth_locked_at"
down_revision: str | None = "0010_revert_sig_sessionvar"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "user",
        sa.Column("locked_at", sa.DateTime(timezone=True), nullable=True),
        schema="auth",
    )


def downgrade() -> None:
    op.drop_column("user", "locked_at", schema="auth")
