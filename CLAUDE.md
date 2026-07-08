# CLAUDE.md — cmc-rd-usp-dashboard

本文件为 Claude Code 在本仓库工作时提供指引。

## 沟通方式（重要）

和项目负责人对话：用**中文**、尽量**简短**、**避免专业术语**。他不是编程 / 数据库专业出身，遇到技术名词要用一句大白话解释，别默认他懂。

## 这是什么

一个 **USP 上游多源分析看板**。顶部两个视图切换：

1. **工艺曲线**（Lucullus）：看生物反应器 USP 上游工艺的**时序数据**——温度、pH、溶氧、搅拌、气体、液位、泵等 49 个通道随时间变化的曲线，横轴培养小时。数据来自 `rd-lucullus-etl`（工作站 Oracle → PostgreSQL）。
2. **细胞生长曲线**（Vi-CELL）：看 Beckman Vi-CELL XR 细胞计数的**生长曲线**——活细胞密度 + 活率随培养天变化（双轴）。数据来自 `rd-vicell-etl`。

**多源定位**：三者同批次/同罐/同培养天，最终能叠着看。将来还会加生化分析仪结果曲线。
> 「细胞曲线叠加工艺参数(pH/DO/温度)」是 Phase 2，需 Lucullus 侧把 `mart.fact_process_daily` 物化出来（当前空）。

本项目对所有库**只读、不写**。

## 技术栈（对齐 cmc-rd-lims-dashboard）

- **后端**：FastAPI + uvicorn + SQLAlchemy 2.0 + asyncpg（用 `uv` 管理，`backend/pyproject.toml`）。手写 SQL + 参数绑定（见 `routers/signals.py`、`routers/vicell.py`），新代码沿用这个风格。
- **前端**：Next.js 16 + React + `@tanstack/react-query` + `echarts-for-react`。**已建好在用**（`frontend/app/page.tsx` + `components/SeriesChart.tsx`（图）+ `components/CellGrowthView.tsx`（细胞视图））。
  - ⚠️ `frontend/AGENTS.md`：这是改过的 Next.js 16，写前端前先读 `node_modules/next/dist/docs/`。

## 数据在哪、怎么连（关键，先读）

- 数据在 **Linux 虚拟机**上的 PostgreSQL，**同一实例 `rd_pg:5432`（原生运行，非 Docker）的两个库**：
  - `cmc_rd`（原始层）→ 工艺曲线 `raw_rd_usp_lucullus.signal_timeseries`。
  - `cmc_analytics`（分析层）→ 细胞曲线视图 `mart.fact_vicell`。
- SSH：`ssh -p 13568 prometheus@172.19.0.105`
- **Mac 上没有真数据**（只有空表结构；工艺侧本地播了 4 个样本批次，细胞侧本地播了 3 个样本批次仅供本地看 UI）。本地看真数据两条路：
  1. **SSH 隧道**把 Linux 5432 映射到本地（一条隧道同时服务两个库，只换库名）：
     `ssh -N -L 15432:localhost:5432 -p 13568 prometheus@172.19.0.105`
     然后 `RAW_DATABASE_URL=...@localhost:15432/cmc_rd`、`ANALYTICS_DATABASE_URL=...@localhost:15432/cmc_analytics`。
  2. 直接部署到 Linux 上开发（Remote-SSH）。
- **两个连接、同一只读账号 `lims_reader`**（别用写账号 `lucullus_etl`/`vicell_etl`）：
  - 读 `cmc_rd` → 配置项 `RAW_DATABASE_URL`。
  - 读 `cmc_analytics` → 配置项 `ANALYTICS_DATABASE_URL`（留空则细胞视图不可用，工艺曲线不受影响）。
  - ⚠️ 授权走 `cmc-schema-migrations`（alembic），别裸 SQL 授到生产。基线 `deploy/linux-native/scripts/04_grants.sql` 已给 `lims_reader` 授 `cmc_analytics` 各 schema 读权，新视图 `mart.fact_vicell` 的显式补授见迁移 `cmc_analytics_vicell_read_grant`（上线前 `alembic upgrade` 并确认 `has_table_privilege('lims_reader','mart.fact_vicell','SELECT')=t`）。

## 治理规矩（架构白皮书 V0.3，务必遵守）

