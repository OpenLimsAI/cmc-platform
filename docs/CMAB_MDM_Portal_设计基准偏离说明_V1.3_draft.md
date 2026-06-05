# CMAB MDM Portal 设计基准偏离说明（V1.3）

| 项目 | 内容 |
|---|---|
| 文档编号 | DEV-MDM-001 |
| 版本 | V1.3 Draft |
| 状态 | 编制中（待 CMC IT 架构组评审） |
| 上位文档 | DM-MDM-001 V1.1 / ARCH-MDM-001 V1.1 / API-MDM-001 V1.1 / UI-MDM-001 V1.1（docx 签字基准） |
| 前序文档 | DEV-MDM-001 V1.2 Draft（封版于 migration 0036，2026-05-14；见其 §1B 封版声明，已转只读归档） |
| 覆盖范围 | **migration 0037 → 0044**（head cap：`0044_eqp_identifiers`）+ Phase 5 全部 + MM v2 + EQP 设备域 |
| 编制 | CMC R&D（实施侧） |
| 日期 | 2026-06-06 |
| 分类 | 合规审计配套文档 |

---

## 1. 文档目的与接力关系

V1.2_draft 封版于 2026-05-14（修订十二，head 0036）。其后代码主线推进了 8 个 migration（0037-0044）与 Phase 5 全部交付，期间产生的偏离、业务规则演化与上位文档缺口**均未在任何偏离说明中登记**——本文档补齐这一真空期，并作为 V1.3 docx 修订批次的决议依据。

三类处置标签沿用 V1.2：🟥 待对齐回归 / 🟢 实施侧合理加强（建议吸收）/ 🟠 未实施推迟。

---

## 2. 覆盖范围明细（0037-0044 + Phase 5）

### 2.1 Migration 增量

| revision | 日期 | 内容 | 偏离定性 |
|---|---|---|---|
| 0037_user_force_password_change | 2026-05-16 | auth.user.force_password_change（首登强改密） | 🟢 加强（V1.1 §4 未定义，Part 11 §11.300 支撑） |
| 0038_mm_material_v2 | 2026-05-19 | MM v2：material_type 4 值 + category 严格枚举 + 7 新字段 | 🟥→🟢 **业务规则取代**，见 §3.1 |
| 0039_mm_category_add_waibao | 2026-05-19 | category 加"外包材"（15 值定稿） | 同上 |
| 0040_eqp_equipment | 2026-06-04 | eqp schema + equipment 主表 + EQP-yyyy 编码 + audit trigger | 🟢 **新域**，见 §3.2 |
| 0041_eqp_add_fields | 2026-06-04 | rated_power / origin + 列注释校准 | 同上 |
| 0042_eqp_category_5class | 2026-06-04 | 设备分类 4 类 → 5 类 + 旧值重映射 | 同上 |
| 0043_eqp_workstation | 2026-06-05 | has_workstation + workstation_info JSONB | 同上 |
| 0044_eqp_identifiers | 2026-06-05 | 三标识体系：设备ID（系统）/ equipment_no（业务）/ fixed_asset_no（财务） | 同上 |

### 2.2 Phase 5 交付（无 migration 的应用层落地）

| 项 | 内容 | 对 V1.2 B 决议的回收 |
|---|---|---|
| 5.A 用户/角色/审计/个人中心 | admin_users / admin_roles / admin_audit（全局审计查询 + CSV 导出 + 签名列表）API + 前端 Admin UI | **API10:B 已落地**（原推迟 Phase 5/6）；**API11-rest（audit-logs/signatures 全局端点）已落地** |
| 5.B 仪表盘 | ECharts 接入，5 域统计 | **ARCH9:B 部分已落地**（ECharts；React Flow 未引入） |
| 5.C JWT RS256 | RS256（生产）/ HS256（开发）双模式 + RUNBOOK_JWT_RS256 | **ARCH2 合规升级完成** |
| EQP 横切 | 全局搜索第 5 类 + 仪表盘第 5 域 + Excel 表头驱动批量导入工具 | 新增能力（V1.1 无对应基准） |

**B 决议中仍未实施项**：P8 project_relationship 上层 API/UI（表自 migration 0016 存在，但 projects.py 无任何 relationship 端点）→ 继续 🟠 推迟，V1.3 评审确认去留。

---

## 3. 实质偏离与业务规则演化

### 3.1 MM v2 业务规则取代（migration 0038/0039 取代 0032 时期规则）

| 维度 | V1.1 §10 基准（= V1.2_draft §11.5.1 所记 0032 实现） | 现行（0038/0039） |
|---|---|---|
| material_type | 7 类型 | **4 值**：reagent / consumable / standard / column |
| 等级 | 4 等级（grade 枚举） | grade 改**自由文本** |
| category | 无独立 category | **15 值公司扁平枚举**（中文存储，含"外包材"），与 type 解耦 |
| material_code | 系统生成 MAT-yyyy | **用户输入为主**（公司既有编码，≤20 字符），trigger 仅兜底 |
| 新字段 | — | manufacturer / catalog_no / spec_model / unit NOT NULL / package_spec / hazard_class[] / category 共 7 个 |

**定性**：🟢 业务规则演化（物料身份注册表定位，对齐 LabOps 上游需求），**非实施错误**。V1.3 docx 修订时 DM §10 按现行规则重写；V1.2_draft §11.5.1 的历史记载不改（时点正确）。

