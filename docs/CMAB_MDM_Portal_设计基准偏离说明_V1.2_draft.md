# CMAB MDM Portal 设计基准偏离说明

| 项目 | 内容 |
|---|---|
| 文档编号 | DEV-MDM-001 |
| 版本 | V1.2 Draft |
| 状态 | 待 CMC IT 架构组评审 |
| 上位文档 | DM-MDM-001 V1.1 / ARCH-MDM-001 V1.1 / API-MDM-001 V1.1 / UI-MDM-001 V1.1 |
| 编制 | CMC R&D（实施侧） |
| 日期 | 2026-05-13 |
| 分类 | 合规审计配套文档 |
| 历史 | V1.1 Draft（2026-05-11，覆盖 Phase 1-2.5 + M3.0 回归）<br>V1.2 Draft（2026-05-12，新增 M3.1-M3.4 ARS 资产域 + 跨域引用补齐 + 跨文档检查）<br>V1.2 Draft（2026-05-13 修订一，完整 §7/§8/§9/§11 独立复核 + Batch A/B/D/E/F 落地）<br>V1.2 Draft（2026-05-13 修订二，架构 / API / UI 三上位文档独立复核 + Batch G1.A/G1.B 落地）<br>V1.2 Draft（2026-05-13 修订三，Batch G2 中优先级 8 项落地）<br>V1.2 Draft（2026-05-13 修订四，Batch G3.A 零评审依赖 2 项落地 + 评审会材料就位）<br>V1.2 Draft（2026-05-13 修订五，**V1.2 评审会 13 项决议落地（Batch H）** — H1 migration 0031：P3:A team partial UNIQUE + R8:A ref 三表 created/updated_by 共 6 个 FK；H2 4 新端点：API11:B 部分立即做 `GET /lookups/{type}` + `GET /system/info` + API13:A `PUT /substances/{code}/protein` + `PUT /substances/{code}/adc`；H3 三 UI 改版：UI7:A 项目概览 Tab 加进度条+统计预览+关联跳转、UI8:A 资产阶段 Timeline、UI9:B 物质血缘 Tab（ADC 父结构 + 反向 ADC 引用，新 endpoint `/substances/{code}/lineage`）；B 决议项（S5/S6/P8/ARCH9/API4/API10/API11-rest）按各自方式登记）|

## 1. 文档目的

本版（V1.2）在 V1.1 基础上增补 Phase 3（M3.1-M3.4）实施过程中识别的所有新偏离 / 加强 / 推迟项，并把检查范围从单一的"数据模型设计文档"扩展到 4 个上位文档（数据模型 + 架构 + API + UI 信息架构）。

**2026-05-13 修订说明**：原 V1.2 Draft §2 / §3 声明"SRS / PRS 100% 对齐"，§6.1-§6.4 声明"ARS 100% 对齐"，§4 / §6.5-§6.6 声明"REF 三表 deleted_by 完全统一"。经对 §7 SRS / §8 ARS / §9 PRS / §11 REF 四章独立逐条复核（不依赖原 V1.2_draft 自我声明），共发现 **39 项实质偏离**（不计 agent 自我撤销项与已识别的实施加强）。处置如下：

- **Batch A**：SRS §7 4 项 DB 基线缺口（external_uuid UNIQUE / protein hash 索引 × 2 / xref_value 索引 / internal_code partial 索引）— 已通过 **migration 0028** 回归
- **Batch B**：SRS §7 API/前端表面缺口 — `ProteinExtension` 加 7 字段、`SubstanceXref` 加 effective_date/expiry_date — 已落地后端 schema + 前端表单 + 详情页
- **Batch S8**：SRS §7.7 触发器 GUC 去除 + service 后置 UPDATE 回填 — 已并入 migration 0028
- **Batch D**：ARS §8.4 + PRS §9.5 同款触发器 GUC 去除 + REF §11.2 `fk_ref_ps_deleted_by` FK 补齐 + PRS §9.2 索引命名回归 + `ix_project_dates` 新建 — 已通过 **migration 0029** 回归
- **Batch E**：REF §11.1 `PROJECT_STATUS_FORBID_LINK` service 层校验补齐（terminated project 双侧禁建）— 已落地
- **Batch F**：ARS/PRS/REF 6 项 API schema 表面暴露（A7-A9 / P9-P10 / R6-R7）— ✅ 已落地（2026-05-13）
- **Batch G1.A**：API1 错误码 40404/40405 错配修正 + UI3 签名理由独立字段 + UI4 GxP 关键动作二次确认 — ✅ 已落地（2026-05-13，21 CFR Part 11 §11.50 合规必修，见 §8.5 / §9.4）
- **Batch G1.B**：API2 状态机请求嵌套 `{comment, signature}` + API3 响应 `StateChangeResponse` 硬切回归 V1.1 §6.5/§7.4/§8.x — ✅ 已落地（2026-05-13，**Breaking change** vs V1.0/V1.2_draft §8.2 扁平契约，详见 §8.5）
- **Batch C**：SRS §7.3 `molecular_weight_da / pi_theoretical` NUMERIC 类型回归 — 待评估
- **Batch G2**：API9 补 11 错误码 + API6 全局搜索响应分组 + UI1 Footer/Sidebar 底部 + UI2 偏好设置 + UI5 物质列表筛选 + UI6 列表关联计数 + UI10 PRS 列表 4 过滤接入 + UI11 详情页头部 3 动作 — ✅ 已落地（2026-05-13）
- **Batch G3.A**：ARCH12 meta.lookup_value + meta.system_config 建表 + seed（migration 0030）+ API5 三域 POST 主资源 Location 头 — ✅ 已落地（2026-05-13）
- **Batch G3.B**：ARCH11 API 限流 + API7 Idempotency-Key — 🚧 推迟到 Phase 4（强依赖 Redis 应用层接入）
- **Batch G3.C**：9 项进 V1.2 评审会议（见 `docs/CMAB_MDM_Portal_V1.2_评审会议材料.md`）— ARCH9 前端技术栈 / API4 项目嵌套 / API10 用户角色权限 12 端点 / API11 全局功能 5 端点 / API13 protein/adc 写端点 / UI7 项目概览 Tab 重构 / UI8 资产阶段时间线 / UI9 物质关联 Tab 拆分
- **Batch H（评审决议落地）**：H1 migration 0031（P3:A team partial UNIQUE + R8:A ref 6 FK）+ H2 4 个新 endpoint（API11:B 部分 lookups/system + API13:A protein/adc PUT）+ H3 三 UI 改版（UI7:A 项目概览 / UI8:A 资产阶段 Timeline / UI9:B 物质血缘 Tab） — ✅ 已落地（2026-05-13）
- **B 决议接受/推迟项**：S5/S6（永久接受 Float）+ P8（Phase 5）+ ARCH9（只引入 ECharts+React Flow，Phase 5）+ API4（永久接受扁平 ID）+ API10（Phase 5/6 Admin）+ API11 audit-logs/signatures 部分（Phase 5）— 文档登记，不动代码
- **Batch G3**：架构/API/UI 推迟与评审决策类（API10/API11 用户角色权限端点、ARCH9 前端技术栈、ARCH11 限流、UI7 项目概览 Tab 重构、UI9 物质关联 Tab 拆分等）
- **评审决策类**：P3 team unique 业务语义、P8 project_relationship 上层、各 🟢 加强项吸收等

三类处置标签不变：
- **🟥 待对齐回归**：将通过迁移强制回归至设计基准。
- **🟢 实施侧合理加强**：基于合规要求或工程坑位保留实施版本，建议吸收进上位文档下一版。
- **🟠 未实施 / 推迟**：设计要求但当前阶段未实施的部分，列入后续里程碑。

新增标签：
- **⚠️ API / 前端表面缺口**：DB 字段齐全但 Pydantic schema / 前端未暴露，归 Batch F 集中补。

---

## 2. SRS（§7 物质域）— 2026-05-13 重写

**原声明**："V1.1 §2 全部条目通过 M3.0.3 migration 0018-0021 完成对齐回归。当前实施与 §7 基准 100% 一致。V1.2 新发现项：无。"

**独立复核结果**：13 项偏离，7 项已修，6 项分类推迟 / 待评审。

### 2.1 🟥 待对齐回归（已修 / migration 0028）

| # | §7.x | 设计要求 | 处置 |
|---|---|---|---|
| S1 | §7.2.2 | `uq_substance_external_uuid UNIQUE (external_uuid)` | ✅ migration 0028 `op.create_unique_constraint` 补齐 |
| S2 | §7.3 | `ix_substance_protein_hc_hash` / `ix_substance_protein_lc_hash` B-tree | ✅ migration 0028 补 2 个索引 |
| S3 | §7.6 | `ix_substance_xref_value` B-tree | ✅ migration 0028 补 |
| S4 | §7.2.2 | partial `ix_substance_internal_code WHERE deleted_at IS NULL` | ✅ migration 0028 补（uq 全表 + partial 部分双索引） |

### 2.2 🟥 触发器 GUC 去除（已修 / Batch S8）

| # | §7.x | 设计 vs 实施偏离 | 处置 |
|---|---|---|---|
| S8 | §7.7 | V1.1 §7.7 注释明文："change_reason 由 service 层在 INSERT status_history 后显式 UPDATE 回填，触发器**不依赖** PostgreSQL session GUC"。原实施仍走 `current_setting('app.change_reason')` GUC | ✅ migration 0028 REPLACE `srs.fn_substance_status_change` 改写字面量 `'status changed'`；`backend/app/domains/srs/services.py` 状态机 flush 后 UPDATE 回填 `change_reason + e_signature_id` |

### 2.3 ⚠️ API / 前端表面缺口（已修 / Batch B）

| # | §7.x | DB 现状 vs API 暴露 | 处置 |
|---|---|---|---|
| S10 | §7.6 | DB 已有 `effective_date` / `expiry_date`（migration 0019）但 `SubstanceXrefBase / Update` Pydantic schema 未暴露 | ✅ 后端 schema 加字段、`services.py` create/add/update_xref 透传、`XrefEditor.tsx` 表单加 DatePicker + 列表两列展示 |
| S11 | §7.3 | DB 已有 `additional_chains / disulfide_bonds / expression_vector / pi_theoretical / extinction_coefficient / sequence_hash_hc/lc / sequence_length_hc/lc` 但 `ProteinExtension` 未暴露 | ✅ 后端 schema + `get_by_code` 序列化白名单 + `SubstanceCreate/EditPage` 表单 + `SubstanceDetailPage` 展示 3 行新增 |

### 2.4 🟢 实施侧加强（已实施，建议吸收 V1.1 下一版）

| # | §7.x | 加强内容 | 现状 |
|---|---|---|---|
| S7 | §7.3 | `fn_substance_protein_compute_hash` 算法增强：设计直接 `digest(NEW.heavy_chain_sequence, 'sha256')`，实施先 `regexp_replace(UPPER(seq), '[^A-Z]', '', 'g')` 归一化（与 Python `_hash_sequence` 一致，规避 FASTA 头/换行/大小写抖动） | migration 0021 已实施；建议正式入 V1.1 §7.3 |
| S9 | §7.8 | `srs.substance_alias` 加 `trg_substance_alias_audit`（v2 3-arg parent_ref 回填 substance_code），与 protein/xref/adc/sm 子表保持一致；设计 §7.8 未要求 | migration 0018 已实施；建议正式入 V1.1 §7.8 |

