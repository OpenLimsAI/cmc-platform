<!--
  AI-READABLE ARCHIVE — NOT a docx-derived doc, NOT covered by `make docs-check`.
  Purpose: 供后续 AI 会话（及工程师）快速掌握 PRS 项目管理模块相对
  SMP-RD-NUM-001 V2.1《研发资产与项目治理编号标准》的对齐现状，逐条差距标状态。
  维护约定：改动 PRS/SMP 对齐相关代码后，手工更新本表并核对断言（字段名/枚举/端点/迁移号）。
-->

# PRS ↔ SMP-RD-NUM-001 V2.1 对齐状态档（AI 阅读用）

- **源标准**：`docs/SMP-RD-NUM-001_V2.1.docx`（研发资产与项目治理编号标准，四层：Substance/Asset/Project/Study）。
- **对齐对象**：本仓 PRS 项目管理域（`backend/app/domains/prs/`、`backend/app/api/v1/projects.py`、`frontend/src/modules/projects/`）。
- **截至**：2026-07-15，migration head `0049`，`make test-be` 309 passed，commit `f1daf09`（三批 `0047/0048/0049`）。
- **原基准冲突**：PRS 代码注释多写"对齐 DM-MDM-001 V1.0"；当二者冲突，**以 SMP V2.1 为准**（负责人 2026-07-15 拍板）。
- **核实方式**：断言可能过期。字段/约束核对 `docker exec cmab-mdm-postgres psql -U postgres -d cmab_mdm -c "\d prs.project"`；枚举核对 `prs/models.py` CHECK + `prs/schemas.py` Literal；端点核对 `app/api/v1/projects.py`。

## 图例
`✅已解决` | `🟡部分(后端全/UI 欠)` | `⬜未做` | `➖范围外`

---

## 1. 逐条差距状态（对应初版差异分析"差距 1–7"+ §7A）

| # | SMP 要求 | 状态 | 落地位置 | 备注 |
|---|---|---|---|---|
| 编号格式 §7.1 | `CMAB-PRJ-YYYY-NNNN` | ✅ | migration 0047：触发器 `prs.fn_project_assign_code` + `services._next_project_code` 前缀 `CMAB-PRJ-` | 年内 4 位、每年重置。旧全局序列 `PRJ-` 行保留未回填 |
| 状态机 §11.3 | 补 `cancelled` | ✅ | 0047：CHECK + `STATE_MACHINE["cancel"]`(proposed/initiated→cancelled，需签名) | 未采用 SMP 的 `planned` 单步，保留现有 proposed→initiated 两步 |
| 分类维度(c) project_type §7.4(c) | Discovery/Nonclinical/CMC/Clinical/Regulatory/Translational/Mixed | ✅ | 0047：取值改 `discovery/nonclinical/cmc/clinical/regulatory/translational/mixed`（全小写） | 旧 `preclinical→nonclinical`；去 `commercial/platform/other` |
| 分类维度(a) project_category §7.4(a) | asset_related/non_asset | ✅ | 0048：列+CHECK；`schemas.ProjectCategory` | 创建默认 `non_asset`（API 层默认，前端表单必填） |
| 分类维度(b) project_nature §7.4(b) | NME/…/Discovery(9值) | ✅ | 0048：列+CHECK（全小写 9 值） | 创建默认 `discovery` |
| 资产关联 §7.5 | Asset→Project **1:N**，asset_id FK，asset_related 必填 | ✅ | 0048：`prs.project.asset_id` FK→`ars.asset`；`services._validate_asset_link` 条件必填 | 选**严格 1:N**（非保留 M:N）。`ref.project_asset` 多对多表**保留为辅助**，端点未拆 |
| owning_function §10.3 | 受控枚举 | ✅ | 0048：列+CHECK(rd/clinical/cmc/regulatory/qa/it/bd/finance/pmo/other) | 旧自由文本 `department` 降级为可选保留 |
| participating_functions §10.3 | 参与部门数组 | 🟡 | 0048：`jsonb` 列 + schema | **无前端 UI**（表单/详情均未加），仅 API 可写 |
| 审批字段 §10.3 | approval_date/reference/year | ✅(date/ref/year) 🟡(UI) | 0048：列；`change_status` 在 `approve` 回填 `approval_date`+`approval_year` | approval_reference 有表单？无——仅 detail 展示；approval_year **不展示** |
| governance_approval_ref §10.3 | DGC 批准号 | 🟡 | 0048：列 + detail 展示 | 无表单输入（仅 API 可写） |
| status_reason §10.3 | 主表状态原因 | 🟡 | 0048：列；`change_status` 写入 | 无独立 UI（状态历史表另有 change_reason） |
| sap_wbs_mapping / external_contract_refs / partner_reference §10.3 | SAP/合同/合作方 | 🟡 | 0048：列 + schema | **无前端 UI**，仅 API |
| project_phase 受控 §10.3 | discovery…post_marketing 枚举 | ✅ | 0048：列改 CHECK(nullable)；旧 `phase_N→pN` remap | 前端 create/edit 下拉、detail、list 均覆盖 |
| §7A 上市后变更 | regulatory_change_level/pre_approval_required/comparability_study_ref/regulatory_submission_refs | ✅(核心) 🟡(部分UI) | 0049：4 列 + CHECK(level)；`_validate_regulatory_change`(nature∈cmc_change/lcm 必填 level；major→pre_approval 强制) | UI：level/pre_approval/comparability 在 create/edit 条件区(nature∈cmc_change/lcm)+detail；**regulatory_submission_refs 无 UI** |
| §11.4-11.6 合并/拆分/衍生 | project_relationship 落地 | ✅ | `prs.project_relationship`(既有表) 补 `services.{list,add,delete}_relationship` + 端点 + detail「项目关系」Tab | 纯关联，**不改状态机**；in/out 双向。0065 本地修改改为取消保留原记录及双端审计，见下方后续记录 |
| §11.8 历史遗留编号 | legacy_project_id | ✅ | 0049：列 + create/edit 表单 + detail | |
| §11.8 / 附录C 保留/禁用编号清单 | RESERVED 编号 | ➖ | — | 偏**资产域**(SMP 例子均为 Asset ID 如 CMAB806)，留待资产域统一 |
| §12 治理角色 / §13 申请流程 / RACI | DGC/Steward/e-Request 工作流 | ➖ | — | 制度流程非系统字段；原型阶段不做（[[project_prototype_stage_posture]]） |

