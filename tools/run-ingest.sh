#!/bin/bash
# =====================================================================
# 统一采集入口 —— 一次把本机所有仪器跑一遍
#
# 用法: run-ingest.sh <day|night> [设备...]
#   day    白天班：不抓图片。仪器白天在用，读图片目录会撞上文件占用
#          （2026-08-04 11:31~11:54 实测：反复 Device or resource busy）
#   night  夜班：全量，含图片
#   设备    可选，flex2 / vicell，不填则跑全部
#
# 为什么要有这个脚本（2026-08-05 定）：
#   两台仪器的数据量都很小（每趟几十个 txt/csv），原先按设备拆成 4 个
#   systemd 定时器、各自错开 10 分钟，收益极小却让"今天几点该跑什么"
#   变得难记、难改。改成"一个时间点把所有设备跑一遍"，定时器减到 2 个。
#
# 设计要点：
#   1) **两个采集脚本不合并**。一台仪器的故障不许拖垮另一台——这里逐台跑、
#      各自记退出码，前面失败后面照跑，最后汇总一条告警。
#   2) FLEX2 先跑（几秒完成），Vi-CELL 后跑（夜班图片可能几十分钟）。
#      顺序反过来的话，图片段一慢，FLEX2 就得干等。
#   3) 退出码：全部成功 0，任一失败 1（systemd 据此触发 OnFailure 告警）。
# =====================================================================
set -uo pipefail

PY=/usr/bin/python3
REPO=/opt/cmc-instrument-ingest
ALERT="$REPO/tools/ingest-alert.sh"

MODE="${1:-}"
case "$MODE" in
  day|night) shift ;;
  *) echo "用法: $0 <day|night> [flex2|vicell ...]" >&2; exit 2 ;;
esac

# ---- 互斥锁（2026-08-11 加）----
# day/night 两个 timer 都是 Persistent=true：停机跨过两个触发点后，开机会把
# 两趟一起补跑，并发写同一批 state 文件。flock 排他锁把它们串行化：
# 后来的一趟阻塞等前一趟跑完（最多等 30 分钟），等不到就报错退出、
# 由 OnFailure 告警——绝不并发跑。
# 锁文件放 /var/lock（各 service 已加 ReadWritePaths=/run/lock，
# ProtectSystem=strict 下才写得进去）。fd 随进程退出自动释放，无需显式解锁。
exec 200>/var/lock/instrument-ingest.lock || { echo "打不开锁文件 /var/lock/instrument-ingest.lock" >&2; exit 1; }
flock -w 1800 200 || { echo "等待采集互斥锁超时（另一趟采集仍在跑？）" >&2; exit 1; }

if [ $# -gt 0 ]; then
  DEVICES=("$@")
else
  DEVICES=(flex2 vicell)
fi

# Vi-CELL：日常一律 --no-legacy（历史目录是一次性回补用的，不是每天要读的）；
# 白天再加 --no-images。
VICELL_ARGS=(--no-legacy)
[ "$MODE" = "day" ] && VICELL_ARGS+=(--no-images)
# FLEX2：--per-event 归档逐次导出文件（见 2026-07-23 的 per-event.conf 缘由）。
# FLEX2 没有"图片"这类白天读不动的大件，所以白天夜班参数相同。
FLEX2_ARGS=(--per-event)

rc_total=0
failed=()

run_one() {
  local name="$1"; shift
  echo ">>> [$MODE] 开始采集 $name"
  "$PY" "$@"
  local rc=$?
  if [ "$rc" -ne 0 ]; then
    echo "<<< [$MODE] $name 失败，退出码 $rc"
    failed+=("$name(rc=$rc)")
    rc_total=1
  else
    echo "<<< [$MODE] $name 完成"
  fi
  return 0   # 关键：这里绝不能把失败往外抛，否则后面那台仪器就不跑了
}

for dev in "${DEVICES[@]}"; do
  case "$dev" in
    flex2)  run_one flex2  "$REPO/flex2/flex2_ingest.py"   "${FLEX2_ARGS[@]}"  ;;
    vicell) run_one vicell "$REPO/vicell/vicell_ingest.py" "${VICELL_ARGS[@]}" ;;
    *)      echo "未知设备: $dev" >&2; failed+=("$dev(未知设备)"); rc_total=1 ;;
  esac
done

if [ "$rc_total" -ne 0 ]; then
  # 各脚本内部已就自己的问题告过警；这里再补一条批次级的，
  # 方便一眼看出"这一趟里哪台没成"。告警脚本永远 exit 0，不会反过来影响退出码。
  "$ALERT" ERROR "采集批次[$MODE]有设备失败: ${failed[*]}（查 journalctl -u instrument-ingest-$MODE.service）"
fi

exit "$rc_total"