### 2.5 🟠 未实施 / 推迟（写入路线图）

| # | §7.x | 内容 | 计划 |
|---|---|---|---|
| S12 | §7.4 / §7.5 / §7.8 | `substance_adc / substance_small_molecule / substance_alias` 表 + audit 触发器 + FK 已齐全（migration 0018 / 0020），但 `app/domains/srs/services.py` 完全无业务路径调用，前端无对应 UI | Phase 3+ ADC / 小分子 / 曾用名业务真正使用时再上 service / API / 前端 |
| S13 | §7.7 | `merged_to_substance_id` 字段 + FK 已建，无 `:merge` 端点 | Phase 5 数据治理工具阶段补（与 V1.2 §8.1.3 一致） |

### 2.6 🟠 待评估（Batch C — 高风险类型回归）

| # | §7.x | 偏离 | 当前判断 |
|---|---|---|---|
| S5 | §7.3 | `molecular_weight_da` 设计 `NUMERIC(10, 2)`，实施 `DOUBLE PRECISION`（Float） | 类型族变化，存量数据精度问题需评估；GxP 数据完整性"精度可重现"原则建议回归 NUMERIC，但需先做 dev 库精度截断验证 |
| S6 | §7.3 | `pi_theoretical` 设计 `NUMERIC(5, 2)`，实施 Float | 同 S5 |

---

## 3. PRS（§9 项目域）— 2026-05-13 重写

**原声明**："V1.1 §3 全部条目通过 M3.0.2 migration 0013-0017 完成对齐回归。V1.2 新发现项：无（V1.1 §3.3.5 团队 unique 离开后再加入语义 仍待 §9.4 文档修订决定）。"

**独立复核结果**：10 项偏离，2 项已修，8 项分类推迟 / 待评审。

### 3.1 🟥 触发器 GUC 去除（已修 / migration 0029）

| # | §9.x | 设计 vs 实施偏离 | 处置 |
|---|---|---|---|
| P1 | §9.5 | V1.1 §9.5 注释明文同 §7.7："change_reason 由 service 层在 INSERT 后显式 UPDATE 回填，触发器**不依赖** session GUC"。原实施 `prs.fn_project_status_change` 仍走 GUC（migration 0010 回退到 v1 形态时未同步去 GUC） | ✅ migration 0029 REPLACE 函数；`prs/services.py` 状态机 flush 后 UPDATE 回填 `change_reason + e_signature_id` |

### 3.2 🟥 索引命名与缺失（已修 / migration 0029）

| # | §9.x | 设计 vs 实施偏离 | 处置 |
|---|---|---|---|
| P2 | §9.2 | V1.1 §9.2 行 1426-1431 命名：`ix_project_type / ix_project_pm / ix_project_name`；migration 0006 实际：`ix_project_project_type` / `ix_project_manager` / `ix_project_project_name`（双前缀 + 命名偏差）；且 `ix_project_dates (planned_start_date, planned_end_date)` 复合索引完全缺失 | ✅ migration 0029 三个 `ALTER INDEX RENAME` + `CREATE INDEX ix_project_dates`；`ix_project_phase` 是实施侧加强保留 |

### 3.3 🟥 团队 unique 业务语义（待评审决定）

| # | §9.x | 偏离 | 处置 |
|---|---|---|---|
| P3 | §9.4 | V1.1 §9.4 写 `UNIQUE (project_id, user_id, role)` 绝对唯一。实施按字面照搬，结果 `left_at IS NOT NULL`（已离职）同 (user, role) 永不能再加入。V1.2_draft 原文也承认"待 §9.4 文档修订" | 🚧 **需 §9.4 评审拍板**：(a) 改为 partial UNIQUE `WHERE left_at IS NULL`；(b) 或保持绝对唯一并明确"同人离职后用同角色再加入须新建 user 记录" |

### 3.4 🟢 实施侧加强（已实施，建议吸收 V1.1）

| # | §9.x | 加强 |
|---|---|---|
| P4 | §9.5 | `prs.project_status_history.e_signature_id` 由 service 显式 UPDATE 回填（避免 asyncpg 池 SET LOCAL 泄漏；V1.1 §5.4 同模式） |
| P5 | §9.2/§9.5 | GxP 关键动作（approve/complete/terminate）强制电子签名 + `project:sign` 权限二阶；hold/resume/start 不签 |
| P6 | §9.2 | M3.0.2 漏建的 `created_by/updated_by/deleted_by/project_manager_id → auth.user` FK，migration 0020 补齐 |
| P7 | §9.3 / §9.4 | 子表 audit trigger 通过 v2 第 3 参数 parent_ref 回填 `entity_code = project_code`（V1.1 §5.3 同模式） |

### 3.5 🟠 未实施 / 推迟

| # | §9.x | 内容 | 计划 |
|---|---|---|---|
| P8 | §9.5 | `prs.project_relationship` 表 + CHECK + UNIQUE + FK 已建（migration 0016），**无 audit trigger，无 service / schema / API / 前端**。0016 注释明示"Phase 3+ 再上" | Phase 3+ 项目血缘 / 衍生关系业务真正使用时再上上层 |

### 3.6 ⚠️ API / 前端表面缺口（✅ 已修 / Batch F）

| # | §9.x | 缺口 | 处置 |
|---|---|---|---|
| P9 | §9.2 | `ProjectFilter` 列表过滤未暴露：`priority` / `program_name` / `parent_project_id` / `confidentiality` / `budget_currency` | ✅ Batch F：schema 加 5 字段、`list_projects` service 加过滤逻辑、`projects.py` endpoint 加同等 query 参数 |
| P10 | §9.2 | `ProjectBrief` 列表项缺：`program_name` / `confidentiality` / `parent_project_id` / `sponsor_id` | ✅ Batch F：schema 加 4 字段，依赖 `from_attributes=True` 自动从 ORM 透传 |

---

## 4. REF（§11 跨域引用）— 2026-05-13 重写

**原声明**：§4 仅追踪三张表存在性，未发现偏离；§6.5.4 / §6.6.5 称"三张 ref 表 deleted_by 完全统一"，附录 A 称 "DM-MDM-001 ~99%"。

**独立复核结果**：8 项偏离（含 1 项 V1.2_draft 自身声明事实错误）。

### 4.1 🟥 ref.project_substance.deleted_by 缺 FK（已修 / migration 0029）

| # | §11.x | 设计 vs 实施 | 处置 |
|---|---|---|---|
| R1 | §11.2 | V1.1 §11.2 行 1667 显式要求 `fk_ref_ps_deleted_by FOREIGN KEY (deleted_by) REFERENCES auth.user(user_id)`。migration 0012 加了 `deleted_by` 列但漏加 FK，migration 0027（V1.2 #A/#B 决议）补 ref.asset_substance / ref.project_asset 时**遗漏了 ps**，但 0027 注释还自称"与 §11.2 ref.project_substance 已有的 deleted_by 对齐" — 实测 `pg_constraint` 仅有 `fk_ref_as_deleted_by` / `fk_ref_pa_deleted_by` | ✅ migration 0029 `op.create_foreign_key("fk_ref_ps_deleted_by", ...)` 补齐 |

**⚠️ 推翻原 V1.2 Draft 声明**：§6.5.4 / §6.6.5 "三表 deleted_by 完全统一" 不实，至 migration 0029 才真正达成。

### 4.2 🟥 service 层业务规则缺校验（已修 / Batch E）

| # | §11.x | 设计 vs 实施 | 处置 |
|---|---|---|---|
| R5 | §11.1 | V1.1 §11.1 行 1659 明文三类禁建：`substance.obsoleted` + `asset.terminated` + **`project.terminated`**。实施仅在 `ref/services.py` 定义 `SUBSTANCE_STATUS_FORBID_LINK / ASSET_STATUS_FORBID_LINK`，**完全缺 `PROJECT_STATUS_FORBID_LINK`**，terminated project 可继续接受新的 substance / asset 关联 | ✅ `ref/services.py` 加 `PROJECT_STATUS_FORBID_LINK = {"terminated"}`；`ProjectSubstanceLinkService.link` + `ProjectAssetLinkService.link` 双侧入口均加校验 |

**⚠️ 推翻原 V1.2 Draft 声明**：§6.6.4 把"terminated 资产禁止"列为"实施侧加强 / 建议 V1.1 §11.4 加业务规则说明"，但 §11.1 行 1659 本就是 V1.1 设计明文要求，不是加强；且漏掉了 project.terminated 的同等规则。

### 4.3 🟢 实施侧加强（已实施）

| # | §11.x | 加强 |
|---|---|---|
| R3 | §11.4 | DB 层未加 `relation_type` CHECK，Pydantic `Literal['primary','supporting','derivative','reference']` 在 API 层枚举校验，与设计 §11.4 一致 |
| R4 | §11.x | audit trigger 第 2 参数 `entity_code_col` 文档为 `NULL`，实施统一传 `''`；PL/pgSQL 中等价处理（v2 函数 `NULLIF(TG_ARGV[1], '')`），属字符表示差异 |

### 4.4 ⚠️ API / 前端表面缺口（R6/R7 ✅ 已修 / Batch F，R8 待评审）

| # | §11.x | 缺口 | 处置 |
|---|---|---|---|
| R6 | §11.3 | `AssetSubstanceLinkItem` schema 缺 `deleted_by`，`_compose_item` 也未传 | ✅ Batch F：schema 加字段、`_compose_item` 传 `link.deleted_by`；test_unlinked_record_exposes_deleted_by 覆盖 |
| R7 | §11.4 | `ProjectAssetLinkItem` schema 缺 `deleted_by` | ✅ Batch F：同 R6 |
| R8 | §11.2 / §11.3 / §11.4 | 三张 ref 表 `created_by` / `updated_by` 均无 FK 到 auth.user（设计未显式列 fk_*_created/updated_by FK，但字段语义上是 user FK） | 🚧 待评审：设计文档应否显式补 FK 约束（实际语义 FK 已成立，由 service 层 `current_user.user_id` 保证） |

### 4.5 表存在性总览

| 表 | 文档章节 | 当前状态 | 备注 |
|---|---|---|---|
| `ref.project_substance` | §11.2 | ✅ M3.0.1 重构完成 + migration 0029 补 deleted_by FK | — |
| `ref.asset_substance` | §11.3 | ✅ M3.3 已建（migration 0025）| 见 §6.5 |
| `ref.project_asset` | §11.4 | ✅ M3.3 已建（migration 0026）| 见 §6.6 |

---

## 5. 跨主题实施侧合理加强 — V1.1 状态延续

V1.1 §5.1-§5.5 全部 5 项（service-level commit / 旁路 session / parent_ref / e_signature_id / `meta.error.type` 401 分流）状态不变，建议 V1.1 文档评审时一并吸收。

> 说明：V1.0 API 错误响应的机器可读错误类型字段位于 `meta.error.type`。本文件中原称 “`meta.error.type`” 的内容统一解释为 `meta.error.type` 字典 / 分流规则，除非后续评审明确决定调整 API 响应结构。

V1.2 在 §10 增补 1 项（asyncpg 池 SET LOCAL GUC 泄漏修复），见下文。

