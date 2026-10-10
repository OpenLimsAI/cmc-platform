# 架构与系统边界

> 版本：V0.6｜日期：2026-10-10｜状态：第一版及跨项目配套代码已在本地实现并验证；Mac Hub模拟预览已发布，真实Linux接入与验收未完成；未提交/push，Linux未部署。

本文件维护系统边界、依赖、采集与存储方案；实际字段、接口、页面、验收和发布分别以README列出的专题为权威，避免重复维护。设计批准状态仅在DECISIONS维护。

## 核实依据与依赖入口

已通读全局/父目录四份文件和本项目全部文档，并核对下列项目说明与相关代码。2026-10-09 Linux调查范围、方法及版本见TASK_INVENTORY E01–E12；这不是运行全量业务或真实角色验收。

| 依赖 | 已读说明或代码入口 | 可支持的结论与限制 |
|---|---|---|
| 全局与父目录 | [全局 AGENTS](/Users/qingcheng/.codex/AGENTS.md)、[父 AGENTS](/Users/qingcheng/code/AGENTS.md)、[CLAUDE](/Users/qingcheng/code/CLAUDE.md)、[白皮书](/Users/qingcheng/code/CMAB_Data_Architecture_Whitepaper_V0_4.md)、[PORTS](/Users/qingcheng/code/PORTS.md) | 按主题合并；白皮书为 Draft。父 AGENTS/CLAUDE 仅工具加载说明不同，业务约定一致；历史差异见准入检查 |
| Hub | [AGENTS](../../cmab-hub/AGENTS.md)、[README](../../cmab-hub/README.md)、[nginx 说明](../../cmab-hub/nginx/README.md)、`frontend/src/config/apps.ts`、`auth/access.ts`、`shared/cmabSession.ts`、`nginx/hub-locations.conf` | 本地代码有角色磁贴及 SYS_ADMIN 显隐短路、MDM 会话母本；未见本项目磁贴或 `/ops/` 代理。Mac/Linux HEAD已核对一致，实际前端构建/真实角色浏览器未验收 |
| MDM | [AGENTS](../../cmab-mdm-platform/AGENTS.md)、[README](../../cmab-mdm-platform/README.md)、[备份恢复说明](../../cmab-mdm-platform/docs/RUNBOOK_BACKUP_RESTORE.md)、`backend/app/core/security.py`、`domains/auth/services.py` | 本地支持 HS256/RS256 签发，access 类型和 exp；签发带 roles/临时密码标记。本项目SYS_ADMIN已获用户确认；实际服务验签配置待实施，备份证据见盘点 |
| 共享迁移 | [AGENTS](../../cmc-schema-migrations/AGENTS.md)、[README](../../cmc-schema-migrations/README.md)、[SOP](../../cmc-schema-migrations/SOP.md) | 自有分析库对象迁移归该仓库；MDM 自身迁移归 MDM。历史首次建集群脚本不用于日常发布；未运行迁移 |
| QC LIMS | [README](../../qc-lims-etl/README.md)、[文档入口](../../qc-lims-etl/docs/README.md)、[运维说明](../../qc-lims-etl/docs/05-ops-deployment.md)；未找到项目 AGENTS | 实查15个raw+staging；配置17表不等于每日17表，独立stage不能代表父管道 |
| RD LIMS | [AGENTS](../../rd-lims-etl/AGENTS.md)、[README](../../rd-lims-etl/README.md) | cron/运维台账与实际水位字段已查，源时间与成功时间分开 |
| Lucullus | [AGENTS](../../rd-lucullus-etl/AGENTS.md) 中的编排与部署说明 | 六步骤实查；SUCCESS同时有VALIDATION，执行与质量分开 |
| 仪器归档 | [CLAUDE](../../cmc-instrument-ingest/CLAUDE.md)、[README](../../cmc-instrument-ingest/README.md)、[备份监控设计](../../cmc-instrument-ingest/docs/BACKUP_MONITORING_DESIGN.md)；未找到项目 AGENTS | 归档/ETL为数据依赖；心跳、JSONL告警可复用；外呼送达与恢复能力未验证 |
| Nova / Vi-CELL ETL | [Nova CLAUDE](../../rd-nova-etl/CLAUDE.md)、[Nova README](../../rd-nova-etl/README.md)、[Nova 部署](../../rd-nova-etl/deploy/DEPLOY.md)、[Vi-CELL AGENTS](../../rd-vicell-etl/AGENTS.md)、[Vi-CELL README](../../rd-vicell-etl/README.md)、[Vi-CELL 部署](../../rd-vicell-etl/deploy/DEPLOY.md) | NAS 归档是输入，存在文件水位和自有 etl_log，不能假定所有任务均使用 meta.etl_run；部署路径/班次以Linux实查为准，差异见盘点 |


