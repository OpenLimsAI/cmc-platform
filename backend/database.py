"""
文件: backend/database.py
用途: PostgreSQL 数据库连接配置(SQLAlchemy 2.0 风格)
说明:
    - 从环境变量 DATABASE_URL 读取连接串
    - 默认 search_path 设为 material_mgmt,所有 ORM 模型直接使用本 schema
    - 提供 FastAPI 依赖注入用的 get_db 生成器
"""
from __future__ import annotations

import os
from typing import Generator

from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, Session, declarative_base

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://cmc_user:change_me@localhost:5432/cmc_inventory",
)

# echo=False:生产关闭 SQL 日志;如需调试可设为 True
engine = create_engine(
    DATABASE_URL,
    echo=False,
    future=True,
    pool_pre_ping=True,
)

# 每个连接建立时,把 search_path 指到 material_mgmt
@event.listens_for(engine, "connect")
def _set_search_path(dbapi_conn, _connection_record):  # noqa: D401
    cur = dbapi_conn.cursor()
    cur.execute("SET search_path TO material_mgmt, public")
    cur.close()


SessionLocal = sessionmaker(
    bind=engine, autoflush=False, autocommit=False, expire_on_commit=False, future=True
)

Base = declarative_base()


def get_db() -> Generator[Session, None, None]:
    """FastAPI 依赖注入:每个请求一个 Session,结束自动关闭。"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
