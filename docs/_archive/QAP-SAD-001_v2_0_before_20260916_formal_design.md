# QAP-SAD-001 质量分析平台 系统架构设计

**Quality Analysis Platform — System Architecture Design**

| 字段 | 值 | 字段 | 值 |
|---|---|---|---|
| **文档编号** | QAP-SAD-001 | **版本** | V2.0 |
| **状态** | 草稿（待评审） | **日期** | 2026-06-17（2026-09-16 命名增补） |
| **编制** | CMC 数据团队 | **密级** | 内部 |

## 修订记录

| 版本 | 日期 | 修订内容 |
|---|---|---|
| V1.0 | 2026-05-13 | 初稿（基于已废弃的 cmc_database_architecture_v0_1.html 单库设想） |
| V2.0 | 2026-06-17 | **全面对齐公司数据架构白皮书 CMAB-DA-WP-001 V0.3**：落库由单库 `cmc_data_platform` 改为 `cmc_analytics`；删除 `app_rd/app_qc/app_unified/qap_config` schema 设想；跨域统一改为"汇入 cmc_analytics + GMP 走快照"；`batch_number`→`batch_id`；权限改为 `cmc_analytics` 只读；端口改 8040/5140；前端补 Ant Design；新增准入清单符合性附录。V1.0 已归档至 `docs/_archive/`。 |
| V2.0 增补 | 2026-09-16 | 按白皮书 V0.4 D13，业务批号标准名称改为 `batch_number`；保留历史修订记录，区分内部主键与源字段，标明代码适配待办。本次仅同步批号命名与权威引用，不代表全部 V0.4 差异已完成对齐。 |

---

# 0. 权威依据与符合性声明

⚠️ **本文档从属于公司数据架构白皮书，白皮书优先。**

- **权威文档**：`../../CMAB_Data_Architecture_Whitepaper_V0_4.md`（**CMAB-DA-WP-001 V0.4**，2026-09-10，含 2026-09-16 D13 增补）——全公司架构标准。本次仅同步批号命名与权威引用；§10 和附录 A 的其余历史现状/符合性声明尚待按 V0.4 复核，不代表当前实现已全部合规。
- **配套现状清单**：`../../CMAB_Database_Inventory_20260518.md`。
- QAP 即白皮书路线图中的「**LIMS 分析系统**」（Part I、Step 7，Month 6-9）。白皮书已规定其落库（`cmc_analytics`）、消费方式（只读）、数据来源（两套 LIMS）与四类质量分析目标。
- 本文档的数据架构、命名、权限、跨域方案如与白皮书冲突，**以白皮书为准**。准入清单逐条回答见 **附录 A**。

---

# 1. 概述

## 1.1 目的
定义质量分析平台（QAP）的系统架构。QAP 是一个面向 CMC 质量数据的 Web 分析应用，提供交互式统计分析、可视化与报告，覆盖来自两套 LIMS 的 R&D 与 QC/GMP 实验室数据。

## 1.2 范围
- R&D LIMS（SampleManager）数据分析
- QC/GMP LIMS（LabVantage）数据分析
- 跨域分析，含持续工艺验证（CPV）
- 生物工艺参数整合（用于 CPV 及未来 AI/ML）
- 统计计算：趋势、相似性、稳定性、Cpk/Ppk
- 导出与报告（PDF、Excel）

## 1.3 不在范围
- ETL 管道（由独立 ETL 程序维护）
- LIMS 系统管理与数据录入
- 主数据维护（归 MDM Portal 与中台 `dim`，QAP 只读消费）
- ERP/MES 集成（远期）

## 1.4 设计原则
- **只读消费者**：QAP 绝不写入任何 LIMS、raw/staging 或维度层。
- **统一从 `cmc_analytics` 取数**（白皮书治理铁律 #1、#2；准入 C01）。
- **不直接访问 raw 库**（`cmc_rd`/`cmc_gmp` 只放 raw+meta，QAP 不得在 raw 库做 join/分析）。
- **GMP 数据走快照**（`snap_gmp`），不直连 `cmc_gmp` join（准入 C12）。
- **API 优先**：前端一切取数经版本化 REST。
- **无状态后端**：JWT 鉴权，无服务端会话。
- **渐进增强**：先核心模块，再扩展，不返工。

---

# 2. 系统上下文

## 2.1 实例与库拓扑（对齐白皮书 §2.2，已实测确认）

3 个 Docker PostgreSQL 16 实例（Mac 为测试、Linux 为正式，结构同步）：

