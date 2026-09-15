# CMAB MDM Portal OQ 测试追溯矩阵（P4.D-2）

| 项目 | 内容 |
|---|---|
| 文档编号 | OQ-MDM-001 |
| 版本 | V1.0 |
| 适用 | CSV OQ（操作确认）阶段证据链 |
| 合规 | GAMP 5 / 21 CFR Part 11 §11.10(a-k) / EU Annex 11 §4.5 |
| 当前自动化基线 | `make test-be` 于 2026-09-15：共 **409 项**，设备状态相关项通过；全量运行仍有 1 项既有账户管理用例偶发失败（两次失败点不同，待治理）；migration head `0060_eqp_device_status` |
| 已完成追溯映射 | 本矩阵 §1-§8 仍只映射 2026-05-13 的 174 用例基线 |

---

## 0. 用途说明

本矩阵把 2026-05-13 基线的 174 个 pytest 用例**逐条映射到 V1.1 上位文档章节 + GxP 风险等级**，作为 CSV OQ 阶段的证据链。

> ⚠️ **缺口说明（2026-09-15 更新）**：自动化套件现有 409 个用例，但本矩阵仍只逐条映射其中 174 个。
> `0045`—`0060` 引入的软删唯一约束修复、SMP V2.1 项目治理、靶点域、物质编码调整、
> 滑动会话、部门管理员、审计索引、设备治理和设备状态收口 MDM 等测试尚未完成 OQ 风险定级与需求追溯。
> 因此自动化结果只表示当前代码回归状态，**不等于 OQ 证据链已经完整**；正式 OQ 前必须补齐剩余 235 个用例的映射，并先治理账户管理用例的偶发失败。

- **GxP-Critical**：直接影响数据完整性 / 电子签名 / 审计追踪 / 权限隔离，**必须 100% 通过**
- **Major**：影响业务正确性但不直接影响合规，**允许 ≤ 2% 失败但需 CAPA**
- **Minor**：辅助测试 / 边界用例，**允许偶发失败但需记录**

总览（每个模块 → 用例数 / 风险分布 / 覆盖章节）：

| 模块 | 用例数 | Critical | Major | Minor | V1.1 主要覆盖章节 |
|---|---|---|---|---|---|
| auth（认证 + 安全）| 4 | 4 | 0 | 0 | API §2 / ARCH §7.1-§7.2 |
| auth（refresh token + 限流 + 幂等）| 15 | 13 | 1 | 1 | API §2.2 / §3.4 / §3.5 / ARCH §7.2.1 / ARCH11 |
| audit（触发器 v1 + v2）| 7 | 7 | 0 | 0 | DM §6 / API §3.6 |
| smoke（健康检查 + 鉴权）| 2 | 0 | 0 | 2 | ARCH §7.2.1 / API §1.4 |
| srs（substance 域）| 13 | 8 | 5 | 0 | DM §7 / API §5.1.3 / §11.2.1 |
| srs（state machine + check_sameness）| 10 | 7 | 3 | 0 | API §11.2.1 / §11.4 |
| srs（signature 电子签名）| 9 | 9 | 0 | 0 | DM §6.4 / 21 CFR Part 11 §11.50/11.70 |
| prs（project 域 + state + milestone/team）| 25 | 14 | 11 | 0 | DM §9 / API §5.1.4 / §11.2.2 |
| ars（asset 域 + state + market id）| 23 | 14 | 9 | 0 | DM §8 / API §5.1.5 |
| mm（material 域 + batch + 反向）| 25 | 13 | 12 | 0 | DM §10 / API §5.1.6 |
| ref（跨域引用三组）| 25 | 12 | 13 | 0 | DM §11 / API §5.1.3-§5.1.5 反向 |
| global_search | 16 | 0 | 14 | 2 | API §8.3 / UI §3.5 |
| **总计** | **174** | **101** | **68** | **5** | — |

> 📌 **2026-06-05 对账勘误**：原版总览明细行加总 183 ≠ 总计 174。根因三处：① `test_asset_substance_link.py` 9 用例在 ars 行与 ref 行**双重计数**（§7.2 原注"已在 §5.3 列出"）——现归属 ref（跨域引用表）单边计数；② auth refresh 行 16 实为 15（6+3+6）；③ ref 行 24 实为 25（8+9+8）。明细行与总计现以 git 基线（commit f477d86，2026-05-13，pytest 174 passed）逐文件清点为准；风险分布按 §1-§8 逐条表重新加总（§5.2/§5.3/§7 逐条表为本次勘误补全）。

