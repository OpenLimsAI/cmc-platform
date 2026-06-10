# 审查状态 2026-06-10

## 1. 当前阶段

Stage 1 阶段性封版（封版文件：REVIEW_REPORT_2026-06-10_STAGE1.md；活跃文件：REVIEW_REPORT_2026-06-10.md）。
进度 18/26 个审查任务，283 条发现（Critical 0 / High 19 / Medium 100 / Low 164）。

> 说明：第三轮补跑在撞限额前已完成 9 个新模块且结果已持久化，封版时一并纳入，故为 18/26 而非此前登记的 9/26。

## 2. 已完成模块（18）

- 文档:架构设计+数据模型(内部质量)
- 文档:API规范+UI信息架构(内部质量)
- 文档:偏离说明修订链条
- 文档:README+QUICKSTART+Makefile
- 文档:RUNBOOK+OQ追溯
- 后端:be-auth
- 后端:be-ref
- 后端:be-srs
- 后端:be-ars
- 后端:be-mm
- 后端:be-eqp
- 后端:be-search
- 后端:be-tests（测试套件质量）
- 前端:auth+admin
- 前端:substances+projects+assets
- 前端:dashboard+profile+common
- 匹配性:API规范↔路由
- 匹配性:数据模型↔ORM+迁移

## 3. 未完成模块（8）

- 后端:be-audit
- 后端:be-prs
- 后端:be-core（core/shared/api/main.py）
- 后端:be-migrations（alembic 迁移链 + scripts）
- 前端:materials+equipments
- 前端:api+stores+routes+shared
- 匹配性:偏离说明V1.3↔代码
- 匹配性:前端↔API

## 4. 当前 High 发现清单（19 条）

| # | 模块 | 标题 | 位置（截断） | 复核状态 |
|---|------|------|------|------|
| H-01 | 后端:be-auth | 锁定期满后可无限暴力破解 | auth/services.py:180-186,122 | 复核未完成 |
| H-02 | 后端:be-auth | auth 域全部表无审计追踪 | alembic 0001_init_schemas | 复核未完成 |
| H-03 | 后端:be-auth | 软删角色重建触发 500 | auth/admin_role_service.py:151-156,234 | 复核未完成 |
| H-04 | 前端:auth+admin | 改密旧密码错被强制登出 | frontend/src/api/client.ts:122-134 | 复核未完成 |
| H-05 | 前端:auth+admin | 强制改密可被完全绕过 | shared/permissions.py:25-88 + frontend/src/routes | 复核未完成 |
| H-06 | 前端:dashboard+profile+common | 改密输错旧密码被强制登出（与 H-04 同源重复发现） | frontend/src/api/client.ts:122-134 | 复核未完成 |
| H-07 | 前端:dashboard+profile+common | 新密码最小长度前后端不一致 | ChangePasswordPage.tsx:111+ | 复核未完成 |
| H-08 | 后端:be-srs | internal_code 软删后无法复用且 500 | srs/services.py:329-339 + alembic 0028 | 复核未完成 |
| H-09 | 后端:be-ref | 主数据软删后引用无法解除 | ref/services.py:64-73,136-169 | 复核未完成 |
| H-10 | 后端:be-ars | market_id 软删后重建撞唯一约束 | ars/services.py:329-364 | 复核未完成 |
| H-11 | 后端:be-ars | 幂等缓存先于事务提交写入 | api/v1/assets.py:101-105 + core/database | 复核未完成 |
| H-12 | 后端:be-ars | 状态机并发竞态可复活已终止资产 | ars/services.py:234-275 | 复核未完成 |
| H-13 | 后端:be-mm | 软删批次后复用批号触发 500 | mm/services.py:380-391,440-454 | 复核未完成 |
| H-14 | 后端:be-tests | 测试硬编码 8000 绕过隔离 test DB | tests/test_smoke.py:8 等 | 复核未完成 |
| H-15 | 匹配性:数据模型↔ORM+迁移 | milestone_type 空约束 ORM↔DB 冲突 | prs/models.py:144 + alembic 0006/0014 | 复核未完成 |
| H-16 | 文档:架构设计+数据模型 | EQP 范围自相矛盾（In/Out-of-Scope 冲突） | 架构设计文档:120 与 41/73 | 复核未完成 |
| H-17 | 文档:README+QUICKSTART+Makefile | 引用不存在的 requirements.txt | README.md:248,269 | 复核未完成 |
| H-18 | 文档:RUNBOOK+OQ追溯 | alembic 校验跑错容器 | RUNBOOK_BACKUP_RESTORE.md:101 + scripts/restore_db.sh | 复核未完成 |
| H-19 | 文档:RUNBOOK+OQ追溯 | 生产恢复 pytest 校验不可行 | RUNBOOK_BACKUP_RESTORE.md:94,102 | 复核未完成 |

注：编号 H-01~H-19 与 REVIEW_TRIAGE_HIGH_2026-06-10.md 一一对应；H-04/H-06 为两个审查员重复发现同一问题，可合并处置。另：第一轮 be-search 评 High 的「先 LIMIT 后排序丢失最优命中」在第二轮重跑中被同审查点改评为 Medium（「LIMIT 无 ORDER BY 截断任意子集」），按后者计，不在 High 清单内。

## 5. 复核未完成的 High

**全部 19 条 High 均为「复核未完成」**——对抗性复核 agent 在两次会话限额中断（13:30 与 11:50pm 窗口）中被打断。报告正文已逐条标注「⏳ 复核未完成（中断），按原审查员置信度采信」。

复核优先级建议（安全相关优先）：H-01 锁定期满暴力破解、H-05 强制改密绕过、H-02 auth 无审计、H-11 幂等缓存先于提交、H-12 状态机并发竞态。

## 6. 下一步建议：只做小批量任务包

不要再做全项目并行审查（单轮 17+ 任务必撞限额）。建议每个会话窗口只跑 **一个小包（≤3 个 agent）**，跑完立即渲染落盘（渲染脚本：session 目录 render_report.py，数据源为 tasks/*.output）：

- **包 A（最优先）**：复核 19 条 High——拆 2 个复核 agent（安全 5 条一组、其余一组），每条在仓库找反证后标注确认/推翻
- **包 B**：后端 be-audit + be-core
- **包 C**：后端 be-prs + be-migrations
- **包 D**：前端 materials+equipments + api/stores/routes/shared
- **包 E**：匹配性 偏离说明V1.3↔代码 + 前端↔API
- 全部完成后：重渲染报告 + 写执行摘要与 Top 10，出最终版

会话限额下次重置时间：今天 23:50（Asia/Shanghai）。

## 7. 数据源（结构化 JSON，含全部 findings）

目录：/private/tmp/claude-501/-Users-qingcheng-code-cmab-mdm-platform/927fabf4-a2e2-4ac1-9510-55c900bb2897/
- 渲染脚本：render_report.py（按轮次传入 output 文件，后者覆盖前者）
- 第 1 轮：tasks/ws4vgr6mk.output、tasks/wbksjp4c8.output、tasks/wp8n138ac.output
- 第 2 轮：tasks/w9fr3o7dl.output、tasks/we4nw6zkv.output、tasks/wje68b6ld.output
- 第 3 轮：tasks/w58wx3j1w.output
