# API-MDM-001（API 接口规范）V1.0 → V1.1 修订清单

| 字段 | 值 |
|---|---|
| 文档 | API-MDM-001 V1.0 → V1.1 |
| 上游决议 | DEV-MDM-001 V1.2_draft §6.4 / §6.5 / §6.6 / §6.7 / §7.1 / §8.1 / §8.2 / §8.3 |
| 修订总数 | 21 项（含本轮评审决议补充 #20 §2.6 / #21 §2.4） |
| 修订模式 | docx Word 修订模式逐项落地 |
| 评审用途 | IT 架构组逐项决议（接受 / 拒绝 / 修改），秘书在 Word 修订模式下落地 |

---

## 修订全景（按 docx 章节序）

| # | docx 章节 | 修订摘要 | 上游决议 |
|---|---|---|---|
| 1 | §1.4.2 错误响应 | 增加 `meta.error.type` 字典指向 §4.4 的交叉引用 | V1.2 §8.3 |
| 2 | §2.2 认证 Endpoint / `POST /auth/refresh` | 标注"V1.0 未实现，Phase 4 安全收尾时补" | V1.2 §8.1.1 |
| 3 | §4.2 通用错误码（错误码表） | 新增 `40106 signature_invalid` 与 `42202 signature_required` 两行 | V1.2 §8.3 |
| 4 | §4 错误码体系 | 新增 §4.4「`meta.error.type` 字典与前端处置约定」整节 | V1.2 §8.3 + V1.1 §5.5 |
| 5 | §5.1.1 认证（auth）索引表 | `/auth/refresh` 行加 "Phase 4 补" 路线图标识 | V1.2 §8.1.1 |
| 6 | §5.1.3 SRS 索引表 | `:reject` / `:merge` 加 "Phase 4 / Phase 5 补" 标识；`/protein` `/adc` `/xrefs` GET 行加"V1.1 简化为 `?expand=`，写操作端点保留"备注 | V1.2 §8.1.2 / §8.1.3 / §8.2 |
| 7 | §5.1.5 ARS 索引表 | 新增 `:hold` / `:resume` / `:terminate` 三行（含权限）；`:advance-phase` 行加 "V1.0 未实现，Phase 5 视需补" | V1.2 §6.4.5 / §8.1.4 |
| 8 | §5.1.5 ARS 索引表 | 新增 ref.asset_substance 4 端点占位（已部分存在，需补齐 PUT / DELETE） | V1.2 §6.5 |
| 9 | §5.1.4 PRS 索引表 | 新增 ref.project_asset 4 端点（GET / POST 已有，补 PUT 关系属性 / DELETE 解除） | V1.2 §6.6 |
| 10 | §5.1.7 全局功能索引 | `/search` 行备注 `types` 当前实现仅 substance / project / asset 3 类，material 推迟 | V1.2 §6.7.1 |
| 11 | §6.5 SRS 状态变更 | `:reject` 与 `:merge` 章节头加"⚠ V1.0 未实现，Phase 4 / Phase 5 补"标识 | V1.2 §8.1.2 / §8.1.3 |
| 12 | §6.7 SRS 子资源 endpoint | 章节头加段落说明：`GET /protein` `/adc` `/xrefs` 已统一改为详情端点 `?expand=protein,adc,xrefs`；写操作端点保留 | V1.2 §8.2 |
| 13 | §8.1 ARS 关键 endpoint | 新增「ARS 状态机端点」子节，定义 `:hold` / `:resume` / `:terminate` 完整签名与权限要求 | V1.2 §6.4.1 / §6.4.5 |
| 14 | §8.1 ARS 关键 endpoint | `:terminate` 端点权限要求列写 **asset:update + asset:sign 双权限**（其它两个仅 asset:update） | V1.2 §6.4.3 |
| 15 | §8.1 ARS 关键 endpoint | `:advance-phase` 章节头加"⚠ V1.0 未实现，Phase 5 视需补"标识 | V1.2 §8.1.4 |
| 16 | §8.1 ARS 关键 endpoint | 新增「ref.asset_substance 关系端点」子节（GET / POST / PUT / DELETE 4 端点完整签名） | V1.2 §6.5 |
| 17 | §8.1 / §7.5 跨域引用 | 新增「ref.project_asset 关系端点」子节（GET / POST / PUT / DELETE 4 端点完整签名） | V1.2 §6.6 |
| 18 | §8.3 全局搜索 | `types` 参数当前可选值表述限定为 `substance,project,asset`；补"命中字段与排序权重"小节（asset 命中 asset_code / internal_name / trade_name / inn_name / indication；trade_name / inn_name 排序权重 = 5） | V1.2 §6.7.1 / §6.7.2 |
| 19 | §11 附录 | 新增 §11.7「路线图：Phase 4 / Phase 5 端点」附录，集中列出 5 个推迟端点的依据、计划阶段、临时替代手段 | V1.2 §8.1 |
| 20 | §2.6 应用层会话上下文（用于审计） | 修订示例代码与说明：禁用 `SET LOCAL app.*` GUC 方案（asyncpg 池跨事务泄漏风险），改为 service 层显式 `UPDATE` 审计字段 + ContextVar 注入 | V1.2 §7.1.1（评审决议补充） |
| 21 | §2.4 权限模型与 Endpoint 权限映射 | 补 `require_all_permissions(...)` 多权限组合工厂示例（针对 GxP 关键不可逆动作的"操作权限 + 签名权限"双校验，如 asset:terminate 要求 `asset:update + asset:sign`） | V1.2 §6.4.3 / V1.2 §7.1.2（评审决议补充） |

