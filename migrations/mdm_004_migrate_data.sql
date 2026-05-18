-- =========================================================================
-- migrations/mdm_004_migrate_data.sql
--
-- 目标:把 rd_pg.cmc_mdm.{mdm_quality.method_master, mdm_core.employee_master}
--      的数据迁到 cmc_analytics.mdm.{test_method, personnel}
--
-- 执行方式:整个文件用一个 psql 会话跑,中途 \c 切库
--          docker exec -i rd_pg psql -U postgres -f /dev/stdin < mdm_004_migrate_data.sql
--      或: docker exec -i rd_pg psql -U postgres -d postgres -P pager=off \
--             -v ON_ERROR_STOP=1 < mdm_004_migrate_data.sql
--
-- 字段映射要点:
--   1. is_active boolean → status varchar:
--        true  -> 'active'   (P0 调研:79/79 全 true,29/29 status='active')
--        false -> 'inactive' (兜底分支,本次实际不会触发)
--   2. created_at / updated_at / updated_by 1:1 保留原值(包括 updated_by NULL)
--   3. created_by / description / deleted_at / deleted_by:默认 NULL(无源数据)
--
-- 临时文件:/tmp/migrate_*.csv (容器内),COMMIT 后立即用 \! rm 清理
-- =========================================================================

\set ON_ERROR_STOP on
\timing on

-- ---------- A. 从 cmc_mdm 导出到容器 /tmp ----------
\c cmc_mdm

\echo '== exporting mdm_quality.method_master =='
\COPY (SELECT method_code, method_name, std_minutes, target_days, CASE WHEN is_active THEN 'active' ELSE 'inactive' END AS status, created_at, updated_at, updated_by FROM mdm_quality.method_master ORDER BY method_code) TO '/tmp/migrate_test_method.csv' CSV HEADER

\echo '== exporting mdm_core.employee_master =='
\COPY (SELECT employee_id, employee_name, department, group_id, status, created_at, updated_at, updated_by FROM mdm_core.employee_master ORDER BY employee_id) TO '/tmp/migrate_personnel.csv' CSV HEADER

-- ---------- B. 切到 cmc_analytics,事务内导入 ----------
\c cmc_analytics

BEGIN;

-- 防御性:确认空表(本次执行前应是 0 行)
DO $$
DECLARE
  m_rows int;
  p_rows int;
BEGIN
  SELECT count(*) INTO m_rows FROM mdm.test_method;
  SELECT count(*) INTO p_rows FROM mdm.personnel;
  IF m_rows > 0 OR p_rows > 0 THEN
    RAISE EXCEPTION 'Aborting: target tables not empty (test_method=%, personnel=%). Investigate before re-running.', m_rows, p_rows;
  END IF;
END $$;

\echo '== importing into mdm.test_method =='
\COPY mdm.test_method (method_code, method_name, std_minutes, target_days, status, created_at, updated_at, updated_by) FROM '/tmp/migrate_test_method.csv' CSV HEADER

\echo '== importing into mdm.personnel =='
\COPY mdm.personnel (employee_id, employee_name, department, group_id, status, created_at, updated_at, updated_by) FROM '/tmp/migrate_personnel.csv' CSV HEADER

-- 行数预校验(失败即 ROLLBACK)
DO $$
DECLARE
  m_rows int;
  p_rows int;
BEGIN
  SELECT count(*) INTO m_rows FROM mdm.test_method;
  SELECT count(*) INTO p_rows FROM mdm.personnel;
  IF m_rows <> 79 THEN
    RAISE EXCEPTION 'Row count mismatch: test_method imported % rows, expected 79', m_rows;
  END IF;
  IF p_rows <> 29 THEN
    RAISE EXCEPTION 'Row count mismatch: personnel imported % rows, expected 29', p_rows;
  END IF;
END $$;

COMMIT;

-- ---------- C. 清理临时文件 ----------
\! rm -f /tmp/migrate_test_method.csv /tmp/migrate_personnel.csv

-- ---------- D. 末尾抽样核对 ----------
\echo ''
\echo '== POST-MIGRATION SAMPLES =='
SELECT method_code, method_name, std_minutes, target_days, status FROM mdm.test_method ORDER BY method_code LIMIT 5;
SELECT employee_id, employee_name, department, group_id, status FROM mdm.personnel ORDER BY employee_id LIMIT 5;

-- applied: 2026-05-18 00:35 by Claude (Phase 3'.A 自动执行,79+29 行,逐字段 diff 与源一致)
