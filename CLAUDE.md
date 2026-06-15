# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 项目概览

CMAB MDM Portal —— 生物制药 CMC 主数据平台,五域:SRS(物质)/PRS(项目)/ARS(资产)/MM(物料)/EQP(设备) + auth/audit/search 横切域。后端 FastAPI(async SQLAlchemy 2.0 + asyncpg + Pydantic v2),前端 React 18 + Vite + Ant Design + Zustand + React Query。

**当前为原型阶段,未进入 GxP/GMP。** 不走正式评审会/合规产物暂缓;原本"需评审"的事项由负责人直接决策。不要主动要求走 GMP 流程或补合规产物——除非用户明确说进入 GMP。

## ⚠️ 数据安全:已上线测试运行,严禁灌 demo / 清库(2026-06-15 起)

项目已进入**上线测试运行**,dev 库里的数据**部分是真实生产数据**,不可破坏:

- **物料(MM)、设备(EQP)= 真实数据**(物料 ~3770、设备 ~461),绝不能被覆盖/清空/灌假数据。
- **物质(SRS)、项目(PRS)、资产(ARS)= 真实即为 0 条**(尚未录入,空是正常状态,不是数据丢失)。若看到物质里有 `audit test...` 之类记录,那是历史污染,清理需用户确认,不要自行 seed 补数。
- **禁止运行任何会灌 demo 或重置库的命令**:`make seed-demo`、`make seed --demo`、`make reset-db`、`app.scripts.seed_real_demo` 等——除非用户**明确**要求。`make seed`(基线种子)同样先确认。
- **测试只能走 `make test-be`**(隔离 `cmab_test` 库)。**绝对禁止** `make test-be-dev` 或在容器里直跑 `pytest`——会打到 dev 库 `cmab_mdm`,污染真实物料/设备数据。

## 工具链全在 Docker 容器里

ruff / mypy / eslint / pytest / alembic **都不装在宿主机**,只在容器内。一律通过 `make`(底层 `docker compose -f deploy/docker-compose.dev.yml exec`)或 `docker exec <容器名> ...` 调用,不要在宿主机直接跑这些命令。容器名:`cmab-mdm-backend` / `cmab-mdm-frontend` / `cmab-mdm-postgres` / `cmab-mdm-redis`。

## 常用命令

```bash
make up / down / logs-be / logs-fe   # 起停/看日志
make migrate          # alembic upgrade head(容器内)
make seed             # 基线种子数据;make seed-demo 带演示数据
make test-be          # ✅ 跑后端测试(见下方坑)
make lint-be          # ruff check . && mypy app
make lint-fe          # pnpm lint(eslint,--max-warnings 0)
make gen-types        # 前端从后端 OpenAPI 生成 src/api/schema.d.ts(需后端在跑)
make docs-extract     # 从 .docx 派生 .md(见文档双轨)
make docs-check       # CI 文档一致性校验
```

## 测试(关键坑)

- **永远用 `make test-be`**,不要在容器里直接 `pytest`。`make test-be` 走 `scripts/run_tests.sh`:重建独立测试库 `cmab_test` + 8001 端口测试服务 + redis db15,与 dev 数据隔离。
- `make test-be-dev`(直跑 `pytest`)会打到 **dev 库 `cmab_mdm`**,造成数据漂移、且缺 seed 用户时登录 fixture 报 401。仅在明知后果时用。
- 单测:`make test-be ARGS` 不支持,直接 `docker exec cmab-mdm-backend bash scripts/run_tests.sh tests/test_x.py::test_y` 或在隔离环境下传参给 run_tests.sh。
- pytest 配置 `asyncio_mode=auto`,测试文件 `test_*.py`,放 `backend/tests/`。

## 数据库变更

- 所有 schema 变更走 **alembic**,不要手改表。迁移文件 `backend/alembic/versions/`,命名 `YYYY_MM_DD_HHMM_NNNN_desc.py`。
- alembic 用同步驱动:`DATABASE_URL_SYNC`(与 app 的异步 `DATABASE_URL` 分开);两者指向不同逻辑库(dev `cmab_mdm` / test `cmab_test`),配错会静默失败。
- 涉及合规字段的库变更,改前先与用户确认。

## 后端代码约定

- 域分层:每个 `app/domains/<域>/` 含 `models.py`(ORM)/`schemas.py`(Pydantic I/O)/`services.py`(业务逻辑);路由在 `app/api/v1/`;横切在 `app/shared/`。
- ruff 选用规则 E,W,F,I,B,C4,UP,N,SIM;忽略 E501/B008/N805;`alembic/versions/*` 忽略 E501,F401。无 `ruff format`(不要擅自引入格式化器,会造成大面积 churn)。
- **async SQLAlchemy 坑**:service 内禁 `try/except IntegrityError + rollback`,用 pre-check 替代;强一致场景在 service 内显式 `commit`(FastAPI yield 依赖的 commit 在 response 之后才跑);登录/签名等失败路径的计数与审计必须用独立旁路 session(`AsyncSessionLocal`)commit,避免主事务 rollback 丢失。

## 前端代码约定

- 包管理器 **pnpm**(禁 npm)。依赖装在容器内:宿主 `pnpm install` + `docker exec -e CI=1 cmab-mdm-frontend pnpm install`;坏了重启容器。
- API 类型由 `make gen-types` 从后端 OpenAPI 生成到 `src/api/schema.d.ts`,不要手改。
- eslint `--max-warnings 0`,提交前需零告警。

## 文档双轨

`docs/*.docx` 是源(Word 编辑),`docs/*.md` 由 `make docs-extract` 自动派生。**不要手改 .md**——CI `make docs-check` 会因不一致而失败。派生工具走 `make docs-extract`,不要在 `scripts/` 另写 pandoc 包装。

## 提交约定

- 中文 conventional commits:`fix(auth): ...` / `feat(mm): ...` / `style(tests): ...`。
- 默认在 `main` 上开发;**仅在用户要求时**才 commit/push;要开 PR 时才建分支。
- commit message 末尾加 `Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>`。

## 端口与账号(dev)

- 宿主端口:前端 15173 / 后端 18000 / postgres 15432 / redis 16379(可被 `HOST_*_PORT` 覆盖)。
- dev 种子账号:`admin/__REDACTED_SEED_PASSWORD_1__`、`qingcheng/__REDACTED_SEED_PASSWORD_2__`、`researcher/__REDACTED_SEED_PASSWORD_5__`、`qa_reviewer/__REDACTED_SEED_PASSWORD_3__`、`readonly/__REDACTED_SEED_PASSWORD_4__`。