---

## 修订清单（按 docx 章节序逐项展开）

### 修订 #1

| 字段 | 内容 |
|---|---|
| docx 章节 | §1.4.2 错误响应 |
| 修订类型 | 新增交叉引用 |
| V1.0 原文位置 | §1.4.2 错误响应 JSON 示例后段，`error.type` 字段注释 |
| V1.0 原文摘录 | `"type": "permission_denied",  // 错误类型（机器可读）` |
| V1.1 修订内容 | 字段注释后新增一句："完整 `meta.error.type` 字典与前端处置约定见 §4.4。" |
| 上游决议引用 | DEV-MDM-001 V1.2 §8.3 |
| 修订理由 | 让 `meta.error.type` 字典具备文档锚点，前端拦截器分流有据可查（V1.1 §5.5 401 双重语义分流的延续）。 |

---

### 修订 #2

| 字段 | 内容 |
|---|---|
| docx 章节 | §2.2 认证 Endpoint — `POST /api/v1/auth/refresh` |
| 修订类型 | 新增路线图标识 |
| V1.0 原文位置 | §2.2 内 `POST /api/v1/auth/refresh` 端点小节 |
| V1.0 原文摘录 | "刷新 Access Token（使用 Cookie 中的 Refresh Token）。" |
| V1.1 修订内容 | 该端点小节开头加灰色批注框："⚠ Phase 4 补：V1.0 阶段未实现 refresh token 流转，当前 access_token 30 min 过期后由前端引导重新登录；Phase 4 安全收尾时补该端点完整实现。" |
| 上游决议引用 | DEV-MDM-001 V1.2 §8.1.1 |
| 修订理由 | 避免下游集成方误认为 refresh 端点已可用；明确推迟阶段。 |

---

### 修订 #3

| 字段 | 内容 |
|---|---|
| docx 章节 | §4.2 通用错误码（错误码表） |
| 修订类型 | 表格新增 2 行 |
| V1.0 原文位置 | §4.2 通用错误码表，401 段与 422 段 |
| V1.0 原文摘录 | 现有 `40105 old_password_wrong` 之后无 40106；`42202 reference_in_use` 已分配 |
| V1.1 修订内容 | (a) 在 `40105 old_password_wrong` 行后新增：`40106 \| 401 \| signature_invalid \| 电子签名密码错误 / 内容哈希不一致`；(b) 在 `42202 reference_in_use` 行后新增：`42203 \| 422 \| signature_required \| 当前操作要求电子签名但未提供 / 签名失败`。**不动 V1.0 已分配的 42202 reference_in_use**。 |
| 上游决议引用 | DEV-MDM-001 V1.2 §8.3 |
| 修订理由 | 实施侧已落地两类 `meta.error.type`，但 V1.0 错误码表未收录；签名流（SRS approve/activate/deprecate/obsolete / PRS approve/complete/terminate / ARS terminate）必须有可识别错误码。 |
| 评审已决议 | 保留 V1.0 `42202=reference_in_use`；新增 `42203=signature_required`。代码侧 `backend/app/core/exceptions.py` 的 `SignatureRequiredError.code` 同步从 42202 改 42203（见后续代码改动清单）。 |

---

### 修订 #4

