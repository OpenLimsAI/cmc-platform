#!/usr/bin/env bash
# =============================================================================
# 文件: install.sh
# 用途: 一键在 Linux 服务器部署 CMC LabOps Portal(原 CMC 物料管理系统)
#       - backend 创建 venv 安装依赖;frontend-react 执行 npm ci + npm run build
#       - 把 systemd unit 装到 /etc/systemd/system/
#       - daemon-reload + enable --now
# 用法:
#   ./install.sh             首次安装 + 启动
#   ./install.sh restart     更新代码后重启服务(不重装 unit)
#   ./install.sh deps        只更新 venv 依赖,不动 systemd
#
# 假定:
#   - 项目克隆在 /opt/cmc-labops(若改路径,sudo 步骤里需要同步改 unit 文件中 WorkingDirectory)
#   - 当前用户在 sudo 组(install / remove unit 需要 sudo)
#   - 系统有 python3 (>= 3.10);默认走 python3,可用 PYTHON 环境变量覆盖
#   - 系统有 Node.js 20+ 与 npm(React 前端构建与 vite preview 伺服)
#   - 服务器可访问 MDM Portal 后端(登录认证与主数据引用依赖它,地址在 .env 的 MDM_BASE_URL)
# =============================================================================
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
PYTHON="${PYTHON:-python3}"
ACTION="${1:-install}"

cd "$ROOT"

ensure_venv() {
    local dir="$1"
    cd "$ROOT/$dir"
    if [ ! -d .venv ]; then
        echo "==> 创建 $dir/.venv"
        $PYTHON -m venv .venv
    fi
    echo "==> 安装/升级 $dir 依赖"
    .venv/bin/pip install --upgrade pip --quiet
    .venv/bin/pip install -r requirements.txt --quiet
    # 留个时间戳,restart.sh 比对 requirements.txt 和它来判断是否需要重新装依赖
    touch .venv/.deps-stamp
}

build_frontend() {
    cd "$ROOT/frontend-react"
    echo "==> 安装前端依赖(npm ci)"
    npm ci --silent
    echo "==> 构建前端(npm run build)"
    npm run build
    # 时间戳供 restart.sh 判断是否需要重新构建
    touch dist/.build-stamp
}

case "$ACTION" in
    install)
        ensure_venv backend
        build_frontend

        if [ ! -f "$ROOT/.env" ]; then
            echo "==> 复制 .env.example -> .env (请检查并按需修改密码)"
            cp "$ROOT/.env.example" "$ROOT/.env"
        fi

        echo "==> 安装 systemd unit 文件(需要 sudo)"
        sudo cp "$ROOT/systemd/cmc-backend.service"  /etc/systemd/system/
        sudo cp "$ROOT/systemd/cmc-frontend.service" /etc/systemd/system/
        sudo systemctl daemon-reload
        sudo systemctl enable --now cmc-backend cmc-frontend

        echo
        echo "==> 服务状态(摘要)"
        sudo systemctl --no-pager status cmc-backend  | head -10
        echo
        sudo systemctl --no-pager status cmc-frontend | head -10
        # 从 .env 读出实际端口,避免与硬编码不一致
        FE_PORT="$(grep -E '^FRONTEND_PORT=' "$ROOT/.env" 2>/dev/null | cut -d= -f2)"
        BE_PORT="$(grep -E '^BACKEND_PORT='  "$ROOT/.env" 2>/dev/null | cut -d= -f2)"
        FE_PORT="${FE_PORT:-5110}"
        BE_PORT="${BE_PORT:-8010}"

        echo
        echo "==> 完成。访问:"
        echo "    前端:   http://<服务器IP>:${FE_PORT}"
        echo "    后端:   http://127.0.0.1:${BE_PORT}/health  (仅服务器本机)"
        echo "    Swagger: 需要 SSH 隧道后访问 http://localhost:${BE_PORT}/docs"
        echo "    日志:   sudo journalctl -u cmc-backend -f"
        ;;

    deps)
        ensure_venv backend
        build_frontend
        echo "==> 依赖已更新。需要重启请: ./restart.sh"
        ;;

    restart)
        echo "==> 重启服务(需要 sudo)"
        sudo systemctl restart cmc-backend cmc-frontend
        sudo systemctl --no-pager status cmc-backend  | head -5
        echo
        sudo systemctl --no-pager status cmc-frontend | head -5
        ;;

    uninstall)
        echo "==> 卸载 systemd unit(数据库不动)"
        sudo systemctl disable --now cmc-backend cmc-frontend || true
        sudo rm -f /etc/systemd/system/cmc-backend.service \
                   /etc/systemd/system/cmc-frontend.service
        sudo systemctl daemon-reload
        echo "==> 完成。venv / .env / 代码 仍保留;如需彻底清理,手动 rm。"
        ;;

    *)
        echo "用法: $0 [install|restart|deps|uninstall]"
        exit 1
        ;;
esac
