# UI-MDM-001（UI 信息架构与线框图）V1.0 → V1.1 修订清单

| 字段 | 值 |
|---|---|
| 文档 | UI-MDM-001 V1.0 → V1.1 |
| 上游决议 | DEV-MDM-001 V1.2_draft §6.4 / §9 / §8.3；DEV-MDM-001 V1.1_draft §5.5 |
| 修订总数 | 14 项 |
| 评审用途 | IT 架构组逐项决议「接受 / 拒绝 / 修改」，决议后秘书在 Word 修订模式下落地 |
| 备注 | 本清单不直接改 docx；M3.x 资产域 UI 是大头，§7.3 章节内多项细化合并为单一修订项以便集中决议 |

---

## 修订清单（按 docx 章节序）

### 修订 #1：§2.1 系统导航树 — 资产详情 Tab 补"状态历史"

| 字段 | 内容 |
|---|---|
| docx 章节 | §2.1 系统导航树（资产模块子树） |
| 修订类型 | 修改既有条目 |
| V1.0 原文位置 | §2.1 "💎 资产 (/assets)" 子节，资产详情 Tab 列表 |
| V1.0 原文摘录 | 资产详情下列 Tab：概览 / 多市场注册 / 关联物质（组分）/ 关联项目 / 审计日志（共 5 个） |
| V1.1 修订内容 | 调整为 6 个 Tab：基本信息 / 多市场注册号 / 关联物质 / 关联项目 / **状态历史**（新增）/ 审计 |
| 上游决议引用 | DEV-MDM-001 V1.2 §9.3 |
| 修订理由 | M3.1-M3.3 实施时资产域已落地 6 Tab，状态历史 Tab 需对齐 substance / project 三域统一风格 |

---

### 修订 #2：§2.3 全局快捷键 — Ctrl+K 标注为 Phase 4 路线图项

| 字段 | 内容 |
|---|---|
| docx 章节 | §2.3 全局快捷键 |
| 修订类型 | 加状态注脚（不删除条目） |
| V1.0 原文位置 | §2.3 快捷键表，第 1 行 |
| V1.0 原文摘录 | `Ctrl/Cmd + K` 打开全局搜索 |
| V1.1 修订内容 | 在表格"Ctrl/Cmd + K"行右侧加状态列「Phase 4 路线图」注脚；§2.3 章节末尾补一段："以上快捷键 Ctrl/Cmd+K 与 G→S/P/A/M 等导航快捷键在 Phase 1-3 未实现，仅保留'?'帮助和 Esc 关闭弹窗；详见附录 12.x 未实现项路线图。" |
| 上游决议引用 | DEV-MDM-001 V1.2 §9.2.1 |
| 修订理由 | M3.x 全局搜索仅有"点击聚焦"，Ctrl+K 推迟到 Phase 4 体验优化阶段 |

---

### 修订 #3：§3.2.2 全局搜索 — 加资产分组 + 三类实体范围

| 字段 | 内容 |
|---|---|
| docx 章节 | §3.2.2 全局搜索 |
| 修订类型 | 修改既有内容 |
| V1.0 原文位置 | §3.2.2 全局搜索描述段 |
| V1.0 原文摘录 | "结果按类型分组（物质 / 项目 / 资产 / 物料），每组最多 5 条" |
| V1.1 修订内容 | 明确说明 Phase 1-3 实际支持范围为 **物质 / 项目 / 资产** 三类（物料推迟到 Phase 4）；资产分组采用 purple Tag 区分；点击建议跳转 `/assets/:code` 详情页 |
| 上游决议引用 | DEV-MDM-001 V1.2 §6.7 / §9.3 |
| 修订理由 | M3.4 全局搜索已接入 asset entity_type；UI 文档原文写"4 类"会与实际不符 |

---

### 修订 #4：§7.3 资产详情页 — 整体重写为 6 Tab 完整规范

