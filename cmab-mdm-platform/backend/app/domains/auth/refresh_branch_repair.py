"""识别既有同时续期的无直接前序分支；保留历史，只结束仍有效的受影响登录。"""
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select, text, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.audit.models import AuditLog
from app.domains.auth.models import RefreshToken, User
from app.domains.auth.refresh_sessions import session_filter

# 同账号/登录起点/来源，签发相差不足 1 秒，且另一条新行有直接旧行指向。
# 正常登录根由 login_history 排除；单凭相同用户名或接近的时间不能认定分支。
BRANCHES_SQL = """
WITH candidates AS (
 SELECT n.user_id, n.jti, n.session_started_at
 FROM auth.refresh_token n
 WHERE (CAST(:user_id AS BIGINT) IS NULL OR n.user_id = CAST(:user_id AS BIGINT))
 AND n.session_started_at IS NOT NULL
 AND EXISTS (SELECT 1 FROM auth.refresh_token a WHERE a.user_id=n.user_id
   AND a.session_started_at=n.session_started_at AND a.revoked_at IS NULL AND a.expires_at>:now)
 AND NOT EXISTS (SELECT 1 FROM auth.refresh_token p WHERE p.rotated_to_jti = n.jti)
 AND NOT EXISTS (SELECT 1 FROM auth.login_history h WHERE h.user_id = n.user_id
   AND h.success AND abs(extract(epoch FROM h.login_at - n.issued_at)) < 1)
 AND EXISTS (
   SELECT 1 FROM auth.refresh_token p JOIN auth.refresh_token s ON s.jti = p.rotated_to_jti
   WHERE p.user_id = n.user_id AND p.revoked_reason = 'rotated'
   AND coalesce(p.session_started_at, p.issued_at) = n.session_started_at
   AND abs(extract(epoch FROM p.revoked_at - n.issued_at)) < 1
   AND s.user_id = n.user_id AND s.session_started_at = n.session_started_at
   AND s.user_agent IS NOT DISTINCT FROM n.user_agent
   AND s.ip_address IS NOT DISTINCT FROM n.ip_address
   AND abs(extract(epoch FROM s.issued_at - n.issued_at)) < 1
 )
)
SELECT user_id, session_started_at, count(*) AS branches
FROM candidates GROUP BY user_id, session_started_at ORDER BY user_id, session_started_at
"""


async def affected_sessions(
    db: AsyncSession, *, now: datetime | None = None, user_id: int | None = None,
) -> list[dict[str, Any]]:
    result = await db.execute(text(BRANCHES_SQL), {'now': now or datetime.now(UTC), 'user_id': user_id})
    return [dict(row) for row in result.mappings()]


async def close_affected_sessions(db: AsyncSession, *, actor: User, reason: str) -> dict[str, int]:
    """调用者提交或回滚；每个账号加锁后重新识别，不按过期的预览结果执行。"""
    candidates = await affected_sessions(db)
    closed, revoked_total = 0, 0
    for user_id in sorted({row['user_id'] for row in candidates}):
        target = (await db.execute(select(User).where(User.user_id == user_id)
                                  .with_for_update().execution_options(populate_existing=True))).scalar_one()
        now = datetime.now(UTC)
        for session in await affected_sessions(db, now=now, user_id=user_id):
            revoked = (await db.execute(update(RefreshToken).where(
                session_filter(user_id, session['session_started_at']),
                RefreshToken.revoked_at.is_(None), RefreshToken.expires_at > now,
            ).values(revoked_at=now, revoked_reason='admin').returning(RefreshToken.jti))).scalars().all()
            if not revoked:
                continue
            closed += 1
            revoked_total += len(revoked)
            db.add(AuditLog(
                user_id=actor.user_id, username=actor.username, action='UPDATE',
                entity_schema='auth', entity_table='user', entity_id=user_id,
                entity_code=target.username, session_id=session['session_started_at'].isoformat(),
                reason=reason, change_summary='维护命令结束同时续期分支所影响的当前登录，历史记录保留',
                extra={'operation': 'close_refresh_branches', 'revoked_records': len(revoked),
                       'detected_branches': session['branches']},
            ))
    await db.flush()
    return {'closed_sessions': closed, 'revoked_records': revoked_total}