| 字段 | 内容 |
|---|---|
| docx 章节 | §4 错误码体系 |
| 修订类型 | 新增整节 §4.4 |
| V1.0 原文位置 | §4.3「域专属错误码（各域分配 100 段）」之后、§5「Endpoint 总索引」之前 |
| V1.0 原文摘录 | V1.0 §4.3 末尾的"⚠ 错误码使用准则"四条 |
| V1.1 修订内容 | 新增 §4.4「`meta.error.type` 字典与前端处置约定」整节，内容：(1) 11 条 `meta.error.type` 全表（`invalid_credentials` / `token_expired` / `token_invalid` / `token_missing` / `old_password_wrong` / `signature_invalid` / `permission_denied` / `account_disabled` / `state_invalid` / `signature_required` / `account_locked`），列出 `meta.error.type` / 错误码 / HTTP / 前端默认处置（如 token_expired → 静默 refresh / 业务身份再验证 → 弹密码二次确认对话框 / 会话失效 → 跳转登录）；(2) 强调"前端按 `meta.error.type` 分流，不按 HTTP 状态码一刀切跳登录" |
| 上游决议引用 | DEV-MDM-001 V1.2 §8.3 + V1.1 §5.5 |
| 修订理由 | V1.1 §5.5 已记载 401 双重语义分流策略但放在偏离说明里；正式 API 文档需要把 `meta.error.type` 当成对外契约固化。 |

---

### 修订 #5

| 字段 | 内容 |
|---|---|
| docx 章节 | §5.1.1 认证（auth）索引表 |
| 修订类型 | 表格行加路线图标识 |
| V1.0 原文位置 | §5.1.1 认证索引表中 `POST /api/v1/auth/refresh` 行 |
| V1.0 原文摘录 | `POST \| /api/v1/auth/refresh \| 刷新 Access Token \| 已登录` |
| V1.1 修订内容 | "说明"列追加（或新增"路线图"列）："⏳ Phase 4 补 — V1.0 未实现" |
| 上游决议引用 | DEV-MDM-001 V1.2 §8.1.1 |
| 修订理由 | 与修订 #2 配套，让索引页直观可见哪些端点未实现。 |

---

### 修订 #6

| 字段 | 内容 |
|---|---|
| docx 章节 | §5.1.3 SRS 索引表 |
| 修订类型 | 表格多行加备注 / 路线图标识 |
| V1.0 原文位置 | §5.1.3 索引表中 4 行：`:reject` / `:merge` / `/protein` GET / `/adc` GET / `/xrefs` GET |
| V1.0 原文摘录 | （V1.0 现有 5 行 substance 子资源 + 状态变更端点定义） |
| V1.1 修订内容 | (a) `POST /substances/{code}:reject` 说明列加："⏳ Phase 4 视业务必要性补 — V1.0 未实现，当前用 DELETE 软删除替代"；(b) `POST /substances/{code}:merge` 说明列加："⏳ Phase 5 数据治理工具阶段补 — V1.0 未实现"；(c) `GET /substances/{code}/protein` / `GET .../adc` / `GET .../xrefs` 三行说明列加："V1.1 简化：详情端点 `?expand=protein,adc,xrefs` 已可返回；本端点保留但建议优先使用 expand"；POST / PUT / DELETE 写操作端点不动 |
| 上游决议引用 | DEV-MDM-001 V1.2 §8.1.2 / §8.1.3 / §8.2 |
| 修订理由 | 让 FE / 集成方一目了然哪些是推迟端点 / 哪些是简化策略。 |

---

### 修订 #7

| 字段 | 内容 |
|---|---|
| docx 章节 | §5.1.5 ARS 索引表 |
| 修订类型 | 表格新增 3 行 + 1 行加标识 |
| V1.0 原文位置 | §5.1.5 ARS 索引表，目前最后一行是 `POST /api/v1/assets/{code}/substances` |
| V1.0 原文摘录 | V1.0 索引 ARS 共 11 行端点；现存 `POST /assets/{code}:advance-phase` 已列 |
| V1.1 修订内容 | (a) 在 `:advance-phase` 行说明列加："⏳ Phase 5 视需补 — V1.0 未实现；当前用 PUT 直接更新 `current_phase`"；(b) 在 `:advance-phase` 行之后新增 3 行：<br>`POST \| /api/v1/assets/{code}:hold \| 暂停资产 \| asset:update`<br>`POST \| /api/v1/assets/{code}:resume \| 恢复资产 \| asset:update`<br>`POST \| /api/v1/assets/{code}:terminate \| 终止资产（不可逆，需电子签名）\| asset:update + asset:sign` |
| 上游决议引用 | DEV-MDM-001 V1.2 §6.4.1 / §6.4.3 / §6.4.5 / §8.1.4 |
| 修订理由 | M3.2 已实施 ARS 状态机，与 SRS / PRS 端点路径风格一致；V1.0 索引表遗漏；terminate 双权限是 GxP 关键加强需要正式入档。 |

---

### 修订 #8

