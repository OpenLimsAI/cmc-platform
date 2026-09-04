#!/usr/bin/env bash
# 门户自身前端更新：拉码 + 重建 frontend/dist（nginx 直接伺服，静态包立即生效；改了 nginx/*.conf 才需要 restart nginx）
source "$(dirname "$0")/00_common.sh"
cd /opt/cmab-hub
log "拉取代码"; git pull -q; git log --oneline -1
log "重建门户前端"; (cd frontend && pnpm install --frozen-lockfile >/dev/null && pnpm build 2>&1 | tail -3)
grep -o 'src="[^"]*"' frontend/dist/index.html | head -1
log "验证"; check http://127.0.0.1:5100/; check http://127.0.0.1:5100/mdm/api/v1/health