| 字段 | 内容 |
|---|---|
| docx 章节 | §7.3 资产详情页 |
| 修订类型 | 重大重写（章节扩充） |
| V1.0 原文位置 | §7.3.1 阶段推进对话框前的 Tab 列表（5 行简要） |
| V1.0 原文摘录 | "Tab 1：概览（基本信息 + 当前阶段时间线）/ Tab 2：多市场注册 / Tab 3：关联物质（组分）/ Tab 4：关联项目 / Tab 5：审计" |
| V1.1 修订内容 | 重写为 6 Tab 详细规范，每 Tab 含字段清单与线框图（参考 §6.2 物质详情页粒度）：<br>- **Tab 1 基本信息**：asset_code / internal_name / trade_name / inn_name / generic_name / asset_type / modality / current_phase / approval_status / target_indication / mechanism_of_action / route_of_administration / sponsor_id / status / confidentiality + 描述字段；阶段推进按钮（保留原 §7.3.1 阶段推进对话框）<br>- **Tab 2 多市场注册号**：表格列 = region / market / status / market_id / approval_date / first_launch_date / withdrawal_date / discontinuation_date / trade_name_local / regulatory_authority；MarketIdTable 组件支持 CRUD（详见修订 #8）<br>- **Tab 3 关联物质（组分）**：表格列 = substance_code / preferred_name / role（main_component / antibody / linker / payload / adjuvant）/ stoichiometry / is_active_ingredient / notes；AssetSubstanceTab 组件支持新增 / 编辑 / 移除（详见修订 #8）<br>- **Tab 4 关联项目**：表格列 = project_code / project_name / relation_type（development / clinical / cmc / regulatory / supply）/ is_primary / start_date / end_date / notes；AssetProjectTab 组件支持双向绑定（详见修订 #8）<br>- **Tab 5 状态历史**：时间线视图，含 status / changed_at / changed_by / reason / e_signature_id（链接到签名详情），与 substance / project 三域统一<br>- **Tab 6 审计**：与 §6.2.7 同结构，按 entity_schema=ars / entity_type=asset 过滤 |
| 上游决议引用 | DEV-MDM-001 V1.2 §6.1-§6.4 / §9.3 |
| 修订理由 | M3.1-M3.3 资产域已完整实现 6 Tab，V1.0 仅 5 Tab 简述且无字段粒度；UI 文档需与 SRS / PRS 详情页粒度对齐 |

---

### 修订 #5：§7.3 资产域 — 新增 4 页面规范（List / Create / Detail / Edit）

| 字段 | 内容 |
|---|---|
| docx 章节 | §7.3 资产详情页（章节内补充 §7.3.0 资产列表页 / §7.3.2 资产创建页 / §7.3.3 资产编辑页） |
| 修订类型 | 新增子章节 |
| V1.0 原文位置 | V1.0 §7.3 仅有详情页与阶段推进对话框，缺列表 / 创建 / 编辑页线框 |
| V1.0 原文摘录 | — |
| V1.1 修订内容 | 补充 3 个子章节：<br>- **§7.3.0 资产列表页**：列 = asset_code / internal_name / asset_type / modality / current_phase / approval_status / target_indication / sponsor / status / updated_at；筛选 = current_phase / approval_status / asset_type / target_indication / 关键词；空状态 + 分页同 §5 通用模式<br>- **§7.3.2 资产创建页**：单页表单（非 Steps），字段分组 = 编码与命名 / 分类与适应症 / 阶段与审批状态 / 关联（sponsor_id）/ 描述与备注；create 后状态默认 = `active`（资产无 draft 态）<br>- **§7.3.3 资产编辑页**：复用创建页表单 + version 乐观锁 + 不可修改字段（asset_code / asset_type 创建后只读） |
| 上游决议引用 | DEV-MDM-001 V1.2 §9.3 |
| 修订理由 | M3.1 资产域已交付 List / Create / Detail / Edit 4 页面，V1.0 缺前 3 个页面的线框定义 |

