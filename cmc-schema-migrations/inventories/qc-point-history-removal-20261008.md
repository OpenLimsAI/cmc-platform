# QC 水点本地历史表移除 — 2026-10-08

负责人明确要求删除 `s_samplepoint_history`、同步配套代码，并通过 migration 在 Mac/Linux 执行。保留此前创建迁移及实施证据，不将其改写为从未建过历史表。

## 迁移范围与实际结果

- 删除 revision：`gmp_qc_point_nohist_20261008`，前驱 `gmp_qc_meta_seq_20261008`。
- 注释修正 revision：`gmp_qc_point_note_20261008`，前驱为删除 revision；只修正水点当前镜像仍提及旧历史的注释。
- Mac 和 Linux 均通过 `dbmig cmc_gmp upgrade <明确revision>`，最终 `current` 为 `gmp_qc_point_note_20261008`。
- `raw_gmp_lims_labvantage` 普通表由 16 张变为 15 张；删除本地历史表、写历史触发器、两个关联函数及表附属对象。没有使用 CASCADE、stamp、手工 DROP 或重写已发布迁移。
- 保留水点主表 361 行、39 个源字段、两列 ETL 时间、主键、索引与既有查询权限。主表完整记录校验值和结构、其他 raw 表数量、meta 台账以及所有角色密码校验值/属性均与备份前一致。
- Mac 补齐前驱密码迁移时，在同一事务内恢复私有备份中的原 gmp_etl verifier，最终现有密码不变；同时补齐前驱规定的两条日志序列 USAGE。Linux 已完成前驱，本次角色密码和存续对象 ACL 无变化。
- 后续水点更新仅保留当前镜像，不再记录本地旧版本。既有 UPSERT 的完整变更审计治理不能据此声称已解决；这是负责人明确选择的当前范围。

## 备份与恢复验证

两端备份含恢复所需 raw 结构、水点主记录和历史数据；其余 raw 表仅包含定义、不包含其业务数据。私有目录 0700，文件 0600。

| 环境 | 备份目录 | 历史 / 主表行数 | dump SHA256 |
|---|---|---|---|
| Mac | `/Users/qingcheng/code/qc-lims-etl/backups/point-history-removal-20261008-160824/` | 361 / 361 | `b720453ffc0fbc5b7cb36df2acc5ac727b781488b4c7a61cb4d6ef1fc7269684` |
| Linux | `/opt/backups/qc-lims-etl/point-history-removal-20261008-1613/` | 361 / 361 | `75cb8c35cf3fe17a99ba6e0cb0bcb705a24039bd2cc07afd933ea8fa515d9c40` |

两份 dump 实际恢复至一次性 PostgreSQL 16 容器，完整记录校验值匹配、原写历史触发器恢复成功。记录校验统一 UTC，避免集群时区差异。各端 `manifest.json` 记录 dump 校验值、历史行数/记录哈希及已实际恢复标记；`before.json` 与 `final-result.json` 保存删除前后对账。凭据 verifier 仅留在 Mac 私有备份，不入 Git 或文档。

删除 migration 强制要求私有清单，先核验恢复标记和 dump SHA256，再锁定主表与历史表核对备份后无新增变化，随后使用 RESTRICT 删除。失败整体回滚。回退不创建空历史表冒充恢复，须审查备份和期间新增数据，再通过新恢复 migration 处理；不能整库覆盖现有业务库。

## 消费者与验证

全局代码检索未发现 ETL、staging 或用水看板直接查询本地历史表，运行依赖仅为数据库触发器。QC 调整迁移验证脚本和说明，保留旧迁移保护测试，并验证当前删除结果。

已实际通过：9 项既有 ETL 回归；隔离库中的备份恢复、无备份拒绝、未知依赖回滚、Mac 前驱补齐与原密码保留、Linux 现有凭据不变、删除后水点写入、重复编号隔离、缺映射不丢样品、原结果不变和最终注释版本。

Linux 实际 ETL 账号的只读 readiness 为 ready：15 张源/目标表、五张 staging SQL/字段/权限通过。raw 为 gmp_etl，分析库为 lims_admin，Oracle 为 QC_LIMS_READONLY。QC 水位仍为空。本次未执行 ETL、Oracle 全量读取或 staging 重建。

QC timer enabled/active，下次 `2026-10-09 04:00:00 CST`，service inactive、无首次启动时间；未调整其他项目定时器。

## Git 发布

按 Mac 验证 → GitHub → Linux 干净工作区快进同一提交执行。删除实现提交 `4c720b7342c56acb3b8bcace1f41ed56fe34f8ee`，注释修正提交 `09199495a4906c4f109af458a800e27491009b8a`；QC 首次配套提交 `f51a9852f0c445f7fe82b1c5ad09dfc7a0c84509`。最终发布记录及验证脚本继续按相同流程同步。迁移仓库原有未提交修改不纳入本次发布。
