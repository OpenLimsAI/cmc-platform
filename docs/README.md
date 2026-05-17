# TT LIMS Platform 使用手册

CMC 研发实验室信息管理系统。FastAPI 后端 + Next.js 前端，连接 PostgreSQL 16。

---

## 必备工具

| 工具 | 推荐版本 | 用途 | 安装方式 |
|------|----------|------|----------|
| Docker Desktop | ≥ 4.x | 运行 PostgreSQL 容器 | https://www.docker.com/products/docker-desktop |
| Python | ≥ 3.13 | 后端运行时 | https://www.python.org 或 Homebrew `brew install python` |
| uv | ≥ 0.11 | Python 依赖管理 | `curl -LsSf https://astral.sh/uv/install.sh \| sh` |
| Node.js | ≥ 22 LTS | 前端运行时 | https://nodejs.org 或 `brew install node` |
| pnpm | ≥ 10 | 前端包管理 | `npm install -g pnpm` |

> **不需要** 手动安装 Python 依赖，`uv` 会自动处理。  
> **不需要** 全局安装 PostgreSQL，数据库跑在 Docker 容器里。

---

## 目录结构

```
tt-lims-platform/
├── .env                    # 环境变量（不提交 git）
├── .env.example            # 环境变量模板
├── docker-compose.dev.yml  # 开发用 Docker 配置（后端容器化运行时用）
├── backend/                # FastAPI 后端
│   ├── app/
│   │   ├── api/v1/         # 路由（lims/ 看板接口，admin/ 管理员接口）
│   │   ├── services/       # 业务逻辑（SQL 查询）
│   │   ├── schemas/        # Pydantic 响应模型
│   │   └── core/           # 配置、数据库连接
│   ├── alembic/            # 数据库迁移脚本
│   └── pyproject.toml      # Python 依赖声明
├── frontend/               # Next.js 前端
│   ├── app/
│   │   ├── dashboard/      # 看板页面（overview/workload/cycle-time/overdue/samples/monthly）
│   │   └── admin/          # 管理员后台
│   ├── components/         # 公共组件
│   └── lib/api.ts          # axios 封装 + 所有接口类型和函数
└── docs/
    ├── README.md           # 本文件
    └── migration-log.md    # 环境搭建 & 数据库迁移记录
```

---

## 环境变量（.env）

在项目根目录创建 `.env`，参考 `.env.example`：

```dotenv
# 只读账号，用于看板数据查询（app_rd schema 视图）
DATABASE_URL=postgresql+asyncpg://lims_reader:<密码>@localhost:5432/cmc_data_platform

# 读写账号，用于管理员后台（meta.dim_method / meta.dim_employee）
ADMIN_DATABASE_URL=postgresql+asyncpg://lims_admin:<密码>@localhost:5432/cmc_data_platform

# 管理员后台登录密码
ADMIN_PASSWORD=<自定义密码>

# 应用配置（通常不需要改）
APP_ENV=development
APP_HOST=0.0.0.0
APP_PORT=8000
LOG_LEVEL=INFO
APP_SCHEMA=app_fastapi
```

| 字段 | 必填 | 说明 |
|------|------|------|
| `DATABASE_URL` | 是 | 只读账号，看板查询用 |
| `ADMIN_DATABASE_URL` | 是 | 读写账号，管理员后台用；若留空则管理员接口报错 |
| `ADMIN_PASSWORD` | 是 | 前端 `/admin` 页面的登录密码 |
| `APP_ENV` | 否 | `development` / `production` |
| `LOG_LEVEL` | 否 | `DEBUG` / `INFO` / `WARNING` |

---

## 首次启动

### 1. 确认数据库容器已运行

```bash
docker ps | grep postgres16
```

如果没有输出，启动容器：

```bash
docker start postgres16
```

容器不存在则参考 `docs/migration-log.md` 的「新机器迁移」章节重建。

### 2. 安装后端依赖

```bash
cd backend
uv sync
```

首次运行会自动创建虚拟环境并安装所有依赖，后续无需重复执行（除非 `pyproject.toml` 有变化）。

### 3. 安装前端依赖

```bash
cd frontend
pnpm install
```

---

## 日常启动（开发）

需要开两个终端窗口：

**终端 1 — 后端**（在 `backend/` 目录）：
```bash
uv run uvicorn app.main:app --reload
```
服务地址：`http://localhost:8000`  
Swagger 接口文档：`http://localhost:8000/docs`

**终端 2 — 前端**（在 `frontend/` 目录）：
```bash
pnpm dev
```
访问地址：`http://localhost:3000`

> 启动顺序不强制，但后端未启动时前端会显示「数据加载失败」。

