#!/usr/bin/env bash
# 一键更新脚本：在 Linux 服务器上跑，把最新代码部署上线。
# 用法：cd /opt/cmc-rd-usp-dashboard && ./deploy.sh
# 做的事：拉代码 → 装后端依赖 → 编译前端 → 重启 systemd 服务 → 健康检查
set -euo pipefail

# 切到脚本所在目录（= 项目根），这样在哪儿运行都行
cd "$(dirname "$0")"
# 2026-08-17 起前后端只听 127.0.0.1，对外统一走门户 cmab-hub（5100）的 /usp 路径
HOST=172.19.0.105
PORTAL="http://${HOST}:5100/usp"

# uv 装在 ~/.local/bin，非登录 shell 可能不在 PATH 里，补一下
command -v uv >/dev/null 2>&1 || export PATH="$HOME/.local/bin:$PATH"

echo "==> 1/5 拉取最新代码 (git pull)"
git pull --ff-only

echo "==> 2/5 后端依赖 (uv sync)"
( cd backend && uv sync )

echo "==> 3/5 编译前端 (npm ci + build)"
( cd frontend && npm ci && npm run build )

echo "==> 4/5 重启服务"
sudo systemctl restart cmc-usp-backend cmc-usp-frontend

echo "==> 5/5 健康检查"
ok=1
for i in $(seq 1 20); do
  curl -s --noproxy '*' -m 2 "http://127.0.0.1:8070/health" >/dev/null 2>&1 \
    && curl -s --noproxy '*' -m 5 -o /dev/null "http://127.0.0.1:5170/usp" >/dev/null 2>&1 && { ok=0; break; }
  sleep 1
done

back=$(systemctl is-active cmc-usp-backend || true)
front=$(systemctl is-active cmc-usp-frontend || true)
# 后端已开鉴权（AUTH_REQUIRED=true），数据接口不带令牌会 401，这里只看健康接口
health=$(curl -s --noproxy '*' -m 5 "http://127.0.0.1:8070/health" || true)

echo "-----------------------------------------"
echo "后端 cmc-usp-backend : ${back}  (8070)"
echo "前端 cmc-usp-frontend: ${front}  (5170)"
echo "后端健康接口          : ${health}"
if [ "$ok" -eq 0 ] && [ "$back" = "active" ] && [ "$front" = "active" ]; then
  echo "✅ 部署完成，访问 ${PORTAL}"
else
  echo "⚠️  有服务没起来，看日志：journalctl -u cmc-usp-backend -u cmc-usp-frontend -n 50 --no-pager"
  exit 1
fi
