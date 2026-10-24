# QAP-DDM-001 质量分析平台 数据模型详细设计

**Quality Analysis Platform — Detailed Data Model**

| 字段 | 值 | 字段 | 值 |
|---|---|---|---|
| **文档编号** | QAP-DDM-001 | **版本** | V2.0 |
| **状态** | 草稿（待评审） | **日期** | 2026-06-17（2026-09-16 命名增补） |
| **编制** | CMC 数据团队 | **密级** | 内部 |

## 修订记录

| 版本 | 日期 | 修订内容 |
|---|---|---|
| V1.0 | 2026-05-13 | 初稿（单库 `cmc_data_platform` 五层 + `app_unified`/`qap_config` 设想） |
| V2.0 | 2026-06-17 | **对齐 CMAB-DA-WP-001 V0.3**：落库改 `cmc_analytics`；分层改 raw 库→staging→mart(星型)+dim；删 `app_unified`（UNION ALL 不成立）；规格改读 `dim.spec_master`；`batch_number`→`batch_id`；权限改只读；QAP 应用配置去向标注为待决策。V1.0 已归档至 `docs/_archive/`。 |
| V2.0 增补 | 2026-09-16 | 按白皮书 V0.4 D13，业务批号标准名称改为 `batch_number`；保留历史修订记录，区分内部主键与源字段，标明代码适配待办。本次仅同步批号命名与权威引用，不代表全部 V0.4 差异已完成对齐。 |

---

# 0. 权威依据

本文档从属于公司数据架构白皮书 **CMAB-DA-WP-001 V0.4**（`../../CMAB_Data_Architecture_Whitepaper_V0_4.md`，含 2026-09-16 D13 增补），并与 **QAP-SAD-001 V2.0** 配套。凡冲突以白皮书为准。基准为白皮书**目标态**；本次仅对齐批号命名，§10 的日期为历史现状快照，其余架构差异仍待复核。

# 1. 概述

## 1.1 目的
定义 QAP 所**消费**的数据模型。注意：QAP 是**纯只读消费者，不创建/写入任何数据库对象**。本文档描述的 `dim`/`staging`/`mart` 等对象**由数据中台维护**；QAP 仅需理解其结构以编写 SQLAlchemy 只读模型与查询。应用配置策略见 §7。

## 1.2 读者
- 后端开发：据本文编写只读 SQLAlchemy 模型与查询
- DBA/运维：按白皮书 Part IV 配置 QAP 只读账号
- 数据中台：据 QAP 需求确认 mart 事实表字段

## 1.3 术语
- PK/FK/IDX/UQ = 主键/外键/索引/唯一约束
- RD = 研发实验室；QC/GMP = 质量/GMP（LabVantage）
- CPV = 持续工艺验证；CQA = 关键质量属性

# 2. 数据架构总览

## 2.1 分层（对齐白皮书 §2.1，跨库 + schema 隔离）

与 V1.0「单库五层」不同，实际是**多库 + schema 分层**：

| 层 | 位置 | 维护方 | QAP 权限 |
|---|---|---|---|
| 原始层 | `cmc_rd.raw_*` / `cmc_gmp.raw_*` | 中台 ETL | 无（QAP 不碰 raw 库） |
| 清洗层 | `cmc_analytics.staging` | 中台 | 只读（明细回溯） |
| 维度字典 | `cmc_analytics.dim` | 中台 | 只读 |
| 分析就绪层 | `cmc_analytics.mart`（星型） | 中台 | **只读，主消费** |
| GMP/MDM 快照 | `cmc_analytics.snap_gmp` / `snap_mdm` | 中台 | 只读 |

> QAP 不持久化应用配置（§7），全程只读，无任何写库。

## 2.2 数据流
原始层（各 raw 库）→ ETL → `cmc_analytics.staging` →（聚合/透视）→ `cmc_analytics.mart`。维度字典 `dim` 在同库供 staging/mart JOIN（零 FDW）。GMP 数据经 `snap_gmp` 快照进入分析。QAP 只读 `mart`/`dim`/`snap_*`。

## 2.3 跨域关联键
**`batch_number`**（VARCHAR(32)，公司既有业务批号，端到端不重编）是标准化模型的批次关联字段。跨源关联前须核验源字段语义、批号质量和记录粒度，不能仅凭同名字段拼接或假定历史批号全局唯一；核验后以 `batch_number` 关联，**不建 crosswalk、不造 global_batch_id**（白皮书铁律 #6、D13）。

> **2026-09-16 D13 决策：**业务批号统一为 `batch_number`，不新增同义 `batch_id` 列。当前 QAP 代码仍将 `s.batch_number AS batch_id` 并向前端返回 `batch_id`，需后续同步调整查询、接口、前端与测试；本次仅改文档。已有内部数字 `batch_id` 主外键（如批号登记系统）、源系统/raw 原字段不改，历史接口须盘点消费者后兼容适配。

# 3. 维度字典层（`cmc_analytics.dim`）

