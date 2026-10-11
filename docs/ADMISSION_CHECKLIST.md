# 白皮书Part V准入检查 C01–C15

> 版本：V0.7｜日期：2026-10-10｜状态：已提交/push并部署Linux真实监控及Hub入口；服务、采集、权限和培训空表核验通过。真实MDM角色浏览器及下一次自然任务端到端通知待验收；详见 RELEASE_20261010。Mac保留模拟预览。

依据CMAB_Data_Architecture_Whitepaper_V0_4.md Part V（Draft、2026-09-16增补）。设计/现状/待确认分别列明，不因有草案就记通过。

| 项 | 本项目具体结论 | 状态/证据 |
|---|---|---|
| C01 数据库/schema | 源仅读RD/GMP运维表；自有记录推荐cmc_analytics.ops_monitor，不新建库/SQLite；training全库复制必须处理 | D06已确认；正式/培训四表已迁移，培训空表 |
| C02 schema命名 | 不新增raw；ops_monitor为运维域schema候选，字段小写下划线 | D06已确认 |
| C03 主数据权威源 | 身份MDM auth/JWT；计划以实际调度为准；如未来需设备属性读MDM eqp/dim映射，不解析source_instance | 10个在用组已真实读取；MDM验签API通过，真实角色浏览器待验收 |
| C04 新主数据 | 不新增设备/人员/物质；task_definition是运维注册，不是第二套业务主数据 | 当前不适用；配置版本化 |
| C05 batch_number | 不处理业务批号或原始业务结果；证据摘要避免携带样品身份 | 当前不适用，不机械改源字段 |
| C06 命名 | 逻辑对象snake_case单数；保留异构来源原名/状态与NULL实例 | ORM/配置与已迁移四表对应 |
| C07 审计 | 自身access_audit_log记录读取范围/操作者/结果/版本，拒绝及失败也留痕，期限拟180天 | D06/D07已确认自有访问记录位置及180天留存；记录安全/运维访问，不引入Part11专用审计流程；不写源raw/meta |
| C08 GxP | 管理员运维辅助，不作放行结论；用户明确本系统暂不涉及GMP合规 | D07已确认普通运维辅助，不设置CSV/QA会签前置 |
| C09 watermark | 不建业务ETL；读取RD/GMP水位及仪器台账候选/当前文件水位，分别解释语义 | 最终只读身份有界读取通过，raw业务列访问被拒绝 |
| C10 GitHub | 独立仓库github.com/qingcheng81/cmc-platform-monitor；用户D15授权发布 | 已提交/push，Linux固定SHA |
| C11 数据重叠 | 复用台账/心跳/告警，不复制全台账、不双写源；记录必要派生观测 | 设计约束；training复制为已发现影响 |
| C12 GMP访问 | 实时meta三表必要运维列、≤500行/次、审计；不读GMP raw/FDW分析，不查Oracle | 有界只读调查完成；运维只读范围D07已确认；结束触发及兜底集成按D09待收敛 |
| C13 前端 | TypeScript/React/Vite/TanStack Query；卡片使用自有CSS/SVG，不增加未使用的UI/图表依赖；复用会话母本 | 本地代码/构建和模拟浏览器已验证 |
| C14 后端 | FastAPI/Pydantic/uv，ORM SQLAlchemy2/asyncpg；独立collector，无源ETL import | 本地53项测试及Linux真实API/读取通过，真实角色浏览器待验收 |
| C15 发布 | Mac→GitHub→Linux固定SHA，/opt/cmc-platform-monitor+systemd，Hub同源；多仓版本/迁移、回滚及真实角色验收 | Mac模拟预览保留，Linux真实数据及Hub已部署，真实角色/自然任务通知待验收；2026-10-10已按用户授权登记PORTS编号25/8025/5125 |

全局AGENTS与CLAUDE正文仅工具加载表述不同；旧端口公式按PORTS及占用核对，不套公式分配。白皮书“Mac仅结构”不作空库依据。旧instrument/nova说明的02:00 ETL、旧source_table水位与实际不一致；本项目已记录差异，相关历史时刻未被当成本轮修改调度的依据；已按D15授权发布监控配套，原任务计划不改。

## 本地开发后的准入状态补充

C01–C15逐项表仍为架构/生产接入检查，不能因代码和模拟测试完成而全部打勾。本项目已采用约定栈、固定8025/5125、MDM后端SYS_ADMIN守卫、源只读有界读取、自有ops_monitor模型/审计、卡片/历史/未知状态、事件+07:00机制。迁移归属/Hub/培训数据隔离已在各所属仓本地整合；共享仓本地整合及离线验证已完成，真实专用权限、生产运维采集及服务发布已完成；真实MDM角色浏览器与自然任务链路尚未完成。外部源/恢复资料缺口仍显示未核实，不新增GMP合规会签。


## P16 MDM恢复验证增补（2026-10-11）

C01/C11：临时容器中的mdm_verify仅为备份恢复副本，结束销毁，不是新增业务数据库或第二套主数据；看板最小报告继续用既有ops_monitor JSONB，无新迁移。C03/C07：账号/角色仍MDM权威，验证服务身份、产物/SHA/版本及诊断留MDM受限报告；monitor只读摘要并留现有访问记录。C08/C12：普通运维验证，不涉及GMP raw、Oracle或业务合规结论。C15：两仓GitHub固定SHA发布，原生实例不作为恢复目标，无新增宿主端口、Hub/PORTS不变；细节及下一次自然链路未验收范围见RELEASE_20261011_BACKUP_VERIFY。
