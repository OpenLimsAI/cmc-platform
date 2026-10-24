# 水系统 mart 普通视图：Mac 创建与验收

2026-10-09｜v1.0｜用户已授权；SQL/迁移/隔离测试及 Mac 数据验收完成；尚未提交、切换看板或发布 Linux。

## 需求与范围

用户要求开始创建水系统 mart。沿用已确认设计：仅三类水、Reviewed、两条已批准 v2 最终结果规则；保留原字段、数值与文字结论；电导率 μS/cm、TOC ppb、pH 无量纲；微生物最终报告 <1 仅绘图为0；不建历史快照。完整契约见cmc-water-system-dashboard/docs/11-water-mart-design.md。未知方法和0681纯化水的3个样品仍待报告核实。

数据库归 cmc_analytics.mart，共享结构归 cmc-schema-migrations。qc-lims-etl 仍负责 staging，日常刷新后普通视图直接读取已提交 staging，不增加 mart 刷新作业。当前看板仍消费五张 staging；本轮没有切换后端、前端或导出。

## 对象与实际数量

| 普通视图 | 粒度与作用 | Mac 行数 |
|---|---|---:|
| v_water_result | 一个最终参数结果，完整12键及全部70个源字段保留 | 84,497 |
| v_water_numeric_trend | 具备绘图资格的精确数值或删失报告结果 | 39,339 |
| v_water_sample | 一个具有入选最终结果的来源/样品，数值与结论不重复计数 | 13,462 |
| v_water_review_item | 一个结果、样品或样品方法核对事项 | 129 |

入选最终结果：WFI40,452行/5,898样品；PW40,125/7,144；PS3,920/420。结果类型为精确29,642、删失9,697、文字45,109、未解析49。未解析原文保留，不提取文本里的数字。

核对事项为49个unparsed_result及80个no_selected_final_result，后者聚合为25种水类型/方法/版本组合。80表示样品方法事项，不是80个独立样品或80次漏检；可能包括无已发布结果、排除状态或未覆盖方法。没有样品属性冲突、绘图元数据冲突、样品身份错误、未支持选择规则、单位冲突或数值缺单位事项。正常文字结论不因单位为空进入缺单位事项。

## 单位和原值

原unit完整保留为source_unit；analysis_unit、display_unit、unit_status、unit_rule_version仅为派生解释，数值不换算。

| 趋势范围 | 行数 | 解释 |
|---|---:|---|
| 电导率 | 7,936 | 1,179业务确认补单位；6,757规范为μS/cm |
| TOC | 9,435 | 业务确认补ppb |
| pH | 3,352 | analysis_unit=NULL，display_unit=无量纲，status=dimensionless |
| 微生物cfu/ml | 7,071 | 沿用源单位，与cfu/100ml分开 |
| 微生物cfu/100ml | 6,076 | 沿用源单位 |
| 不挥发物mg | 5,469 | 沿用源单位 |

可绘图行数从按非空源单位的25,373变为39,339，新增13,966均为原有精确结果，没有新增最终结果。9,697条微生物<1的plot_value=0、bound=1、operator=<、exact_numeric_value=NULL；1,143条精确1的plot_value和exact_numeric_value均为1。0不是实测零或统计替代值。

## 文件和迁移

- alembic/versions/cmc_analytics/20261009_analytics_water_mart.py：analytics_water_mart_20261009，接analytics_water_final_20261009，创建四普通视图、注释和已存在 reader 角色的SELECT。
- alembic/versions/cmc_analytics/20261009_analytics_water_mart_perf.py：analytics_water_mart_perf_1009，接上述revision，优化样品计数；先前已应用迁移保持不变。
- tests/test_water_mart_sql.py：临时 PostgreSQL 表/视图隔离测试；连接退出前回滚，不改真实数据。

执行入口为共享仓库 `./dbmig cmc_analytics upgrade analytics_water_mart_perf_1009`；本机最终current已确认analytics_water_mart_perf_1009。培训库在此前本机盘点不存在，本轮未创建或测试；Linux未执行，后续须按固定Git提交和当地数据独立验收。SQL支持正式/培训库名，不能将此解释为培训已验收。

## 实际验证

15项SQL隔离测试全部通过，覆盖审核/来源/水类型/规则过滤、单位补充与冲突、pH无量纲、微生物<1/1/<=1/<10、元数据不一致、未解析、点位日期缺失、样品属性冲突、重复号与方法/阶段隔离、数值/结论去重和方法头事项粒度。执行：在qc-lims-etl使用 `.venv/bin/python ../cmc-schema-migrations/tests/test_water_mart_sql.py`，需要该环境已有psycopg及dotenv；测试从共享仓库.env读取连接，不输出凭据。

真实数据在REPEATABLE READ READ ONLY事务核对：全部70个源字段及完整键双向EXCEPT ALL差异均0；来源键84,497唯一，样品13,462唯一；第四/第五表和其他staging行数未变化；此前19个mart视图定义指纹均未变化。实际lims_reader可查询四视图，SELECT为true，INSERT/UPDATE/DELETE/TRUNCATE/REFERENCES/TRIGGER均false，PUBLIC没有权限。

样品统计初版因三次连接出现约7.7秒耗时；追加迁移改为一次按完整属性分组，再用每样品的属性组合数判定一致性。不同属性样品仍排除出计数视图并生成review事项，不能任取首条/MAX隐藏冲突。优化前后全部样品列在同一只读事务双向比较差异0。最终EXPLAIN ANALYZE实测：按水类型样品计数返回3行，56.437ms；WFI真实点位SP-00000101、2026自然年范围的趋势返回160行，2.569ms。另一次按该点位最近有数据日期回溯12个月读出229行，3.56ms。以上仅本机单次查询，不能推定Linux或并发容量。

## 备份、恢复和后续边界

本机备份与敏感验收文件仅留qc-lims-etl/backups/water-mart-20261009，不提交Git：schema-before.dump已通过pg_restore清单检查，SHA256=3f422a49bce2c969f95fe278b2e1edd7b3554f2f978b5e4c8ba49286a567155a；before.json保存原revision、staging行数与已有mart指纹，verification.json保存最终只读核对，sample-optimization-compare.json保存优化前后对账。目录/文件权限收紧为本人访问。

本轮仅增加/替换派生视图，无raw/staging写入，不运行ETL、Oracle同步或水位操作。应用回退可保留视图；如确需降级，须核对数据库依赖和应用消费者，视图删除使用RESTRICT，不CASCADE。备份恢复不自动执行。

后续仍需看板适配器切换及单位筛选/比较组重建、真实身份下图表和全部导出一致性验收；再commit/push、Linux固定版本迁移和当地数据验收。尚未执行步骤不记为已完成。
