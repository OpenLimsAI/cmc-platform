#!/usr/bin/env bash
# CMAB MDM Portal - PostgreSQL 备份脚本（P4.B-6；2026-09-10 增加 Linux 原生模式）
#
# 用途：全库 pg_dump（custom format，可压缩、可并行恢复）+ 保留窗口清理
#
# 两种模式，自动识别：
#   docker  —— Mac 本地开发：库在容器 cmab-mdm-postgres 里
#   native  —— Linux 正式环境：库是原生 postgresql@16-mdm（:5433），连接串取自 backend/.env
#   可用 BACKUP_MODE=docker|native 强制指定。
#
# 调用：
#   - Linux 由 systemd timer 每天跑（deploy/systemd/cmab-mdm-backup.timer）
#   - 或手工：bash scripts/backup_db.sh
#
# 合规：21 CFR Part 11 §11.10(c)「保护记录使其能够准确、迅速地检索」
# 建议保留窗口：在线 30 天 + 离线归档 ≥ 7 年（药品上市后归档要求）
#
# 退出码：0=成功 / 1=参数错 / 2=备份失败 / 3=清理失败

set -euo pipefail
umask 077

# ---------- 参数（环境变量优先） ----------
REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PG_CONTAINER="${PG_CONTAINER:-cmab-mdm-postgres}"
PG_DB="${POSTGRES_DB:-cmab_mdm}"
PG_USER="${POSTGRES_DBA_USER:-postgres}"
RETENTION_DAYS="${RETENTION_DAYS:-30}"
COMPRESS_LEVEL="${COMPRESS_LEVEL:-6}"   # 0-9，pg_dump custom format

# 模式判定：显式指定 > 容器在跑则 docker > 否则 native
if [[ -z "${BACKUP_MODE:-}" ]]; then
    if command -v docker >/dev/null 2>&1 && docker ps --format '{{.Names}}' 2>/dev/null | grep -q "^${PG_CONTAINER}$"; then
        BACKUP_MODE=docker
    else
        BACKUP_MODE=native
    fi
fi

if [[ "$BACKUP_MODE" == "docker" ]]; then
    BACKUP_DIR="${BACKUP_DIR:-${REPO_DIR}/backups}"
else
    # Linux 正式环境：与既有手工备份同目录（~/cmc_backups），便于统一归档
    BACKUP_DIR="${BACKUP_DIR:-${HOME}/cmc_backups/mdm}"
    # 连接串取自 backend/.env 的 DATABASE_URL_SYNC（形如 postgresql://user:pw@127.0.0.1:5433/cmab_mdm）
    PG_DSN="${PG_DSN:-$(grep -h '^DATABASE_URL_SYNC=' "${REPO_DIR}/backend/.env" 2>/dev/null | head -1 | cut -d= -f2-)}"
fi

# ---------- 主流程 ----------
mkdir -p "$BACKUP_DIR"

TIMESTAMP=$(date -u +"%Y%m%d_%H%M")
HOSTNAME_TAG=$(hostname -s | tr -cd '[:alnum:]_-')
DUMP_FILE="cmab_mdm_${HOSTNAME_TAG}_${TIMESTAMP}.dump"
LOG_FILE="${BACKUP_DIR}/backup.log"

log() {
    echo "[$(date -u +"%Y-%m-%dT%H:%M:%SZ")] $*" | tee -a "$LOG_FILE"
}

HOST_PATH="${BACKUP_DIR}/${DUMP_FILE}"
BACKUP_STARTED_AT=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
log "==== 备份开始（${BACKUP_MODE} 模式）：${PG_DB} → ${HOST_PATH} ===="

