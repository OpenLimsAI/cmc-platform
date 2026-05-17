# 数据库连接：v0.1 双引擎
#   - analytics_engine：cmc_analytics 只读，dashboard 取数
#   - mdm_engine：cmc_mdm 读写，admin 维护主数据
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


async def get_analytics_db() -> AsyncGenerator[AsyncSession, None]:
    async with AnalyticsSessionFactory() as session:
        yield session


async def get_mdm_db() -> AsyncGenerator[AsyncSession, None]:
    async with MdmSessionFactory() as session:
        yield session
