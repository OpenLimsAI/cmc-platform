#!/usr/bin/env bash
# 门户自身前端更新：拉码 + 重建 frontend/dist（nginx 直接伺服，静态包立即生效；改了 nginx/*.conf 才需要 restart nginx）
source "$(dirname "$0")/00_common.sh"
cd /opt/cmab-hub
log "拉取代码"; git pull -q; git log --oneline -1
log "重建门户前端"; (cd frontend && pnpm install --frozen-lockfile >/dev/null && pnpm build 2>&1 | tail -3)
grep -o 'src="[^"]*"' frontend/dist/index.html | head -1 || true   # 同上：别让 SIGPIPE 掐断脚本
# nginx 配置（压缩 / 安全响应头 / 子系统路由表）也在仓库里，pull 下来要重载才生效。
# 用 reload 不用 restart：listen 没变，reload 不断连接；restart 反而会闪断。
log "重载 nginx（配置随代码更新）"; sudo nginx -t && sudo systemctl reload nginx

log "验证"; check http://127.0.0.1:5100/; check http://127.0.0.1:5100/mdm/api/v1/health

# 压缩自检：门户主脚本带 Accept-Encoding 请求必须回 gzip，否则用户白下几倍体积（2026-09-11）
# ⚠️ 00_common.sh 是 set -euo pipefail：grep | head 里 grep 会被 SIGPIPE 打断(141)，
# pipefail 让整条管道算失败，脚本会在这里**静默退出**（2026-09-11 实测踩到）。补 || true。
js=$(grep -o '/assets/[^"]*\.js' frontend/dist/index.html | head -1 || true)
if [ -n "$js" ]; then
  enc=$(curl -s --noproxy '*' -I -H 'Accept-Encoding: gzip' "http://127.0.0.1:5100$js" | grep -i '^content-encoding' | tr -d '\r')
  [ -n "$enc" ] && echo "压缩自检 OK（$enc）" || echo "！压缩自检失败：主脚本没有被压缩，检查 nginx/compression.conf 是否被 include"
fi
