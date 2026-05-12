# DM-MDM-001（数据模型设计文档）V1.0 → V1.1 修订清单

| 项目 | 内容 |
|---|---|
| 文档 | DM-MDM-001 V1.0 → V1.1 |
| 上游决议 | DEV-MDM-001 V1.2_draft §2 / §3 / §4 / §5 / §6 |
| 用途 | 供 CMC IT 架构组逐项决议「接受 / 拒绝 / 修改」；秘书在 Word 修订模式下落地。**本清单不直接改 docx**。 |
| 修订总数 | 12 项（9 项建议接受 + 2 项待评审决议 + 1 项可选备注） |
| 编制日期 | 2026-05-12 |

定位说明：V1.0 docx 提取的 txt 无页码，本清单用「§X.Y 第 N 个 DDL 块 / 第 N 段文字 / 行号 ≈ N」三类锚点定位；秘书在 docx 中按章节标题与 DDL 关键词搜索即可。

---

## 修订清单（按 docx 章节序）

### 修订 #1 — §6.5 通用审计触发器函数：函数签名扩为 3 参数

| 字段 | 内容 |
|---|---|
| docx 章节 | §6.5 通用审计触发器函数 |
| 修订类型 | 函数体修改 + 注释更新 |
| V1.0 原文位置 | §6.5 函数体 `audit.fn_audit_trigger()`，`TG_ARGV[0]` 与 `TG_ARGV[1]` 引用块（INSERT/UPDATE/DELETE 三个分支） |
| V1.0 原文摘录 | `v_entity_id := (v_new_jsonb ->> (TG_ARGV[0]))::BIGINT; v_entity_code := v_new_jsonb ->> COALESCE(TG_ARGV[1], 'code');` —— 函数仅使用 2 个 TG_ARGV，子表 entity_code 写 NULL |
| V1.1 修订内容 | 函数加入第 3 参数 `parent_ref`，格式约定 `'<schema>.<parent_table>:<parent_pk_col>:<parent_code_col>:<fk_col_on_this_table>'`。函数体新增：当 TG_ARGV[2] 非空时，解析 parent_ref，按当前行的 FK 值查父表回填 `v_entity_code`（子表事件按业务编码可查）。函数注释更新为「子表传 parent_ref 让 entity_code 从父表回填」。 |
| 上游决议引用 | DEV-MDM-001 V1.2 §5（延续 V1.1 §2.2.1 / §4.2 / §5.3） |
| 修订理由 | 子表 audit_log.entity_code 写 NULL，按 SUB-XXX / PRJ-XXX / AST-XXX 查全链路审计历史会丢子表事件，违反 21 CFR Part 11 可追溯性。 |

### 修订 #2 — §6.5 触发器使用示例：补 3 参数调用约定

| 字段 | 内容 |
|---|---|
| docx 章节 | §6.5 通用审计触发器函数 — 末尾「💡 应用层使用方式」段后 |
| 修订类型 | 新增子段 |
| V1.0 原文位置 | §6.5 「💡 应用层使用方式」后、§7 开始之前 |
| V1.0 原文摘录 | （无对应原文，新增段） |
| V1.1 修订内容 | 新增「💡 触发器调用约定」子段：① 主表（substance / project / asset / material 等）`fn_audit_trigger('<pk_col>', '<code_col>')`（2 参数）；② 子表（无业务编码）`fn_audit_trigger('<pk_col>', NULL, '<schema>.<parent_table>:<parent_pk>:<parent_code>:<fk_col>')`（3 参数）；并给出示例 `fn_audit_trigger('xref_id', NULL, 'srs.substance:substance_id:substance_code:substance_id')`。 |
| 上游决议引用 | DEV-MDM-001 V1.2 §5（延续 V1.1 §2.2.1） |
| 修订理由 | 仅改函数定义不足以让实施侧统一调用方式，必须给出调用模板，否则各子表 trigger 仍会按 V1.0 2 参写法漏传 parent_ref。 |

### 修订 #3 — §7、§8、§9、§11 所有子表 CREATE TRIGGER 调用：补第 3 参数