白皮书 Part III 定义的维度字典，QAP 只读消费。关键表：

| 表 | 内容 | QAP 用途 |
|---|---|---|
| `project_dict` | 项目简表（来源 snap_mdm/手工） | 项目筛选/标签 |
| `product_master` | 产品 | 产品维度 |
| `method_master` | 检测方法（method_code、std_minutes、target_days） | 方法维度、周转基准 |
| `test_item_master` | 检测项目 | 趋势/放行的检测项维度 |
| `cqa_master` | CQA 字典 | CQA 趋势/类 APR |
| **`spec_master`** | **规格（检测项→上下限，~500）** | **控制限/规格符合性（取代 V1.0 的 qap_config.control_limits）** |
| `equipment_master` | 设备主数据（source_instance 唯一） | CPV 工艺设备维度 |
| `unit_master` | 单位 + 换算 | 单位归一 |
| `employee_master` | 人员 | 操作人维度 |

> **重要变更**：V1.0 设想 QAP 自建 `qap_config.control_limits` 存规格上下限。实际公司规格主数据归 **`dim.spec_master`**（准入 C03：主数据从权威源读）。QAP **改为只读 `dim.spec_master`**，不再自建控制限表。

# 4. 清洗层（`cmc_analytics.staging`）

中台清洗层，跨源统一命名、单位统一、时间轴对齐。白皮书目标骨架：

| 表 | 内容 |
|---|---|
| `stg_batch` | 批次注册（batch_number、产品、工艺、状态、时间） |
| `stg_quality_result` | 质量检测结果（跨两套 LIMS 统一结构） |
| `stg_process_timeseries` | 工艺时序（USP/DSP/DP） |
| `stg_dsp_peak` | 层析峰数据 |

QAP 通常不直接查 staging（性能与稳定性原因），仅在 mart 不满足时做明细回溯。`stg_quality_result` 的概念结构（统一后）：`batch_number, project_id, attribute(标准化), value_num, value_str, unit, method_code, test_date, sample_type, test_type, timepoint, timepoint_unit, source_system`。

> ⚠️ 现状：实际库 staging 仍是旧表 `stg_sample/stg_test/stg_result`（三表关系模型），目标骨架尚未落地。见 §10。

# 5. 应用就绪层（`cmc_analytics.mart`，星型）— QAP 主数据源

白皮书 mart 采用**星型** `dim_*`/`fct_*`/`kpi_*`，BI/QAP 直接消费。QAP 各模块所需事实表：

## 5.1 核心事实表

| 表 | 粒度 | 关键字段 | 服务模块 |
|---|---|---|---|
| `fct_quality_result` | 每检测结果一行 | `batch_number, test_item_code, test_value, value_str, unit, spec_lsl, spec_usl, test_date, source_system` | 趋势、相似性 |
| `fct_stability_result` | 研究×时间点×属性 | `protocol_id, storage_condition, time_point, test_value, batch_number` | 稳定性 |
| `fct_batch_release` | 批次×检测项 | `batch_number, test_item_code, test_value, spec_status, release_status` | 批次放行对比 |
| `fct_batch_summary` | 每批次一行（透视） | `batch_number, product_code, <质量属性列>, <工艺统计列 temp_mean/ph_mean/...>` | CPV |
| `fct_cqa_summary` | CQA×产品×周期 | `cqa_code, product_code, period, value_stats, oot_count` | CQA 趋势/类 APR |

## 5.2 维度表（mart 内）
`dim_batch`（目标批次维度，业务关联键 `batch_number`，主键/唯一性按批次粒度核验）、`dim_product`、`dim_equipment`、`dim_stability_protocol` 等，供事实表星型关联。此处为目标模型，不表示现有 `mart.dim_batch` 视图或内部数字主键已改名。

## 5.3 现有 LIMS 看板视图
`mart` 已有 7 个运营视图（`v_sample_overview`、`v_completed_tests`、`v_pending_tests`、`v_test_task_monitor`、`v_daily_workload`、`v_overdue_snapshot`、`v_turnaround_time`）+ `dim_employee`/`dim_method` 视图，供「实验室运营」模块直接复用。

> **已删除**（V1.0 设想，白皮书无）：`app_rd`/`app_qc` schema 及其视图、`app_unified` 跨域视图。跨域统一在 mart 内以 `batch_number` + `source_system` 完成，不需要 `app_unified`。

# 6. 原始层（仅说明，QAP 不访问）

QAP **不读取** raw 库；列此仅为追溯数据来源。

- R&D：`cmc_rd.raw_rd_lims_samplemanager.{sample, test, result}`（SampleManager 原样抽取，字段保留大写源命名）
- GMP：`cmc_gmp.raw_gmp_lims_labvantage.{batch, sample, result}`（LabVantage，batch 46/sample 46/result 39 字段）
- 工艺：`cmc_rd.raw_rd_usp_lucullus`（Lucullus，含 signal_timeseries）

# 7. 应用配置策略：QAP 为纯只读消费者（无写库）

