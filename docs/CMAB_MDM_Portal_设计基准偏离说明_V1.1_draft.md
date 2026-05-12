# CMAB MDM Portal 设计基准偏离说明

| 项目 | 内容 |
|---|---|
| 文档编号 | DEV-MDM-001 |
| 版本 | V1.1 Draft |
| 状态 | 待 CMC IT 架构组评审 |
| 上位文档 | DM-MDM-001 V1.0（数据模型设计文档）/ ARCH-MDM-001 V1.0 |
| 编制 | CMC R&D（实施侧） |
| 日期 | 2026-05-11 |
| 分类 | 合规审计配套文档 |

## 1. 文档目的

记录 Phase 1（SRS）/ Phase 2（PRS + REF + 全局搜索）/ Phase 2.5（电子签名 + 安全收尾）实施过程中，**与 DM-MDM-001 V1.0 数据模型设计文档的全部已识别偏离**，并给出三类处置：
- **🟥 待对齐回归**：将通过 M3.0 系列迁移强制回归至设计文档基准（migration 0012–0020）。
- **🟢 实施侧合理加强**：基于 21 CFR Part 11 / EMA Annex 11 合规要求或 SQLAlchemy/FastAPI 实际工程坑位，**保留实施版本**，建议吸收进设计文档 V1.1。
- **🟠 未实施 / 推迟**：设计文档要求但 Phase 1-2.5 未实施的部分，列入后续里程碑。

本文档作为 GxP 计算机化系统验证（CSV）的"设计基准与实施差异说明"提交质量审计。

---

## 2. SRS（§7 物质域）偏离

### 2.1 🟥 待对齐回归

| # | 设计基准 §7 | 实施现状 | 处置（M3.0.3） |
|---|---|---|---|
| 2.1.1 | §7.4 `srs.substance_adc` 表（含 antibody_substance_id / linker_substance_id / payload_substance_id 父子血缘 + DAR） | 未建表，ADC 类型物质只有主表行 | migration 0017 补建 |
| 2.1.2 | §7.5 `srs.substance_small_molecule` 表（smiles / inchi / inchi_key / molecular_formula） | 未建表 | migration 0017 补建 |
| 2.1.3 | §7.8 `srs.substance_alias` 表（曾用名 / 项目代号） | 未建表 | migration 0017 补建 |
| 2.1.4 | §7.6 `substance_xref` 含 `effective_date` / `expiry_date` 字段 + `UNIQUE(xref_type, xref_value) WHERE deleted_at IS NULL` 部分唯一 | 缺这两个字段，缺唯一约束 | migration 0018 补字段 + 唯一约束 |
| 2.1.5 | §7.2 `substance.created_by/updated_by/registered_by/deleted_by` 均 FK 到 auth.user(user_id) | 用裸 BIGINT，无外键约束 | migration 0019 加 FK（同步处理 PRS 主表的同类字段）|
| 2.1.6 | §7.2 主表索引 `ix_substance_extra` GIN on `extra` 字段 | 未建该索引 | migration 0019 补 |
| 2.1.7 | §7.3 `substance_protein` 的 `sequence_hash_hc/lc` 与 `sequence_length_hc/lc` 由 DB 触发器 `fn_substance_protein_compute_hash` 自动算 | 在 Python service 层算（Phase 1 M1.1 + migration 0004 backfill） | migration 0020 改用 DB 触发器，service 层移除算法；保留 Python 兼容路径用于 unit test |

### 2.2 🟢 实施侧合理加强（建议吸收进 V1.1）

| # | 实施加强项 | 触发原因 | 建议 V1.1 处置 |
|---|---|---|---|
| 2.2.1 | `audit.fn_audit_trigger` 加第 3 参数 `parent_ref`（格式 `schema.table:pk:code_col:fk_on_this_table`），让子表 audit_log.entity_code 自动回填父表 code（如 substance_xref 行回填 SUB-XXXXXXX） | §6.5 通用审计触发器对子表 entity_code 写 NULL，按业务编码查审计历史不可用 | V1.1 §6.5 加入此设计 |
| 2.2.2 | service 层在状态变更后**显式 `await db.commit()`**，避免 FastAPI yield 依赖的 cleanup commit 发生在 response 之后导致客户端连续请求读 pre-commit 状态 | FastAPI 异步 yield 依赖文档化的行为；§11.300 强一致性要求 | V1.1 §15.2 ORM 实现章加施工说明 |
| 2.2.3 | 登录失败与签名失败的 `failed_login_count++` + 审计日志写入走**旁路独立 AsyncSession 独立 commit** | 主事务 raise 异常后 `get_db` rollback 会丢失防暴力破解计数与失败审计（违反 §11.300）| V1.1 §15.2 实现示例加 |

