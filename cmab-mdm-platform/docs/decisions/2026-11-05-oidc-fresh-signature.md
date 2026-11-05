# 新鲜统一身份认证的签名边界

本地候选使用 `MDM_SIGNATURE_MODE=oidc_fresh`，将签名密码验证留在身份服务页面。MDM 不收取或保存该密码，不复用普通登录会话作为签名证明。默认仍为 `local_password`；正式开启、客户端与密钥配置是独立操作。

每个挑战绑定服务端会话、issuer+subject、既有数字 user_id、独立签名 audience、业务实体及内容哈希、签名意图和短期有效期。授权码使用 PKCE/state/nonce，验证签名、issuer/audience、有效期、auth_time 和同一主体；回调消息还验证 origin/source/state。业务事务消费一次性挑战，取消、过期、重放、换人及内容变化均不能继续签署。

0069 仅增加 `auth.oidc_signature_challenge`，不删除旧口令字段、历史用户ID、旧签名或审计。fresh 模式不再受旧初始化签名口令强制改密门槛阻断；兼容模式保留原语义。有任何挑战证据时 downgrade 主动拒绝删除表，回退需保留证据或恢复经过验证的备份。

中文密码单字段使用官方客户端展示设置：隐藏 Username/Logo/Languages，保留可见 Password 和验证按钮，禁用自动登录；`Forgot password?` 保留隐藏项并明确 `Auto sign in - False`，避免官方默认开启记住登录。MDM 使用当前可信身份生成 login_hint 并仍校验回调主体，隐藏用户名本身不构成安全绑定。临时合成 fixture 的纯配置函数在 `backend/scripts/e2e_signature_form.py`，不会更改其他客户端、grant、受众、权限或凭据，不是正式组织的自动配置工具。

本轮有两条本人实际输入测试密码后的业务签署证据，但没有全无人值守签署或输入时截图。受控浏览器文档曾暂停，未强制放行；工具拒绝不能靠换工具绕过。

已知审计缺口：新签名的 `audit_log_id` 仍可为空，基线同样如此。状态历史签名外键和挑战可追溯不等于直接 SIGN 审计外键完整。应另行在同事务取得确定的成功 SIGN 审计行并关联，覆盖并发与回滚；不能按“最新日志”猜测，也不伪造历史证明。当前是原型，不宣称法规合规验收。

复跑入口与分层证据见[候选验证报告](../verification/pr-candidate-20261105/report.md)。正式升级还需匹配的补丁身份服务、准确提交 CI、完整浏览器验收、真实备份恢复和维护授权。