---

## 看板页面

进入后自动跳转 `/dashboard/overview`。侧边栏有**日期范围选择器**和**检验组多选**，筛选状态通过 URL 参数传递，所有页面共享。

| 页面 | 路径 | 主要内容 |
|------|------|----------|
| 概况 | `/dashboard/overview` | 到样/完结/未完成 KPI 卡片 + 月度趋势折线图 + 项目分布饼图 + 方法分布条形图 + 待检测 CSV 导出 |
| 员工工时 | `/dashboard/workload` | 送检/已完成/未完成工时 KPI + 员工工时条形图 + 方法工时饼图 + 明细表（可导出 CSV）；口径切换按钮（送检/已完成/未完成） |
| 检验周期 | `/dashboard/cycle-time` | 近 N 月平均/中位/最长周期趋势 + 重点方法检测时限达标分析 + 按方法汇总明细表 |
| 超期未检 | `/dashboard/overdue` | 4 类超期计数 KPI + 未完成检项方法分布饼图 + 未送样检项方法分布饼图 |
| 样本总览 | `/dashboard/samples` | 分页样本列表，支持状态筛选（全部/已完成/检验中/未送检）和项目编号搜索 |
| 方法月报 | `/dashboard/monthly` | 近 N 月按方法完结检项数和标准工时堆叠柱状图 + 数据透视表（可导出 CSV） |

### 未定义标准工时警告

工时页面如果出现橙色警告横幅「以下 method_code 未定义标准工时，已按 0 计入」，说明数据库中有检项用了未在 `meta.dim_method` 登记的方法编码。需进入管理员后台补录对应方法的标准工时。

---

## 管理员后台

访问 `http://localhost:3000/admin`，输入 `.env` 中 `ADMIN_PASSWORD` 的值。

登录后 token 存在浏览器 `sessionStorage`，关闭标签页后需重新登录。

### 检验方法（`meta.dim_method`）

| 操作 | 方式 |
|------|------|
| 查看 | 进入「检验方法」标签，列出全部方法编码、名称、标准工时（分钟/样）、检测时限（工作日） |
| 编辑 | 鼠标悬停某行，点击铅笔图标，内联修改后回车或点 ✓ 保存 |
| 新增 | 点击「新增」按钮，填写方法编码（必填）、名称、标准工时、检测时限后保存 |
| 批量导入 | 点击「导入 Excel」，选择 `standard_worktime.xlsx`，自动读取 `method_hours` 工作表，按方法编码 upsert |

**字段说明：**
- `method_code`：与 LIMS 数据库中的方法编码一致（主键，必填）
- `method_name`：显示名称
- `std_minutes`：标准工时，单位分钟/样，用于工时统计
- `target_days`：检测时限，单位工作日，用于超期分析（重点方法填写）

### 检验人员（`meta.dim_employee`）

| 操作 | 方式 |
|------|------|
| 查看 | 进入「检验人员」标签，列出全部员工 ID、姓名、部门 |
| 编辑 | 内联编辑姓名和部门 |
| 新增 | 填写员工 ID（必填）、姓名、部门后保存 |
| 批量导入 | 同一 Excel 文件，读取 `testers` 工作表，按员工 ID upsert |

---

## 数据库账号

| 账号 | 权限 | 用途 |
|------|------|------|
| `postgres` | 超级用户 | 运维管理，不用于应用 |
| `lims_reader` | SELECT on `app_rd` / `staging_rd` / `raw_rd_lims` / `meta` | 看板数据查询 |
| `lims_admin` | SELECT + INSERT + UPDATE + DELETE on `meta` | 管理员后台读写 |

数据库：PostgreSQL 16，Docker 容器 `postgres16`，端口 5432，库名 `cmc_data_platform`

---

## 常见问题

**Q: 前端显示「数据加载失败，请确认后端服务已启动」**  
A: 检查后端是否在运行（`http://localhost:8000/docs` 能否打开），以及 `frontend/.env.local` 中 `NEXT_PUBLIC_API_BASE_URL` 是否正确。

**Q: 工时数据全是 0**  
A: `meta.dim_method` 表中没有录入标准工时数据，进入 `/admin` 批量导入或手动录入。

**Q: 管理员后台登录后立即失效**  
A: `sessionStorage` 是标签页级别的，刷新不丢失，但新标签或关闭后需重新登录——这是预期行为。

**Q: `uv sync` 报错找不到 Python 3.13**  
A: 运行 `uv python install 3.13` 后重试。

**Q: 后端启动报 `greenlet` 相关错误**  
A: `uv sync` 重新同步依赖，`greenlet` 是 SQLAlchemy async 必须的显式依赖。
