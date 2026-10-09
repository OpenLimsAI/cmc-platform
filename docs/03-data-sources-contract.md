# 03 · 数据来源与字段约定

> 版本：0.4｜日期：2026-10-02｜状态：Mac 已实现，验收部分完成；Linux 未发布。

## 1. 已核实的代码与日期化证据

文档编制核对的 QC ETL 本地完整 SHA：`5c30e61b996a1b3111a1be6a43b3fa948cdf2f0b`。以下字段和规则来自其代码及迁移文件；行数来自上游装载记录，2026-10-02 未完成数据库实时复核。后续开发必须重新检查真实结构、权限、行数与日期覆盖。

```text
Oracle LabVantage → qc-lims-etl
  → cmc_gmp.raw_gmp_lims_labvantage
  → cmc_analytics.staging.stg_lv_*
  → 本项目只读 API → Hub 中的制药用水看板
```

Mac 数据来源为 2026-09-29 生产 XLSX 快照。不能称为实时 Oracle 数据；结果日期最大值、ETL 装载时间和源导出截止含义不同。

## 2. 消费表

| 表 | 用途 | 约束 |
|---|---|---|
| `stg_lv_test_result_wide` | 主看板最终参数结果 | 强制 QC 来源和两条水系统规则；不是全部检项完整报告 |
| `stg_lv_sample` | 样品状态、取样点、时间与追溯 | 样品总量的状态/日期口径需独立标注 |
| `stg_lv_workitem` | 检测项目与状态追溯 | 用完整检项键关联 |
| `stg_lv_dataset` | 方法、阶段、数据集追溯 | 用完整数据集键关联 |
| `stg_lv_dataitem` | 完整参数链核对 | 包含 LES 中间过程，不直接用于最终趋势 |

所有表强制 `source_system='gmp_labvantage'`。主看板再限制 `samplesubtypeid` 为注射用水、纯化水、纯蒸汽，`selection_rule` 为 `water_system_v1` 或 `water_conductivity_method1_numeric_v1`。未知新规则先列为待核对，不自动混入已有分析组。

## 3. 粒度与关联键

样品标识：`(source_system, s_sampleid)`。

结果复合主键来自 staging 迁移：

```text
source_system, sdcid, keyid1, keyid2, keyid3,
paramlistid, paramlistversionid, variantid, dataset,
paramid, paramtype, replicateid
```

检测项目和数据集的全部关联均包含 `source_system`，防止不同来源的相同编号串联。检测项目键为 `(source_system,sdcid,keyid1,keyid2,keyid3,workitemid,workiteminstance)`；数据集键为 `(source_system,sdcid,keyid1,keyid2,keyid3,paramlistid,paramlistversionid,variantid,dataset)`。

已核对：宽表含 `workitemid`，数据集表同时含 `workitemid`、`workiteminstance`。现有只读追溯步骤为：完整结果键 → 同键 dataitem；去除参数三列得到数据集键 → dataset；使用 dataset 的完整检项键 → workitem；使用来源及样品 ID → sample。各步校验宽表与数据集的 `workitemid` 一致性、存在性和唯一性；不一致或缺失时明确返回来源缺口，不能自动选第一条或交叉连接。

原始检项与数据集桥接由上游 raw `sdiworkitemitem` 完成；dataset 使用 DISTINCT ON，宽表使用 LATERAL LIMIT 1，按检项实例排序选择关联。staging 保留的是选定关联，不包含所有原始桥接历史。OP-13 先验证这条已有链路，仅在无法支持目标口径时才提出上游兼容扩展；本看板不为追溯直接扫描 raw。

## 4. 主看板字段

| 分类 | 来源字段 | 消费语义 |
|---|---|---|
| 样品 | `s_sampleid,sample_name,samplesubtypeid,samplestatus` | 样品 ID、名称、水类型、状态；不是业务批次 |
| 取样点 | `samplepointid,locationid` | 源编号与位置编号；名称/系统/回路映射尚待核实 |
| 检项方法 | `workitemid,workitemdesc,paramlistid,paramlistversionid,variantid,paramid,paramtype,replicateid` | 方法版本、阶段和参数保持分别可识别 |
| 结果 | `displayvalue,enteredvalue,transformvalue,unit,valuestatus` | 原显示值、来源数值与状态；派生数值与原值分别输出 |
| 时间 | `collectiondt,sample_eventdt,receiveddt,sample_createdt,trend_dt,trend_dt_source` | 趋势日期及其来源；回退值不能标为原始采样时间 |
| 信号 | `releasedflag,dataitem_reportflag,spec_reportflag,u_statisticflag` | 来源证据；不能凭单一标志重新选择最终值 |
| 来源规则 | `selection_rule,selection_reason,sdidataitemid` 及复合键 | 保留结果选择依据与来源定位 |
| 装载 | `_etl_loaded_at`，上线前核对真实结构 | staging 装载时间，不是正式源数据导出截止 |
| 可选批号 | `u_batchno` | API 如需使用适配为 `batch_number`；为空正常，不删水样 |

## 5. 历史覆盖记录

| 类型 | 2026-09-29 水系统 v1 结果行 | 后续方法1数值补充行 | 历史记录推得的结果行合计 |
|---|---:|---:|---:|
| 注射用水 | 38,878 | 1,541 | 40,419 |
| 纯化水 | 40,284 | 0 | 40,284 |
| 纯蒸汽 | 3,596 | 321 | 3,917 |
| 合计 | 82,758 | 1,862 | 84,620 |

