#!/bin/bash
# 统一告警出口。被两处调用：
#   1) 采集/巡检程序的 ALERT_CMD（vicell_ingest.py、heartbeat_check.py）
#   2) systemd 各单元的 OnFailure=instrument-alert@%n.service
#
# 用法: ingest-alert.sh <级别> <消息>
#   级别 = CRITICAL | ERROR | WARNING | INFO
#
# 设计要点：
# - **永远 exit 0**。告警失败绝不能反过来把备份/ETL 弄挂（这是 alerting.py 的既定原则）。
# - 外呼是可选的：未配 INGEST_ALERT_WEBHOOK 时只写 journald，配上即刻生效，不用改代码。
#   查看：journalctl -t instrument-alert --since today
set -uo pipefail

SEV="${1:-INFO}"
MSG="${2:-（无消息）}"

# 把级别映射成 syslog 优先级，方便 journalctl -p 过滤
case "$SEV" in
  CRITICAL) PRIO="daemon.crit" ;;
  ERROR)    PRIO="daemon.err" ;;
  WARNING)  PRIO="daemon.warning" ;;
  *)        PRIO="daemon.info" ;;
esac

# 落 journald：这是唯一保证可用的记录方式（各单元 ProtectSystem=strict，
# 写不了任意路径，但 journald socket 始终可达）
logger -t instrument-alert -p "$PRIO" -- "[$SEV] $MSG" 2>/dev/null || true

# 外呼配置可以放独立文件（OnFailure 以 root 运行时用得到）；
# 采集程序自己的 EnvironmentFile 里若已带 INGEST_ALERT_WEBHOOK，则以已有值为准。
if [ -z "${INGEST_ALERT_WEBHOOK:-}" ] && [ -r /etc/instrument-ingest/alert.env ]; then
  # shellcheck disable=SC1091
  . /etc/instrument-ingest/alert.env 2>/dev/null || true
fi

if [ -n "${INGEST_ALERT_WEBHOOK:-}" ]; then
  # 企业微信群机器人格式。换钉钉/Slack 只需改这段 JSON。
  # --max-time 10：外呼再慢也不许拖住备份。
  BODY=$(printf '{"msgtype":"text","text":{"content":"[%s] %s"}}' "$SEV" "${MSG//\"/\\\"}")
  curl -sS --max-time 10 --noproxy '*' \
       -H 'Content-Type: application/json' \
       -d "$BODY" "$INGEST_ALERT_WEBHOOK" >/dev/null 2>&1 \
    || logger -t instrument-alert -p daemon.warning -- "外呼失败（消息已记在上一行，不影响主流程）" 2>/dev/null
fi

exit 0
