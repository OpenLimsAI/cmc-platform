# QAP 数据库设计必要复核记录

2026-09-16｜只读证据，非上线验收。范围：现有代码、中央迁移链、本机 cmc_analytics 结构/计数/权限汇总。**未连接 Linux、未下载 Linux 业务数据、未写数据库。** 未展示 `.env` 密码，未提交或推送 Git。

## 1. 本机查询结果

通过 `docker exec rd_pg psql -X`，显式 `BEGIN READ ONLY` 查询 catalog/information_schema 及汇总；不读取/导出业务明细。

| 项目 | 本轮结果 |
|---|---|
| 数据库 / revision | cmc_analytics / cmc_analytics_qad_phase1 |
| dim 已有表 | channel_dict、employee_master、equipment_master、method_master |
| staging 已有表 | stg_batch、stg_sample、stg_test、stg_result、stg_nova_run、stg_vicell_run、stg_process_daily |
| mart 已有对象 | 15 个视图：dim_batch/dim_employee/dim_method、5 个 fact_*、7 个 v_*；没有正式质量 fct 表 |
| 其他保留对象 | manual.sample_result、quality.quality_data/import_history |
| meta/snap_mdm/snap_gmp | 未发现表（此处不推断其他环境或其他对象种类） |
| stg_sample / stg_result 行数 | 19,752 / 122,722 |
| quality_data / import_history 行数 | 84,757 / 14 |
| stg_sample 批号超32 / 缺失 | 5 / 73 |
| quality_data 批号超32 / 缺失 | 0 / 0 |
| result 缺 test / 有test缺sample | 0 / 0 |
| 三张 LIMS staging PK | 均为(source_system,source_id)，关联携带 source_system |
| method_master PK | method_code VARCHAR(32)；无 method_id |
| 旧 quality 唯一性 | 各表只有自身 id 主键；文件索引非唯一，无完整业务防重约束 |
| lims_admin 有效权限 | stg_result 可读可写，staging 可 CREATE |
| lims_reader/quality_user | stg_result 可读、无 INSERT/UPDATE/DELETE，staging 无 CREATE；不是全库权限验收 |

`mart.dim_batch` 从 staging.stg_batch 取 batch_key、project_id、batch_number、batch_year、设备/工艺/起止时间等，是工艺维度视图，不能因名字就认定所有质量批次完整登记。

源样品含 sampled_dt/received_dt/authorised_dt/status 等，检测含 method_code/status/authorised_dt，结果含 source_test_id、attribute、value_num/value_str、unit、judgement、result_authorised_dt 等；时间多为不带时区的 timestamp。仅存在授权时间不等于确认其批准业务语义。

## 2. 代码证据与影响

| 证据位置 | 核验事实 / 设计影响 |
|---|---|
| backend/app/repositories/quality_repository.py:37–63 | 三表 JOIN、batch_number AS batch_id；只筛数值非空/项目非空，没有批准状态过滤；未投影 test/result 源键 |
| backend/app/services/dashboards/release_service.py:30–61 | 按 is_pct 给规格乘100、仅按 attribute_name 分组；未按方法/单位/样品隔离，不能视为正式统计口径 |
| backend/app/services/specs.py:191–235 | 中文样品映射、项目别名/后缀回退及默认规格；无有效期/批准文件/版本 |
| backend/app/config/attribute_map.csv | 静态共525条原名，15条填写映射、14个唯一标准名；与 specs.py 的38个规格键仅3个交集。这不是今日实库映射覆盖率 |
| 同CSV:10–12 与 specs.py:24–26 | nrce_main_peak_pct vs nr_ce_main_peak_pct、rce_purity_pct vs r_ce_purity_pct、nghc_pct vs r_ce_nghc_pct，业务等价待确认 |
| specs.py:20–23 | 百分比限度混用明显可疑：一项为25、同类多为比例小数；这里只登记风险，不修改或确认真实限度 |
| backend/app/services/mapping/data_type.py:56–66 | 未配置检验类别可关键词推断 release/stability；不是源批准标记 |
| backend/app/services/stats/mixed_models.py:150–168；tests/test_stats_regression.py:256–260 | 组名匹配和旧算法对照不足以独立证明分组排序不影响结论；本轮未改算法或重跑测试 |
| backend/app/core/database.py:20–26 | default_transaction_read_only 连接选项是可配置防线，不等于账号最小权限 |
| backend/app/core/security.py:8–15；api/v1/router.py:5–10 | 只有可选 API key 函数且未见挂载；路由只有meta/release，无MDM/导入 |
| frontend/src/App.tsx:51–55；services/api.ts:17–36 | 稳定性/相似性占位，无MDM会话拦截器；旧batch_id字段仍需适配 |

