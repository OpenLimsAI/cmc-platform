# gmp_etl 密码变更与 QC 定时启用（2026-10-08）

## 范围与授权

负责人已明确授权修改 Linux `gmp_etl` 密码，并已授权 QC 每日北京时间 04:00 自动执行。此前只读盘点没有发现现用项目配置使用该账号，活动连接为零；未登记的外部客户端仍无法从服务器配置完全排除。

变更仅旋转 `gmp_pg:5434` 的现有 `gmp_etl` 密码。账号权限、其他账号及业务数据不变。QC 的 `PG_DSN` 单独改用该账号的新密码；Oracle 与分析库 `lims_admin` 配置不变。Mac 现有数据库账号密码不随 Linux 同步修改。

## 迁移入口

- 前置 revision：`gmp_qc_point_raw_20261008`。
- 目标 revision：`gmp_etl_password_20261008`。
- 新增文件：`alembic/versions/cmc_gmp/20261008_cmc_gmp_etl_password.py`。
- 入口仍为 `./dbmig cmc_gmp upgrade gmp_etl_password_20261008`。
- `GMP_ETL_PASSWORD_FILE` 指向执行者拥有的 0600 普通文件；包含单行、至少 24 字符的新密码。每个环境独立配置，不将密码放入 Git、命令参数或发布记录。
- 执行前确认目标 `cmc_gmp` 和现有非超级用户 `gmp_etl`。迁移先生成 SCRAM-SHA-256 verifier，再执行密码变更；不将明文密码发送为 SQL 文本。
- 离线 SQL 模式被拒绝，防止凭据进入 SQL 导出文件。以后从基线建立新环境并经过本 revision 时，也必须明确提供本环境的密码文件。

## Mac 隔离验证（已完成）

使用临时 PostgreSQL 16 容器，构造前置 revision 的隔离测试库并通过真实 `dbmig` 执行。没有修改 Mac 现有 `gmp_pg` 或其他数据库。

已验证：缺少密码文件及文件权限不合格时拒绝变更；拒绝离线 SQL；新密码登录成功、旧密码登录失败；其他账号 verifier、原权限及测试数据不变；使用旧 verifier 的专项回退成功。测试容器和临时测试凭据已清理。

## Linux 执行与回退要求

固定已发布 Git SHA，确认工作区干净、当前 revision 和账号活动连接；私有备份 QC 原 `.env`、该账号原 verifier 及 `cmc_gmp`。其他账号 verifier 不需要备份或读取。

生成随机新密码，写入受限文件后通过上述 migration 执行；原子更新 QC `.env` 的 `PG_DSN`。分别核对 `dbmig current`、账号登录、权限及数据未变、其他项目配置和调度未变。通过只读 `python -m scripts.check_linux_readiness` 后才能启用 QC timer；不立即手动运行完整 ETL。

以下密码 downgrade 只适用于当前 revision 正好是 `gmp_etl_password_20261008` 的情况；若已经执行后续权限迁移，先专项评审后续 revision，不直接跨越降级。如需回退本次密码变更，先停用 QC timer，核实备份对应本次执行并协调任何已经改用新密码的客户端。`GMP_ETL_ROLLBACK_VERIFIER_FILE` 指向受限的原 verifier 文件，再执行 `./dbmig cmc_gmp downgrade gmp_qc_point_raw_20261008`，并恢复对应 QC 原配置。此专项回退不适用于其他 revision，不需要整库恢复。

实际 Linux 执行 SHA、备份目录、验收结果及定时首次触发时间记录于 [QC 运维文档](../../qc-lims-etl/docs/05-ops-deployment.md)。结构版本与凭据配置完成不代表首次生产数据同步已完成。


## Linux 启动检查发现的序列授权缺口

密码迁移后只读预检查确认 `gmp_etl` 在 `meta.etl_run_run_id_seq` 与 `meta.load_error_log_error_id_seq` 上均无 USAGE/SELECT/UPDATE。该缺口此前已存在：账号有对应表 INSERT，但创建运行记录或错误记录时不能调用序列取得 ID。

追加 revision `gmp_qc_meta_seq_20261008`，仅授予以上两个既有序列的 USAGE，先核对其归属列分别为 `meta.etl_run.run_id` 和 `meta.load_error_log.error_id`。不授予序列 UPDATE，不修改其他序列、表权限或数据。执行入口 `./dbmig cmc_gmp upgrade gmp_qc_meta_seq_20261008`。不自动撤销供客户端运行所需的权限，降级须专项审查。

Mac 隔离环境另已验证：两条 QC 序列的 nextval 成功；序列 UPDATE 及其他序列 USAGE 保持拒绝。测试夹具使用与 Linux 相同的既有 meta schema USAGE。
