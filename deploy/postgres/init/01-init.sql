-- ============================================================
-- CMAB MDM Portal - PostgreSQL 初始化脚本
-- 此脚本在 postgres 容器首次启动时由 init 目录自动执行
-- 使用 DBA 账号（postgres）执行
-- ============================================================

-- 启用必要扩展
CREATE EXTENSION IF NOT EXISTS "pgcrypto";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";
CREATE EXTENSION IF NOT EXISTS "btree_gin";
CREATE EXTENSION IF NOT EXISTS "unaccent";

-- 设置数据库时区
ALTER DATABASE cmab_mdm SET timezone TO 'UTC';

-- 创建应用账号（如不存在）
DO $$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = 'cmab_app') THEN
        CREATE ROLE cmab_app WITH LOGIN PASSWORD '__REDACTED_POSTGRES_PASSWORD__';
    END IF;
END
$$;

-- 创建审计审查账号
DO $$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = 'cmab_audit_reader') THEN
        CREATE ROLE cmab_audit_reader WITH LOGIN PASSWORD 'audit_dev_CHANGE_ME';
    END IF;
END
$$;

-- 授权
GRANT CONNECT ON DATABASE cmab_mdm TO cmab_app;
GRANT CONNECT ON DATABASE cmab_mdm TO cmab_audit_reader;

-- PG 15+ 默认收回 public schema 的 CREATE 权限
-- alembic 版本表 (alembic_version) 默认建在 public，需显式授权
GRANT CREATE, USAGE ON SCHEMA public TO cmab_app;

-- 创建所有 schema（schema 内的对象由 Alembic 创建）
CREATE SCHEMA IF NOT EXISTS auth   AUTHORIZATION cmab_app;
CREATE SCHEMA IF NOT EXISTS meta   AUTHORIZATION cmab_app;
CREATE SCHEMA IF NOT EXISTS audit  AUTHORIZATION cmab_app;
CREATE SCHEMA IF NOT EXISTS srs    AUTHORIZATION cmab_app;
CREATE SCHEMA IF NOT EXISTS prs    AUTHORIZATION cmab_app;
CREATE SCHEMA IF NOT EXISTS ars    AUTHORIZATION cmab_app;
CREATE SCHEMA IF NOT EXISTS mm     AUTHORIZATION cmab_app;
CREATE SCHEMA IF NOT EXISTS ref    AUTHORIZATION cmab_app;

-- 设置默认 search_path
ALTER DATABASE cmab_mdm SET search_path TO public, srs, prs, ars, mm, ref, auth, meta, audit;

-- 审计 schema 给审计账号只读权限（在表创建后会再次执行）
GRANT USAGE ON SCHEMA audit TO cmab_audit_reader;

\echo '✓ CMAB MDM Portal 数据库初始化完成'
