# 签名审计关联与全量类型检查修复

本文件为原生工程验证记录，不是 Word 设计文档的派生副本。仅验证本地隔离合成环境；不涉及 Maibo、真实账号、正式数据或部署。

## 修改边界

- 新电子签名先写入一条成功的 `SIGN` 审计，并在同一业务事务中将其 ID 保存到 `e_signature.audit_log_id`。审计包含操作者、对象、签名含义、独立签名理由、时间、内容/签名哈希和认证方式，不记录密码或认证令牌。
- 原有密码验证及 OIDC 新鲜认证、主体/会话绑定、一次性挑战和业务权限保持执行。成功审计不走独立提交；业务事务回滚时，签名和成功审计一起回滚。已知未提交失败与提交结果不确定应区分，不能据网络异常推断数据库未提交。
- 不新增数据库迁移、不回填历史、不改变旧签名哈希。新 API 摘要提供可空的审计 ID，界面显示关联 ID；旧记录缺少关联时显示“历史记录未关联”。
- 全量 `mypy app` 从162项降至0项，覆盖127个源文件。保留原检查规则，未增加忽略诊断或排除模块。Pydantic 官方插件启用类型化初始化；移除覆盖 Redis 原生类型的旧 `types-redis` 及其三个专用传递 stub，其余锁定版本不变。
- 使用 TypedDict 明确种子定义与导入统计结构；修正真正缺失的类型导入、变量复用与数据库结果边界。持久化字符串进入 Literal 响应字段时继续由原 Pydantic 模型实际验证。没有运行真实导入、demo 或真实库 seed。

## TDD 与回归

1. 基线 `75cb755` 实际复现162项全量 mypy诊断。
2. 新增新鲜认证业务测试的直接审计关联断言，初次因 `audit_log_id is None` 失败；实现后通过。首轮 Compose 相对挂载配置失败不算业务 red，修正挂载后的断言失败才是 red。
3. 增加新签名关联、成功记录原子回滚、独立签署不共享审计记录、历史空关联不回填、API 摘要兼容的隔离数据库测试。既有取消、过期、重放、内容变化及失效会话拒绝继续保留。
4. 身份/项目/签名397项回归通过；前端55项单测、严格 eslint、TypeScript/Vite生产构建通过。
5. 扩展领域回归首轮170通过、1失败，捕获本轮字典整理导致的物料引用列表问题。已修正为从 SQLAlchemy 的行序列构造字典，强化该接口200断言，并将11组受影响领域回归纳入同一CI入口；本地扩充后的568项全部通过。
6. API 类型通过实际应用的 OpenAPI 和官方 `openapi-typescript` 生成，未手改生成文件；同时补齐主线既有 OIDC/PM 接口的生成类型，不表示本轮新增这些业务接口。
7. 最后补充的3项聚焦验证通过：在业务提交前注入明确失败后，OIDC挑战回到ready且未绑定签名，业务状态、签名和成功SIGN审计全部回滚；另外核验原生兼容/历史空关联保留及物料引用列表。该故障注入为数据库集成测试，不是浏览器认证证明。

`type-refactor-integrity.json` 保存11组种子常量的 AST 哈希对照及锁定版本对照；没有复制任何账号密码或导入业务数据。
`dto-refactor-integrity.json` 核对15处响应边界，字段及取值表达式与基线一致，保留原模型的运行时验证。

## 可重复执行

在仓库根目录运行：

```sh
docker compose -p mdm-audit-types-ci -f cmab-mdm-platform/deploy/docker-compose.phase1-test.yml up --build --abort-on-container-exit --exit-code-from tests
docker compose -p mdm-audit-types-ci -f cmab-mdm-platform/deploy/docker-compose.phase1-test.yml down -v
docker build -f cmab-mdm-platform/deploy/test/frontend.Dockerfile cmab-mdm-platform/frontend
```

该 Compose 是新建、无固定卷名、无宿主发布端口的测试环境，使用空 tmpfs PostgreSQL与独立 Redis。测试入口验证 `TEST_DB=cmab_test`、`TEST_DB_HOST=postgres`，通过 `run_tests.sh` 重建的仅为该新测试库。不要将这些命令改成 dev 或共享库配置。

CI入口 `backend/scripts/run_phase2_tests.py` 保留原检查并新增完整 `mypy app` 和受影响领域回归；不降低测试、覆盖率或认证要求。

## 合并后真实浏览器验收

尚未执行本轮合并后的完整浏览器签署。计划固定三仓库提交及镜像指纹，在独立191xx回环环境用合成账号通过正常页面完成门户→MDM/PM、创建关联、签名再次验密、状态/审计展示和必要拒绝路径；不以 API 或单测冒充浏览器验收，不修改原190xx体验环境。

本轮合成密码在内存中自动输入已获用户明确许可，但仍遵守实际工具审批和任何安全停止；密码不得进入截图、日志、仓库或聊天。实际完成后记录独立截图、时间、HTTP/数据库断言及清理结果；当前不预写通过结论。

本轮代码 PR、精确提交的CI、squash和主线CI结果另随实际执行记录更新。代码合入不等于 Maibo 部署，也不构成正式合规验收。