**2026-05-13 修订增补**：V1.1 §5.4（status_history.e_signature_id service 后置 UPDATE 回填）模式经 M3.5 / M3.6 扩展到 **change_reason 字段同处理**（migration 0028 SRS、migration 0029 ARS+PRS）。三个域的 `fn_*_status_change` 触发器现统一不读 `app.change_reason` GUC，仅写字面量 `'status changed'` 占位；service 在 flush 后 UPDATE 同时回填 `change_reason + e_signature_id`。建议 V1.1 §7.7 / §8.4 / §9.5 注释**统一**改为反映此模式。

---

## 6. M3.1-M3.4 ARS 资产域与跨域引用补齐（V1.2 新增）

### 6.1 🟢 ARS §8.2 asset 主表 — 实施侧补齐项

| # | 设计基准 §8.2 | 实施现状 | 处置 |
|---|---|---|---|
| 6.1.1 | asset 主表（asset_code / asset_type / current_phase / status / is_commercial / 等）| ✅ migration 0022 按 §8.2 DDL 新建 | 无偏离 |
| 6.1.2 | `asset_code` 编码格式 `AST-XXXXXXX`（全局序列）| 实施一致；与 §9.2 PRJ-YYYY-XXXX 按年生成不同 | 无偏离（§8.2 未指定按年）|
| 6.1.3 | `status` ∈ active/on_hold/terminated（3 值，状态机管控）| 一致 | 无偏离 |
| 6.1.4 | `current_phase` ∈ discovery/preclinical/phase_1/phase_2/phase_3/submission/approved/marketed/discontinued（9 值，业务进度）| 一致 | 无偏离 |
| 6.1.5 | `status` 与 `current_phase` 是两个独立维度 | 实施做了清晰分离（status 走状态机；current_phase 由 PUT 直接更新）| 无偏离 |

### 6.2 🟢 ARS §8.3 asset_market_id — 实施侧补齐

| # | 设计基准 §8.3 | 实施现状 | 处置 |
|---|---|---|---|
| 6.2.1 | `asset_market_id` 表（多市场注册号）| ✅ migration 0023 按 §8.3 DDL 建表 | 无偏离 |
| 6.2.2 | `UNIQUE (asset_id, market_code, id_type, id_value)` | 实施一致 | 无偏离 |
| 6.2.3 | `deleted_at` 软删除字段，V1.0 **无** `deleted_by` | 实施侧已按 V1.1 修订统一补 `deleted_by` | ✅ 已吸收进 DM-MDM-001 V1.1：补 `deleted_by BIGINT REFERENCES auth.user(user_id)`，与 substance_xref / project_milestone 等子表 soft-delete 字段组保持一致。|
| 6.2.4 | audit trigger 接入，第 3 参数 `parent_ref` 回填 `asset_code` | 实施保留实施侧加强（V1.1 §5.3）| 🟢 与 V1.1 §5.3 同模式 |

### 6.3 🟢 ARS §8.1 asset_status_history — 文档遗漏 + 实施补齐

| # | 设计基准 §8 | 实施现状 | 处置 |
|---|---|---|---|
| 6.3.1 | §8.1 表清单列出 `asset_status_history`，但 §8 章节后续**未给出 DDL** | ✅ migration 0024 按 §7.7 / §9.5 同构补建（old_status / new_status / change_reason / changed_at / changed_by / e_signature_id）| 🟢 **建议 V1.1 § 8 补 DDL**，与 §7.7 / §9.5 完全对齐 |
| 6.3.2 | `e_signature_id` BIGINT FK | 实施侧加强（与 V1.1 §5.4 同模式）| 🟢 建议正式入 V1.1 §8 |

### 6.4 🟢 ARS 状态机 + 电子签名（M3.2）

| # | 设计基准 | 实施现状 | 处置 |
|---|---|---|---|
| 6.4.1 | §8.2 status 3 值 → 状态机：hold / resume / terminate | ✅ 实施 `STATE_MACHINE = {hold: active→on_hold, resume: on_hold→active, terminate: active+on_hold→terminated}` | 无偏离 |
| 6.4.2 | 21 CFR Part 11 §11.50 关键不可逆动作要求电子签名 | ✅ terminate 强制电子签名（沿用 V1.1 §5.4 模式）| 🟢 与 SRS/PRS 一致 |
| 6.4.3 | RBAC 权限设计 | terminate 端点要求 **asset:update + asset:sign 双权限**（实施侧加强）；hold/resume 仅需 asset:update | 🟢 比文档严格的设计，建议 V1.1 评审 |
| 6.4.4 | 角色权限分配 | seed 加 `asset:sign` 权限，PROJECT_MANAGER + QA_REVIEWER 持有 | 🟢 与 substance:sign / project:sign 模式一致 |
| 6.4.5 | 状态机端点路径 | `POST /assets/{code}:hold` / `:resume` / `:terminate` | 🟢 与 substance/project 路径风格一致；API-MDM-001 V1.0 文档 §8.2 未明示资产状态机端点路径，建议补 |

### 6.5 🟢 REF §11.3 ref.asset_substance（M3.3）

| # | 设计基准 §11.3 | 实施现状 | 处置 |
|---|---|---|---|
| 6.5.1 | 复合 PK `(asset_id, substance_id, component_role)` | ✅ migration 0025 按 §11.3 DDL 建表 | 无偏离 |
| 6.5.2 | `component_role` ∈ `main_component / antibody / linker / payload / excipient / impurity`（6 值 CHECK）| 实施一致 | 无偏离 |
| 6.5.3 | `is_active_ingredient BOOLEAN NOT NULL DEFAULT TRUE` | 实施一致 | 无偏离 |
| 6.5.4 | 软删除 `deleted_at`，V1.0 **无** `deleted_by`（与 §11.2 不同）| 实施侧已按 V1.1 修订统一补 `deleted_by` | ✅ 已吸收进 DM-MDM-001 V1.1：`ref.asset_substance` / `ref.project_asset` 均补 `deleted_by`，三张 ref 表采用一致 soft-delete 模式（`deleted_at + deleted_by`）。|
| 6.5.5 | audit trigger 第 1 参数用 `asset_id`（§11.3 复合 PK 无单一 ID），第 3 参数 `parent_ref` 回填 `asset_code` | 实施一致 | 🟢 沿用 V1.1 §5.3 |

### 6.6 🟢 REF §11.4 ref.project_asset（M3.3）

| # | 设计基准 §11.4 | 实施现状 | 处置 |
|---|---|---|---|
| 6.6.1 | 复合 PK 仅 `(project_id, asset_id)` — `relation_type` **是属性不入 PK**（与 §11.2 复合三键 PK 的关键差异）| ✅ migration 0026 按 §11.4 实建 | 无偏离 |
| 6.6.2 | `relation_type VARCHAR(32) NOT NULL DEFAULT 'primary'` 文档未限定 CHECK 枚举 | 实施一致（后端无 CHECK；前端给建议值 primary/supporting/derivative/reference）| 🟢 与 §11.4 设计一致 |
| 6.6.3 | audit trigger parent_ref 回填 `project_code`（project 是关系中"更主"的实体）| 实施一致 | 🟢 业务语义合理 |
| 6.6.4 | 业务规则：`asset.status='terminated'` 禁止新建关联 | 实施侧加强（service 层校验，与"obsoleted 物质不允许新关联" V1.1 §3 类似）| 🟢 建议 V1.1 §11.4 加业务规则说明 |
| 6.6.5 | 软删除 `deleted_at`，V1.0 **无** `deleted_by`（与 §11.2 不同）| 实施侧已按 V1.1 修订统一补 `deleted_by` | ✅ 已吸收进 DM-MDM-001 V1.1，与 `ref.asset_substance` 保持一致。|

### 6.7 🟢 全局搜索接入 asset（M3.4）

| # | 设计基准 | 实施现状 | 处置 |
|---|---|---|---|
| 6.7.1 | API-MDM-001 §3.2.2 全局搜索 entity_type ∈ {substance, project, asset} | ✅ 实施 3 类全覆盖；`asset` 命中字段 = asset_code / internal_name / trade_name / inn_name / indication | 无偏离 |
| 6.7.2 | 命中排序权重 | 实施 trade_name / inn_name 归入 weight=5（与 name_en / internal_code 并列）| 🟢 排序策略建议 V1.1 API 文档备注 |
| 6.7.3 | 权限过滤 | 实施按 asset:read 过滤（SYS_ADMIN bypass）| 无偏离 |

### 6.8 🟢 演示数据扩充（M3.4）

| # | 内容 | 处置 |
|---|---|---|
| 6.8.1 | seed_data --demo 增加 4 个 `[DEMO]` 资产（Anti-PD-1 marketed / Anti-TIGIT Ph1 / CD19xCD3 discovery / HER2-DXd Ph3）| 🟢 与现有 DEMO_SUBSTANCES / DEMO_PROJECTS 1:1 配对 |
| 6.8.2 | 演示资产含 asset_substance + project_asset 跨域绑定 + 1 条 asset_market_id（NMPA 批文）| 🟢 体现 §11.3 / §11.4 / §8.3 全链路 |

### 6.9 §8 ARS 独立复核增补（2026-05-13）

经独立复核（不依赖 §6.1-§6.4 自我声明），§8 共 7 项偏离：1 项 🟥 已修、3 项 🟢 加强、3 项 ⚠️ 表面缺口。

#### 🟥 已修（migration 0029）

| # | §8.x | 设计 vs 实施 | 处置 |
|---|---|---|---|
| A3 | §8.4 | V1.1 §8.4 注释明文同 §7.7 / §9.5："change_reason 由 service 后置 UPDATE，触发器**不依赖** GUC"。原 migration 0024 实施 `ars.fn_asset_status_change` 仍走 `current_setting('app.change_reason')` GUC | ✅ migration 0029 REPLACE 函数；`ars/services.py` 状态机 flush 后 UPDATE 回填 `change_reason + e_signature_id` |

#### 🟢 实施侧加强（已实施，建议吸收 V1.1）

| # | §8.x | 加强 |
|---|---|---|
| A4 | §8.3 | `asset_market_id.created_by / updated_by` 加 FK 到 auth.user（V1.1 §8.3 仅要求 deleted_by FK），与 §8.2 主表风格对齐 |
| A5 | §8.2 | `ars.fn_asset_before_update` 自动维护 `updated_at / version+1` + 当 `current_phase` 变化时回填 `phase_change_at`，与 §7.7 / §9.5 同模式 |
| A6 | §8.3 | migration 0027 补 `asset_market_id.deleted_by + fk_asset_market_id_deleted_by`（与 §6.2.3 一致） |

#### ⚠️ API / 前端表面缺口（✅ 已修 / Batch F）

| # | §8.x | 缺口 | 处置 |
|---|---|---|---|
| A7 | §8.2 | `AssetDetail` 响应 schema 漏 `deleted_at / deleted_by` | ✅ Batch F：schema 加 2 字段；`model_validate(asset)` 自动从 ORM 透传 |
| A8 | §8.3 | `AssetMarketIdSchema` 漏 `deleted_at / deleted_by` | ✅ Batch F：同 A7 |
| A9 | §8.4 | `StatusHistoryItem` 通用 schema 缺 `asset_id`（同 substance_id / project_id 在跨域复用时也缺）| ✅ Batch F：`audit/schemas.py::StatusHistoryItem` 加 `substance_id` / `project_id` / `asset_id` 三个可选字段，三选一非 None 取决于 ORM 来源表 |

**⚠️ 推翻原 V1.2 Draft 声明**：§6.1.x-§6.4.x 声明 ARS 100% 对齐与 V1.1 一致；实际 A3 与 §8.4 V1.1 注释存在实质偏离，A7-A9 schema 表面有缺口。