## 已核实现状与复用

现状依据以[TASK_INVENTORY](TASK_INVENTORY.md)为准。已有systemd/journal、异构ETL台账、文件水位、NAS心跳/JSONL告警/校验清单可复用；现有heartbeat-check只覆盖两仪器最新心跳，不覆盖全部班次、ETL、数据库备份及恢复能力。告警出口ingest-alert.sh存在，FLEX2/Vi-CELL配置已引用；独立webhook文件未找到，没有消息送达证据。本项目不自动开通知。

Hub磁贴角色机制、统一会话母本、MDM JWT及session-policy可以复用；Hub无业务后端。本项目已有本地前后端与采集代码，无.git、无数据库对象；Hub本地注册已整合并发布Mac模拟预览，Linux服务及真实角色接入未部署。

## 实施架构（本地代码基线，生产配套未完成）

浏览器 → Hub:5100 `/ops/` → React/Vite；`/ops/api/`剥`/ops` → FastAPI `/api/`。MDM提供身份，后端独立SYS_ADMIN守卫。网页默认读统一观测；按需更新已在本项目实现，仅读固定范围运维证据，不启动源任务或任意shell。

本机结束事件/兜底触发独立collector → 白名单systemd元信息、受限cron调度摘要、有限journal/日志、RD/GMP运维台账、NAS已有清单 → 标准化观测及规则 → 自有历史/缓存 → API。不访问外部Oracle、仪器DB或业务raw，不改源台账。来源独立超时/失败隔离；整轮有snapshot_id，失败项保留，不能拿上一轮绿色拼成本轮全部成功。

推荐SQLAlchemy 2.0 ORM/asyncpg+FastAPI/Pydantic/uv；前端TypeScript/React/Vite/TanStack Query，自有CSS/SVG卡片；图表需要时再引入ECharts。监控不是另一套ETL编排器，不引入Airflow/Celery；采集器不import源ETL模块（避免导入初始化副作用），仅解析源记录。

## 结束事件与异步更新接入（D09草案）

任务的执行入口产生最小结束通知 → 本机受限通知入口/事件队列 → 独立collector读取既有台账、日志及产物元信息 → 追加观测并发布快照。通知是采集提示，原任务不调用网页业务接口、不使用管理员MDM token、不直接写监控数据库。浏览器业务API仍只SYS_ADMIN。

| 已有入口 | 拟接入方法与粒度 |
|---|---|
| QC、Nova、Vi-CELL systemd service | 以完整服务终止为通知边界，覆盖所有ExecStart阶段、启动失败/超时；接在系统级结束通知，不只监听成功 |
| instrument-ingest day/night service | 各班完整归档批次结束分别通知；保留两设备子结果，不凭最新设备心跳代替另一班 |
| MDM backup service | 自身备份结束通知；数据库备份并不归cmc-instrument-ingest |
| Lucullus、RD LIMS cron | 在既有顶层脚本的收尾路径增加小型结束通知，正常、异常退出均处理；保留原退出码，不改业务步骤或cron时刻 |
| 巡检/培训同步 | 如纳入全清单更新，按各自完整执行入口接通知；培训不是灾备 |
| 外部/历史来源 | 未核实外部主机通知能力，先靠兜底/按需采集，不假称已经事件接入 |

本轮检查的是本地部署单元及顶层脚本，未改变Linux单元或读取新运行事实；实际生效接法须按目标systemd版本、权限与服务沙箱验证后确定。cron进程被强制杀死可能无法执行收尾，必须依靠兜底；不宣称任何路径均保证送达。

通知推荐本机Unix socket并校验发送进程身份/固定任务白名单，或等效的受限本地消息入口；不新增公开匿名HTTP/源SQL凭据。消息仅含注册task_key、来源实例/班次、源运行ID（如有）、开始/结束时间及结束原因，不传日志/口令/连接串。发送来源及权限须绑定登记，通知中自称成功仍必须重新读源证据。

发送助手短时、尽力且不影响原任务结果；接收成功后记录事件并异步采集，源任务不等待看板完成、不依赖看板可用。发送失败只留本机运维提示，日兜底/启动补采补查；接收后事件按身份去重、并发合并并保留全部运行。事件接收故障与采集失败分别可见，恢复后补查未覆盖的源时间窗。

结束通知涉及多仓单元或顶层脚本及本机IPC权限；用户已授权并完成其他项目本地配套整合，Linux接入未执行。不要以监控名义改原任务时刻、重跑任务或让monitor控制源程序。不存在为此修改源数据库结构的要求。

## 数据归属与培训复制影响

已确认持久化到`cmc_analytics.ops_monitor`，迁移归cmc-schema-migrations；逻辑模型权威在[DATA_MODEL](DATA_MODEL.md)。源库只SELECT，自有schema可以追加采集/状态/访问记录，属于看板自身数据，不是源业务写操作。本轮没有建表或授权。

