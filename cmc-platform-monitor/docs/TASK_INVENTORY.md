# Linux 任务与证据盘点

## 2026-11-05 调度调整基线

10:28只读复核：Nova与Vi-CELL实际timer均仅12:05/16:20、Persistent=yes、随机延迟0；凌晨归档当天02:00:27至02:01:15结束，service允许最长4小时。用户确认两个ETL补充02:20，首个新增凌晨计划为2026-11-06；归档时刻不变。以下10月盘点保留历史原值，当前配置生效/首次自然运行结果见CHANGELOG。20分钟仅为固定错峰，不以当天短耗时保证以后均能提前结束。

> 版本：V0.7｜日期：2026-10-10｜状态：已提交/push并部署Linux真实监控及Hub入口；服务、采集、权限和培训空表核验通过。真实MDM角色浏览器及下一次自然任务端到端通知待验收；详见 RELEASE_20261010。Mac保留模拟预览。

2026-10-10补充只读复核：Mac/Linux未见8025/5125监听，相关LaunchAgent/systemd/nginx配置未发现冲突，父PORTS已按用户授权登记编号25；该登记不代表已启动服务。Linux cron再次确认每天00:00调用training_db_reset.sh；脚本SRC=cmc_analytics、DST=cmc_analytics_training，仍整库复制，不含ops_monitor排除策略。下列其余运行事实保留2026-10-09调查时间，不作全量重新盘点。

## 调查范围与计数

主机172.19.0.105、hostname=prometheus，SSH 13568；主要调查约2026-10-09 21:40–21:49，22:10另复核运维表catalog字段与类型，时区Asia/Shanghai。下列运行时间均为北京时间。仅调查现有调度、代码、运维台账、限定日志及备份元信息；未执行原任务、备份校验或恢复。

已发现 **10个在用的Linux顶层任务组**：5个ETL管道、3个备份/归档执行组、1个心跳巡检、1个培训同步。对应 **7个自定义systemd timer和5条用户cron表达式**（合并为3组）。父管道与子步骤分开计数，不相加。这是已发现入口的清单，不是全平台覆盖100%的声明。

源主机/环境默认为本Linux正式环境，任务种类另列；RD/GMP表示数据域，不由source_instance字符串解析。owner须由负责人补认，操作系统运行身份不等于业务责任人。

## 顶层任务清单

| ID / 类型 | 实际入口、计划、运行身份 | 最近运行及证据 | 风险/缺口 |
|---|---|---|---|
| L01 Lucullus / ETL | prometheus cron 01:00；/opt/rd-lucullus-etl/run_lucullus_pipeline.sh | 10-09 01:00:01–01:19:26；父日志失败步骤数0，5条子台账SUCCESS | 第6步仅日志；batch_dim有84条VALIDATION，不能汇总无质量风险 |
| L02 RD LIMS / ETL | prometheus cron 08:00/12:00/16:00；/opt/rd-lims-etl/scripts/run_etl.sh | run1225，16:00:02–16:01:05 SUCCESS；读11253、写21354、错误0；7天21次SUCCESS | etl_job.owner/schedule为空，须读实际cron；人员字典属于同次子阶段 |
| L03 QC LIMS / ETL | qc-lims-etl.timer 04:00 Asia/Shanghai；enabled、Persistent=false；prometheus；flock -n | service 04:00:02–04:03:48 exit0；15个raw success、错误0；staging run34 success | TimeoutStart=infinity；最新staging run35为20:50–20:54独立执行，不能替代04:00父运行 |
| L04 Vi-CELL / ETL | vicell-etl.timer 12:05/16:20；enabled/Persistent=true/随机0；prometheus | raw etl_log id184，16:20:33–16:20:35 success，扫描12/加载0/错误0；stage日志16:20:47完成，service exit0 | run和stage两条ExecStart；stage无独立台账；文件水位不是执行时间 |
| L05 Nova / ETL | nova-etl.timer 12:05/16:20；enabled/Persistent=true/随机0；prometheus | raw etl_log id152，16:20:34 success；文件0/行0/冲突0/未解决0；stage日志/退出证据 | CLI对partial也返回0；旧补齐文件仍有行宽跳过WARNING，不能只看exit0 |
| L06 白天仪器归档 / backup | instrument-ingest-day.timer 11:45/16:00；enabled/Persistent=true/随机0；flex2ingest | 16:00:01–16:00:33 exit0；两台心跳SUCCESS，Vi-CELL WARNING=1 | 白天不抓图片；每设备一个心跳文件被各班覆盖，须保留mode/run_tag |
| L07 夜间仪器归档 / backup | instrument-ingest-night.timer 02:00；enabled/Persistent=true/随机0；flex2ingest | 02:00:03–02:01:23 exit0；Vi-CELL既有SHA报告554行MATCH；Nova2行Match | 10-08夜班Vi-CELL失败4项，后来白天成功不能抹去；未找到恢复演练 |
| L08 MDM每日数据库备份 / backup | cmab-mdm-backup.timer 02:00；enabled/Persistent=true/随机≤300s；prometheus | 02:03:52–02:03:53 exit0、日志完成，dump=1000861字节 | 脚本仅非空检查；顶层36份dump含手工产物；无当前日常hash/恢复验证 |
| L09 心跳巡检 / monitor | heartbeat-check.timer 09:00+随机≤120s；enabled/Persistent=true；flex2ingest | 09:01:10 exit0，“检查2台、全部正常” | 仅最新设备心跳、36h静默阈值；不能证明每个班次成功或全部备份正常 |
| L10 培训库同步 / sync | prometheus cron 00:00；/opt/rd-batch-registry-training/scripts/training_db_reset.sh | 日志00:00:01–00:00:35完成，batch_register=34 | 正式cmc_analytics整库数据复制到training；临时库换名后删old；不是灾备，可能复制未来监控/审计记录 |

