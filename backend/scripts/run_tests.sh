#!/usr/bin/env bash
# ============================================================
# 在独立 test DB 上跑后端测试（保留 Phase 1 的真实 HTTP 策略）
#
# 流程：引导/重建 cmab_test → alembic 迁移 → 基线 seed →
#       在 8001 起独立 uvicorn（指向 test DB + 独立 redis db）→
#       pytest 打 8001 → 退出时关服务
#
# 与 dev 服务（8000 / cmab_mdm）完全隔离：测试不再受 demo/dev 数据漂移影响。
#
# 用法（在 backend 容器内，或经 `make test-be`）：
#   bash scripts/run_tests.sh                # 全量
#   bash scripts/run_tests.sh tests/test_x.py -k foo   # 透传 pytest 参数
# ============================================================
set -euo pipefail

# export 这些变量——pytest / bootstrap 等子进程要靠它们定位测试库
export TEST_DB="${TEST_DB:-cmab_test}"
export TEST_DB_HOST="${TEST_DB_HOST:-postgres}"
TEST_PORT="${TEST_PORT:-8001}"
PGHOST="${TEST_DB_HOST}"
APP_USER="${POSTGRES_USER:-cmab_app}"
APP_PASS="${POSTGRES_PASSWORD:-__REDACTED_POSTGRES_PASSWORD__}"

export DATABASE_URL="postgresql+asyncpg://${APP_USER}:${APP_PASS}@${PGHOST}:5432/${TEST_DB}"
export DATABASE_URL_SYNC="postgresql://${APP_USER}:${APP_PASS}@${PGHOST}:5432/${TEST_DB}"
# 独立 redis db，避免与 dev 服务(0 库)的限流/幂等计数串扰
export REDIS_URL="${TEST_REDIS_URL:-redis://redis:6379/15}"

echo "▶ 1/5 引导测试库 ${TEST_DB}（DROP+CREATE 确定性基线）"
python -m app.scripts.bootstrap_test_db --recreate

echo "▶ 2/5 alembic 迁移到 head"
alembic upgrade head

echo "▶ 3/5 基线 seed（无 --demo）"
python -m app.scripts.seed_data

echo "▶ 4/5 在 :${TEST_PORT} 启动测试服务（指向 ${TEST_DB}）"
uvicorn app.main:app --host 0.0.0.0 --port "${TEST_PORT}" --log-level warning &
SERVER_PID=$!
cleanup() {
  kill "${SERVER_PID}" 2>/dev/null || true
  wait "${SERVER_PID}" 2>/dev/null || true
}
trap cleanup EXIT

# 等健康检查就绪（最多 ~20s）
ready=0
for _ in $(seq 1 40); do
  if curl -sf "http://localhost:${TEST_PORT}/api/v1/health" >/dev/null 2>&1; then
    ready=1; break
  fi
  sleep 0.5
done
if [ "${ready}" -ne 1 ]; then
  echo "✗ 测试服务未能在超时内就绪"; exit 1
fi

echo "▶ 5/5 pytest（打 :${TEST_PORT}）"
export TEST_BASE_URL="http://localhost:${TEST_PORT}"
pytest "$@"
