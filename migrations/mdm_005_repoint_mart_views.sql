-- =========================================================================
-- migrations/mdm_005_repoint_mart_views.sql
--
-- 目标:把 mart.dim_method / mart.dim_employee 的取数源
--       从 ext_legacy_meta.* (FDW → cmc_data_platform legacy) 切到
--       cmc_analytics.mdm.{test_method, personnel} 本地表
--
-- 风险点:
--   * CREATE OR REPLACE VIEW 是原子操作但短瞬持锁;dev 环境无 SLA 顾虑
--   * 新视图必须保持旧列签名 (name + type) —— 旧视图用 text 列,新表是
--     varchar(n),所以 SELECT 列要 ::text 显式 cast
--   * 新增 WHERE deleted_at IS NULL 过滤,迁后 0 行受影响(全部 deleted_at NULL)
--
-- 执行前 / 后 必须做:
--   docker exec ... psql -d cmc_analytics -c "SELECT count(*) FROM mart.dim_method; SELECT count(*) FROM mart.dim_employee;"
--   迁前应是 79 / 29(从 FDW),迁后应仍是 79 / 29(从 mdm.*)
--
-- Rollback:
--   见文件末尾 commented-out section,粘出来跑即可恢复指向 ext_legacy_meta
-- =========================================================================

\set ON_ERROR_STOP on

\c cmc_analytics

BEGIN;

-- ---------- 0. 修复 mdm.* 表 owner ----------
-- 背景:mdm_002/003 用 postgres 执行,导致 mdm.test_method/personnel 的 owner
--       为 postgres,而 cmc_analytics 内 mart/staging/meta 等 schema 下的表
--       owner 都是 lims_admin。第一次跑本文件时,mart 视图 owner = lims_admin
--       (随 mart 历史)无法读 owner=postgres 的 mdm 表 (view owner needs
--       SELECT on base tables),CREATE OR REPLACE VIEW 自检阶段失败。
--       本次把 owner 统一到 lims_admin,与 cmc_analytics 其余表对齐。
-- 注:既有的 lims_reader=r 和 mdm_admin=arwd grants 不受 owner 变更影响。
ALTER TABLE mdm.test_method OWNER TO lims_admin;
ALTER TABLE mdm.personnel   OWNER TO lims_admin;

-- 设置 default privileges,确保未来 lims_admin 在 mdm 下新建表时
-- lims_reader / mdm_admin 仍自动拿到对应权限(原 001 只针对 postgres-创建的表)
ALTER DEFAULT PRIVILEGES FOR ROLE lims_admin IN SCHEMA mdm
  GRANT SELECT ON TABLES TO lims_reader;
ALTER DEFAULT PRIVILEGES FOR ROLE lims_admin IN SCHEMA mdm
  GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO mdm_admin;

-- ---------- 1. dim_method ----------
CREATE OR REPLACE VIEW mart.dim_method AS
SELECT
    method_code::text  AS method_code,
    method_name::text  AS method_name,
    std_minutes,
    target_days
FROM mdm.test_method
WHERE deleted_at IS NULL;

COMMENT ON VIEW mart.dim_method IS
'检验方法维度。2026-05-18 之前从 ext_legacy_meta.dim_method (FDW → cmc_data_platform) 取数,'
'之后改读 cmc_analytics.mdm.test_method 本地表。列签名保持兼容(全 text)。';

-- ---------- 2. dim_employee ----------
CREATE OR REPLACE VIEW mart.dim_employee AS
SELECT
    employee_id::text    AS employee_id,
    employee_name::text  AS employee_name,
    department::text     AS department,
    group_id::text       AS group_id,
    status::text         AS status
FROM mdm.personnel
WHERE deleted_at IS NULL;

COMMENT ON VIEW mart.dim_employee IS
'检测员维度。2026-05-18 之前从 ext_legacy_meta.dim_employee (FDW → cmc_data_platform) 取数,'
'之后改读 cmc_analytics.mdm.personnel 本地表。';

-- ---------- 3. 事务内校验:行数必须仍是 79 / 29 ----------
DO $$
DECLARE
  m_rows int;
  e_rows int;
BEGIN
  SELECT count(*) INTO m_rows FROM mart.dim_method;
  SELECT count(*) INTO e_rows FROM mart.dim_employee;
  IF m_rows <> 79 THEN
    RAISE EXCEPTION 'mart.dim_method row count post-repoint = % (expected 79). ROLLBACK.', m_rows;
  END IF;
  IF e_rows <> 29 THEN
    RAISE EXCEPTION 'mart.dim_employee row count post-repoint = % (expected 29). ROLLBACK.', e_rows;
  END IF;
END $$;

COMMIT;

-- ---------- 4. 末尾抽样 + 元数据确认 ----------
\echo ''
\echo '== mart.dim_method now sources from =='
SELECT view_definition FROM information_schema.views WHERE table_schema='mart' AND table_name='dim_method';
\echo '== mart.dim_employee now sources from =='
SELECT view_definition FROM information_schema.views WHERE table_schema='mart' AND table_name='dim_employee';

\echo ''
\echo '== samples (should match pre-migration values) =='
SELECT method_code, method_name, std_minutes, target_days FROM mart.dim_method ORDER BY method_code LIMIT 5;
SELECT employee_id, employee_name, department, group_id, status FROM mart.dim_employee ORDER BY employee_id LIMIT 5;

-- =========================================================================
-- ROLLBACK (粘下面这段到 psql 即可恢复指向 ext_legacy_meta;FDW 未删除,可用):
--
-- \c cmc_analytics
-- BEGIN;
-- CREATE OR REPLACE VIEW mart.dim_method AS
-- SELECT method_code, method_name, std_minutes, target_days
-- FROM ext_legacy_meta.dim_method;
--
-- CREATE OR REPLACE VIEW mart.dim_employee AS
-- SELECT employee_id, employee_name, department, group_id, status
-- FROM ext_legacy_meta.dim_employee;
-- COMMIT;
-- =========================================================================

-- applied: 2026-05-18 00:40 by Claude (Phase 3'.B;首次因 view-owner 缺权失败 +
--          rollback,加 ALTER TABLE OWNER 后重跑成功。迁前后 hash 一致)
