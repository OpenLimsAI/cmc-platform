#!/bin/bash
# Execute only after Git publication and Linux release authorization.
set -euo pipefail
expected_sha="${1:?必须指定已发布的完整40位提交SHA}"
root=/opt/cmc-water-system-dashboard
cd "$root"
bash deploy/linux/prepare.sh "$expected_sha"
mkdir -p logs/matplotlib
# Import settings without printing any connection or verification credentials.
(cd backend && .venv/bin/python - <<'PY'
from pathlib import Path
from app.core import settings
if settings.app_env == 'mac_dev':
    raise SystemExit('Linux APP_ENV 不可使用 mac_dev')
if not Path(settings.png_font_path).is_file():
    raise SystemExit('缺少已配置的中文字体，请先配置 PNG_FONT_PATH')
print('环境及字体路径检查通过；这不替代数据、业务角色及中文渲染验收')
PY
)
# Hub is maintained in its own repository; do not overwrite it from this script.
if ! curl --noproxy '*' --fail --silent --max-time 5 http://127.0.0.1:5100/mdm/api/v1/health >/dev/null; then
    echo 'MDM 健康检查未通过。请核对本机端口/接口，脚本未安装服务。' >&2
    exit 1
fi
backup_dir="$root/logs/deploy-$(date +%Y%m%d-%H%M%S)"
mkdir -p "$backup_dir"
for file in /etc/systemd/system/water-backend.service /etc/nginx/conf.d/water.conf; do
    if sudo test -f "$file"; then sudo cp -p "$file" "$backup_dir/"; fi
done
sudo install -m 0644 deploy/linux/water-backend.service /etc/systemd/system/water-backend.service
sudo install -m 0644 deploy/linux/water.conf /etc/nginx/conf.d/water.conf
if ! sudo nginx -t; then
    for file in /etc/systemd/system/water-backend.service /etc/nginx/conf.d/water.conf; do
        name="$(basename "$file")"
        if sudo test -f "$backup_dir/$name"; then sudo cp -p "$backup_dir/$name" "$file"; else sudo rm -f "$file"; fi
    done
    echo "nginx配置检查失败；已恢复本脚本改动的配置，未重载nginx；备份：$backup_dir" >&2
    exit 1
fi
sudo systemctl daemon-reload
sudo systemctl enable --now water-backend.service
sudo systemctl restart water-backend.service
sudo systemctl is-active --quiet water-backend.service
curl --noproxy '*' --fail --silent --retry 5 --retry-connrefused --retry-delay 1 --max-time 10 http://127.0.0.1:8015/api/health >/dev/null
sudo systemctl reload nginx
curl --noproxy '*' --fail --silent --max-time 10 http://127.0.0.1:5115/water/ >/dev/null
printf '应用版本：%s\n配置备份：%s\n' "$expected_sha" "$backup_dir"
echo '服务启动检查完成。Hub须按所属仓库固定版本发布，再执行docs/09的真实登录、API、文件和业务数据验收。'
