# ARCH-MDM-001（架构设计文档）V1.0 → V1.1 修订清单

| 字段 | 内容 |
|---|---|
| 文档 | ARCH-MDM-001 V1.0 → V1.1 |
| V1.0 发布日期 | 2026-05-11 |
| 上游决议 | DEV-MDM-001 V1.2_draft §5 / §7.1 / §7.2 + DEV-MDM-001 V1.1_draft §5 |
| 修订总数 | 11 项（10 项条目修订 + 1 项附录新增） |
| 用途 | IT 架构组评审「接受 / 拒绝 / 修改」对照表，秘书在 Word 修订模式下逐项落地 |
| 编制日期 | 2026-05-12 |

## 章节映射说明

V1.2 偏离说明中提到的「§11.300 / §15.2 / §6.5」是 DM-MDM-001 数据模型文档的章节号。本架构文档 V1.0 实际仅 10 章，本清单已按 ARCH 实际章节定位：

| DEV 文档引用 | ARCH V1.0 实际章节 |
|---|---|
| §6.5（审计触发器实现）| ARCH §6.5（审计与合规数据模型） |
| §15.2（ORM 实现章）| ARCH §4.3 Backend API 组件图 — Repository Layer / Domain Layer 说明 |
| §11.300（强一致性）| ARCH §7.1（Part 11 合规映射）+ §7.2.1（认证流程）|
| §11.x（权限组合）| ARCH §7.2.2（RBAC 权限模型）|

---

## 修订清单（按 ARCH V1.0 docx 章节序）

### 修订 #1：§4.3 Backend API 组件图 — Domain Layer 加 service-level commit 施工说明

| 字段 | 内容 |
|---|---|
| docx 章节 | §4.3 C4 Level 3：后端组件图（Domain Layer 段落下） |
| 修订类型 | 新增施工说明段落 |
| V1.0 原文位置 | §4.3 Domain Layer 框图后、Shared Layer 框图前 |
| V1.0 原文摘录 | 「Domain Layer (域层 - 业务逻辑) ┌───────┐ ┌───────┐ ┌───────┐ ┌────┐ │ SRS │ │ PRS │ │ ARS │ │ MM │ │Service│ │Service│ │Service│ │Svc │」 |
| V1.1 修订内容 | 在 Domain Layer 描述下新增一段：「**Service 层事务提交规则**：<br>① **适用范围（强制显式 commit）**：状态机变更（status / current_phase 变化）、电子签名生效写入（status_history.e_signature_id 回填）、跨域引用写入（ref.* 三表 link / unlink）等**强一致性写操作**，service 必须在所有数据库变更完成后**显式** `await self.db.commit()`，**不依赖** FastAPI yield 依赖（`get_db`）的 cleanup commit。<br>② **不适用范围（沿用统一 transaction pattern）**：普通 CRUD（读、单表 INSERT / UPDATE / soft-delete）、列表查询、详情查询等无强一致性约束的端点，按 FastAPI yield 依赖默认 commit 即可，不必引入 service 显式 commit。<br>③ **原因**：FastAPI 异步 yield 依赖的 cleanup 在 HTTP response 已发送给客户端之后执行，客户端紧接的下一请求可能在 pre-commit 状态下读到旧快照（pytest 全集实测 ~10% 失败率）。Service 显式 commit 后，yield cleanup 的 commit 退化为空操作。<br>④ **判断准则**：端点是否触发后续读操作必须看到本次写入结果？若是 → 强一致性，显式 commit；若否 → 沿用统一 pattern。」 |
| 上游决议引用 | DEV-MDM-001 V1.1 §5.1 + V1.2 §5 |
| 修订理由 | 实施侧高频踩坑，影响强一致性读写；落入架构文档以建立规范，避免后续模块（MM / Admin）重蹈覆辙 |

---

### 修订 #2：§6.5 审计与合规数据模型 — 失败副作用旁路 session 模式

