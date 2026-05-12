.PHONY: help up down logs logs-be logs-fe migrate seed reset-db test-be lint-be lint-fe gen-types docs-extract docs-check

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

up:
	$(COMPOSE) up -d --build
	@echo ""
	@echo "✓ 服务已启动"
	@echo "  前端：       http://localhost:5173"
	@echo "  后端：       http://localhost:8000"
	@echo "  API 文档：   http://localhost:8000/api/v1/docs"

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
