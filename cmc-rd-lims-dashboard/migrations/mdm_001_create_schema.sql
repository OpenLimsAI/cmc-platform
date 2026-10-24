-- =========================================================================
-- migrations/mdm_001_create_schema.sql
--
-- 目标库:cmc_analytics (rd_pg :5432)
-- 作用  :在 cmc_analytics 下新建 mdm schema,作为 LIMS 域内主数据存放点
--         (test_method / personnel)。schema 自身不放表,表见 002/003。
--
-- 设计依据 (2026-05-18 决策):
--   原计划把 method/employee 主数据迁到 cmab_mdm.qms,后改为留在
--   cmc_analytics.mdm —— 因为这两张表只有本看板一个消费方,放公司级
--   MDM 是过度工程。详见 migrations/README.md "历史背景"。
--
-- 角色复用:
--   - lims_reader (已存在):看板取数账号,迁后增 mdm.* SELECT 权限
--   - mdm_admin   (已存在):原本连 cmc_mdm 写 method/employee,迁后改连
--                          cmc_analytics 写 mdm.*(SELECT 上扩到 mart.*)
--   不新建 lims_dashboard_readonly。
--
-- 幂等性:全部 IF NOT EXISTS,可重复执行。
-- =========================================================================

\set ON_ERROR_STOP on

BEGIN;

-- ---------- 1. schema ----------
CREATE SCHEMA IF NOT EXISTS mdm AUTHORIZATION lims_admin;

COMMENT ON SCHEMA mdm IS
'LIMS 域内主数据(method / personnel)。本 schema 由 Dashboard 后端写,'
'通过 mart.dim_* 视图对外暴露。看板和 cmab_mdm(公司级 MDM)正交,'
'不与 cmab_mdm.auth.user 等表重叠。建立日期 2026-05-18,'
'来源决策:见 migrations/README.md。';

-- ---------- 2. 权限 ----------

-- 2.1 lims_reader:读 mdm.* (看板取数 + mart.dim_* 视图依赖)
GRANT USAGE ON SCHEMA mdm TO lims_reader;
ALTER DEFAULT PRIVILEGES IN SCHEMA mdm
  GRANT SELECT ON TABLES TO lims_reader;

-- 2.2 mdm_admin:写 mdm.*  (admin 面板 CRUD + Excel 上传)
--      同时给 mart.* SELECT,便于 admin 端点做交叉校验。
GRANT CONNECT ON DATABASE cmc_analytics TO mdm_admin;
GRANT USAGE ON SCHEMA mdm  TO mdm_admin;
GRANT USAGE ON SCHEMA mart TO mdm_admin;
ALTER DEFAULT PRIVILEGES IN SCHEMA mdm
  GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO mdm_admin;
ALTER DEFAULT PRIVILEGES IN SCHEMA mdm
  GRANT USAGE, SELECT, UPDATE ON SEQUENCES TO mdm_admin;
GRANT SELECT ON ALL TABLES IN SCHEMA mart TO mdm_admin;
ALTER DEFAULT PRIVILEGES IN SCHEMA mart
  GRANT SELECT ON TABLES TO mdm_admin;

COMMIT;

-- 校验:
--   \dn mdm
--   \dp+ mdm.*       -- 002/003 跑完后看

-- applied: 2026-05-18 00:30 by Claude (Phase 2' 自动执行)