| 字段 | 内容 |
|---|---|
| docx 章节 | §6.5 审计与合规数据模型（在「⚠ 数据完整性关键设计」框前） |
| 修订类型 | 新增设计原则段落 |
| V1.0 原文位置 | §6.5 三张表 DDL 之后、「⚠ 数据完整性关键设计」之前 |
| V1.0 原文摘录 | 「audit.e_signature（电子签名）... └─ ip_address ... ⚠ 数据完整性关键设计 • 所有时间戳使用 UTC 存储...」 |
| V1.1 修订内容 | 在「⚠ 数据完整性关键设计」之前新增小节：「**失败副作用的旁路 session 持久化**：<br>① **严格适用范围**：仅用于"失败但必须留痕的副作用"——典型场景：`failed_login_count++` / `failed_signature_count++` / 登录失败审计日志 / 签名失败审计日志 / 账号锁定记录。<br>② **不得用于**：普通业务写操作（CRUD / link / unlink / 状态机变更等）。普通写操作必须在主事务内完成，依赖统一 transaction 边界保证 ACID；旁路 session 绕过主事务原子性，误用会造成数据一致性破坏。<br>③ **实现**：独立 `AsyncSessionLocal()` 创建 session，写入后单独 `await session.commit()`，再 raise 业务异常。主事务被 `get_db` 的 `except: rollback()` 整体回滚时，旁路 session 已提交的失败痕迹不受影响。<br>④ **原因**：21 CFR Part 11 §11.300 要求防暴力破解与失败审计必须可追溯；若挂在主事务上，raise → rollback 将一并丢失计数与日志，破解保护失效。<br>⑤ **评审准则**：每个使用旁路 session 的位置都应有 code review 备注说明"为何必须脱离主事务"，避免后续维护者将其扩展到普通写场景。」 |
| 上游决议引用 | DEV-MDM-001 V1.1 §5.2 + V1.2 §5 |
| 修订理由 | 补齐合规审计在异常路径下的可追溯性；与"审计 schema 仅可写不可改"原则配套 |

---

### 修订 #3：§6.5 审计与合规数据模型 — audit_trigger parent_ref 设计

| 字段 | 内容 |
|---|---|
| docx 章节 | §6.5 审计与合规数据模型（audit_log 表说明段落下） |
| 修订类型 | 修订表字段说明 + 新增触发器签名说明 |
| V1.0 原文位置 | §6.5 audit.audit_log 表 DDL 与「⚠ 数据完整性关键设计」框之间 |
| V1.0 原文摘录 | 「audit.audit_log（操作审计）... ├─ entity_id ├─ change_summary (变更摘要) ...」 |
| V1.1 修订内容 | 在 audit_log 字段列表之后新增段落：「**子表 entity_code 回填机制**：通用审计触发器 `audit.fn_audit_trigger(...)` 采用 3 参数签名 `(pk_col, code_col, parent_ref)`，其中 `parent_ref` 格式为 `'schema.table:pk_col:code_col:fk_on_this_table'`。子表（如 `substance_xref` / `project_milestone` / `asset_market_id` / `ref.asset_substance`）自身无业务编码，触发器通过 parent_ref 自动将 audit_log.entity_code 回填为父表 code（SUB-XXX / PRJ-XXX / AST-XXX），保证『按业务编码查全量审计历史』能跨主子表覆盖。」 |
| 上游决议引用 | DEV-MDM-001 V1.1 §5.3 + V1.2 §6.2.4 / §6.5.5 / §6.6.3 |
| 修订理由 | 实施侧已落地 4 张子表（xref / milestone / market_id / ref.asset_substance）；架构文档需正式接收此设计，避免后续每张子表都重复申辩 |

---

### 修订 #4：§7.1 Part 11 / Annex 11 合规映射表 — 新增「会话与签名错误分流」行

| 字段 | 内容 |
|---|---|
| docx 章节 | §7.1 21 CFR Part 11 / Annex 11 合规映射 |
| 修订类型 | 在合规映射表中新增 1 行 |
| V1.0 原文位置 | §7.1 合规映射表末行「系统验证 \| 后续完整 CSV 流程，文档化测试」之上 |
| V1.0 原文摘录 | 「会话超时 \| JWT 短有效期 + Refresh Token，空闲超时强制重登 \| 数据备份 \| PostgreSQL 每日全量 + WAL 增量」 |
| V1.1 修订内容 | 在「会话超时」行之后新增 1 行：「**身份再验证错误分流** \| 401 响应携带 `errorType` 字段区分会话失效（`token_expired` / `token_invalid` / `token_missing`）与业务身份再验证失败（`signature_invalid` / `old_password_wrong`）；前端拦截器按 errorType 分流处置，会话失效跳登录、业务身份错误就地提示，不一刀切清 token」 |
| 上游决议引用 | DEV-MDM-001 V1.1 §5.5 + V1.2 §8.3 |
| 修订理由 | 21 CFR Part 11 §11.10(g)「权限检查」与 §11.50「电子签名记录」属于不同审计语义；混在一个 401 错误码下会导致签名密码错误的用户被错误踢出会话，破坏审计连续性 |