服务在timer驱动下可为static/disabled；不能凭service.enabled认定停用，须结合timer、实际调用和加载状态。系统级failed=0，但用户级旧cmc-frontend服务failed，口径不同。

## 子任务、实际字段与依赖

L01共6个必需步骤，按每站reference→daily，再全局batch_dim→process_daily：

| 源job_name / source_instance | cmc_rd.meta.etl_run最近成功 | 范围 |
|---|---|---|
| lucullus_sync_reference / rd_ws01_usp_lucullus_01 | run1218，01:00:02–01:00:04 | 参考表 |
| lucullus_daily_sync / rd_ws01_usp_lucullus_01 | run1219，01:00:05–01:05:43 | 独立水位 |
| lucullus_sync_reference / rd_ws02_usp_lucullus_01 | run1220，01:05:44 | 参考表 |
| lucullus_daily_sync / rd_ws02_usp_lucullus_01 | run1221，01:05:45–01:06:43 | 独立水位 |
| lucullus_build_batch_dim / NULL（全部） | run1222，01:06:44–01:09:56 | 全局维度 |
| lucullus_build_process_daily（脚本身份） | 无台账，父日志01:09:56–01:19:26完成 | 日聚合，日志写57382行 |

父脚本单步失败继续，累计失败数作为退出码。7天各有台账步骤7次SUCCESS；load_error_log VALIDATION共588条；最新run1222有84条=49 unparseable+35 suspect_test。代码明确此类提示不累加rows_errored；这是重复运行产生的校验记录数量，不是588个唯一坏对象，也不是84次执行崩溃。

L02源job_name=rd_lims_etl_samplemanager、source_instance=NULL。实际水位字段是target_table/last_success_ts，而非旧文档的source_table/watermark_col；本次last_success_ts=14:42:22是源到样时刻，updated_at=16:01:05是ETL更新时间。raw/staging及dim.employee_master同次执行，阶段证据不能省略。

L03常规15个raw子任务均source_instance=lims-prod：qc_lims.s_batch、s_sample、sdiworkitem、sdiworkitemitem、sdidata、sdidataitem、s_samplepoint、workitem、paramlist、paramlistitem、param、sdispec、sdidataitemspec、spec、specparamitems；全部成功后qc_lims.staging。凌晨run34 stage=04:00:20–04:03:48；raw约17s、stage约208s，为阶段墙钟耗时。最新run35是独立stage，不作为整管道最近成功。