- **`cmc_rd` 是原始层，只读**。本项目**绝不往 `cmc_rd` 写东西**。
- 如果要算/存分析结果（如批次特征、KPI），放到 **`cmc_analytics`**（分析层），不是 `cmc_rd`。
- **不要字符串解析 `source_instance`**（如 `rd_ws01_usp_lucullus_01`）。要设备/产线信息就 join `meta.equipment_lookup`。
- 部署：Mac 改 → git push → Linux pull → 跑（与其它项目一致）。
- 完整白皮书：`~/code/CMAB_Data_Architecture_Whitepaper_V0_3.md`（新建项目准入清单见 Part V）。

## 数据模型（要查的主表）

`cmc_rd.raw_rd_usp_lucullus.signal_timeseries` —— 每行 = 一个通道在某采样点的值。关键列：

| 列 | 含义 |
|---|---|
| `source_instance` | 哪台工作站（`rd_ws01_usp_lucullus_01` / `rd_ws02_...`）|
| `procid` | 批次编号（Oracle 里的）|
| `procname` | 批次名（当批号用）|
| `reactor_name` | 反应器名（如 A2）|
| `channel_code` | 通道短名（`m_temp` 温度 / `m_ph` / `m_do` 溶氧 / `m_stirrer` 搅拌 …）|
| `time_hours` | 相对批次起点的小时数 |
| `timestamp_from_starttime` | 真实时间（TIMESTAMPTZ，UTC）|
| `value` | 采样值 |
| `unitsymbol` | 单位（如 °C）|

- 主键 `(source_system, source_instance, procid... )`；查单批次走索引 `(source_instance, procid)`，快。
- 一个批次可能有上百万个采样点 → **画图前要降采样**（后端已给示例：按时间分桶取平均）。
- 参考表在同一个 schema 下（`process_src` 批次信息、`reactor_src` 反应器、`logiporttype_src` 通道字典、`unit_src` 单位等），需要更多元信息时 join。
- 目前库里已有数据：ws01 / ws02 的 2025、2026 年批次，约 92 批、3300 万行。更早年份 ETL 那边随时可补。

### 细胞计数（Vi-CELL）

`cmc_analytics.mart.fact_vicell`（视图）—— 每行 = 某批次某罐在某培养天的一次取样。关键列：

| 列 | 含义 |
|---|---|
| `batch_key` | 批次身份 = `项目_批号_罐`，如 `0071_R2601_B2`，一条生长曲线的唯一 id |
| `project_id` / `batch_number` / `bioreactor_id` | 项目编号 / 批号(R+4位) / 罐号 |
| `culture_day` | 培养天（生长曲线横轴）|
| `viable_per_ml` | 活细胞密度（×10⁶/ml，纵轴一）|
| `viability_pct` | 活率（%，纵轴二）|
| `total_per_ml` / `avg_diameter_um` / `avg_circularity` | 总密度 / 直径 / 圆度 |
| `lucullus_procid` / `batch_starttime` … | 工艺关联字段（来自 `mart.dim_batch`，只有约 61 批有；Phase 2 叠图用）|

- 规模：共 ~18,473 样本，其中 ~15,361 带 `culture_day`、覆盖 ~1,389 批次 = 能画生长曲线的范围。
- 数据质量：历史 `sample_id` 命名杂，约 84% `parse_status` 为 suspect/unparseable，按批次看只覆盖能拆出 `batch_key` 的那部分（**这是数据本身限制，不是 bug**）。
- 后端接口只取 `batch_key` 非空且 `culture_day` 非空的批次；`batch_year` 从批号 `R2601→2026` 在 SQL 里解析（多数批次没关联 dim_batch，别指望 `batch_year` 列）。

## 运行（后端）

```bash
cd backend
uv sync
uv run uvicorn app.main:app --reload --port 8070
# 打开 http://localhost:8070/docs 看接口
```

先复制 `.env.example` 为 `.env` 并填好 `RAW_DATABASE_URL`（工艺曲线，必填）与 `ANALYTICS_DATABASE_URL`（细胞曲线，选填）。两者走同一 SSH 隧道 / Linux 本机，只换库名。前端 `cd frontend && npm run dev`（端口 5170）。
