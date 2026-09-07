#!/usr/bin/env bash
# 批号管理【培训环境】rd-batch-registry-training 挂到门户 /batch-train/（编号 85：后端 8085 / 前端 5185）
# 同一仓库、同一代码，独立库 cmc_analytics_training；前端用 build:training（浅黄底+横幅+base /batch-train/）。
# 首次安装：先手工完成 ①建库拷数据 ②/opt 目录 clone + .env ③systemd 单元（见 rd-batch-registry/docs/培训环境.md），
# 之后每次更新只跑本脚本：拉码 → 重建前端 → 重启后端 → nginx。
source "$(dirname "$0")/00_common.sh"
cd /opt/rd-batch-registry-training
log "拉取代码"; git pull -q; git log --oneline -1
log "后端依赖同步 + 重启（8085）"
(cd backend && ~/.local/bin/uv sync --frozen -q)
restart_unit rd-batch-registry-training-backend.service
log "重建前端（培训包 --mode training）"; (cd frontend && npm ci --silent && npm run build:training 2>&1 | tail -3)
grep -o 'src="[^"]*"' frontend/dist/index.html | head -1
log "nginx：/batch-train/ 伺服 + api 转发 + 只听本机 5185"
CONF=/etc/nginx/conf.d/rd-batch-registry-training.conf; [ -f "$CONF" ] && backup "$CONF"
sudo tee "$CONF" >/dev/null <<'NGX'
# 受管来源：cmab-hub/deploy/linux/26_batch_train.sh（批号管理培训环境）
server {
    listen 127.0.0.1:5185;   # 只听本机：对外统一走 cmab-hub 5100/batch-train/
    server_name _;
    root /opt/rd-batch-registry-training/frontend/dist;
    index index.html;

    location /api/ {
        proxy_pass http://127.0.0.1:8085;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 60s;
    }
    location = /                  { return 302 /batch-train/; }
    location /batch-train/api/    { proxy_pass http://127.0.0.1:8085/api/; }
    # index.html 不缓存：普通 F5 就拿到新版（资源文件名带哈希，可长期缓存）；SPA 回落/目录 index 都内部跳到这里
    location = /batch-train/index.html {
        alias /opt/rd-batch-registry-training/frontend/dist/index.html;
        add_header Cache-Control "no-cache, no-store, must-revalidate";
        add_header Pragma "no-cache";
    }
    location /batch-train/assets/ { alias /opt/rd-batch-registry-training/frontend/dist/assets/; add_header Cache-Control "public, max-age=31536000, immutable"; }
    location /batch-train/        { alias /opt/rd-batch-registry-training/frontend/dist/; try_files $uri $uri/ /batch-train/index.html; }
    location /                    { try_files $uri $uri/ /index.html; }
}
NGX
nginx_reload
log "验证"; ss -ltnH | grep -E ':(5185|8085) ' | awk '{print "    listen", $4}'
check http://127.0.0.1:5100/batch-train/; check http://127.0.0.1:5100/batch-train/api/v1/dashboard/summary
