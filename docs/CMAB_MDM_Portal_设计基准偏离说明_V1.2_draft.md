# CMAB MDM Portal 设计基准偏离说明

| 项目 | 内容 |
|---|---|
| 文档编号 | DEV-MDM-001 |
| 版本 | V1.2 Draft |
| 状态 | 待 CMC IT 架构组评审 |
| 上位文档 | DM-MDM-001 V1.1 / ARCH-MDM-001 V1.1 / API-MDM-001 V1.1 / UI-MDM-001 V1.1 |
| 编制 | CMC R&D（实施侧） |
| 日期 | 2026-05-12 |
| 分类 | 合规审计配套文档 |
| 历史 | V1.1 Draft（2026-05-11，覆盖 Phase 1-2.5 + M3.0 回归）<br>V1.2 Draft（本版，新增 M3.1-M3.4 ARS 资产域 + 跨域引用补齐 + 跨文档检查） |

## 1. 文档目的

本版（V1.2）在 V1.1 基础上增补 Phase 3（M3.1-M3.4）实施过程中识别的所有新偏离 / 加强 / 推迟项，并把检查范围从单一的"数据模型设计文档"扩展到 4 个上位文档（数据模型 + 架构 + API + UI 信息架构）。

V1.1 已记录的偏离与处置在第 2-5 节保留不变（部分状态从"待对齐"改为"已对齐"反映 M3.0 实际完成）；V1.2 新增内容集中在第 6-9 节。

三类处置标签不变：
- **🟥 待对齐回归**：将通过迁移强制回归至设计基准。
- **🟢 实施侧合理加强**：基于合规要求或工程坑位保留实施版本，建议吸收进上位文档下一版。
- **🟠 未实施 / 推迟**：设计要求但当前阶段未实施的部分，列入后续里程碑。

---

## 2. SRS（§7 物质域）— V1.1 状态延续

V1.1 §2 全部条目通过 M3.0.3 migration 0018-0021 完成对齐回归。当前实施与 §7 基准 100% 一致。

V1.2 新发现项：无。

---

## 3. PRS（§9 项目域）— V1.1 状态延续

V1.1 §3 全部条目通过 M3.0.2 migration 0013-0017 完成对齐回归。

V1.2 新发现项：无（V1.1 §3.3.5 "团队 unique 离开后再加入语义" 仍待 §9.4 文档修订决定）。

---

## 4. REF（§11 跨域引用）— V1.1 +补建

V1.1 §4.1 / §4.2 / §4.3 状态更新：

| 表 | 文档章节 | V1.1 状态 | V1.2 状态 | 备注 |
|---|---|---|---|---|
| `ref.project_substance` | §11.2 | ✅ M3.0.1 重构完成 | ✅ 保持 | — |
| `ref.asset_substance` | §11.3 | 🟠 未建（Phase 3 ARS 时建）| ✅ M3.3 已建（migration 0025）| 见 §6.3 |
| `ref.project_asset` | §11.4 | 🟠 未建（Phase 3 ARS 时建）| ✅ M3.3 已建（migration 0026）| 见 §6.4 |

---

## 5. 跨主题实施侧合理加强 — V1.1 状态延续

V1.1 §5.1-§5.5 全部 5 项（service-level commit / 旁路 session / parent_ref / e_signature_id / `meta.error.type` 401 分流）状态不变，建议 V1.1 文档评审时一并吸收。

> 说明：V1.0 API 错误响应的机器可读错误类型字段位于 `meta.error.type`。本文件中原称 “`meta.error.type`” 的内容统一解释为 `meta.error.type` 字典 / 分流规则，除非后续评审明确决定调整 API 响应结构。

V1.2 在 §10 增补 1 项（asyncpg 池 SET LOCAL GUC 泄漏修复），见下文。

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

### 7.3 已对齐项（无偏离）

技术栈 / 分层结构 / JWT 认证 / RBAC / 审计追踪 / 中间件链均与 ARCH-MDM-001 V1.0 一致。架构层面对齐率 **95%**（缺口主要在生产部署 / 可观测性，非核心阻塞）。

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

### 8.4 已对齐项

CRUD 路径 / 响应格式（code/message/data/meta + pagination）/ 错误码 HTTP 映射 / 状态机端点路径 / 审计端点 / 跨域绑定端点均与 API-MDM-001 V1.0 一致。API 层面对齐率 **~85%**（缺口集中在 batch / refresh / merge / advance-phase 等非核心扩展端点）。

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
| **V1.1 / V1.2 评审** | **IT 架构组评审本偏离说明 + 决定吸收哪些"实施侧合理加强"到上位文档** | 🚧 待安排 |
| Phase 4 | 物料域（MM）基础域 + `/auth/refresh` + 全局搜索 material 接入 + 独立审计页 + Prometheus / 集中日志 / 生产部署配置 + 备份恢复演练 + CSV 验证准备 | 🚧 待开工 |
| Phase 5 | 数据治理工具（merge / reject / batch / advance-phase 视需）+ Redis 缓存 + 系统管理 Admin UI + 复杂 fuzzy matching / 体验增强 | 🚧 待开工 |

