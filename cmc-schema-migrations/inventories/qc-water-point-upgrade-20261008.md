# QC 水点结构升级记录

2026-10-08 用户确认升级。追加两条迁移：`gmp_qc_point_raw_20261008`（15 张 LIMS 镜像之外新增水点变更历史）及 `analytics_qc_point_20261008`（样品和宽表六个可空映射字段）。保留所有原字段、数据和已发布 revision；不自动降级。

正式 Oracle MBTK.S_SAMPLEPOINT 的 39 列和主键经 QC_LIMS_READONLY 只读验证，361 行；WFI002/WFI003 各有两个内部 ID，新增字段不改变主键和结果分组。源字段类型沿用项目映射：VARCHAR2→text，DATE→timestamptz，NUMBER→numeric。

PostgreSQL16 隔离环境通过 dbmig 实际执行两条迁移，验证历史不可更新/删除/清空、源变更留旧新值、重复编号及缺点位不丢行、定向补充幂等和原结果不变。Mac dbmig 升级成功，完整备份及对账证据见 qc-lims-etl/docs/water-point-upgrade-20261008.md；只补新增映射列，57,406 样品和 85,373 结果的全部原字段哈希不变。

新增 raw 表继承 s_sample 的 SELECT/INSERT/UPDATE ACL；历史只继承 SELECT，写入由受限 SECURITY DEFINER 触发器负责。不改变现有 staging 表授权，新增列沿用已有表权限。Linux 正式分析库与培训库需同步同一 revision，但培训库不得装载正式数据。

本次提交仅包含新增迁移与本记录；工作区已有总纲/环境/README/SOP 等未提交修改保留，不混入本次发布。Linux 数据、权限和部署结果由升级后的追加记录确认。

## Linux 验收追加

2026-10-08 通过固定代码 SHA e036101431d788bd1dd806cc2e96890e7b7c9d40 与迁移 SHA 017249a2cebde65d0c95cf1f7ecff30ffe5d46ff 发布。备份 `/opt/backups/qc-lims-etl/water-point-20261008/` 的正式 raw、分析库和培训库均有可读 custom dump 及 SHA256SUMS。

cmc_gmp 当前 gmp_qc_point_raw_20261008；cmc_analytics 和 cmc_analytics_training 当前 analytics_qc_point_20261008。六个新增字段均存在，培训库只升级结构。正式源 MBTK.S_SAMPLEPOINT 装载 361 行、错误 0，变更历史 361 行；reader 仅 SELECT，ETL 镜像写权限及历史禁止直接写权限实查符合方案。原 Linux 样品和 QC staging 结果为空，未装载原14表，不能称检验结果已到位。

原周期 ETL PG_DSN 密码认证失败、分析库写密码未配置，本次一次性装载使用迁移管理员连接；timer 保持 disabled/inactive。看板仅完成 Mac 代码/36 项后端/3 项前端测试及只读 API/export 验证，GitHub 登录与实际用户浏览器验收仍待完成，Linux 未发布。
