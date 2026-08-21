#!/usr/bin/env bash
# lcms-panel-explorer 挂到门户 /lcms/:拉码、重建前端、nginx 静态伺服(只听本机;后端 8005 由 systemd lcms-backend 托管)
source "$(dirname "$0")/00_common.sh"
cd /opt/lcms-panel-explorer
log "拉取代码"; git pull -q; git log --oneline -1
log "重建前端"; (cd frontend && npm ci --silent && LCMS_BASE=/lcms/ npm run build 2>&1 | tail -3)
grep -o "src=\"[^\"]*\"" frontend/dist/index.html | head -1
log "nginx:5105 静态伺服 /lcms/ + /lcms/api/ 转发(只听本机)"
CONF=/etc/nginx/conf.d/lcms-panel.conf; backup "$CONF"
sudo tee "$CONF" >/dev/null <<'NGX'
# 受管来源:cmab-hub/deploy/linux/05_lcms.sh(对齐 lcms-panel-explorer/docs/03-deploy-linux.md)
server {
    listen 127.0.0.1:5105;   # 只听本机:对外统一走 cmab-hub 5100
    server_name _;
    root /opt/lcms-panel-explorer/frontend/dist;
    index index.html;

    # 前端挂在统一门户 /lcms/ 子路径下(vite base:"/lcms/")
    location = /            { return 302 /lcms/; }
    location /lcms/api/     { proxy_pass http://127.0.0.1:8005/api/; }
    location /lcms/         { alias /opt/lcms-panel-explorer/frontend/dist/; try_files $uri $uri/ /lcms/index.html; }
    location /              { try_files $uri $uri/ /index.html; }
}
NGX
log "重载 nginx"; sudo nginx -t && sudo systemctl reload nginx
log "后端重启(代码可能更新)"; sudo systemctl restart lcms-backend; sleep 3
curl --noproxy "*" -s http://127.0.0.1:8005/healthz; echo