| 字段 | 内容 |
|---|---|
| docx 章节 | §7.3 / §7.4 / §7.5 / §7.6 / §8.3 / §9.3 / §11.2 各表 `CREATE TRIGGER trg_*_audit ... fn_audit_trigger(...)` 行 |
| 修订类型 | 批量改 CREATE TRIGGER 语句（共 7 处） |
| V1.0 原文位置 | §7.3 `trg_substance_protein_audit`（参数 `'substance_id', NULL`）/ §7.4 `trg_substance_adc_audit`（`'substance_id', NULL`）/ §7.5 `trg_substance_sm_audit`（`'substance_id', NULL`）/ §7.6 `trg_substance_xref_audit`（`'xref_id', NULL`）/ §8.3 `trg_asset_market_id_audit`（`'market_id_pk', NULL`）/ §9.3 `trg_project_milestone_audit`（`'milestone_id', NULL`）/ §11.2 `trg_ref_ps_audit`（`'project_id', NULL`） |
| V1.0 原文摘录 | 示例：`CREATE TRIGGER trg_substance_xref_audit AFTER INSERT OR UPDATE OR DELETE ON srs.substance_xref FOR EACH ROW EXECUTE FUNCTION audit.fn_audit_trigger('xref_id', NULL);` |
| V1.1 修订内容 | 7 处 TRIGGER 调用统一改为 3 参数。改后示例：`fn_audit_trigger('xref_id', NULL, 'srs.substance:substance_id:substance_code:substance_id')`；其余按下表 parent_ref 值替换。<br><br>**parent_ref 参数对照表**：<br>· §7.3 substance_protein → `'srs.substance:substance_id:substance_code:substance_id'`<br>· §7.4 substance_adc → `'srs.substance:substance_id:substance_code:substance_id'`<br>· §7.5 substance_small_molecule → `'srs.substance:substance_id:substance_code:substance_id'`<br>· §7.6 substance_xref → `'srs.substance:substance_id:substance_code:substance_id'`<br>· §8.3 asset_market_id → `'ars.asset:asset_id:asset_code:asset_id'`<br>· §9.3 project_milestone → `'prs.project:project_id:project_code:project_id'`<br>· §11.2 ref.project_substance → `'prs.project:project_id:project_code:project_id'` |
| 上游决议引用 | DEV-MDM-001 V1.2 §4 / §5 / §6.2.4 / §6.5.5 / §6.6.3 |
| 修订理由 | 与修订 #1/#2 联动，全部子表 trigger 必须用 3 参数版本，否则功能上无法回填 entity_code。 |

### 修订 #4 — §8.1 表清单：在 §8 章节内补建 asset_status_history DDL（§8.4 新建）

| 字段 | 内容 |
|---|---|
| docx 章节 | §8 Schema: ars（Asset Registration）— §8.3 之后插入新小节 §8.4 |
| 修订类型 | 新增小节 + 新增 DDL |
| V1.0 原文位置 | §8.1 表清单第 3 行列出 `ars.asset_status_history`（"资产状态变更历史"），但 §8 全章只有 §8.2 asset / §8.3 asset_market_id，**§8.4 缺失** |
| V1.0 原文摘录 | "ars.asset_status_history｜资产状态变更历史"（§8.1 表清单）；§8 章节后续无对应 DDL |
| V1.1 修订内容 | 在 §8.3 后新增 §8.4 `ars.asset_status_history（状态变更历史）`，DDL 与 §7.7 / §9.5 同构：<br>字段：history_id BIGINT PK / asset_id BIGINT NOT NULL FK ars.asset / old_status / new_status NOT NULL / change_reason TEXT NOT NULL / changed_at TIMESTAMPTZ DEFAULT NOW() / changed_by BIGINT NOT NULL FK auth.user / **e_signature_id BIGINT FK audit.e_signature**（terminate 强制电签）<br>索引：`ix_asset_status_history_asset (asset_id, changed_at DESC)`<br>触发器：`trg_asset_status_change AFTER UPDATE ON ars.asset`（OLD.status DISTINCT FROM NEW.status 时自动写入，参照 §7.7 / §9.5 的 fn_*_status_change 函数模板）<br>章节注释：「ars.asset 状态机 3 值（active / on_hold / terminated）；terminate 为关键不可逆动作（21 CFR Part 11 §11.50），强制要求 e_signature_id 非空」 |
| 上游决议引用 | DEV-MDM-001 V1.2 §6.3.1 / §6.3.2（实施 migration 0024 已建） |
| 修订理由 | §8.1 表清单已声明此表存在，DDL 缺失为文档遗漏；实施侧 M3.1 已按 §7.7/§9.5 同构补建，须正式入文档闭环。 |

### 修订 #5 — §9.5 prs.project_status_history：补 `e_signature_id` 字段

