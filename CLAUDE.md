# CLAUDE.md — cmc-rd-usp-dashboard

本文件为 Claude Code 在本仓库工作时提供指引。

## 沟通方式（重要）

和项目负责人对话：用**中文**、尽量**简短**、**避免专业术语**。他不是编程 / 数据库专业出身，遇到技术名词要用一句大白话解释，别默认他懂。

## 这是什么

一个 **USP 上游多源分析看板**，全站只有一页，交互分两层（负责人 2026-09-08 定稿）：

1. **先选批次（看谁）**——左栏全站唯一的筛选：项目编号 → 批次年份 → 批号（可多选）→ 罐号（可多选，默认全部）。
   选出的批次集合就是"要看的对象"，右侧所有板块共用；板块切换绝不动这里的选择。
2. **再选看什么**——右栏板块开关，可同屏多开、多批次叠加：
   - **生长曲线**（Vi-CELL 细胞密度 / 活率，按培养天，`rd-vicell-etl`）
   - **生化曲线**（Nova FLEX2 葡萄糖 / 乳酸 / 氨 / 谷氨酰胺 / 谷氨酸 / 钠 / 钾 / 钙，按培养天，`rd-nova-etl`）
   - **血气分析**（同样来自 Nova FLEX2：pH / 氧分压 / 二氧化碳分压，2026-09-09 从生化里拆出来单独一张图）
   - **工艺参数（按时段）**（Lucullus 温度 / pH / 溶氧…每 N 小时一格取平均，24/12/6/3/1h 可切，**默认 6h**（负责人 2026-09-08 定，日均太粗）。
     接口 `GET /api/process-bucketed`（`routers/signals.py`）直接从原始时序现算，指标→通道按字典 `canonical_key` 归并，两个工作站都对；
     **不用** ETL 的日均表 `mart.fact_process_daily`（那张表只认 ws01 通道名，且一天一点），日均表现在只给「数据表」板块用）
   - **工艺时序（全量）**（Lucullus 按小时原始采样，78 个通道，放大自动加载更细的点）
   - 同一批次有多段工艺记录（中途重开，`lucullus_runs` 长度 >1）时，两个工艺板块都**按真实开始时间先后接续**画（`lib/batches.ts` `runOffsets`），
     不是都从 0 小时叠在一起；按时段板块在段与段的空档处断线。
   - **数据表**（一行 = 一个批次一个培养天，三源列并排，对齐《项目第一表》）
   - **取样明细**（每次取样一行）

   另有独立页面 **数据录入**（`/usp/entry`，顶栏按钮进出；2026-09-09 起，**本看板唯一会写库的功能**；2026-09-11 从「渗透压录入」
   扩成「数据录入」，每行样品两格：**渗透压** mOsm/kg 100–1000、**葡萄糖** g/L 0.00–20.00）：按日期列出当天该取样的
   全部样品——以**批号登记系统**（rd-batch-registry，`REGISTRY_BASE_URL`，接口 `batches:samples-by-date`）的当天清单为准，再并上
   仪器（Nova / Vi-CELL）当天实测样品；批次 / 罐 / 培养天 / 样品名 / **取样时刻**（自动取自仪器记录，Nova 真 UTC 换北京时间、
   Vi-CELL 表里钟点直接当北京时间——ETL 时区 bug）自动带出，试验员只填数值；同一样品当天仪器记录相隔 ≥2h 自动分成多次取样
   （第二次起样品名带 -T1），时刻/样品名可改，每行「＋」再加一次取样；没取样的行点 × 删（本机记忆、可恢复），临时样品「添加一行」。存 `cmc_analytics.manual.sample_result`（通用人工录入表，含 sampled_at / sample_name，只追加不覆盖，按 (批次, 天, 样品名)
   取最新一行；录入人 = MDM 登录人工号+姓名快照）。曲线上渗透压按自己的取样时刻定位；录入时没填时刻的，画图时自动借同一批次同一天仪器（Nova / Vi-CELL）最早记录的时刻，都没有才放正午（`routers/nova.py` 读时现算，不改库）。生化曲线的「渗透压」线和数据表的渗透压列读视图 `mart.fact_manual_latest`。写库走单独账号 `usp_writer`
   （只对该表有 INSERT），配置项 `MANUAL_WRITE_DATABASE_URL`，留空则录入页不可用。以后滴度等人工指标复用这张表
   （`metric_code`），后端 `routers/manual.py` 的 `METRICS` 登记 + 放开表 CHECK（迁移 `cmc_analytics_manual_metric_gluc`）。

   **人工葡萄糖的取数规则（2026-09-11 负责人定）**：摇瓶 / 摇管常不做生化分析，只用试剂盒单测葡萄糖，仪器不联网采不到，
   所以录入页留了这一格。**同一批次同一培养天，Nova 测了葡萄糖就用仪器值，没测才用人工值**——生化曲线（`routers/nova.py`
   `/series`，人工点带 `gluc_manual=true`，前端画空心标记、提示框标「人工」）和数据表（`routers/overview.py` `/daily-table`，
   `coalesce(仪器, 人工)` + `gluc_manual` 标记，人工值后面标个「人」）都按这个优先级，两种值画同一条葡萄糖线。
   录入页对已有仪器值的格子灰字显示「仪器 x.xx」，仍可填（仪器数据当天没传到时先记着），填了只留档不上图。
   摇瓶摇管一定会上 Vi-CELL，所以批次名单（三源合并）里跑得掉——人工录入**不是**批次名单的来源。