### 2.3 🟠 暂未识别偏离

无。SRS 主体（substance + protein + xref + status_history）字段层面与文档一致。

---

## 3. PRS（§9 项目域）偏离

⚠️ 本节偏离量最大。Phase 1-2.5 实施时 PRS 数据模型为 Phase 2 阶段在 .docx 设计文档之外**独立设计**，与 §9 大量字段命名/枚举/约束不一致。M3.0.2 将强制回归。

### 3.1 🟥 prs.project 主表

#### 3.1.1 状态枚举不一致

| 设计基准 §9.2 `ck_project_status` | 实施 V0.5（M2.1）| 处置 |
|---|---|---|
| `proposed / initiated / active / on_hold / completed / terminated` | `draft / planned / active / on_hold / completed / terminated` | M3.0.2 迁移；现有 demo 数据按 draft→proposed、planned→initiated 映射 |

#### 3.1.2 项目类型枚举不一致

| 设计基准 §9.2 `ck_project_type` | 实施 V0.5 | 处置 |
|---|---|---|
| `cmc / preclinical / clinical / regulatory / commercial / platform / other` | `discovery / preclinical / clinical / cmc / tech_transfer / lifecycle / other` | M3.0.2 迁移，含枚举值映射表 |

#### 3.1.3 缺失字段

| 设计基准 §9.2 字段 | 实施 V0.5 | 处置 |
|---|---|---|
| `parent_project_id BIGINT FK self`（子项目层级） | 未建 | M3.0.2 补 |
| `program_name VARCHAR(128)`（所属 Program） | 未建 | M3.0.2 补 |
| `sponsor_id BIGINT FK auth.user` | 未建 | M3.0.2 补 |
| `department VARCHAR(64)` | 未建 | M3.0.2 补 |
| `budget_total NUMERIC(18,2)` / `budget_currency` / `budget_actual` | 未建 | M3.0.2 补 |
| `objective TEXT` / `scope` / `deliverables` / `success_criteria` | 未建 | M3.0.2 补 |
| `priority VARCHAR(16)` | 未建 | M3.0.2 补 |
| `confidentiality VARCHAR(16)` | 未建 | M3.0.2 补 |
| `ck_project_dates CHECK (planned_end_date >= planned_start_date)` | 未建 | M3.0.2 补 |

#### 3.1.4 字段命名不一致

| 设计基准 §9.2 | 实施 V0.5 | 处置 |
|---|---|---|
| `project_phase` | `phase` | M3.0.2 重命名 |
| `project_manager_id`（FK auth.user）| `project_owner_id` | M3.0.2 重命名 |

#### 3.1.5 实施多加的字段

| 实施 V0.5 额外字段 | 文档 §9.2 状态 | 处置 |
|---|---|---|
| `approved_at TIMESTAMPTZ` / `approved_by BIGINT` | 文档不含 | M3.0.2 移除；同等信息由 `project_status_history` 推断 |
| `phase` 字段 CHECK 约束 10 个枚举值 | 文档允许任意字符串 | M3.0.2 移除 CHECK；保留字段 |

#### 3.1.6 编码生成函数

| 设计基准 §9.2 | 实施 V0.5 | 处置 |
|---|---|---|
| 按年生成 `PRJ-2026-XXXX`（`meta.fn_ensure_year_sequence`） | 全局 `PRJ-XXXXXXX` | M3.0.2 改造编码函数；现有 PRJ-XXX 不回填（保持稳定 ID）|

### 3.2 🟥 prs.project_milestone

| # | 设计基准 §9.3 | 实施 V0.5 | 处置 |
|---|---|---|---|
| 3.2.1 | `status` 枚举：`planned / in_progress / completed / delayed / cancelled` | `pending / achieved / missed / cancelled` | M3.0.2 改枚举 + FE 状态颜色 |
| 3.2.2 | `milestone_type` 枚举：`gate / deliverable / decision`（3 值） | `gate / deliverable / regulatory / clinical / cmc / other`（6 值） | M3.0.2 改枚举（接受文档约束）|
| 3.2.3 | `planned_date DATE NOT NULL` | nullable | M3.0.2 改 NOT NULL |
| 3.2.4 | 文档无 `deleted_at` / `deleted_by`（依赖 ON DELETE CASCADE 父项目） | 我加了软删除字段 | M3.0.2 移除字段；改 ON DELETE CASCADE |

