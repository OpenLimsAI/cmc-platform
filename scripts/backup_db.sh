#!/usr/bin/env bash
# CMAB MDM Portal - PostgreSQL 备份脚本（P4.B-6）
#
# 用途：定时全库 pg_dump（custom format，可压缩可并行恢复）+ 保留窗口清理
# 调用：
#   - host crond / systemd timer 定时跑（推荐每天 02:00 UTC）
#   - 或手工：bash scripts/backup_db.sh
#
# 合规：21 CFR Part 11 §11.10(c) "保护记录使其能够准确、迅速地检索"
# 建议保留窗口：在线 30 天 + 离线归档 ≥ 7 年（药品上市后归档要求）
#
# 退出码：0=成功 / 1=参数错 / 2=备份失败 / 3=清理失败

set -euo pipefail

# ---------- 参数（环境变量优先；默认对齐 docker-compose.prod） ----------
BACKUP_DIR="${BACKUP_DIR:-/var/lib/cmab-mdm/backups}"
PG_CONTAINER="${PG_CONTAINER:-cmab-mdm-postgres}"
PG_DB="${POSTGRES_DB:-cmab_mdm}"
PG_USER="${POSTGRES_DBA_USER:-postgres}"
RETENTION_DAYS="${RETENTION_DAYS:-30}"
COMPRESS_LEVEL="${COMPRESS_LEVEL:-6}"   # 0-9，pg_dump custom format

# ---------- 主流程 ----------
mkdir -p "$BACKUP_DIR"

TIMESTAMP=$(date -u +"%Y%m%d_%H%M")
HOSTNAME_TAG=$(hostname -s | tr -cd '[:alnum:]_-')
DUMP_FILE="cmab_mdm_${HOSTNAME_TAG}_${TIMESTAMP}.dump"
LOG_FILE="${BACKUP_DIR}/backup.log"

log() {
    echo "[$(date -u +"%Y-%m-%dT%H:%M:%SZ")] $*" | tee -a "$LOG_FILE"
}

log "==== 备份开始：${PG_DB} @ ${PG_CONTAINER} → ${DUMP_FILE} ===="

if ! docker ps --format '{{.Names}}' | grep -q "^${PG_CONTAINER}$"; then
    log "ERROR：postgres 容器 ${PG_CONTAINER} 未运行"
    exit 2
fi

# 在容器内 pg_dump 写到 /backups（compose 已挂载到 host BACKUP_DIR）
if ! docker exec "$PG_CONTAINER" pg_dump \
    -U "$PG_USER" \
    -d "$PG_DB" \
    -F c \
    -Z "$COMPRESS_LEVEL" \
    -f "/backups/${DUMP_FILE}" 2>>"$LOG_FILE"
then
    log "ERROR：pg_dump 失败，详见 ${LOG_FILE}"
    exit 2
fi

# 校验文件存在 + 大小 > 0
HOST_PATH="${BACKUP_DIR}/${DUMP_FILE}"
if [[ ! -s "$HOST_PATH" ]]; then
    log "ERROR：备份文件 ${HOST_PATH} 不存在或为空"
    exit 2
fi
SIZE=$(du -h "$HOST_PATH" | cut -f1)
log "✓ 备份完成 ${HOST_PATH}（${SIZE}）"

# ---------- 保留窗口清理 ----------
log "清理 ${RETENTION_DAYS} 天前的 cmab_mdm_*.dump"
if ! find "$BACKUP_DIR" -maxdepth 1 -name "cmab_mdm_*.dump" -type f \
       -mtime +"${RETENTION_DAYS}" -delete 2>>"$LOG_FILE"
then
    log "WARN：清理过期备份失败（不阻断本次备份）"
    exit 3
fi

REMAIN=$(find "$BACKUP_DIR" -maxdepth 1 -name "cmab_mdm_*.dump" -type f | wc -l | tr -d ' ')
log "==== 备份结束。当前保留 ${REMAIN} 份 ===="