---

## 1. auth（认证与安全）

### 1.1 test_auth_security.py — 4 用例 / 全 Critical

| 用例 | V1.1 章节 | 风险 | 验证点 |
|---|---|---|---|
| test_change_password_invalidates_old_tokens | API §2.2 / ARCH §7.1 | Critical | 改密后旧 access_token 立即失效（password_changed_at vs iat 整数秒截断） |
| test_lockout_after_max_failed_attempts | API §2.2 / DM §4.6 | Critical | 5 次失败后账户锁定 30min（22 CFR Part 11 §11.300 标识码生命周期）|
| test_auto_unlock_after_duration | API §2.2 / DM §4.6 | Critical | 锁定时长后自动解锁，failed_login_count 清零 |
| test_signature_failure_persists_audit_independently | DM §6.4 / 旁路 session | Critical | 签名失败计数走 AsyncSessionLocal 独立 commit，主事务 rollback 不丢 |

### 1.2 test_refresh_token.py — 6 用例 / Critical 全

| 用例 | V1.1 章节 | 风险 | 验证点 |
|---|---|---|---|
| test_login_sets_refresh_cookie | API §2.2 | Critical | HttpOnly Cookie 设置正确（Path=/api/v1/auth, SameSite=Strict）|
| test_refresh_returns_new_access_and_rotates_cookie | API §2.2 + ARCH §7.2.1 | Critical | 每次 refresh 旋转 — 新 access + 新 refresh cookie |
| test_refresh_old_token_rejected_after_rotation | ARCH §7.2.1（防 refresh 重放）| Critical | 旧 jti 已 revoke，重放抛 40103 token_invalid |
| test_refresh_without_cookie_returns_401 | API §2.2 / API §4 | Critical | 缺 cookie → 40104 token_missing |
| test_refresh_with_bogus_cookie_rejected | API §2.2 | Critical | 伪造 cookie → 40103 token_invalid |
| test_logout_revokes_and_clears_cookie | API §2.2 | Critical | logout 撤销 + 清 cookie + 后续 refresh 401 |

### 1.3 test_rate_limit.py — 3 用例 / 1 Critical + 1 Major + 1 Minor

| 用例 | V1.1 章节 | 风险 | 验证点 |
|---|---|---|---|
| test_response_carries_rate_limit_headers | API §3.5 | Major | X-RateLimit-Limit/Remaining/Reset 三 header 必出现 |
| test_login_rate_limit_hit_returns_42901 | API §3.5 / ARCH11 | Critical | 登录端点带 X-RateLimit-* + Retry-After |
| test_metrics_endpoint_excluded_from_rate_limit | ARCH §7.2 / 监控 | Minor | /metrics 不被限流（Prometheus scrape 1/s）|

### 1.4 test_idempotency.py — 6 用例 / Critical 全

| 用例 | V1.1 章节 | 风险 | 验证点 |
|---|---|---|---|
| test_material_idem_same_key_same_body_returns_cached | API §3.4 | Critical | 同 key + 同 body 返回缓存（不创建第二份）|
| test_material_idem_same_key_different_body_409 | API §3.4 / §4.3 | Critical | 同 key + 不同 body → 40905 duplicate_request |
| test_material_idem_no_key_normal_path | API §3.4 | Critical | 无 key 端点正常工作 |
| test_material_idem_invalid_key_400 | API §3.4 / §4.1 | Critical | 非 UUID → 40003 invalid_value |
| test_substance_idem_same_key_same_body | API §3.4 | Critical | 跨域统一行为 |
| test_idem_keys_scoped_per_user | API §3.4 + ARCH §7.1 | Critical | per-user 命名空间隔离 |

---

## 2. audit（审计触发器）

### 2.1 test_audit_trigger.py — 4 用例 / Critical 全

| 用例 | V1.1 章节 | 风险 | 验证点 |
|---|---|---|---|
| test_create_writes_audit_log | DM §6.2 + §6.5 | Critical | INSERT 触发器写 audit_log + change_history 全量字段 |
| test_update_writes_change_history | DM §6.3 + §6.5 | Critical | UPDATE 写变更前后值（旧值/新值/字段名）|
| test_delete_writes_audit_log | DM §6.2 | Critical | DELETE 触发器写 action=DELETE |
| test_change_reason_session_var | DM §6.5 / GxP 数据完整性 | Critical | service 写 set_config('app.change_reason') → audit.reason 列回填 |

