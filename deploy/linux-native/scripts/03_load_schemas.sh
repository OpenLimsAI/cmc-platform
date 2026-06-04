#!/usr/bin/env bash
# 把 Mac 导出的 schema 快照灌进 Linux 各库。
# 用法: sudo bash 03_load_schemas.sh <schema目录> <cmc_data_platform_baseline.sql>
# 例:   sudo bash 03_load_schemas.sh ~/cmc-deploy/schema ~/cmc_data_platform_baseline.sql
set -euo pipefail

SCHEMA_DIR="${1:?需要 schema 目录}"
CDP_BASELINE="${2:?需要 cmc_data_platform 的 assets/004 快照路径}"

run() {  # port db file [psql_user]
  local port="$1" db="$2" file="$3" user="${4:-postgres}"
  echo "==> :$port  $db  <-  $(basename "$file")  (as $user)"
  sudo -u postgres psql -p "$port" -d "$db" -v ON_ERROR_STOP=1 \
    -c "SET ROLE $user" -f "$file" >/dev/null
  echo "    schema 数: $(sudo -u postgres psql -p "$port" -d "$db" -tAc \
    "SELECT count(*) FROM information_schema.schemata WHERE schema_name NOT LIKE 'pg_%' AND schema_name<>'information_schema'")"
}

# rd_pg :5432
run 5432 cmc_rd        "$SCHEMA_DIR/cmc_rd.schema.sql"
run 5432 cmc_analytics "$SCHEMA_DIR/cmc_analytics.schema.sql"

# cmc_data_platform：02_init 已 DROP+CREATE 为全新空库，直接灌 baseline
echo "==> :5432 cmc_data_platform  <-  $(basename "$CDP_BASELINE")"
sudo -u postgres psql -p 5432 -d cmc_data_platform -v ON_ERROR_STOP=1 -f "$CDP_BASELINE" >/dev/null
echo "    schema 数: $(sudo -u postgres psql -p 5432 -d cmc_data_platform -tAc \
  "SELECT count(*) FROM information_schema.schemata WHERE schema_name NOT LIKE 'pg_%' AND schema_name<>'information_schema'")"

# gmp_pg :5434
run 5434 cmc_gmp "$SCHEMA_DIR/cmc_gmp.schema.sql"

# mdm_pg :5433 —— cmab_mdm 含 4 个扩展(需超级用户), 必须先由 postgres 预建,
# 再以 cmab_app 身份加载(去掉 CREATE/COMMENT EXTENSION 行), 保证表/序列 owner=cmab_app。
echo "==> :5433 cmab_mdm  预建扩展(postgres) + 加载(cmab_app)"
sudo -u postgres psql -p 5433 -d cmab_mdm -v ON_ERROR_STOP=1 -c \
  "CREATE EXTENSION IF NOT EXISTS btree_gin;
   CREATE EXTENSION IF NOT EXISTS pg_trgm;
   CREATE EXTENSION IF NOT EXISTS pgcrypto;
   CREATE EXTENSION IF NOT EXISTS unaccent;"
grep -vE '^(CREATE EXTENSION|COMMENT ON EXTENSION)' "$SCHEMA_DIR/cmab_mdm.schema.sql" > /tmp/cmab_mdm.noext.sql
sudo -u postgres psql -p 5433 -d cmab_mdm -v ON_ERROR_STOP=1 -c "SET ROLE cmab_app" -f /tmp/cmab_mdm.noext.sql >/dev/null
echo "    schema 数: $(sudo -u postgres psql -p 5433 -d cmab_mdm -tAc \
  "SELECT count(*) FROM information_schema.schemata WHERE schema_name NOT LIKE 'pg_%' AND schema_name<>'information_schema'")"

echo "全部 schema 加载完成。"
