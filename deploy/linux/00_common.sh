#!/usr/bin/env bash
# 各子系统部署脚本共用函数（在 Linux 172.19.0.105 上以 prometheus 运行，已配免密 sudo）
set -euo pipefail
STAMP=$(date +%Y%m%d-%H%M%S)

log()  { printf '\n\033[1;34m==> %s\033[0m\n' "$*"; }
ok()   { printf '\033[1;32m    ✓ %s\033[0m\n' "$*"; }

# 备份后就地替换文件（sudo）
backup() { sudo cp -a "$1" "$1.bak-$STAMP"; ok "已备份 $1 → $1.bak-$STAMP"; }

# 把 systemd 单元里 uvicorn/next 的监听地址从 0.0.0.0 改成 127.0.0.1（对外统一走 cmab-hub 5100）
bind_localhost() {  # $1 = unit 名
  local unit="$1" path
  path=$(systemctl show -p FragmentPath --value "$unit")
  [ -n "$path" ] || { echo "找不到 unit $unit"; exit 1; }
  if grep -qE -- '--host 0\.0\.0\.0|-H 0\.0\.0\.0' "$path"; then
    backup "$path"
    sudo sed -i -E 's/--host 0\.0\.0\.0/--host 127.0.0.1/; s/-H 0\.0\.0\.0/-H 127.0.0.1/' "$path"
    ok "$unit 改为只听本机: $(grep -E '^ExecStart' "$path")"
    sudo systemctl daemon-reload
  else
    ok "$unit 已是只听本机，跳过"
  fi
}

restart_unit() { sudo systemctl restart "$1"; sleep 3; systemctl is-active --quiet "$1" && ok "$1 已重启并运行" || { echo "$1 启动失败"; sudo journalctl -u "$1" -n 20 --no-pager; exit 1; }; }

nginx_reload() { sudo nginx -t && sudo systemctl reload nginx && ok "nginx 已重载"; }

check() { printf '    %-52s → %s\n' "$1" "$(curl -s -o /dev/null -w '%{http_code} %{redirect_url}' "$1")"; }