QC config.yaml有17张源镜像配置；INCIDENT/INCIDENTITEM受QC_INCIDENT_SYNC_ENABLED控制，默认不进日常调度，未见对应运行台账；不能把代码17表写成当前每日17表。qc_lims.point_enrichment只有10-08手工记录，无周期入口。报告候选preview已有代码及snap_gmp对象，无已发现自动调度，属于事件/手工任务登记，不能套04:00漏跑规则。

L04/L05 raw结果来自cmc_rd.raw_rd_usp_vicell.etl_log、raw_rd_usp_nova.etl_log，stage来自限定日志/service；只读这两张运维表必要列，不扫同schema业务表。文件水位分别为/var/lib/vicell-etl/watermark=1791361233.910739、/var/lib/nova-etl/watermark=1791506973.4002616，单位epoch秒；归档保留旧mtime，历史回补可能落到水位下方，本项目不重扫修复。

L06/L07每次按FLEX2→Vi-CELL串行；子设备T281240040C_Nova、C4V61257XH_ViCell不能互相代替。父任一失败返回1，并继续其他设备；day/night共用flock（最多等30min）。service硬超时day=15min、night=4h；day硬上限小于脚本最长等锁30min，重叠时可能被service先终止，应呈现配置/依赖风险，本轮不改上限。最新设备心跳两班共写一个文件，不足以证明夜班；需按父journal、run_tag、mode关联。

归档→ETL是数据依赖，**不是完成后触发的父子关系**；day 11:45/16:00、ETL12:05/16:20的固定20min间隔不保证故障时先后完成。上游失败而下游零新增成功要显示dependency_risk。

## 停用、其他入口和外部覆盖

| 来源/标识 | 已核实事实 | 缺口/判断边界 |
|---|---|---|
| flex2-ingest.timer.bak-20260723 | 旧01:00配置备份文件，未加载 | 历史文件不是仍在重复调度 |
| pg_dump@/pg_basebackup@/pg_compresswal@ timer、pg_receivewal@service | 模板disabled，无已加载实例 | 安装模板不代表数据库在备份 |
| 旧qc_lims_etl | /opt/backups/retired-projects/qc_lims_etl-20261008归档，无有效入口 | 不执行归档脚本 |
| 旧rd_lims_etl/tt-lims-platform | cron只新版；tt-lims-platform目录仍在，无发现运行入口 | 目录存在不等于仍运行 |
| 用户级旧LIMS服务 | cmc-backend、cmc-frontend均disabled；前者inactive、后者failed | 不等于系统级现行LIMS或ETL失败 |
| RALF设计/脚本 | ralf目录存在，无timer/cron/运行记录 | 未证实上线，不当作计划停用 |
| CZC1079M4B_Biacore外部备份 | NAS10-09 04:46:19日志PYTHON_EXIT_CODE=0，state更新；最新SHA报告0行 | 源Windows计划/开关未核实；日志尾MD5字样与SHA清单不一致，保留算法原文 |
| PBXYXD3_XEVOG2S外部备份 | 10-09 05:24:03结束文本；最近MD5清单03-10，37行Match | 结束文本不证明完整成功；近期校验缺口及源调度未知 |
| LACE07_PC13FN6K外部备份 | 10-09 21:00:03日志结束；无Checksums文件 | 不能证明完整Empower库及审计追踪可恢复 |
| P509W57K_AVANT历史/外部备份 | 最近可见日志03-11，Access is denied / RETRY LIMIT EXCEEDED | 是否计划停用未知，登记unknown+最后可见失败，不套每日漏跑 |
| SA18215201_Biacore历史/外部备份 | Daily目录存在，Logs/Checksums无文件 | 计划/开关/成功未知 |
| PBXYXD3_XEVOG2S20250708旧Daily目录 | 额外旧目录存在 | 是否历史别名待确认，不新增成功计数 |
| OS维护 | 系统35个timer文件/24个已加载，用户2个timer文件/1个已加载 | dpkg-db-backup仅包数据库，sysstat/e2scrub/轮换不算业务备份 |

未发现同ETL的cron+timer双入口。三条RD LIMS cron是三个计划时刻；Nova/Vi-CELL同点执行是不同任务。培训脚本在两代码目录都有，cron只调用training副本。未证实实际重复执行；手工重叠仍需关联，QC有flock，RD/Lucullus入口未见等价互斥。