---

## 2. 权威枚举值（全小写，与 SMP CamelCase 有意偏离；核对 `prs/models.py` CHECK）

- **project_type**：`discovery, nonclinical, cmc, clinical, regulatory, translational, mixed`
- **project_status**：`proposed, initiated, active, on_hold, completed, terminated, cancelled`
- **project_category**：`asset_related, non_asset`
- **project_nature**：`nme, indication_expansion, geographic_expansion, lcm, regulatory_commitment, cmc_change, bd_evaluation, platform, discovery`
- **owning_function**：`rd, clinical, cmc, regulatory, qa, it, bd, finance, pmo, other`
- **project_phase**（nullable）：`discovery, lead_opt, ind_enabling, p1, p2, p3, filed, post_marketing`
- **regulatory_change_level**（nullable）：`minor, moderate, major`
- **relationship_type**：`merged_into, split_from, derived_from, depends_on, blocks`
- 状态机动作：`approve(→initiated), start(→active), hold, resume, complete, terminate, cancel(→cancelled)`；签名要求动作 = `{approve, complete, terminate, cancel}`

## 3. 新增/变更端点（`app/api/v1/projects.py`）
- `POST /projects/{code}:cancel`（0047，需签名）
- list `GET /projects` 新增查询参数：`project_category, project_nature, owning_function, asset_id`（0048）
- `GET/POST /projects/{code}/relationships`、`DELETE /projects/{code}/relationships/{relationship_id}`（0049）
- 附带：`AssetBrief` 增 `asset_id`（供项目绑定下拉），`app/domains/ars/schemas.py`

## 4. 迁移
- `0047_prs_smp_v21_batch1`：A1 前缀 / A2 cancelled / A3 project_type
- `0048_prs_smp_v21_batch2`：B1-B7（13 列 + FK + lookup）
- `0049_prs_smp_v21_batch3`：C1 §7A(4 列) + C3 legacy_project_id + lookup

## 5. 关键设计决策
1. 枚举值**全小写**，不照搬 SMP CamelCase（对齐本库既有 `mab/active/in_house` 惯例）。
2. 资产关联选**严格 1:N**（project.asset_id），`ref.project_asset` M:N 降级为辅助（端点未拆）。
3. 分类三维度 API 层给**默认值**（non_asset/discovery/rd，与 DB server_default 一致），"必填"由**前端表单**强制——避免打穿 7 个测试文件的既有创建方。
4. asset_id 条件必填、regulatory level 条件必填等**放 service 层**（DB 无法表达条件约束）。
5. major 级变更 `pre_approval_required` 未给时**服务端强制 true**；显式 false 则 400。

## 6. 大坑（改 PRS 约束必记）
本库 `MetaData` 命名约定 `ck: "ck_%(table)s_%(constraint_name)s"`，故模型里 `name="ck_project_x"` 的 CHECK 实际库名是**双前缀 `ck_project_ck_project_x`**。迁移里 drop/add 必须用双前缀名，否则新旧约束并存、老约束挡新枚举值（批一踩过，见 0047 注释）。

## 7. 后端完整、UI 欠缺（🟡 明细，后续如需补前端）
仅 API 可写、无表单/多数无展示：`participating_functions`、`approval_reference`(仅展示)、`approval_year`(不展示)、`governance_approval_ref`(仅展示)、`status_reason`、`sap_wbs_mapping`、`external_contract_refs`、`partner_reference`、`regulatory_submission_refs`。

## 8. 数据现状
PRS 项目真实数据 **0 条**（[[project_real_demo_dataset]]）；加必填/迁移零回填压力。物质/资产也为 0；物料~3770、设备~461 为真实数据，勿动。


## 9. 后续本地变更（2026-10-14，0065）
负责人已确认：项目关系建立和取消均填写至少5个字符的原因；取消前确认，保留记录、取消人和时间，取消后可重新建立。每个成功动作只写一份审计及字段明细，保存两端项目编码和关系类型；两端项目审计页均能查询。已有方向、类型、权限和项目状态规则保留，失败事务一起撤回，重复取消不重复留成功事件。0065 同时包含三主记录编辑和六类重复新增保护，需求、验证和阶段状态以 README 对应章节为准。本节仅说明本地修改，不宣称真实业务库或 Linux 已升级。
