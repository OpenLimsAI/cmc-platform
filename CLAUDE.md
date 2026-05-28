# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

CMC R&D LIMS Dashboard — CMC 研发 LIMS 检验进度与考核看板。FastAPI 后端 + Next.js 16 前端。前身项目 `tt-lims-platform`，按 CMC 数据中台架构 v0.1 重建：

- 看板**只读** `cmc_analytics.mart`（mart 由数据侧负责建设，看板侧只消费）
- admin 面板**读写** `cmc_analytics.mdm.{personnel, test_method}`（MDM 数据 2026-05-18 已由独立 `cmc_mdm` 库归并到 `cmc_analytics.mdm`，由数据侧维护表结构 + 软删除字段）
- 本 app **不拥有任何 DB 表**，因此不带 alembic
- 原 Streamlit 看板的统计口径仍是基准，在 `/Users/qingcheng/Documents/Python/tt_lims_dashboard`

数据流向：
```
cmc_rd.raw_rd_lims_samplemanager  →  cmc_analytics.staging  →  cmc_analytics.mart  →  本看板
cmc_analytics.mdm.{personnel,test_method}  →  mart.dim_{employee,method}（WHERE deleted_at IS NULL）  →  本看板
                                           ←——————— admin 面板（SELECT/INSERT/UPDATE，软删除）———————
```

## Development Commands

### Backend (in `backend/`)
```bash
uv run uvicorn app.main:app --reload --port 8001   # dev server（与 frontend/.env.local 对齐；8000 默认端口常被 cmc-inventory 占用）
uv run pytest                               # all tests
```

### Frontend (in `frontend/`)
```bash
pnpm dev    # dev server at http://localhost:3000
pnpm build
pnpm lint
```

> **Next.js version note**: This project uses Next.js 16. Read `node_modules/next/dist/docs/` before writing Next.js code — APIs may differ from training data.

## Architecture

### Request flow

Browser → Next.js page (`app/dashboard/*/page.tsx`) → `lib/api.ts` (axios) → FastAPI (`/api/v1/...`) → `services/lims/stats_service.py` (raw SQL via SQLAlchemy async) → `cmc_analytics.mart.*`

### Backend (`backend/app/`)

- `api/v1/lims/stats.py` — 看板 read 端点；薄路由，业务逻辑在 `services/`，依赖 `get_analytics_db()`
- `api/v1/admin/` — auth + CRUD for `cmc_analytics.mdm.test_method` / `mdm.personnel`；依赖 `get_mdm_db()`；list/get/update 都带 `WHERE deleted_at IS NULL`
- `services/lims/stats_service.py` — 所有 SQL 查询逻辑。常用辅助：
  - `_group_clause(groups)` — 构建 `group_id = ANY(ARRAY['TT1',...])` 或 `TRUE`；group 内联为字面量，避免 asyncpg 类型推断报错
  - `_workload_where(scope, group_sql)` — 工时三口径 WHERE 子句
  - `_STATUS_EXCL_XU` / `_STATUS_EXCL_X` — 状态过滤
  - `_DATE_WINDOW_RECEIVED` / `_DATE_WINDOW_AUTHORISED` — 日期窗口
- `schemas/lims/stats.py` — 所有 Pydantic 响应模型
- `models/lims/views.py` — mart 视图 ORM（`mart.vw_test_task_monitor` / `mart.vw_sample_overview`）
- `models/mdm/masters.py` — MDM 主数据 ORM（`mdm.test_method` / `mdm.personnel`），含软删除字段
- `core/database.py` — 双异步引擎都连 `cmc_analytics`：`analytics_engine`（`lims_reader`，pool=5）+ `mdm_engine`（`lims_mdm_writer`，pool=2）；分开仅为隔离读 / 写角色
- `core/config.py` — pydantic-settings；读 `.env` 或 `../.env`

### Frontend (`frontend/`)