### 3.3 🟥 prs.project_team

| # | 设计基准 §9.4 | 实施 V0.5 | 处置 |
|---|---|---|---|
| 3.3.1 | 字段名 `role VARCHAR(64)` 无 CHECK 约束 | `role_in_project VARCHAR(32)` + 8 值 CHECK | M3.0.2 改字段名 + 移除 CHECK |
| 3.3.2 | 缺 `function_area VARCHAR(64)` | — | M3.0.2 补 |
| 3.3.3 | 缺 `allocation_pct INT 0-100` | — | M3.0.2 补 |
| 3.3.4 | `joined_at DATE NOT NULL DEFAULT CURRENT_DATE` / `left_at DATE` | TIMESTAMPTZ | M3.0.2 改类型 |
| 3.3.5 | `UNIQUE (project_id, user_id, role)` 绝对唯一 | partial unique WHERE left_at IS NULL（允许"离开后再加入"）| M3.0.2 改普通唯一；离开后再加入需走解绑+重建并放弃唯一性的语义。**待 §9.4 修订决定**：是否允许离开后再加入？建议 V1.1 明确 |

### 3.4 🟥 prs.project_status_history

| # | 设计基准 §9.5 | 实施 V0.5 | 处置 |
|---|---|---|---|
| 3.4.1 | 无 `e_signature_id` 字段 | 加了 `e_signature_id BIGINT FK audit.e_signature`（M2.5.1 加）| 🟢 实施侧合理加强（§11.50 状态变更需关联电子签名）；建议 V1.1 §9.5 加此字段 |

### 3.5 🟥 prs.project_relationship

| # | 设计基准 §9.5 | 实施 V0.5 | 处置 |
|---|---|---|---|
| 3.5.1 | `prs.project_relationship` 表（merged_into / split_from / derived_from / depends_on / blocks） | 未建 | M3.0.2 补建（但 API 层 M3.0 阶段不上线，留 Phase 3+ ARS 联动时再做）|

---

## 4. REF（§11 跨域引用）偏离

### 4.1 🟥 ref.project_substance 结构完全重构

| 维度 | 设计基准 §11.2 | 实施 V0.5（M2.3） | 处置 |
|---|---|---|---|
| 主键 | 复合 PK `(project_id, substance_id, relation_type)` | 自增 `link_id BIGINT` | M3.0.1 DROP + CREATE 重建表 |
| 关联字段 | `relation_type VARCHAR(32)` | `role VARCHAR(32)` | 重命名 + 改枚举 |
| 枚举值 | `primary / secondary / reference / control / derivative` | `primary_target / candidate / backup / excluded / reference` | M3.0.1 改 |
| 额外字段 | `is_primary BOOLEAN NOT NULL DEFAULT FALSE` | `priority INT` | 用 is_primary 替代 |
| 解除语义 | `deleted_at / deleted_by`（软删=取消引用）| `unlinked_at / unlinked_by`（专门字段）| 用 deleted_at 替代 |
| audit trigger 入参 | `('project_id', NULL)` | `('link_id', '', 'prs.project:...')` | 改回 project_id；但保留实施侧加强（第 3 参数 parent_ref）|

### 4.2 🟢 实施侧合理加强

`audit.fn_audit_trigger` 第 3 参数 `parent_ref`（让子表 entity_code 自动回填父 code）保留，但 ref.project_substance 的 trigger 第 1 参数由 `link_id` 改回 `project_id`（与 §11.2 一致）。

### 4.3 🟠 待新增

| 表 | 文档章节 | 状态 |
|---|---|---|
| `ref.asset_substance` | §11.3 | 未建，Phase 3 ARS 时建 |
| `ref.project_asset` | §11.4 | 未建，Phase 3 ARS 时建 |

---

## 5. 跨主题实施侧合理加强（21 CFR Part 11 / FastAPI 工程坑）

下述加强是基于实施过程中发现的真实合规缺口或工程 race condition，**应保留并吸收进 V1.1**：

### 5.1 状态变更的 service 显式 commit

**原因**：FastAPI 的 `yield` 依赖（如 `get_db`）的 cleanup 代码（`await session.commit()`）在 **response 已发送给客户端之后** 才执行。客户端拿到 200 后立即发送下一请求，可能赶在 commit 完成前到达 → 新连接读到 pre-commit 快照（pytest 全集观察到 ~10% 失败率）。

**实施**：service 在写完所有变更后**显式** `await self.db.commit()`，FastAPI 依赖的 commit 退化为空操作。