---

### 修订 #5：§7.1 合规映射 — JWT iat 与 password_changed_at 比较精度

| 字段 | 内容 |
|---|---|
| docx 章节 | §7.1 21 CFR Part 11 / Annex 11 合规映射（脚注或附加说明）|
| 修订类型 | 新增施工注意事项 |
| V1.0 原文位置 | §7.1 合规映射表之后、§7.2 认证与授权之前 |
| V1.0 原文摘录 | 「系统验证 \| 后续完整 CSV 流程，文档化测试」（合规映射表末行后） |
| V1.1 修订内容 | 新增「⚠ 实施侧关键比较精度规则」框：「**JWT `iat` 与 `auth.user.password_changed_at` 比较时必须按整数秒截断**。JWT `iat` 由 PyJWT 写入为整数秒（Unix epoch），而 PostgreSQL `TIMESTAMPTZ` 的 `password_changed_at` 精度为微秒。直接比较会因为 `password_changed_at` 微秒部分非零，导致刚改完密码立刻签发的 token（同一秒）被判定为「在密码变更之前签发」从而误判失效。**正确比较**：`int(jwt['iat']) < int(password_changed_at.timestamp())`。改密码后旧 token 即时失效的语义仍然保证（密码变更跨秒后所有旧 token 失效）。」 |
| 上游决议引用 | DEV-MDM-001 V1.2 §7.1.3 |
| 修订理由 | M2.5.2 实测踩坑；属于"会话失效"合规要求的实施侧关键细节，文档不写就会被下一个开发者再次踩到 |

---

### 修订 #6：§7.2.1 认证流程 — 失败计数旁路提交补丁

| 字段 | 内容 |
|---|---|
| docx 章节 | §7.2.1 认证流程 |
| 修订类型 | 修订流程步骤 |
| V1.0 原文位置 | §7.2.1 流程第 2 步 |
| V1.0 原文摘录 | 「2. 后端验证密码（bcrypt 哈希比对），失败 5 次锁定账号」 |
| V1.1 修订内容 | 将第 2 步修订为：「2. 后端验证密码（bcrypt 哈希比对），失败 5 次锁定账号。**注意**：失败计数 `failed_login_count++` 与登录失败审计日志必须通过独立 `AsyncSessionLocal()` 旁路 session 提交，不能挂在主请求事务上（详见 §6.5 失败副作用旁路 session）；否则 raise 401 后主事务 rollback 会丢失计数，账号锁定保护失效。」 |
| 上游决议引用 | DEV-MDM-001 V1.1 §5.2 + V1.2 §5 |
| 修订理由 | 与 §6.5 旁路 session 修订形成闭环；明确账号锁定保护机制的实现约束 |

---

### 修订 #7：§7.2.2 RBAC 权限模型 — 多权限组合工厂

| 字段 | 内容 |
|---|---|
| docx 章节 | §7.2.2 RBAC 权限模型 |
| 修订类型 | 在「权限粒度」段落下新增小节 |
| V1.0 原文位置 | §7.2.2 末段「权限粒度」之后 |
| V1.0 原文摘录 | 「权限粒度： - 模块级：能否访问某个域的功能 - 操作级：能否在某域执行 CREATE / UPDATE / APPROVE / SIGN 等 - 数据级：能否访问某些受限数据（如保密项目）」 |
| V1.1 修订内容 | 在「数据级」之后新增小节：「**权限组合校验（GxP 关键端点）**：对 21 CFR Part 11 §11.50 / §11.70 要求电子签名的关键不可逆操作，端点装饰器使用 `require_all_permissions(...)` 工厂同时校验**操作权限 + 签名权限**双权限。例如：物质审批端点要求 `substance:approve + substance:sign`、资产终止端点要求 `asset:update + asset:sign`、项目状态变更要求 `project:update + project:sign`。**单一权限不足以触发关键操作**。权限矩阵种子数据中 `*:sign` 权限仅分配给 `QA_REVIEWER` 与 `PROJECT_MANAGER` / `SUBSTANCE_STEWARD` 等具备签名职责的角色。」 |
| 上游决议引用 | DEV-MDM-001 V1.2 §7.1.2 + §6.4.3 / §6.4.4 |
| 修订理由 | M2.5.1 / M3.2 实施已落地；属于关键合规端点设计模式，需在架构文档建立规范以约束 Phase 4-5 后续模块 |