### 2.2 test_audit_trigger_v2.py — 3 用例 / Critical 全

| 用例 | V1.1 章节 | 风险 | 验证点 |
|---|---|---|---|
| test_parent_ref_back_fill | DM §6.5 v2 第 3 参 | Critical | 子表（market_id / batch / link）audit_log.entity_code 自动回填主表 code |
| test_entity_code_in_audit_log | DM §6.5 | Critical | entity_code 列写入（不只 entity_id）|
| test_change_history_field_name_correctness | DM §6.3 | Critical | field_name 列与表字段名严格一致 |

---

## 3. SRS（物质域）

### 3.1 test_substance_crud.py — 13 用例 / 8 Critical + 5 Major

主要覆盖：DM §7.2-§7.6 / API §5.1.3 / §11.2.1

| 用例 | V1.1 章节 | 风险 |
|---|---|---|
| test_create_substance_returns_code | DM §7.2 + meta.fn_next_code | Critical |
| test_get_substance_after_create | API §6.2.4 | Major |
| test_update_increments_version_exactly_one | DM §7.2 触发器 / 乐观锁 | Critical |
| test_optimistic_lock_conflict | API §11.3.1 / 40904 | Critical |
| test_duplicate_internal_code_rejected | DM §7.2 UNIQUE | Critical |
| test_soft_delete_excludes_from_list | DM §1.1 soft-delete | Major |
| test_create_with_extended_protein_fields | DM §7.3 / Batch B | Major |
| test_xref_effective_expiry_dates | DM §7.6 / Batch B | Major |
| test_put_protein_independent_endpoint | API §5.1.3 + Batch H API13:A | Critical |
| test_put_adc_independent_endpoint | API §5.1.3 + Batch H API13:A | Critical |
| test_lookups_endpoint | API §5.1.7 + Batch H API11:B | Major |
| test_system_info_endpoint | API §5.1.7 + Batch H API11:B | Major |
| test_soft_delete_requires_reason | API §11.3.1 / GxP | Critical |

### 3.2 test_state_machine.py — 5 用例 / 4 Critical + 1 Major

主要覆盖：API §11.2.1（substance 状态机 5 转移）+ DM §7.7（status_history）

| 用例 | V1.1 章节 | 风险 |
|---|---|---|
| test_full_lifecycle | API §11.2.1 全链路 draft→registered→active→deprecated→obsoleted | Critical |
| test_invalid_transition_rejected | API §11.2.1 / 42201 | Critical |
| test_reason_too_short | API §11.3.1 / GxP comment 必填 | Critical |
| test_restrict_then_deprecate | API §11.2.1 分支路径 | Major |
| test_status_history_recorded | DM §7.7 / GxP 不可篡改历史 | Critical |

### 3.3 test_check_sameness.py — 5 用例 / 3 Critical + 2 Major

主要覆盖：API §11.4（同一性判定）/ DM §7.3 sequence_hash 索引

| 用例 | V1.1 章节 | 风险 |
|---|---|---|
| test_sameness_by_internal_code | API §11.4 | Critical |
| test_sameness_by_protein_sequence | DM §7.3 sequence_hash_hc/lc | Critical |
| test_sameness_normalization_strips_invalid_chars | API §11.4 | Major |
| test_no_match_returns_empty | API §11.4 | Major |
| test_sameness_excludes_deleted | DM §7 soft-delete | Critical |

### 3.4 test_signature.py — 9 用例 / Critical 全

主要覆盖：DM §6.4 e_signature + 21 CFR Part 11 §11.50 / §11.70

| 用例 | V1.1 章节 | 风险 |
|---|---|---|
| test_approve_without_password_rejected | API §6.5 嵌套 signature | Critical |
| test_approve_wrong_password_rejected | DM §6.4 / 40106 | Critical |
| test_approve_correct_password_signs_and_transitions | 21 CFR Part 11 §11.70 数字签名 | Critical |
| test_multiple_signatures_independent | DM §6.4 SHA-256 双哈希 | Critical |
| test_restrict_does_not_require_signature | API §6.5 / §8.x 状态机分级 | Critical |
| test_sign_permission_required | DM §4 / 21 CFR Part 11 §11.10(g) | Critical |
| test_project_approve_signature_flow | DM §9 + §6.4 | Critical |
| test_signature_reason_independent_from_comment | Batch G1.A / 21 CFR Part 11 §11.50(a)(4) | Critical |
| test_project_start_does_not_require_signature | API §11.2.2 状态机分级 | Critical |

---

