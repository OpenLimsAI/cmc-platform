-- 白皮书 Part IV 应用层权限矩阵 —— 基线授权（rd_pg = :5432 三库）
-- 用法: sudo -u postgres psql -p 5432 -v ON_ERROR_STOP=1 -f 04_grants.sql
-- 原则: Raw 库(cmc_rd) ETL 写 / 读者只读; 分析库(cmc_analytics) 统一只读+管理员写;
--       cmc_data_platform 物料库归 cmc_user。细粒度可后续按 Part IV 再收紧。

-- ============ cmc_rd（R&D 原始：ETL 写，读者只读）============
\c cmc_rd
GRANT CONNECT ON DATABASE cmc_rd TO lucullus_etl, lims_reader, lims_admin, quality_user;
GRANT USAGE ON SCHEMA meta, raw_rd_lims_samplemanager, raw_rd_usp_lucullus TO lucullus_etl, lims_reader, lims_admin;
-- ETL 读写
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA meta, raw_rd_lims_samplemanager, raw_rd_usp_lucullus TO lucullus_etl;
GRANT USAGE ON ALL SEQUENCES IN SCHEMA meta, raw_rd_lims_samplemanager, raw_rd_usp_lucullus TO lucullus_etl;
-- 只读
GRANT SELECT ON ALL TABLES IN SCHEMA meta, raw_rd_lims_samplemanager, raw_rd_usp_lucullus TO lims_reader, quality_user;
-- 管理员
GRANT ALL ON ALL TABLES IN SCHEMA meta, raw_rd_lims_samplemanager, raw_rd_usp_lucullus TO lims_admin;
-- 未来新表默认权限
ALTER DEFAULT PRIVILEGES FOR ROLE postgres IN SCHEMA meta, raw_rd_lims_samplemanager, raw_rd_usp_lucullus
  GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO lucullus_etl;
ALTER DEFAULT PRIVILEGES FOR ROLE postgres IN SCHEMA meta, raw_rd_lims_samplemanager, raw_rd_usp_lucullus
  GRANT SELECT ON TABLES TO lims_reader, quality_user;

-- ============ cmc_analytics（跨域分析：只读为主，管理员写）============
\c cmc_analytics
GRANT CONNECT ON DATABASE cmc_analytics TO lims_reader, quality_user, lims_admin, lucullus_etl, lims_mdm_writer;
DO $$
DECLARE s text;
BEGIN
  FOR s IN SELECT nspname FROM pg_namespace
           WHERE nspname NOT LIKE 'pg_%' AND nspname NOT IN ('information_schema','public')
  LOOP
    EXECUTE format('GRANT USAGE ON SCHEMA %I TO lims_reader, quality_user, lims_admin, lucullus_etl, lims_mdm_writer', s);
    EXECUTE format('GRANT SELECT ON ALL TABLES IN SCHEMA %I TO lims_reader, quality_user, lucullus_etl', s);
    EXECUTE format('GRANT ALL ON ALL TABLES IN SCHEMA %I TO lims_admin', s);
    EXECUTE format('ALTER DEFAULT PRIVILEGES FOR ROLE postgres IN SCHEMA %I GRANT SELECT ON TABLES TO lims_reader, quality_user', s);
  END LOOP;
END $$;
-- mdm/snap_mdm 由 lims_mdm_writer 写
GRANT INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA mdm, snap_mdm TO lims_mdm_writer;

-- ============ cmc_data_platform（物料/成本：cmc_user）============
\c cmc_data_platform
GRANT CONNECT ON DATABASE cmc_data_platform TO cmc_user, lims_reader;
GRANT USAGE ON SCHEMA material_mgmt, cost_accounting TO cmc_user;
GRANT ALL ON ALL TABLES IN SCHEMA material_mgmt, cost_accounting TO cmc_user;
GRANT USAGE ON ALL SEQUENCES IN SCHEMA material_mgmt, cost_accounting TO cmc_user;
ALTER DEFAULT PRIVILEGES FOR ROLE postgres IN SCHEMA material_mgmt, cost_accounting
  GRANT ALL ON TABLES TO cmc_user;

\echo 'rd_pg 三库授权完成。'

-- ============ 另需在各自端口单独执行 ============
-- gmp_pg (:5434, cmc_gmp)：仅 ETL 写 + 审计只读
--   sudo -u postgres psql -p 5434 -d cmc_gmp -c "
--     GRANT CONNECT ON DATABASE cmc_gmp TO gmp_etl, gmp_reader;
--     GRANT USAGE ON SCHEMA meta, raw_gmp_lims_labvantage TO gmp_etl, gmp_reader;
--     GRANT SELECT,INSERT,UPDATE,DELETE ON ALL TABLES IN SCHEMA meta, raw_gmp_lims_labvantage TO gmp_etl;
--     GRANT SELECT ON ALL TABLES IN SCHEMA meta, raw_gmp_lims_labvantage TO gmp_reader;
--     ALTER DEFAULT PRIVILEGES FOR ROLE postgres IN SCHEMA meta, raw_gmp_lims_labvantage GRANT SELECT ON TABLES TO gmp_reader;"
--
-- mdm_pg (:5433, cmab_mdm)：cmab_app 已是 owner（全权）；审计只读账号:
--   sudo -u postgres psql -p 5433 -d cmab_mdm -c "
--     GRANT CONNECT ON DATABASE cmab_mdm TO cmab_audit_reader;
--     GRANT USAGE ON SCHEMA audit TO cmab_audit_reader;
--     GRANT SELECT ON ALL TABLES IN SCHEMA audit TO cmab_audit_reader;"
