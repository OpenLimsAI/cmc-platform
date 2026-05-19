#!/usr/bin/env bash
# =============================================================================
# 文件: restart.sh
# 用途: Linux 服务器上一键重启 CMC 库存系统前后端
#
# 用法:
#   cd /opt/cmc-inventory
#   ./restart.sh
#
# 如果提示 sudo 密码,输入 Linux 登录用户的密码即可。
# =============================================================================
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
ENV_FILE="$ROOT/.env"

BACKEND_SERVICE="${BACKEND_SERVICE:-cmc-backend}"
FRONTEND_SERVICE="${FRONTEND_SERVICE:-cmc-frontend}"
BACKEND_PORT="${BACKEND_PORT:-8000}"
FRONTEND_PORT="${FRONTEND_PORT:-8501}"

if [ -f "$ENV_FILE" ]; then
    # .env 由 systemd EnvironmentFile 使用,格式是 KEY=VALUE。
    # 这里读取端口只是为了打印访问地址,真正启动参数仍由 systemd 读取。
    BACKEND_PORT="$(grep -E '^BACKEND_PORT=' "$ENV_FILE" | tail -1 | cut -d= -f2- || true)"
    FRONTEND_PORT="$(grep -E '^FRONTEND_PORT=' "$ENV_FILE" | tail -1 | cut -d= -f2- || true)"
    BACKEND_PORT="${BACKEND_PORT:-8000}"
    FRONTEND_PORT="${FRONTEND_PORT:-8501}"
fi

server_ip() {
    hostname -I 2>/dev/null | awk '{print $1}'
}

SERVER_IP="$(server_ip)"
SERVER_IP="${SERVER_IP:-服务器IP}"

echo "============================================================"
echo " CMC 库存系统 - Linux 一键重启"
echo " 项目目录: $ROOT"
echo " 后端服务: $BACKEND_SERVICE"
echo " 前端服务: $FRONTEND_SERVICE"
echo "============================================================"
echo

# 步骤 0:检测 requirements.txt 是否比 venv 里最近一次装依赖时新,是就先装依赖。
# 这样日常重启不花时间,git pull 后哪怕忘了 install.sh deps,也会被自动救回来。
needs_deps() {
    local dir="$1"
    local req="$ROOT/$dir/requirements.txt"
    local stamp="$ROOT/$dir/.venv/.deps-stamp"
    [ ! -f "$stamp" ] && return 0      # 从没装过(或老版本没留戳)
    [ "$req" -nt "$stamp" ] && return 0 # requirements.txt 比上次装依赖新
    return 1
}

echo "0. 检测依赖变化"
if needs_deps backend || needs_deps frontend; then
    echo "   检测到 requirements.txt 有变化或首次运行,先更新依赖..."
    "$ROOT/install.sh" deps
else
    echo "   依赖无变化,跳过"
fi
echo

echo "1. 重新加载 systemd 配置"
sudo systemctl daemon-reload
echo

echo "2. 重启后端和前端"
sudo systemctl restart "$BACKEND_SERVICE" "$FRONTEND_SERVICE"
echo

echo "3. 服务状态"
sudo systemctl --no-pager --lines=0 status "$BACKEND_SERVICE" | sed -n '1,8p'
echo
sudo systemctl --no-pager --lines=0 status "$FRONTEND_SERVICE" | sed -n '1,8p'
echo

echo "4. 健康检查"
# systemctl restart 返回时,服务进程刚 fork,uvicorn/streamlit 的 socket 还没 listen,
# 直接 curl 会 connection refused。这里 retry 最多 20 秒,每秒一次。
backend_ok=0
for i in $(seq 1 20); do
    if curl -fsS --max-time 2 "http://127.0.0.1:${BACKEND_PORT}/health" >/dev/null 2>&1; then
        echo "后端 OK: http://127.0.0.1:${BACKEND_PORT}/health (启动 ${i}s)"
        backend_ok=1
        break
    fi
    sleep 1
done
if [ "$backend_ok" -eq 0 ]; then
    echo "后端 20s 内未通过健康检查,查看日志:"
    echo "  sudo journalctl -u $BACKEND_SERVICE -n 80 --no-pager"
fi

frontend_ok=0
for i in $(seq 1 20); do
    if curl -fsSI --max-time 2 "http://127.0.0.1:${FRONTEND_PORT}" >/dev/null 2>&1; then
        echo "前端 OK: http://${SERVER_IP}:${FRONTEND_PORT} (启动 ${i}s)"
        frontend_ok=1
        break
    fi
    sleep 1
done
if [ "$frontend_ok" -eq 0 ]; then
    echo "前端 20s 内未通过健康检查,查看日志:"
    echo "  sudo journalctl -u $FRONTEND_SERVICE -n 80 --no-pager"
fi
echo

echo "完成。浏览器访问:"
echo "  http://${SERVER_IP}:${FRONTEND_PORT}"
echo
echo "常用看日志命令:"
echo "  sudo journalctl -u $BACKEND_SERVICE -f"
echo "  sudo journalctl -u $FRONTEND_SERVICE -f"