---

### 修订 #6：§7.3.x 新增「资产状态变更对话框」（hold / resume / terminate）

| 字段 | 内容 |
|---|---|
| docx 章节 | §7.3 资产详情页（在阶段推进对话框 §7.3.1 之后新增 §7.3.x，建议命名 §7.3.2 资产状态变更对话框；原 §7.3.2 创建页等顺延为 §7.3.3 / §7.3.4） |
| 修订类型 | 新增子节（区别于已有的 §7.3.1 阶段推进对话框） |
| V1.0 原文位置 | V1.0 §7.3 仅有 §7.3.1「阶段推进对话框」（advance-phase UI），**未涉及 hold / resume / terminate 三个状态机动作的对话框**；该 §7.3.1 对应的 `:advance-phase` 端点 V1.0 已声明但 Phase 1-3 未实施（推迟至 Phase 5，见修订 #13 路线图） |
| V1.0 原文摘录 | §7.3.1 阶段推进对话框（含目标阶段 / 阶段变更日期 / 推进原因 / 密码确认）—— 此对话框是 advance-phase 用，**不是** hold/resume/terminate 用 |
| V1.1 修订内容 | 新增 §7.3.x「资产状态变更对话框（hold / resume / terminate）」，明确与 §7.3.1 阶段推进对话框**不同**：<br>1. **触发位置**：资产详情页右上"状态变更"按钮（当前 status=active 时显示 hold/terminate；status=on_hold 时显示 resume/terminate；status=terminated 时无可用动作）<br>2. **公共字段**：变更原因（≥5 字，前后端双校验，错误提示"请填写变更原因（至少 5 个字符）"）<br>3. **签名要求按动作分**：<br>   - `hold` / `resume`：**不要求电子签名**（可逆调整）—— 对话框无密码字段<br>   - `terminate`：**强制电子签名**（关键不可逆动作，21 CFR Part 11 §11.50）—— 对话框含「电子签名密码 *」+「签名理由 *」<br>4. **二次确认弹窗**：terminate 提交前再弹一次"确认终止资产？此操作将记录电子签名且不可撤销"；hold/resume 不弹二次确认（轻量操作）<br>5. **密码错误 errorType 分流**：仅 terminate 涉及；401 + `errorType=signature_invalid` → 仅显示"密码错误，请重新输入"且保留对话框，不清 token、不跳登录（详见修订 #11）<br>6. **章节关联**：本对话框抽象自 §9.2.1 状态变更全局交互模式（见修订 #10），与 substance / project 同模式 |
| 上游决议引用 | DEV-MDM-001 V1.2 §6.4 / V1.1 §5.5 |
| 修订理由 | V1.0 仅画了 advance-phase 对话框（推迟项），但 M3.2 实施落地的是 hold/resume/terminate 三个状态机动作的对话框；这两类对话框语义不同（current_phase vs status 两个独立维度），UI 文档须分开描述以免开发误用 |

---

### 修订 #7：§7.4 物料模块 — 标注为 Phase 4 路线图，保留 V1.0 线框作设计预留

| 字段 | 内容 |
|---|---|
| docx 章节 | §7.4 物料模块 |
| 修订类型 | 加状态注脚（不删除内容） |
| V1.0 原文位置 | §7.4 物料模块（含 §7.4.1 批次 Tab） |
| V1.0 原文摘录 | "物料模块结构最简单，列表 → 详情 → 批次列表" + 批次表线框 |
| V1.1 修订内容 | 章节开头加注脚框：「**实施状态（V1.1）**：物料域（MM）整体 UI 在 Phase 1-3 未实现，前端仅 PlaceholderPage 占位；下方线框为 Phase 4 设计预留，实施时以 DEV-MDM-001 V1.x §6.x 偏离说明为准。」 |
| 上游决议引用 | DEV-MDM-001 V1.2 §9.2.5 |
| 修订理由 | 物料模块 UI 推迟到 Phase 4，但 V1.0 线框可保留作设计基线，避免后续返工；评审组决定是否保留章节 vs 移到附录路线图 |

