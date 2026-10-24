-- mdm_pg (:5433) 角色 + cmab_mdm 库（owner = cmab_app）
-- 用法: sudo -u postgres psql -p 5433 -v ON_ERROR_STOP=1 -f 02_init_mdm_pg.sql
-- ⚠️ 执行前改 CHANGE_ME_*。

DO $$
DECLARE r record;
BEGIN
  FOR r IN SELECT * FROM (VALUES
      ('cmab_app',          'CHANGE_ME_cmab_app'),
      ('cmab_audit_reader', 'CHANGE_ME_cmab_audit_reader')
    ) AS t(rolname, pw)
  LOOP
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = r.rolname) THEN
      EXECUTE format('CREATE ROLE %I LOGIN PASSWORD %L', r.rolname, r.pw);
    ELSE
      EXECUTE format('ALTER ROLE %I LOGIN PASSWORD %L', r.rolname, r.pw);
    END IF;
  END LOOP;
END $$;

-- cmab_mdm 由应用账号 cmab_app 持有（与 Mac 一致：所有 schema owner=cmab_app）
SELECT 'CREATE DATABASE cmab_mdm OWNER cmab_app'
  WHERE NOT EXISTS (SELECT 1 FROM pg_database WHERE datname='cmab_mdm')\gexec

\echo 'mdm_pg 角色与库就绪。schema 用 cmab_app 身份加载（见 03_load_schemas.sh）。'
