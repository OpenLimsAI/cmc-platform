# MDM创建并关联后端：TDD与隔离回归记录

2026-10-26，ThinkpadT14-Le。本记录仅是后端单测/持久化回归，不是标准授权码、真实Casdoor或浏览器端到端验收结果。

## Red → 实现 → Green

13:22 UTC，主任务在全新`mdm-phase2-unit` PostgreSQL中通过原`run_phase1_tests.py` / `run_tests.sh`执行`tests/test_oidc_protocol.py tests/test_pm_create.py`。创建模块尚不存在，collection明确报`ModuleNotFoundError: app.domains.prs.pm_create`。创建文件当时先写了7个测试；之后才实现创建模块和0068迁移。

实现后补充本地完成提交失败、过期worker晚返回、已知远端回执丢失3项防御测试。没有为这些补充测试伪造独立red，也没有把中途import排序lint失败算作业务测试red。

13:46 UTC前有效执行完成：

```text
docker exec -e LOGURU_LEVEL=WARNING -e APP_LOG_LEVEL=WARNING cmc-mdm-phase2-unit-backend \
  python scripts/run_phase1_tests.py tests/test_pm_create.py tests/test_project_pm_link.py

14 passed, 1 warning in 12.50s
exit code: 0
```

新建测试库完整迁移到`0068_pm_create_request`，包含父任务`0067_oidc_identity`；原脚本重建的目标仅为隔离`cmab_test`，未碰已上线dev或原有数据库。前置ruff/mypy通过；本切片额外ruff和mypy检查也通过。唯一warning为既有passlib `crypt` Python3.13弃用提示，没有放松断言/测试规则。

## 本轮覆盖

1. 匿名/只读写入拒绝；原生MDM JWT不能隐式使用第一阶段静态核验身份创建PM。
2. 重复、并发同请求只持久化一个请求、一条映射和一条成功关联审计；同键异参冲突。
3. PM已经创建但响应超时，原UUID查询恢复，不再创建。
4. PM回执持久化后进程中断，租约到期恢复。
5. 本地完成commit失败，映射/成功审计回滚，但远端回执仍可恢复，最终只一条成功关联。
6. 创建处理中人工另行绑定被拒；租约过期后新worker完成，旧worker晚返回不能覆盖。
7. 负责人、当前/目标阶段、计划日期必须显式输入；日期及额外预算字段校验。
8. HTTP响应大小有界、PM访问令牌只在Authorization头、不进入URL/响应；错误登记回执拒绝。
9. 已知远端回执后PM查询404，明确进入对账状态，禁止再次POST重建。
10. 第一阶段原有关联权限、静态配置缺失、唯一性/并发/审计和远端缺失/失效回归4项仍通过。

PM传输使用明确的ContractPM/MockTransport边界替身；SQL事务、租约、唯一映射和审计使用新PostgreSQL。真实跨应用创建、统一登录/登出、回调/禁用和真实失败重试仍必须由主任务在获批新隔离身份环境中验收，不能用本记录代替。

测试容器镜像：`mdm-phase2-unit-tests`，image ID `sha256:d082fe3a2676639e63108acd857fb3919561318fca33a1978362b45175bb7eb0`；宿主源码以只读绑定供该容器验证。此次已测文件哈希见[创建后端源码清单](backend-create-source-hashes.json)。该清单只绑定此轮检查，后续若源码改变需重新验证并更新最终验收版本记录。
