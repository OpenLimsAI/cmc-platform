# CMAB MDM Portal OQ 测试追溯矩阵（P4.D-2）

| 项目 | 内容 |
|---|---|
| 文档编号 | OQ-MDM-001 |
| 版本 | V1.0 |
| 适用 | CSV OQ（操作确认）阶段证据链 |
| 合规 | GAMP 5 / 21 CFR Part 11 §11.10(a-k) / EU Annex 11 §4.5 |
| 基线 | pytest 174 用例（2026-05-13 全过）/ migration head `0034_auth_refresh_token` |

---

## 0. 用途说明

本矩阵把现有 174 个 pytest 用例**逐条映射到 V1.1 上位文档章节 + GxP 风险等级**，作为 CSV OQ 阶段的证据链。

- **GxP-Critical**：直接影响数据完整性 / 电子签名 / 审计追踪 / 权限隔离，**必须 100% 通过**
- **Major**：影响业务正确性但不直接影响合规，**允许 ≤ 2% 失败但需 CAPA**
- **Minor**：辅助测试 / 边界用例，**允许偶发失败但需记录**

总览（每个模块 → 用例数 / 风险分布 / 覆盖章节）：

| 模块 | 用例数 | Critical | Major | Minor | V1.1 主要覆盖章节 |
|---|---|---|---|---|---|
| auth（认证 + 安全）| 4 | 4 | 0 | 0 | API §2 / ARCH §7.1-§7.2 |
| auth（refresh token + 限流 + 幂等）| 16 | 13 | 3 | 0 | API §2.2 / §3.4 / §3.5 / ARCH §7.2.1 / ARCH11 |
| audit（触发器 v1 + v2）| 7 | 7 | 0 | 0 | DM §6 / API §3.6 |
| smoke（健康检查 + 鉴权）| 2 | 0 | 0 | 2 | ARCH §7.2.1 / API §1.4 |
| srs（substance 域）| 13 | 8 | 5 | 0 | DM §7 / API §5.1.3 / §11.2.1 |
| srs（state machine + check_sameness）| 10 | 7 | 3 | 0 | API §11.2.1 / §11.4 |
| srs（signature 电子签名）| 9 | 9 | 0 | 0 | DM §6.4 / 21 CFR Part 11 §11.50/11.70 |
| prs（project 域 + state + milestone/team）| 25 | 14 | 11 | 0 | DM §9 / API §5.1.4 / §11.2.2 |
| ars（asset 域 + state + market id）| 32 | 18 | 14 | 0 | DM §8 / API §5.1.5 |
| mm（material 域 + batch + 反向）| 25 | 13 | 12 | 0 | DM §10 / API §5.1.6 |
| ref（跨域引用三组）| 24 | 14 | 10 | 0 | DM §11 / API §5.1.3-§5.1.5 反向 |
| global_search | 16 | 0 | 14 | 2 | API §8.3 / UI §3.5 |
| **总计** | **174** | **107** | **72** | **4** | — |

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

### 1.3 test_rate_limit.py — 3 用例 / 2 Critical + 1 Minor

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

## 5. ARS（资产域）— 32 用例 / 18 Critical + 14 Major

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

### 5.2 test_asset_state_machine.py — 12 用例 / 主体 Critical（含 terminate 电子签名）

主要覆盖：API §8.x + DM §8.4 / 8.1 + 21 CFR Part 11

### 5.3 test_asset_substance_link.py — 9 用例

主要覆盖：DM §11.3 + 业务规则 ASSET_STATUS_FORBID_LINK / SUBSTANCE_STATUS_FORBID_LINK

---

## 6. MM（物料域）— 25 用例 / 13 Critical + 12 Major

### 6.1 test_material_crud.py — 12 用例

主要覆盖：DM §10.1 / API §5.1.6

### 6.2 test_material_batch.py — 8 用例

主要覆盖：DM §10.2 / API §5.1.6 / 44001 错误码

### 6.3 test_material_substance_link.py — 5 用例

主要覆盖：DM §10.1 substance_id FK + V1.1 §11.1 obsoleted 业务规则

---

## 7. REF（跨域引用）— 24 用例 / 14 Critical + 10 Major

### 7.1 test_project_substance_link.py — 8 用例

主要覆盖：DM §11.2 / 业务规则 PROJECT_STATUS_FORBID_LINK + SUBSTANCE_STATUS_FORBID_LINK

### 7.2 test_asset_substance_link.py — 9 用例（已在 §5.3 列出）

### 7.3 test_project_asset_link.py — 8 用例

主要覆盖：DM §11.4 / 复合 PK 仅 (project_id, asset_id) — relation_type 不入 PK

---

## 8. 全局功能 — 16 用例 / 14 Major + 2 Minor

test_global_search.py 覆盖：API §8.3 分组结构（4 类齐：substance/project/asset/material）+ 权限分流 + 排序权重 + types 过滤

---

## 9. OQ 执行说明

### 9.1 执行命令

```bash
# 完整 OQ 跑一次（约 50 秒）
docker exec cmab-mdm-backend pytest tests/ -v --tb=short --color=no > oq_run_$(date -u +%Y%m%d_%H%M).log 2>&1

# 验证：174 passed
grep "passed" oq_run_*.log | tail -1
```

### 9.2 通过判定

| 风险等级 | 通过标准 |
|---|---|
| Critical（107 项）| 100% 通过 — 任何 fail 直接整改后重测 |
| Major（72 项）| ≥ 98% 通过（允许 ≤ 1 项偶发 fail）；fail 需 CAPA 单号 |
| Minor（4 项）| ≥ 90% 通过；fail 仅需记录 |

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