| 字段 | 内容 |
|---|---|
| docx 章节 | §9.5 prs.project_status_history 与 project_relationship — `CREATE TABLE prs.project_status_history` DDL |
| 修订类型 | 表结构修改（加字段 + 加 FK） |
| V1.0 原文位置 | §9.5 第 1 个 CREATE TABLE 块，字段列表（history_id / project_id / old_status / new_status / change_reason / changed_at / changed_by 共 7 字段，**无 e_signature_id**） |
| V1.0 原文摘录 | `CREATE TABLE prs.project_status_history ( history_id ... changed_by BIGINT NOT NULL, CONSTRAINT fk_project_status_history_project ..., CONSTRAINT fk_project_status_history_user ... );` |
| V1.1 修订内容 | 在 `changed_by` 后新增字段 `e_signature_id BIGINT,                          -- 关键状态变更需电子签名`；CONSTRAINT 列表内补 `CONSTRAINT fk_project_status_history_sig FOREIGN KEY (e_signature_id) REFERENCES audit.e_signature(signature_id)`。与 §7.7 `srs.substance_status_history` 完全对齐（§7.7 V1.0 已有此字段）。 |
| 上游决议引用 | DEV-MDM-001 V1.2 §5（延续 V1.1 §3.4.1 / §5.4） |
| 修订理由 | §7.7 substance_status_history 已含 e_signature_id，§9.5 project_status_history 缺失为不一致点；21 CFR Part 11 §11.50/11.70 要求电子签名绑定到被签业务记录，必须与 SRS 对齐。 |

### 修订 #6 — §11.1 设计原则：补「业务规则」原则项

| 字段 | 内容 |
|---|---|
| docx 章节 | §11.1 设计原则 |
| 修订类型 | 文字段落新增条目 |
| V1.0 原文位置 | §11.1 第 4 条「被引用实体不可物理删除（外键约束保证）」之后 |
| V1.0 原文摘录 | "跨域引用集中管理 / 引用关系类型灵活 / 支持多对多关系 / 被引用实体不可物理删除（外键约束保证）"（4 条原则，无业务规则项） |
| V1.1 修订内容 | 新增第 5 条："**业务规则：被引用实体处于终止态（substance.status='obsoleted' / asset.status='terminated' / project.status='terminated'）时，service 层禁止新建关联记录（已存在记录不强制清理）。本规则由应用层校验，DB 层不加 CHECK。**" |
| 上游决议引用 | DEV-MDM-001 V1.2 §6.6.4（延续 V1.1 §3 "obsoleted 物质不允许新关联"） |
| 修订理由 | 实施侧已在 service 层强制 terminated/obsoleted 实体禁止新建关联，文档需正式声明此业务规则，让后续 service 实现有据可依，亦避免日后被误判为越权加强。 |

### 修订 #7 — §15.2 SQLAlchemy ORM 映射示例：补 service-level 显式 commit 施工说明

| 字段 | 内容 |
|---|---|
| docx 章节 | §15.2 SQLAlchemy ORM 映射示例 — 在 ORM 类定义示例之后新增子段 |
| 修订类型 | 新增子段（施工说明） |
| V1.0 原文位置 | §15.2 章节末尾 `class Substance(Base): ...` 示例之后，§15.3 之前 |
| V1.0 原文摘录 | §15.2 仅有 Substance ORM 类定义示例，无 service 层事务管理说明 |
| V1.1 修订内容 | 新增子段「§15.2.1 service 层事务提交时机」：<br>1. 写操作完成后，service 必须**显式 `await self.db.commit()`**，不依赖 FastAPI yield 依赖（`get_db`）的 cleanup commit。<br>2. 原因：FastAPI 的 `yield` 依赖 cleanup 在 **response 已发送给客户端之后** 才执行，客户端连续请求可能在 commit 完成前到达新连接，读到 pre-commit 快照，违反 §11.300 强一致性要求。<br>3. 示例伪代码：<br>`async def update_status(...): self.db.add(...); await self.db.flush(); await self.db.commit(); return result`<br>4. 影响范围：所有状态变更端点、签名生效端点、跨域关联写入端点。 |
| 上游决议引用 | DEV-MDM-001 V1.2 §5（延续 V1.1 §2.2.2 / §5.1） |
| 修订理由 | FastAPI + asyncpg 异步事务的典型工程坑，pytest 全集观察到 ~10% 失败率；不入文档则下次实施仍会踩同一个坑。 |

### 修订 #8 — §15.2 ORM 映射示例：补「失败副作用旁路 session」施工说明