## 备份覆盖和恢复证据

| 对象 | 已找到周期策略 | 已有验证与缺口 |
|---|---|---|
| cmab_mdm | L08每日本机dump，mtime>30天清理 | 当前每日仅非空；9-15发布副本有backup-sha256.txt、backup-catalog.txt，不能泛化到所有dump；SOP存在，未找到已执行恢复演练 |
| cmc_rd/cmc_analytics/cmc_data_platform/cmc_gmp/cmab_qv/cmc_analytics_training | 未发现周期业务备份入口 | QC/MDM发布前手工dump及SHA/目录清单存在，不是每日策略；培训整库复制不是灾备 |
| 三PG实例PITR | archive_mode=off、archive_command=(disabled) | 不代表已核实IT/VM层没有其他备份，外部策略待补证 |
| Nova/Vi-CELL归档 | L06/L07 | 夜班既有hash分别2/554行匹配；只覆盖本次改变文件；零行报告不能代表全量完整；无已找到恢复演练 |
| 外部仪器/应用、NAS、异地副本、代码配置 | NAS/发布目录有部分记录，未找到统一Linux周期入口 | 源主机/IT/NAS/VM实际调度和恢复证据未知；不读取备份业务内容或秘密副本 |

Nova最近Database/Backup_2026-10-08_233022含DatabaseBackup.dbb=17140509字节、Persist.dbb=22620字节；工具/密钥/完整恢复范围未核实，不解密或解析。MDM最近dump名为cmab_mdm_prometheus_20261008_1803.dump（UTC命名，对应10-09 02:03北京时间）。

白皮书Draft目标GMP≤15min/2h、RD/Analytics≤24h/8h；MDM SOP为最近24h/60min，均是目标，不是实测。每日dump不能直接满足15min；本项目不实施WAL/备份改造。

## 最小权限与未覆盖项

调查用prometheus SSH与既有sudo；数据库以postgres核对目录与台账，但全部SQL显式BEGIN READ ONLY，statement_timeout=8s，仅SELECT。**调查权限不作为服务账号模板**。直接授权证据：lims_reader/gmp_reader对meta四表有SELECT；两仪器etl_log主要只给ETL写角色，尚缺专用监控SELECT；未验证这些读账号登录/继承的完整权限。

未来需专用角色，仅CONNECT/USAGE+指定表/列SELECT；不继承ETL角色、pg_read_all_data/pg_read_server_files、不授通用sudo。raw命名的etl_log属于运维元信息例外，不许可业务raw扫描。运维meta只读范围及访问记录已于2026-10-10获D07确认；本项目按普通运维辅助推进，不新增GMP合规流程。

本轮未访问其他用户管理器、Windows计划任务/厂商系统、VM/IT备份平台；未证实恢复记录不存在于外部受控档案；未做故障注入或真实角色浏览器验收。已发现缺口必须可见。

## 证据登记与复核方法

