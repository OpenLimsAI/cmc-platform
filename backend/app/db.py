from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from .config import settings

_engine: AsyncEngine | None = None


def init_engine() -> None:
    global _engine
    if not settings.raw_database_url:
        raise RuntimeError("RAW_DATABASE_URL 未配置，请复制 .env.example 为 .env 并填写")
    _engine = create_async_engine(
        settings.raw_database_url,
        pool_pre_ping=True,
        pool_size=5,
        max_overflow=5,
    )


async def dispose_engine() -> None:
    global _engine
    if _engine is not None:
        await _engine.dispose()
        _engine = None


def engine() -> AsyncEngine:
    if _engine is None:
        raise RuntimeError("数据库引擎未初始化")
    return _engine
