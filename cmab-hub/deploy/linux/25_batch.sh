#!/usr/bin/env bash
# 批号管理 rd-batch-registry 挂到门户 /batch/：拉码、重建前端、nginx 加 /batch/ 并只听本机（后端 8080 本已只听本机）
source "$(dirname "$0")/00_common.sh"
cd /opt/rd-batch-registry
log "拉取代码"; git pull -q; git log --oneline -1
# 批号前端用 npm（仓库只有 package-lock.json，没有 pnpm-lock.yaml，用 pnpm --frozen-lockfile 会报 ERR_PNPM_NO_LOCKFILE）
log "重建前端"; (cd frontend && npm ci --silent && npm run build 2>&1 | tail -3)
grep -o 'src="[^"]*"' frontend/dist/index.html | head -1
log "nginx：加 /batch/ 伺服 + /batch/api/ 转发 + 只听本机"
CONF=/etc/nginx/conf.d/rd-batch-registry.conf; backup "$CONF"
sudo tee "$CONF" >/dev/null <<'NGX'
# 受管来源：cmab-hub/deploy/linux/25_batch.sh
server {
    listen 127.0.0.1:5180;   # 只听本机：对外统一走 cmab-hub 5100
    server_name _;
    root /opt/rd-batch-registry/frontend/dist;
    index index.html;

    location /api/ {
        proxy_pass http://127.0.0.1:8080;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 60s;
    }
    # 前端挂在统一门户 /batch/ 子路径下（vite base:'/batch/'）
    location = /            { return 302 /batch/; }
    location /batch/api/    { proxy_pass http://127.0.0.1:8080/api/; }
    # index.html 不缓存：普通 F5 就拿到新版（资源文件名带哈希，可长期缓存）；SPA 回落/目录 index 都内部跳到这里
    location = /batch/index.html {
        alias /opt/rd-batch-registry/frontend/dist/index.html;
        add_header Cache-Control "no-cache, no-store, must-revalidate";
        add_header Pragma "no-cache";
    }
    location /batch/assets/ { alias /opt/rd-batch-registry/frontend/dist/assets/; add_header Cache-Control "public, max-age=31536000, immutable"; }
    location /batch/        { alias /opt/rd-batch-registry/frontend/dist/; try_files $uri $uri/ /batch/index.html; }
    location /              { try_files $uri $uri/ /index.html; }
}
NGX
nginx_reload
log "验证"; ss -ltnH | grep -E ':(5180|8080) ' | awk '{print "    listen", $4}'
check http://127.0.0.1:5100/batch/; check http://127.0.0.1:5100/batch/api/v1/dashboard/summary; check http://127.0.0.1:5180/
