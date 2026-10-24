# QC报告预览迁移记录

日期2026-10-09。用户要求先落实计划再继续数据层开发；正式Oracle只读。

新增GMP两张调查当前镜像及专用只读NOLOGIN角色；新增分析快照/源行/候选表、四个普通mart预览视图及专用追加NOLOGIN角色。没有改变既有五张staging、QAP或水系统看板消费者接口。分析对象不能作为已签发报告或统计方法已验证的依据。

## Mac实际执行

- 目标cmc_gmp：127.0.0.1:5434，gmp_qc_point_note_20261008 → gmp_qc_incident_20261009。
- 目标cmc_analytics：127.0.0.1:5432，analytics_qc_point_20261008 → analytics_qc_preview_20261009 → analytics_qc_null_20261009 → analytics_qc_catalog_20261009。
- 迁移前核实新增表不存在，保存结构备份和SHA256于相邻qc-lims-etl仓库backups/qc-report-preview-20261009/。仅新增对象/索引/角色；不是全库业务行备份。
- 通过dbmig执行明确revision；未手工绕过迁移链。事件源现场核实83列/主键，Oracle只读查询；装载Mac raw分别77/222行，转换错误0。
- 六个限定原样品、3050条来源行保存为版本bf38b25a-1ec9-4785-94fd-58fdeaaaf29c，84候选=50可预览+34待核对；不是全量报告结果交付。
- 已执行：有效只读角色查询、写角色最小权限、lims_reader四视图读取、SQL NULL选择合同、重复失败回滚、已提交版本追加拒绝、行数上限、已有文件保护、数值完整键去重核验；qc-lims-etl的35项单元测试通过。

完整数据契约、证据文件、命令、模板/代码哈希与业务缺口见相邻项目`qc-lims-etl/docs/report-preview-runbook-20261009.md`。版本目录要求按snapshot_id读取，source_cutoff是混合逐表窗口的保守观察时间，不能解释为Oracle SCN或报告签发时点。

## 尚未执行

两仓库未commit/push；Linux未拉取、迁移、装载或部署，培训库未同步。独立登录账户/成员资格与密码未创建或修改，Mac开发使用既有管理连接SET ROLE验证；正式运行需另配置最小权限登录。原调度没有改动，预览CLI未加入定时任务。

未来Linux发布须先备份、确认Git SHA和已有版本，执行上述明确迁移，再发布含17表配置的ETL，独立核验数据、权限与消费者。保留历史迁移与已提交快照；本新增链downgrade明确拒绝通用删除回滚，不自动drop证据对象。PDF对账、历史规格缺口、调查采纳、全量覆盖及业务验收仍未完成。

本仓库工作开始时存在用户未提交改动（.env.example、README、SOP、alembic.ini、env.py、dbmig、部署说明及AGENTS.md），此次均保留，仅新增四份迁移及本记录。
