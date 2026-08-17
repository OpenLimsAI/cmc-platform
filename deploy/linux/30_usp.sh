#!/usr/bin/env bash
# 上游看板挂到门户 /usp：拉码、.env.local 改相对路径、next build、前后端只听本机
source "$(dirname "$0")/00_common.sh"
cd /opt/cmc-rd-usp-dashboard
log "拉取代码"; git pull -q; git log --oneline -1
log "前端 .env.local → 相对路径 /usp"; backup frontend/.env.local
printf '# 相对路径：经统一门户 nginx(5100)/usp/api → 后端 8070\nNEXT_PUBLIC_API_BASE=/usp\n' > frontend/.env.local
log "next build"; (cd frontend && npm install --silent && npm run build 2>&1 | tail -3)
log "前端 5170 / 后端 8070 只听本机"; bind_localhost cmc-usp-frontend; bind_localhost cmc-usp-backend
restart_unit cmc-usp-backend; restart_unit cmc-usp-frontend
log "验证"; ss -ltnH | grep -E ':(5170|8070) ' | awk '{print "    listen", $4}'
check http://127.0.0.1:5100/usp; check http://127.0.0.1:5100/usp/api/auth/me; check http://127.0.0.1:5170/