---

## 7. 架构（ARCH-MDM-001 V1.0）偏离 — V1.2 新增

### 7.1 🟢 实施侧合理加强（建议 V1.1 / 架构文档下一版吸收）

| # | 加强项 | 触发原因 | 建议处置 |
|---|---|---|---|
| 7.1.1 | asyncpg 连接池 + `SET LOCAL GUC` 跨事务泄漏修复 | M2.5.1 发现：第 2 条 status_history 写入第 1 条事务的 `e_signature_id`（GUC 在被复用连接里残留）→ 改为 service 显式 `UPDATE status_history SET e_signature_id = …` 取代 `SET LOCAL` 注入 | 架构文档 §15.2 加施工说明 |
| 7.1.2 | RBAC 权限组合：`require_all_permissions(...)` 多权限工厂 | M2.5.1 / M3.2 GxP 关键端点需要"操作权限 + 签名权限"双校验（如 `substance:approve + substance:sign`、`asset:update + asset:sign`）| 架构文档 §11.x 加权限组合模式 |
| 7.1.3 | JWT `iat`（整秒）与 `password_changed_at`（微秒）的整数秒截断比较 | M2.5.2 老 bug：精度不一致导致刚改完密码的 token 误判失效 | 架构文档 §11.300 加比较规则说明 |

### 7.2 🟠 未实施 / 推迟

| # | 设计要求 | 当前状态 | 计划 |
|---|---|---|---|
| 7.2.1 | Redis 缓存层应用层接入 | 容器已部署，代码未集成 | Phase 5 性能优化阶段接入；当前 dev 数据量下无瓶颈 |
| 7.2.2 | Prometheus metrics endpoint | 未实现 | Phase 4 / 生产部署前补 |
| 7.2.3 | 集中日志收集（ELK / Splunk）| 仅 stdout loguru | 生产部署前配置 |
| 7.2.4 | 生产级 nginx 反代 + k8s manifest | 仅 docker-compose dev | Phase 4 / 生产部署前补 |
| 7.2.5 | 数据库备份策略 | 未定义 | Phase 4 生产部署前定义备份策略，并完成至少一次恢复演练，形成可审计记录 |
| 7.2.6 | 测试覆盖率工具兼容性 | V1.1 §附录 A 提到 schema 一致性检查脚本，未实现 | 维持记录，CI 门禁待 Phase 4 补 |

### 7.3 已对齐项（V1.2 原表述）

技术栈 / 分层结构 / JWT 认证 / RBAC / 审计追踪 / 中间件链均与 ARCH-MDM-001 V1.0 一致。架构层面对齐率 **95%**（缺口主要在生产部署 / 可观测性，非核心阻塞）。

**⚠️ 2026-05-13 修订**：本节"~95%"声明经独立复核**不准确**，实际约 **~85%**，新发现偏离详见 §7.4。

### 7.4 §7 架构 独立复核增补（2026-05-13）

经对 ARCH-MDM-001 V1.1 独立逐节复核（不依赖 §7.1-§7.3 自我声明），共发现 15 项实质偏离 / 加强 / 推迟项。

#### 🟥 待对齐回归

| # | V1.1 §X | 设计要求 vs 实施 | 引用 | 严重 |
|---|---|---|---|---|
| ARCH1 | §4.3 中间件链 | 设计要求 JWT / RBAC / 审计拦截器 / 请求 ID / CORS / 限流 6 层；实施 main.py 仅 CORS + RequestID + AuditContext 3 层（JWT/RBAC 走 Depends，审计写入散落 service+触发器，**限流缺失**） | `backend/app/main.py:49-58` | 中 |
| ARCH2 | §7.2.1 行 918 | 设计 Access + Refresh Token 双 token + HttpOnly Cookie；实施 `create_refresh_token` 已定义但 `login()` 未调用、无 Cookie | `backend/app/core/security.py:48-58` + `backend/app/domains/auth/services.py:196-213` | 中（与 V1.2_draft §8.1.1 推迟一致） |
| ARCH3 | §4.3 链路追踪 | RequestID 走 `BaseHTTPMiddleware` + `ContextVar.set()`，dispatch 后 ContextVar 已逃离原始 task 上下文，下游 Depends 取值不稳定（audit 触发器偶发拿不到 request_id） | `backend/app/shared/middleware/request_id.py:17` | 低 |

#### 🟢 实施侧加强（V1.2_draft §7.1 已记录 3 项 + 新增 2 项）

| # | 加强 | 状态 |
|---|---|---|
| ARCH4 | 失败副作用旁路 session 同时覆盖**登录失败 + 电子签名失败**（V1.1 §6.5 行 867-877 已吸收）| 已对齐，文档准确 |
| ARCH5 | `require_all_permissions` 工厂（V1.2_draft §7.1.2 已记录）| 描述准确 |
| ARCH6 | asyncpg GUC 显式 UPDATE 改造（V1.2_draft §7.1.1 已记录）| 描述准确 |
| ARCH7 | JWT iat 整秒截断（V1.2_draft §7.1.3 已记录）| 描述准确 |
| ARCH8 | `audit.fn_audit_trigger` 3 参数 + parent_ref 父表 entity_code 回填（V1.1 §6.5 行 865 已吸收）| 已对齐，文档准确 |

#### 🟠 未实施 / 推迟（V1.2_draft §7.2 已记 6 项 + 新增 2 项）

| # | 内容 | 计划 |
|---|---|---|
| ARCH9 | **前端技术栈缺 5 项**：V1.1 §5.1 列 React Hook Form + Zod / ECharts / Recharts / React Flow / Ant Design Pro Components；`frontend/package.json:13-25` 均无（表单走 antd 原生 Form，图表与血缘图组件无）| 进 Batch G3 / Phase 4-5 评审决定哪些需要 |
| ARCH10 | V1.1 §4.2 Celery Worker / MinIO 行 481/496（设计标注"可选"）| 推迟 |
| ARCH11 | **API 限流缺失**：V1.1 §3.5 行 562-579 要求 4 档速率限制 + `X-RateLimit-*` 头 + 42901 + `Retry-After`；`backend/app/main.py:55` 仅 expose header，无实际限流中间件，pyproject 无 slowapi/limits | 进 Batch G3 / Phase 4 生产前 |
| ARCH12 | **meta schema 表只落地 1/3**：V1.1 §6.1 行 727 列 `meta.lookup_value` / `meta.system_config` / `meta.code_sequence`，alembic 仅建 code_sequence | 进 Phase 5 Admin 工具时建 |
| ARCH13 | V1.2_draft §7.2.1-§7.2.6 已记 6 项（Redis / Prometheus / ELK / nginx / 备份 / 测试覆盖率）| 描述准确 |

#### ⚠️ V1.2_draft §7 声明不准确

| # | 原文 | 实测 |
|---|---|---|
| ARCH14 | §7.3"~95%"声明 | 缺前端 5 项技术栈（ARCH9）+ 缺限流（ARCH11）+ Refresh Token 流转未实施（ARCH2）+ 中间件链与 V1.1 §4.3 设计图非一对一（ARCH1）+ meta 表只 1/3（ARCH12）→ 实际 **~85%** |
| ARCH15 | §7.1 未记录 | ARCH3 ContextVar 跨边界泄漏风险 + ARCH12 meta 表落地不完整 |

---

---

## 8. API（API-MDM-001 V1.0）偏离 — V1.2 新增

### 8.1 🟠 未实施端点（推迟）

| # | API-MDM-001 端点 | 用途 | 当前状态 | 计划 |
|---|---|---|---|---|
| 8.1.1 | `POST /auth/refresh` | JWT 刷新令牌 | ❌ 未实现 | Phase 4 安全收尾时补；当前 access_token 30 min + 重新登录覆盖 |
| 8.1.2 | `POST /substances/{code}:reject` | 物质驳回（draft → deleted）| ❌ 未实现 | 待评估业务必要性；当前用 DELETE 软删除替代 |
| 8.1.3 | `POST /substances/{code}:merge` | 物质合并（含 merged_to_substance_code）| ❌ 未实现 | Phase 5 数据治理工具阶段补 |
| 8.1.4 | `POST /assets/{code}:advance-phase` | 资产推进阶段（current_phase 单独流转）| ❌ 未实现 | 当前用 PUT 直接更新 current_phase；如需流转校验和签名再补端点 |
| 8.1.5 | `POST /{domain}:batch-create / :batch-update / :batch-delete` | 批量操作 | ❌ 未实现 | Phase 5 数据治理工具阶段补 |

### 8.2 🟢 实施侧简化（建议 API 文档下一版备注）

| # | API-MDM-001 设计 | 实施现状 | 理由 |
|---|---|---|---|
| 8.2.1 | `GET /substances/{code}/protein` 独立子资源端点 | 实施改用 `GET /substances/{code}?expand=protein` 查询参数 | 单实体单查询模式更省请求；FE 详情页一次拿全数据 |
| 8.2.2 | `GET /substances/{code}/adc` 独立子资源端点 | 同上，用 `?expand=adc` | 同上 |
| 8.2.3 | `GET /substances/{code}/xrefs` 独立列表端点 | 同上，用 `?expand=xrefs`；POST/PUT/DELETE 独立子资源端点保留 | 列表数据少，跟主体一起返回开销低 |

### 8.3 🟢 `meta.error.type` 体系（V1.1 §5.5 延续）

实施已落地基于 `meta.error.type` 的错误分流（`signature_invalid` / `token_expired` / `token_invalid`），但 API-MDM-001 V1.0 尚未定义完整的 `meta.error.type` 字典。

**建议 V1.1 评审决定**是否将 `meta.error.type` 体系正式纳入 API 文档：
- `40101 invalid_credentials`
- `40102 token_expired`
- `40103 token_invalid`
- `40104 token_missing`
- `40105 old_password_wrong`
- `40106 signature_invalid` ← 实施侧新增
- `40301 permission_denied`
- `40302 account_disabled`
- `42201 state_invalid`
- `42203 signature_required` ← 实施侧新增（保留 V1.0 既有 `42202 reference_in_use`，避免破坏性变更）
- `42301 account_locked`

### 8.4 已对齐项（V1.2 原表述）

CRUD 路径 / 响应格式（code/message/data/meta + pagination）/ 错误码 HTTP 映射 / 状态机端点路径 / 审计端点 / 跨域绑定端点均与 API-MDM-001 V1.0 一致。API 层面对齐率 **~85%**（缺口集中在 batch / refresh / merge / advance-phase 等非核心扩展端点）。

**⚠️ 2026-05-13 修订**：本节"~85%"声明经独立复核**不准确**，实际约 **~70-75%**（G1.A/G1.B 已修若干合规缺口后回升至 ~78%），详见 §8.5。

### 8.5 §8 API 独立复核 + G1 落地（2026-05-13）

经对 API-MDM-001 V1.1 端点逐条复核，共发现 23 项偏离。本批次（G1.A + G1.B）已修 4 项严重合规相关项，其余进路线图。

#### 🟥 已修 / Batch G1.A（合规必修）