| 字段 | 内容 |
|---|---|
| docx 章节 | §15.2 SQLAlchemy ORM 映射示例 — 紧接修订 #7 之后再新增子段 |
| 修订类型 | 新增子段（施工说明） |
| V1.0 原文位置 | §15.2.1（新建，见修订 #7）之后 |
| V1.0 原文摘录 | （无对应原文，新增段） |
| V1.1 修订内容 | 新增子段「§15.2.2 失败副作用旁路 session 持久化」：<br>1. 适用场景：登录失败计数（`user.failed_login_count++`）、签名密码错误、状态机非法转换等"失败但需留痕"的副作用。<br>2. 反模式：在主 service session 里写 `failed_login_count++` 再 raise → `get_db` 的 except 分支 rollback 会同时撤销计数与失败 audit_log，导致防暴力破解失效。<br>3. 推荐模式：副作用走独立 `AsyncSessionLocal()` 旁路 session，单独 `await session.commit()`，再 raise 业务异常。主事务的 rollback 不影响旁路 session 已提交的失败记录。<br>4. 示例伪代码：<br>`async with AsyncSessionLocal() as bypass: bypass.add(audit_log); user.failed_login_count += 1; await bypass.merge(user); await bypass.commit(); raise HTTPException(401, ...)`<br>5. 与 §6.5 通用审计触发器的关系：成功路径的审计走触发器；失败路径的审计走 service 显式写入 + 旁路 session。 |
| 上游决议引用 | DEV-MDM-001 V1.2 §5（延续 V1.1 §2.2.3 / §5.2） |
| 修订理由 | §11.300 要求失败行为必须留痕，主事务 rollback 会冲掉计数与日志属典型陷阱；建立标准实现模式避免各域 service 各写各的。 |

### 修订 #9 — §6.4 audit.e_signature 章节后补「errorType 与审计的对应关系」备注

| 字段 | 内容 |
|---|---|
| docx 章节 | §6.4 audit.e_signature — DDL 与 COMMENT 之后 |
| 修订类型 | 新增章节末尾备注段 |
| V1.0 原文位置 | §6.4 章节末尾，`COMMENT ON TABLE audit.e_signature IS '电子签名记录，满足 21 CFR Part 11.50/11.70';` 之后 |
| V1.0 原文摘录 | §6.4 仅有 e_signature DDL，无 errorType 与审计行为的关联说明 |
| V1.1 修订内容 | 新增备注「💡 签名失败与会话失效的审计分流」：<br>1. **业务身份再验证失败**（签名密码错）：HTTP 401 + errorType=`signature_invalid`；走"失败副作用旁路 session"（§15.2.2）写 `audit_log.action='SIGN'` 且 result=failed；**不**清前端 token。<br>2. **会话失效**（JWT 过期 / 无效 / 缺失）：HTTP 401 + errorType=`token_expired` / `token_invalid` / `token_missing`；前端拦截器清 token 跳登录。<br>3. errorType 字典的完整定义参见 API-MDM-001 V1.1。<br>4. 本数据模型层仅声明：audit_log + e_signature 表必须能区分上述两类 401 事件，便于合规审计时分流统计。 |
| 上游决议引用 | DEV-MDM-001 V1.2 §8.3（延续 V1.1 §5.5） |
| 修订理由 | DM 层与 API 层在 errorType 上有耦合（审计行为区分）；DM 文档需指明数据模型对 errorType 的最小支撑，否则 API/UI 的 errorType 设计与审计模型脱节。 |

---

## 待评审决议项（架构组需先决议，决议后再决定是否落地修订）

### 决议项 #A — §8.3 ars.asset_market_id：是否补 `deleted_by` 字段？

| 字段 | 内容 |
|---|---|
| docx 章节 | §8.3 ars.asset_market_id |
| 修订类型 | （待评审）表结构 — 加字段 |
| V1.0 原文位置 | §8.3 DDL，字段列表至 `deleted_at TIMESTAMPTZ,` 即结束，无 `deleted_by` |
| V1.0 原文摘录 | `created_by BIGINT NOT NULL, updated_at ..., updated_by BIGINT NOT NULL, deleted_at TIMESTAMPTZ, CONSTRAINT uq_asset_market_id ...` —— 仅有 `deleted_at` 无 `deleted_by` |
| 备选方案 A（接受补字段）| 加 `deleted_by BIGINT,` + `CONSTRAINT fk_asset_market_id_deleted_by FOREIGN KEY (deleted_by) REFERENCES auth.user(user_id)`；与 §7.2 substance / §8.2 asset / §9.2 project 主表对齐。 |
| 备选方案 B（接受设计差异）| 保留 V1.0 现状（仅 deleted_at）；在 §8.3 表注释补一句"删除者通过 audit.audit_log.user_id（action='DELETE'）反查，子表 soft-delete 不冗余 deleted_by"。 |
| 上游决议引用 | DEV-MDM-001 V1.2 §6.2.3 |
| 评审决议建议 | 倾向方案 B（保留差异 + 加注释）：子表追溯通过 audit_log 已闭环，冗余字段维护成本高于收益。**待架构组拍板。** |

