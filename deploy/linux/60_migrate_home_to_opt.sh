#!/usr/bin/env bash
# 把还留在 /home/prometheus 下的项目统一搬到 /opt（总纲 CLAUDE.md §7：正式项目一律 /opt），2026-09-04 负责人决定「不管在不在用都迁」。
# 可重复跑：已在 /opt 的跳过。同一文件系统，mv 瞬间完成；Python .venv 里写死了绝对路径，搬完必须重建。
#   早期 quality-analysis-platform 已于 2026-09-24 退役，不得由本脚本重新创建。
#   未用 3 个：tt-lims-platform、qc_lims_etl、cmc-deploy（只搬目录，过期 .venv 删掉，要用时 uv sync 重建）
source "$(dirname "$0")/00_common.sh"
UV="$HOME/.local/bin/uv"
export PATH="$HOME/.local/bin:$PATH"

move() {  # $1 = 目录名
  local src="$HOME/$1" dst="/opt/$1"
  if [ -d "$dst" ]; then ok "$dst 已存在，跳过搬迁"; return 0; fi
  [ -d "$src" ] || { echo "    ✗ 找不到 $src"; return 1; }
  sudo mv "$src" "$dst" && sudo chown -R prometheus:prometheus "$dst" && ok "$src → $dst"
}
rebuild_uv_venv() { (cd "$1" && rm -rf .venv && "$UV" sync 2>&1 | tail -2) && ok "$1 .venv 已用 uv sync 重建"; }

# ── 1. cmc-schema-migrations（手工工具，pip venv）
log "1/7 cmc-schema-migrations"
move cmc-schema-migrations
(cd /opt/cmc-schema-migrations && rm -rf .venv && "$UV" venv .venv --python 3.12 >/dev/null 2>&1 && "$UV" pip install -q -r requirements.txt --python .venv/bin/python) && ok ".venv 已按 README 重建"

# ── 2. rd-lims-etl（crontab 8/12/16 点）
log "2/7 rd-lims-etl"
move rd-lims-etl
rebuild_uv_venv /opt/rd-lims-etl
if crontab -l 2>/dev/null | grep -q "/home/prometheus/rd-lims-etl"; then
  crontab -l > "$HOME/crontab.bak-$STAMP"
  crontab -l | sed 's#/home/prometheus/rd-lims-etl#/opt/rd-lims-etl#g' | crontab -
  ok "crontab 已改路径（备份 ~/crontab.bak-$STAMP）"
fi
crontab -l | grep rd-lims-etl

# ── 3. cmc-rd-lims-dashboard（systemd cmc-lims-backend / cmc-lims-frontend）
log "3/7 cmc-rd-lims-dashboard"
sudo systemctl stop cmc-lims-frontend cmc-lims-backend || true
move cmc-rd-lims-dashboard
rebuild_uv_venv /opt/cmc-rd-lims-dashboard/backend
(cd /opt/cmc-rd-lims-dashboard/frontend && pnpm install --frozen-lockfile >/dev/null && pnpm build 2>&1 | tail -2) && ok "前端已重装依赖并重建"
for u in cmc-lims-backend cmc-lims-frontend; do
  p=/etc/systemd/system/$u.service
  if grep -q "/home/prometheus/cmc-rd-lims-dashboard" "$p"; then
    backup "$p"; sudo sed -i 's#/home/prometheus/cmc-rd-lims-dashboard#/opt/cmc-rd-lims-dashboard#g' "$p"; ok "$u unit 已改路径"
  fi
done
sudo systemctl daemon-reload
restart_unit cmc-lims-backend; restart_unit cmc-lims-frontend
check http://127.0.0.1:5100/lims; check http://127.0.0.1:5100/lims/api/v1/lims/stats/data-freshness

# ── 4~6. 未用三个：只搬目录，过期 .venv 删掉
log "4/6 tt-lims-platform"; move tt-lims-platform; rm -rf /opt/tt-lims-platform/backend/.venv; ok "过期 .venv 已删（要用时 cd backend && uv sync）"
log "5/6 qc_lims_etl";      move qc_lims_etl;      rm -rf /opt/qc_lims_etl/.venv;             ok "过期 .venv 已删（要用时 uv sync）；.env 的 CSV_DIR 仍指向 ~/qc_lims_csv_snapshot 数据目录，未动"
log "6/6 cmc-deploy";       move cmc-deploy

log "收尾检查：还有谁引用 /home/prometheus/<项目>"
grep -l "/home/prometheus/\(cmc-rd-lims-dashboard\|rd-lims-etl\|cmc-schema-migrations\|tt-lims-platform\|qc_lims_etl\|cmc-deploy\)" /etc/systemd/system/*.service /etc/nginx/conf.d/*.conf 2>/dev/null || ok "systemd / nginx 无残留引用"
crontab -l | grep -c "/home/prometheus/rd-lims-etl" | xargs -I{} sh -c '[ "{}" = "0" ] && echo "    ✓ crontab 无残留引用" || echo "    ✗ crontab 仍有 {} 处引用"'
ls -d /opt/cmc-schema-migrations /opt/rd-lims-etl /opt/cmc-rd-lims-dashboard /opt/tt-lims-platform /opt/qc_lims_etl /opt/cmc-deploy