| 字段 | 内容 |
|---|---|
| docx 章节 | §5.1.5 ARS 索引表 — ref.asset_substance 4 端点 |
| 修订类型 | 表格补齐 |
| V1.0 原文位置 | §5.1.5 ARS 索引表，`/assets/{code}/substances` 现仅 GET / POST 2 行 |
| V1.0 原文摘录 | `GET \| /api/v1/assets/{code}/substances \| 关联物质 \| asset:read`<br>`POST \| /api/v1/assets/{code}/substances \| 关联物质 \| asset:update` |
| V1.1 修订内容 | 在 POST 行后新增 2 行，凑齐 4 端点：<br>`PUT \| /api/v1/assets/{code}/substances/{substance_code} \| 更新关系（component_role / is_active_ingredient）\| asset:update`<br>`DELETE \| /api/v1/assets/{code}/substances/{substance_code} \| 解除关联（软删除）\| asset:update` |
| 上游决议引用 | DEV-MDM-001 V1.2 §6.5 |
| 修订理由 | M3.3 已实施 4 端点（migration 0025 + service 完整 CRUD）；V1.0 索引仅列读写新增，未列改与删，需补齐。 |

---

### 修订 #9

| 字段 | 内容 |
|---|---|
| docx 章节 | §5.1.4 PRS 索引表 — ref.project_asset 4 端点 |
| 修订类型 | 表格补齐 |
| V1.0 原文位置 | §5.1.4 PRS 索引表，`/projects/{code}/assets` 现仅 GET / POST 2 行 |
| V1.0 原文摘录 | `GET \| /api/v1/projects/{code}/assets \| 关联资产 \| project:read`<br>`POST \| /api/v1/projects/{code}/assets \| 关联资产 \| project:update` |
| V1.1 修订内容 | 在 POST 行后新增 2 行：<br>`PUT \| /api/v1/projects/{code}/assets/{asset_code} \| 更新关系（relation_type）\| project:update`<br>`DELETE \| /api/v1/projects/{code}/assets/{asset_code} \| 解除关联（软删除）\| project:update` |
| 上游决议引用 | DEV-MDM-001 V1.2 §6.6 |
| 修订理由 | M3.3 已实施 4 端点（migration 0026）；`relation_type` 是关系属性可改不入 PK，PUT 端点必要。 |

---

### 修订 #10

| 字段 | 内容 |
|---|---|
| docx 章节 | §5.1.7 全局功能索引 |
| 修订类型 | 表格行加备注 |
| V1.0 原文位置 | §5.1.7 全局功能索引中 `GET /api/v1/search` 行 |
| V1.0 原文摘录 | `GET \| /api/v1/search \| 全局搜索 \| 已登录` |
| V1.1 修订内容 | 说明列改为："全局搜索（V1.1 实现 entity_type ∈ {substance, project, asset} 3 类；material 推迟至 **Phase 4 MM 域开发**）" |
| 上游决议引用 | DEV-MDM-001 V1.2 §6.7.1 |
| 修订理由 | V1.0 §8.3 与 §3.2.2 同时罗列 4 类（含 material），但实施侧 M3.4 仅落地 3 类；需对外明示当前可用类型。 |

---

### 修订 #11

| 字段 | 内容 |
|---|---|
| docx 章节 | §6.5 SRS 状态变更 |
| 修订类型 | 章节小节加标识 |
| V1.0 原文位置 | §6.5 内 `:reject` / `:merge` 子节（V1.0 §6.5 包含 approve / reject / deprecate / merge 等动作） |
| V1.0 原文摘录 | （`:reject` 与 `:merge` 端点的请求体与响应示例） |
| V1.1 修订内容 | (a) `:reject` 子节标题后加批注框："⚠ V1.0 未实现，Phase 4 视业务必要性补；当前用 DELETE /substances/{code} 软删除替代驳回语义。"<br>(b) `:merge` 子节标题后加批注框："⚠ V1.0 未实现，Phase 5 数据治理工具阶段补；需配合 merged_to_substance_code 字段（DM-MDM-001 §7.x）的运维流程。" |
| 上游决议引用 | DEV-MDM-001 V1.2 §8.1.2 / §8.1.3 |
| 修订理由 | 详细规范章节也需要与索引页一致地标记推迟状态，避免实现差距遗漏。 |

---

### 修订 #12

| 字段 | 内容 |
|---|---|
| docx 章节 | §6.7 SRS 子资源 endpoint |
| 修订类型 | 新增章节前导段 |
| V1.0 原文位置 | §6.7 开头（"GET /api/v1/substances/{code}/xrefs 获取标识符列表。" 之前） |
| V1.0 原文摘录 | V1.0 §6.7 直接列出 `GET /xrefs` `POST /xrefs` `GET /projects` 端点定义 |
| V1.1 修订内容 | 章节开头新增一段说明："**V1.1 实施侧简化**：详情查询端点 `GET /api/v1/substances/{code}?expand=protein,adc,xrefs,projects,assets,materials` 已可一次返回全部子资源数据，建议前端优先使用 expand 参数；本节定义的独立 GET 子资源端点保留作为兼容路径。写操作（POST / PUT / DELETE）独立子资源端点保持必要，不得用 expand 替代。" |
| 上游决议引用 | DEV-MDM-001 V1.2 §8.2 |
| 修订理由 | M3.x 实施已统一改用 `?expand=` 减少请求数；V1.1 把这个简化策略对外明文。 |