---

### 修订 #8：§7.2.1 认证流程 — JWT 黑名单与改密失效

| 字段 | 内容 |
|---|---|
| docx 章节 | §7.2.1 认证流程 |
| 修订类型 | 修订第 6 步 + 新增第 7 步 |
| V1.0 原文位置 | §7.2.1 流程第 6 步 |
| V1.0 原文摘录 | 「6. 用户主动登出或会话失效，Token 加入 Redis 黑名单」 |
| V1.1 修订内容 | 将第 6 步修订为：「6. 用户主动登出或会话失效，Token 加入 Redis 黑名单（**注**：Redis 应用层接入推迟至 Phase 5，当前由 JWT `iat` 与 `auth.user.password_changed_at` 比较实现即时失效，见 §7.1 比较精度规则）」并新增第 7 步：「7. 用户改密后，`auth.user.password_changed_at` 更新至当前 UTC 时间；后续所有旧 token 因 `iat < password_changed_at`（按整数秒截断）被网关拒绝，无需 Redis 黑名单参与。」 |
| 上游决议引用 | DEV-MDM-001 V1.2 §7.1.3 + §7.2.1（Redis 推迟）|
| 修订理由 | 当前 Redis 应用层未接入但即时失效语义已通过 password_changed_at 实现；文档需反映实际实施路径与未来计划 |

---

### 修订 #9：§7.2.2 RBAC 权限模型 — 异步 GUC 注入禁用 + 显式 UPDATE

| 字段 | 内容 |
|---|---|
| docx 章节 | §7.2.2 RBAC 权限模型（或 §6.5 审计设计末尾，二选一由评审决定）|
| 修订类型 | 新增「实施侧反模式与正确做法」框 |
| V1.0 原文位置 | §7.2.2 末段（修订 #7 之后），或 §6.5 «⚠ 数据完整性关键设计» 之后 |
| V1.0 原文摘录 | — （V1.0 未涉及） |
| V1.1 修订内容 | 新增「⚠ 反模式：asyncpg 连接池 SET LOCAL GUC 跨事务泄漏」框：「**禁止**通过 `SET LOCAL <session_var> = …` 在事务内注入业务上下文（如 `e_signature_id`）让 DB 触发器读取，**即便使用 `SET LOCAL` 关键字**。asyncpg 连接池在事务结束后归还连接到池中，下一个事务复用同一物理连接时，前事务的 `SET LOCAL` 值会残留（M2.5.1 实测：第 2 条 status_history 写入了第 1 条事务的 e_signature_id）。**正确做法**：service 在创建 status_history 行后显式执行 `UPDATE status_history SET e_signature_id = :sid WHERE history_id = :hid`，由 ORM 显式传参，不依赖 session 变量注入。」 |
| 上游决议引用 | DEV-MDM-001 V1.2 §7.1.1 |
| 修订理由 | M2.5.1 实测踩坑且属于"看似工作但跨事务出错"的隐蔽 bug；架构文档必须显式禁止该模式，避免 Phase 4-5 后续模块重蹈 |

---

### 修订 #10：§7.4 备份与灾备 — 标注"生产部署前定义"