| # | V1.1 §X | 偏离 | 处置 |
|---|---|---|---|
| API1 | §4.2 行 638-641 | 错误码错配：`AssetNotFoundError.code = 40405`（应为 40404）、`XrefNotFoundError.code = 40404`（应为新位）；V1.1 表 40404=asset / 40405=material 被实施侧错位 | ✅ `core/exceptions.py` 修正：asset→40404、xref→40406（V1.1 表未定义，扩展位）、新增 MaterialNotFoundError=40405 占位；新增测试 `test_asset_not_found_returns_40404` |

#### 🟥 已修 / Batch G1.B（V1.1 §6.5/§7.4/§8.x 嵌套契约硬切）

| # | V1.1 §X | 偏离（原 V1.2_draft 表述） | 处置 |
|---|---|---|---|
| API2 | §6.5 行 1129-1138 | 状态机请求 V1.1 要求嵌套 `{"comment", "signature": {"password", "meaning", "reason"}}`；实施侧扁平 `{"change_reason", "password"}`（G1.A 后扩展为 `{"change_reason", "password", "signature_reason"}` 仍是扁平） | ✅ 后端 `SubstanceStatusChange / ProjectStatusChange / AssetStatusChange` 全部重构为 `comment + signature: SignatureBlock\|None`；新建 `audit/schemas.py::SignatureBlock`（password/meaning?/reason）|
| API3 | §6.5 行 1140-1155 | 状态机响应 V1.1 要求 `{entity_code, old_status, new_status, signature_id, registered_at?, registered_by?}`；实施侧返回 Detail 全量 | ✅ 新建 `audit/schemas.py::StateChangeResponse`（三域共用，含 substance_code/project_code/asset_code 三选一 + version 乐观锁）；3 个 service.change_status 返回新类型；3 个 router 改返回结构 |

**G1.B 是 Breaking change**：所有依赖旧扁平契约的客户端必须改为嵌套。本仓库前端 + 测试已同步切换（StatusActionsBar、3 个 DetailPage、3 个 API client、~28 处测试 json body）。

#### 🟥 已修 / Batch G1.A（UI 配套，登记于此供审计追溯）

| # | V1.1 §X | 偏离 | 处置 |
|---|---|---|---|
| UI3-API | §6.4 + §7.3 行 982 + §9.2.1 | 签名理由字段缺失（被 change_reason 共用，违反 §11.50"独立签名含义记录"）| ✅ 后端 schema + service 透传 `signature.reason` 写入 `e_signature.signature_reason`（与 `comment` 分离）；新增 `test_signature_reason_independent_from_comment` |

#### 🟥 已修 / Batch G2（中优先级）

| # | V1.1 §X | 偏离 | 处置 |
|---|---|---|---|
| API6 | §8.3 行 1688-1721 | 全局搜索响应 V1.1 要求 `data: {query, total, results: {substance, project, asset}}` 分组；实施返回平铺 `data: [SearchHit, ...]` | ✅ Batch G2：`audit/schemas` 新增 `SearchGroup` + `GlobalSearchResponse`；`search/services.search` 重构返回分组；router + 前端 `GlobalSearchBox` + 4 个 link Tab 的 AutoComplete 全部适配新结构；test_global_search 11 → 12（新增 test_search_response_structure 严格断言分组）|
| API9 | §4.2 行 614-654 | V1.1 §4.2 定义 ~30 错误码；实施仅 18 个 | ✅ Batch G2：补 11 个错误类（MissingRequiredError 40002 / InvalidValueError 40003 / WeakPasswordError 40010 / PasswordInHistoryError 40011 / CodeFormatInvalidError 40020 / DataAccessDeniedError 40303 / OperationNotAllowedError 40304 / UserNotFoundError 40401 / DuplicateNameError 40903 / DuplicateRequestError 40905 / ReferenceInUseError 42202）；`exceptions.py` 现 35 类 |

#### 🟠 推迟 / Batch G3 或 Phase 4-5

| # | V1.1 §X | 偏离 | 计划 |
|---|---|---|---|
| API4 | §7.2 行 1346-1382 | 项目创建请求 V1.1 用 `project_manager_username/sponsor_username` + 嵌套 `related_substances/related_assets/team`；实施只接 ID，无嵌套子资源 | Phase 5 评审决定（与 P3 团队 unique 一起）|
| API5 | §6.2 行 971-972 | POST 创建响应缺 `Location: /api/v1/{entity}/{code}` 头 | Batch G3 轻量 |
| API7 | §3.4 行 541-558 | `Idempotency-Key` 24h 幂等 + 40905 duplicate_request 未实现 | Phase 4 生产前 |
| API8 | §3.5 行 562-579 | 速率限制中间件 + 4 档限流 + 42901 + `Retry-After`（同 ARCH11）| 进 ARCH11 / Phase 4 |
| API10 | §5.1.2 行 720-735 | **用户/角色/权限管理 12 端点全部缺**：`/users` `/roles` `/permissions` list/create/lock/unlock/reset-password/角色分配等 | UI Phase 5/6 Admin（V1.2_draft §9.2.6 已记 UI 推迟，API 与之同步推迟）|
| API11 | §5.1.7 行 821-832 + §8.4-§8.6 | **全局功能端点缺**：`GET /audit-logs` / `POST /audit-logs:export` / `GET /lookups/{type}` / `GET/POST /signatures` / `GET /system/info` 全部未实现 | Phase 4-5 |
| API12 | §5.1.3 行 759 | `GET /substances/{code}/materials` 反向列表端点未实现 | 跟 MM 域 Phase 4 一起 |
| API13 | §5.1.3 行 750-756 | `GET/PUT /substances/{code}/protein`、`GET/PUT /substances/{code}/adc`、`GET /substances/{code}/xrefs` 独立子资源端点缺；V1.2_draft §8.2 已记 GET 用 expand 替代，但写端点 PUT /protein、PUT /adc 也未实现 | Phase 5 ADC/小分子业务时补 |

#### 🟢 实施侧加强（已实施，建议吸收 V1.1 下版）

| # | V1.1 §X | 加强 |
|---|---|---|
| API14 | §5.1.3 行 746-749 | Substance 状态机端点补全：V1.1 仅列 approve/reject/deprecate/merge；实施补 `:activate / :restrict / :obsolete` 三个端点（与 DM-MDM-001 完整状态机匹配）|
| API15 | §5.1.4 行 764-787 | Project 状态机端点补全：V1.1 仅列 approve/terminate；实施补 `:start / :hold / :resume / :complete` 四个端点 |
| API16 | 无 V1.1 明示 | Project DELETE / Milestone DELETE / Team DELETE 带 body 携带 `change_reason ≥ 5`；21 CFR Part 11 §11.10(e) 要求软删审计有原因，实施统一强制 |
| API17 | §5.1.3-§5.1.5 | `audit-logs` 端点加 `include_children=true` 查询参数（默认包含子表审计）|

#### ⚠️ V1.2_draft §8.4 声明不准确

按端点数粗算：V1.1 §5.1 共定义约 64 端点，实施约 47 个核心端点；缺 12 用户/角色 + 5 全局功能 + 部分子资源 + 错误码错位 + 状态机契约偏离（G1.B 前）≈ 17+ 端点 schema 级偏差。**实际对齐率 G1.A/G1.B 前 ~65-70%，G1.A/G1.B 后回升到 ~78%**；非"~85%"。

---

---

## 9. UI 信息架构（UI-MDM-001 V1.0）偏离 — V1.2 新增

### 9.1 🟢 已对齐（M3.x 完成）

- 导航 / 侧边菜单 / Header 全局搜索（接入 substance + project + asset 三类）
- 物质 / 项目 / 资产三域的列表 / 详情 / 创建 / 编辑页
- 详情页 Tab 结构（基本信息 / 关联 / 状态历史 / 审计）
- 状态变更 UI 全套（变更原因强制 ≥5 字 + 二次确认 + `meta.error.type` 分流）；其中关键不可逆动作（如 terminate / approve / deprecate）额外要求电子签名密码与签名理由，普通 hold / resume 不默认强制电签
- PermissionGuard 权限守卫
- 修改密码页（含 §11.300 提示 + 旧 token 即时失效）

### 9.2 🟠 待补 / 推迟

| # | UI-MDM-001 要求 | 当前状态 | 优先级 / 计划 |
|---|---|---|---|
| 9.2.1 | Ctrl+K 全局搜索快捷键 | 仅有点击聚焦 | 中 / Phase 4 体验优化 |
| 9.2.2 | 项目详情"概览" Tab 含甘特图 | 仅 Descriptions 基本信息 Tab | 中 / Phase 5（需引入甘特图组件） |
| 9.2.3 | 项目 / 资产列表多视图切换（表格 / 看板 / 时间轴） | 仅表格视图 | 低 / 体验增强，与业务工作流配套 |
| 9.2.4 | 创建表单 Steps 分步（基本 / 结构 / 标识符 / 关联 / 确认） | 单页表单 | 低 / 单页表单功能等价，体验差异有限 |
| 9.2.5 | 物料模块（MM）整体 UI | PlaceholderPage 占位 | 高 / Phase 4 物料域；全局搜索 `material` 类型也随 MM 基础域在 Phase 4 接入 |
| 9.2.6 | 系统管理子页（用户 / 角色 / 权限矩阵 / 编码序列 / 字典 / 配置）| Placeholder | Phase 5 / 6 Admin 工具 |
| 9.2.7 | 独立审计日志页（全系统日志浏览）| Placeholder（详情页内 AuditLogPanel 已实现）| 中 / Phase 4 |
| 9.2.8 | 密码复杂度强制（大小写 + 数字 + 特殊字符）| 仅长度 ≥8 校验 | 中 / 合规建议加强 |
| 9.2.9 | 仪表盘待办 / 最近访问 / 通知中心 | 占位文案 | 低 / 体验功能 |
| 9.2.10 | 项目详情 `sponsor_id` 显示为 user 名称而非 ID | 当前显示 ID | 低 / 单点 UX 修复 |

### 9.3 🟢 M3.x 新增 UI（V1.1 未记录）

- 资产域 4 个页面（List / Create / Detail / Edit）
- 资产详情页 6 个 Tab：基本信息 / 多市场注册号 / 关联物质 / 关联项目 / 状态历史 / 审计
- `MarketIdTable` 多市场注册号 CRUD 组件（含 4 日期字段 + status Tag）
- `AssetSubstanceTab` / `AssetProjectTab`（资产侧组分 / 项目绑定）
- `ProjectAssetTab`（项目侧资产绑定）
- `RelatedAssetsTab`（物质详情侧反向只读列表）
- `asset.status = terminated` 时绑定按钮禁用 + tooltip 提示；`current_phase = discontinued` 仅表示业务进度 / 商业阶段，不自动等同于资产终止
- Header 搜索分组加 `资产` 组（purple Tag）+ `/assets` 跳转
- 修改密码页 `ChangePasswordPage`（M2.5.x 实施侧加，符合 §11.300）

UI 层面对齐率 **~82%**（缺口集中在 Phase 4-6 范围内的物料 / 系统管理 / 高级体验组件）。

**⚠️ 2026-05-13 修订**：本节"~82%"声明经独立复核**不准确**，实际约 **~70-72%**（G1.A 修复 UI3/UI4 后回升到 ~76%），详见 §9.4。

### 9.4 §9 UI 独立复核 + G1.A 落地（2026-05-13）

经对 UI-MDM-001 V1.1 §1-§9 逐节复核，共发现 21 项偏离。本批次（G1.A）已修 2 项与 21 CFR Part 11 §11.50 直接相关的合规缺口，其余进路线图。

