# 数据库连接：
#   - analytics_engine：lims_reader @ cmc_analytics，mart.* 只读，dashboard 取数
#   - mdm_engine：lims_mdm_writer @ cmc_analytics，mdm.{personnel,test_method} 读写，admin 维护主数据
#   - raw_engine（可选）：lims_reader @ cmc_rd，meta.etl_run 只读，data-freshness 拿 ETL 跑完时间
# analytics 和 mdm 都连 cmc_analytics，分开仅为隔离读 / 写角色。raw 是旁路读取，专用于一个端点。
from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import settings

analytics_engine = create_async_engine(
    settings.analytics_database_url,
    pool_size=5,
    max_overflow=10,
    pool_pre_ping=True,
    echo=(settings.app_env == "development"),
)

AnalyticsSessionFactory = async_sessionmaker(
    analytics_engine,
    class_=AsyncSession,
    expire_on_commit=False,
)

mdm_engine = create_async_engine(
    settings.mdm_database_url or settings.analytics_database_url,
    pool_size=2,
    max_overflow=5,
    pool_pre_ping=True,
    echo=(settings.app_env == "development"),
)

MdmSessionFactory = async_sessionmaker(
    mdm_engine,
    class_=AsyncSession,
    expire_on_commit=False,
)

# raw_engine 可选：未配置 raw_database_url 时为 None，依赖 get_raw_db 会 yield None
raw_engine = (
    create_async_engine(
        settings.raw_database_url,
        pool_size=1,
        max_overflow=2,
        pool_pre_ping=True,
        echo=(settings.app_env == "development"),
    )
    if settings.raw_database_url
    else None
)

RawSessionFactory = (
    async_sessionmaker(raw_engine, class_=AsyncSession, expire_on_commit=False)
    if raw_engine is not None
    else None
)


async def get_analytics_db() -> AsyncGenerator[AsyncSession, None]:
    async with AnalyticsSessionFactory() as session:
        yield session


async def get_mdm_db() -> AsyncGenerator[AsyncSession, None]:
    async with MdmSessionFactory() as session:
        yield session


async def get_raw_db() -> AsyncGenerator[AsyncSession | None, None]:
    if RawSessionFactory is None:
        yield None
        return
    async with RawSessionFactory() as session:
        yield session