---

### 修订 #8：§8.1 业务组件清单 — 新增 M3.x 资产域组件

| 字段 | 内容 |
|---|---|
| docx 章节 | §8.1 业务组件设计（组件表） |
| 修订类型 | 表格新增行 |
| V1.0 原文位置 | §8.1 组件表（共 19 个组件，从 EntityCodeLink 到 EmptyState） |
| V1.0 原文摘录 | （表格已含 EntityRelationsTable / StatusBadge 等通用组件，未列资产域专用组件） |
| V1.1 修订内容 | 在组件表末尾追加 5 行：<br>- **MarketIdTable**：多市场注册号 CRUD 组件 / Props = `assetCode, readonly, onChange` / 含 4 日期字段（approval/launch/withdrawal/discontinuation）+ status Tag<br>- **AssetSubstanceTab**：资产侧组分绑定 Tab / Props = `assetCode, readonly` / 支持新增 / 编辑 role / stoichiometry / 移除<br>- **AssetProjectTab**：资产侧项目绑定 Tab / Props = `assetCode, readonly` / 支持选择项目 + relation_type<br>- **ProjectAssetTab**：项目侧资产绑定 Tab（反向）/ Props = `projectCode, readonly` / 与 AssetProjectTab 共用 API 但视角不同<br>- **RelatedAssetsTab**：物质详情侧反向只读列表 / Props = `substanceCode` / 仅展示，不提供 CRUD（资产侧才是源头） |
| 上游决议引用 | DEV-MDM-001 V1.2 §9.3 |
| 修订理由 | M3.1-M3.3 实施落地这 5 个跨域 Tab / Table 组件，需进组件清单作为前端复用约定 |

---

### 修订 #9：§8.x 业务组件 — 终止态资产绑定按钮禁用规则（仅 `status='terminated'`）

| 字段 | 内容 |
|---|---|
| docx 章节 | §8.x（新增子节，建议放在 §8.4 PermissionGuard 之后作 §8.5） |
| 修订类型 | 新增子节 |
| V1.0 原文位置 | V1.0 §8 通用组件清单未涉及业务规则态禁用 |
| V1.0 原文摘录 | — |
| V1.1 修订内容 | 新增 **§8.5 业务规则态禁用**：<br>① **资产域（ARS）禁用以 `asset.status='terminated'` 为唯一判定依据**——所有写入按钮（添加市场注册号 / 添加组分 / 添加项目绑定 / 编辑）置 disabled + tooltip 提示"资产已终止，禁止变更绑定关系"。<br>② **`asset.current_phase='discontinued'` 不触发禁用**——current_phase 与 status 是 ARS 两个独立维度（业务进度 vs 管控状态），discontinued 只是阶段标记，不影响绑定行为；该资产仍可被关联、编辑（如有 status=active）。<br>③ **物质域（SRS）**：`substance.status='obsoleted'` 触发禁用（与 ARS terminated 同语义——终态、不可逆）；`status='deprecated'` 是可恢复弃用态，**不禁用**新建关联（service 层校验亦不拒绝，与 M3.3 实施一致）。<br>④ **项目域（PRS）**：`project.status='terminated'` 触发禁用；其他状态（active / on_hold / completed）不影响绑定。<br>⑤ 上述判定与后端 service 层业务规则一致（V1.2 §6.6.4、§3 obsoleted 物质禁新关联），UI 仅做按钮态反馈，最终拒绝由后端 422 错误兜底。 |
| 上游决议引用 | DEV-MDM-001 V1.2 §9.3 / §6.4 / §6.6.4 |
| 修订理由 | M3.3 实施时已落地此交互；V1.0 仅在 §9.2 提到"二次确认"但未涉及"按钮态禁用"的统一规则；本次评审明确：(a) ARS 禁用必须按 status='terminated' 而非 current_phase='discontinued'（两个维度），(b) SRS 禁用按 obsoleted 而非 deprecated（终态 vs 可逆态）——避免开发与测试组合并术语 |