| 字段 | 内容 |
|---|---|
| docx 章节 | §7.4 备份与灾备 |
| 修订类型 | 修订状态标注（不改设计本身） |
| V1.0 原文位置 | §7.4 备份表标题之上 |
| V1.0 原文摘录 | 「类型 \| 频率 \| 保留期 \| 位置 全量备份 \| 每日 02:00 \| 30 天 \| 本地 + Duck-mounted NAS ...」 |
| V1.1 修订内容 | 在 §7.4 标题下新增一段说明：「**当前实施状态（Phase 1-3 完成时）**：本节备份策略为目标设计，dev / 测试环境尚未部署完整备份流程；**生产部署（Phase 4）前必须完成下列三项，缺一不可**：<br>① 按本节定义部署备份执行流程（全量 + WAL 增量）；<br>② **完成至少一次完整恢复演练**（从备份还原到独立环境并验证业务可用性，验证 RTO ≤ 4h / RPO ≤ 1h 指标）；<br>③ **演练记录归档**（含演练日期、执行人、起止时间、恢复结果、RTO/RPO 实测值、异常处理），并由 QA 归档至 GxP 验证证据库。<br>⚠ 未完成恢复演练的备份策略**不能视为已实施**——21 CFR Part 11 / Annex 11 与 GxP 数据完整性（ALCOA+）均要求"备份必须可恢复"，仅定义策略不算合规。详见 §10.6 路线图。」表格本体保持不变。 |
| 上游决议引用 | DEV-MDM-001 V1.2 §7.2.5 |
| 修订理由 | 避免审计组误读为"已实施"；与新增的 §10.6 未实施路线图相互引用 |

---

### 修订 #11：§10 附录 — 新增 §10.6「未实施项路线图」

| 字段 | 内容 |
|---|---|
| docx 章节 | §10 附录（在 §10.5 联系与反馈之后新增 §10.6） |
| 修订类型 | 新增附录小节 |
| V1.0 原文位置 | §10.5 联系与反馈之后、文档版权页之前 |
| V1.0 原文摘录 | 「10.5 联系与反馈 文档维护者：CMC IT 架构组 反馈渠道：项目协作平台 / 邮件 ...」（§10 当前以 10.5 结尾） |
| V1.1 修订内容 | 新增 §10.6 章节，内容如下：<br><br>**10.6 未实施项路线图（V1.1 新增）**<br><br>本架构文档 V1.0 描述的部分能力在 Phase 1-3（SRS / PRS / ARS）范围内**目标设计**已确定但**尚未实施**，列入后续阶段计划。各项与本文档相关章节交叉引用如下：<br><br>\| 项 \| 涉及章节 \| 当前状态 \| 计划阶段 \| 备注 \|<br>\|---\|---\|---\|---\|---\|<br>\| Redis 缓存层应用层接入 \| §4.2 容器图 / §7.2.1 第 6 步 \| 容器已部署，应用层未集成；JWT 即时失效改用 `password_changed_at` 实现 \| Phase 5 性能优化 \| 当前 dev 数据量无瓶颈 \|<br>\| Prometheus metrics endpoint \| §4.3 组件图（未画 metrics 端点）\| 未实现 \| Phase 4 生产部署前 \| 与可观测性建设打包 \|<br>\| 集中日志收集（ELK / Splunk）\| §4.5 部署视图 \| 仅 stdout loguru，日志目录 `/var/log/cmab-mdm/` 本地保留 \| Phase 4 生产部署前 \| — \|<br>\| 生产级 Nginx 反代 + k8s manifest \| §4.5 部署视图 \| 仅 docker-compose dev 配置 \| Phase 4 生产部署前 \| 当前部署形态见 §5.3 dev / test / prod 环境 \|<br>\| 数据库备份策略落地 \| §7.4 备份与灾备 \| 策略已定义，未部署执行 \| Phase 4 生产部署前 \| 含恢复演练 \|<br>\| CI 门禁 schema 一致性检查脚本 \| §5.2 开发工具链 \| 未实现 \| Phase 4 \| 比对 `information_schema` 与 DM-MDM-001 §7/§8/§9/§11 DDL diff \|<br>\| 完整 CSV 验证（URS / FS / DS / IQ / OQ / PQ）\| §7.5 CSV 验证策略 \| Phase 1 R&D 工具简化版完成 \| Phase 2 GxP 升级时（上线后 6-12 月）\| 与现行分阶段验证策略一致，无变更 \|<br>\| `/auth/refresh` 端点 \| §7.2.1 认证流程第 5 步 \| 未实现，当前 access_token 30min 过期需重登 \| Phase 4 安全收尾 \| 见 DEV-MDM-001 V1.2 §8.1.1 \|<br><br>本路线图**不影响**当前 Phase 1-3 范围内的 21 CFR Part 11 / Annex 11 合规**主要路径**符合性（实施侧整体加权对齐率 ~90%）。**全面合规结论需待完整 CSV 验证（OQ / PQ）通过后正式确认**；本文档不作"100% 合规"宣称。生产上线（Phase 4）前必须完成上表中标注「Phase 4 生产部署前」的全部项 + CSV 验证。 |
| 上游决议引用 | DEV-MDM-001 V1.2 §7.2.1–§7.2.6 + §8.1.1 |
| 修订理由 | 让架构文档与实施现状对齐；让 CSV 审计组与 QA 一眼看清"目标设计 vs 当前实施"边界，避免审计误判；为 Phase 4 部署收尾提供清单 |

