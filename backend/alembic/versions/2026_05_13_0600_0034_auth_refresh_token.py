"""auth.refresh_token table for Phase 4.B refresh-token rotation

Revision ID: 0034_auth_refresh_token
Revises: 0033_mm_material_batch
Create Date: 2026-05-13 06:00:00.000000

Phase 4.B 第 1 步：建 auth.refresh_token 表，承载 /auth/refresh 端点的 token 状态。

设计要点（V1.1 §7.2 + ARCH §7.2.1 + API §2）：
  - PK 用 jti（VARCHAR(36) UUID）：与 JWT payload.jti 一一对应；查询走 PK
  - 不存原始 token，只存 jti（JWT 自身已签名校验，DB 只承担"是否撤销/过期"事实）
  - revoked_at NULL = 未撤销；非 NULL 表示已 logout/rotate/被改密撤销
  - rotated_to_jti：旋转链审计字段（旧 jti -> 新 jti），便于排查 refresh 重放攻击
  - device_info：ip_address + user_agent，写入审计、便于运维定位异常会话

索引策略：
  - PK(jti) 自带索引（refresh 端点查 jti 主路径）
  - (user_id, revoked_at IS NULL) partial idx：列出某用户活跃 refresh + 改密撤销批量 UPDATE
  - expires_at idx：定期清理过期 token 的批处理走

注意：V1.1 §7.2 提到 Redis 黑名单 jti 是 Phase 5 目标；本期用 PG 表实现同样语义，
不引入 Redis 依赖。后续若上 Redis，迁移路径是把 DB 表查询替换为 Redis SETNX/GET。
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0034_auth_refresh_token"
down_revision: str | None = "0033_mm_material_batch"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "refresh_token",
        sa.Column("jti", sa.String(36), primary_key=True),
        sa.Column(
            "user_id",
            sa.BigInteger,
            sa.ForeignKey("auth.user.user_id"),
            nullable=False,
        ),
        sa.Column("issued_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True)),
        sa.Column("revoked_reason", sa.String(32)),  # rotated/logout/password_changed/admin
        sa.Column("rotated_to_jti", sa.String(36)),  # 指向旋转链的下一个 jti
        sa.Column("ip_address", sa.String(45)),       # IPv4/IPv6
        sa.Column("user_agent", sa.String(512)),
        sa.CheckConstraint(
            "revoked_reason IS NULL OR revoked_reason IN "
            "('rotated','logout','password_changed','admin','expired')",
            name="ck_refresh_token_reason",
        ),
        schema="auth",
    )

    # Partial index：列出某用户活跃 refresh + 批量撤销路径
    op.execute(
        "CREATE INDEX ix_refresh_token_user_active "
        "ON auth.refresh_token (user_id) WHERE revoked_at IS NULL"
    )
    # 过期清理批处理
    op.create_index(
        "ix_refresh_token_expires", "refresh_token", ["expires_at"],
        schema="auth",
    )


def downgrade() -> None:
    op.drop_index("ix_refresh_token_expires", table_name="refresh_token", schema="auth")
    op.execute("DROP INDEX IF EXISTS auth.ix_refresh_token_user_active")
    op.drop_table("refresh_token", schema="auth")
