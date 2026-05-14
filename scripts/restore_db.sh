#!/usr/bin/env bash
# CMAB MDM Portal - PostgreSQL 恢复脚本（P4.B-6）
#
# 用途：从 backup_db.sh 产出的 .dump 文件恢复整个数据库
# ⚠️ 危险操作：会先 DROP DATABASE，再 CREATE + restore。仅用于灾难恢复 / 演练
#
# 用法：
#   bash scripts/restore_db.sh <dump-file>
#   # dump-file 可以是 host 上完整路径或 BACKUP_DIR 内文件名
#
# 合规：恢复前后必须执行 IQ/OQ 验证（CSV 验证 §3.4 数据完整性确认）

set -euo pipefail

if [[ $# -ne 1 ]]; then
    echo "用法：$0 <dump-file>"
    echo "例：  $0 cmab_mdm_host_20260513_0200.dump"
    exit 1
fi

DUMP_ARG="$1"
BACKUP_DIR="${BACKUP_DIR:-/var/lib/cmab-mdm/backups}"
PG_CONTAINER="${PG_CONTAINER:-cmab-mdm-postgres}"
PG_DB="${POSTGRES_DB:-cmab_mdm}"
PG_USER="${POSTGRES_DBA_USER:-postgres}"

# 解析 dump 路径
if [[ "$DUMP_ARG" = /* ]]; then
    HOST_PATH="$DUMP_ARG"
else
    HOST_PATH="${BACKUP_DIR}/${DUMP_ARG}"
fi

if [[ ! -s "$HOST_PATH" ]]; then
    echo "ERROR：备份文件 $HOST_PATH 不存在或为空"
    exit 2
fi

DUMP_FILE=$(basename "$HOST_PATH")

echo "==== 准备恢复 ===="
echo "  容器     : $PG_CONTAINER"
echo "  目标库   : $PG_DB"
echo "  来源文件 : $HOST_PATH"
echo ""
read -r -p "⚠️ 这会 DROP + 重建库 ${PG_DB}，所有数据将被覆盖。输入 YES 继续："  CONFIRM
if [[ "$CONFIRM" != "YES" ]]; then
    echo "已取消。"
    exit 0
fi

# 步骤 1：踢掉所有连接
docker exec "$PG_CONTAINER" psql -U "$PG_USER" -d postgres -c \
    "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = '${PG_DB}' AND pid <> pg_backend_pid();" \
    >/dev/null

# 步骤 2：DROP + CREATE
docker exec "$PG_CONTAINER" psql -U "$PG_USER" -d postgres -c \
    "DROP DATABASE IF EXISTS ${PG_DB};"
docker exec "$PG_CONTAINER" psql -U "$PG_USER" -d postgres -c \
    "CREATE DATABASE ${PG_DB} WITH ENCODING='UTF8';"

# 步骤 3：pg_restore（custom format）
# 备份文件应已挂到容器内 /backups/
docker exec "$PG_CONTAINER" pg_restore \
    -U "$PG_USER" \
    -d "$PG_DB" \
    --no-owner \
    --no-privileges \
    --verbose \
    "/backups/${DUMP_FILE}"

echo ""
echo "✓ 恢复完成。请立即跑下列验证："
echo "  1. docker exec ${PG_CONTAINER} alembic current   # 版本应 = 备份时 head"
echo "  2. make test-be                                 # 全量回归测试"
echo "  3. 业务侧抽检：物质 / 项目 / 资产 / 物料各域记录数与备份时间点比对"