---

### 修订 #10：§9.2 不可逆操作 — 状态变更交互模式纳入"全局交互模式"

| 字段 | 内容 |
|---|---|
| docx 章节 | §9.2 不可逆操作的二次确认 |
| 修订类型 | 章节扩充 + 新增子节 |
| V1.0 原文位置 | §9.2 含确认对话框模式线框（删除原因 + 确认按钮） |
| V1.0 原文摘录 | 软删除确认对话框线框；条目列表含 "Substance 弃用 / 合并、Project 终止、电子签名提交" 等 |
| V1.1 修订内容 | 在 §9.2 后新增 **§9.2.1 状态变更通用交互模式**：明确所有三域（SRS substance / PRS project / ARS asset）的状态流转 UI 统一规范：<br>1. **触发方式**：详情页右上操作菜单 → 选择当前状态可用的动词命令（按状态机派发，UI 自动过滤）<br>2. **公共必填字段**：「变更原因 *」（≥5 字校验，前后端双校验）<br>3. **签名字段按动作分（不是所有状态变更都签）**——仅 **关键不可逆动作** 强制电子签名：<br>   - **SRS substance**（4 个签字动作）：`approve` / `activate` / `deprecate` / `obsolete`<br>   - **PRS project**（3 个签字动作）：`approve` / `complete` / `terminate`<br>   - **ARS asset**（1 个签字动作）：`terminate`<br>   - 其他动作（如 substance.reject 推迟未实现 / project.start / project.hold / project.resume / asset.hold / asset.resume）**不要求电子签名**，对话框无密码字段<br>   - 是否签字由后端 `SIGNATURE_REQUIRED_ACTIONS` 集合权威定义；前端按 `ACTION_TO_MEANING` constants 渲染对应字段<br>4. **二次确认弹窗**：仅签字动作（不可逆）触发二次确认；可逆动作（hold/resume 等）不弹<br>5. **401 响应 errorType 分流**：仅签字动作涉及；详见 §9.6 errorType 处置约定（修订 #11）<br>6. **提交成功后**：刷新详情页 + Toast 通知 + 状态历史 Tab 立即追加新条目；签字动作的 status_history.e_signature_id 非空，可逆动作的 e_signature_id 为空 |
| 上游决议引用 | DEV-MDM-001 V1.2 §6.4 / §9.1 |
| 修订理由 | M2.5 + M3.x 实施时三域状态变更 UI 已统一为此模式（变更原因 ≥5 字 + 二次确认 + 密码 + errorType 分流），V1.0 仅在 §6.4 物质审核流程画了一次，未抽象为全局交互模式 |

---

### 修订 #11：§9.x 新增 — errorType 体系与 axios 拦截器分流约定

| 字段 | 内容 |
|---|---|
| docx 章节 | §9（新增子节，建议放在 §9.5 锁与并发之后作 §9.6） |
| 修订类型 | 新增子节 |
| V1.0 原文位置 | V1.0 §9 关键交互模式未涉及 401 分流 / errorType |
| V1.0 原文摘录 | — |
| V1.1 修订内容 | 新增 **§9.6 401 响应 errorType 分流（axios 拦截器约定）**：<br>**背景**：电子签名密码错（业务身份再验证）与 JWT 过期（会话失效）都返回 401，但语义不同。前端拦截器若一律按"会话失效"清 token 跳登录，会把签名密码错的用户错误踢出。<br>**约定**：前端 `api/client.ts` 的 axios response 拦截器按 `errorType` 字段分流：<br>- `errorType=token_expired` 或 `token_invalid` → 清 localStorage token + redirect 到 `/login?redirect=...`<br>- `errorType=signature_invalid` → **保留 token**，仅在调用方对话框内显示"密码错误，请重新输入"，**不跳登录**<br>- 无 `errorType` 字段或未知值 → 默认按会话失效处理（向后兼容）<br>**实施位置**：`frontend/src/api/client.ts`；调用方（如 ESignatureDialog）捕获后单独处理 |
| 上游决议引用 | DEV-MDM-001 V1.1 §5.5；DEV-MDM-001 V1.2 §8.3 |
| 修订理由 | M2.5.2 / M2.5.3 实施时落地此分流逻辑，V1.0 文档完全未提；为前端工程师交接和测试用例设计提供 UI 侧规范依据 |

