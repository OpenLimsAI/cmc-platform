# 数据模型与权威来源

> 版本：V0.7｜日期：2026-10-10｜状态：已提交/push并部署Linux真实监控及Hub入口；服务、采集、权限和培训空表核验通过。真实MDM角色浏览器及下一次自然任务端到端通知待验收；详见 RELEASE_20261010。Mac保留模拟预览。

## 已核实源结构（E05/E06）

下表为必要字段摘录，不是统一源表DDL；22:10另以只读catalog复核字段与类型。

| 来源 | 可适配字段与语义 | 特别约束 |
|---|---|---|
| RD/GMP meta.etl_job | job_name/source_system/owner/schedule_cron/is_active | 不能当实际调度清单，RD只注册一job而Lucullus仍运行 |
| RD/GMP meta.etl_run | run_id/job_name/source_instance/mode/run_started_at/run_finished_at/status/rows_read/rows_written/rows_errored | RD大写状态、GMP小写；SUCCESS仍可能有VALIDATION；源run_id非全局唯一 |
| RD/GMP meta.etl_watermark | job_name/source_system/source_instance/target_table/last_success_ts/last_run_id/updated_at | 无source_table/watermark_col；last_success_ts语义因任务而异 |
| meta.load_error_log | error_id/run_id/error_time/source_system/source_instance/target_schema/target_table/error_type/error_message | 仅必要脱敏摘要/数量，不复制offending_data和业务context |
| Vi-CELL etl_log | id/run_started_at/run_finished_at/status/files_scanned/files_loaded/files_skipped/files_errored/watermark_before/watermark_after | 位于raw命名schema但为运维表，单表列授权，不访问业务run明细 |
| Nova etl_log | 上述加rows_inserted/rows_skipped/rows_conflict/rows_unresolved | partial可exit0；stage日志独立 |
| 心跳JSON | machine_name/run_tag/last_run_time/last_run_finished/last_success_time/backup_status/files_failed/alerts/duration_sec/max_silence_hours | 单机单文件被day/night覆盖；NAS与本地冲突单列 |
| checksum CSV / JSONL | match_status、算法字段、相对路径、run_tag、event_time/event_type/severity | Match/MATCH归一化但原文保留；只代表清单范围，空文件不判全量 |
| systemd/cron/journal及backup stat | unit/计划/开关/Persistent/随机延迟/Result/exit；路径引用/大小/mtime | trigger不等于success；mtime不等于业务截止点 |

RD与instrument时间列为timestamptz；GMP meta列为timestamp without time zone。实查GMP会话TimeZone=Asia/Shanghai，state.py用CURRENT_TIMESTAMP写入、pg_connect未另设时区，凌晨台账与journal时间一致。适配器按本次已核实Asia/Shanghai解释旧naive值，同时保存source_timezone/timezone_basis；未来配置变化或历史范围不能确认时为unknown，不统一当UTC，也不修改源列。

## 逻辑对象与物理实现（Linux四表已建；逻辑对象不等同独立表）

归属cmc_analytics.ops_monitor，持久化已由D06确认；培训复制影响见ARCHITECTURE。源权威继续在源系统，统一模型只保存最小观测、证据引用及判断，不复制完整ETL台账。

| 对象 | 关键字段及约束 |
|---|---|
| task_definition | task_key（稳定URL安全ID）、host、environment、kind、source_project、source_job_name、source_instance、source_database/table、owner、enabled_expected、schedule/timezone、rule_version、evidence_mapping；配置Git版本化，不提供网页编辑 |
| task_relation | parent_task_key/child_task_key、relation_type=execution/data_dependency、required、valid_from/to；无环；归档与ETL为data_dependency |
| update_event | event_id/task_key/source_scope/source_run_id或invocation_id/mode、producer_identity、started_at/finished_at、received_at、delivery_status/processing_status、snapshot_id；只存通知与处理结果，不能把消息状态当源成功；去重键以实际来源身份确定，无run_id时保留关联歧义 |
| collection_batch | snapshot_id、start/finish、collector_version、inventory_version、trigger_kind(event/daily_safety/startup/manual)、trigger_event_ids、expected/received_sources、collection_status；有失败批次也发布可用部分 |
| task_occurrence | task_key、scheduled_for、rule_version、activation_kind、source_invocation_id、parent_occurrence、association_status；唯一键(task_key,scheduled_for,rule_version)用于计划窗口 |
| task_observation | observation_id/snapshot_id/task_key/occurrence_ref、collected_at/source_at、source_status、标准四维状态、reason_codes、rule_version、evidence_refs；追加式，不覆盖历史失败 |
| run_reference | source_host/database/table/run_id、job_name/instance、mode、start/finish、指标、association_confidence；不造跨源唯一run_id |
| evidence_reference | evidence_id、source_kind、允许的locator、range、observed_at、parser_version、content_digest（脱敏摘要的哈希）、redacted_excerpt；客户端只接ID，不接任意路径 |
| backup_observation | task_key/artifact_ref、scope、size/mtime、业务cutoff可空、execution/artifact/integrity/restore状态、verification_scope/method/time/ref；恢复验证不能由文件存在推导 |
| access_audit_log | access_id/request_id、actor_type(user/service)、actor_id、已验证的actor_sub/username/roles快照、task/source范围、query_window、rows_returned/result、snapshot/rule_version、access_time；不存JWT/密码/DSN |

