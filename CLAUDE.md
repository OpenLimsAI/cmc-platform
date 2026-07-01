# CLAUDE.md — cmc-rd-usp-dashboard

本文件为 Claude Code 在本仓库工作时提供指引。

## 沟通方式（重要）

和项目负责人对话：用**中文**、尽量**简短**、**避免专业术语**。他不是编程 / 数据库专业出身，遇到技术名词要用一句大白话解释，别默认他懂。

## 这是什么

一个**看板 / 分析应用**，用来看 Lucullus 生物反应器（USP 上游工艺）的**时序数据**——温度、pH、溶氧、搅拌、气体、液位、泵等 49 个通道随时间变化的曲线，支持跨批次对比、异常查看等。

数据由**另一个项目 `rd-lucullus-etl`** 从工作站 Oracle 同步进 PostgreSQL，本项目**只读、不写原始数据**。

## 技术栈（对齐 cmc-rd-lims-dashboard）

- **后端**：FastAPI + uvicorn + SQLAlchemy 2.0 + asyncpg（用 `uv` 管理，`backend/pyproject.toml`）
- **前端**：Next.js 16 + React + `@tanstack/react-query` + `echarts-for-react`（画时序曲线）+ `@base-ui/react`
- 前端还没建：在新窗口里 `cd frontend && npx create-next-app@latest .` 起步，再加 `echarts-for-react`、`@tanstack/react-query`。

## 数据在哪、怎么连（关键，先读）

- 数据在 **Linux 虚拟机**上的 PostgreSQL：`cmc_rd` 库（`rd_pg:5432`，原生运行，非 Docker）。
- SSH：`ssh -p 13568 prometheus@172.19.0.105`
- **Mac 上没有这份数据**（只有空表结构）。本地开发要看到真数据，两条路选一：
  1. **SSH 隧道**把 Linux 的 5432 映射到本地，后端连隧道（开发期最简单）：
     `ssh -N -L 15432:localhost:5432 -p 13568 prometheus@172.19.0.105`
     然后 `RAW_DATABASE_URL=postgresql+asyncpg://<只读账号>:<口令>@localhost:15432/cmc_rd`
  2. 直接把应用部署到 Linux 上开发（Remote-SSH）。
- **只读账号**：别用 ETL 的写账号 `lucullus_etl`。用一个只读角色（如 `lims_reader`）。⚠️ 上线前先确认该角色对 `raw_rd_usp_lucullus` 有 `SELECT` 权限（`cmc-schema-migrations/deploy/linux-native/scripts/04_grants.sql` 里核对，没有就补授或新建只读角色）。

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

## 运行（后端）

```bash
cd backend
uv sync
uv run uvicorn app.main:app --reload --port 8040
# 打开 http://localhost:8040/docs 看接口
```

先复制 `.env.example` 为 `.env` 并填好 `RAW_DATABASE_URL`（走 SSH 隧道或 Linux 本机）。