---

### 修订 #12：§12.1 路由清单 — 新增 ChangePasswordPage + Phase 1-3 实施状态列

| 字段 | 内容 |
|---|---|
| docx 章节 | §12.1 路由清单 |
| 修订类型 | 表格扩充 + 新增列 |
| V1.0 原文位置 | §12.1 路由清单表（已含 `/profile/password` → `PasswordChangePage`） |
| V1.0 原文摘录 | `/profile/password` 行：组件 `PasswordChangePage` / 权限 `已登录` / 说明 `修改密码` |
| V1.1 修订内容 | 1. 将组件名校准为 `ChangePasswordPage`（M2.5.x 实施侧实际命名）；<br>2. 路由清单表追加"实施状态"列，逐行标注 ✅ 已实施 / 🚧 Placeholder / ⌛ Phase 4-6 路线图：<br>- ✅：`/login`、`/dashboard`、`/substances/*`、`/projects/*`、`/assets/*`、`/search`、`/profile`、`/profile/password`<br>- 🚧 Placeholder：`/materials/*`、`/audit/logs`、`/audit/signatures`、`/admin/*`<br>3. `ChangePasswordPage` 行说明加："含 §11.300 提示 + 旧 token 即时失效（password_changed_at 变化触发）" |
| 上游决议引用 | DEV-MDM-001 V1.2 §9.3 / §9.2.5-9.2.7 |
| 修订理由 | M2.5 修改密码页已交付且符合 §11.300；其他 Placeholder 路由实施状态需在文档中标注，避免测试组误以为已完成 |

---

### 修订 #13：§12 附录 — 新增"未实现项路线图"附录章

| 字段 | 内容 |
|---|---|
| docx 章节 | §12（新增子节，建议作 §12.3 未实现项路线图） |
| 修订类型 | 新增附录子节 |
| V1.0 原文位置 | V1.0 §12 附录仅含 §12.1 路由清单 / §12.2 前端目录结构 |
| V1.0 原文摘录 | — |
| V1.1 修订内容 | 新增 **§12.3 未实现项路线图（Phase 4-6）**：表格列 = 项 / V1.0 章节引用 / 当前状态 / 优先级 / 计划阶段。条目（共 10 项，来自 DEV-MDM-001 V1.2 §9.2）：<br>1. Ctrl+K 全局搜索快捷键（§2.3）— 仅有点击聚焦 — 中 / Phase 4<br>2. 项目详情概览 Tab 甘特图（§7.2.1）— 仅 Descriptions — 中 / Phase 5<br>3. 项目 / 资产列表多视图切换（表格 / 看板 / 时间轴）（§7.1）— 仅表格 — 低 / 体验增强<br>4. 创建表单 Steps 分步（§6.3.1）— 单页表单 — 低 / 等价<br>5. 物料模块整体 UI（§7.4）— PlaceholderPage — 高 / Phase 4<br>6. 系统管理子页（用户 / 角色 / 权限矩阵 / 编码序列 / 字典 / 配置）（§2.1 / §12.1）— Placeholder — Phase 5-6<br>7. 独立审计日志页（§7.6）— Placeholder（详情页内 AuditLogPanel 已实现）— 中 / Phase 4<br>8. 密码复杂度强制（大小写 + 数字 + 特殊字符）（§4.1.2）— 仅长度 ≥8 — 中 / 合规建议<br>9. 仪表盘高级功能（项目状态分布图表 / 系统公告动态加载）（§4.2）— 部分静态 — 低 / Phase 5<br>10. 项目详情 `sponsor_id` 显示为 user 名称而非 ID — 当前显示 ID — 低 / 单点 UX 修复<br>11. **资产阶段推进对话框（advance-phase UI）**（§7.3.1）— V1.0 已画线框，但 `:advance-phase` 端点 Phase 1-3 未实现（当前用 PUT 直接更新 current_phase）— 中 / Phase 5（与端点同步上线；详见 API-MDM-001 修订 #15） |
| 上游决议引用 | DEV-MDM-001 V1.2 §9.2 全部条目 |
| 修订理由 | 集中标注所有"V1.0 已设计但 Phase 1-3 未实现"的 UI 项，避免散落在各章节注脚；为 Phase 4-6 排期提供输入；评审组也可在此章节统一决议优先级 |