| 实例 | 端口(Mac/Linux) | 库 | 职责 | QAP 关系 |
|---|---|---|---|---|
| `rd_pg` | 5432 | `cmc_rd` | R&D 原始（raw+meta） | 间接（经 cmc_analytics） |
| `rd_pg` | 5432 | `cmc_analytics` | **跨域分析 + 维度字典** | **QAP 唯一取数库（只读）** |
| `gmp_pg` | 5434 | `cmc_gmp` | GMP 原始 LabVantage（raw+meta） | 间接（经 snap_gmp） |
| `cmab-mdm-postgres` | 15432/5433 | `cmab_mdm` | MDM Portal（Part 11） | 间接（经 snap_mdm 字典快照） |

> ⚠️ 旧库 `cmc_data_platform` 已退役（仅余 cost_accounting/material_mgmt 待迁）；空库 `quality_analysis` 白皮书计划 DROP（L4）——**QAP 一律不使用这两个库**。

## 2.2 外部系统与数据流

```
SampleManager(R&D LIMS, Oracle) → R&D ETL → cmc_rd.raw_rd_lims_samplemanager ┐
LabVantage(GMP LIMS, Oracle)    → QC ETL  → cmc_gmp.raw_gmp_lims_labvantage  ┤
Lucullus(Bioprocess)            → ETL     → cmc_rd.raw_rd_usp_lucullus       ┘
        │
        ▼  (ETL：清洗/单位统一/时间轴对齐；GMP 经 snap_gmp 快照)
   cmc_analytics.staging  →  cmc_analytics.mart (dim_*/fct_*/kpi_* 星型)
        ▲ 维度字典 cmc_analytics.dim（设备/方法/规格/CQA…）
        │
        ▼  只读
   QAP 后端 (FastAPI) → REST /api/v1 → QAP 前端 (React+AntD)
```

- ETL（含两套 LIMS 与 Lucullus）均为**独立程序**，不在 QAP 范围内。
- QAP 仅消费 `cmc_analytics`（`mart`/`dim`/`staging`，必要时只读）。

---

# 3. 组件架构

## 3.1 技术栈（对齐白皮书准入 C13/C14）

| 组件 | 技术 | 职责 |
|---|---|---|
| 前端 | **React + Ant Design + Vite + TypeScript** | 交互看板、图表（Recharts/Plotly）、用户交互 |
| 后端 API | **FastAPI + SQLAlchemy + Pydantic**（Python 3.11+） | REST 端点、查询编排、统计计算、鉴权 |
| 数据库 | PostgreSQL 16（`cmc_analytics`，只读） | 由中台维护；QAP 纯只读、不建表、不写库（见 DDM §7） |
| 缓存 | Redis（Phase 4 可选） | 查询结果缓存 |
| ETL（外部） | 独立 Python 程序 | LIMS/工艺数据抽取（不在本系统范围） |

## 3.2 前端架构
按分析模块分页，每页含独立的筛选面板、图表区、数据表。共享组件：
- `FilterPanel`：项目、批次、方法、日期范围、数据源（R&D / QC / 全部）选择
- `ChartContainer`：Recharts/Plotly 统一封装 + 导出图片
- `DataTable`：可排序/筛选/分页的结果表
- `AnalysisToolbar`：统计参数（置信度、控制限等）通用控件

## 3.3 后端架构
分层模式：
- **API 层** `app/api/v1/`：路由、请求校验、响应序列化
- **服务层** `app/services/`：业务逻辑与统计引擎（`trend_engine`/`similarity_engine`/`cpv_engine`/`stability_engine`）
- **数据访问层** `app/models/`：SQLAlchemy 模型，映射到 `cmc_analytics` 的 `mart`/`dim`（**只读**）
- **Schema 层** `app/schemas/`：Pydantic 请求/响应模型

统计计算集中在服务层，便于从遗留 Streamlit 项目移植已验证的函数。

---

# 4. 数据架构

> 详细表结构见 **QAP-DDM-001 V2.0**。本节为概览。基准为白皮书**目标态**；当前数据库**现状缺口**见 §10。

## 4.1 Schema 映射（QAP 视角，全部位于 `cmc_analytics`）