---

### 修订 #13

| 字段 | 内容 |
|---|---|
| docx 章节 | §8.1 ARS 关键 endpoint |
| 修订类型 | 新增子节「ARS 状态机端点」 |
| V1.0 原文位置 | §8.1 内，紧跟 `POST /api/v1/assets/{code}:advance-phase` 子节之后，`POST /api/v1/assets/{code}/market-ids` 之前 |
| V1.0 原文摘录 | V1.0 §8.1 现有 `POST /assets`、`:advance-phase`、`/market-ids` 三个端点定义，未涉及 `:hold` `:resume` `:terminate` |
| V1.1 修订内容 | 新增子节「8.1.x ARS 状态机端点」，分别定义 3 个端点的：(1) HTTP 方法 + 路径；(2) 请求体（含 reason；terminate 还含 signature 对象）；(3) 状态机前置条件（hold: active → on_hold；resume: on_hold → active；terminate: active+on_hold → terminated）；(4) 权限要求；(5) 失败场景与错误码（如 422/42201 state_invalid；422/42202 signature_required）。给出最小完整 JSON 示例 |
| 上游决议引用 | DEV-MDM-001 V1.2 §6.4.1 / §6.4.5 |
| 修订理由 | 实施已完整 M3.2 但 V1.0 详细规范章节遗漏；与 SRS / PRS 状态机端点章节风格保持一致。 |

---

### 修订 #14

| 字段 | 内容 |
|---|---|
| docx 章节 | §8.1 ARS 关键 endpoint — `:terminate` 子节 |
| 修订类型 | 权限要求列加双权限 |
| V1.0 原文位置 | 与修订 #13 同节，`:terminate` 子小节内的"权限"行 |
| V1.0 原文摘录 | （V1.0 不存在此节，由修订 #13 一并创建） |
| V1.1 修订内容 | `:terminate` 端点权限要求明文："**asset:update + asset:sign**（同时持有；按 ARCH-MDM-001 V1.0 §11.x 权限组合工厂 `require_all_permissions` 校验）"；并补充"角色映射：PROJECT_MANAGER + QA_REVIEWER 默认持有 asset:sign，与 substance:sign / project:sign 一致" |
| 上游决议引用 | DEV-MDM-001 V1.2 §6.4.3 / §6.4.4 |
| 修订理由 | terminate 是 21 CFR Part 11 §11.50 关键不可逆动作，双权限是 GxP 加强；权限要求列必须明示，单权限是文档遗漏。 |

---

### 修订 #15

| 字段 | 内容 |
|---|---|
| docx 章节 | §8.1 ARS 关键 endpoint — `:advance-phase` 子节 |
| 修订类型 | 章节小节加标识 |
| V1.0 原文位置 | §8.1 现有 `POST /api/v1/assets/{code}:advance-phase` 子小节 |
| V1.0 原文摘录 | "请求体 { \"to_phase\": \"phase_2\", \"phase_change_date\": \"2026-08-01\", \"reason\": \"Phase I 试验完成，正式进入 Phase II\", \"signature\": { ... } }" |
| V1.1 修订内容 | 子节标题后加批注框："⚠ V1.0 未实现，Phase 5 视需补 — 当前实施用 `PUT /api/v1/assets/{code}` 直接更新 `current_phase` 字段；若后续需要状态机流转校验和电子签名再上独立端点。" |
| 上游决议引用 | DEV-MDM-001 V1.2 §8.1.4 |
| 修订理由 | 与修订 #7 索引行配套；正文章节也需明示推迟以免误用。 |

---

### 修订 #16

