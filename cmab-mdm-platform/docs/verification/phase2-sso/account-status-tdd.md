# Casdoor 本人账号状态核验：TDD 与配置边界

2026-10-26，ThinkpadT14-Le。本记录是后端自动回归，不替代真实 Casdoor 禁用、原有浏览器会话拒绝和恢复后的新登录验收。

## 发现与最小权限实现

本轮核实 Casdoor 3.152.0 的 introspection 对尚未到期令牌可继续返回 active，而不反映账号当前禁用/删除状态。MDM 在严格 introspection 通过后，使用该 MDM 应用原有短期用户令牌，只读 `GET /api/get-user`，参数固定为配置组织 `owner` 和已验证 subject 的 `userId`。不使用管理员密钥、不枚举组织用户、不调用会签发新令牌的 get-account，不读取或导入上游业务角色。

仅当响应为 status=ok、data 对象、id 与已验证 subject 精确一致、owner 与固定组织精确一致、两个状态字段 `isForbidden`/`isDeleted` 均为布尔 false 时，才继续承认会话。缺字段、空响应、主体/组织不符、非布尔 false，以及 HTTP 401/403/404 都拒绝；网络、超时、上游 5xx、坏 JSON 继续按现有 OIDC 不可用路径安全返回 503，不静默降级。

Casdoor AccountItems 可以将 Admin-only 状态字段过滤为 false，单看响应字段不足以证明状态可见。因此新增 `MDM_OIDC_ORGANIZATION`（默认空）和 `MDM_OIDC_ACCOUNT_STATUS_VISIBLE`（默认 false）。启用 SSO 需显式固定组织并确认可见性；组织只接受 1–100 个 ASCII 字母、数字、下划线、点或连字符。可见性开关只是部署前提确认，不能自动证明权限正确。部署前必须核实这两个字段对 Self/Public 可见，并用真实禁用动作确认旧会话被拒绝；不要求放开编辑权限或增加管理身份。条件不满足时，SSO 关闭，明确启用的原生恢复仍可用。

## 实际 TDD

先新增旧令牌 active、账号 isForbidden/isDeleted 为 true 的两个测试，使用专用 `cmc-mdm-phase2-unit-backend`：

```text
python scripts/run_phase2_tests.py \
  tests/test_oidc_provider.py::test_active_old_token_cannot_keep_disabled_provider_account_alive

2 failed in 1.76s，exit 1，实际断言 True is False
```

继续先补完整状态契约和配置门槛测试，再实现核验逻辑；组合修复前 `26 failed, 15 passed, 1 warning in 7.17s`，exit 1。两轮前置 ruff/mypy 均通过，失败不是安装、lint 或环境故障。

实现后同组合命令 `python scripts/run_phase2_tests.py tests/test_oidc_provider.py tests/test_oidc_recovery_urls.py` 实际为 `41 passed, 1 warning in 5.95s`，exit 0。HTTP 边界使用明确 MockTransport；原生登录恢复使用隔离 PostgreSQL。未把这些替身当真实端到端证据。

随后扩充现有持久化会话回归：确认禁用造成的本地撤销在上游恢复后仍不复活旧 cookie，新登录可用；临时上游故障返回 503、恢复后可继续未被撤销的会话。这些是既有会话语义的补充回归，没有为其伪造独立 red。

## 完整回归与范围

14:59 UTC 前完整 `python scripts/run_phase2_tests.py` 实际完成：`268 passed, 1 warning in 100.97s (0:01:40)`，exit 0；前置 ruff、mypy 也通过。这是本阶段所选后端回归集合，不能扩大称整个仓库或真实浏览器端到端验收通过。

始终使用项目原 `scripts/run_tests.sh`，只重建新隔离 `cmab_test` 并迁移 0068；未操作本轮真实 E2E 容器、组织配置、截图、账号、原有数据库或生产服务。唯一已有 warning 为 passlib `crypt` 弃用提示。已测源码与模板的本次快照见 [account-status-source-hashes.json](account-status-source-hashes.json)，最终交付须使用主任务的最终提交和完整验收来源清单。
