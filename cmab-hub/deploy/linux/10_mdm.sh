#!/usr/bin/env bash
# MDM 挂到门户 /mdm/：拉码、重建前端、nginx 换受管配置并只听本机、后端只听本机
source "$(dirname "$0")/00_common.sh"
cd /opt/cmab-mdm-platform
log "拉取代码"; git pull -q; git log --oneline -1
log "重建前端"; (cd frontend && pnpm install --frozen-lockfile >/dev/null && pnpm build 2>&1 | tail -3)
grep -o 'src="[^"]*"' frontend/dist/index.html | head -1
log "nginx：换成仓库受管副本 + 只听本机"
backup /etc/nginx/conf.d/cmab-mdm.conf
sudo cp deploy/nginx/linux-host/cmab-mdm.conf /etc/nginx/conf.d/cmab-mdm.conf
sudo sed -i 's/listen 15173 default_server;/listen 127.0.0.1:15173 default_server;  # 只听本机：对外统一走 cmab-hub 5100/' /etc/nginx/conf.d/cmab-mdm.conf
nginx_reload
log "后端 18000 只听本机"; bind_localhost cmab-backend; restart_unit cmab-backend
log "验证"; ss -ltnH | grep -E ':(15173|18000) ' | awk '{print "    listen", $4}'
check http://127.0.0.1:5100/mdm/; check http://127.0.0.1:5100/mdm/api/v1/health; check http://127.0.0.1:15173/
