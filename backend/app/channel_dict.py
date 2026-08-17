"""通道字典：原始 channel_code → 人话名 / 分组 / 排序（来自 cmc_analytics.dim.channel_dict）。

字典是权威数据，放数据库不放代码；本模块只做「读 + 进程内缓存」：
- 每 10 分钟最多回库一次，通道列表接口不用每次查字典；
- 未配置 ANALYTICS_DATABASE_URL、或字典表不存在 / 查询失败时，返回空字典 → 前端回退显示 channel_code，
  工艺曲线功能不受影响（字典只是锦上添花，绝不能把主功能拖垮）。
"""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass

from sqlalchemy import text

from . import db

log = logging.getLogger(__name__)

_TTL_SECONDS = 600


@dataclass(frozen=True)
class ChannelMeta:
    channel_code: str
    display_name: str
    display_name_en: str | None
    category: str
    measure_kind: str
    device_tag: str | None
    canonical_key: str | None
    is_preferred: bool
    unit: str | None
    range_min: float | None
    range_max: float | None
    is_active: bool
    sort_order: int
    notes: str | None


_cache: dict[str, ChannelMeta] = {}
_cache_at: float = 0.0


async def get_channel_dict(force: bool = False) -> dict[str, ChannelMeta]:
    """返回 {channel_code: ChannelMeta}。失败或未配置时返回 {}（可能是缓存的旧值）。"""
    global _cache, _cache_at
    now = time.monotonic()
    if not force and _cache and now - _cache_at < _TTL_SECONDS:
        return _cache
    try:
        eng = db.analytics_engine()
    except RuntimeError:
        return _cache  # 未配置 analytics 连接：无字典
    sql = text(
        """
        SELECT channel_code, display_name, display_name_en, category, measure_kind,
               device_tag, canonical_key, is_preferred, unit, range_min, range_max,
               is_active, sort_order, notes
        FROM dim.channel_dict
        WHERE source_system = 'lucullus'
        """
    )
    try:
        async with eng.connect() as conn:
            rows = (await conn.execute(sql)).mappings().all()
    except Exception as e:  # noqa: BLE001 —— 字典读不到不能影响主功能
        log.warning("读取 dim.channel_dict 失败，沿用缓存/回退原始通道名: %s", e)
        return _cache
    _cache = {r["channel_code"]: ChannelMeta(**dict(r)) for r in rows}
    _cache_at = now
    return _cache
