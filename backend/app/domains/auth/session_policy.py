"""会话策略（空闲超时 + 滑动会话 + 硬上限）—— 读写 meta.system_config 的 session.* 键

设计（2026-09-04 负责人拍板，migration 0054）：
  - access_token_minutes      通行证有效期；到期由前端 refresh 静默换新
  - idle_timeout_minutes      空闲窗口：refresh token 每次换证只续到「现在 + 空闲窗口」
  - absolute_max_hours        硬上限：自首次登录起，到点无论多活跃都必须重登
  - display_mode_idle_minutes DISPLAY_MODE 角色专用空闲窗口（墙屏/看板）

不做进程内缓存：每次登录/换证读 4 行小表，管理员改完立即全公司生效。
.env 里的 ACCESS_TOKEN_EXPIRE_MINUTES 仅在库里缺行时兜底。
"""
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import DateTime, String, Text, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, mapped_column

from app.core.config import settings
from app.core.database import Base
from app.core.exceptions import ValidationError

DISPLAY_MODE_ROLE = "DISPLAY_MODE"

KEY_ACCESS = "session.access_token_minutes"
KEY_IDLE = "session.idle_timeout_minutes"
KEY_ABSOLUTE = "session.absolute_max_hours"
KEY_DISPLAY_IDLE = "session.display_mode_idle_minutes"

# (最小值, 最大值)：防手滑填 0 或填成秒
LIMITS: dict[str, tuple[int, int]] = {
    "access_token_minutes": (5, 120),
    "idle_timeout_minutes": (5, 1440),
    "absolute_max_hours": (1, 168),
    "display_mode_idle_minutes": (5, 10080),
}


class SystemConfig(Base):
    """meta.system_config 键值配置（migration 0030 建表；此处首次挂 ORM）"""

    __tablename__ = "system_config"
    __table_args__ = ({"schema": "meta"},)

    config_key: Mapped[str] = mapped_column(String(64), primary_key=True)
    config_value: Mapped[str] = mapped_column(Text, nullable=False)
    value_type: Mapped[str] = mapped_column(String(16), nullable=False, default="int")
    description: Mapped[str | None] = mapped_column(Text)
    is_sensitive: Mapped[bool] = mapped_column(default=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_by: Mapped[int | None] = mapped_column()


@dataclass(frozen=True)
class SessionPolicy:
    access_token_minutes: int
    idle_timeout_minutes: int
    absolute_max_hours: int
    display_mode_idle_minutes: int
    updated_at: datetime | None = None

    def idle_minutes_for(self, roles: Sequence[str]) -> int:
        """按角色取空闲窗口：展示模式账号放宽，其余用通用值"""
        if DISPLAY_MODE_ROLE in roles:
            return self.display_mode_idle_minutes
        return self.idle_timeout_minutes

    def to_dict(self) -> dict:
        return {
            "access_token_minutes": self.access_token_minutes,
            "idle_timeout_minutes": self.idle_timeout_minutes,
            "absolute_max_hours": self.absolute_max_hours,
            "display_mode_idle_minutes": self.display_mode_idle_minutes,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


def default_policy() -> SessionPolicy:
    return SessionPolicy(
        access_token_minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES,
        idle_timeout_minutes=30,
        absolute_max_hours=12,
        display_mode_idle_minutes=720,
    )


_FIELD_KEYS = {
    "access_token_minutes": KEY_ACCESS,
    "idle_timeout_minutes": KEY_IDLE,
    "absolute_max_hours": KEY_ABSOLUTE,
    "display_mode_idle_minutes": KEY_DISPLAY_IDLE,
}


def validate_policy(p: SessionPolicy) -> None:
    """范围 + 逻辑一致性校验；不合法抛 ValidationError（400）"""
    for field, (lo, hi) in LIMITS.items():
        v = getattr(p, field)
        if not isinstance(v, int) or v < lo or v > hi:
            raise ValidationError(f"{field} 须在 {lo}~{hi} 之间")
    if p.access_token_minutes > p.idle_timeout_minutes:
        raise ValidationError("通行证有效期不能大于空闲超时，否则空闲判断会失准")
    if p.idle_timeout_minutes > p.absolute_max_hours * 60:
        raise ValidationError("空闲超时不能大于单次登录最长时长")
    if p.display_mode_idle_minutes > p.absolute_max_hours * 60:
        raise ValidationError("展示模式空闲超时不能大于单次登录最长时长")


async def load_session_policy(db: AsyncSession) -> SessionPolicy:
    rows = (
        await db.execute(
            select(SystemConfig).where(SystemConfig.config_key.in_(list(_FIELD_KEYS.values())))
        )
    ).scalars().all()
    by_key = {r.config_key: r for r in rows}
    base = default_policy()
    values: dict[str, int] = {f: getattr(base, f) for f in _FIELD_KEYS}
    latest: datetime | None = None
    for field, key in _FIELD_KEYS.items():
        row = by_key.get(key)
        if row is None:
            continue
        try:
            values[field] = int(row.config_value)
        except (TypeError, ValueError):
            continue  # 脏值按默认处理，不让登录挂掉
        if latest is None or row.updated_at > latest:
            latest = row.updated_at
    return SessionPolicy(
        access_token_minutes=values["access_token_minutes"],
        idle_timeout_minutes=values["idle_timeout_minutes"],
        absolute_max_hours=values["absolute_max_hours"],
        display_mode_idle_minutes=values["display_mode_idle_minutes"],
        updated_at=latest,
    )


async def save_session_policy(
    db: AsyncSession, new: SessionPolicy, updated_by: int | None
) -> tuple[SessionPolicy, list[tuple[str, int, int]]]:
    """写入并返回 (保存后的策略, 变更列表 [(字段, 旧值, 新值)])。调用方负责 commit + 审计。"""
    validate_policy(new)
    current = await load_session_policy(db)
    changes: list[tuple[str, int, int]] = []
    for field, key in _FIELD_KEYS.items():
        old_v = getattr(current, field)
        new_v = getattr(new, field)
        if old_v == new_v:
            continue
        row = await db.get(SystemConfig, key)
        if row is None:
            row = SystemConfig(config_key=key, value_type="int")
            db.add(row)
        row.config_value = str(new_v)
        row.updated_by = updated_by
        row.updated_at = datetime.now(UTC)
        changes.append((field, old_v, new_v))
    await db.flush()
    return await load_session_policy(db), changes
