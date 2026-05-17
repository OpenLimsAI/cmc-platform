# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

TT LIMS Platform — CMC 研发实验室信息管理系统。FastAPI 后端 + Next.js 前端，连接现有 PostgreSQL 16 实例（容器名 `postgres16`，库名 `cmc_data_platform`）。原 Streamlit 看板迁移项目，原版代码在 `/Users/qingcheng/Documents/Python/tt_lims_dashboard`，统计口径以原版为准。

## Development Commands

### Backend (in `backend/`)
```bash
uv run uvicorn app.main:app --reload        # dev server
uv run pytest                               # all tests
uv run pytest tests/path/to/test.py::name  # single test
uv run alembic upgrade head                 # apply migrations
uv run alembic revision --autogenerate -m "desc"
docker compose -f docker-compose.dev.yml up backend  # Docker mode
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

Browser → Next.js page (`app/dashboard/*/page.tsx`) → `lib/api.ts` (axios) → FastAPI (`/api/v1/...`) → `services/lims/stats_service.py` (raw SQL via SQLAlchemy async) → PostgreSQL `app_rd` schema views

### Backend (`backend/app/`)

- `api/v1/lims/stats.py` — all dashboard read endpoints; thin route handlers, business logic lives in `services/`
- `api/v1/admin/` — auth + CRUD for `meta.dim_method` / `meta.dim_employee`; uses `get_admin_db()` → `lims_admin` account
- `services/lims/stats_service.py` — all SQL query logic. Helper patterns:
  - `_group_clause(groups)` — builds `group_id = ANY(ARRAY['TT1',...])` or `TRUE`; groups are inlined as literals (not bind params) to avoid asyncpg type inference errors
  - `_workload_where(scope, group_sql)` — returns WHERE clause for the three workload scopes (submitted/completed/pending)
  - `_STATUS_EXCL_XU` / `_STATUS_EXCL_X` — shared status filter strings
  - `_DATE_WINDOW_RECEIVED` / `_DATE_WINDOW_AUTHORISED` — shared date window strings
- `schemas/lims/stats.py` — all Pydantic response models for stats endpoints
- `core/database.py` — two async engines: `engine` (reader, pool_size=5) and `admin_engine` (writer, pool_size=2)
- `core/config.py` — pydantic-settings; reads `.env` or `../.env`

### Frontend (`frontend/`)

- `app/dashboard/layout.tsx` — dashboard shell: sidebar + main content area
- `app/dashboard/*/page.tsx` — four pages: overview, workload, cycle-time, overdue. All are `"use client"` + `export const dynamic = "force-dynamic"` (required because they use `useSearchParams`)
- `app/admin/page.tsx` — password-protected admin panel; token stored in `sessionStorage`
- `lib/api.ts` — single axios instance + all typed fetch functions. Array params serialized as `?k=v1&k=v2` (FastAPI style). Add new fetch functions and TypeScript interfaces here.
- `components/stat-card.tsx` — colored KPI card; 7 schemes (blue/green/lapis/orange/red/purple/gray) matching the original Streamlit palette. Used on all four dashboard pages.
- `components/dashboard-sidebar.tsx` — date range pickers + group multiselect; propagates filters via URL search params to all pages

### Database

Dashboard queries read from `app_rd` schema views (primarily `v_test_task_monitor`). Never query raw tables from dashboard routes — always use the views.

| Account | Permission | Used by |
|---------|-----------|---------|
| `lims_reader` | read-only | Dashboard API (`get_db`) |
| `lims_admin` | read-write | Admin API (`get_admin_db`) |

Key `.env` vars: `DATABASE_URL`, `ADMIN_DATABASE_URL`, `ADMIN_PASSWORD`

### API

Backend: `http://localhost:8000` — Swagger docs at `/docs`  
Frontend env var: `NEXT_PUBLIC_API_BASE_URL` (defaults to `http://localhost:8000`)

## Known Gotchas

- **asyncpg + group params**: Never pass `groups` as a bind parameter when it's a list. Use `_group_clause()` which inlines `ARRAY['TT1','TT5']` as a SQL literal. Passing `None` causes `AmbiguousParameterError`.
- **SQLAlchemy async sessions**: Do not run concurrent queries on the same session with `asyncio.gather`. Always `await` sequentially.
- **useSearchParams in Next.js**: Every component that calls `useSearchParams()` must be wrapped in `<Suspense>` and the page must export `const dynamic = "force-dynamic"`.
- **Axios array params**: The custom `paramsSerializer` in `lib/api.ts` serializes arrays as `?k=v1&k=v2`. Do not use `k[]=v1` style.
- **cycle-time page date range**: The date range on this page is controlled by the `trendMonths` slider, not the sidebar date pickers. `tableStart = dayjs().subtract(trendMonths-1, "month").startOf("month")` — this matches the backend SQL logic exactly.
