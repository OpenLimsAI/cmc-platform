#!/usr/bin/env bash
# Mac business DB only. Does not seed, reset, copy training data, or contact Linux.
set -euo pipefail
umask 077
REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_DIR"
COMPOSE=(docker compose -f deploy/docker-compose.dev.yml)
CHECK=(python -m app.scripts.db_release --environment mac
       --expected-host postgres --expected-port 5432 --expected-database cmab_mdm --counts)
mkdir -p backups/releases
REPORT_DIR=$(mktemp -d "$REPO_DIR/backups/releases/mac-$(date -u +%Y%m%dT%H%M%SZ).XXXXXX")
stopped=0
trap 'echo "升级未完成，报告: $REPORT_DIR；后端已停止标记: $stopped。请排查后重新执行；不自动降级或覆盖数据。" >&2' ERR

echo "▶ 1/6 核对明确目标 postgres:5432/cmab_mdm（Mac Docker）"
git rev-parse HEAD > "$REPORT_DIR/code-commit.txt"
git status --short > "$REPORT_DIR/working-tree.txt"
"${COMPOSE[@]}" run --rm --no-deps -T backend "${CHECK[@]}" --allow-pending > "$REPORT_DIR/preflight.json"
TARGET_REVISION=$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["expected_revision"])' "$REPORT_DIR/preflight.json")
CHECK+=(--expected-revision "$TARGET_REVISION")

echo "▶ 2/6 停止 Mac 后端并备份（不影响 Linux）"
"${COMPOSE[@]}" stop backend
stopped=1
"${COMPOSE[@]}" run --rm --no-deps -T backend "${CHECK[@]}" --allow-pending > "$REPORT_DIR/before.json"
BACKUP_MODE=docker PG_CONTAINER=cmab-mdm-postgres POSTGRES_DB=cmab_mdm \
    BACKUP_DIR="$REPORT_DIR/database" bash scripts/backup_db.sh
DUMP_FILES=("$REPORT_DIR"/database/*.dump)
[[ ${#DUMP_FILES[@]} -eq 1 && -s "${DUMP_FILES[0]}" ]]
docker exec -i cmab-mdm-postgres pg_restore --list < "${DUMP_FILES[0]}" > "$REPORT_DIR/backup-catalog.txt"
shasum -a 256 "${DUMP_FILES[0]}" > "$REPORT_DIR/backup-sha256.txt"

echo "▶ 3/6 只通过 Alembic 执行增量迁移"
"${COMPOSE[@]}" run --rm --no-deps -T backend alembic upgrade "$TARGET_REVISION"

echo "▶ 4/6 严格核验目标版本、真实字段和数据计数"
"${COMPOSE[@]}" run --rm --no-deps -T backend "${CHECK[@]}" > "$REPORT_DIR/after.json"
python3 scripts/check_release_counts.py "$REPORT_DIR/before.json" "$REPORT_DIR/after.json"

echo "▶ 5/6 恢复后端并验证数据库就绪接口"
"${COMPOSE[@]}" start backend
stopped=0
ready=0
for ((attempt=0; attempt<20; attempt++)); do
    if "${COMPOSE[@]}" exec -T backend curl -fsS --max-time 6 \
        http://localhost:8000/api/v1/health > "$REPORT_DIR/health.json"; then
        ready=1; break
    fi
    sleep 1
done
[[ "$ready" == 1 ]]
echo "▶ 6/6 Mac 升级完成；Linux 未操作，业务数据未做跨环境同步"
echo "备份和验收报告: $REPORT_DIR"
