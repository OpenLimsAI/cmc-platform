#!/usr/bin/env bash
# 仅发布Mac模拟预览与Hub入口；不启动监控API/collector或源任务。
set -euo pipefail
[[ "${1:-}" == "--apply" && "$(uname -s)" == "Darwin" ]] || {
  echo "用法：在已获授权的Mac本地发布中运行 bash scripts/deploy_mac_preview.sh --apply" >&2
  exit 2
}
export PATH="/opt/homebrew/bin:/usr/bin:/bin:/usr/sbin:/sbin:$PATH"
REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
HUB="$(cd "$REPO/../cmab-hub" && pwd)"
LABEL=com.qingcheng.cmc-platform-monitor.frontend
PLIST="$HOME/Library/LaunchAgents/$LABEL.plist"
DOMAIN="gui/$(id -u)"
BACKUP="$REPO/.local/mac-preview-$(date +%Y%m%d-%H%M%S)"

# 在覆盖在用产物前检查路由、入口显隐与备份。
nginx -t
node "$REPO/scripts/check_hub_integration.cjs"
mkdir -p "$BACKUP"
[[ ! -d "$HUB/frontend/dist" ]] || cp -a "$HUB/frontend/dist" "$BACKUP/hub-dist"
[[ ! -d "$REPO/frontend/dist" ]] || cp -a "$REPO/frontend/dist" "$BACKUP/monitor-dist"
[[ ! -f "$PLIST" ]] || cp -a "$PLIST" "$BACKUP/frontend.plist"
cp "$HUB/nginx/hub-locations.conf" "$BACKUP/hub-locations.conf"
VITE_DEMO_MODE=true npm --prefix "$REPO/frontend" run build
(cd "$HUB/frontend" && pnpm build)

if launchctl print "$DOMAIN/$LABEL" >/dev/null 2>&1; then
  launchctl bootout "$DOMAIN/$LABEL"
fi
# 5125当前开发进程只有在工作目录确属本项目时才停止，不自动改端口。
PIDS="$(lsof -tiTCP:5125 -sTCP:LISTEN || true)"
for PID in $PIDS; do
  CWD="$(lsof -a -p "$PID" -d cwd -Fn | sed -n 's/^n//p')"
  [[ "$CWD" == "$REPO/frontend" ]] || { echo "5125被其他项目占用，停止发布" >&2; exit 1; }
  kill -TERM "$PID"
done
for _ in 1 2 3 4 5; do
  [[ -n "$(lsof -tiTCP:5125 -sTCP:LISTEN || true)" ]] || break
  sleep 0.2
done
[[ -z "$(lsof -tiTCP:5125 -sTCP:LISTEN || true)" ]] || { echo "5125尚未释放" >&2; exit 1; }
mkdir -p "$HOME/Library/LaunchAgents" "$HOME/Library/Logs/cmc-platform-monitor"
cp "$REPO/deploy/mac/$LABEL.plist" "$PLIST"
plutil -lint "$PLIST"
launchctl bootstrap "$DOMAIN" "$PLIST"
# 只新增路径，监听地址未改；平滑加载避免中断其他Mac应用。
nginx -t
nginx -s reload
echo "Mac预览与Hub入口已发布；备份：$BACKUP"