### 3.2 EQP 设备域（V1.1 基准完全无此域）

全部为 🟢 新增（V1.2 修订记录行已在 md 声明，docx 待吸收）。上位文档同步缺口已勘误登记：

- **ARCH 缺口最大**：§1.3.2 仍把设备主数据列范围外（**与自身修订记录矛盾**）、§3.2 无 EQP 子节、§6.1 无 eqp 行 → 勘误 **E7/E8/E9**（ARCH 修订清单）
- DM：§10A 已有（md），§2.1 总表缺 eqp 行 → 并入 E3
- UI：权限矩阵缺设备行 + 两新角色列 → E4
- API：§5.1.6A 已有（md）

### 3.3 角色模型四方不一致（待评审决议）

DM §4.3 列 7 角色（含 **REGULATORY_USER**）/ ARCH §7.2.2 列 6 角色（camelCase）/ UI §2.2 列 6 角色 / 代码 seed **8 角色**（无 REGULATORY_USER，含 V1.2 两新角色）。

- REGULATORY_USER 从未实现（无 seed/权限绑定/UI/测试）→ 勘误 E12，**已决策方案 A 删除（2026-06-06，项目负责人）并落地**：代码无改动需要（seed 从未含），兜底清理脚本 `cleanup_regulatory_user.py` dev 实跑 no-op；决策依据：原型阶段简化角色体系，该场景用 READ_ONLY_USER + 临时权限码等价
- 角色命名 SNAKE_CASE 统一 + 8 角色补全 → 勘误 E10
- 2026-06-05 代码侧已修：STEWARD 补 project:read / asset:read / material:read 对齐 UI 矩阵（278 测试全过）

### 3.4 文档控制层面发现（流程级，非单点勘误）

1. **封面版本/文件名/修订记录三者脱钩**：四份上位文档封面均 V1.1、文件名 \*_V1_1，但派生 md 修订记录已含 V1.2 行；该 V1.2 行**只在 md**（docx 仍是自洽的 V1.1）。V1.3 批次规则：新增修订行 → 改封面版本字段 → 改文件名，三者绑定一次完成，随后重跑 `make docs-extract` 使 docs-check 回绿。
2. **docs-check 基线红**（自 commit 3ecf1f5 / 1b4d87c 起）：V1.2 增量被直接写入派生 md。过渡期权威 = 修订清单勘误段（E1-E12）+ 本文档；V1.3 docx 吸收后基线回绿。
3. **偏离说明封版机制**：每个 V1.x_draft 显式声明 head migration cap 与封版日期（V1.2_draft 已补 §1B）；主线越过 cap 时必须起新 _draft 接力，不允许真空期。

---

## 4. 测试基线桥（174 → 278）

| 时点 | 计数 | 增量内容 |
|---|---|---|
| 2026-05-13（修订十二基线，commit f477d86 实证） | **174** | csv_oq_traceability §1-§8 映射范围（总览已对账修正：101C + 68M + 5Min） |
| Phase 5 完成（2026-05-16） | 235 | +61：admin users/roles/audit、dashboard、force_password_change、RS256 |
| EQP 横切完成 | 275 | +40：MM v2 改造回归 + EQP CRUD/导入工具 |
| 2026-06-05（0043/0044） | 277 | +2：工作站 / 三标识 |
| 2026-06-05（STEWARD 权限断言） | **278** | +1：test_get_role_detail_substance_steward |

**OQ 卡点（P4.D 前置）**：174 之后的 104 条用例尚未进 OQ 追溯矩阵定级（csv_oq_traceability §0 已登记缺口）。OQ 执行前必须补完映射，否则证据链不闭合。

---

## 5. V1.3 docx 修订批次工作清单（汇总）

| # | 工作项 | 依据 | 状态 |
|---|---|---|---|
| 1 | 吸收 md 中既有 V1.2 增量（EQP §10A / API §5.1.6A / UI 设备导航 / 修订记录行）进 docx | docs-check 差异 | ⏳ |
| 2 | 勘误 E1-E12（四份修订清单 V1.3 勘误段，含建议吸收文字） | 修订清单 | ⏳ |
| 3 | B 决议建议吸收文字（V1.2_draft 附录 D：S5/S6、API4、ARCH9） | V1.2_draft | ⏳ |
| 4 | MM v2 规则重写 DM §10（本文档 §3.1） | 本文档 | ⏳ |
| 5 | 封面版本 + 文件名重命名 + docs-extract 重跑 | 本文档 §3.4 | ⏸ 不在原型阶段执行；待进入 GMP 准备阶段前一次性处理（连同 V1.3 docx 正文修订一起做）——2026-06-06 决策 |
| 6 | REGULATORY_USER 决议（E12 方案 A/B） | 项目负责人决策 | ✅ 已完成（2026-06-06 方案 A 删除并落地，见 §3.3 与 DM 修订清单 #E12） |
| 7 | P8 project_relationship 去留确认 | 评审会 | ⏳ |
| 8 | OQ 矩阵 +104 用例定级 | csv_oq §0 | ⏸ 不在原型阶段执行；待真正 GMP 启用前一次性补完——2026-06-06 决策 |

---

## 6. 评审记录

| 评审人 | 日期 | 决议 |
|---|---|---|
| _待 CMC IT 架构组_ | _待安排_ | _待评审_ |
| _待 QA 质量管理部_ | _待安排_ | _待评审_ |
