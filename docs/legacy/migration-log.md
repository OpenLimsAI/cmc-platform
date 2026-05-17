# 迁移日志 / Migration Log

---

## 当前生产环境（2026-04-21 建立）

### 开发机配置

| 组件 | 版本 | 说明 |
|------|------|------|
| macOS | 26.4.1 arm64 | M5 Pro |
| Docker Desktop | 29.2.1 | 运行所有容器 |
| PostgreSQL | 16（Docker 容器） | 容器名 `postgres16`，端口 5432 |
| Python | 3.13 | 系统级 |
| uv | 0.11.7 | 后端依赖管理 |
| Node.js | 22.22.1 | 前端运行时 |
| pnpm | 10.33.0 | 前端包管理 |

### 数据来源

原始数据库：Win Server 2016 虚拟机，PostgreSQL 16，库名 `cmc_data_platform`

涉及 schema：`app_rd`（视图层）、`staging_rd`（清洗层）、`raw_rd_lims`（原始层）、`meta`（配置层）

### 数据库行数基准（2026-04-21 迁移时）

| 表 | 行数 |
|----|------|
| `raw_rd_lims.sample` | 16,573 |
| `raw_rd_lims.test` | 37,129 |
| `raw_rd_lims.result` | 125,446 |
| `staging_rd.sample_clean` | 16,573 |
| `staging_rd.test_clean` | 37,129 |
| `staging_rd.result_clean` | 100,217 |

| 视图 | 行数 |
|------|------|
| `app_rd.v_test_task_monitor` | 37,129 |
| `app_rd.v_sample_overview` | 16,573 |
| `app_rd.v_turnaround_time` | 37,129 |
| `app_rd.v_overdue_snapshot` | 34,586 |
| `app_rd.v_pending_tests` | 492 |
| `app_rd.v_completed_tests` | 34,094 |
| `app_rd.v_daily_workload` | 6,036 |

---

## 从 Win Server 迁出数据库（原始操作记录）

在 Win Server 上用 `pg_dump` 导出：

```powershell
# 导出结构（含 4 个 schema，不含 postgres 权限语句）
pg_dump -h localhost -U postgres -d cmc_data_platform `
  --schema-only --no-owner --no-privileges `
  --schema=app_rd --schema=staging_rd `
  --schema=raw_rd_lims --schema=meta `
  -f C:\temp\cmc_schema.sql

# 导出数据（全量，约 56 MB）
pg_dump -h localhost -U postgres -d cmc_data_platform `
  --data-only --no-owner --no-privileges --disable-triggers `
  --schema=staging_rd --schema=raw_rd_lims --schema=meta `
  -f C:\temp\cmc_data.sql
```

> `app_rd` schema 全是视图，无需导出数据。

在 Mac 上导入：

```bash
# 将两个 sql 文件传输到 Mac（scp / U 盘均可）
# 进入 postgres16 容器执行导入
docker exec -i postgres16 psql -U postgres -d cmc_data_platform < cmc_schema.sql
docker exec -i postgres16 psql -U postgres -d cmc_data_platform < cmc_data.sql
```

所需 PostgreSQL 扩展：`dblink 1.2`（在导入结构前需先安装）：

```sql
CREATE EXTENSION IF NOT EXISTS dblink;
```

---

## 新机器完整迁移步骤

当需要把整套系统迁移到另一台 Mac（或 Linux 服务器）时，按以下顺序操作。

### 第一步：安装必备工具

```bash
# 安装 Homebrew（macOS）
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

# Docker Desktop：手动下载安装，或：
brew install --cask docker

# Python 3.13
brew install python@3.13

# uv（Python 依赖管理）
curl -LsSf https://astral.sh/uv/install.sh | sh

# Node.js 22 LTS + pnpm
brew install node@22
npm install -g pnpm
```

### 第二步：迁移 PostgreSQL 数据

**在旧机器上导出（Mac 本地）：**

```bash
# 导出结构
docker exec postgres16 pg_dump -U postgres -d cmc_data_platform \
  --schema-only --no-owner --no-privileges \
  --schema=app_rd --schema=staging_rd \
  --schema=raw_rd_lims --schema=meta \
  -f /tmp/cmc_schema.sql
