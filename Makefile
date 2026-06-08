.PHONY: help up down logs logs-be logs-fe migrate seed reset-db test-be test-be-dev lint-be lint-fe gen-types docs-extract docs-check backup restore check-schema

COMPOSE := docker compose -f deploy/docker-compose.dev.yml

help:
	@echo "CMAB MDM Portal - 常用命令"
	@echo ""
	@echo "  make up          启动所有 dev 服务"
	@echo "  make down        停止所有服务"
	@echo "  make logs        查看所有日志"
	@echo "  make logs-be     仅看后端日志"
	@echo "  make logs-fe     仅看前端日志"
	@echo "  make migrate     应用数据库迁移"
	@echo "  make seed        加载种子数据（仅 baseline：权限/角色/用户/示例 substance）"
	@echo "  make seed-demo   加载 baseline + 演示数据集（项目/里程碑/团队/跨域绑定，幂等）"
	@echo "  make reset-db    重置数据库（⚠️ 删除全部数据）"
	@echo "  make shell-be    进入后端容器 shell"
	@echo "  make shell-db    进入数据库 psql"
	@echo "  make test-be     运行后端测试"
	@echo "  make lint-be     后端代码检查"
	@echo "  make lint-fe     前端代码检查"
	@echo "  make gen-types   从后端 OpenAPI 生成前端 TS 类型"
	@echo ""
	@echo "  make docs-extract 从 V1.1+ docx 派生 markdown（双轨同步）"
	@echo "  make docs-check   校验 markdown 与 docx 一致性（CI 门禁）"
	@echo ""
	@echo "  make backup      跑 pg_dump（dev 写到 backups/ 目录）"
	@echo "  make restore F=<dump>  从 backups/F 恢复（dev 测试用）"
	@echo ""
	@echo "  make check-schema 对比 DB schema 与 V1.1 DM 设计基线（CSV CI 门禁）"

up:
	$(COMPOSE) up -d --build
	@echo ""
	@echo "✓ 服务已启动"
	@echo "  前端：       http://localhost:15173"
	@echo "  后端：       http://localhost:18000"
	@echo "  API 文档：   http://localhost:18000/api/v1/docs"

down:
	$(COMPOSE) down

logs:
	$(COMPOSE) logs -f --tail=100

logs-be:
	$(COMPOSE) logs -f --tail=100 backend

logs-fe:
	$(COMPOSE) logs -f --tail=100 frontend

migrate:
	$(COMPOSE) exec backend alembic upgrade head

seed:
	$(COMPOSE) exec backend python -m app.scripts.seed_data

seed-demo:
	$(COMPOSE) exec backend python -m app.scripts.seed_data --demo

reset-db:
	@echo "⚠️ 这将删除所有数据。3 秒后开始..."
	@sleep 3
	$(COMPOSE) down -v
	$(COMPOSE) up -d postgres redis
	@sleep 5
	$(COMPOSE) up -d --build backend frontend
	@sleep 5
	$(COMPOSE) exec backend alembic upgrade head
	$(COMPOSE) exec backend python -m app.scripts.seed_data
	@echo "✓ 数据库已重置并加载种子数据"

shell-be:
	$(COMPOSE) exec backend bash

shell-db:
	$(COMPOSE) exec postgres psql -U cmab_app -d cmab_mdm

test-be:
	$(COMPOSE) exec backend bash scripts/run_tests.sh -v

# 旧策略：直接打 dev 服务(8000/cmab_mdm)，会受 dev 数据漂移影响；仅快速本地调试用
test-be-dev:
	$(COMPOSE) exec backend pytest -v

lint-be:
	$(COMPOSE) exec backend ruff check .
	$(COMPOSE) exec backend mypy app

lint-fe:
	$(COMPOSE) exec frontend pnpm lint

gen-types:
	cd frontend && pnpm gen:api

# ============== 双轨文档同步 ==============
# docx 是源（签字定稿、Word 修订模式追踪）；markdown 由 docx 自动派生。
# markdown 不能手工修改；CI 通过 docs-check 强制一致性。
docs-extract:
	@python3 scripts/docs/extract_md.py

docs-check:
	@python3 scripts/docs/check_consistency.py

# ============== 备份 / 恢复（P4.B-6） ==============
# dev 模式无 /backups 挂载，pg_dump 写到容器 /tmp 再 docker cp 出来；prod 走 backup_db.sh
backup:
	@mkdir -p backups
	@TS=$$(date -u +"%Y%m%d_%H%M") && \
	  $(COMPOSE) exec -T postgres pg_dump -U postgres -d cmab_mdm -F c -Z 6 -f "/tmp/cmab_mdm_$$TS.dump" && \
	  docker cp cmab-mdm-postgres:/tmp/cmab_mdm_$$TS.dump backups/ && \
	  $(COMPOSE) exec -T postgres rm -f /tmp/cmab_mdm_$$TS.dump && \
	  echo "✓ 备份完成：backups/cmab_mdm_$$TS.dump"

# ============== JWT 密钥生成（Phase 5.C / ARCH2） ==============
# 默认输出 deploy/jwt/jwt_{private,public}.pem；私钥 600 权限
jwt-keys:
	@bash scripts/gen_jwt_keys.sh

# ============== schema 一致性 CI 门禁（P4.D-3） ==============
# 把 scripts/ + docs/ 临时拷到 backend 容器，连容器内 DATABASE_URL_SYNC 跑
# 注意：docker cp 进已存在目录会嵌套，所以每次先 rm 清空
check-schema:
	@docker exec cmab-mdm-backend rm -rf /tmp/csv_check 2>/dev/null || true
	@docker cp scripts/csv cmab-mdm-backend:/tmp/csv_check
	@docker cp docs/CMAB_MDM_Portal_数据模型设计文档_V1_1.md cmab-mdm-backend:/tmp/csv_check/dm_v1_1.md
	@$(COMPOSE) exec -T -e DM_MD_OVERRIDE=/tmp/csv_check/dm_v1_1.md \
	    -e DATABASE_URL_SYNC=postgresql://postgres:__REDACTED_POSTGRES_DBA_PASSWORD__@postgres:5432/cmab_mdm \
	    backend python -B /tmp/csv_check/check_schema_alignment.py
	@docker exec cmab-mdm-backend rm -rf /tmp/csv_check

restore:
	@if [ -z "$(F)" ]; then echo "用法：make restore F=<dump-file>（在 backups/ 下）"; exit 1; fi
	@if [ ! -s "backups/$(F)" ]; then echo "ERROR：backups/$(F) 不存在或为空"; exit 2; fi
	@docker cp "backups/$(F)" cmab-mdm-postgres:/tmp/restore.dump
	@$(COMPOSE) exec -T postgres psql -U postgres -d postgres -c \
	    "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = 'cmab_mdm' AND pid <> pg_backend_pid();" >/dev/null
	@$(COMPOSE) exec -T postgres psql -U postgres -d postgres -c "DROP DATABASE IF EXISTS cmab_mdm;"
	@$(COMPOSE) exec -T postgres psql -U postgres -d postgres -c "CREATE DATABASE cmab_mdm WITH ENCODING='UTF8';"
	@$(COMPOSE) exec -T postgres pg_restore -U postgres -d cmab_mdm --no-owner --no-privileges /tmp/restore.dump
	@$(COMPOSE) exec -T postgres rm -f /tmp/restore.dump
	@echo "✓ 恢复完成。建议跑 make test-be 验证完整性"
