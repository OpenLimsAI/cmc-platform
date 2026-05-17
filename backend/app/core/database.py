# 数据库连接：异步 SQLAlchemy engine + session 工厂
from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import settings

engine = create_async_engine(
    settings.database_url,
    pool_size=5,
    max_overflow=10,
    pool_pre_ping=True,
    echo=(settings.app_env == "development"),
)

AsyncSessionFactory = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)

admin_engine = create_async_engine(
    settings.admin_database_url or settings.database_url,
    pool_size=2,
    max_overflow=5,
    pool_pre_ping=True,
    echo=(settings.app_env == "development"),
)

AdminSessionFactory = async_sessionmaker(
    admin_engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionFactory() as session:
        yield session


async def get_admin_db() -> AsyncGenerator[AsyncSession, None]:
    async with AdminSessionFactory() as session:
        yield session
