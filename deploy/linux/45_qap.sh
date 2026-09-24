#!/usr/bin/env bash
# QAP 挂到门户 /qap/：部署只读后端与静态前端，端口只听 Linux 本机。
source "$(dirname "$0")/00_common.sh"

DIR=/opt/cmc-quality-analytics-platform
REPO_URL="${REPO_URL:-git@github.com:qingcheng81/cmc-quality-analytics-platform.git}"
if [ ! -d "$DIR/.git" ]; then
  log "首次克隆 QAP"
  sudo mkdir -p "$DIR"
  sudo chown prometheus:prometheus "$DIR"
  git clone "$REPO_URL" "$DIR"
fi

log "部署 QAP"
bash "$DIR/deploy/linux/deploy.sh"

# hub-locations.conf 已随本仓库更新；使 /qap/ 入口生效。
log "重载 Hub nginx"
nginx_reload

log "验证 Hub 单一入口"
check http://127.0.0.1:5100/qap/
check http://127.0.0.1:5100/qap/health
code=$(curl --noproxy '*' -sS -o /dev/null -w '%{http_code}' http://127.0.0.1:5100/qap/api/v1/meta/projects)
[ "$code" = 401 ] && ok "Hub 下无令牌业务接口返回 401" || { echo "鉴权自检失败：返回 $code，应为 401"; exit 1; }