**决策（2026-06-17）**：QAP **不持久化任何应用配置到数据库**，是 100% 只读消费者。这彻底规避了"应用本地可写配置无处安放"的治理难题，并使 QAP 完全符合白皮书"消费方对 `cmc_analytics` 只读"的规则。

| 原 V1.0 设想 | V2.0 处理 |
|---|---|
| `qap_config.control_limits`（规格上下限） | **取消**，改只读 `dim.spec_master`（§3，权威主数据） |
| `qap_config.analysis_preset`（用户保存的筛选/参数预设） | **取消该功能**。页面每次以默认设置打开，用户自行选择筛选条件 |

**带来的好处**：无需新建可写库/schema、无需审批例外、无 Alembic 应用迁移、后端无写路径。

**筛选状态便利（前端方案，不碰数据库）**：为减少"每次重选"的不便，前端**可选**用浏览器 `localStorage` 记住用户上次的筛选条件，下次打开自动恢复。该方案纯客户端、不涉及后端与数据库、无治理影响。局限：仅对"同一浏览器/设备"有效，不支持命名多套预设；满足 MVP 即可。若未来确需服务端预设，再单独评审落位（届时按白皮书 §9.2 补入修订记录）。

# 8. 数据库权限模型（对齐白皮书 Part IV）

| 数据对象 | QAP 权限 | 说明 |
|---|---|---|
| `cmc_analytics.{mart,dim,staging,snap_gmp,snap_mdm}` | SELECT | 只读消费 |
| `cmc_analytics.meta.access_audit_log` | INSERT/SELECT | 访问审计 |
| `cmc_rd.*` / `cmc_gmp.*` | 无 | 不访问 raw 库 |

> QAP 无任何写库需求（§7）；不申请写权限。筛选状态便利由前端 `localStorage` 实现。

- QAP 作为消费方 = **`cmc_analytics` 只读**（白皮书 Part IV）。
- **已废除**（V1.0 §8）：`qap_reader`/`qap_writer`/`etl_rd_user`/`etl_qc_user`——实测均不存在；不新建。实际只读账号沿用中台角色（如 `lims_reader`/`quality_user`，具体由 DBA 按 Part IV 分配）。

# 9. 索引与性能
QAP 不维护中台索引。查询性能依赖 mart 星型设计与中台索引策略。CPV 等重聚合走 `fct_batch_summary`（建议中台实现为物化视图 + `REFRESH ... CONCURRENTLY`，刷新随 ETL/快照同步）。QAP 侧仅做：合理分页、避免 N+1、必要时 Redis 缓存（Phase 4）。

# 10. 现状缺口与待办（实测 2026-06-17）

| 项 | 现状 | 目标 | 待办 |
|---|---|---|---|
| `dim` 维度字典 | 未建表 | 见 §3 | 等中台 Step 4（Month 2）；`spec_master` 是规格依赖 |
| `mart` 事实表 | 仅 7 个 v_* 看板视图 | §5 的 `fct_*`/`dim_*` | **核心依赖，尚未建**；需与中台对齐字段 |
| `staging` 表名 | `stg_sample/stg_test/stg_result` | `stg_quality_result/stg_batch/...` | 中台 staging 重构中 |
| `snap_gmp` | 待确认是否已建 | GMP 快照 | CPV 依赖；确认快照频率 |
| `dim.spec_master` | 未建 | 规格上下限 ~500 | 取代自建 control_limits 的前提 |
| `batch_number` 一致性 | 2026-09-16 命名核验：LIMS/旧 Excel 导入使用 `batch_number`；当前 QAP 查询与响应仍别名为 `batch_id` | 业务批号标准名统一为 `batch_number`，值不变 | 同步适配接口/前端/测试并核验跨源批号语义；不改内部主外键、raw 源列或历史迁移 |

> QAP 应用配置落位问题已关闭：QAP 纯只读、不写库（§7）。

# 附录 A — 命名规范（对齐白皮书 §2.5）

- 表名：小写下划线、单数、不带厂商前缀
- 主键：`<entity>_id`；业务编码：`<entity>_code`
- 时间戳：`created_at`/`updated_at`/`deleted_at`（TIMESTAMPTZ, UTC）
- 批号：`batch_number`（VARCHAR(32)，公司全局统一）
- 视图：`v_` 前缀；物化视图 `mv_`；事实表 `fct_`；维度表 `dim_`；KPI `kpi_`
- 索引：`ix_<table>_<columns>`；唯一：`uq_<table>_<columns>`

# 附录 B — 跨域关联示意

```
fct_quality_result.batch_number
  = fct_batch_summary.batch_number
  = dim_batch.batch_number
  = snap_gmp.*.batch_number   （GMP 工艺/质量，经快照）
```
上述为目标模型的批次关联示意：先核验源字段语义、批号质量及记录粒度，再经 `batch_number` 在 `cmc_analytics` 内关联，不据字段名直接拼接或假定唯一；无需 app_unified、无需跨实例视图。
