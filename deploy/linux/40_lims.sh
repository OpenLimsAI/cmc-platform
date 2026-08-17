#!/usr/bin/env bash
# LIMS 看板挂到门户 /lims：拉码、.env.local 改相对路径、next build、前后端只听本机
source "$(dirname "$0")/00_common.sh"
cd /home/prometheus/cmc-rd-lims-dashboard
log "拉取代码"; git pull -q; git log --oneline -1
log "前端 .env.local → 相对路径 /lims"; backup frontend/.env.local
printf '# 相对路径：经统一门户 nginx(5100)/lims/api → 后端 8030\nDEV_EXTRA_ORIGINS=\nNEXT_PUBLIC_API_BASE_URL=/lims\n' > frontend/.env.local
log "next build"; (cd frontend && pnpm install --frozen-lockfile >/dev/null && pnpm build 2>&1 | tail -3)
log "前端 5130 / 后端 8030 只听本机"; bind_localhost cmc-lims-frontend; bind_localhost cmc-lims-backend
restart_unit cmc-lims-backend; restart_unit cmc-lims-frontend
log "验证"; ss -ltnH | grep -E ':(5130|8030) ' | awk '{print "    listen", $4}'
check http://127.0.0.1:5100/lims; check http://127.0.0.1:5100/lims/api/v1/lims/stats/kpi; check http://127.0.0.1:5130/
