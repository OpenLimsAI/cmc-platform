-- gmp_pg (:5434) 角色 + cmc_gmp 库
-- 用法: sudo -u postgres psql -p 5434 -v ON_ERROR_STOP=1 -f 02_init_gmp_pg.sql
-- ⚠️ 执行前改 CHANGE_ME_*。

DO $$
DECLARE r record;
BEGIN
  FOR r IN SELECT * FROM (VALUES
      ('gmp_etl',    'CHANGE_ME_gmp_etl'),
      ('gmp_reader', 'CHANGE_ME_gmp_reader')
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

\echo 'gmp_pg 角色与库就绪。'