### 决议项 #B — §11.3 ref.asset_substance：是否补 `deleted_by` 字段（顺带 §11.4 ref.project_asset）？

| 字段 | 内容 |
|---|---|
| docx 章节 | §11.3 ref.asset_substance / §11.4 ref.project_asset |
| 修订类型 | （待评审）表结构 — 加字段 |
| V1.0 原文位置 | §11.3 DDL 字段至 `deleted_at TIMESTAMPTZ,` 结束；§11.4 同；但 §11.2 ref.project_substance 有 `deleted_by` |
| V1.0 原文摘录 | §11.3：`updated_by BIGINT NOT NULL, deleted_at TIMESTAMPTZ, CONSTRAINT pk_ref_asset_substance ...` ；§11.2 同位置有 `deleted_by BIGINT,` |
| 备选方案 A（统一补字段）| §11.3 / §11.4 各加 `deleted_by BIGINT,` + 对应 FK；ref 三表 soft-delete 模式完全统一。 |
| 备选方案 B（保留 §11.2 与 §11.3/§11.4 差异）| 维持现状；在 §11.1 设计原则备注"ref.project_substance 因含 relation_type 较丰富语义，保留 deleted_by；ref.asset_substance / ref.project_asset 为纯关联表，删除者走 audit_log 反查"。 |
| 上游决议引用 | DEV-MDM-001 V1.2 §6.5.4 / 附录 A |
| 评审决议建议 | 倾向方案 A（统一补）：ref 三表对外行为一致，避免实施侧记忆负担与未来对齐成本。**待架构组拍板。** |

---

## 可选项（架构组若认为属 API 文档范畴可跳过）

### 可选 #C — §15.3 关键约束清单：加「关键不可逆动作的双权限要求」一行

| 字段 | 内容 |
|---|---|
| docx 章节 | §15.3 关键约束清单 — 表格内 |
| 修订类型 | 新增表格行 |
| V1.0 原文位置 | §15.3 表格末行 `Optimistic lock｜version 字段 + 应用层比对｜substance, project, asset` 之后 |
| V1.0 原文摘录 | §15.3 6 行约束（PK / UQ on code / CHECK on enum / FK with audit / NOT NULL on key fields / Soft delete pattern / Optimistic lock），无 RBAC / 双权限项 |
| V1.1 修订内容 | 表格末尾追加一行：`RBAC 双权限｜关键不可逆动作（terminate / obsolete / merge / reject）要求"操作权限 + 签名权限"双校验｜substance:approve+sign / project:approve+sign / asset:update+sign` |
| 上游决议引用 | DEV-MDM-001 V1.2 §6.4.3 / §7.1.2 |
| 评审决议建议 | 倾向接受（RBAC 是数据模型完整性的一部分；与 §6.4 e_signature 闭环）；若架构组判定该项更适合放 ARCH-MDM-001 / DEV-MDM-001，本项可移出本清单。 |

---

## 修订统计

| 类型 | 计数 | 章节分布 |
|---|---|---|
| 函数 / 触发器修订 | 3（#1 / #2 / #3）| §6.5 |
| 表结构修订 | 2（#4 / #5）| §8（新增 §8.4）/ §9.5 |
| 业务规则 / 设计原则 | 1（#6）| §11.1 |
| 施工说明补充 | 3（#7 / #8 / #9）| §6.4 / §15.2 |
| 待决议（字段是否补）| 2（#A / #B）| §8.3 / §11.3 / §11.4 |
| 可选（RBAC 约束）| 1（#C）| §15.3 |
| **合计** | **12** | — |

---

## 评审记录

| 项目编号 | 决议（接受 / 拒绝 / 修改）| 决议人 | 日期 | 备注 |
|---|---|---|---|---|
| #1 |  |  |  |  |
| #2 |  |  |  |  |
| #3 |  |  |  |  |
| #4 |  |  |  |  |
| #5 |  |  |  |  |
| #6 |  |  |  |  |
| #7 |  |  |  |  |
| #8 |  |  |  |  |
| #9 |  |  |  |  |
| #A |  |  |  |  |
| #B |  |  |  |  |
| #C |  |  |  |  |

评审通过后，秘书按本清单在 `CMAB_MDM_Portal_数据模型设计文档_V1.0.docx` Word 修订模式下逐项落地，输出 V1.1.docx。

---

**附**：本清单仅覆盖 DM-MDM-001（数据模型）。DEV-MDM-001 V1.2 §7（架构）/ §8（API）/ §9（UI）的修订建议另立 ARCH-MDM-001 / API-MDM-001 / UI-MDM-001 同名修订清单。
