#!/bin/bash
set -euo pipefail
root="$(cd "$(dirname "$0")/../.." && pwd)"
mkdir -p "$root/logs"
for port in 8015 5115; do
  if lsof -tiTCP:"$port" -sTCP:LISTEN >/dev/null; then echo "端口 $port 已占用，请先核对进程" >&2; exit 1; fi
done
(cd "$root/backend" && .venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8015 --no-access-log) >"$root/logs/backend.log" 2>&1 &
backend_pid=$!
(cd "$root/frontend" && pnpm dev) >"$root/logs/frontend.log" 2>&1 &
frontend_pid=$!
trap 'kill "$backend_pid" "$frontend_pid" 2>/dev/null || true' EXIT INT TERM
echo '入口：http://localhost:5100/water/；Ctrl+C 停止本次启动的两个进程'
# macOS Bash 3.2 has no wait -n. Stop the sibling if either service exits.
while kill -0 "$backend_pid" 2>/dev/null && kill -0 "$frontend_pid" 2>/dev/null; do sleep 1; done
echo '一个服务已退出，请检查 logs/backend.log 和 logs/frontend.log' >&2
exit 1