---

## 11. 风险与缓解 — V1.1 状态延续

V1.1 §7 内容不变。新增风险：

| 风险 | 影响 | 缓解 |
|---|---|---|
| `asset_market_id` / `ref.asset_substance` / `ref.project_asset` 缺 `deleted_by` 与其他子表不一致 | 已通过 DM-MDM-001 V1.1 修订吸收，风险关闭 | 已统一补 `deleted_by`，与 `deleted_at` 共同构成标准 soft-delete 字段组 |
| `/auth/refresh` 缺失，access_token 30 min 过期需重登 | 低（dev / UAT 阶段）| 生产前补 refresh 端点 |
| Redis 部署但未用，docker-compose 资源浪费 | 极低 | Phase 5 接入或先从 dev compose 移除 |

---

## 12. 评审记录

| 评审人 | 日期 | 决议 |
|---|---|---|
| _待 CMC IT 架构组_ | _待安排_ | _待评审_ |
| _待 QA 质量管理部_ | _待安排_ | _待评审_ |

---

## 附录 A：跨文档对齐率汇总

| 上位文档 | 当前对齐率 | 主要缺口 |
|---|---|---|
| DM-MDM-001 V1.1（数据模型）| **~99%** | `asset_market_id.deleted_by` / `ref.asset_substance.deleted_by` / `ref.project_asset.deleted_by` 已吸收；§10 物料域整域未实施（Phase 4）|
| ARCH-MDM-001 V1.1（架构）| **~95%** | Redis 应用层 / Prometheus / 集中日志 / 生产部署配置未做（Phase 4-5）；路线图已与本文件统一 |
| API-MDM-001 V1.1（API）| **~85%** | refresh / reject / merge / advance-phase / batch CRUD 推迟（Phase 4-5）；protein/adc/xrefs 实施侧用 expand 简化；`meta.error.type` 字典已正式入文档 |
| UI-MDM-001 V1.1（UI 信息架构）| **~82%** | 物料域 UI / 系统管理 Admin / 项目甘特图 / 多视图切换 / Ctrl+K 等推迟；ARS 资产域 UI 与状态/阶段语义已补齐 |

**整体加权对齐率**：**~90%**（按当前 Phase 1-3 功能范围加权）。Phase 1-3 范围（substance / project / asset / ref）的核心设计路径已形成闭环，包括审计追踪、电子签名、权限控制、失败留痕与状态历史；但生产部署级控制、备份恢复演练、集中日志、完整 CSV 文档包以及 Phase 4-5 范围（material / admin / batch / 缓存 / 监控）仍按计划推迟，不能表述为生产级 GxP 全面完成。

---

## 附录 B：自动化检查工具

V1.1 §附录 A 提到的"schema 一致性检查脚本"仍未实现，列入 Phase 4 / CI 门禁建设计划。

当前回归依赖 `backend/tests/` 中 117 条 pytest 用例（M3.4 完成时计数）。每次 alembic upgrade head + pytest 全量通过作为 M3.x 各里程碑验收门禁。

详细的「偏离项 → 测试覆盖」映射见**附录 C**（CSV 验证 IQ/OQ 阶段证据链）。

---

## 附录 C：偏离项 ↔ 回归测试覆盖映射

本附录提供 V1.2 各偏离项 / 实施侧加强的回归测试证据链，供 CSV 验证 IQ（安装确认）/ OQ（操作确认）阶段引用。

### C.1 SRS（§7 物质域）

| V1.2 偏离项 | 测试文件 | 用例数 | 关键用例 |
|---|---|---|---|
| §2 SRS 子表（§7.4 ADC / §7.5 small_molecule / §7.8 alias）补建 | `test_substance_crud.py` | 7 | create / get / update（version+1）/ 乐观锁 / 重复 internal_code / soft delete |
| §7.6 substance_xref effective/expiry + 唯一约束 | `test_substance_crud.py` + `test_check_sameness.py` | 5 | sameness 判定走 xref |
| §7.7 substance_status_history 状态机 | `test_state_machine.py` | 5 | full_lifecycle / invalid_transition / reason_too_short / restrict→deprecate / status_history_recorded |
| §7.7 substance_status_history.e_signature_id（V1.1 §5.4 加强）| `test_signature.py` | 8 | approve / activate / deprecate / obsolete 签名流；密码错；缺签名；signature_invalid 分流 |
| §7.3 substance_protein DB 触发器（hash 自动算）| `test_audit_trigger.py` + `test_audit_trigger_v2.py` | 4+3 | INSERT/UPDATE hash 一致；parent_ref 回填 substance_code |
| 物质同一性判定（业务功能）| `test_check_sameness.py` | 5 | 序列哈希命中 / xref 命中 / 不同 substance_type 不判同 |

**SRS 小计**：约 32 条用例

### C.2 PRS（§9 项目域）