| Schema | 层 | QAP 用途 | 权限 |
|---|---|---|---|
| `dim` | 维度字典 | 项目/方法/设备/规格(spec_master)/CQA/检测项等主数据 | 只读 |
| `staging` | 清洗层 | 必要时的明细回溯（`stg_quality_result` 等） | 只读 |
| `mart` | 分析就绪 | **主要取数源**：星型 `dim_*`/`fct_*`/`kpi_*` | 只读 |
| `snap_gmp` | GMP 快照 | CPV 等需要 GMP 工艺/质量数据时的来源 | 只读 |
| `snap_mdm` | MDM 快照 | 产品/项目字典（来自 MDM Portal） | 只读 |

> **已删除**（V1.0 的错误设想，白皮书无此 schema）：`raw_rd_lims`/`staging_rd`/`app_rd`/`app_qc`/`app_unified`/`qap_config`，以及"五层都在 `cmc_data_platform` 单库"的假设。

## 4.2 跨域统一方案（取代 V1.0 的 app_unified）

V1.0 设想用同库 `UNION ALL` 视图 `app_unified` 合并两套 LIMS——**物理上不成立**（R&D 在 `rd_pg`、LabVantage 在 `gmp_pg`，跨实例），且违反白皮书 FDW 分级。**正确方案**：

- 两套 LIMS 与工艺数据由 ETL **统一汇入 `cmc_analytics`**（R&D 来自 `cmc_rd`，GMP 经 `snap_gmp` 快照），在 `staging`/`mart` 层完成清洗与合并。
- 跨源批次关联使用 **`batch_number`**（公司既有业务批号，VARCHAR(32)）；先核验源字段语义、批号质量及记录粒度，不据字段名直接拼接或假定历史批号全局唯一。不建 crosswalk、不造 global_batch_id（铁律 #6、D13）。
- QAP 读 `mart` 的星型事实表（如 `fct_quality_result`、`fct_batch_summary`）即获得跨域结果，无需自行跨库。
- GMP 大表分析/AI **严禁 FDW**，必走 `snap_gmp` 物化快照（准入 C12、白皮书 §3.3）。

## 4.3 "QC LIMS" 定位澄清
白皮书 D4：LabVantage 的权威源是 **`cmc_gmp`（GMP 库）**，不是独立的 QC 库；旧 `raw_qc_lims` 已归档。本文档凡提"QC 数据"均指经 `snap_gmp`/`mart` 汇入 `cmc_analytics` 后的 LabVantage 数据。

---

# 5. 分析模块

## 5.1 模块清单

| 模块 | 数据源（mart 事实表） | 关键能力 |
|---|---|---|
| 趋势分析 | `fct_quality_result` + `dim.test_item_master` + `dim_batch` | 控制图(X-bar/R、I-MR)、Nelson 规则、OOT/OOS、回归 |
| 相似性分析 | `fct_quality_result` | 生物类似物可比性、谱图叠加、等效检验(f2/T 检验) |
| 稳定性分析 | `fct_stability_result` + `dim_stability_protocol` | ICH Q1E 效期、Arrhenius、可合并性检验 |
| CPV 看板 | `fct_batch_summary`（质量+工艺）+ `snap_gmp` | 工艺参数×质量属性相关、Cpk/Ppk、分阶段趋势 |
| 批次放行对比 | `fct_batch_release` + `dim_batch` | 多批次横向对比、规格符合性、CoA 数据 |
| 实验室运营 | `mart` 现有 LIMS 看板视图（v_*） | 周转、工作量、积压监控 |

> 与白皮书 Part VI「Phase 0 四类质量分析」对齐：趋势/Cpk/Ppk、稳定性、批次放行对比、CQA 趋势/类 APR。

## 5.2 CPV 架构要点
CPV 需多源数据：工艺参数（来自 `snap_gmp`/工艺 staging 的批次级统计：均值/极值/SD）+ 质量属性（来自 `fct_quality_result`），在 `mart.fct_batch_summary` 以 `batch_number` 合并为每批次一行。CPV 引擎计算 Cpk/Ppk、生成 I-MR 与 X-bar/R、应用 Nelson 规则、支持阶段化趋势（Stage 1 确认 vs Stage 2 监控），输出结构化 JSON 供前端渲染。

## 5.3 数据源选择
每个模块支持 `data_source` 参数：`RD` / `QC` / `ALL`。三者均查询 `cmc_analytics.mart`，由事实表中的 `source_system` 维度过滤（不再像 V1.0 那样切换不同 schema）。

---

# 6. API 设计概览

> 详见 QAP-API-001。

## 6.1 路由结构