---

### 修订 #14：封面修订记录 — 增 V1.1 行

| 字段 | 内容 |
|---|---|
| docx 章节 | 封面"修订记录"表 |
| 修订类型 | 表格新增行 |
| V1.0 原文位置 | 封面"修订记录"表，目前仅 V1.0 一行 |
| V1.0 原文摘录 | V1.0 / 2026-05-11 / CMC IT 架构组 / 初始版本，定义信息架构、设计系统、关键页面线框、组件清单 |
| V1.1 修订内容 | 追加一行：<br>V1.1 / 2026-05-12 / CMC IT 架构组 / 吸收 Phase 1-3（M1-M3.4）实施偏离：补资产域 4 页面 + 6 Tab + MarketIdTable / AssetSubstanceTab / AssetProjectTab / ProjectAssetTab / RelatedAssetsTab 组件；纳入状态变更全局交互模式；新增 errorType 401 分流约定；新增"未实现项路线图"附录；路由清单加实施状态列；其他细化与状态注脚 |
| 上游决议引用 | DEV-MDM-001 V1.2_draft 整体 |
| 修订理由 | 标准修订记录维护 |

---

## 评审决议汇总表（评审组填写）

| # | 修订项 | 决议（接受/拒绝/修改） | 修改意见 | 决议人 | 决议日期 |
|---|---|---|---|---|---|
| 1 | §2.1 资产 6 Tab |  |  |  |  |
| 2 | §2.3 Ctrl+K 路线图注脚 |  |  |  |  |
| 3 | §3.2.2 全局搜索三类实体 |  |  |  |  |
| 4 | §7.3 资产详情页 6 Tab 重写 |  |  |  |  |
| 5 | §7.3 资产域 4 页面 |  |  |  |  |
| 6 | §7.3.1 状态变更交互细化 |  |  |  |  |
| 7 | §7.4 物料模块 Phase 4 注脚 |  |  |  |  |
| 8 | §8.1 资产域 5 组件 |  |  |  |  |
| 9 | §8.5 terminated 按钮禁用 |  |  |  |  |
| 10 | §9.2.1 状态变更全局交互模式 |  |  |  |  |
| 11 | §9.6 errorType axios 分流 |  |  |  |  |
| 12 | §12.1 路由清单 + 实施状态列 |  |  |  |  |
| 13 | §12.3 未实现项路线图附录 |  |  |  |  |
| 14 | 封面修订记录 V1.1 行 |  |  |  |  |

---

## 关联文档

- 偏离说明（决议依据）：`docs/CMAB_MDM_Portal_设计基准偏离说明_V1.2_draft.md` §6.4 / §8.3 / §9
- 偏离说明（401 分流背景）：`docs/CMAB_MDM_Portal_设计基准偏离说明_V1.1_draft.md` §5.5
- 其他 V1.1 修订清单：DM-MDM-001 / API-MDM-001 / ARCH-MDM-001（同目录）