- `app/dashboard/layout.tsx` — 看板壳：sidebar + 主内容
- `app/dashboard/*/page.tsx` — 6 个看板页面（overview/cycle-time/overdue/workload/samples/monthly），全部 `"use client"` + `export const dynamic = "force-dynamic"`（用了 `useSearchParams`）
- `app/admin/page.tsx` — 密码保护的 admin 面板；token 在 `sessionStorage`
- `lib/api.ts` — 单 axios 实例 + 全部 typed fetch 函数。数组参数序列化为 `?k=v1&k=v2`（FastAPI 风格）
- `components/stat-card.tsx` — 7 色 KPI 卡（blue/green/lapis/orange/red/purple/gray），对齐原 Streamlit 色板
- `components/dashboard-sidebar.tsx` — 日期范围 + 检验组多选；通过 URL search params 传给所有页面

### Database

看板只查 `cmc_analytics.mart.*` 视图；不要直接查 raw 库或 staging 层。

| 账号 | 权限 | 用途 |
|---|---|---|
| `lims_reader` | SELECT on `cmc_analytics`（mart / mdm 全部只读） | 看板 API（`get_analytics_db`） |
| `lims_mdm_writer` | SELECT/INSERT/UPDATE on `cmc_analytics.mdm.{personnel,test_method}`（无 DELETE，强制走软删除） | admin API（`get_mdm_db`） |

`.env` 关键变量：`ANALYTICS_DATABASE_URL`、`MDM_DATABASE_URL`、`ADMIN_PASSWORD`

### API

Backend: `http://localhost:8001` — Swagger: `/docs`
Frontend env: `NEXT_PUBLIC_API_BASE_URL`（默认 `http://localhost:8001`）

## Known Gotchas

- **asyncpg + group params**：永远不要把 list 直接绑 group 参数。用 `_group_clause()` 把 `ARRAY['TT1','TT5']` 内联为 SQL 字面量。绑 `None` 会触发 `AmbiguousParameterError`。
- **SQLAlchemy async sessions**：不要用 `asyncio.gather` 在同一 session 并发查询，要顺序 `await`
- **useSearchParams in Next.js**：调 `useSearchParams()` 的组件必须包 `<Suspense>`，页面必须 `export const dynamic = "force-dynamic"`
- **Axios array params**：`lib/api.ts` 里自定义的 `paramsSerializer` 把数组序列化成 `?k=v1&k=v2`，不要用 `k[]=v1`
- **cycle-time page date range**：本页日期范围由 `trendMonths` slider 控制，不是 sidebar 日期。`tableStart = dayjs().subtract(trendMonths-1, "month").startOf("month")`，跟后端 SQL 对齐
- **MDM 软删除约定**：`cmc_analytics.mdm.{personnel,test_method}` 用 `deleted_at IS NOT NULL` 标记软删；admin 读 / 写、`mart.dim_employee` / `mart.dim_method` 视图都要过滤掉软删行。`lims_mdm_writer` 没有 DELETE 权限，物理删要走 DBA。
- **旧 `cmc_mdm` 库 / `mdm_admin` 角色已删除**（2026-05-18）：所有 `mdm_quality.*` / `mdm_core.*` / `mdm_admin` 引用都已废弃，看到要立刻替换成 `cmc_analytics.mdm.*` / `lims_mdm_writer`。`docs/mdm_contracts.md` 与 `docs/mart_contracts.md` 里残留的旧契约描述属于历史快照，仅作参考。

## 重要文档

- `docs/mart_contracts.md` — 看板与 mart 的接口（数据侧建表依据）
- `docs/mdm_contracts.md` — admin 与 MDM 的接口（**历史快照**：原 `cmc_mdm` 独立库方案，现已归并到 `cmc_analytics.mdm.*`，文本未刷新仅作参考）
- `docs/README.md` — 项目说明
- `docs/legacy/` — tt-lims-platform 历史文档（仅参考）
