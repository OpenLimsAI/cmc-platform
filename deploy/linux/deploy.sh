#!/usr/bin/env bash
# 在 Linux /opt/cmc-quality-analytics-platform 内执行。数据库仅使用已有只读凭据，不创建或迁移表。
set -euo pipefail
export PATH="$HOME/.local/bin:$PATH"

DIR=/opt/cmc-quality-analytics-platform
ENV_FILE="$DIR/backend/.env"
log() { printf '\n\033[1;34m==> %s\033[0m\n' "$*"; }
fail() { echo "！$*"; exit 1; }

[ -d "$DIR/.git" ] || fail "缺少 $DIR Git 仓库，请先由 cmab-hub 的 45_qap.sh 克隆"
cd "$DIR"
log "拉取代码"; git pull --ff-only; git log --oneline -1

[ -f "$ENV_FILE" ] || fail "缺少 backend/.env；请先配置 cmc_analytics 只读数据库账号"
grep -Eq '^QAP_DB_PASSWORD=.+$' "$ENV_FILE" || fail "backend/.env 未配置 QAP_DB_PASSWORD"
grep -q '^QAP_DB_PASSWORD=__set_me__$' "$ENV_FILE" && fail "QAP_DB_PASSWORD 仍为模板占位值"

# 正式环境必须强制 MDM 登录；已有键就替换，避免同一变量重复定义。
set_env() {
  local key="$1" value="$2"
  if grep -q "^${key}=" "$ENV_FILE"; then
    sed -i "s|^${key}=.*|${key}=${value}|" "$ENV_FILE"
  else
    printf '%s=%s\n' "$key" "$value" >> "$ENV_FILE"
  fi
}
set_env QAP_ENVIRONMENT production
set_env QAP_AUTH_REQUIRED true
set_env QAP_JWT_ALGORITHM HS256
set_env QAP_READ_ROLES '["QAP_QC_GENERAL","QAP_QA_RELEASE"]'
set_env QAP_IMPORT_PREVIEW_ROLES '["QAP_QC_GENERAL"]'

if ! grep -Eq '^QAP_JWT_SECRET_KEY=.+$' "$ENV_FILE"; then
  MDM_ENV=""
  for candidate in /opt/cmab-mdm-platform/.env /opt/cmab-mdm-platform/backend/.env; do
    [ -f "$candidate" ] && MDM_ENV="$candidate" && break
  done
  [ -n "$MDM_ENV" ] || fail "找不到 MDM .env，无法配置令牌验签"
  secret_line=$(grep '^SECRET_KEY=' "$MDM_ENV" | head -1 || true)
  [ -n "$secret_line" ] || fail "MDM .env 中没有 SECRET_KEY"
  sed -i '/^QAP_JWT_SECRET_KEY=/d' "$ENV_FILE"
  printf '%s\n' "${secret_line/SECRET_KEY=/QAP_JWT_SECRET_KEY=}" >> "$ENV_FILE"
fi
chmod 600 "$ENV_FILE"

log "安装锁定依赖并构建前端"
(cd backend && uv sync --locked --quiet)
(cd frontend && pnpm install --frozen-lockfile >/dev/null && pnpm build)

log "安装并重启后端服务"
sudo cp deploy/linux/qap-backend.service /etc/systemd/system/qap-backend.service
sudo systemctl daemon-reload
sudo systemctl enable -q qap-backend
sudo systemctl restart qap-backend

log "安装本机静态前端"
sudo cp deploy/linux/qap-platform.nginx.conf /etc/nginx/conf.d/qap-platform.conf
sudo nginx -t
sudo systemctl reload nginx
sleep 3

health=$(curl --noproxy '*' -sS -o /dev/null -w '%{http_code}' http://127.0.0.1:8040/health)
unauth=$(curl --noproxy '*' -sS -o /dev/null -w '%{http_code}' http://127.0.0.1:8040/api/v1/meta/projects)
frontend=$(curl --noproxy '*' -sS -o /dev/null -w '%{http_code}' http://127.0.0.1:5140/qap/)
[ "$health" = 200 ] || fail "后端健康检查返回 $health"
[ "$unauth" = 401 ] || fail "鉴权自检失败：无令牌业务接口返回 $unauth，应为 401"
[ "$frontend" = 200 ] || fail "前端返回 $frontend"
echo "QAP 本机服务就绪：health=$health，unauthenticated=$unauth，frontend=$frontend"
