#!/usr/bin/env bash
# =============================================================================
# 文件: restart.sh
# 用途: Linux 服务器上一键重启 CMC 库存系统前后端
#
# 用法:
#   cd /opt/cmc-labops
#   ./restart.sh
#
# 如果提示 sudo 密码,输入 Linux 登录用户的密码即可。
# =============================================================================
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
ENV_FILE="$ROOT/.env"

BACKEND_SERVICE="${BACKEND_SERVICE:-cmc-backend}"
FRONTEND_SERVICE="${FRONTEND_SERVICE:-cmc-frontend}"
BACKEND_PORT="${BACKEND_PORT:-8010}"
FRONTEND_PORT="${FRONTEND_PORT:-5110}"
# 前端伺服模式:nginx(本生产实际,前端走 nginx 伺服 dist,本脚本不碰 cmc-frontend)
#              vite(无 nginx 主机,由 cmc-frontend.service 跑 vite preview)
# 覆盖:FRONTEND_MODE=vite ./restart.sh
FRONTEND_MODE="${FRONTEND_MODE:-nginx}"

if [ -f "$ENV_FILE" ]; then
    # .env 由 systemd EnvironmentFile 使用,格式是 KEY=VALUE。
    # 这里读取端口只是为了打印访问地址,真正启动参数仍由 systemd 读取。
    BACKEND_PORT="$(grep -E '^BACKEND_PORT=' "$ENV_FILE" | tail -1 | cut -d= -f2- || true)"
    FRONTEND_PORT="$(grep -E '^FRONTEND_PORT=' "$ENV_FILE" | tail -1 | cut -d= -f2- || true)"
    BACKEND_PORT="${BACKEND_PORT:-8010}"
    FRONTEND_PORT="${FRONTEND_PORT:-5110}"
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
if [ "$FRONTEND_MODE" = "vite" ]; then
    echo " 前端服务: $FRONTEND_SERVICE (vite 模式)"
else
    echo " 前端伺服: nginx(伺服 dist;本脚本只重建 dist,不重启 cmc-frontend)"
fi
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

# 前端(React):dist 不存在,或 src/package-lock.json 比上次构建新,就需要重新构建
needs_frontend_build() {
    local fr="$ROOT/frontend-react"
    local stamp="$fr/dist/.build-stamp"
    [ ! -f "$stamp" ] && return 0
    [ -n "$(find "$fr/src" "$fr/package-lock.json" "$fr/vite.config.ts" -newer "$stamp" -print -quit 2>/dev/null)" ] && return 0
    return 1
}

echo "0. 检测依赖/构建变化"
if needs_deps backend || needs_frontend_build; then
    echo "   检测到依赖或前端源码有变化,先更新依赖并重新构建..."
    "$ROOT/install.sh" deps
else
    echo "   无变化,跳过"
fi
echo

echo "1. 重新加载 systemd 配置"
sudo systemctl daemon-reload
echo

if [ "$FRONTEND_MODE" = "vite" ]; then
    echo "2. 重启后端和前端"
    sudo systemctl restart "$BACKEND_SERVICE" "$FRONTEND_SERVICE"
else
    echo "2. 重启后端(前端走 nginx,dist 已在步骤 0 重建,无需重启服务)"
    sudo systemctl restart "$BACKEND_SERVICE"
fi
echo

echo "3. 服务状态"
sudo systemctl --no-pager --lines=0 status "$BACKEND_SERVICE" | sed -n '1,8p'
if [ "$FRONTEND_MODE" = "vite" ]; then
    echo
    sudo systemctl --no-pager --lines=0 status "$FRONTEND_SERVICE" | sed -n '1,8p'
fi
echo

echo "4. 健康检查"
# systemctl restart 返回时,服务进程刚 fork,uvicorn 的 socket 还没 listen,
# 直接 curl 会 connection refused。这里 retry 最多 20 秒,每秒一次。
# 前端 5110:nginx 模式下打到 nginx,vite 模式下打到 cmc-frontend,两种都该通。
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
    if [ "$FRONTEND_MODE" = "vite" ]; then
        echo "  sudo journalctl -u $FRONTEND_SERVICE -n 80 --no-pager"
    else
        echo "  sudo nginx -t && sudo tail -n 80 /var/log/nginx/error.log"
    fi
fi
echo

echo "完成。浏览器访问:"
echo "  http://${SERVER_IP}:${FRONTEND_PORT}"
echo
echo "常用看日志命令:"
echo "  sudo journalctl -u $BACKEND_SERVICE -f"
if [ "$FRONTEND_MODE" = "vite" ]; then
    echo "  sudo journalctl -u $FRONTEND_SERVICE -f"
else
    echo "  sudo tail -f /var/log/nginx/access.log   # 前端访问日志(nginx)"
fi