| 证据号 | 调查方法和范围 | 已获得结果 |
|---|---|---|
| E01 | systemctl list-timers --all/list-unit-files(timer/service/path)、相关cat/show；prometheus --user | 7自定义timer；历史/模板/用户服务见上表；系统failed=0 |
| E02 | 当前用户及root crontab；sudo ls /var/spool/cron/crontabs；/etc/crontab、cron.d及periodic目录；rc.local/anacron/atq | spool只有prometheus；root无crontab；5条有效业务cron；无rc.local/anacrontab；atq未安装 |
| E03 | docker ps -a（无容器）；/etc/systemd/user与prometheus用户配置；/opt部署目录 | 未发现容器调度；用户旧LIMS服务；未查所有用户管理器 |
| E04 | Linux /opt 527个py/sh/yaml文件有界静态搜索，排除env/凭据、venv、git、tests、备份、构建、alembic | 未发现APScheduler/Celery beat等运行入口；while True命中是读取/轮询逻辑，不据其推定调度 |
| E05 | 三实例information_schema、pg_roles/直接grants、pg_settings；READ ONLY、8s超时 | 实际台账结构、直接SELECT、WAL off；不执行迁移、DML/DDL |
| E06 | RD/GMP meta.etl_run按job+instance最近记录及7天分组；watermark；错误按run/time汇总；两仪器etl_log最近6条 | 上述运行事实；RD校验588/最新84；GMP最近窗口错误0，不宣称历史从无失败 |
| E07 | journal限当天、每unit25条；instrument-alert近7天15条；文件tail限定25行 | 完成、质量warning、10-08夜班失败；不是全量日志审计 |
| E08 | NAS State/Logs/Checksums/Alerts/Daily顶层及白名单子目录；读取最新2份≤2MB既有checksum CSV | 两仪器心跳、已有hash范围、外部记录；未重算hash/扫描全部原始文件 |
| E09 | 本机备份目录stat；MDM脚本/SOP；发布校验文件名称；恢复命名记录搜索 | dump产物及已有校验记录；SOP不代表演练完成 |
| E10 | PORTS.md、Mac lsof 8025/5125、LaunchAgent及Hub路由文本；Linux ss/systemd/nginx | 候选8025/5125未见监听/登记/引用；/ops/未注册；未分配或保留端口 |
| E11 | Hub access/apps/session母本；MDM security/auth/session代码；各ETL说明/实际脚本/配置 | SYS_ADMIN按角色、统一会话可复用；文档旧时刻/旧水位与实际有差异 |
| E12 | Git rev-parse/status --porcelain --untracked-files=no | 下表相关Mac/Linux HEAD一致；Linux跟踪文件无改动，不证明ignored配置或部署构建一致 |

2026-10-09调查时Linux/Mac核实HEAD（当前发布SHA见RELEASE_20261010）：

| 项目 | 完整SHA |
|---|---|
| rd-lims-etl | e11460a4c8635f444a3c7dc1d749206f575bf5ec |
| rd-lucullus-etl | fdc1638ea28c36c31dd70f6be6db87f93188ada0 |
| rd-nova-etl（Linux nova-etl） | 1f7613f785a1d30185427ed649743de1e0433f20 |
| rd-vicell-etl（Linux vicell-etl） | 1d05b50083e51a06a56e1fa0041e2ae7e3d07985 |
| qc-lims-etl | 8e52a174c19849286e536ab4e5e451857e8a382b |
| cmc-instrument-ingest | 930111136cf2ce970d09b29699c737729f033c71 |
| cmab-mdm-platform | 47e1405ffc0387885ad1ebeae5e40a72b17628f8 |
| cmab-hub | 39342a88c58bc2f7d27e2a96096fd0096bd2a722 |

另核实Linux cmc-schema-migrations=9e78966b9e22bec632eb7d9c0a31a6eb72b0df39、training=d9463fb2188a5db8bd28af652af6f55db31bd985（未在此声称两者Mac一致）。该调查时本项目尚无.git；后续10-10已发布，版本见RELEASE_20261010。

## E13 — 2026-10-10开发期间的有限只读复核

未重做全量运行调查。只读确认Linuxsystemd版本255、Nova单元终止证据及manager/process的invocation字段；确认QC开始/结束标记带同一INVOCATION_ID且有journal游标，当前QC10-10 04:00:00.747–04:03:30.603有单元完整退出证据（约209.856s）。本次没有重新查询对应16条台账，不将单元退出单独写成全管道验收通过。

读取QC/Nova实时TimersCalendar与主机Timezone：QC04:00、Nova12:05/16:20，主机Asia/Shanghai。MDM备份脚本本地核对目录为/home/prometheus/cmc_backups/mdm；程序清单已纠正，不使用项目目录下不存在的backups路径。源读取、设备checksum/heartbeat和结束标记代码已实现；专用身份未接入运行，实际覆盖仍以此前调查及未验证限制为准。

本地登记清单16条：10个在用组、5个未接入外部/历史源、1个归档旧QC条目。代码不是新增生产入口或实际接入率。手工/未上线对象仍在上述调查表登记，未增设虚假周期。


## E14 — 本地通知配套完成（不代表Linux已接入）

