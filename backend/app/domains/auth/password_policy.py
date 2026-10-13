"""负责人确认的密码规则；历史校验与业务变更使用同一事务。"""
import re
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import PasswordInHistoryError, WeakPasswordError
from app.core.security import verify_password
from app.domains.auth.models import PasswordHistory, User
from app.domains.auth.session_policy import SystemConfig


@dataclass(frozen=True)
class PasswordPolicy:
    min_length: int = 8
    expire_days: int = 90
    history_count: int = 5


async def load_password_policy(db: AsyncSession) -> PasswordPolicy:
    keys = {"min_length": (8, 72), "expire_days": (1, 3650), "history_count": (1, 100)}
    values = {field: getattr(PasswordPolicy(), field) for field in keys}
    rows = (await db.execute(select(SystemConfig).where(
        SystemConfig.config_key.in_([f"password.{field}" for field in keys])
    ))).scalars().all()
    for row in rows:
        field = row.config_key.split(".", 1)[1]
        try:
            value = int(row.config_value)
        except (ValueError, TypeError):
            continue
        lo, hi = keys[field]
        if lo <= value <= hi:
            values[field] = value
    return PasswordPolicy(**values)


def validate_strength(password: str, policy: PasswordPolicy) -> None:
    # bcrypt 超出 72 字节会截断；新密码明确拒绝，旧密码验证保持兼容。
    if len(password.encode("utf-8")) > 72:
        raise WeakPasswordError("密码过长，请缩短到 72 字节以内（中文等字符占多个字节）")
    if len(password) < policy.min_length or not all(
        re.search(pattern, password) for pattern in (r"[A-Z]", r"[a-z]", r"[0-9]", r"[^\w\s]|_")
    ):
        raise WeakPasswordError(f"密码至少 {policy.min_length} 位，须包含大写、小写、数字和符号")


async def validate_new_password(db: AsyncSession, password: str, user: User | None = None) -> PasswordPolicy:
    policy = await load_password_policy(db)
    validate_strength(password, policy)
    if user is not None:
        hashes = (await db.execute(select(PasswordHistory.password_hash).where(
            PasswordHistory.user_id == user.user_id
        ).order_by(PasswordHistory.recorded_at.desc(), PasswordHistory.history_id.desc())
          .limit(policy.history_count))).scalars().all()
        if any(verify_password(password, hashed) for hashed in {user.password_hash, *hashes}):
            raise PasswordInHistoryError(f"不能重复使用最近 {policy.history_count} 次密码（含当前密码）")
    return policy


async def record_password(db: AsyncSession, user: User) -> None:
    db.add(PasswordHistory(user_id=user.user_id, password_hash=user.password_hash,
                           recorded_at=datetime.now(UTC)))
    await db.flush()


async def ensure_current_password_recorded(db: AsyncSession, user: User) -> None:
    found = (await db.execute(select(PasswordHistory.history_id).where(
        PasswordHistory.user_id == user.user_id, PasswordHistory.password_hash == user.password_hash
    ).limit(1))).scalar_one_or_none()
    if found is None:
        await record_password(db, user)


def requires_password_change(user: User, now: datetime | None = None) -> bool:
    return user.force_password_change or (
        user.password_expires_at is not None and user.password_expires_at <= (now or datetime.now(UTC))
    )


def temporary_password_expired(user: User, now: datetime | None = None) -> bool:
    return user.force_password_change and user.password_expires_at is not None and (
        user.password_expires_at <= (now or datetime.now(UTC))
    )


def access_deadline(user: User, minutes: int, now: datetime | None = None) -> datetime:
    now = now or datetime.now(UTC)
    deadline = now + timedelta(minutes=minutes)
    if user.password_expires_at is not None and user.password_expires_at > now:
        deadline = min(deadline, user.password_expires_at)
    return deadline
