"""
数据库连接与会话管理（async SQLAlchemy 2.0）
"""
import asyncio
from collections.abc import AsyncGenerator

from loguru import logger
from sqlalchemy import MetaData, text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from app.core.config import settings
from app.core.db_release import database_target, inspect_database

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
    """Fail startup when the application and database release do not match."""
    report = await database_readiness()
    if report["status"] != "ready":
        logger.error("数据库尚未就绪: {}", report)
        raise RuntimeError("Database release mismatch; run the explicit migration workflow first")
    logger.info("数据库连接、迁移版本与设备字段检查成功")


async def database_readiness() -> dict:
    """Bounded, read-only check; never exposes a DSN or performs a migration."""
    if database_target(settings.DATABASE_URL) != database_target(settings.DATABASE_URL_SYNC):
        return {"status": "target_mismatch"}
    try:
        async with asyncio.timeout(5):
            async with engine.connect() as conn:
                await conn.execute(text("SET TRANSACTION READ ONLY"))
                report = await conn.run_sync(inspect_database)
                # Public readiness must not disclose database host/user/credentials.
                report.pop("database", None)
                return report
    except Exception as exc:
        logger.warning("数据库就绪检查失败: {}", type(exc).__name__)
        return {"status": "unavailable"}


async def close_db():
    """关闭连接池"""
    await engine.dispose()
