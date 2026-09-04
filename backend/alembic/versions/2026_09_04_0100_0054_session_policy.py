"""会话策略（空闲超时 + 滑动会话 + 硬上限）落到 meta.system_config，可在系统管理页在线调整

Revision ID: 0054_session_policy
Revises: 0053_substance_code_4digits
Create Date: 2026-09-04 01:00:00.000000

负责人 2026-09-04 拍板（统一门户下"用着不掉线、不用自动登出"）：
  - access token 15 分钟（原 30）
  - 空闲窗口 30 分钟：refresh token 每次换证只续到「现在 + 空闲窗口」，没人换证就自然过期
  - 硬上限 12 小时：从首次登录算起，到点无论多活跃都必须重登（原 refresh 7 天弃用）
  - 展示模式（DISPLAY_MODE 角色）空闲窗口 720 分钟：墙屏/看板账号

三个时间不再读 .env，改读 meta.system_config（session.* 键），管理员在 /admin/session-policy 改，立即生效。
refresh_token 加 session_started_at：轮换时原样传递，用来算硬上限；历史行回填为 issued_at。
"""
from collections.abc import Sequence

from alembic import op

revision: str = "0054_session_policy"
down_revision: str | None = "0053_substance_code_4digits"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("ALTER TABLE auth.refresh_token ADD COLUMN IF NOT EXISTS session_started_at TIMESTAMPTZ")
    op.execute("UPDATE auth.refresh_token SET session_started_at = issued_at WHERE session_started_at IS NULL")
    op.execute("COMMENT ON COLUMN auth.refresh_token.session_started_at IS '所属登录会话的首次登录时间（轮换时原样传递，硬上限按此计算）'")

    op.execute("""
        INSERT INTO meta.system_config (config_key, config_value, value_type, description) VALUES
            ('session.access_token_minutes',      '15',  'int', 'Access Token 有效期（分钟）；到期由前端用 refresh 静默换新'),
            ('session.idle_timeout_minutes',      '30',  'int', '空闲超时（分钟）：超过此时长没有换证（无操作）即登出，全公司各系统共用'),
            ('session.absolute_max_hours',        '12',  'int', '单次登录最长时长（小时）：自首次登录起到点必须重新登录'),
            ('session.display_mode_idle_minutes', '720', 'int', '展示模式（DISPLAY_MODE 角色）专用空闲超时（分钟），墙屏/看板账号')
        ON CONFLICT (config_key) DO UPDATE
           SET config_value = EXCLUDED.config_value,
               value_type = EXCLUDED.value_type,
               description = EXCLUDED.description,
               updated_at = NOW()
    """)
    # refresh 7 天固定有效期已由「空闲窗口 + 硬上限」替代
    op.execute("DELETE FROM meta.system_config WHERE config_key = 'session.refresh_token_days'")


def downgrade() -> None:
    op.execute("""
        INSERT INTO meta.system_config (config_key, config_value, value_type, description)
        VALUES ('session.refresh_token_days', '7', 'int', 'Refresh Token 有效期')
        ON CONFLICT (config_key) DO NOTHING
    """)
    op.execute("""
        DELETE FROM meta.system_config
         WHERE config_key IN ('session.idle_timeout_minutes', 'session.absolute_max_hours',
                              'session.display_mode_idle_minutes')
    """)
    op.execute("""
        UPDATE meta.system_config SET config_value = '30', updated_at = NOW()
         WHERE config_key = 'session.access_token_minutes'
    """)
    op.execute("ALTER TABLE auth.refresh_token DROP COLUMN IF EXISTS session_started_at")