| 端点 | 方法 | 鉴权 | 说明 |
|---|---|---|---|
| `/api/v1/samples` | GET | 是 | 分页样品列表（筛选/排序） |
| `/api/v1/results` | GET | 是 | 结果数据（属性/批次/项目筛选） |
| `/api/v1/analysis/trend` | POST | 是 | 趋势分析 |
| `/api/v1/analysis/similarity` | POST | 是 | 相似性/可比性 |
| `/api/v1/analysis/cpv` | POST | 是 | CPV 看板数据 |
| `/api/v1/analysis/stability` | POST | 是 | 稳定性分析 |
| `/api/v1/meta/projects` | GET | 是 | 项目维度（读 `dim`） |
| `/api/v1/meta/methods` | GET | 是 | 方法维度（读 `dim`） |
| `/api/v1/export/{format}` | POST | 是 | 导出（PDF/Excel/CSV） |

## 6.2 约定
- 基础路径 `/api/v1/`，版本前缀。
- 分页：offset/limit，总数放响应头。
- 过滤：GET 用查询参数；POST（分析端点）用结构化 JSON 体。
- **响应信封**：`{ data: [...], meta: { total, page, ... }, errors: [] }`。
- 错误码：标准 HTTP；422 校验失败；业务错误码放 body。
- 鉴权：JWT Bearer（Phase 2 实现；Phase 1 可用 API key）。

---

# 7. 项目结构

| 路径 | 说明 |
|---|---|
| `backend/app/main.py` | FastAPI 入口 |
| `backend/app/api/v1/` | 路由模块（samples/results/analysis/meta/export） |
| `backend/app/core/` | 配置、安全、数据库连接（只读 `cmc_analytics`） |
| `backend/app/models/` | SQLAlchemy 模型（映射 mart/dim） |
| `backend/app/services/` | 业务逻辑：trend/similarity/cpv/stability 引擎 |
| `backend/app/schemas/` | Pydantic 请求/响应 schema |
| `backend/tests/` | pytest 测试 |
| `frontend/src/pages/` | 路由级页面 |
| `frontend/src/components/` | 共享 UI（图表/筛选/表格，基于 Ant Design） |
| `frontend/src/services/` | API 客户端（axios/fetch 封装） |
| `frontend/src/hooks/` | 自定义 hooks |
| `frontend/src/types/` | TypeScript 类型 |
| `docs/` | 架构、数据模型、API、UI 文档 |

---

# 8. 部署架构

## 8.1 目标环境（对齐白皮书准入 C15）
开发在办公 PC（后端 PyCharm + Miniconda，前端 VS Code）→ **Git push** → Linux 正式机 **Docker** 部署。数据库由中台以 Docker PostgreSQL 维护（非应用部署项）。

| 服务 | 运行时 | 端口 | 说明 |
|---|---|---|---|
| QAP 后端 | Uvicorn | **8040** | 端口写死 `--port 8040`，禁止漂移 |
| QAP 前端 | Vite(dev)/Nginx(prod) | **5140** | `strictPort`，Nginx 反代 + TLS |
| PostgreSQL | Docker（中台维护） | 5432(`cmc_analytics`) | QAP 只读连接 |

> 端口依据 `../../PORTS.md`（QAP 编号 40）。V1.0 写的 8000 已被 email-agent 占用，作废。

## 8.2 开发工作流
- Mac 开发 → Git → Linux `git pull` → 跑测试 → 重启服务（Docker）。
- QAP 纯只读、不写库，**无数据库迁移需求**（不引入 Alembic 应用迁移）；更**不得**对中台 `mart`/`dim`/`staging` 发起任何迁移。用户筛选状态的便利由前端 `localStorage` 提供，不落库（见 DDM §7）。

---

# 9. 安全

- **数据库访问**：QAP 以**只读**账号连接 `cmc_analytics`，仅 SELECT。无 raw/staging 写权限，不直连 `cmc_gmp`。具体角色按白皮书 Part IV（消费方 = `cmc_analytics` 只读）；不新建 `qap_*` 角色（V1.0 §8 的 `qap_reader/qap_writer/etl_*` 实际不存在，已废除）。
- **审计**：访问记入 `cmc_analytics.meta.access_audit_log`（FDA/EMA 检查必备，白皮书 §2.8）。
- **API 鉴权**：JWT + RBAC（admin/analyst/viewer）。
- **CORS**：限定已知前端来源。
- **输入校验**：全部经 Pydantic；SQL 一律参数化。
- **网络**：PostgreSQL 仅监听本地/内网；Nginx 终止 TLS。

---