**建议**：V1.1 §15.2 ORM 实现章节加施工说明。

### 5.2 失败副作用旁路 session 持久化

**原因**：service 层中的 `user.failed_login_count += 1` + 失败 audit_log 写入位于 raise 异常之前，但 raise 触发 `get_db` 的 `except: rollback()` → 防暴力破解计数与失败审计**全部回滚**，违反 §11.300。

**实施**：登录失败、签名失败的副作用均使用独立 `AsyncSessionLocal()` 旁路 session 单独 commit，不受主事务 rollback 影响。

**建议**：V1.1 §6.5 通用审计触发器之外，明确"失败审计旁路写入"模式作为标准实现。

### 5.3 audit.fn_audit_trigger 第 3 参数 parent_ref

**原因**：§6.5 通用审计触发器对子表（如 substance_xref、project_milestone）的 `entity_code` 字段写 NULL（子表无业务编码），导致"按 SUB-XXX / PRJ-XXX 查询全部审计历史"不能覆盖子表事件。

**实施**：触发器函数加第 3 个 TG_ARG，格式 `'schema.table:pk_col:code_col:fk_on_this_table'`，子表触发器传此参数让 audit_log.entity_code 自动从父表回填。

**建议**：V1.1 §6.5 更新触发器签名为 3 参数。

### 5.4 status_history 加 e_signature_id

**原因**：21 CFR Part 11 §11.50/11.70 要求电子签名记录绑定到被签业务记录。仅在 audit.e_signature 表存签名行不够，需要从业务表的状态历史能直接查到签名。

**实施**：`substance_status_history` 和 `project_status_history` 均加 `e_signature_id BIGINT FK audit.e_signature(signature_id)`。

**建议**：V1.1 §7.7 和 §9.5 加此字段。

### 5.5 401 响应分流（业务身份再验证 vs 会话失效）

**原因**：电子签名密码错（业务身份再验证失败）与 JWT 过期（会话失效）都是 401，但语义不同。前端拦截器若一律按"会话失效"清 token 跳登录，会把"签名密码错"的用户错误踢出。

**实施**：后端响应 errorType 区分 `signature_invalid` / `token_expired` / `token_invalid`；前端 axios 拦截器按 errorType 分流。

**建议**：V1.1 API 接口规范（API-MDM-001）加 errorType 字典与前端处置约定。

---

## 6. 处置时间表

| 子里程碑 | 内容 | 状态 |
|---|---|---|
| **M3.0.1** | ref.project_substance 重构（§11.2）| ✅ 已完成 2026-05-11（migration 0012）|
| **M3.0.2** | prs 全表对齐（§9.2 / §9.3 / §9.4 / §9.5）| ✅ 已完成 2026-05-11（migration 0013-0017）|
| **M3.0.3** | srs 补缺子表（§7.4 / §7.5 / §7.6 / §7.8）+ FK 加强 + sequence_hash DB 触发器 | ✅ 已完成 2026-05-11（migration 0018-0021）|
| **M3.1+** | Phase 3 ARS 按 §8 设计文档新建 | 🚧 待开工 |
| **V1.1 文档评审** | IT 架构组评审本偏离说明 + 决定吸收哪些"实施侧合理加强"到 DM-MDM-001 V1.1 | 待安排 |

---

## 7. 风险与缓解

| 风险 | 影响 | 缓解 |
|---|---|---|
| M3.0.2 PRS 状态枚举改动会破坏前端组件 / 演示数据 | 中 | reset-db + 重 seed --demo；前端测试覆盖 |
| 数据迁移期间生产数据丢失 | 高（生产上线后）| dev 环境无生产数据，M3.0 阶段无影响；生产部署前需 freeze + 数据迁移演练 |
| V1.1 评审周期延后阻塞 M3.0 | 中 | M3.0 按本文档草案先实施；V1.1 评审主要决定"实施侧加强"是否吸收，与回归对齐不冲突 |

---

## 8. 评审记录

| 评审人 | 日期 | 决议 |
|---|---|---|
| _待 CMC IT 架构组_ | _待安排_ | _待评审_ |
| _待 QA 质量管理部_ | _待安排_ | _待评审_ |

---

## 附录 A：自动化检查工具

实施侧已在 `backend/tests/` 加入针对偏离的回归测试。M3.0 完成后将增加 schema 一致性检查脚本，每次 alembic upgrade 后比对 `information_schema` 与 §7/§8/§9/§11 DDL 的字段/枚举/约束 diff，作为 CI 门禁。
