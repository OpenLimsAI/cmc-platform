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
uv run uvicorn app.main:app --reload --port 8030   # dev server（本项目编号 30,见 ~/code/PORTS.md；与 frontend lib/api.ts 默认值对齐）
uv run pytest                               # all tests
```

### Frontend (in `frontend/`)
```bash
pnpm dev    # dev server at http://localhost:5130（端口在 package.json 的 next dev -p 5130 钉死）
pnpm build
pnpm lint
```

> **Next.js version note**: This project uses Next.js 16. Read `node_modules/next/dist/docs/` before writing Next.js code — APIs may differ from training data.

## Architecture

### Request flow

Browser → Next.js page (`app/dashboard/*/page.tsx`) → `lib/api.ts` (axios) → FastAPI (`/api/v1/...`) → `services/lims/stats_service.py` (raw SQL via SQLAlchemy async) → `cmc_analytics.mart.*`

### Backend (`backend/app/`)

- `api/v1/lims/stats.py` — 看板 read 端点；薄路由，业务逻辑在 `services/`，依赖 `get_analytics_db()`
- `api/v1/auth.py` — MDM 统一登录代理（login/refresh/logout 转发 `MDM_BASE_URL`，refresh 走 HttpOnly Cookie 中转，接法对齐 labops，见 `~/code/CLAUDE.md` 第 8 节）
- `core/security.py` + `core/auth.py` — JWT 验签（HS256 共享密钥/RS256）+ 角色依赖。三角色在 MDM 维护：`CMC_LIMS_ANALYST`(查看) / `CMC_LIMS_CHEMIST`(查看+导出) / `CMC_LIMS_ADMIN`(查看+导出+admin 后台)，`SYS_ADMIN` 恒放行。看板读接口在 `router.py` 统一挂 `require_view`；`/api/v1/health` 与 `/api/v1/auth/*` 开放。未配 `JWT_SECRET_KEY` = 本地开放模式（不鉴权）；`AUTH_REQUIRED=true` 且没配密钥则启动报错
- `api/v1/admin/` — CRUD for `cmc_analytics.mdm.test_method` / `mdm.personnel`；依赖 `get_mdm_db()`；鉴权走 `verify_admin`（= `require_admin`，旧共享密码 + x-admin-token 机制已废除）；list/get/update 都带 `WHERE deleted_at IS NULL`
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
- `app/login/page.tsx` — MDM 统一登录页（工号+密码）；`components/auth-guard.tsx` 未登录跳 /login
- `app/admin/page.tsx` — admin 面板；管理员角色（`CMC_LIMS_ADMIN`/`SYS_ADMIN`）免密直入，无角色提示无权限
- `lib/auth.ts` — token 存 `localStorage`（key `lims_token`），前端只 base64 解 payload 取角色做显隐（真鉴权在后端）
- `lib/api.ts` — 单 axios 实例 + 全部 typed fetch 函数 + 认证拦截器（自动带 Bearer、access 剩 <5min 主动续期、401 兜底续期重放一次后登出）。数组参数序列化为 `?k=v1&k=v2`（FastAPI 风格）
- `components/stat-card.tsx` — 7 色 KPI 卡（blue/green/lapis/orange/red/purple/gray），对齐原 Streamlit 色板
- `components/dashboard-sidebar.tsx` — 日期范围 + 检验组多选；通过 URL search params 传给所有页面

### Database

看板只查 `cmc_analytics.mart.*` 视图；不要直接查 raw 库或 staging 层。

| 账号 | 权限 | 用途 |
|---|---|---|
| `lims_reader` | SELECT on `cmc_analytics`（mart / mdm 全部只读） | 看板 API（`get_analytics_db`） |
| `lims_mdm_writer` | SELECT/INSERT/UPDATE on `cmc_analytics.mdm.{personnel,test_method}`（无 DELETE，强制走软删除） | admin API（`get_mdm_db`） |

`.env` 关键变量：`ANALYTICS_DATABASE_URL`、`MDM_DATABASE_URL`、`JWT_SECRET_KEY`（须等于 MDM 的 SECRET_KEY）、`MDM_BASE_URL`、`AUTH_REQUIRED`（旧 `ADMIN_PASSWORD` 已废除）

### API

Backend: `http://localhost:8030` — Swagger: `/docs`
Frontend env: `NEXT_PUBLIC_API_BASE_URL`（默认 `http://localhost:8030`）

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

## 统一门户 cmab-hub（2026-08-17 起，改前端必读）

- 本系统已挂在统一门户之下：正式入口 **http://172.19.0.105:5100/lims**（Linux 上本系统前后端只听 127.0.0.1，老端口内网不可达）。Mac 本地同样经 `localhost:5100/lims`。
- 前端**自己认前缀** `/lims`：`next.config.ts` `basePath:'/lims'`；`lib/auth.ts` 有 BASE/withBase/stripBase；`lib/api.ts` `BASE_URL` 默认 `/lims`。API 一律相对路径 `/lims/api/...`，由门户 nginx 剥掉前缀转给后端（后端路由不变）。**不要**写死 host:端口，**不要**用不带前缀的绝对路径跳转/引资源。
- 登录态用**全公司统一 key**：`localStorage['cmab_access_token']`（MDM JWT）+ `localStorage['cmab_user']`（MDM 登录响应 user 对象）；同源共享 → 门户登录一次这里免登。别再改回私有 key。 `frontend/.env.local` 的 `NEXT_PUBLIC_API_BASE_URL` 必须是 `/lims`（不进 git，Mac/Linux 都已改）。跳转用 `router`（自动带 basePath），直接 `window.location` 要 `withBase`。
- 门户侧配置/路由/部署脚本在 `~/code/cmab-hub`（`nginx/hub-locations.conf`、`deploy/linux/`），约定见其 `CLAUDE.md`。