## 4. PRS（项目域）— 25 用例 / 14 Critical + 11 Major

### 4.1 test_project_crud.py — 11 用例

主要覆盖：DM §9 / API §5.1.4

| 用例 | 风险 |
|---|---|
| test_create_project_returns_code | Critical |
| test_get_project_after_create | Major |
| test_update_increments_version_exactly_one | Critical |
| test_optimistic_lock_conflict | Critical |
| test_duplicate_project_name_rejected | Critical |
| test_soft_delete_excludes_from_list | Major |
| test_filters_by_type_and_phase | Major |
| test_filters_by_owner_and_status | Major |
| test_audit_log_entity_code | Critical |
| test_readonly_cannot_create_project | Critical |
| test_create_with_full_brief_fields | Major |

### 4.2 test_project_state_machine.py — 6 用例

主要覆盖：API §11.2.2 + DM §9.5

| 用例 | 风险 |
|---|---|
| test_full_lifecycle | Critical |
| test_invalid_transition_rejected | Critical |
| test_reason_too_short | Critical |
| test_status_history_recorded | Critical |
| test_state_change_requires_approve_permission | Critical |
| test_terminate_requires_signature | Critical |

### 4.3 test_project_milestone_team.py — 8 用例

主要覆盖：DM §9.3 + §9.4

| 用例 | 风险 |
|---|---|
| test_milestone_crud | Major |
| test_team_crud | Major |
| test_milestone_status_independent | Major |
| test_team_unique_after_left | Major（H1:P3:A）|
| test_audit_parent_ref_to_project | Critical |
| test_milestone_dates_validation | Major |
| test_team_role_required | Major |
| test_milestone_type_check | Major |

---

## 5. ARS（资产域）— 23 用例 / 14 Critical + 9 Major

### 5.1 test_asset_crud.py — 11 用例

| 用例 | 风险 |
|---|---|
| test_create_asset_returns_code | Critical |
| test_get_asset_after_create | Major |
| test_list_assets_filters | Major |
| test_update_asset_version_and_phase_change | Critical |
| test_update_asset_optimistic_lock | Critical |
| test_invalid_asset_type_rejected | Major |
| test_invalid_phase_rejected_by_check | Major |
| test_soft_delete_excludes_from_list | Major |
| test_soft_delete_requires_reason | Critical |
| test_asset_audit_log_entity_code | Critical |
| test_readonly_cannot_create_asset | Critical |

### 5.2 test_asset_state_machine.py — 12 用例 / 8 Critical + 4 Major

主要覆盖：API §8.x + DM §8.4 / 8.1 + 21 CFR Part 11

| 用例 | 风险 |
|---|---|
| test_hold_resume_roundtrip | Major |
| test_terminate_requires_signature | Critical |
| test_terminate_wrong_password_rejected | Critical |
| test_terminate_correct_password_signs_and_transitions | Critical |
| test_terminate_from_on_hold | Major |
| test_resume_from_active_rejected | Critical |
| test_status_history_recorded | Critical |
| test_asset_not_found_returns_40404 | Major |
| test_terminate_requires_sign_permission | Critical |
| test_market_id_crud_roundtrip | Major |
| test_market_id_duplicate_rejected | Critical |
| test_market_id_audit_inherits_asset_code | Critical |

> 注：`test_asset_substance_link.py`（9 用例）属跨域引用表 `ref.asset_substance`，归 §7.2 计数（2026-06-05 勘误前曾在本节重复计数）。

---

## 6. MM（物料域）— 25 用例 / 13 Critical + 12 Major

### 6.1 test_material_crud.py — 12 用例

主要覆盖：DM §10.1 / API §5.1.6

### 6.2 test_material_batch.py — 8 用例

主要覆盖：DM §10.2 / API §5.1.6 / 44001 错误码

### 6.3 test_material_substance_link.py — 5 用例

主要覆盖：DM §10.1 substance_id FK + V1.1 §11.1 obsoleted 业务规则

---

## 7. REF（跨域引用）— 25 用例 / 12 Critical + 13 Major

### 7.1 test_project_substance_link.py — 8 用例 / 4 Critical + 4 Major

主要覆盖：DM §11.2 / 业务规则 PROJECT_STATUS_FORBID_LINK + SUBSTANCE_STATUS_FORBID_LINK

