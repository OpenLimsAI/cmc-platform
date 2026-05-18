# 数据库连接：单库 cmc_analytics，两个角色
#   - analytics_engine：lims_reader，cmc_analytics.mart.* 只读，dashboard 取数
#   - mdm_engine：lims_mdm_writer，cmc_analytics.mdm.{personnel,test_method} 读写，admin 面板维护主数据
# 两个 engine 都连同一个库 (cmc_analytics)；分开是为了在角色层面隔离读 / 写权限。
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