collector源查询用服务身份单独记录来源/时间窗/结果/行数，不虚构成浏览器管理员操作；用户API访问另记录经验证身份，未登录/伪造请求仅记录未验证主体与失败原因，不信任token自称角色。访问记录不写源库。

内部时间UTC、API带时区ISO8601、UI Asia/Shanghai；unknown数值用null，不用0替代。NULL source_instance保留其全局语义，不能猜成某工作站。键含主机/环境/源任务，hostname不代替host标识。

建议查询索引(task_key,collected_at DESC)、occurrence唯一键、snapshot_id、source引用范围；历史分页按ID/时间游标且限窗口。源已有RD etl_run(job_name,run_started_at)、load_error_log(run_id,error_time)索引已查到；本轮没有更改索引。观测90天、访问记录180天已确认，本地ORM已实现，正式/培训均已应用20261010_ops_monitor_v1；不自动删除源日志或备份。

采集source只读；自身追加由专用writer，API读取本schema并写自己的访问审计/更新请求；schema迁移及最小列权限另行通过共享迁移链。无SQLite/新库/新身份表/新设备权威源。实施前核验源字段变化，不为迎合统一模型改源台账。

## MDM恢复验证报告契约（P16已确认）

报告是MDM生成的文件证据，不是monitor新建业务台账。建议版本化字段：schema_version、verification_id、task_key/host/environment、source_run_id或明确源执行引用、artifact（basename/size_bytes/sha256/backup_started_at/backup_finished_at）、baseline（snapshot_basis/captured_at/table_counts/schema_summary/migration_revision/extensions/coverage）、verification（started_at/finished_at/target_pg_version/image_digest/restore_status/integrity_status/checks/exclusions/failure_step/reason）、cleanup_status。

执行、完整性、恢复、清理分别记录；建议验证流程状态pending/running/passed/failed/incomplete与监控健康状态分开。只有同产物全部必要检查通过才映射verified；读不到为unknown，可读但没有验证证据为not_verified。历史备份baseline不可得用null并显式缺口，不造0行或补造历史版本。

monitor只接脱敏摘要和有界检查结果，保存在既有Run/证据JSONB；完整业务行、凭据及原始restore日志不进入浏览器。SHA由MDM负责计算，monitor仅核对已有摘要身份及可信导出，不读取dump重算hash。服务身份、Git/镜像版本及scope帮助回溯；报告原子写入，禁止读取半写文件。物理路径及权限见ARCHITECTURE和MDM runbook；字段检查已实现，复用既有JSONB，无新增数据库迁移。真实报告生成及权限验收见RELEASE_20261011_BACKUP_VERIFY。

## V1实际物理模型

| 表 | 实际键与用途 |
|---|---|
| ops_monitor.collection_batch | id UUID文本、at timestamptz、payload JSONB；一次观测不可变 |
| ops_monitor.run_reference | (id, observed_at)联合主键；task_key、at、payload；按每轮追加观察版本，后续完成不会改写旧视图 |
| ops_monitor.update_event | id、at、status、lease_at、payload、snapshot_id；UID+来源event_id去重，状态pending/processing/done |
| ops_monitor.access_audit_log | id、at、payload；管理员/API拒绝和服务采集分别记录 |

任务/主机/环境/来源绑定在config/tasks.json，不建第二套主数据。子步骤、水位、备份检查和最小证据嵌入JSONB；上述逻辑对象不代表已经分别建表。V1使用人可读的状态/原因文本，没有独立reason_codes字典、task_occurrence表；迁移revision已发布为20261010_ops_monitor_v1。确认漏跑只在监控首次采集后的计划窗口追加source_kind=schedule的历史引用，start为计划时刻，界面标“计划”，不假称实际启动。

ORM在backend/app/store.py；共享迁移权威在cmc-schema-migrations/alembic/versions/cmc_analytics/20261010_ops_monitor_v1.py，接analytics_water_mart_perf_1009并离线/隔离数据库核对ORM；Linux正式及培训库已应用目标revision。实际源字段、角色列授权和原始业务表拒绝访问均已核验，见RELEASE_20261010。运行数据90天/审计180天的自有清理代码在成功日兜底之后执行，不清理源台账或备份。已完成隔离数据库迁移测试和两库正式迁移、真实持久化与历史API读取。培训四表为空，下一次自然培训复制后仍需复核。

## D17 设备归档关联

复用既有JSONB，不建新表或迁移。配置新增按设备的派生任务和内部来源可见性；原ingest-day/night标识继续接收真实flex2ingest通知及保留父历史，新ingest-vicell/ingest-nova从已读父批次子结果派生。设备Run保留archive_mode、parent_run_id、父计划启动时刻及设备实际耗时，证据只导出固定标记和校验计数，不展示业务文件路径或内容。日/夜原标识不改作设备标识，不混淆旧历史。