**2026-10-10再次只读核对Linux cron及同步脚本：L10每天00:00将正式cmc_analytics整库复制为cmc_analytics_training，供批号注册培训系统使用。** 这就是门户“批号管理【培训】”对应的库。将来新建ops_monitor后，现有整库复制也会带入真实任务状态、历史、事件及访问记录。

“不进入培训库”仅指排除ops_monitor的正式数据，不停止每天同步、不排除原有batch等业务数据，也不删除正式监控历史。培训库仍保留相同表结构和迁移版本；若未来需要练习监控，另用明确标注的模拟数据。目的是避免把真实生产运维记录当作培训记录，并避免新schema默认扩散到培训环境；不是新增GMP合规要求。数据排除已在原培训同步脚本本地实现并以隔离桩测试失败保护；未执行真实同步或改库。真实培训对账及发布未完成前不得部署持久化方案。

原仅内存+源历史备选未采用；用户已确认保存自身监控历史。更新触发与兜底方式按MONITORING_RULES事件方案草案，不默认SQLite或另建库。

## 采集最小权限方案

| 边界 | 建议权利 | 禁止/剩余条件 |
|---|---|---|
| collector OS | 专用非root账号；读取指定unit元信息、指定日志/状态路径 | 不用prometheus免密sudo或SSH私钥；不执行任务脚本；通过限定导出避免加入可读全部journal的adm组 |
| cron/受限journal | 经部署审核的固定元信息导出器，只输出计划、unit状态和脱敏片段 | 若需root执行，必须固定白名单、无用户命令/路径参数、独立审查；也可先用受控cron快照但新鲜度必须unknown，不能假称实时 |
| RD DB | 专用monitor_ro，CONNECT cmc_rd、USAGE meta及两instrument schema，meta三表/两etl_log必要列SELECT | 不继承ETL写角色或全库读；不读offending_data/任意context业务行 |
| GMP DB | 专用monitor_ro仅meta三表必要列SELECT | 运维元信息只读范围D07已确认；单次≤500条，禁止raw业务读取/FDW分析 |
| 自有存储 | collector追加自身观测/事件并按留存清理；API读取观测/运行/事件并追加访问/更新请求 | 不给DDL/源库写；保留策略由受控运维而非网页执行 |
| NAS/MDM dump | 固定心跳、Alerts、Logs、Checksums和产物stat | 备份内容及600权限dump不需要浏览器/collector读；产物元信息可由固定导出器提供 |

本轮postgres只读目录调查不代表未来生产应使用superuser。实际账号、ACL及导出器权限尚未创建，验收须用最终服务身份验证允许和拒绝；任意一源不足权利要显示unknown。

## 鉴权与Hub接入

身份与会话协议权威在[API_SPEC](API_SPEC.md)：MDM access签名/exp/type/sub/roles校验，must_change_password=403，业务只SYS_ADMIN。缺鉴权配置拒绝启动；token不落审计。复用cmab-hub/frontend/src/shared/cmabSession.ts，直接向MDM续期，时长从session-policy读；母本本轮不改。

建议磁贴“数据中台运维”，path=/ops/、requires=['SYS_ADMIN']，新增站内前端/API反代；Vite base/Router basename均/ops/。前端权限只是入口控制；直达API同样限制，按角色而非用户名，不新建管理员源。

## 固定端口与部署

2026-10-10按用户授权，已在父目录PORTS.md登记编号25：后端8025、前端5125。本次复查Mac/Linux监听、LaunchAgent及systemd/nginx相关配置，未发现冲突；仅完成文档分配，无服务或配置落地。未来严格固定且只听本机，外部仍走Hub5100；不新增ufw直连端口，发布前再次复查。

Linux建议/opt/cmc-platform-monitor，独立API/collector服务，监控故障不影响ETL。Mac开发验证→GitHub独立仓库→Linux固定SHA；Hub/迁移/training相关改动分别记录SHA。发布与回滚方案见[DEPLOYMENT](DEPLOYMENT.md)，尚无可执行部署脚本。

## 访问记录、使用边界及验收

用户已明确本系统暂不涉及GMP合规；V1定位为普通管理员运维辅助。只读任务运行记录/必要错误摘要已确认，不增设QA会签、CSV/Part11验证或恢复合规流程。保留已有证据与未知状态，不改变源系统用途、数据或备份策略；安全读取、权限限制、脱敏与访问记录仍保留。

审计分别记录collector服务身份的源读取与经验签管理员的API访问；记录操作者sub/username/roles快照、request_id、读取任务/来源/窗口、结果、行数、规则与快照版本；不记录token、口令、完整DSN或raw业务payload。失败/拒绝也需记录；审计落库不可用时，受保护证据详情接口建议503，最小存活探针不能返回运维信息。留存90天观测、180天访问记录已确认。

