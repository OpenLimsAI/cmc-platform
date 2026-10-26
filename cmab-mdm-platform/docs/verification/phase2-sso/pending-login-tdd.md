# 退出与原生登录后的迟到 OIDC 回调：TDD 记录

2026-10-26，ThinkpadT14-Le。范围仅 MDM 后端当前浏览器的登录事务取消；不修改身份提供方、上游注销契约、UI 或运行态。

## 实际 Red → Green

先新增参数化测试，覆盖本地 OIDC 退出、统一退出、成功原生登录，分别发生于未回调、令牌交换进行中、回调已建会话但浏览器尚未收到响应三个阶段，共九项。

首轮测试有六项因测试自身使用了错误请求字段别名而失败，另三项暴露真实原生登录迟到回调问题；没有将这六项夹具错误当作业务 red。修正别名后，在未修改实现时重跑：

```text
docker exec -e LOGURU_LEVEL=WARNING -e APP_LOG_LEVEL=WARNING cmc-mdm-phase2-unit-backend \
  python scripts/run_phase2_tests.py \
  tests/test_oidc_sessions.py::test_browser_logout_or_native_login_cancels_its_pending_callback

9 failed, 1 warning in 8.56s，exit 1
```

九项均实际显示旧流程仍可建立或使用新的 SSO 会话，没有按预期抛出状态或会话失效错误。两个真实隔离 PostgreSQL 会话分别模拟回调请求与退出/登录请求，令牌交换用显式边界替身和受控停点；不冒充真实浏览器端到端。

随后实现并复跑同一命令：`9 passed, 1 warning in 8.43s`，exit 0；前置 ruff/mypy 通过。中途一次局部 import 排序失败已手工修正，没有使用自动格式化、降级 lint 或将其记为行为 red。

## 取消边界

原实现会在调用身份提供方之前删除登录事务，因此交换进行中已没有可被退出取消的记录。新实现通过短行锁领取事务，在加密 payload 标记 claimed 后提交，保持原五分钟到期；网络调用期间不持数据库锁。令牌交换返回后再次锁定并检查该事务仍存在、未过期、未完成，才进入最终提交。

会话建立、旧会话撤销与短期 completed_session_id 回执原子提交。回执只新增会话哈希 ID，不保存访问令牌；仍受原登录事务有效期约束。当前浏览器的 LOGIN cookie 可精确取消这条事务，亦能撤销刚完成但响应尚未送达浏览器的会话。它不按用户或组织批量撤销其他浏览器的无关联登录事务。

本地/统一 OIDC 退出及成功原生登录都清除 LOGIN cookie 并执行上述取消；原生恢复不依赖身份提供方可用性。原生登录仍需真实本地密码，失败登录不会取消当前流程。统一退出的上游实际效果与失败警告保持原契约，本记录不扩称全局注销的额外能力。

九项测试还分别确认 cookie 删除属性、当前事务被删除，以及另一浏览器独立事务仍能完成。原有错误 state/cookie 不消费他人事务、同一回调不能二次消费及 nonce 协议检查随完整回归执行。

## 完整回归

完整第二阶段 `python scripts/run_phase2_tests.py` 实际结果：`277 passed, 1 warning in 105.45s (0:01:45)`，exit 0；前置 ruff、mypy 均通过。该数量是本阶段所选后端回归，不是全仓测试或真实浏览器端到端验收。

底层仍为项目原 `scripts/run_tests.sh`，只重建本阶段专用 `cmab_test` 并迁移 0068。未操作真实 E2E 实例、凭据、账号、截图或 PR。唯一已有 warning 为 passlib `crypt` 弃用提示。已测文件快照见 [pending-login-source-hashes.json](pending-login-source-hashes.json)；最终版本以主任务的合并提交与完整验收清单为准。