---

## 评审决议表（评审会现场填写）

| 修订 # | 涉及章节 | 接受 / 修改 / 拒绝 | 修改要点（如需）| 决议人 | 日期 |
|---|---|---|---|---|---|
| #1 | §4.3 Domain Layer service commit | | | | |
| #2 | §6.5 失败副作用旁路 session | | | | |
| #3 | §6.5 audit_trigger parent_ref | | | | |
| #4 | §7.1 errorType 401 分流 | | | | |
| #5 | §7.1 JWT iat 整秒比较 | | | | |
| #6 | §7.2.1 失败计数旁路提交 | | | | |
| #7 | §7.2.2 require_all_permissions | | | | |
| #8 | §7.2.1 JWT 黑名单与改密失效 | | | | |
| #9 | §7.2.2 / §6.5 禁用 SET LOCAL GUC | | | | |
| #10 | §7.4 备份策略状态标注 | | | | |
| #11 | §10.6 未实施项路线图（新增）| | | | |

---

## 编制说明

- 本清单仅列出 V1.0 → V1.1 的**条目级修订指令**，秘书在 Word 修订模式下逐条落地。
- 所有「实施侧合理加强」均已在实施代码中落地并通过 117 条 pytest 用例回归（M3.4 完成时计数），架构文档吸收后不需要回滚代码。
- 「推迟项」不要求 V1.1 引入新章节描述实施方案，仅在 §10.6 路线图标注计划阶段；具体实施方案待 Phase 4 / 5 启动时另立设计文档（DEPLOY-MDM-001 等）。
- 修订 #9 的章节归属（§7.2.2 vs §6.5）建议评审会现场决定；DBA 视角可能更适合 §6.5，安全视角更适合 §7.2.2。
- 章节号若因新增 §10.6 等导致后续编号变化，秘书在 Word 修订时一并处理目录重建。

---

# V1.3 勘误登记（2026-06-06，待 V1.3 docx Word 修订吸收）

> **V1.1 docx（及派生 md）的事实性勘误**：文档与已实施代码不符，错误方为文档。不直接改签字 docx、不手改派生 md（`make docs-check` 强制 docx↔md 一致）；**过渡期以本节为准**（索引见 DEV-MDM-001 V1.2 §1A）。ARCH 是 V1.2 EQP 增补落地最不完整的一份：仅修订记录行 + 适用范围两处提及，正文实质章节全部未同步。

### 勘误 #E7 — §1.3.2 范围外清单：设备主数据仍列为 Out-of-Scope，与 V1.2 修订记录直接矛盾

| 字段 | 内容 |
|---|---|
| docx 章节 | §1.3.2 范围外（行 120） |
| V1.1 现状 | 范围外列表含"设备主数据（未来纳入 CMMS 或独立 Equipment Master）" |
| 实施事实 | V1.2（2026-06-04）EQP 设备域已为本系统第五业务域（migration 0040-0044：eqp.equipment + 三标识体系 + 5 类分类 + 工作站字段），修订记录行与适用范围"五大主数据域"均已声明 |
| 建议吸收文字 | 从范围外列表删除该行；如需保留语义，改为"设备**运营**数据（在用状态/位置/校验/维护等）— 归下游 CMC LabOps Portal，本系统仅管设备主数据（身份/采购属性）" |
| 来源 | 2026-06-06 文档一致性审查（外部复核报告 S2/N2 确认） |
| 状态 | **已落实**（2026-06-11，H-16 修复，负责人决策直接改 md）：ARCH md §1.3.1 表补 EQP 行（Equipment Master / 全公司仪器设备身份注册（V1.2 新增）/ 仪器设备）；§1.3.2 该条改写为"V1.1 原列范围外；V1.2 起已纳入本系统作为第五业务域 EQP"（保留历史语境，未采用"设备运营数据"改写口径——该语义留给 E8 §3.2 子节增补时表达）。E8/E9 仍未落实，随 V1.3 批次处理 |

