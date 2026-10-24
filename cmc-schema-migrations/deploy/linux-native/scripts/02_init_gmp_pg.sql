-- gmp_pg (:5434) 角色 + cmc_gmp 库 + cmab_qv 库（验证部平台，2026-09-10）
-- 用法: sudo -u postgres psql -p 5434 -v ON_ERROR_STOP=1 -f 02_init_gmp_pg.sql
-- ⚠️ 执行前改 CHANGE_ME_*。

DO $$
DECLARE r record;
BEGIN
  FOR r IN SELECT * FROM (VALUES
      ('gmp_etl',    'CHANGE_ME_gmp_etl'),
      ('gmp_reader', 'CHANGE_ME_gmp_reader'),
      ('qv_app',     'CHANGE_ME_qv_app'),
      ('qv_reader',  'CHANGE_ME_qv_reader')
    ) AS t(rolname, pw)
  LOOP
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = r.rolname) THEN
      EXECUTE format('CREATE ROLE %I LOGIN PASSWORD %L', r.rolname, r.pw);
    ELSE
      EXECUTE format('ALTER ROLE %I LOGIN PASSWORD %L', r.rolname, r.pw);
    END IF;
  END LOOP;
END $$;

SELECT 'CREATE DATABASE cmc_gmp'
  WHERE NOT EXISTS (SELECT 1 FROM pg_database WHERE datname='cmc_gmp')\gexec

SELECT 'CREATE DATABASE cmab_qv'
  WHERE NOT EXISTS (SELECT 1 FROM pg_database WHERE datname='cmab_qv')\gexec
-- 之后：cd cmc-schema-migrations && ./dbmig cmab_qv upgrade head（建 schema / 授权）

\echo 'gmp_pg 角色与库就绪。'