| V1.2 偏离项 | 测试文件 | 用例数 | 关键用例 |
|---|---|---|---|
| §9.2 project 主表对齐（枚举 / 字段 / 编码按年）| `test_project_crud.py` | 10 | create 编码 PRJ-2026-XXXX / get / update / version 乐观锁 / soft delete / 枚举校验 |
| §9.3 project_milestone（枚举 / NOT NULL / 无软删除）| `test_project_milestone_team.py` | 8（含 team）| milestone CRUD / planned_date 必填 / 枚举校验 |
| §9.4 project_team（role 任意 + function_area + allocation_pct）| `test_project_milestone_team.py` | （同上）| team CRUD / 唯一性 / 离职后再加入 |
| §9.5 project_status_history.e_signature_id（V1.1 §5.4 加强）| `test_project_state_machine.py` | 6 | proposed→initiated→active→on_hold→completed/terminated 全链路；approve / complete / terminate 签名 |

**PRS 小计**：约 24 条用例

### C.3 REF（§11 跨域引用）

| V1.2 偏离项 | 测试文件 | 用例数 | 关键用例 |
|---|---|---|---|
| §11.2 ref.project_substance 复合 PK 重构 | `test_project_substance_link.py` | 7 | link/unlink 往返；同对 substance 不同 relation_type 并存；relink 恢复；obsoleted 物质禁止；audit parent_ref 回填 project_code |
| §11.3 ref.asset_substance（V1.2 §6.5 新建）| `test_asset_substance_link.py` | 8 | link/unlink；不同 component_role 并存（ADC 场景：antibody/linker/payload）；relink；terminated 资产禁止；obsoleted 物质禁止；audit parent_ref 回填 asset_code |
| §11.4 ref.project_asset（V1.2 §6.6 新建）| `test_project_asset_link.py` | 7 | 双向 link（project 侧 / asset 侧）；同对 (project, asset) 不同 relation_type 仍冲突（PK 仅含两键）；relink 换 relation_type；terminated 资产禁止双侧；audit parent_ref 回填 project_code |

**REF 小计**：22 条用例

### C.4 ARS（§8 资产域，V1.2 新增）

| V1.2 偏离项 | 测试文件 | 用例数 | 关键用例 |
|---|---|---|---|
| §6.1 asset 主表 + §6.2 market_id（CRUD）| `test_asset_crud.py` | 11 | create AST-XXXXXXX / get / update（version+1） / phase_change_at / soft delete / 枚举校验 |
| §6.4 状态机（hold/resume/terminate）+ §6.3 status_history + §6.4.2 电签 + §6.4.3 双权限 | `test_asset_state_machine.py` | 11 | hold/resume 往返；terminate 需 password；密码错 401 signature_invalid；缺 password 422 signature_required；asset:sign 权限缺失 403；status_history 含 e_signature_id |

**ARS 小计**：22 条用例

### C.5 跨主题实施侧加强

| V1.1/V1.2 加强项 | 测试文件 | 用例数 | 关键用例 |
|---|---|---|---|
| V1.1 §5.2 失败副作用旁路 session（登录失败 / 签名失败计数不因 raise 而 rollback）| `test_auth_security.py` | 4 | 5 次错密码 → account_locked；解锁后重置；signature_invalid 也独立计数 |
| V1.1 §5.3 audit_trigger parent_ref（子表 entity_code 回填）| `test_audit_trigger_v2.py` | 3 | substance_xref / substance_protein / project_milestone 子表 audit_log.entity_code 回填父 code |
| V1.1 §5.1 service-level 显式 commit（响应后立即可见）| 隐式覆盖 | — | 全部状态机 + link 测试均依赖此（无失败说明已生效）|
| V1.1 §5.4 status_history.e_signature_id | `test_signature.py` + `test_project_state_machine.py` + `test_asset_state_machine.py` | 多处 | 签名后 status_history.e_signature_id 非空 |
| V1.1 §5.5 `meta.error.type` 401 分流 | `test_signature.py` + `test_auth_security.py` | 多处 | signature_invalid vs token_expired 区分；FE 不一刀切跳登录 |

**跨主题加强**：直接专项 7 用例 + 多处间接覆盖

### C.6 全局搜索（API §3.2.2 + V1.2 §6.7）

| V1.2 偏离项 | 测试文件 | 用例数 | 关键用例 |
|---|---|---|---|
| 全局搜索 substance + project + asset 三类 | `test_global_search.py` | 11 | substance name / project code / substance xref / types 过滤 / 权限分流（readonly 仅可见 read 权限实体）/ 401 未登录；asset name / code / trade_name / types=asset 过滤 / 默认返回三类 |

**搜索小计**：11 用例（M3.4 +5 for asset）

### C.7 基础冒烟

| 项 | 测试文件 | 用例数 |
|---|---|---|
| 健康检查 + 受保护端点鉴权 | `test_smoke.py` | 2 |

### C.8 总计

| 域 | 用例数 |
|---|---|
| SRS（§7） | 32 |
| PRS（§9） | 24 |
| ARS（§8） | 22 |
| REF（§11） | 22 |
| 跨主题加强 | 7 |
| 全局搜索 | 11 |
| 冒烟 | 2 |
| **合计** | **117** ✅ M3.4 全量通过 |

### C.9 验证门禁

- **每次 alembic upgrade head 后**：`make test-be` 全量 117 用例必须 100% 通过
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
