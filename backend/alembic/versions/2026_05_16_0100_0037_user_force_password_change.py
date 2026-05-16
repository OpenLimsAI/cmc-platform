"""auth.user.force_password_change column (admin reset → 强制首次改密)

Revision ID: 0037_user_force_pwd_change
Revises: 0036_audit_trigger_v3
Create Date: 2026-05-16 01:00:00.000000

Phase 5.A / M5.1：管理员调用 :reset-password 时返回临时密码并将该列置 TRUE。
用户用临时密码登录时，前端识别 must_change_password 标记后强制跳改密页；
用户改密后该列自动复位为 FALSE（在 AuthService.change_password 中处理）。

字段为 NOT NULL DEFAULT FALSE，已有 5 个 seed 用户回填 FALSE。
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0037_user_force_pwd_change"
down_revision: str | None = "0036_audit_trigger_v3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "user",
        sa.Column(
            "force_password_change",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("FALSE"),
        ),
        schema="auth",
    )


def downgrade() -> None:
    op.drop_column("user", "force_password_change", schema="auth")
