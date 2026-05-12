"""
数据库连接与会话管理（async SQLAlchemy 2.0）
"""
from collections.abc import AsyncGenerator

from loguru import logger
from sqlalchemy import MetaData
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from app.core.config import settings

# ============== Base ==============
# 所有 ORM 模型继承此 Base
# 使用 schema_translate_map 支持多 schema
metadata = MetaData(
    naming_convention={
        "ix": "ix_%(column_0_label)s",
        "uq": "uq_%(table_name)s_%(column_0_name)s",
        "ck": "ck_%(table_name)s_%(constraint_name)s",
        "fk": "fk_%(table_name)s_%(referred_table_name)s_%(column_0_name)s",
        "pk": "pk_%(table_name)s",
    }
)


class Base(DeclarativeBase):
    metadata = metadata


# ============== Engine ==============
engine: AsyncEngine = create_async_engine(
    settings.DATABASE_URL,
    pool_size=settings.DB_POOL_SIZE,
    max_overflow=settings.DB_MAX_OVERFLOW,
    pool_pre_ping=True,
    pool_recycle=3600,
    echo=False,  # 生产环境关闭，调试时改 True
)

AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)


# ============== 依赖注入 ==============
async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI 依赖：获取数据库会话，并在事务起始处注入审计上下文

    审计上下文以 PG session 变量 (app.user_id / app.username / app.request_id / app.ip_address)
    形式写入当前事务，供 audit.fn_audit_trigger() 在 INSERT/UPDATE/DELETE 时读取。
    认证完成后 get_current_user 会再次调用 set_audit_session_vars 把 user 信息回灌进同一事务。
    """
    from app.shared.audit_context import set_audit_session_vars

    async with AsyncSessionLocal() as session:
        try:
            await set_audit_session_vars(session)
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


# ============== 生命周期 ==============
async def init_db():
    """启动时检查连接"""
    try:
        async with engine.begin() as conn:
            await conn.execute(__import__("sqlalchemy").text("SELECT 1"))
        logger.info("数据库连接测试成功")
    except Exception as e:
        logger.error(f"数据库连接失败: {e}")
        raise


async def close_db():
    """关闭连接池"""
    await engine.dispose()