**批次名单是三源合并的**：`GET /api/overview/batches`（`routers/overview.py`）把细胞、生化、工艺（`mart.dim_batch` 中有时序数据的记录）
按 `batch_key` 并成一张总名单，只有工艺没细胞/生化的批次、以及工艺批次名不规范（test610 这类）的批次也在（后者归「未识别」项目，
`batch_key` 用 `lucullus:<工作站>#<procid>` 顶替）。每个批次带 `lucullus_runs`（全部工艺记录段）。
> 旧的 `GET /api/batches`（直接读 `process_src` 解析批次名）前端已不用，仅留给脚本。

本项目对所有库**只读、不写**——唯一例外是上面的人工录入表 `manual.sample_result`（追加写）。

## 技术栈（对齐 cmc-rd-lims-dashboard）

- **后端**：FastAPI + uvicorn + SQLAlchemy 2.0 + asyncpg（用 `uv` 管理，`backend/pyproject.toml`）。手写 SQL + 参数绑定（见 `routers/signals.py`、`routers/vicell.py`），新代码沿用这个风格。
- **前端**：Next.js 16 + React + `@tanstack/react-query` + `echarts-for-react`。文件分工：
  `components/Dashboard.tsx`（主体：筛选状态 + 板块开关）、`BatchFilter.tsx`（左栏筛选）、`CurveSection.tsx`（生长/生化/日均工艺三个按天板块共用）、
  `ProcessTimeseriesSection.tsx`（全量时序，多段叠加 + 缩放取数）、`DailyTable.tsx`、`SamplesSection.tsx`、`SeriesChart.tsx`（echarts 封装）、
  `lib/batches.ts`（排序/显示名小工具）、`lib/metrics.ts`（三源指标表 + **固定配色/线型**）。
  - 曲线区分规则（负责人 2026-09-08/09 定，所有图统一）：**颜色永远跟指标固定**（活率红、活细胞密度蓝、总细胞密度橙黄、
    葡萄糖橙、乳酸绿、温度橙、溶氧绿…），全部实线；**不同罐/批次靠标记形状**（圆/方/三角…）区分，全量时序点太密改用线型
    （实线/虚线/点线）分段。指标按钮本身就是图例（勾上 = 该线颜色），图内不放图例，罐号图例放图正上方。
    曲线上下各留 15% 空白；悬停不加粗，只把其他线变淡。改配色只改 `lib/metrics.ts` 里的表（`color`/`shape`/`axis`）。
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
- **通道的人话名 / 分组 / 单位 / 归并键来自 `cmc_analytics.dim.channel_dict`**（2026-08-17 起，权威在数据库、不在代码里硬编码）。
  后端 `app/channel_dict.py` 读它（进程内缓存 10 分钟；读不到就回退显示 `channel_code`），`/channels` 接口已合并
  `display_name` / `category` / `canonical_key` / `is_preferred` / `sort_order`，另有 `GET /api/channel-dict` 查全表。
  改显示名 = 在 `cmc-schema-migrations` 里写一条 UPDATE 迁移改那张表，**不要**在前端/后端写通道名字典。
  同一物理量在两站/别名下的通道共用 `canonical_key`（如 ws01 的 `m_o2` 与 ws02 的 `m_mfc3` 都是 `mfc3_flow`），做跨站对比按它归并。
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

先复制 `.env.example` 为 `.env` 并填好 `RAW_DATABASE_URL`（工艺曲线，必填）、`ANALYTICS_DATABASE_URL`（细胞曲线，选填）、
`MANUAL_WRITE_DATABASE_URL`（数据录入：渗透压 / 葡萄糖，选填；账号 `usp_writer` 的密码由运维 `ALTER ROLE usp_writer PASSWORD '...'` 设置，
迁移 `cmc_analytics_manual_sample` 建表建角色）、`REGISTRY_BASE_URL`（批号登记系统后端，Linux 上 `http://localhost:8080`；录入页取当天样品清单用）。两者走同一 SSH 隧道 / Linux 本机，只换库名。前端 `cd frontend && npm run dev`（端口 5170）。

## 统一门户 cmab-hub（2026-08-17 起，改前端必读）

- 本系统已挂在统一门户之下：正式入口 **http://172.19.0.105:5100/usp**（Linux 上本系统前后端只听 127.0.0.1，老端口内网不可达）。Mac 本地同样经 `localhost:5100/usp`。
- 前端**自己认前缀** `/usp`：`next.config.ts` `basePath:'/usp'`（含 redirects/rewrites 供直连时用）；`lib/api.ts` `API_BASE` 默认 `/usp`。API 一律相对路径 `/usp/api/...`，由门户 nginx 剥掉前缀转给后端（后端路由不变）。**不要**写死 host:端口，**不要**用不带前缀的绝对路径跳转/引资源。
- 登录态用**全公司统一 key**：`localStorage['cmab_access_token']`（MDM JWT）+ `localStorage['cmab_user']`（MDM 登录响应 user 对象）；同源共享 → 门户登录一次这里免登。别再改回私有 key。 `frontend/.env.local` 的 `NEXT_PUBLIC_API_BASE` 必须是 `/usp`（不进 git，Mac/Linux 都已改）。
- 门户侧配置/路由/部署脚本在 `~/code/cmab-hub`（`nginx/hub-locations.conf`、`deploy/linux/`），约定见其 `CLAUDE.md`。