### 勘误 #E8 — §3.2 各域职责定义：缺 Equipment Master 子节

| 字段 | 内容 |
|---|---|
| docx 章节 | §3.2（行 229-325，现有 3.2.1 SRS / 3.2.2 PRS / 3.2.3 ARS / 3.2.4 MM / 3.2.5 REF / 3.2.6 AUDIT 六子节） |
| V1.1 现状 | 无 EQP 子节；§3.1 主数据域分治模型、§3.3 数据流向同样未含设备域 |
| 实施事实 | eqp.equipment 已实现：全公司仪器设备身份注册表；EQP-yyyy 年度序列设备ID + equipment_no（业务）/ fixed_asset_no（财务）三标识；5 类分类体系；无状态机（简化设计）；下游 LabOps 经 API 拉取，不跨库外键 |
| 建议吸收文字 | 新增 §3.2.4A（或重编号为 3.2.5）Equipment Master (EQP) 子节，内容按 migration 0040-0044 docstring 与 DM §10A 表述对齐；§3.1 / §3.3 图示同步补第五域 |
| 来源 | 2026-06-06 文档一致性审查（S2/N2） |

### 勘误 #E9 — §6.1 PostgreSQL Schema 划分表：缺 eqp 行 + 表清单多处与实现不符

| 字段 | 内容 |
|---|---|
| docx 章节 | §6.1 Schema 划分表（行 729-738） |
| V1.1 现状 | ① 无 eqp 行；② srs 行缺 substance_small_molecule / substance_alias；③ mm 行列有不存在的 material_attribute；④ ref 行写 `ref_project_substance, ref_asset_substance, ref_material_substance`——前缀写法与实现不符且 ref_material_substance 从未定义、漏 project_asset；⑤ prs 行缺 project_relationship；⑥ auth 行缺 login_history / password_history |
| 实施事实 | 实际 9 个业务 schema；srs 7 表 / prs 5 表 / ars 3 表 / mm 2 表 / eqp 1 表 / ref 3 表（project_substance, asset_substance, project_asset）— 与 DM 修订清单 #E3（含扩展）一致 |
| 建议吸收文字 | 按实现重写该表（与 DM §2.1 修正稿保持同一份表清单，避免两文档再次漂移） |
| 来源 | 2026-06-06 文档一致性审查（S2/S3/N2，代码侧 migration 0001-0044 实物核对） |

### 勘误 #E10 — §7.2.2 预设角色：命名 camelCase 与实现不符 + 角色集不完整

| 字段 | 内容 |
|---|---|
| docx 章节 | §7.2.2 RBAC（行 944-950） |
| V1.1 现状 | 6 角色，camelCase（SystemAdmin / SubstanceSteward / ProjectManager / CMCResearcher / QAReviewer / ReadOnlyUser） |
| 实施事实 | 代码 role_code 为 SNAKE_CASE，且 seed 共 **8** 角色：SYS_ADMIN / SUBSTANCE_STEWARD / PROJECT_MANAGER / CMC_RESEARCHER / QA_REVIEWER / READ_ONLY_USER + V1.2 新增 CMC_WAREHOUSE_ADMIN / CMC_EQUIPMENT_ADMIN。注意：DM §4.3 还列有 REGULATORY_USER（代码无），四处角色集不一致的统一决议见 DM 修订清单 #E12 |
| 建议吸收文字 | 角色名改 SNAKE_CASE 并补全 8 角色（REGULATORY_USER 去留按 #E12 决议结果同步） |
| 来源 | 2026-06-06 文档一致性审查（S4/N4 + seed_data.py 实物核对） |

### 勘误 #E11 — §1.4 关键决策摘要：JWT 签名算法未注明环境分野

| 字段 | 内容 |
|---|---|
| docx 章节 | §1.4（行 141） |
| V1.1 现状 | "认证方式 \| 系统自建用户表 + JWT" |
| 实施事实 | Phase 5.C 已落地 RS256（生产）/ HS256（开发）双模式（见 RUNBOOK_JWT_RS256.md）；API-MDM-001 §2 已注明，ARCH 作为上位文档未同步 |
| 建议吸收文字 | 改为"系统自建用户表 + JWT（HS256 开发 / RS256 生产，密钥管理见 RUNBOOK_JWT_RS256）" |
| 来源 | 2026-06-06 文档一致性审查 |
