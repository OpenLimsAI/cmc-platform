-- rd_pg (main:5432) 角色 + 数据库
-- 用法: sudo -u postgres psql -p 5432 -v ON_ERROR_STOP=1 -f 02_init_rd_pg.sql
-- ⚠️ 执行前把 CHANGE_ME_* 改成真实密码（或执行后 ALTER ROLE ... PASSWORD）。

-- ---- 角色（幂等：存在则只改密码）----
DO $$
DECLARE r record;
BEGIN
  FOR r IN SELECT * FROM (VALUES
      ('cmc_user',        'CHANGE_ME_cmc_user'),
      ('lims_admin',      'CHANGE_ME_lims_admin'),
      ('lims_reader',     'CHANGE_ME_lims_reader'),
      ('lims_mdm_writer', 'CHANGE_ME_lims_mdm_writer'),
      ('lucullus_etl',    'CHANGE_ME_lucullus_etl'),
      ('quality_user',    'CHANGE_ME_quality_user')
    ) AS t(rolname, pw)
  LOOP
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = r.rolname) THEN
      EXECUTE format('CREATE ROLE %I LOGIN PASSWORD %L', r.rolname, r.pw);
    ELSE
      EXECUTE format('ALTER ROLE %I LOGIN PASSWORD %L', r.rolname, r.pw);
    END IF;
  END LOOP;
END $$;

-- ---- 数据库（推平重建：先 DROP 再 CREATE，保证与 Mac 完全一致的干净结构）----
-- ⚠️ DROP DATABASE 要求无活动连接 —— 执行前必须先停掉所有应用/ETL（见 README §3.1）。
-- 连接在维护库 postgres 上执行，不会自连被删库。
-- WITH (FORCE)：PG13+ 会先踢掉残留连接再删，防止个别 straggler 卡住。
DROP DATABASE IF EXISTS cmc_data_platform WITH (FORCE);
DROP DATABASE IF EXISTS cmc_rd WITH (FORCE);
DROP DATABASE IF EXISTS cmc_analytics WITH (FORCE);
CREATE DATABASE cmc_rd;
CREATE DATABASE cmc_analytics;
CREATE DATABASE cmc_data_platform;

\echo 'rd_pg 角色与库就绪（干净重建）。'
