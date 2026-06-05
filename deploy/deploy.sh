#!/usr/bin/env bash
# ============================================================
# CMAB MDM Portal — Linux 部署/更新脚本
#
# 适用：Linux 原生部署形态（与 Mac 的 docker 不同）：
#   - 前端：nginx 服务静态构建产物 frontend/dist（端口 15173）
#   - 后端：systemd 单元 cmab-backend.service 跑 uvicorn（端口 18000）
#   - PostgreSQL / Redis / nginx：均由 systemd 托管（开机自启）
#
# 一条命令完成：拉代码 → 迁移库 → 构建前端 → 经 systemd 重启后端 → 健康检查。
# 重启后端用到 sudo（systemctl），运行时会提示输入密码。
#
# 用法：  bash deploy/deploy.sh
# ============================================================
set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PORT=18000
SVC=cmab-backend
HEALTH="http://127.0.0.1:${PORT}/health"

cd "$REPO"
echo "仓库: $REPO"

echo "▶ 1/5 拉取最新代码 (git pull --ff-only)"
git pull --ff-only origin main

echo "▶ 2/5 数据库迁移 (alembic upgrade head)"
( cd backend && .venv/bin/alembic upgrade head )

echo "▶ 3/5 构建前端静态产物 (nginx 直接服务 dist)"
( cd frontend && pnpm install --prefer-offline && pnpm build )

echo "▶ 4/5 经 systemd 重启后端 (开机自启 + 崩溃自恢复都由它保证)"
# 清掉可能残留的手动(非 systemd)进程, 释放 18000, 避免 systemd 启动时端口占用
fuser -k "${PORT}/tcp" 2>/dev/null || true
sleep 2
sudo systemctl restart "$SVC"

echo "▶ 5/5 健康检查"
ok=0
for _ in $(seq 1 20); do
  code=$(curl -s --noproxy '*' -o /dev/null -w '%{http_code}' "$HEALTH" || true)
  if [ "$code" = "200" ]; then ok=1; break; fi
  sleep 1
done
if [ "$ok" = "1" ]; then
  echo "✓ 部署完成，后端健康（$HEALTH）"
  if systemctl is-active "$SVC" >/dev/null 2>&1; then
    echo "✓ 后端已由 systemd 托管（开机自启 + 崩溃自恢复生效）"
  else
    echo "⚠ 后端健康但 systemd 显示未 active，请检查：systemctl status $SVC"
  fi
  echo "提示：浏览器硬刷新（Ctrl+F5）以加载新前端产物"
else
  echo "✗ 健康检查失败。查看日志：sudo journalctl -u $SVC -n 50"
  exit 1
fi
