"""
Alembic 环境配置
"""
import os
import sys
from logging.config import fileConfig
from pathlib import Path

from alembic import context
from sqlalchemy import engine_from_config, pool

# 把 backend 加入 sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.config import settings  # noqa: E402
from app.core.database import Base  # noqa: E402

# 导入所有 ORM 模型，确保 Alembic 能发现
from app.domains.audit import models as audit_models  # noqa: E402,F401
from app.domains.auth import models as auth_models  # noqa: E402,F401
from app.domains.srs import models as srs_models  # noqa: E402,F401

config = context.config

# 优先使用环境变量
db_url = os.getenv("DATABASE_URL_SYNC") or settings.DATABASE_URL_SYNC
config.set_main_option("sqlalchemy.url", db_url)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def include_name(name, type_, parent_names):
    """限定我们关心的 schema"""
    if type_ == "schema":
        return name in {"auth", "meta", "audit", "srs", "prs", "ars", "mm", "ref"}
    return True


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        include_schemas=True,
        include_name=include_name,
        version_table_schema="public",
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
            include_name=include_name,
            version_table_schema="public",
            compare_type=True,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
