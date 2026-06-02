# CMC R&D LIMS Dashboard

CMC 研发 LIMS 检验进度与考核看板。FastAPI 后端 + Next.js 前端。

按 CMC 数据中台架构 v0.1：
- 看板**只读** `cmc_analytics.mart.{vw_*, dim_*, fct_*}`
- admin 面板**读写** `cmc_mdm.{mdm_quality.method_master, mdm_core.employee_master}`
- 不直接连任何 raw 库（cmc_rd / cmc_gmp / cmc_data_platform）

---

## 必备工具

| 工具 | 推荐版本 | 用途 |
|---|---|---|
| Docker Desktop | ≥ 4.x | PostgreSQL 容器 |
| Python | ≥ 3.13 | 后端运行时 |
| uv | ≥ 0.11 | Python 依赖管理 |
| Node.js | ≥ 22 LTS | 前端运行时 |
| pnpm | ≥ 10 | 前端包管理 |

---

## 目录结构

```
cmc-rd-lims-dashboard/
├── .env                # 环境变量（不入 git）
├── .env.example        # 模板
├── backend/            # FastAPI 后端
│   └── app/
│       ├── api/v1/lims/    # 看板 API（连 cmc_analytics）
│       ├── api/v1/admin/   # admin API（连 cmc_mdm）
│       ├── services/       # SQL 业务逻辑
│       ├── models/lims/    # mart 视图 ORM
│       ├── models/mdm/     # MDM 主数据 ORM
│       └── core/           # config + 双引擎 database
├── frontend/           # Next.js 前端
└── docs/
    ├── mart_contracts.md   # 看板↔mart 接口（数据侧建表依据）
    ├── mdm_contracts.md    # admin↔MDM 接口（MDM 侧建库依据）
    └── legacy/             # tt-lims-platform 历史文档
```

---

## 环境变量（.env）

```dotenv
# 看板读：cmc_analytics 只读账号
ANALYTICS_DATABASE_URL=postgresql+asyncpg://lims_reader:<密码>@localhost:5432/cmc_analytics

# admin 写：cmc_mdm 读写账号
MDM_DATABASE_URL=postgresql+asyncpg://mdm_admin:<密码>@<mdm_pg_host>:5433/cmc_mdm

# admin 前端登录密码
ADMIN_PASSWORD=<自定义密码>

# 其余（默认即可）。监听端口固定在启动命令（uvicorn --port 8030），不走 env。
APP_ENV=development
LOG_LEVEL=INFO
```

| 字段 | 必填 | 说明 |
|---|---|---|
| `ANALYTICS_DATABASE_URL` | 是 | cmc_analytics 只读；看板所有取数 |
| `MDM_DATABASE_URL` | 是 | cmc_mdm 读写；admin 面板。**当前 cmc_mdm 未创建**，参见 `mdm_contracts.md` |
| `ADMIN_PASSWORD` | 是 | 前端 `/admin` 登录密码 |

---

## 首次启动

### 0. 前置数据准备

启动前必须保证：

| 资源 | 检查 | 不满足时 |
|---|---|---|
| `cmc_analytics` 数据库 + `mart` schema | `\dn` 列出 mart | 已就绪（`lims_admin` 已建） |
| `mart.vw_*` / `mart.fct_*` / `mart.dim_*` | `\dv mart.*` | 看 `docs/mart_contracts.md` 自建 |
| `cmc_mdm` 数据库 | `\l` 列出 cmc_mdm | 看 `docs/mdm_contracts.md` §2.3 建库 SQL |

### 1. 安装依赖

```bash
cd backend && uv sync
cd ../frontend && pnpm install
```

### 2. 启动（双终端）

```bash
# 终端 1（本项目编号 30,见 ~/code/PORTS.md）
cd backend && uv run uvicorn app.main:app --reload --port 8030
# Swagger: http://localhost:8030/docs

# 终端 2
cd frontend && pnpm dev
# 访问: http://localhost:5130
```

---

## 看板页面

| 页面 | 路径 | 主要数据来源 |
|---|---|---|
| 概况 | `/dashboard/overview` | `mart.vw_test_task_monitor` |
| 员工工时 | `/dashboard/workload` | `mart.vw_test_task_monitor` + `mart.dim_method` + `mart.dim_employee` |
| 检验周期 | `/dashboard/cycle-time` | `mart.vw_test_task_monitor` + `mart.dim_method` |
| 超期未检 | `/dashboard/overdue` | `mart.vw_test_task_monitor` |
| 样本总览 | `/dashboard/samples` | `mart.vw_sample_overview` |
| 方法月报 | `/dashboard/monthly` | `mart.vw_test_task_monitor` |

---

## admin 面板

访问 `/admin`，输入 `ADMIN_PASSWORD`。

| 操作 | 落库位置 |
|---|---|
| 检验方法 CRUD / Excel 上传 | `cmc_mdm.mdm_quality.method_master` |
| 检验人员 CRUD / Excel 上传 | `cmc_mdm.mdm_core.employee_master` |

mart 层的 `mart.dim_method` / `mart.dim_employee` 应当从 cmc_mdm 通过 `snap_mdm` 每日同步（v0.1 §FDW 分级），不在 admin 直接维护。

---

## 已知开放项

1. **mart 表未落地** — 看板无法启动；按 `mart_contracts.md` §6 落地清单建表后即可用
2. **cmc_mdm 数据库未创建** — admin 面板无法用；按 `mdm_contracts.md` §2.3 建库后启用
3. **`dim_project` / `dim_group` 在 MDM 暂无对应 master 表** — mart 侧可先 `SELECT DISTINCT` 兜底

---

## 历史/参考

- 前身项目：`tt-lims-platform`（仍在生产运行，等 cmc-rd-lims-dashboard 验收通过后替换）
- 原 Streamlit 版：`/Users/qingcheng/Documents/Python/tt_lims_dashboard`（统计口径基准）
- 旧迁移日志：`docs/legacy/migration-log.md`
