#!/usr/bin/env bash
# LabOps 挂到门户 /labops/：拉码、重建前端、nginx 加 /labops/ 并只听本机（后端 8010 本已只听本机）
source "$(dirname "$0")/00_common.sh"
cd /opt/cmc-labops
log "拉取代码"; git pull -q; git log --oneline -1
log "重建前端"; (cd frontend-react && npm install --silent && npm run build 2>&1 | tail -3)
grep -o 'src="[^"]*"' frontend-react/dist/index.html | head -1
log "nginx：加 /labops/ 伺服 + /labops/api/ 转发 + 只听本机"
CONF=/etc/nginx/conf.d/cmc-labops.conf; backup "$CONF"
sudo tee "$CONF" >/dev/null <<'NGX'
# 受管来源：cmab-hub/deploy/linux/20_labops.sh（对齐 cmc-labops/DEPLOY.md §4b）
server {
    listen 127.0.0.1:5110;   # 只听本机：对外统一走 cmab-hub 5100
    server_name _;
    root /opt/cmc-labops/frontend-react/dist;
    index index.html;

    location /api/ {
        proxy_pass http://127.0.0.1:8010;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 60s;
    }
    # 前端挂在统一门户 /labops/ 子路径下（vite base:'/labops/'）
    location = /            { return 302 /labops/; }
    location /labops/api/   { proxy_pass http://127.0.0.1:8010/api/; }
    location /labops/       { alias /opt/cmc-labops/frontend-react/dist/; try_files $uri $uri/ /labops/index.html; }
    location /              { try_files $uri $uri/ /index.html; }
}
NGX
nginx_reload
log "验证"; ss -ltnH | grep -E ':(5110|8010) ' | awk '{print "    listen", $4}'
check http://127.0.0.1:5100/labops/; check http://127.0.0.1:5110/