| 字段 | 内容 |
|---|---|
| docx 章节 | §8.1 ARS 关键 endpoint |
| 修订类型 | 新增子节「ref.asset_substance 关系端点」 |
| V1.0 原文位置 | §8.1 末尾（`/market-ids` 之后）追加 |
| V1.0 原文摘录 | V1.0 §8.1 只在 ARS 索引列出 `GET /substances` / `POST /substances` 关联端点，未给出请求体、响应、PUT / DELETE |
| V1.1 修订内容 | 新增子节「8.1.x ref.asset_substance 关系端点」，列出 4 个端点：<br>(1) `GET /api/v1/assets/{code}/substances` — 列表，响应含 `substance_code` / `component_role` / `is_active_ingredient` / `linked_at`；<br>(2) `POST /api/v1/assets/{code}/substances` — 请求体 `{substance_code, component_role, is_active_ingredient}`，`component_role` ∈ `main_component / antibody / linker / payload / excipient / impurity`；<br>(3) `PUT /api/v1/assets/{code}/substances/{substance_code}` — 修改 component_role / is_active_ingredient；<br>(4) `DELETE /api/v1/assets/{code}/substances/{substance_code}` — 软删除关系。所有端点权限按修订 #8。备注：terminated 资产禁止新建关联（service 层校验，412/422 错误） |
| 上游决议引用 | DEV-MDM-001 V1.2 §6.5 |
| 修订理由 | M3.3 已实施完整 4 端点，V1.0 详细规范章节遗漏；ADC / mAb 多组分场景靠这些端点维护跨域关系。 |

---

### 修订 #17

| 字段 | 内容 |
|---|---|
| docx 章节 | §7.5 PRS 子资源 / §8.1 ARS 关键 endpoint |
| 修订类型 | 新增子节「ref.project_asset 关系端点」 |
| V1.0 原文位置 | §7.5 PRS 子资源章节末尾（V1.0 §7.5 现有 milestones / team / substances 子资源定义，未含 assets 完整定义） |
| V1.0 原文摘录 | V1.0 §7.5 只给出 `POST /api/v1/projects/{code}/substances`，未涉及 `/assets` 子资源完整端点 |
| V1.1 修订内容 | 在 §7.5 末尾新增子节「7.5.x ref.project_asset 关系端点」，列出 4 端点：<br>(1) `GET /api/v1/projects/{code}/assets` — 列表，响应含 `asset_code` / `internal_name` / `current_phase` / `relation_type` / `linked_at`；<br>(2) `POST /api/v1/projects/{code}/assets` — 请求体 `{asset_code, relation_type}`，`relation_type` 默认 `primary`，建议值 `primary/supporting/derivative/reference`（后端无 CHECK，前端提示）；<br>(3) `PUT /api/v1/projects/{code}/assets/{asset_code}` — 修改 relation_type（属性可变，不入 PK，与 §11.4 数据模型一致）；<br>(4) `DELETE /api/v1/projects/{code}/assets/{asset_code}` — 软删除关系。权限按修订 #9 |
| 上游决议引用 | DEV-MDM-001 V1.2 §6.6 |
| 修订理由 | M3.3 已实施 4 端点；relation_type 不入 PK 的关键差异（与 §11.2 三键 PK 不同）需要在 API 文档同步明示，否则前端易混淆。 |

---

### 修订 #18

| 字段 | 内容 |
|---|---|
| docx 章节 | §8.3 全局搜索 |
| 修订类型 | 端点说明修改 + 新增小节 |
| V1.0 原文位置 | §8.3 全局搜索查询参数表 `types` 行；响应示例 `results` 对象 |
| V1.0 原文摘录 | "types \| string \| 限定类型，逗号分隔（substance,project,asset,material）"；响应示例中含 `"material": { "total": 4, "items": [ ... ] }` |
| V1.1 修订内容 | (a) `types` 描述改为："限定类型，逗号分隔（**V1.1 支持：substance, project, asset**；material 推迟至 **Phase 4 MM 域开发**）"；(b) 响应示例移除 `material` 块，保留 substance / project / asset 三块；(c) 新增小节「8.3.x 命中字段与排序权重」：列出 substance / project / asset 三类各自命中字段（asset = asset_code / internal_name / trade_name / inn_name / indication）和排序权重（trade_name / inn_name 归入 weight=5，与 name_en / internal_code 并列），权限过滤说明按 `<entity>:read`（SYS_ADMIN bypass） |
| 上游决议引用 | DEV-MDM-001 V1.2 §6.7.1 / §6.7.2 / §6.7.3 |
| 修订理由 | (1) 当前实现仅 3 类，需与 V1.0 文档对齐；(2) 排序权重 / 命中字段是前端搜索结果排序的契约，需明示。 |

---

### 修订 #19

