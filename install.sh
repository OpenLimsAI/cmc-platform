#!/usr/bin/env bash
# =============================================================================
# 文件: install.sh
# 用途: 一键在 Linux 服务器部署 CMC 物料管理系统
#       - 给 backend / frontend 各创建独立 venv 并安装依赖
#       - 把 systemd unit 装到 /etc/systemd/system/
#       - daemon-reload + enable --now
# 用法:
#   ./install.sh             首次安装 + 启动
#   ./install.sh restart     更新代码后重启服务(不重装 unit)
#   ./install.sh deps        只更新 venv 依赖,不动 systemd
#
# 假定:
#   - 项目克隆在 /opt/cmc-inventory(若改路径,sudo 步骤里需要同步改 unit 文件中 WorkingDirectory)
#   - 当前用户在 sudo 组(install / remove unit 需要 sudo)
#   - 系统有 python3 (>= 3.10);默认走 python3,可用 PYTHON 环境变量覆盖
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
}

case "$ACTION" in
    install)
        ensure_venv backend
        ensure_venv frontend

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
        echo
        echo "==> 完成。访问:"
        echo "    前端:   http://<服务器IP>:8501"
        echo "    后端:   http://<服务器IP>:8000/docs"
        echo "    日志:   sudo journalctl -u cmc-backend -f"
        ;;

    deps)
        ensure_venv backend
        ensure_venv frontend
        echo "==> 依赖已更新。需要重启请: ./install.sh restart"
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
