#!/usr/bin/env bash
# 在 Linux 上新建 mdm_pg(:5433) 和 gmp_pg(:5434) 两个原生 PG16 集群。
# rd_pg = 现有 16/main:5432，不在此创建。
# 需以 root / sudo 运行（pg_createcluster 属 postgresql-common，Debian/Ubuntu）。
set -euo pipefail

PGVER=16

create() {
  local name="$1" port="$2"
  if pg_lsclusters -h 2>/dev/null | awk '{print $1"/"$2}' | grep -qx "${PGVER}/${name}"; then
    echo "集群 ${PGVER}/${name} 已存在，跳过"
  else
    echo "创建集群 ${PGVER}/${name} 端口 ${port} ..."
    pg_createcluster "$PGVER" "$name" --port "$port" --start \
      -- --encoding=UTF8 --locale=C.UTF-8
  fi
  # 开机自启
  systemctl enable "postgresql@${PGVER}-${name}" >/dev/null 2>&1 || true
}

create mdm 5433
create gmp 5434

echo "----"
pg_lsclusters
echo "完成。下一步：分别用 -p 5432/5433/5434 跑 02_init_*.sql"
