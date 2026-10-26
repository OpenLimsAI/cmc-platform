"""
为测试创建/重建独立 test DB（默认 cmab_test），复刻 deploy/postgres/init/01-init.sql
里**与数据库绑定**的部分（扩展 / schema / search_path / 授权）。

容器内无 psql，故用 asyncpg 以 DBA 账号执行。每次 --recreate 都 DROP + CREATE，
保证确定性基线，根治 dev DB 数据漂移咬测试的问题（schema 内对象仍由 alembic 建）。

用法（在 backend 容器内）：
  python -m app.scripts.bootstrap_test_db --recreate

环境变量（compose 已注入）：
  POSTGRES_DBA_USER / POSTGRES_DBA_PASSWORD  DBA 账号
  POSTGRES_USER     / POSTGRES_PASSWORD      应用账号（schema owner）
  TEST_DB                                    测试库名（默认 cmab_test）
  TEST_DB_HOST                               PG 主机（默认 postgres）
"""
from __future__ import annotations

import argparse
import asyncio
import os
import sys

import asyncpg
from loguru import logger

# 与 01-init.sql 一致；eqp schema 由 migration 0040 建，这里不预建。
EXTENSIONS = ["pgcrypto", "pg_trgm", "btree_gin", "unaccent"]
SCHEMAS = ["auth", "meta", "audit", "srs", "prs", "ars", "mm", "ref"]
SEARCH_PATH = "public, srs, prs, ars, mm, ref, auth, meta, audit"


def _env(name: str, default: str) -> str:
    return os.getenv(name, default)


async def bootstrap(recreate: bool) -> None:
    host = _env("TEST_DB_HOST", "postgres")
    port = int(_env("TEST_DB_PORT", "5432"))
    dba_user = _env("POSTGRES_DBA_USER", "postgres")
    dba_pass = _env("POSTGRES_DBA_PASSWORD", "__REDACTED_POSTGRES_DBA_PASSWORD__")
    app_user = _env("POSTGRES_USER", "cmab_app")
    test_db = _env("TEST_DB", "cmab_test")

    if test_db in ("cmab_mdm", "postgres"):
        raise SystemExit(f"拒绝把 {test_db} 当测试库（会毁掉真实库）")

    # 1) 连 maintenance db 'postgres'，DROP + CREATE 测试库
    sys_conn = await asyncpg.connect(
        host=host, port=port, user=dba_user, password=dba_pass, database="postgres"
    )
    try:
        exists = await sys_conn.fetchval(
            "SELECT 1 FROM pg_database WHERE datname = $1", test_db
        )
        if exists and recreate:
            await sys_conn.execute(
                """
                SELECT pg_terminate_backend(pid)
                FROM pg_stat_activity
                WHERE datname = $1 AND pid <> pg_backend_pid()
                """,
                test_db,
            )
            await sys_conn.execute(f'DROP DATABASE "{test_db}"')
            logger.info(f"已 DROP 旧测试库 {test_db}")
            exists = False
        if not exists:
            await sys_conn.execute(f'CREATE DATABASE "{test_db}" OWNER "{app_user}"')
            logger.success(f"已 CREATE 测试库 {test_db}（owner={app_user}）")
    finally:
        await sys_conn.close()

    # 2) 连测试库，建扩展 / 时区 / search_path / schema / 授权
    db_conn = await asyncpg.connect(
        host=host, port=port, user=dba_user, password=dba_pass, database=test_db
    )
    try:
        for ext in EXTENSIONS:
            await db_conn.execute(f'CREATE EXTENSION IF NOT EXISTS "{ext}"')
        await db_conn.execute(f'ALTER DATABASE "{test_db}" SET timezone TO \'UTC\'')
        await db_conn.execute(
            f'ALTER DATABASE "{test_db}" SET search_path TO {SEARCH_PATH}'
        )
        # PG15+ 默认收回 public.CREATE；alembic_version 建在 public
        await db_conn.execute(f'GRANT CREATE, USAGE ON SCHEMA public TO "{app_user}"')
        for sch in SCHEMAS:
            await db_conn.execute(
                f'CREATE SCHEMA IF NOT EXISTS {sch} AUTHORIZATION "{app_user}"'
            )
        logger.success(
            f"测试库 {test_db} 引导完成：{len(EXTENSIONS)} 扩展 + {len(SCHEMAS)} schema"
        )
    finally:
        await db_conn.close()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--recreate",
        action="store_true",
        help="若测试库已存在则先 DROP（确定性基线）",
    )
    args = ap.parse_args()
    asyncio.run(bootstrap(recreate=args.recreate))
    return 0


if __name__ == "__main__":
    sys.exit(main())