关键验收权威在[TEST_ACCEPTANCE](TEST_ACCEPTANCE.md)，页面权威在[INFORMATION_ARCHITECTURE](INFORMATION_ARCHITECTURE.md)，规则只在[MONITORING_RULES](MONITORING_RULES.md)维护。共机Linux/Hub/DB故障可能连看板也失联；UI须检查最后采集时间，外部存活检查/通知为后续独立能力，第一版不宣称覆盖整机灾难。

白皮书C01–C15结论权威在[ADMISSION_CHECKLIST](ADMISSION_CHECKLIST.md)，本篇只引用，不重复维护。


## 测试与验收

以[TEST_ACCEPTANCE](TEST_ACCEPTANCE.md)为权威；逐项覆盖UR01–UR08及本次真实边界案例，源权限用最终服务身份验证允许与拒绝。业务测试、Linux适配、同SHA发布与真实角色浏览器分别报告；本轮已完成本地代码与隔离验证；真实接入及生产验收尚未执行。

## 白皮书 Part V 准入

C01–C15逐项结论权威在[ADMISSION_CHECKLIST](ADMISSION_CHECKLIST.md)；D01–D12作为开发基线，本地代码及跨项目配套已实现，生产接入未完成，不能记准入全部通过。本项目为已有文档项目，沿用已有专题，不再新增同主题文件。

## 本地实现及生产限制（2026-10-10）

实际代码：API与独立collector分进程；每个来源再使用可终止的读取子进程，单源5s/整轮30s。事件按Unix socket SO_PEERCRED取得真实UID，与固定任务白名单比对；数据库提交后ACK，合并2秒内的通知，采集期间新消息留待后轮。队列持久化、重启恢复未完成批次；积压使当前视图未知，历史视图保留截至结果。内部队列等待不读取源，不属于每分钟检查任务。

每日07:00北京时间的安全检查在collector内按日期去重，晚于07:00启动补查当天；另做启动补采，管理员可请求异步更新。网页打开读最近视图，不常驻轮询；只有点击更新后短时检查该请求的完成结果。来源失败逐项未知，不能保留旧绿色；应更新时间已过但collector失联，API在打开时也会把状态改为未知。

systemd读取实时开关/日历并与登记对照，journal用固定生命周期标记、有界游标分页和invocation关联；先过滤后读取，避免读取整段业务日志。cron不能让collector读取全部用户配置：新增本项目只读摘要导出器，以原prometheus身份读取自己的crontab，仅导出三个固定任务的时刻/开关，06:59模板准备07:00兜底所需摘要。源调度未被修改；导出模板未安装，缺失/过期/计划变化显示未知。

systemd结束通知选用OnSuccess/OnFailure独立观察单元，保留原失败告警。目标Linux只读确认systemd255；该能力及语义已查[systemd v255原文](https://github.com/systemd/systemd/blob/v255/man/systemd.unit.xml)，journal游标/正向限行见[原文](https://github.com/systemd/systemd/blob/v255/man/journalctl.xml)。模板尚未经过生产沙箱实测。cron EXIT通知保留原退出码，SIGKILL/主机失联由每日兜底补查。

持久化实际采用4张表及JSONB观测，逻辑对象与物理表区分见DATA_MODEL。没有Alembic自动建表，没有生产内存降级或SQLite。API和collector部署时分别使用不同OS身份/数据库角色与环境文件；API无需任何源凭据。

尚未验证：PostgreSQL真实持久化/并发恢复、专用只读权限、日志/NAS读取ACL、源通知成功/失败送达、Hub/MDM真实角色会话、培训隔离、多仓同SHA发布。共享迁移已在所属链追加，Hub与源项目已整合本地配套；deploy是待安装的受管配置，权限材料仍待核实，上线前须逐项落实。当前无法宣称Linux全部来源已接入。

凭据按进程进一步隔离：API环境为backend/.env.example，collector为backend/.env.collector.example；读取子进程不接收MDM密钥或监控写库连接，只接收源只读连接和白名单。collector/reader不读取API dotenv。API明确拒绝以无鉴权的采集配置启动，相关隔离已纳入测试。生产读取角色的有效权限仍未验证。


本地配套权威入口见[integration导航](../integration/README.md)。7个源service直接新增结束观察指令，原OnFailure告警仍保留；3个cron在原顶层脚本EXIT出口发送提示，不包装或另起源任务。发送助手的全部连接/收发共享2秒期限、ACK最多128字节且完整换行，部分ACK不会误当拒绝。培训复制以pipefail+ON_ERROR_STOP拦截导出和灌库失败，且仅排除ops_monitor数据；先核对新库空运维表/业务计数，再沿用原换库步骤，失败保护按桩测试验证。