本地 `.env` 使用 lims_admin 来自交接快照；本轮未输出配置内容。账号实际写权限已用 catalog 函数独立复核。

## 3. 旧项目复用边界

参考项目是 `../quality_analysis_dashboard`，不是 Linux 的另一套 quality-analysis-platform。

| 旧代码 | 可复用 / 需替换 |
|---|---|
| analytics/data_loader.py:240–278 | 模板/列名别名/重复列检查可复用 |
| dashboards/import_dashboard.py:62–95 | 校验预览、错误下载、文件变化使预览失效可复用 |
| etl/import_service.py:63–83,210–260 | SHA256、事务锁、事务失败回滚思想可复用 |
| import_dashboard.py:21–48 | 共享口令、临时目录删除文件不满足 MDM 员工身份及原文件留档 |
| import_service.py:124–148 | 丢弃行号、过滤非数值/无效时间点、统一声明QC_LIMS不适合正式模型 |
| import_service.py:223–255 | 按文件名 DELETE/INSERT，旧id不稳定；同名同内容仍重写，只有文件历史不足以恢复结果版本 |

保留旧看板读取可用；未来回填与写入口切换需窗口和对账，不能长期两个写口各自覆盖。

## 4. 中央迁移和培训风险证据

- `../cmc-schema-migrations/README.md`、`SOP.md`：所有结构经中央 Alembic；共享表先查所有使用方；Mac验证后Git同步。
- `alembic.ini:18–26`：正式/培训共用 cmc_analytics versions 路径。
- 本地静态50个迁移、单一head=qad_phase1；一期文件仍未跟踪，父节点 manual_metric_gluc。已提交链与本机实库存在该未提交差异。
- 一期迁移本轮只读文件指纹 SHA256：`bbe2838dc2afb57b7d8db1d249526f673f00b4bdc40e80b8107476791cfc2880`，后续执行前应重新比对。
- 一期迁移 `20260916_cmc_analytics_qad_phase1.py:15–70`：创建旧quality表和qad角色，IF NOT EXISTS不查结构匹配，importer能DELETE，downgrade拒绝自动销毁。
- baseline method表 + `20260910_cmc_analytics_mdm_to_dim.py:47`：原位迁移并保留method_code主键。
- `../rd-batch-registry/scripts/training_db_reset.sh:26,32–44`：从正式整库复制含数据，停止的只有批号培训服务，终止培训库连接、换库并删除旧库；本地文档称每日00:00。Linux定时任务是否启用**未复核**，不得当成现行生产事实。

Linux正式/培训版本、三表结构一致性及旧quality未在Linux创建来自本次用户交接快照，不作为本轮新增实查结果。

## 5. 本次修订范围与尚未验证项

修订 DDM/SAD/项目CLAUDE，新建实施清单和本记录，归档更新前的两份V2.0。业务代码、密钥、旧数据、中央迁移文件均未修改；Git未首次提交状态保持。

本轮只做文档一致性/链接检查及独立交叉评审，不用运行旧算法单测冒充新模型验证。新表、真实最小权限、MDM接入、导入并发/恢复、三类统计业务口径、Linux部署均待实施与验收。

文档检查结果：本项目当前五份Markdown的相对链接存在、代码围栏配对、换行检查通过；两名独立审阅者核查了实码事实及迁移方案，所提追溯/关联/旧写口切换问题已补齐。此检查不涉及新模型运行测试。