2026-10-10按用户授权，在各所属仓本地为10个在用顶层任务补齐结束通知：systemd为QC、Vi-CELL、Nova、仪器day/night、MDM每日备份、心跳巡检共7组；cron为Lucullus、RD LIMS、培训同步共3个原顶层脚本（RD LIMS的3条计划共享入口）。只改通知与培训隔离/失败保护；原业务命令、User、timer内容和已有告警静态对照保持。Hub本地注册/ops，共享迁移接本地唯一链尾。

没有重新查询源台账或更新Linux部署，原10-09/有限10-10事实保持日期边界；真实采集接入率、源证据覆盖及5个外部来源缺口不因本地代码而改变。通知的Linux身份/送达和最终读取权限未验收。

## 2026-10-10 用户补充的Biacore备份现状

用户确认Biacore备份目前由各设备工作站上的自动任务执行，目标为NAS；后续拟统一纳入cmc-instrument-ingest管理。本条来源为用户说明，不是本轮实际访问工作站核查的结果；不能据此认定历史Biacore目录仍对应在用工作站、校验完整或恢复可用。各工作站具体计划、任务身份、在用设备与NAS目录对应仍待核实。首页将外部来源和已停用任务分别默认收起，保留登记和缺口；当前10个Linux在用组保持主区。集中接管未执行，不新增重复的在用顶层任务。

## E15 — 2026-10-10 Linux上线真实读取

最终服务身份已读到10个在用顶层组：Lucullus7条、RD LIMS21、QC3、Vi-CELL14、Nova14、日班归档14、夜班7、MDM备份7、巡检7、培训同步7（7天有界窗口）。2026-10-10 17:28北京时间快照6项执行成功，Lucullus执行完成有校验提醒，3项备份/归档执行完成但完整性或恢复验证不足；夜班部分最新心跳已被其他批次覆盖，保留范围缺口。5个外部源仍未知，旧QC保留停用。此为现有证据读取，不是本轮主动执行任务。

实际cron与7个timer时刻保持，3个cron顶层脚本及7个systemd成功/失败观察通知已发布，原User/ExecStart及旧OnFailure告警保留。最终只读角色/沙箱、10个真实producer ACK及拒绝测试通过；下一次自然源任务通知端到端仍待验收。两库迁移、培训空表与各仓完整SHA权威见RELEASE_20261010，不用上面的旧调查版本认定当前上线状态。


## E16 — 2026-10-11 MDM逐份验证接入及实测

P16已确认并实施。MDM源备份仍为原生PG16.15 :5433的cmab_mdm，每日02:00 timer；新增Docker PG16.15独立验证service/path为L08派生检查，不增加第二张备份顶层卡片、不改源备份时刻。当前备份账号只读基线覆盖38张应用表、当前大对象0个，无范围缺口；没有新增账号授权。

最新每日产物（本地10-11 02:03:44、UTC文件名10-10_1803）已实际完整恢复并清理。恢复9.276秒、恢复库约23MB、临时目录约80MB、结束内存样本49.8MiB，镜像约157MB；不是容量峰值或未来耗时保证。该旧备份缺同snapshot基线，因此恢复通过、完整性仍未验证。身份、SHA、权限、版本与验收权威见RELEASE_20261011_BACKUP_VERIFY。

下一次自然每日备份会自动生成同snapshot基线并触发验证，完整自动链路待2026-10-12自然运行验收；不主动执行每日正式备份。新报告只归本份产物，不用其刷新仪器/其他库验证状态。此前10个在用组/5个外部源/1个旧QC范围保持，其他来源未补恢复证据。

## D17 设备归档展示调整（2026-10-12）

L06/L07仍是实际日/夜调度父任务和通知来源，但首页替换为ingest-vicell“Vi-CELL 文件归档”及ingest-nova“Nova FLEX2 文件归档”。每台合并02:00/11:45/16:00历史，保留父Invocation、模式和独立SHA清单，不改源程序、times或NAS策略。公开10项Linux在用、5项外部、1项停用仍保持；内部另保留2个父来源。当天只读核对：Vi-CELL02:00清单50行/11:45为1行/16:00为11行均MATCH且两端64位指纹一致；Nova02:00为2行MATCH，白天两份有效空清单表示无新增。这些不是全历史重新校验或恢复演练。
