#!/usr/bin/env bash
# Linux native release. Invoke from a reviewed, clean commit:
#   bash deploy/deploy.sh <full-commit-sha>
# No implicit git pull: code + migrations stay pinned throughout release.
set -euo pipefail
umask 022
REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_DIR"
if [[ $# -ne 1 || $(git rev-parse HEAD) != "$1" || -n $(git status --porcelain) ]]; then
    echo "请先检出审核过的提交，保持工作区干净，并传入当前完整 commit SHA。" >&2
    exit 1
fi
CHECK=(.venv/bin/python -m app.scripts.db_release --environment linux
       --expected-host 127.0.0.1 --expected-port 5433 --expected-database cmab_mdm --counts)
mkdir -p backups/releases
REPORT_DIR=$(mktemp -d "$REPO_DIR/backups/releases/linux-$(date -u +%Y%m%dT%H%M%SZ).XXXXXX")
STAGE_DIR=$(mktemp -d /tmp/cmab-mdm-frontend.XXXXXX)
stopped=0
trap 'echo "发布未完成，报告: $REPORT_DIR；后端已停止标记: $stopped。不要盲目重启旧代码或 downgrade。" >&2' ERR

echo "▶ 1/7 核对明确目标 127.0.0.1:5433/cmab_mdm（Linux）"
git rev-parse HEAD > "$REPORT_DIR/code-commit.txt"
(cd backend && "${CHECK[@]}" --allow-pending) > "$REPORT_DIR/preflight.json"
TARGET_REVISION=$(backend/.venv/bin/python -c 'import json,sys; print(json.load(open(sys.argv[1]))["expected_revision"])' "$REPORT_DIR/preflight.json")
CHECK+=(--expected-revision "$TARGET_REVISION")
sudo -n true

echo "▶ 2/7 构建前端到独立目录（不覆盖正在服务的文件）"
(cd frontend && pnpm install --frozen-lockfile && pnpm exec tsc -b && pnpm exec vite build --outDir "$STAGE_DIR")
if [[ -d frontend/dist ]]; then cp -a frontend/dist "$REPORT_DIR/frontend-dist"; fi

echo "▶ 3/7 停后端、留基线、备份并检查归档"
sudo -n systemctl stop cmab-backend
stopped=1
(cd backend && "${CHECK[@]}" --allow-pending) > "$REPORT_DIR/before.json"
# Use the same resolved settings as preflight, not a separately parsed .env or
# inherited PG_DSN. The connection string is not written into release reports.
PG_DSN=$(cd backend && .venv/bin/python -c 'from app.core.config import settings; print(settings.DATABASE_URL_SYNC)') \
    BACKUP_MODE=native BACKUP_DIR="$REPORT_DIR/database" bash scripts/backup_db.sh
DUMP_FILES=("$REPORT_DIR"/database/*.dump)
[[ ${#DUMP_FILES[@]} -eq 1 && -s "${DUMP_FILES[0]}" ]]
pg_restore --list "${DUMP_FILES[0]}" > "$REPORT_DIR/backup-catalog.txt"
sha256sum "${DUMP_FILES[0]}" > "$REPORT_DIR/backup-sha256.txt"

echo "▶ 4/7 通过 Alembic 迁移，并严格核验版本、字段及计数"
(cd backend && .venv/bin/alembic upgrade "$TARGET_REVISION")
(cd backend && "${CHECK[@]}") > "$REPORT_DIR/after.json"
backend/.venv/bin/python scripts/check_release_counts.py "$REPORT_DIR/before.json" "$REPORT_DIR/after.json"

echo "▶ 5/7 发布前端并恢复服务"
mkdir -p frontend/dist
# Retain old hashed assets for already-open pages. mktemp's 700 must not reach nginx.
cp -R "$STAGE_DIR"/. frontend/dist/
chmod 755 frontend/dist
sudo -n systemctl start cmab-backend
stopped=0

echo "▶ 6/7 验证门户后端就绪、静态首页和服务状态"
ready=0
for ((attempt=0; attempt<20; attempt++)); do
    if curl --noproxy '*' -fsS --max-time 6 http://127.0.0.1:5100/mdm/api/v1/health > "$REPORT_DIR/health.json"; then
        ready=1; break
    fi
    sleep 1
done
[[ "$ready" == 1 ]]
curl --noproxy '*' -fsS --max-time 10 http://127.0.0.1:5100/mdm/ > "$REPORT_DIR/served-index.html"
cmp frontend/dist/index.html "$REPORT_DIR/served-index.html"
sudo -n systemctl is-active cmab-backend nginx
echo "▶ 7/7 Linux 发布完成；Mac 未操作，业务数据未做跨环境同步"
echo "备份和验收报告: $REPORT_DIR"
