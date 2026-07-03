"""数据库引擎。

两个只读连接（同一实例、同一只读账号，不同库）：
- raw    -> cmc_rd（原始层，Lucullus 工艺时序，signals.py 用）
- analytics -> cmc_analytics（分析层，Vi-CELL 细胞计数，vicell.py 用）

analytics 是可选的：未配置 ANALYTICS_DATABASE_URL 时对应引擎为 None，
只影响「细胞生长曲线」接口，工艺曲线照常。
"""
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from .config import settings

_engine: AsyncEngine | None = None
_analytics_engine: AsyncEngine | None = None


def _make_engine(url: str) -> AsyncEngine:
    return create_async_engine(url, pool_pre_ping=True, pool_size=5, max_overflow=5)


def init_engine() -> None:
    global _engine, _analytics_engine
    if not settings.raw_database_url:
        raise RuntimeError("RAW_DATABASE_URL 未配置，请复制 .env.example 为 .env 并填写")
    _engine = _make_engine(settings.raw_database_url)
    if settings.analytics_database_url:
        _analytics_engine = _make_engine(settings.analytics_database_url)


async def dispose_engine() -> None:
    global _engine, _analytics_engine
    if _engine is not None:
        await _engine.dispose()
        _engine = None
    if _analytics_engine is not None:
        await _analytics_engine.dispose()
        _analytics_engine = None


def engine() -> AsyncEngine:
    if _engine is None:
        raise RuntimeError("数据库引擎未初始化")
    return _engine


def analytics_engine() -> AsyncEngine:
    if _analytics_engine is None:
        raise RuntimeError(
            "cmc_analytics 引擎未初始化：请在 .env 配置 ANALYTICS_DATABASE_URL"
        )
    return _analytics_engine
