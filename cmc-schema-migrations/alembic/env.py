"""共享 Alembic 环境（多库）。

一个 env.py 服务多个数据库：运行时用 `alembic -n <库名> ...` 选择环境，
本文件据 section 名（= 库名）从 .env 拼出连接串。4 个库共用同一套
连接凭据（PG_USER / PG_PASSWORD），仅端口按库区分：

    cmc_rd / cmc_analytics / cmc_data_platform  → rd_pg  (PG_PORT_RD, 默认 5432)
    cmc_gmp                                     → gmp_pg (PG_PORT_GMP, 默认 5434)

Mac（docker）与 Linux（原生）端口相同，故同一份 .env 两端通用。
cmab_mdm 不在此管理（由 cmab-mdm-platform app 自带 alembic，见 dbmig）。
"""
from __future__ import annotations

import os
from logging.config import fileConfig
from pathlib import Path

from alembic import context
from sqlalchemy import engine_from_config, pool

try:
    from dotenv import load_dotenv

    load_dotenv(Path(__file__).resolve().parent.parent / ".env")
except Exception:
    pass

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

DB = config.config_ini_section  # alembic -n <这里>
KNOWN = {"cmc_rd", "cmc_analytics", "cmc_analytics_training", "cmc_data_platform", "cmc_gmp", "cmab_qv"}
if DB not in KNOWN:
    raise RuntimeError(
        f"必须用 -n <库名> 指定环境；可选 {sorted(KNOWN)}（当前 section='{DB}'）。"
        " 例: alembic -n cmc_rd upgrade head"
    )

_host = os.environ.get("PG_HOST", "127.0.0.1")
_user = os.environ.get("PG_USER")
_pw = os.environ.get("PG_PASSWORD")
if not _user or not _pw:
    raise RuntimeError("PG_USER / PG_PASSWORD 未设置；请复制 .env.example 为 .env 并填写。")
_GMP_INSTANCE = {"cmc_gmp", "cmab_qv"}  # 跑在 gmp_pg:5434 的库
_port = os.environ.get("PG_PORT_GMP", "5434") if DB in _GMP_INSTANCE else os.environ.get("PG_PORT_RD", "5432")

db_url = f"postgresql+psycopg2://{_user}:{_pw}@{_host}:{_port}/{DB}"
config.set_main_option("sqlalchemy.url", db_url)

# 跨多 app 共享库，不绑定单一 ORM 模型 → 迁移手写，metadata 留空。
target_metadata = None


def run_migrations_offline() -> None:
    context.configure(
        url=db_url,
        target_metadata=target_metadata,
        literal_binds=True,
        include_schemas=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            include_schemas=True,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
