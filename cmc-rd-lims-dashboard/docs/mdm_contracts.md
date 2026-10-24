# cmc_mdm 契约 — 看板 admin 端依赖的主数据

> 本文是 cmc-rd-lims-dashboard 与 `cmc_mdm` 主数据库的接口约定。
> 看板的 admin 面板（`/admin` 页面）会对下面两张表做 CRUD + Excel 上传，
> 它们也是 mart 层 `dim_method` / `dim_employee` 的上游事实源。
>
> ⚠️ `cmc_mdm` 数据库当前**尚未创建**。本文档同时给出建库 SQL，
> 由 MDM owner 落地后，把 `MDM_DATABASE_URL` 写进看板 `.env` 即可。

## 1. 实例与库

按 v0.1 架构：

| 项 | 规范值 | 当前状态 |
|---|---|---|
| 实例 | `mdm_pg :5433` | ❌ 未启动 |
| 库 | `cmc_mdm` | ❌ 未创建 |
| 账号 | `mdm_admin`（看板 admin 写） / `mdm_reader`（看板 dashboard 读，用于 snap_mdm 同步） | ❌ 未创建 |

> 现存的 `cmab-mdm-postgres :15432`（库 `cmab_mdm`，schema `ars/prs/srs/mm/...`）是另一个独立 MDM 项目，**不是** v0.1 规范的 `cmc_mdm`。两者不要混用。

## 2. Schema 与表

### 2.1 `mdm_quality.method_master`（检验方法主数据）

```sql
CREATE TABLE mdm_quality.method_master (
  method_code   text         PRIMARY KEY,
  method_name   text,
  std_minutes   numeric(6,2),
  target_days   integer,
  -- 治理字段（v0.1 主数据通用）
  is_active     boolean DEFAULT true,
  created_at    timestamptz DEFAULT now(),
  updated_at    timestamptz DEFAULT now(),
  updated_by    text
);
COMMENT ON TABLE  mdm_quality.method_master IS 'CMC 检验方法主数据（迁移自 cmc_data_platform.meta.dim_method）';
COMMENT ON COLUMN mdm_quality.method_master.std_minutes IS '标准检测工时（分钟），用于工时统计';
COMMENT ON COLUMN mdm_quality.method_master.target_days IS '目标周转天数，用于超期判定';
```

**初始数据**（约 79 条）：可从旧库导入：
```bash
docker exec rd_pg pg_dump -U postgres -d cmc_data_platform \
  --data-only --table=meta.dim_method \
  | sed 's/COPY meta.dim_method/COPY mdm_quality.method_master/g' \
  | docker exec -i <mdm_pg> psql -U postgres -d cmc_mdm
```
（导入前需在 `mdm_quality.method_master` 加 `std_minutes/target_days` 列，或调整 COPY 列序）

### 2.2 `mdm_core.employee_master`（员工主数据）

```sql
CREATE TABLE mdm_core.employee_master (
  employee_id    text         PRIMARY KEY,
  employee_name  text,
  department     text         NOT NULL DEFAULT '药学及技术转移部',
  group_id       text,
  status         text         NOT NULL DEFAULT 'active',
  is_active      boolean GENERATED ALWAYS AS (status = 'active') STORED,
  created_at     timestamptz  DEFAULT now(),
  updated_at     timestamptz  DEFAULT now(),
  updated_by     text
);
COMMENT ON TABLE  mdm_core.employee_master IS 'CMC 员工主数据（迁移自 cmc_data_platform.meta.dim_employee）';
COMMENT ON COLUMN mdm_core.employee_master.employee_id IS '员工 ID，对应 raw LIMS 中的 tester / authoriser 字段值';
COMMENT ON COLUMN mdm_core.employee_master.group_id IS '所属检验组（TT1/TT5/PD/...），FK→mdm_core.group_master';
```

**初始数据**（约 29 条）：从旧库 `meta.dim_employee` 同上导入。

### 2.3 完整建库脚本