2026-10-01 记录第五表共 85,373 行，其中另含产品 pH 753 行；不能把第五表总行数称为水系统检测次数。补充行与原结论代表同一次检测，样品数未因此增加。2023 年以来历史入选样品数为注射用水 5,890、纯化水 7,198、纯蒸汽 419；这是日期化证据。

## 6. 已知缺口与预检

- 纯化水 3 个已发布样品的特定通则 0681 电导率方法未进入宽表，需实际报告确认后由上游版本化补规则（OP-03）。
- 历史水系统 v1 有 1 行缺 `samplepointid`；名称与系统映射未核实（OP-01）。
- `collectiondt` 在历史快照全空；`trend_dt` 主要来自 `eventdt`，少量回退；事件时间的业务语义待确认（OP-02）。
- 历史完整参数链曾有少量记录关联不到样品；该记录不能推断为宽表也存在相同缺口。主看板追溯基于宽表入选行；质量核对另列完整链的孤立记录，显示无法确认的水类型与来源，不将其混入已确认水样计数。
- 启动预检核对必需字段/类型、SELECT 权限和固定来源/规则配置；权限不足或结构不兼容明确报错。真实行数/样品数/空值、数值格式、单位与方法分布在首次数据预检及受限诊断中记录，不要求每次启动重复全量画像。
- 用只读连接/事务获取查询结果；检查索引和查询计划，新增索引归共享迁移链。

## 7. 证据与责任

- [staging 代码](../../qc-lims-etl/etl/staging.py)、[staging 建表迁移](../../cmc-schema-migrations/alembic/versions/cmc_analytics/20260929_cmc_analytics_qc_lv_staging.py)。
- [本地首次装载](../../qc-lims-etl/docs/local-staging-load-20260929.md)、[数值补充记录](../../qc-lims-etl/docs/water-numeric-companion-20261001.md)、[筛选原则](../../qc-lims-etl/docs/staging-filter-principles.md)。
- 上游结构/数据/规则问题归 qc-lims-etl 与迁移链；本项目承担消费适配、质量提示、分析规则和结果追溯。

## 8. 数据质量的两种集合

已入选结果集合用于主看板，其取数范围由水类型、状态、上游两条规则和用户筛选确定。宽表缺少的方法结果无法从这个集合独立发现。

候选覆盖核对集合由同一 QC 来源的 sample → dataitem 建立：sample 的 source_system/s_sampleid 对应 dataitem 的 source_system/keyid1，并限定 sdcid=Sample；参数数据集按完整数据集键校验。按水类型、Completed/Reviewed 状态、可确认日期和已核对的候选方法身份限定，再用完整结果键与宽表比较。已知方法缺口的候选还须满足发布、dataset=1、Standard、无计算/转换错误及未被计算排除等基础质量条件；不满足条件的记录列为排除原因，不一律算缺失最终值。

候选记录仅是“待核对参数”，不等同于最终报告值；缺口也不能由全部中间参数与宽表的行数差计算。首期先覆盖 OP-03 的已知缺口，候选方法/版本/阶段/参数名单需来源证据，不能用通用“结果/结论”正则扩展。

日期缺失记录不落入指定月份/季度；点位缺失记录不归属指定编号。质量页为这些记录提供独立未归属分区，明确所用水类型/状态与未应用的时间/点位条件，显示数量与来源范围。无样品的孤立链不能确定水类型时仅作为来源链诊断，不能算为三类水样缺失数量。

## 9. 导出原始数据表的范围

用户所需“相应的原始数据表格”指当前趋势筛选和比较组对应的已入选最终结果记录，保留 staging 中的结果原文、源单位、日期及日期来源、状态、方法版本、选择规则与完整 source_key。它不是 Oracle/raw 全库导出，也不是包含全部 LES 中间参数的表。派生数值和解析/绘图状态单独列明，不覆盖源值；未能绘图的入选记录保留并注明原因，图点数和表格结果行数分别计数。


## Mac 实施状态（2026-10-02）

V0.3 的工作设计和历史复核记录保留用于追踪；当前事实以 [Mac 验收记录](acceptance/mac-20261002.md) 和 docs/10 新决定为准。基础应用已运行，不能据此将所有验收项或 Linux 发布登记为通过。


## 点位编号更正（2026-10-02）

当前 SP-xxxxxxxx 为 LIMS 点位内部 ID，未确认等同现场水点编号。源点位主表 SAMPLEPOINTDESC 等字段应优先核对；源样品 LOCATIONPATH 实际存位置描述。详见 [字段复查](water-point-field-investigation-20261002.md)。前次分析库/MDM无映射的调查不能代表LIMS没有主表。


## 2026-10-08 水点编号升级

正式 Oracle 只读核实 MBTK.S_SAMPLEPOINT.LOCATIONLABEL 为现场编号，SAMPLEPOINTDESC 为描述；361 行、39 列，S_SAMPLEPOINTID 主键。WFI002/WFI003 各有两个内部 ID，筛选/比较组继续保留内部 ID，不按现场编号合并。当前主表字段经 QC ETL 和共享迁移链进入 staging，看板只读消费并导出映射来源、源 MODDT 和抽取时间。current_master 仅为观察到的当前映射，不能证明历史采样时点的名称或系统。

方案与验证记录见 [QC 升级方案](../../qc-lims-etl/docs/water-point-upgrade-20261008.md)。OP-01 的编号和名称来源已查明；系统、回路及历史有效期仍未完成。代码、Mac 数据验收及 Linux 状态以该记录为准。
