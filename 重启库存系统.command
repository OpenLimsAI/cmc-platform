#!/usr/bin/env bash
# 双击此文件即可重启 CMC 库存系统的本机开发服务。
# 后端: FastAPI / uvicorn, 固定 http://127.0.0.1:8010(本项目编号 10,见 ~/code/PORTS.md)
# 前端: React / Vite,   固定 http://localhost:5110
# 注意:登录依赖 MDM Portal(Docker, :18000),请确保它已启动。

set -u

ROOT="$(cd "$(dirname "$0")" && pwd)"
BACKEND_DIR="$ROOT/backend"
FRONTEND_DIR="$ROOT/frontend-react"
LOG_DIR="$ROOT/logs"

BACKEND_PORT="${BACKEND_PORT:-8010}"
FRONTEND_PORT="${FRONTEND_PORT:-5110}"
BACKEND_HOST="${BACKEND_HOST:-127.0.0.1}"
# Vite 绑定 localhost(含 IPv6),浏览器请用 localhost 访问
FRONTEND_HOST="${FRONTEND_HOST:-localhost}"

if [ -f "$ROOT/.env" ]; then
    set -a
    # shellcheck disable=SC1091
    source "$ROOT/.env"
    set +a
    BACKEND_PORT="${BACKEND_PORT:-8010}"
    FRONTEND_PORT="${FRONTEND_PORT:-5110}"
fi

BACKEND_URL="http://${BACKEND_HOST}:${BACKEND_PORT}"
FRONTEND_URL="http://${FRONTEND_HOST}:${FRONTEND_PORT}"

cd "$ROOT" || exit 1
mkdir -p "$LOG_DIR"

echo "============================================================"
echo " CMC 库存系统 - 一键重启"
echo " 项目目录: $ROOT"
echo " 后端地址: $BACKEND_URL"
echo " 前端地址: $FRONTEND_URL"
echo "============================================================"
echo

if [ ! -x "$BACKEND_DIR/.venv/bin/uvicorn" ]; then
    echo "找不到后端启动程序: $BACKEND_DIR/.venv/bin/uvicorn"
    echo "请先在项目根目录执行: ./install.sh deps"
    read -r -p "按回车退出..."
    exit 1
fi

if [ ! -d "$FRONTEND_DIR/node_modules" ]; then
    echo "找不到前端依赖: $FRONTEND_DIR/node_modules"
    echo "请先执行: (cd \"$FRONTEND_DIR\" && npm install)"
    read -r -p "按回车退出..."
    exit 1
fi

NPM_BIN="$(command -v npm || true)"
if [ -z "$NPM_BIN" ]; then
    echo "找不到 npm,请确认已安装 Node.js"
    read -r -p "按回车退出..."
    exit 1
fi

stop_port() {
    local port="$1"
    local name="$2"
    local pids

    pids="$(lsof -tiTCP:"$port" -sTCP:LISTEN 2>/dev/null || true)"
    if [ -z "$pids" ]; then
        echo "$name: 端口 $port 没有正在监听的旧进程"
        return
    fi

    echo "$name: 停止端口 $port 上的旧进程: $pids"
    kill $pids 2>/dev/null || true
    sleep 1

    pids="$(lsof -tiTCP:"$port" -sTCP:LISTEN 2>/dev/null || true)"
    if [ -n "$pids" ]; then
        echo "$name: 旧进程未退出,强制停止: $pids"
        kill -9 $pids 2>/dev/null || true
        sleep 1
    fi
}

wait_for_url() {
    local url="$1"
    local name="$2"
    local i

    for i in $(seq 1 30); do
        # --noproxy:绕过本机 SOCKS 代理(7890),localhost 直连
        if curl -fsS --noproxy '*' "$url" >/dev/null 2>&1; then
            echo "$name: 已启动"
            return 0
        fi
        sleep 1
    done

    echo "$name: 30 秒内没有响应,请查看日志"
    return 1
}

echo "1. 停止旧服务"
stop_port "$FRONTEND_PORT" "前端"
stop_port "$BACKEND_PORT" "后端"
echo

echo "2. 启动后端"
(
    cd "$BACKEND_DIR" || exit 1
    nohup .venv/bin/uvicorn main:app \
        --host "$BACKEND_HOST" \
        --port "$BACKEND_PORT" \
        > "$LOG_DIR/backend.log" 2>&1 &
)
echo "后端日志: $LOG_DIR/backend.log"
echo

echo "3. 启动前端 (React / Vite)"
(
    cd "$FRONTEND_DIR" || exit 1
    nohup "$NPM_BIN" run dev -- \
        --port "$FRONTEND_PORT" \
        --strictPort \
        > "$LOG_DIR/frontend.log" 2>&1 &
)
echo "前端日志: $LOG_DIR/frontend.log"
echo

echo "4. 等待服务响应"
wait_for_url "$BACKEND_URL/health" "后端"
wait_for_url "$FRONTEND_URL" "前端"
echo

echo "5. 打开浏览器"
open "$FRONTEND_URL"
echo
echo "完成。浏览器地址: $FRONTEND_URL"
echo "如果页面没有刷新,请在浏览器里手动按 Command+R。"
echo
read -r -p "按回车关闭这个窗口..."