| 字段 | 内容 |
|---|---|
| docx 章节 | §11 附录 — 新增 §11.7 |
| 修订类型 | 新增附录章节 |
| V1.0 原文位置 | §11.6「参考」之后追加（成为新的 §11.7） |
| V1.0 原文摘录 | （V1.0 附录无路线图章节，仅含状态机参考 / cURL / 后端示例 / 后续文档清单 / 参考） |
| V1.1 修订内容 | 新增 §11.7「路线图：Phase 4 / Phase 5 端点」，以表格列出 5 个推迟端点：<br><br>`# \| 端点 \| 用途 \| 推迟理由 \| 临时替代 \| 计划阶段`<br>`R1 \| POST /auth/refresh \| JWT 刷新 \| 当前 access_token 30min 自然过期已覆盖 dev/UAT \| 重新登录 \| Phase 4 安全收尾`<br>`R2 \| POST /substances/{code}:reject \| 物质驳回 \| 业务必要性待评估；驳回与软删除语义重叠 \| DELETE /substances/{code} 软删除 \| Phase 4 视需`<br>`R3 \| POST /substances/{code}:merge \| 物质合并 \| 需配合 merged_to_substance_code 字段与数据治理流程 \| 手工 DBA 数据迁移 + 双向引用更新 \| Phase 5 数据治理工具`<br>`R4 \| POST /assets/{code}:advance-phase \| 阶段流转 \| 状态机校验和签名需求未明 \| PUT /assets/{code} 直接更新 current_phase \| Phase 5 视需`<br>`R5 \| POST /{domain}:batch-create / :batch-update / :batch-delete \| 批量操作 \| 单条 CRUD 配合幂等键已覆盖 90% 场景 \| 循环单条调用 + Idempotency-Key \| Phase 5 数据治理工具` |
| 上游决议引用 | DEV-MDM-001 V1.2 §8.1 |
| 修订理由 | 将"哪些端点 V1.0 未实现 / 哪些将进 Phase 4 / 哪些进 Phase 5"作为对外契约的一部分，避免下游集成方反复发问；与索引页 / 详情页的"推迟"标识相互索引。 |

---

### 修订 #20

| 字段 | 内容 |
|---|---|
| docx 章节 | §2.6 应用层会话上下文（用于审计） |
| 修订类型 | 修订示例代码 + 加技术备注 |
| V1.0 原文位置 | §2.6 整节（`audit_context_middleware` 伪代码 + 5 行 `SET LOCAL app.*`） |
| V1.0 原文摘录 | `await conn.execute(text(f"SET LOCAL app.user_id = '{user.id}'"))` 等 5 行 `SET LOCAL` GUC 注入；末尾"此后所有 SQL 操作都会被审计触发器自动记录调用方信息" |
| V1.1 修订内容 | 整节重写：(1) 删除 5 行 `SET LOCAL app.*` 示例；(2) 改为说明："**V1.1 已禁用 `SET LOCAL` GUC 方案**——在 asyncpg 连接池模式下，`SET LOCAL` 设置的会话变量在事务提交/回滚后未必清理干净，可能跨事务泄漏到下一个复用的连接（M2.5.1 发现：第 2 条 status_history 行写入第 1 条事务的 e_signature_id）。"；(3) 新增 V1.1 推荐做法：service 层在写入业务记录时**显式 `UPDATE` 审计字段**（`created_by` / `updated_by` / `e_signature_id`），不依赖触发器从 GUC 取值；ContextVar + AuditContextMiddleware 仍负责把 user / IP / request_id 注入 Python 调用栈供日志使用，但**不进 PG 连接级变量**。 |
| 上游决议引用 | DEV-MDM-001 V1.2 §7.1.1（评审决议补充） |
| 修订理由 | V1.0 §2.6 示范的 `SET LOCAL` 方案在 asyncpg 池下存在跨事务泄漏的合规风险；继续按 V1.0 实施会导致 audit_log 错位（违反 21 CFR Part 11 §11.10(e)）。本次评审决议同步把工程修复入档。 |

---

### 修订 #21

| 字段 | 内容 |
|---|---|
| docx 章节 | §2.4 权限模型与 Endpoint 权限映射 |
| 修订类型 | 新增示例代码段 |
| V1.0 原文位置 | §2.4 末尾（`require_permission("substance:approve")` 示例之后） |
| V1.0 原文摘录 | V1.0 仅给出 `require_permission(...)` 单权限示例（3 行 endpoint 示例） |
| V1.1 修订内容 | 在 §2.4 末尾追加示例与说明："**V1.1 新增：`require_all_permissions(...)` 多权限组合工厂**——针对 21 CFR Part 11 §11.50 关键不可逆动作（如 ARS terminate），endpoint 需要同时校验"操作权限 + 签名权限"：<br>`@router.post("/assets/{code}:terminate", dependencies=[Depends(require_all_permissions("asset:update", "asset:sign"))])`<br>`async def terminate_asset(...): ...`<br>角色映射示例：PROJECT_MANAGER + QA_REVIEWER 默认持有 `asset:sign` / `substance:sign` / `project:sign`；普通操作角色仅持 `*:update`。**单权限不足以触发签名流**。" |
| 上游决议引用 | DEV-MDM-001 V1.2 §6.4.3 / §7.1.2（评审决议补充） |
| 修订理由 | M3.2 实施已落地 `require_all_permissions`，但 V1.0 §2.4 仅有单权限示例，下游集成方 / FE 不知道有这个工厂，无法对照需求设计角色矩阵。GxP 关键动作的双权限约束需要在 API 文档明示。 |

