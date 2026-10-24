"""drop legacy app_user and auth_session tables (auth unified to MDM JWT)

Revision ID: 08941b314a8f
Revises: cad3b5fb876b
Create Date: 2026-06-15 12:57:34.864748
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = '08941b314a8f'
down_revision = 'cad3b5fb876b'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 认证自 v2.0 起统一走 MDM Portal 的 JWT,本系统无本地用户表;
    # app_user / auth_session 为老 inventory 的本地认证遗留,彻底废弃。
    # 先删引用方 auth_session(FK 指向 app_user),再删 app_user。
    op.execute("DROP TABLE IF EXISTS material_mgmt.auth_session")
    op.execute("DROP TABLE IF EXISTS material_mgmt.app_user")


def downgrade() -> None:
    # 按原 sql/init.sql 定义复刻重建(回到 cad3b5fb876b 形态)。
    # 先建被引用方 app_user,再建 auth_session 及其外键。
    op.execute("""
        CREATE TABLE material_mgmt.app_user (
            id                    SERIAL PRIMARY KEY,
            username              VARCHAR(50)  NOT NULL UNIQUE,
            password_hash         VARCHAR(255) NOT NULL,
            role                  VARCHAR(20)  NOT NULL
                                  CHECK (role IN ('admin','warehouse_admin','user')),
            is_active             BOOLEAN      NOT NULL DEFAULT TRUE,
            must_change_password  BOOLEAN      NOT NULL DEFAULT FALSE,
            created_at            TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
            last_login_at         TIMESTAMP
        );
    """)
    op.execute("CREATE INDEX idx_app_user_active ON material_mgmt.app_user(is_active);")
    op.execute("""
        CREATE TABLE material_mgmt.auth_session (
            token         VARCHAR(64) PRIMARY KEY,
            user_id       INT NOT NULL
                          REFERENCES material_mgmt.app_user(id) ON DELETE CASCADE,
            created_at    TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            expires_at    TIMESTAMP NOT NULL,
            last_seen_at  TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            source_ip     VARCHAR(45)
        );
    """)
    op.execute("CREATE INDEX idx_auth_session_user    ON material_mgmt.auth_session(user_id);")
    op.execute("CREATE INDEX idx_auth_session_expires ON material_mgmt.auth_session(expires_at);")
