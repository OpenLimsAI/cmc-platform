"""一次登录的凭据边界及重复续期；所有写入口先锁账号，再锁凭据。"""
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from sqlalchemy.sql.elements import ColumnElement

from app.core.exceptions import TokenInvalidError
from app.domains.auth.models import RefreshToken, User

REPEAT_WINDOW = timedelta(seconds=5)


def session_start(token: RefreshToken) -> datetime:
    return token.session_started_at or token.issued_at


def session_filter(user_id: int, started_at: datetime) -> ColumnElement[bool]:
    return and_(
        RefreshToken.user_id == user_id,
        or_(RefreshToken.session_started_at == started_at,
            and_(RefreshToken.session_started_at.is_(None), RefreshToken.issued_at == started_at)),
    )


def normalized_agent(ua: str | None) -> str | None:
    return ua[:512] if ua else None


async def lock_refresh_context(db: AsyncSession, payload: dict[str, Any]) -> tuple[User, RefreshToken]:
    try:
        user_id = int(payload['sub'])
    except (KeyError, TypeError, ValueError) as exc:
        raise TokenInvalidError('refresh token 用户无效') from exc
    user = (await db.execute(
        select(User).where(User.user_id == user_id).options(selectinload(User.roles))
        .with_for_update(of=User).execution_options(populate_existing=True)
    )).scalar_one_or_none()
    if user is None:
        raise TokenInvalidError('refresh token 用户不存在')
    token = (await db.execute(
        select(RefreshToken).where(RefreshToken.jti == payload.get('jti'), RefreshToken.user_id == user_id)
        .with_for_update().execution_options(populate_existing=True)
    )).scalar_one_or_none()
    if token is None:
        raise TokenInvalidError('refresh token 不存在')
    return user, token


async def repeated_refresh_result(
    db: AsyncSession, old: RefreshToken, *, now: datetime, ip: str | None, ua: str | None,
) -> RefreshToken:
    """固定窗口从原轮换时间算；多标签页不同轮次交叠时取仍有效的末端。"""
    if (old.revoked_reason != 'rotated' or old.revoked_at is None
            or not timedelta(0) <= now - old.revoked_at <= REPEAT_WINDOW):
        raise TokenInvalidError('refresh token 已被撤销')
    started = session_start(old)
    current = old
    seen = {old.jti}
    # 仅防损坏的历史链或环；正常 5 秒窗口的链长远低于此上限。
    for _ in range(64):
        if current.revoked_reason != 'rotated' or not current.rotated_to_jti:
            break
        if current.rotated_to_jti in seen:
            break
        seen.add(current.rotated_to_jti)
        child = (await db.execute(
            select(RefreshToken).where(RefreshToken.jti == current.rotated_to_jti)
            .with_for_update().execution_options(populate_existing=True)
        )).scalar_one_or_none()
        if (child is None or child.user_id != old.user_id or session_start(child) != started
                or child.ip_address != ip or child.user_agent != normalized_agent(ua)
                or child.expires_at <= now):
            break
        if child.revoked_at is None:
            return child
        current = child
    raise TokenInvalidError('refresh token 的续期结果已失效')