# 10. 现状缺口与依赖（重要）

QAP 文档以白皮书**目标态**描述，但当前数据库尚在迁移中。开发前必须确认以下依赖（实测 2026-06-17）：

| 缺口 | 现状 | 目标（白皮书） | 影响 / 依赖 |
|---|---|---|---|
| `dim` 维度字典 | 尚未建表 | `dim.{spec_master, test_item_master, cqa_master, equipment_master,...}` | 白皮书 Step 4（Month 2）落地；QAP 的规格/CQA 依赖它 |
| `mart` 事实表 | 仅有 7 个 LIMS 看板 `v_*` | `fct_quality_result/fct_stability_result/fct_batch_release/fct_batch_summary/dim_batch` | QAP 分析模块的主数据源，**尚未建** |
| `staging` 表名 | 旧 `stg_sample/stg_test/stg_result` | 统一骨架 `stg_quality_result/stg_batch/...` | 中台 staging 重构未完成 |
| `snap_gmp` 快照 | 待确认是否已建 | GMP 物化快照（CPV 必走） | CPV 模块依赖；需与中台确认快照频率 |
| 时间线 | QAP 排期 Month 6-9（Step 7） | 依赖 dim/mart 先落地（Step 4，Month 2） | QAP 可先搭骨架，数据接入需等中台 |

**结论**：QAP 现阶段可启动应用骨架开发（API/前端/统计引擎），但**真实数据接入须等中台 `dim`/`mart`/`snap_gmp` 就绪**，并按届时实际表名对齐。

---

# 11. 路线图（对齐白皮书 Part VII）

- **Phase 1（MVP）**：FastAPI + React(AntD) 骨架；R&D 趋势/相似性；基础鉴权（API key）。
- **Phase 2**：QC/GMP 数据（经 mart/snap_gmp）；批次放行、稳定性；JWT 鉴权。
- **Phase 3**：CPV 看板 + 工艺数据整合；Cpk/Ppk。
- **Phase 4**：AI/ML（对接 `ml_features`）、高级报告、Redis、多用户 RBAC。

---

# 附录 A — 新建项目准入清单符合性（白皮书 Part V，C01–C15）

| # | 检查项 | QAP 回答 |
|---|---|---|
| C01 | 数据放哪个库/schema？ | `cmc_analytics`（mart/dim/staging/snap_*），**纯只读、不写任何库** ✅ |
| C02 | Schema 命名符合 §2.3？ | 不新建分析 schema；复用中台命名 ✅ |
| C03 | 主数据从哪个权威源读？ | 设备/方法/规格/CQA 从 `cmc_analytics.dim`；产品/项目从 `snap_mdm` ✅ |
| C04 | 需新增主数据？归哪？ | 不新增主数据 ✅ |
| C05 | 业务批号用 `batch_number`？ | D13 目标：VARCHAR(32) 公司既有批号；现有 QAP 代码/API 仍用 `batch_id` 别名，兼容适配与测试待完成 ⏳ |
| C06 | 命名符合 §2.5？ | 小写下划线单数 ✅ |
| C07 | 审计追踪级别？ | 读 `meta.access_audit_log`；应用侧 JWT+RBAC ✅ |
| C08 | GxP 范围？ | R&D/分析工具，不进放行链路（输出属二次使用）✅ |
| C09 | ETL 有 watermark？ | 不适用（QAP 不做 ETL）— |
| C10 | 代码在 GitHub？ | 独立 repo（**待初始化远程**）⏳ |
| C11 | 与现有系统数据重叠？ | 只读消费，LIMS/中台为权威源 ✅ |
| C12 | 需读 GMP 数据？走快照？ | 是，经 `snap_gmp`，不直连 `cmc_gmp` ✅ |
| C13 | 前端技术栈？ | React + Ant Design + Vite ✅ |
| C14 | 后端技术栈？ | FastAPI + SQLAlchemy + Pydantic ✅ |
| C15 | 部署流程？ | Mac → Git → Linux Docker ✅ |

⏳ 待办：C10 远程仓库初始化。

---

# 附录 B — 交付文档清单

- QAP-SAD-001：系统架构设计（本文档，V2.0）
- QAP-DDM-001：详细数据模型设计（V2.0）
- QAP-API-001：API 设计规范（OpenAPI/Swagger）
- QAP-UIA-001：UI 信息架构
- QAP-AMS-001：分析模块规范（算法定义、I/O 契约）
- QAP-PCS-001：项目结构与编码规范