| 用例 | 风险 |
|---|---|
| test_link_unlink_roundtrip | Major |
| test_duplicate_active_relation_rejected | Critical |
| test_different_relation_types_can_coexist | Major |
| test_relink_after_unlink_restores_record | Major |
| test_invalid_relation_type_rejected | Major |
| test_link_obsoleted_substance_rejected | Critical |
| test_link_terminated_project_rejected | Critical |
| test_link_audit_inherits_project_code | Critical |

### 7.2 test_asset_substance_link.py — 9 用例 / 4 Critical + 5 Major

主要覆盖：DM §11.3 + 业务规则 ASSET_STATUS_FORBID_LINK / SUBSTANCE_STATUS_FORBID_LINK（2026-06-05 勘误：自 §5.3 移入本节，消除双重计数）

| 用例 | 风险 |
|---|---|
| test_link_unlink_roundtrip | Major |
| test_duplicate_active_role_rejected | Critical |
| test_different_component_roles_coexist | Major |
| test_relink_after_unlink | Major |
| test_invalid_component_role_rejected | Major |
| test_terminated_asset_forbids_new_link | Critical |
| test_obsoleted_substance_forbids_new_link | Critical |
| test_unlinked_record_exposes_deleted_by | Major |
| test_link_audit_inherits_asset_code | Critical |

### 7.3 test_project_asset_link.py — 8 用例 / 4 Critical + 4 Major

主要覆盖：DM §11.4 / 复合 PK 仅 (project_id, asset_id) — relation_type 不入 PK

| 用例 | 风险 |
|---|---|
| test_link_unlink_roundtrip_from_project | Major |
| test_link_from_asset_side | Major |
| test_unlink_from_asset_side | Major |
| test_duplicate_active_pair_rejected | Critical |
| test_relink_after_unlink | Major |
| test_terminated_asset_forbids_link_from_both_sides | Critical |
| test_terminated_project_forbids_link_from_both_sides | Critical |
| test_link_audit_inherits_project_code | Critical |

---

## 8. 全局功能 — 16 用例 / 14 Major + 2 Minor

test_global_search.py 覆盖：API §8.3 分组结构（4 类齐：substance/project/asset/material）+ 权限分流 + 排序权重 + types 过滤

---

## 9. OQ 执行说明

### 9.1 执行命令

```bash
# 从项目根目录运行；脚本会重建独立 cmab_test、迁移到 head、启动 :8001 测试服务
make test-be 2>&1 | tee oq_run_$(date -u +%Y%m%d_%H%M).log

# 当前参考结果：409 项；设备状态相关项通过，全量有 1 项既有账户管理用例偶发失败（2026-09-15）
grep "passed" oq_run_*.log | tail -1
```

禁止在后端容器直接执行 `pytest` 或运行 `make test-be-dev`；两者可能沿用开发库连接，
无法提供与真实数据隔离的 OQ 证据。

### 9.2 通过判定

| 风险等级 | 通过标准 |
|---|---|
| Critical（101 项）| 100% 通过 — 任何 fail 直接整改后重测 |
| Major（68 项）| ≥ 98% 通过（允许 ≤ 1 项偶发 fail）；fail 需 CAPA 单号 |
| Minor（5 项）| ≥ 90% 通过；fail 仅需记录 |

### 9.3 失败处置

- Critical 测试失败 → 整改 + 重跑 + 偏差报告
- Major 测试失败但单跑通过（test_optimistic_lock_conflict 等历史 flaky 项）→ 在备注栏标 `已知 flaky / 单跑通过 / 重跑 2 次通过`；超过 3 次 fail 视为偏差
- Minor 测试失败 → 仅记录在 OQ 报告附件

### 9.4 已知 flaky 项

| 用例 | 现象 | 根因 | 处置 |
|---|---|---|---|
| test_optimistic_lock_conflict | 全套跑偶尔 fail，单跑过 | 测试数据共享 dev DB / fixture 顺序 | 重跑 2-3 次确认；OQ 期间允许 |
| test_soft_delete_excludes_from_list | 同上 | 同上 | 同上 |
| test_change_password_invalidates_old_tokens | iat 整数秒比较 timing | `await asyncio.sleep(1.1)` 偶尔不够 | 增大 sleep 或单跑通过即视为 PASS |

---

## 10. 签字确认

| 角色 | 姓名 | 签字 | 日期 |
|---|---|---|---|
| 测试执行 | | | |
| QA 复核 | | | |
| CSV 验证工程师 | | | |

**结论**：☐ Critical 100% PASS + Major ≥ 98% PASS + Minor ≥ 90% PASS，进入 PQ；☐ 存在偏差，CAPA 单号 _______
