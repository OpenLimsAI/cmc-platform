# 全局注销成功后置条件 TDD

2026-10-26，真实 Casdoor 3.152.0 / PostgreSQL 发现 `/api/sso-logout` 返回 `status=ok`，但所有应用令牌未失效，旧门户仍能执行真实身份刷新。官方修复为 [Casdoor #5740 / edfbb93](https://github.com/casdoor/casdoor/commit/edfbb9323be4e6ac3a507f08d49fae025431c52f)，首次发布在 [v3.154.4](https://github.com/casdoor/casdoor/releases/tag/v3.154.4)。原版本与新版本必须分别记录，不能手工改 token 表代替产品退出。

MDM 对远端 transport success 的判断也需要防御：

- 2026-10-26 实际运行 `run_phase1_tests.py tests/test_oidc_provider.py -k global_logout_requires`：5 failed。有效成功路径没有执行任何 introspection；四类失败均未拒绝。
- 实现当前本人 token 的明确 active/client_id/sub 前置核验及注销后 `active is False` 后置条件；未确认时抛受控错误，由原 logout API 明确告知局部退出与统一退出未确认的区别，不宣称全局成功。
- 实际运行 `run_phase2_tests.py tests/test_oidc_provider.py`：31 passed，ruff/mypy 前置通过。覆盖远端仍 active、畸形结果、原会话已失效、错误受众以及有效撤销。

这些用例采用合成 token 名称与 HTTP 传输替身，是边界单测；真正跨应用退出仍要求官方修复版本上完成浏览器、应用接口与数据库断言。没有从浏览器/数据库提取令牌，没有将 token 放进 URL，也未增加管理员权限。