```sql
-- Step 1: 在 mdm_pg 实例上创建库与角色
CREATE DATABASE cmc_mdm WITH ENCODING='UTF8';
CREATE ROLE mdm_admin  LOGIN PASSWORD 'change_me';
CREATE ROLE mdm_reader LOGIN PASSWORD 'change_me';

\c cmc_mdm

-- Step 2: 建 v0.1 规范的 schema 集
CREATE SCHEMA IF NOT EXISTS mdm_core      AUTHORIZATION mdm_admin;
CREATE SCHEMA IF NOT EXISTS mdm_quality   AUTHORIZATION mdm_admin;
CREATE SCHEMA IF NOT EXISTS mdm_process   AUTHORIZATION mdm_admin;
CREATE SCHEMA IF NOT EXISTS mdm_reference AUTHORIZATION mdm_admin;
CREATE SCHEMA IF NOT EXISTS export        AUTHORIZATION mdm_admin;
CREATE SCHEMA IF NOT EXISTS meta          AUTHORIZATION mdm_admin;

-- Step 3: 建上述两张表（见 §2.1 / §2.2）

-- Step 4: 授权
GRANT USAGE ON SCHEMA mdm_quality, mdm_core TO mdm_admin, mdm_reader;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA mdm_quality, mdm_core TO mdm_admin;
GRANT SELECT ON ALL TABLES IN SCHEMA mdm_quality, mdm_core TO mdm_reader;
ALTER DEFAULT PRIVILEGES IN SCHEMA mdm_quality, mdm_core
  GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO mdm_admin;
ALTER DEFAULT PRIVILEGES IN SCHEMA mdm_quality, mdm_core
  GRANT SELECT ON TABLES TO mdm_reader;
```

## 3. 看板侧配置

`.env`：
```bash
MDM_DATABASE_URL=postgresql+asyncpg://mdm_admin:change_me@<mdm_pg_host>:5433/cmc_mdm
```

看板代码已经按 v0.1 路径写好，连接成功后无需任何 patch 即可工作：
- `app/models/mdm/masters.py` → `MethodMaster` (`mdm_quality.method_master`) / `EmployeeMaster` (`mdm_core.employee_master`)
- `app/api/v1/admin/methods.py` 与 `employees.py` 通过 `get_mdm_db()` 拿 cmc_mdm session

## 4. mart 层与 MDM 的连接

mart 层的 `mart.dim_method` / `mart.dim_employee` 应当**从 cmc_mdm 同步过来**，不是 mart owner 自己维护。建议方式（v0.1 §FDW 分级里"MDM 字典类"对应 `每日快照`）：

```sql
-- 在 cmc_analytics 库里：
-- 选项 A：FDW 视图（实时一致，但跨库）
CREATE FOREIGN TABLE ext_mdm.method_master (...) SERVER mdm_srv;
CREATE VIEW mart.dim_method AS SELECT * FROM ext_mdm.method_master;

-- 选项 B：每日 snap（推荐，字典低变更高查询）
CREATE TABLE snap_mdm.method_master AS SELECT * FROM ext_mdm.method_master;
-- 每日 ETL refresh：
TRUNCATE snap_mdm.method_master;
INSERT INTO snap_mdm.method_master SELECT * FROM ext_mdm.method_master;
-- mart view 走 snap：
CREATE VIEW mart.dim_method AS SELECT * FROM snap_mdm.method_master;
```

## 5. 落地清单

| # | 对象 | 状态 | 备注 |
|---|---|---|---|
| 1 | `mdm_pg :5433` 实例 | ⬜ | 起容器 |
| 2 | `cmc_mdm` 数据库 | ⬜ | |
| 3 | `mdm_admin` / `mdm_reader` 角色 | ⬜ | |
| 4 | 6 个 schema（mdm_core 等） | ⬜ | |
| 5 | `mdm_quality.method_master` 表 + 初始 79 条 | ⬜ | 从旧库导入 |
| 6 | `mdm_core.employee_master` 表 + 初始 29 条 | ⬜ | 从旧库导入 |
| 7 | 配 `MDM_DATABASE_URL` 到看板 `.env` | ⬜ | |
| 8 | （可选）cmc_analytics ←→ cmc_mdm FDW + snap_mdm | ⬜ | mart owner 协作 |