#### 🟥 已修 / Batch G1.A（GxP/Part 11 合规必修）

| # | V1.1 §X | 偏离（原 V1.2_draft 描述错位）| 处置 |
|---|---|---|---|
| UI3 | §6.4 行 833-839 + §7.3 行 982 + §9.2.1 行 1230 | 电子签名表单缺**独立"签名理由"字段**：V1.1 设计要求三字段（变更原因 / 签名理由 / 密码）；实施 `StatusActionsBar.tsx` 只有变更原因 + 密码，签名理由被 `change_reason` 共用 — **违反 21 CFR Part 11 §11.50「记录单独的签名含义」** | ✅ `StatusActionsBar.tsx` 在 `requiresSignature` 时增 `signature_reason` TextArea（min_length=5）；后端 schema + service 把字段独立写到 `e_signature.signature_reason`；G1.B 又把整个请求改成嵌套 `signature: {password, reason, meaning?}` |
| UI4 | §9.2 行 1184-1196 + §7.3 行 984 | terminate / 不可逆操作 V1.1 要求二次确认弹窗；实施 `StatusActionsBar` 直接在表单 Modal onOk 提交，无第二级 Modal.confirm | ✅ `StatusActionsBar.handleSubmit` 在 `requiresSignature \|\| danger` 时调 `Modal.confirm`，文案"该操作不可撤销，将以电子签名形式记录"+ "确认签名"/"我再想想" 两按钮 |

#### 🟥 已修 / Batch G2（中优先级）

| # | V1.1 §X | 偏离 | 处置 |
|---|---|---|---|
| UI10 | §9.2 + Batch F 后端 | PRS 列表前端未接入 priority / program_name / parent_project_id / confidentiality | ✅ Batch G2：ProjectListPage 加 priority + confidentiality Select、program_name + parent_project_id input；constants 加 PROJECT_PRIORITY_OPTIONS + PROJECT_CONFIDENTIALITY_OPTIONS |
| UI5 | §6.1.1 行 545 | SRS 列表常用筛选缺「靶点」+ 全部「更多筛选」| ✅ Batch G2：SubstanceListPage 常用区加「靶点」input + 「更多筛选」Drawer 含保密等级；表达系统/创建人/日期范围 Phase 4 SubstanceFilter 扩展时补 |
| UI1 | §3.1 / §3.3 行 218/259 | MainLayout 缺 Footer + Sidebar 底部缺版本/健康 | ✅ Batch G2：MainLayout 加 Footer（VITE_APP_VERSION + 服务器时间秒级刷新）；Sidebar 底部加版本号 + 健康检查 Badge（30s 探测 /health） |
| UI2 | §3.2.3 行 247 | 用户下拉菜单缺「偏好设置」 | ✅ Batch G2：Header userMenu 加「偏好设置」项；Phase 4-5 实际页未实现时占位 message.info |
| UI6 | §6.1 行 420-426 | SRS 列表列缺「关联项目」计数列 | ✅ Batch G2：后端 `srs/services.list_substances` 真填 project_count / asset_count（IN + group_by + count）；前端 SubstanceListPage 加「关联项目 / 关联资产」两列计数 |
| UI11 | §3.4.2 行 274-291 | 详情页头部缺「分享 / 复制编码 / 审计跳转」 | ✅ Batch G2：三域 DetailPage 头部加「复制编码 / 分享 / 查看审计」3 按钮；Tabs 改受控（activeKey + onChange）；"查看审计"调 setActiveTab('audit') |

#### 🟠 待修 / Batch G3（破坏性 UI 改造）

| # | V1.1 §X | 偏离 | 计划 |
|---|---|---|---|
| UI7 | §7.2.1 行 859-887 | 项目详情 Tab 1「概览」V1.1 要求含进度条 / 时间轴 / 团队预览卡 / 关联预览卡；实施 Tab 1 仅 Descriptions 字段表（甘特图推迟在 V1.2_draft §9.2.2 已记，但 progress + 预览卡不在推迟清单）| Batch G3 重大改版 |
| UI8 | §7.3 行 925 | 资产详情 Tab 1 V1.1 要求含「当前阶段时间线」；实施仅 `phase_change_at` 一行 | Batch G3 |
| UI9 | §6.2.5 行 648-677 | 物质详情「关联」V1.1 设计是 **1 Tab × 5 分组**（项目/资产/物料/父substance/子substance），实施拆为 2 Tab，缺**父/子 substance 视图**（ADC ↔ antibody 反向引用，重要 ADC 业务场景）| Batch G3 评审是否回归 |

#### 🟠 推迟（V1.2_draft §9.2 之外的新发现）

| # | V1.1 §X | 内容 | 计划 |
|---|---|---|---|
| UI14 | §4.2 仪表盘 | 「我的项目」/「项目状态分布」/「系统公告」三块缺（V1.2_draft §9.2.9 只说「待办/最近访问」占位，§4.2 还要这三块）| Phase 5 |
| UI15 | §6.1 / §5.3.4 工具栏 | 三域列表无 rowSelection / 批量操作 / 列设置 / 导出 | Phase 5 |
| UI16 | §9.1.3 | 创建页自动保存草稿（IndexedDB 30s）未实现 | Phase 5 |
| UI17 | §9.5 并发锁 | 详情页无"他人正在编辑"提示；version 冲突仅靠 422 toast | Phase 4-5 |

#### 🟢 实施侧加强（V1.1 未记录，建议吸收）

| # | 加强 | 文件 |
|---|---|---|
| UI12 | 物质/项目/资产**三域统一把"状态历史"独立成 Tab**（V1.1 仅物质详情提）| 三个 `*DetailPage.tsx` history Tab |
| UI13 | substance_type 补 `bispecific / oligonucleotide / other` 三项（V1.1 §6.2.2 仅列 mAb/ADC/small_molecule）| `constants.ts:3-11` |

#### ⚠️ V1.2_draft §9.1 / §9.3 声明不准确

| # | 原文 | 实测 |
|---|---|---|
| UI18 | §9.1 "导航/侧边菜单/Header 全局搜索 已对齐" | Footer 缺（UI1）/ Sidebar 底部缺（UI1）/ 用户菜单缺偏好设置（UI2）/ GlobalSearchBox placeholder 缺 Ctrl+K 提示（V1.1 §3.2.2 强制要求文案）|
| UI19 | §9.1 "详情页 Tab 结构 已对齐" | 项目详情 Tab 1 概览结构不一致（UI7）/ 资产详情 Tab 1 缺阶段时间线（UI8）/ 物质详情关联从 1 Tab 5 组拆为 2 Tab 缺父/子 substance（UI9）|
| UI20 | §9.1 "状态变更 UI 全套 已对齐 ... 电子签名密码与签名理由" | G1.A 修复前**签名理由字段不存在**（UI3）；G1.A 修复前**无二次确认弹窗**（UI4）；G1.A/G1.B 后已对齐 |
| UI21 | §9.3 "Header 搜索分组对齐" | 准确，但 placeholder 未提 Ctrl+K（§3.2.2 强制）与 §9.2.1 推迟自相矛盾 |

#### 整体重估

UI 实际对齐率：G1.A 前 ~70-72%，G1.A 后回升到 **~76%**；非"~82%"。

---

## 10. 处置时间表

| 子里程碑 | 内容 | 状态 |
|---|---|---|
| M3.0.1 | ref.project_substance 重构（§11.2）| ✅ 2026-05-11 完成 |
| M3.0.2 | prs 全表对齐（§9.2-§9.5）| ✅ 2026-05-11 完成 |
| M3.0.3 | srs 补缺子表（§7.4-§7.8）+ FK + sequence_hash DB 触发器 | ✅ 2026-05-11 完成 |
| **M3.1** | **ARS §8.2 主表 + §8.3 market_id + §8.1 status_history（实施侧补 DDL）** | ✅ 2026-05-12 完成 |
| **M3.2** | **ARS 状态机 + 电子签名（terminate 双权限）+ market_id CRUD** | ✅ 2026-05-12 完成 |
| **M3.3** | **REF §11.3 asset_substance + §11.4 project_asset + 终止资产业务规则** | ✅ 2026-05-12 完成 |
| **M3.4** | **全局搜索接入 asset + 演示数据扩充（4 [DEMO] assets）** | ✅ 2026-05-12 完成 |
| **M3.5 (Batch A+B+S8)** | **SRS §7 独立复核 + migration 0028（external_uuid UNIQUE / protein hash 索引 × 2 / xref_value 索引 / internal_code partial 索引 / fn_substance_status_change 去 GUC）+ Batch B API/前端字段暴露（xref effective/expiry + protein 7 字段）** | ✅ 2026-05-12 完成 |
| **M3.6 (Batch D+E)** | **ARS §8 + PRS §9 + REF §11 独立复核 + migration 0029（fk_ref_ps_deleted_by / ars+prs fn_status_change 去 GUC / prs 索引命名 + ix_project_dates）+ Batch E（ref service 加 PROJECT_STATUS_FORBID_LINK）** | ✅ 2026-05-13 完成 |
| **M3.7 (Batch F)** | **API schema 表面暴露（A7-A9 ARS / P9-P10 PRS / R6-R7 REF 共 6 项）：AssetDetail / AssetMarketIdSchema / StatusHistoryItem / ProjectFilter / ProjectBrief / AssetSubstanceLinkItem / ProjectAssetLinkItem 加字段；prs/services.py list_projects 加 5 条过滤分支；api/v1/projects.py 加 5 query 参数；ref/services.py _compose_item 传 deleted_by** | ✅ 2026-05-13 完成 |
| **M3.8 (Batch G1.A)** | **架构/API/UI 三上位文档独立复核 + 21 CFR Part 11 §11.50 合规必修**：API1 错误码 40404/40405 错位修正（asset→40404 / xref→40406 / 新增 Material 占位）；UI3 StatusActionsBar 加独立"签名理由" TextArea + 后端 schema/service 透传 e_signature.signature_reason 与 change_reason 分离；UI4 GxP 关键动作二次确认 Modal.confirm | ✅ 2026-05-13 完成 |
| **M3.9 (Batch G1.B)** | **状态机契约硬切回归 V1.1 嵌套**：请求 `{comment, signature: {password, meaning, reason}}` + 响应 `StateChangeResponse`（含 entity_code / old_status / new_status / signature_id / registered_at? / registered_by? / version）；audit/schemas.py 新增 SignatureBlock + SignatureMeaning + StateChangeResponse；后端 3 schema/3 service/3 router；前端 types.ts + 3 API client + StatusActionsBar + 3 DetailPage；测试 ~28 处 json body + 12 处 data["new_status"]。**Breaking change vs V1.0 扁平契约**，本仓库内全栈同步切换 | ✅ 2026-05-13 完成 |
| **M3.10 (Batch G2)** | **中优先级 8 项**：API9 补 11 错误码（exceptions.py 18→35 类）+ API6 全局搜索响应改 V1.1 §8.3 分组结构（audit/schemas 新增 SearchGroup + GlobalSearchResponse，前后端 + 4 个 link Tab AutoComplete 全部适配）+ UI1 MainLayout Footer + Sidebar 底部健康检查 + UI2 用户菜单加偏好设置 + UI5 物质列表加靶点 input + 更多筛选 Drawer + UI6 物质列表加关联项目/资产计数列（srs.list_substances 改聚合查询）+ UI10 PRS 列表加 priority/program_name/parent/confidentiality 4 过滤 + UI11 三域 DetailPage 头部加复制编码/分享/查看审计 3 按钮 + Tabs 改受控；test_global_search 11→12 用例 | ✅ 2026-05-13 完成 |
| **M3.11 (Batch G3.A)** | **零评审依赖 2 项**：ARCH12 建 meta.lookup_value + meta.system_config（migration 0030，DM V1.1 §5.2/§5.3 完整 seed：33 lookup + 10 config）+ API5 三域 POST 主资源（substance/project/asset）加 V1.1 §6.2 Location 响应头；test_substance_crud test_create_substance_returns_code 加 Location 头断言 | ✅ 2026-05-13 完成 |
| **Batch G3.B** | **推迟到 Phase 4**：ARCH11 API 限流（slowapi + 4 档 + X-RateLimit-* + 42901 + Retry-After）+ API7 Idempotency-Key 24h 幂等 + 40905；强依赖 Redis 应用层接入 | 🚧 Phase 4 |
| **Batch G3.C** | **9 项进 V1.2 评审会**：详见 docs/CMAB_MDM_Portal_V1.2_评审会议材料.md | ✅ 2026-05-13 评审完成（决议见下） |
| **M3.12 (Batch H 评审决议落地)** | **H1 migration 0031**（P3:A team UNIQUE 改 partial WHERE left_at IS NULL；R8:A ref 三表 created_by+updated_by 共 6 FK）+ **H2 4 新 endpoint**（API11:B 部分 `GET /api/v1/lookups/{type}` + `GET /api/v1/system/info` + API13:A `PUT /substances/{code}/protein` + `PUT /substances/{code}/adc`）+ **H3 UI 改版**（UI7:A ProjectDetailPage Tab1 加 Progress + Statistic + 关联跳转按钮；UI8:A AssetDetailPage Tab1 加 9-phase Timeline；UI9:B SubstanceDetailPage 加"血缘关系"Tab + 新 endpoint `/substances/{code}/lineage`）；test 130 用例新增 5 条（API13 PUT protein/adc + API11 lookups/system_info + P3 team rejoin） | ✅ 2026-05-13 完成 |
| **B 决议项（文档登记，不动代码）** | S5/S6（永久接受 Float，建议 V1.1 §7.3 下版加质谱容差备注）+ P8（project_relationship 上层推迟 Phase 5）+ ARCH9（只引入 ECharts + React Flow，Phase 5；其他放弃）+ API4（永久接受扁平 ID，V1.2 §8.2 简化条目）+ API10（用户角色权限 12 端点 Phase 5/6 Admin 一起）+ API11 audit-logs/signatures 端点（Phase 5）| ✅ 2026-05-13 决议 |
| **Batch G3** | **推迟与评审决策**：API4 项目嵌套子资源 / API5 Location 头 / API7 Idempotency-Key / API10 用户角色权限 12 端点 / API11 全局功能 5 端点 / API12 substances/{}/materials / API13 protein/adc 独立写端点 / ARCH9 前端技术栈 5 项 / ARCH11 限流 / ARCH12 meta lookup_value + system_config / UI7 项目概览 Tab 重构 / UI8 资产阶段时间线 / UI9 物质关联 Tab 拆分回 1 Tab 5 组 | 🚧 评审决定 |
| **Batch C** | **SRS §7.3 molecular_weight_da / pi_theoretical 从 Float 回归 NUMERIC** | 🚧 待评估（dev 库精度截断验证） |
| **V1.1 / V1.2 评审** | **IT 架构组评审本偏离说明 + 决定吸收哪些"实施侧合理加强"到上位文档；PRS P3 团队 unique 业务语义拍板；PRS P8 project_relationship 上层是否进 Phase 3+；UI7/UI8/UI9 重大改版决定** | 🚧 待安排 |
| Phase 4 | 物料域（MM）基础域 + `/auth/refresh` + 全局搜索 material 接入 + 独立审计页 + Prometheus / 集中日志 / 生产部署配置 + 备份恢复演练 + CSV 验证准备 | 🚧 待开工 |
| Phase 5 | 数据治理工具（merge / reject / batch / advance-phase 视需）+ Redis 缓存 + 系统管理 Admin UI + 复杂 fuzzy matching / 体验增强 | 🚧 待开工 |

