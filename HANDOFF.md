# 交接说明（新窗口从这里开始）

这个项目是 `rd-lucullus-etl` 的**下游**：ETL 把 Lucullus 工艺时序数据同步进了 `cmc_rd`，本项目做**看板/分析**来用这些数据。骨架已搭好，接着开发即可。

## 已经给你准备好的

- `CLAUDE.md` —— 项目全貌、技术栈、**数据在哪怎么连**、治理规矩、数据模型。**先读它。**
- `backend/` —— 一个能跑的最小 FastAPI 后端（asyncpg 连 `cmc_rd`），已实现 3 个接口：
  - `GET /api/batches` —— 批次列表（含批次名、反应器、起止时间）
  - `GET /api/batches/{source_instance}/{procid}/channels` —— 该批次有哪些通道
  - `GET /api/series` —— 某批次某通道的**降采样**曲线（画图用）
- `.env.example` —— 复制成 `.env` 填数据库连接。
- `docs/` —— 放设计文档。

## 建议的第一步（按顺序）

1. **打通数据连接**：开 SSH 隧道（见 CLAUDE.md），复制 `.env.example` → `.env` 填 `RAW_DATABASE_URL`，跑起后端，在 `/docs` 里点 `GET /api/batches` 看能不能返回批次列表。**先确认能读到真数据**，再往下做。
2. **搭前端**：`cd frontend && npx create-next-app@latest .`，装 `echarts-for-react` + `@tanstack/react-query`。
3. **做第一个页面**：选一个批次 → 选几个通道（温度/pH/溶氧）→ 用 echarts 画出随时间变化的曲线。这就是最小可用版。
4. 之后再加：跨批次对比（多批次同一通道叠加）、批次筛选（按工作站/年份/反应器）等。

## 关键提醒（别踩坑）

- **只读**：本项目绝不往 `cmc_rd` 写。分析结果要落库就放 `cmc_analytics`。
- **别用写账号**：连库用只读角色，不要用 ETL 的 `lucullus_etl`。
- **数据量大**：单批次上百万点，画图前一定降采样（后端 `/api/series` 已做，前端别一次拉全量原始点）。
- **数据只在 Linux**：Mac 本地默认没有这份数据，靠 SSH 隧道连过去。

## 相关项目

- 数据来源 ETL：`~/code/rd-lucullus-etl`
- 结构迁移（谁管数据库表结构）：`~/code/cmc-schema-migrations`（命令 `dbmig`）
- 架构白皮书：`~/code/CMAB_Data_Architecture_Whitepaper_V0_3.md`
- 同类看板（技术栈参照）：`~/code/cmc-rd-lims-dashboard`
