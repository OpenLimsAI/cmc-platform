"""收回 2026-09-04 滑动会话改造之前签发的长效 refresh token（最长 7 天，一直没被回收）

Revision ID: 0058_revoke_legacy_tokens
Revises: 0057_eqp_governance_fields
Create Date: 2026-09-10 04:00:00.000000

现象（负责人 2026-09-10 反馈）：打开门户直接就进去了，不用输密码。

原因：migration 0054（2026-09-04）把会话改成「滑动窗口」——每次换证只续到
min(现在+空闲 30 分钟, 首次登录+12 小时)，没人操作就自然过期。但那次改造**只影响
之后新签发的凭证**，已经发出去的旧凭证仍然保持原来的固定 7 天有效期，也没有被撤销。
于是一张 2026-09-04 签发的 admin 凭证到 2026-09-11 都还有效：浏览器一打开门户，
前端静默换证成功，人就直接进去了，空闲多久都不掉线——正是「空闲自动登出」要防的情况。

本迁移把这类遗留凭证一次性撤销：凡是**未撤销**且**有效期长度超过当前硬上限**
（session.absolute_max_hours，默认 12 小时）的，一律标记撤销。判据用「有效期长度」
而不是签发时间，这样无论历史上用过什么口径都能覆盖到。

影响：这些会话的持有人下次打开系统需要重新输一次密码。当前口径下签发的正常凭证
（30 分钟滑动窗口）不受影响，正在使用的人不会被踢。

安全性：只改 revoked_at / revoked_reason 两列，不删行、不动别的表；审计链完整保留。
"""
from collections.abc import Sequence

from alembic import op

revision: str = "0058_revoke_legacy_tokens"  # 名字要 ≤32 字符：alembic_version.version_num 是 varchar(32)
down_revision: str | None = "0057_eqp_governance_fields"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# 撤销原因用 'admin'（管理性撤销）；auth.refresh_token 的 CHECK 只允许
# rotated / logout / password_changed / admin / expired 五种
REVOKED_REASON = "admin"


def upgrade() -> None:
    op.execute(f"""
        UPDATE auth.refresh_token
           SET revoked_at = NOW(),
               revoked_reason = '{REVOKED_REASON}'
         WHERE revoked_at IS NULL
           AND expires_at - issued_at > (
                 COALESCE(
                   (SELECT config_value::int FROM meta.system_config
                     WHERE config_key = 'session.absolute_max_hours'),
                   12
                 ) * interval '1 hour'
               )
    """)


def downgrade() -> None:
    # 不恢复：撤销后的凭证不该再复活（复活等于把已经收回的长效会话重新放出去）。
    # 需要重新登录即可拿到新凭证。
    pass