---

## 11. 风险与缓解 — V1.1 状态延续

V1.1 §7 内容不变。新增风险：

| 风险 | 影响 | 缓解 |
|---|---|---|
| `asset_market_id` / `ref.asset_substance` / `ref.project_asset` 缺 `deleted_by` 与其他子表不一致 | 已通过 DM-MDM-001 V1.1 修订吸收，**部分关闭**：migration 0027 补 as/pa，但 ps 表至 migration 0029 才补齐 fk_ref_ps_deleted_by；现已全部统一 | `deleted_at + deleted_by` 标准 soft-delete 字段组在三张 ref 表完整 |
| `terminated` 项目仍可接受新 substance/asset 关联（违反 §11.1 设计原则） | 中（已暴露 7 个月，dev 库未触发，但 GxP 合规缺口）| migration 0029 + Batch E：ref/services.py 加 `PROJECT_STATUS_FORBID_LINK`，双侧入口校验 |
| ARS / PRS / SRS 三表 `fn_*_status_change` 走 `app.change_reason` GUC 通道，与 V1.1 §7.7 / §8.4 / §9.5 注释明文冲突 | 中（在 asyncpg 连接池下偶发 GUC 泄漏，e_signature_id 已先修，change_reason 残留） | migration 0028 + 0029 全部去 GUC，service 后置 UPDATE 回填实际 reason |
| V1.2_draft §2 / §3 / §6 历史声明 "100% 对齐" 不实，构成审计可靠性风险 | 中（评审引用本文件作为合规证据时，"自我声明 100%" 会被打脸） | 2026-05-13 修订一：明确列出 §7/§8/§9/§11 实测偏离 39 项 + 处置批次 |
| V1.2_draft §7/§8/§9 历史声明 "~95%/~85%/~82%" 不实，架构/API/UI 三上位文档实测对齐率分别为 ~85%/~78%/~76%（G1.A/G1.B 修复后）| 中 | 2026-05-13 修订二：§7.4/§8.5/§9.4 三处独立复核增补共列 30+ 项偏离 + Batch G1.A/G1.B 已修 |
| API1 错误码 40404/40405 错位影响审计可追溯性（asset_not_found 错占 40405，xref_not_found 错占 40404）| 高（违反 V1.1 §4.2 表，可能误导日志检索/告警规则）| ✅ G1.A 修正：asset→40404、xref→40406、新增 MaterialNotFoundError=40405 占位 |
| 电子签名签名理由字段被 change_reason 共用 — **违反 21 CFR Part 11 §11.50**「记录单独的签名含义」 | 高（GxP 合规直接缺口）| ✅ G1.A 加独立 signature_reason 字段；G1.B 进一步嵌入 `signature.reason`，与 `comment` 完全分离 |
| GxP 关键动作（terminate / deprecate / obsolete 等）缺二次确认 — 违反 V1.1 §7.3 行 984 / §9.2.1 设计 | 中 | ✅ G1.A：StatusActionsBar 加 Modal.confirm 二次确认 |
| **G1.B 状态机契约从扁平改为嵌套是 Breaking change**，依赖旧契约的外部调用方需要同步修改 | 中（dev/uat 阶段；生产前应通知所有客户端 SDK / 集成点）| 本仓库内前后端 + 测试已全部同步切换；外部集成方在 V1.2 评审通过后通知 |
| `/auth/refresh` 缺失，access_token 30 min 过期需重登 | 低（dev / UAT 阶段）| 生产前补 refresh 端点 |
| Redis 部署但未用，docker-compose 资源浪费 | 极低 | Phase 5 接入或先从 dev compose 移除 |

---

## 12. 评审记录

| 评审人 | 日期 | 决议 |
|---|---|---|
| _待 CMC IT 架构组_ | _待安排_ | _待评审_ |
| _待 QA 质量管理部_ | _待安排_ | _待评审_ |

---

## 附录 A：跨文档对齐率汇总（2026-05-13 修订五）

> **说明**：本表对齐率已基于完整独立复核 + Batch A/B/S8/D/E/F/G1.A/G1.B/G2/G3.A/H 全部落地 + V1.2 评审会 13 项决议后重新计算。

| 上位文档 | 修订四 | 修订五 | 主要缺口 |
|---|---|---|---|
| DM-MDM-001 V1.1（数据模型）| ~97% | **~99%** _H1 后_ | H1 修 P3:A（team partial UNIQUE）+ R8:A（ref 6 FK 全补齐）；S5/S6 永久接受 Float（B 决议，文档备注 §7.3 加容差说明）；P8 推迟 Phase 5（B 决议）；§10 物料域 Phase 4 |
| ARCH-MDM-001 V1.1（架构）| ~87% | **~88%** _H1+H2 后_ | H2 部分修 API11 lookups/system → 间接降低架构缺口；ARCH9 决议 B（只引入 ECharts+React Flow Phase 5）；剩 ARCH11 Phase 4 + ARCH2/3 |
| API-MDM-001 V1.1（API）| ~84% | **~90%** _H2 后_ | H2 修 API13:A（PUT protein/adc 独立写端点）+ API11:B 部分（lookups + system/info 立即做）；API4:B 永久接受扁平 ID；API10:B + API11 rest Phase 5；剩 API7 Phase 4 + API5 子资源 |
| UI-MDM-001 V1.1（UI 信息架构）| ~82% | **~92%** _H3 后_ | H3 修 UI7:A（项目概览 Progress+Statistic+跳转）+ UI8:A（资产 9-phase Timeline）+ UI9:B（物质血缘 Tab + 父/子 ADC 视图）；剩物料域 UI / Admin UI / 仪表盘 Phase 5 |

**整体加权对齐率**：**~92%**（修订四 ~88% + Batch H 落地 +4pp）。Phase 1-3 + 数据模型 + 主要 UX 路径已**全部完整对齐 V1.1**（含 V1.2 评审决议的"实施侧简化"项 — S5/S6/API4/ARCH9 等）。剩余缺口集中在：
- ARCH11 限流 + API7 Idempotency（Phase 4 与 Redis 应用层接入一起）
- Phase 4 物料域整域 + 生产部署 + 监控 + Refresh Token + CSV 验证
- Phase 5 Admin UI + API10 用户角色权限 + API11 全局功能 + 仪表盘 + 数据治理工具

**至此 V1.2 评审决议全部完成处置**，Phase 4 物料域可正式启动（无评审依赖阻塞）。

---

## 附录 B：自动化检查工具

V1.1 §附录 A 提到的"schema 一致性检查脚本"仍未实现，列入 Phase 4 / CI 门禁建设计划。

当前回归依赖 `backend/tests/` 中 **130 条** pytest 用例（M3.12 完成时计数，比 M3.4 的 117 条新增 13 条：S10/S11/R5×2/P9+P10 联合/R6 + G1.A API1/G1.B signature_reason/G2 API6 search 分组 + **M3.12 H2 的 PUT protein/PUT adc/lookups/system_info 共 4 条 + H1 P3:A team rejoin 重写测试（净 +0，替换原 absolute unique 测试）**）。每次 alembic upgrade head + pytest 全量通过作为 M3.x 各里程碑验收门禁。

详细的「偏离项 → 测试覆盖」映射见**附录 C**（CSV 验证 IQ/OQ 阶段证据链）。

