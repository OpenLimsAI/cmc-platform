#!/usr/bin/env bash
# 把 deploy/systemd/ 下的受管副本装到 Linux 并生效（幂等，可反复跑）。
#   - cmab-backend.service      后端（带 --proxy-headers，见文件内注释）
#   - cmab-mdm-backup.service   每日备份任务
#   - cmab-mdm-backup.timer     每天 02:00 触发
# 用法：ssh 到 Linux 后 `bash /opt/cmab-mdm-platform/deploy/linux/install_systemd.sh`
set -euo pipefail
REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$REPO"

for f in cmab-backend.service cmab-mdm-backup.service cmab-mdm-backup.timer; do
    src="deploy/systemd/$f"; dst="/etc/systemd/system/$f"
    if [[ -f "$dst" ]] && ! diff -q "$src" "$dst" >/dev/null; then
        sudo cp -a "$dst" "${dst}.bak-$(date +%Y%m%d-%H%M%S)"
        echo "  已备份原 $f"
    fi
    sudo cp "$src" "$dst"
    echo "✓ 安装 $f"
done

sudo systemctl daemon-reload
sudo systemctl restart cmab-backend
sudo systemctl enable --now cmab-mdm-backup.timer
echo
echo "后端: $(systemctl is-active cmab-backend)"
systemctl list-timers cmab-mdm-backup.timer --no-pager | head -3
