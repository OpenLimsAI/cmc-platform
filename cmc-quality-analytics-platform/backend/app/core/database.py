# -*- coding: utf-8 -*-
"""SQLAlchemy 只读引擎与会话。

强制只读：每个连接在建立后执行 `SET SESSION default_transaction_read_only = on`，
会话只读防止误写，不代替账号权限。Mac 已使用仅有业务表 SELECT 权限的 qap_reader。
"""
from collections.abc import Iterator

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import settings

# 在连接启动时把整个会话设为只读（libpq options）。
# 注意：不能用 connect 事件里的 `SET SESSION ...`——那条 SET 跑在未提交事务中，
# 连接归还连接池时被回滚而失效（PG 的 SET 受事务回滚影响）。
# 用启动参数 `-c default_transaction_read_only=on` 则在连接建立时生效、不受回滚影响，
# 此参数防误写，但不能代替最小权限账号这个真正的权限边界。
engine: Engine = create_engine(
    settings.database_url,
    pool_pre_ping=True,
    pool_size=5,
    max_overflow=5,
    future=True,
    connect_args={"options": "-c default_transaction_read_only=on"},
)


SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False, future=True)


def get_session() -> Iterator[Session]:
    """FastAPI 依赖：提供一个只读会话。"""
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


def ping() -> bool:
    """连通性自检：SELECT 1。"""
    with engine.connect() as conn:
        return conn.execute(text("SELECT 1")).scalar_one() == 1