---

## 附录 C：偏离项 ↔ 回归测试覆盖映射

本附录提供 V1.2 各偏离项 / 实施侧加强的回归测试证据链，供 CSV 验证 IQ（安装确认）/ OQ（操作确认）阶段引用。

### C.1 SRS（§7 物质域）

| V1.2 偏离项 | 测试文件 | 用例数 | 关键用例 |
|---|---|---|---|
| §2 SRS 子表（§7.4 ADC / §7.5 small_molecule / §7.8 alias）补建 | `test_substance_crud.py` | 9 | create / get / update（version+1）/ 乐观锁 / 重复 internal_code / soft delete + **S10 / S11 新增 2 条** |
| §7.6 substance_xref effective/expiry + 唯一约束 | `test_substance_crud.py` + `test_check_sameness.py` | 5 | sameness 判定走 xref |
| **§7.6 xref effective_date / expiry_date API 暴露（S10，M3.5）**| `test_substance_crud.py::test_xref_effective_expiry_dates` | 1 | create + GET + PUT 更新 expiry，未传字段保持原值 |
| **§7.3 protein 扩展字段 API 暴露（S11，M3.5）**| `test_substance_crud.py::test_create_with_extended_protein_fields` | 1 | expression_vector / pi_theoretical / extinction_coefficient 端到端；sequence_hash_hc 由 DB 触发器自动算 |
| §7.7 substance_status_history 状态机 | `test_state_machine.py` | 5 | full_lifecycle / invalid_transition / reason_too_short / restrict→deprecate / **status_history_recorded（S8 加强：change_reason 必须实值非占位）** |
| §7.7 substance_status_history.e_signature_id（V1.1 §5.4 加强）| `test_signature.py` | 8 | approve / activate / deprecate / obsolete 签名流；密码错；缺签名；signature_invalid 分流 |
| §7.3 substance_protein DB 触发器（hash 自动算）| `test_audit_trigger.py` + `test_audit_trigger_v2.py` | 4+3 | INSERT/UPDATE hash 一致；parent_ref 回填 substance_code |
| 物质同一性判定（业务功能）| `test_check_sameness.py` | 5 | 序列哈希命中 / xref 命中 / 不同 substance_type 不判同 |

**SRS 小计**：34 条用例（M3.4 32 + M3.5 新增 2）

### C.2 PRS（§9 项目域）

| V1.2 偏离项 | 测试文件 | 用例数 | 关键用例 |
|---|---|---|---|
| §9.2 project 主表对齐（枚举 / 字段 / 编码按年）+ **P9/P10 列表过滤 & Brief 字段（M3.7）**| `test_project_crud.py` | 11 | create 编码 PRJ-2026-XXXX / get / update / version 乐观锁 / soft delete / 枚举校验 + **test_list_filter_priority_and_brief_fields：priority/program_name/confidentiality 过滤 + Brief 含 program_name/confidentiality/parent_project_id/sponsor_id** |
| §9.3 project_milestone（枚举 / NOT NULL / 无软删除）| `test_project_milestone_team.py` | 8（含 team）| milestone CRUD / planned_date 必填 / 枚举校验 |
| §9.4 project_team（role 任意 + function_area + allocation_pct）| `test_project_milestone_team.py` | （同上）| team CRUD / 唯一性 / 离职后再加入 — **P3 待评审**|
| §9.5 project_status_history.e_signature_id（V1.1 §5.4 加强）+ **P1 status_history change_reason 实值（M3.6）**| `test_project_state_machine.py` | 6 | proposed→initiated→active→on_hold→completed/terminated 全链路；approve / complete / terminate 签名；**status_history_recorded 加 P1 断言：change_reason 必须非 'status changed' 占位** |

**PRS 小计**：25 条用例（M3.4 24 + M3.7 +1 P9/P10 联合）

### C.3 REF（§11 跨域引用）

| V1.2 偏离项 | 测试文件 | 用例数 | 关键用例 |
|---|---|---|---|
| §11.2 ref.project_substance 复合 PK 重构 | `test_project_substance_link.py` | 8 | link/unlink 往返；同对 substance 不同 relation_type 并存；relink 恢复；obsoleted 物质禁止；audit parent_ref 回填 project_code；**R5 terminated project 禁止 link（M3.6 新增）** |
| §11.3 ref.asset_substance（V1.2 §6.5 新建）+ **R6 deleted_by 暴露（M3.7）**| `test_asset_substance_link.py` | 9 | link/unlink；不同 component_role 并存（ADC 场景：antibody/linker/payload）；relink；terminated 资产禁止；obsoleted 物质禁止；audit parent_ref 回填 asset_code；**test_unlinked_record_exposes_deleted_by：include_deleted=true 列表项 deleted_by 非空** |
| §11.4 ref.project_asset（V1.2 §6.6 新建）| `test_project_asset_link.py` | 8 | 双向 link（project 侧 / asset 侧）；同对 (project, asset) 不同 relation_type 仍冲突（PK 仅含两键）；relink 换 relation_type；terminated 资产禁止双侧；audit parent_ref 回填 project_code；**R5 terminated project 双侧禁止 link（M3.6 新增）** |

**REF 小计**：25 条用例（M3.3 22 + M3.6 +2 R5 + M3.7 +1 R6）

### C.4 ARS（§8 资产域，V1.2 新增）

| V1.2 偏离项 | 测试文件 | 用例数 | 关键用例 |
|---|---|---|---|
| §6.1 asset 主表 + §6.2 market_id（CRUD）| `test_asset_crud.py` | 11 | create AST-XXXXXXX / get / update（version+1） / phase_change_at / soft delete / 枚举校验 |
| §6.4 状态机（hold/resume/terminate）+ §6.3 status_history + §6.4.2 电签 + §6.4.3 双权限 + **A3 change_reason 实值（M3.6）+ API1 错误码 40404（M3.8）**| `test_asset_state_machine.py` | 12 | hold/resume 往返；terminate 需 signature 嵌套对象（G1.B 后）；密码错 401 signature_invalid；缺 signature 422 signature_required；asset:sign 权限缺失 403；status_history 含 e_signature_id；status_history_recorded 加 A3 断言；**test_asset_not_found_returns_40404（API1）**|

**ARS 小计**：23 条用例

### C.5 跨主题实施侧加强 + G1 合规必修

| V1.1/V1.2 加强项 | 测试文件 | 用例数 | 关键用例 |
|---|---|---|---|
| V1.1 §5.2 失败副作用旁路 session（登录失败 / 签名失败计数不因 raise 而 rollback）| `test_auth_security.py` | 4 | 5 次错密码 → account_locked；解锁后重置；signature_invalid 也独立计数 |
| V1.1 §5.3 audit_trigger parent_ref（子表 entity_code 回填）| `test_audit_trigger_v2.py` | 3 | substance_xref / substance_protein / project_milestone 子表 audit_log.entity_code 回填父 code |
| V1.1 §5.1 service-level 显式 commit（响应后立即可见）| 隐式覆盖 | — | 全部状态机 + link 测试均依赖此（无失败说明已生效）|
| V1.1 §5.4 status_history.e_signature_id | `test_signature.py` + `test_project_state_machine.py` + `test_asset_state_machine.py` | 多处 | 签名后 status_history.e_signature_id 非空 |
| V1.1 §5.5 `meta.error.type` 401 分流 | `test_signature.py` + `test_auth_security.py` | 多处 | signature_invalid vs token_expired 区分；FE 不一刀切跳登录 |
| **UI3 / G1.A / G1.B 签名理由与 comment 分离（§11.50）**| `test_signature.py::test_signature_reason_independent_from_comment` | 1 | signature.reason ≠ comment 各自落到独立字段；signature 缺失 → 422 signature_required；signature.reason 缺失 → 422 pydantic |
| **G1.B 嵌套契约校验（隐式覆盖）**| 全部状态机 + 签名测试 | 多处 | 全部 json body 用 `{comment, signature:{password, reason}}`；响应用 `data.new_status`；无失败说明 schema/service 嵌套已生效 |

**跨主题加强**：直接专项 8 用例 + 多处间接覆盖

### C.6 全局搜索（API §3.2.2 + V1.2 §6.7 + G2-API6 V1.1 §8.3 分组结构）

| V1.2 偏离项 | 测试文件 | 用例数 | 关键用例 |
|---|---|---|---|
| 全局搜索 substance + project + asset 三类 + **G2-API6 响应分组结构（M3.10）**| `test_global_search.py` | 12 | substance name / project code / substance xref / types 过滤 / 权限分流（readonly 仅可见 read 权限实体）/ 401 未登录；asset name / code / trade_name / types=asset 过滤 / 默认返回三类；**test_search_response_structure：严格断言 data 含 query/total/results 三 key，results 含 substance/project/asset 三组，每组含 total + items 且 total == len(items)** |

**搜索小计**：12 用例（M3.4 +5 for asset，M3.10 +1 分组结构）

### C.7 基础冒烟

| 项 | 测试文件 | 用例数 |
|---|---|---|
| 健康检查 + 受保护端点鉴权 | `test_smoke.py` | 2 |

### C.8 总计

| 域 | 用例数 | 增量来源 |
|---|---|---|
| SRS（§7：state_machine + substance_crud + check_sameness + signature + audit_trigger × 2） | 35 | M3.4 32 + **M3.5 +2（S10/S11）+ M3.9 重写 signature_reason 测试（替换旧用例，net +1：用例从 2 个断言升级为 3 个断言：signature 缺失 + signature.reason 缺失）** |
| PRS（§9：project_crud + state_machine + milestone_team） | 25 | M3.4 24 + M3.7 +1（P9/P10 联合）；M3.6 加 P1 断言（不增用例）|
| ARS（§8：asset_crud + asset_state_machine） | 23 | M3.4 22 + **M3.8 +1（API1 错误码 40404）**；M3.6 加 A3 断言（不增用例）|
| REF（§11：3 张 link 表） | 25 | M3.4 22 + M3.6 +2（R5 双侧）+ M3.7 +1（R6 deleted_by 暴露） |
| auth_security（V1.1 §5.2 失败副作用旁路） | 4 | — |
| 全局搜索（test_global_search） | 12 | M3.4 11 + **M3.10 +1（API6 分组结构）** |
| 冒烟（test_smoke） | 2 | — |
| **合计** | **126** | ✅ M3.10 全量通过（2026-05-13）|

### C.9 验证门禁

- **每次 alembic upgrade head 后**：`make test-be` 全量 130 用例必须 100% 通过
- **生产部署前**：在生产基线数据库快照上跑全量 + 数据迁移演练（Phase 4 计划）
- **CI 门禁**（Phase 4 建设）：PR 合并前必须跑全量 + schema 一致性检查脚本

### C.10 测试不覆盖的项（待补）

| 项 | 当前状态 | 计划 |
|---|---|---|
| §10 物料域 | 未实施，无测试 | Phase 4 |
| `/auth/refresh` | 未实施 | Phase 4 |
| substance `:reject` / `:merge` | 未实施 | Phase 5 |
| asset `:advance-phase` | 未实施 | Phase 5 视业务必要性评估；当前 `current_phase` 由 PUT 直接更新，不等同于 `status` 状态机 |
| batch CRUD | 未实施 | Phase 5 |
| Redis 缓存层 / Prometheus 指标 | 未集成 | Phase 4-5 |
| 数据迁移演练（生产场景）| 未做 | 生产部署前 |