---

## 评审决议汇总（待评审组逐项填写）

| 修订 # | docx 章节 | 决议 | 备注 |
|---|---|---|---|
| 1 | §1.4.2 | 接受 / 拒绝 / 修改 | |
| 2 | §2.2 `/auth/refresh` | 接受 / 拒绝 / 修改 | |
| 3 | §4.2 错误码表 | ✅ 已决议接受 | 保留 42202=reference_in_use；新增 42203=signature_required；代码侧同步改 SignatureRequiredError.code |
| 4 | §4.4 `meta.error.type` 字典（新增） | 接受 / 拒绝 / 修改 | |
| 5 | §5.1.1 auth 索引 | 接受 / 拒绝 / 修改 | |
| 6 | §5.1.3 SRS 索引 | 接受 / 拒绝 / 修改 | |
| 7 | §5.1.5 ARS 索引 (3 状态机端点) | 接受 / 拒绝 / 修改 | |
| 8 | §5.1.5 ref.asset_substance 4 端点 | 接受 / 拒绝 / 修改 | |
| 9 | §5.1.4 ref.project_asset 4 端点 | 接受 / 拒绝 / 修改 | |
| 10 | §5.1.7 search material 推迟 | 接受 / 拒绝 / 修改 | |
| 11 | §6.5 `:reject` `:merge` | 接受 / 拒绝 / 修改 | |
| 12 | §6.7 expand 简化 | 接受 / 拒绝 / 修改 | |
| 13 | §8.1 ARS 状态机端点（新增） | 接受 / 拒绝 / 修改 | |
| 14 | §8.1 `:terminate` 双权限 | 接受 / 拒绝 / 修改 | **GxP 关键，建议保留** |
| 15 | §8.1 `:advance-phase` 推迟 | 接受 / 拒绝 / 修改 | |
| 16 | §8.1 ref.asset_substance 端点（新增） | 接受 / 拒绝 / 修改 | |
| 17 | §7.5 ref.project_asset 端点（新增） | 接受 / 拒绝 / 修改 | |
| 18 | §8.3 全局搜索 | 接受 / 拒绝 / 修改 | |
| 19 | §11.7 路线图附录（新增） | 接受 / 拒绝 / 修改 | |
| 20 | §2.6 GUC 调整（重写示例代码）| 接受 / 拒绝 / 修改 | **本轮评审补加；合规关键工程修复** |
| 21 | §2.4 require_all_permissions 示例（新增）| 接受 / 拒绝 / 修改 | **本轮评审补加；GxP 双权限明示** |

---

## 配套修订（决议通过后秘书落地）

1. 封面「修订记录」表追加一行：`V1.1 \| 2026-05-XX \| CMC IT 架构组 \| 增补 ARS 状态机端点 / ref 关系端点 / `meta.error.type` 字典 / 双权限工厂示例 / §2.6 GUC 工程修复；标注 Phase 4/5 路线图端点`
2. 文档头「版本」字段：`V1.0` → `V1.1`
3. 全文检索校对：所有 `V1.0` 引用确认是否需要改 `V1.1`（修订记录除外）
4. 目录 (TOC) 重新生成：新增 §4.4 / §8.1.x ARS 状态机端点 / §8.1.x ref.asset_substance / §7.5.x ref.project_asset / §8.3.x 命中字段与排序权重 / §11.7 路线图（§2.4 §2.6 是修订内容不新增章节，不入 TOC）
5. **代码侧同步**（决议接受后由开发执行，非秘书工作）：
   - `backend/app/core/exceptions.py`：`SignatureRequiredError.code` 42202 → 42203
   - 测试侧扫描硬编码 `42202` 改为 `42203`（如有）

---

## 参考

- 上游：`/Users/qingcheng/code/cmab-mdm-platform/docs/CMAB_MDM_Portal_设计基准偏离说明_V1.2_draft.md` §6.4 / §6.5 / §6.6 / §6.7 / §8.1 / §8.2 / §8.3
- 背景：`/Users/qingcheng/code/cmab-mdm-platform/docs/CMAB_MDM_Portal_设计基准偏离说明_V1.1_draft.md` §5.5（`meta.error.type` 401 双重语义分流）
- V1.0 原文：`/tmp/mdm_docs_extract/API_____V1_0.txt`（OpenAPI 3.0 / REST / JSON / JWT，API-MDM-001 V1.0，2026-05-11 发布）