docker cp postgres16:/tmp/cmc_schema.sql ./cmc_schema.sql

# 导出数据
docker exec postgres16 pg_dump -U postgres -d cmc_data_platform \
  --data-only --no-owner --no-privileges --disable-triggers \
  --schema=staging_rd --schema=raw_rd_lims --schema=meta \
  -f /tmp/cmc_data.sql
docker cp postgres16:/tmp/cmc_data.sql ./cmc_data.sql
```

**在新机器上建库导入：**

```bash
# 1. 启动 postgres16 容器（第一次需要 run，之后用 start）
docker run -d \
  --name postgres16 \
  -e POSTGRES_PASSWORD=<postgres超级用户密码> \
  -p 5432:5432 \
  postgres:16

# 2. 建库
docker exec -i postgres16 psql -U postgres -c "CREATE DATABASE cmc_data_platform;"

# 3. 装扩展
docker exec -i postgres16 psql -U postgres -d cmc_data_platform \
  -c "CREATE EXTENSION IF NOT EXISTS dblink;"

# 4. 导入结构和数据
docker exec -i postgres16 psql -U postgres -d cmc_data_platform < cmc_schema.sql
docker exec -i postgres16 psql -U postgres -d cmc_data_platform < cmc_data.sql
```

### 第三步：创建数据库账号

```sql
-- 连接到 postgres16 容器执行：
-- docker exec -it postgres16 psql -U postgres -d cmc_data_platform

-- 只读账号（看板用）
CREATE USER lims_reader WITH PASSWORD '<密码>';
GRANT CONNECT ON DATABASE cmc_data_platform TO lims_reader;
GRANT USAGE ON SCHEMA app_rd, staging_rd, raw_rd_lims, meta TO lims_reader;
GRANT SELECT ON ALL TABLES IN SCHEMA app_rd TO lims_reader;
GRANT SELECT ON ALL TABLES IN SCHEMA staging_rd TO lims_reader;
GRANT SELECT ON ALL TABLES IN SCHEMA raw_rd_lims TO lims_reader;
GRANT SELECT ON ALL TABLES IN SCHEMA meta TO lims_reader;

-- 读写账号（管理员后台用）
CREATE USER lims_admin WITH PASSWORD '<密码>';
GRANT CONNECT ON DATABASE cmc_data_platform TO lims_admin;
GRANT USAGE ON SCHEMA meta TO lims_admin;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA meta TO lims_admin;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA meta TO lims_admin;
```

### 第四步：克隆代码 & 配置环境变量

```bash
# 克隆代码（或从旧机器 scp 整个目录）
git clone <repo-url> tt-lims-platform
cd tt-lims-platform

# 创建 .env
cp .env.example .env
# 编辑 .env，填入数据库密码、ADMIN_PASSWORD
```

### 第五步：安装依赖 & 启动

```bash
# 后端
cd backend && uv sync

# 前端
cd ../frontend && pnpm install

# 启动后端（终端 1，在 backend/ 目录）
uv run uvicorn app.main:app --reload

# 启动前端（终端 2，在 frontend/ 目录）
pnpm dev
```

### 第六步：验证

1. 打开 `http://localhost:8000/docs` — FastAPI Swagger 正常显示
2. 打开 `http://localhost:3000` — 看板页面正常加载数据
3. 打开 `http://localhost:3000/admin` — 能用 `ADMIN_PASSWORD` 登录，方法和人员列表有数据
4. 核对 `app_rd.v_test_task_monitor` 行数与基准值一致

---

## Docker 容器日常管理

```bash
# 查看容器状态
docker ps -a | grep postgres16

# 启动（每次开机后需要）
docker start postgres16

# 停止
docker stop postgres16

# 查看日志
docker logs postgres16 --tail 50

# 进入容器执行 SQL
docker exec -it postgres16 psql -U postgres -d cmc_data_platform
```

> Docker Desktop 设置里可开启「Start Docker Desktop when you log in」，容器设置里可开启「Start when Docker starts」，这样开机自动启动，无需手动 `docker start`。