if [[ "$BACKUP_MODE" == "docker" ]]; then
    if ! docker ps --format '{{.Names}}' | grep -q "^${PG_CONTAINER}$"; then
        log "ERROR：postgres 容器 ${PG_CONTAINER} 未运行"
        exit 2
    fi
    # 容器内 dump 到 /tmp 再拷回宿主（不依赖 compose 是否挂了 /backups）
    if ! docker exec "$PG_CONTAINER" pg_dump -U "$PG_USER" -d "$PG_DB" \
            -F c -Z "$COMPRESS_LEVEL" -f "/tmp/${DUMP_FILE}" 2>>"$LOG_FILE"
    then
        log "ERROR：pg_dump 失败，详见 ${LOG_FILE}"
        exit 2
    fi
    docker cp "${PG_CONTAINER}:/tmp/${DUMP_FILE}" "$HOST_PATH" >>"$LOG_FILE" 2>&1
    docker exec "$PG_CONTAINER" rm -f "/tmp/${DUMP_FILE}" >>"$LOG_FILE" 2>&1 || true
else
    if [[ -z "${PG_DSN:-}" ]]; then
        log "ERROR：拿不到连接串（backend/.env 里的 DATABASE_URL_SYNC），也未提供 PG_DSN"
        exit 1
    fi
    # Daily native backups opt into a same-snapshot baseline. Release/manual
    # backups retain the ordinary path unless explicitly enabled.
    SNAPSHOT_OK=0
    if [[ "${BACKUP_VERIFY_ENABLED:-0}" == "1" ]]; then
        if PG_DSN="$PG_DSN" "${REPO_DIR}/backend/.venv/bin/python" \
            "${REPO_DIR}/scripts/mdm_backup_verification.py" snapshot \
            --output "$HOST_PATH" --level "$COMPRESS_LEVEL" 2>>"$LOG_FILE"; then
            SNAPSHOT_OK=1
        else
            log "WARN：备份时点基线不可用，回退普通全库备份；完整性不能视为已验证"
        fi
    fi
    if [[ "$SNAPSHOT_OK" != "1" ]]; then
        if ! pg_dump "$PG_DSN" -F c -Z "$COMPRESS_LEVEL" -f "$HOST_PATH" 2>>"$LOG_FILE"; then
            log "ERROR：pg_dump 失败，详见 ${LOG_FILE}"
            exit 2
        fi
    fi
fi

# 校验文件存在 + 大小 > 0
if [[ ! -s "$HOST_PATH" ]]; then
    log "ERROR：备份文件 ${HOST_PATH} 不存在或为空"
    exit 2
fi
SIZE=$(du -h "$HOST_PATH" | cut -f1)
chmod 600 "$HOST_PATH" 2>/dev/null || true   # 备份含全部业务数据，仅属主可读
log "✓ 备份完成 ${HOST_PATH}（${SIZE}）"

# Enqueue only this completed daily artifact. Verification has an independent
# outcome; unavailable Docker/monitor must not change the backup exit status.
if [[ "$BACKUP_MODE" == "native" && "${BACKUP_VERIFY_ENABLED:-0}" == "1" ]]; then
    if ! /usr/bin/python3 "${REPO_DIR}/scripts/mdm_backup_verification.py" enqueue \
        --artifact "$HOST_PATH" --start "$BACKUP_STARTED_AT" \
        --finish "$(date -u +"%Y-%m-%dT%H:%M:%SZ")" --invocation "${INVOCATION_ID:-}" 2>>"$LOG_FILE"; then
        log "WARN：恢复验证请求未完成；本次备份文件已生成，验证结果须另行核查"
    fi
fi

# ---------- 保留窗口清理 ----------
log "清理 ${RETENTION_DAYS} 天前的 cmab_mdm_*.dump"
if ! find "$BACKUP_DIR" -maxdepth 1 -name "cmab_mdm_*.dump" -type f \
       -mtime +"${RETENTION_DAYS}" -delete 2>>"$LOG_FILE"
then
    log "WARN：清理过期备份失败（不阻断本次备份）"
    exit 3
fi

# Baseline sidecars are private source evidence; their dump retention is 30d.
find "$BACKUP_DIR" -maxdepth 1 -name 'cmab_mdm_*.dump.baseline.json' -type f \
    -mtime +"${RETENTION_DAYS}" -delete 2>>"$LOG_FILE" || \
    log "WARN：过期基线摘要清理失败"

REMAIN=$(find "$BACKUP_DIR" -maxdepth 1 -name "cmab_mdm_*.dump" -type f | wc -l | tr -d ' ')
log "==== 备份结束。当前保留 ${REMAIN} 份 ===="
