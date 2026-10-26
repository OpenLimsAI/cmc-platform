# OIDC 坏 URL 与原生登录恢复：TDD 记录

2026-10-26，ThinkpadT14-Le。本记录仅为隔离后端回归证据；真实浏览器 SSO、PM 创建关联、退出与异常场景由主验收报告分别记录。

## 实际 Red → Green

先新增 `backend/tests/test_oidc_recovery_urls.py`，再运行：

```text
docker exec -e LOGURU_LEVEL=WARNING -e APP_LOG_LEVEL=WARNING cmc-mdm-phase2-unit-backend \
  python scripts/run_phase2_tests.py tests/test_oidc_recovery_urls.py
```

修复前 ruff、mypy 通过，原 `scripts/run_tests.sh` 在新隔离 `cmab_test` 完整迁移到 `0068_pm_create_request` 后，实际结果为 `6 failed, 1 warning in 5.03s`，exit 1。失败都指向 `urlsplit` 的 `ValueError` 未转换为受控 OIDC 错误，导致坏 issuer/public 配置同时阻断配置查询和明确启用的原生恢复登录。未将前置 lint 或环境故障冒称为业务 red。

随后只改两处：`checked_url` 将 URL 解析纳入既有 `ValueError` → `OIDCError` 边界；原生 refresh cookie 路径解析失败时回退到原有窄路径 `/api/v1/auth`。合法 public 前缀仍使用 `/mdm/api/v1/auth`，没有放宽来源校验、身份验证或密码规则。

同一命令实际复跑为 `6 passed, 1 warning in 4.92s`，exit 0；之后将新文件纳入第二阶段 runner 默认测试集合。唯一 warning 是既有 passlib `crypt` 的 Python 3.13 弃用提示。

六项分别覆盖两个坏 URL 的受控异常、坏 issuer/public 时配置查询保留原生恢复，以及使用真实隔离 PostgreSQL 原生用户登录与正确 cookie 路径。测试只断言非秘密 cookie 属性，不保存或输出令牌；没有联网调用 Casdoor，也不是浏览器端到端验收。

## 完整回归

14:42 UTC 启动同容器 `python scripts/run_phase2_tests.py`，实际完成结果为 `238 passed, 1 warning in 109.29s (0:01:49)`，exit 0。前置 ruff、mypy 通过；完整迁移到 0068。范围包括 OIDC 协议/提供方/注销/映射与会话/端点/恢复、PM 创建与第一阶段关联，以及原生认证、密码/会话策略、签名、审计、PRS 和数据库就绪检查。这个数量是本阶段 runner 所选回归集合，不能扩大称为仓库全部测试或真实端到端通过。

运行环境是主任务为本阶段新建的 `cmc-mdm-phase2-unit-backend`，runner 只接受 `TEST_DB=cmab_test`、`TEST_DB_HOST=postgres`，底层仍使用项目原有 `scripts/run_tests.sh`。未操作真实 E2E 运行容器、账号、数据库、截图、PR 或原有开发数据。

## 本次已测文件快照

以下 SHA-256 在完整回归期间从宿主已测文件取得；最终验收版本须以主任务后续提交和完整来源清单为准。

|相对 `cmab-mdm-platform/` 的路径|SHA-256|
|---|---|
|`backend/app/domains/auth/oidc/config.py`|`5019c2543991ae1bead1a082b3f46dd2afd2c88c08bce0837ab1936c92ab7c2e`|
|`backend/app/api/v1/auth.py`|`2db320e3be5468225ba20637fdfbf96dfe64ececee09fd181773215064e83ad5`|
|`backend/tests/test_oidc_recovery_urls.py`|`13be8e3e685faa2f87dc8e75f15bf2b35fcfafb8288dcb40558315b15ba15bce`|
|`backend/scripts/run_phase2_tests.py`|`e5d8d0a78129cbfbcbe5635843f9f66bd4e39c51cfb0d796d119ace9f457876e`|
