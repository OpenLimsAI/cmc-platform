# 03 · 数据来源与字段约定

> 版本：0.8｜日期：2026-10-09｜状态：现行消费契约；数量和源调查为标明日期的历史证据。

## 0. 本次范围和位置调查

两页整理撤销独立质量页，相关页面、scope和专用API已移除。2026-10-09已只读核实正式点位LOCATIONID→S_LOCATION房间名称关联；当前staging的locationid为空，房间名称/厂区层级未提供。361点与167位置的观察、Mac宽表覆盖对账、上游字段分工和历史边界见[两页整理设计](changes/20261009-two-page-dashboard.md)第3–4节。用户本轮明确暂停位置接入，等待对照表及数字含义，不改变以下五表消费边界。

## 1. 数据链与来源识别

早期规则编制依据为 QC ETL `5c30e61b996a1b3111a1be6a43b3fa948cdf2f0b`；该SHA仅代表当时规则，不代表当前ETL或部署版本。当前看板只消费下述五表及两条规则，数量、数据覆盖、QC作业状态按对应环境执行证据判断，见 [STATUS](STATUS.md)。

```text
Oracle LabVantage → qc-lims-etl
  → cmc_gmp.raw_gmp_lims_labvantage
  → cmc_analytics.staging.stg_lv_*
  → 本项目只读 API → Hub 中的制药用水看板
```

早期Mac验收使用2026-09-29 XLSX派生staging；2026-10-09 Linux发布记录已核对Oracle ETL生成的staging。当前运行环境以已核实装载证据设置STAGING_DATA_ORIGIN（legacy_xlsx/oracle_etl/unverified），不能按Mac/Linux名称猜来源。raw已更新不等于staging已更新；结果最大日期、装载时间和来源截止是不同概念。环境配置不会自动检测或证明来源。

## 2. 消费表

| 表 | 用途 | 约束 |
|---|---|---|
| `stg_lv_test_result_wide` | 主看板最终参数结果 | 强制 QC 来源和两条水系统规则；不是全部检项完整报告 |
| `stg_lv_sample` | 样品状态、取样点、时间与追溯 | 样品总量的状态/日期口径需独立标注 |
| `stg_lv_workitem` | 检测项目与状态追溯 | 用完整检项键关联 |
| `stg_lv_dataset` | 方法、阶段、数据集追溯 | 用完整数据集键关联 |
| `stg_lv_dataitem` | 完整参数链核对 | 包含 LES 中间过程，不直接用于最终趋势 |

所有表强制 `source_system='gmp_labvantage'`。主看板还限制sdcid=Sample，再限制 `samplesubtypeid` 为注射用水、纯化水、纯蒸汽，`selection_rule` 为 `water_system_v1` 或 `water_conductivity_method1_numeric_v1`。未知新规则被当前主看板排除；没有通用未知规则诊断页（GAP-03），新增规则需先核对并兼容适配。

## 3. 粒度与关联键

样品标识：`(source_system, s_sampleid)`。

结果复合主键来自 staging 迁移：

```text
source_system, sdcid, keyid1, keyid2, keyid3,
paramlistid, paramlistversionid, variantid, dataset,
paramid, paramtype, replicateid
```

检测项目和数据集的全部关联均包含 `source_system`，防止不同来源的相同编号串联。检测项目键为 `(source_system,sdcid,keyid1,keyid2,keyid3,workitemid,workiteminstance)`；数据集键为 `(source_system,sdcid,keyid1,keyid2,keyid3,paramlistid,paramlistversionid,variantid,dataset)`。

已核对：宽表含 `workitemid`，数据集表同时含 `workitemid`、`workiteminstance`。现有只读追溯步骤为：完整结果键 → 同键 dataitem；去除参数三列得到数据集键 → dataset；使用 dataset 的完整检项键 → workitem；使用来源及样品 ID → sample。代码按表主键定位，并检查关联是否存在及宽表与dataset的workitemid是否一致；缺失/不一致返回gaps。唯一性依赖实际表主键，当前没有另做多条关联或全部桥接历史检查。

原始检项与数据集桥接由上游 raw `sdiworkitemitem` 完成；dataset 使用 DISTINCT ON，宽表使用 LATERAL LIMIT 1，按检项实例排序选择关联。staging 保留的是选定关联，不包含所有原始桥接历史。OP-13 先验证这条已有链路，仅在无法支持目标口径时才提出上游兼容扩展；本看板不为追溯直接扫描 raw。

## 4. 主看板字段

| 分类 | 来源字段 | 消费语义 |
|---|---|---|
| 样品 | `s_sampleid,sample_name,samplesubtypeid,samplestatus` | 样品 ID、名称、水类型、状态；不是业务批次 |
| 取样点 | `samplepointid,locationid`及六个samplepoint映射字段 | 内部ID/源位置ID；现场编号/名称来自当前LIMS主表；系统/回路/历史有效期未知 |
| 检项方法 | `workitemid,workitemdesc,paramlistid,paramlistversionid,variantid,paramid,paramtype,replicateid` | 方法版本、阶段和参数保持分别可识别 |
| 结果 | `displayvalue,enteredvalue,transformvalue,unit,valuestatus` | 原显示值、来源数值与状态；派生数值与原值分别输出 |
| 时间 | `collectiondt,sample_eventdt,receiveddt,sample_createdt,trend_dt,trend_dt_source` | 趋势日期及其来源；回退值不能标为原始采样时间 |
| 信号 | `releasedflag,dataitem_reportflag,spec_reportflag,u_statisticflag` | 来源证据；不能凭单一标志重新选择最终值 |
| 来源规则 | `selection_rule,selection_reason,sdidataitemid` 及复合键 | 保留结果选择依据与来源定位 |
| 装载 | `_etl_loaded_at`，启动校验必需字段 | staging 装载时间，不是正式源数据导出截止 |
| 可选批号 | `u_batchno` | API已增加别名 `batch_number`；为空正常，不删水样 |

## 5. 历史覆盖记录

| 类型 | 2026-09-29 水系统 v1 结果行 | 后续方法1数值补充行 | 历史记录推得的结果行合计 |
|---|---:|---:|---:|
| 注射用水 | 38,878 | 1,541 | 40,419 |
| 纯化水 | 40,284 | 0 | 40,284 |
| 纯蒸汽 | 3,596 | 321 | 3,917 |
| 合计 | 82,758 | 1,862 | 84,620 |

2026-10-01 记录第五表共 85,373 行，其中另含产品 pH 753 行；不能把第五表总行数称为水系统检测次数。补充行与原结论代表同一次检测，样品数未因此增加。2023 年以来历史入选样品数为注射用水 5,890、纯化水 7,198、纯蒸汽 419；这是日期化证据。

## 6. 已知缺口与预检

- 2026-10-02历史记录曾发现3个特定0681纯化水样品未入宽表；该数量不作当前缺口断言。变更前质量页只查询特定候选名单，该功能现已删除；最终参数仍需CoA核对后由上游版本化补规则（OP-03）。
- 历史水系统 v1 有 1 行缺 `samplepointid`；当前编号/名称已接入；系统与历史有效期仍未知（OP-01）。
- `collectiondt` 在历史快照全空；`trend_dt` 主要来自 `eventdt`，少量回退；事件时间的业务语义待确认（OP-02）。
- 历史完整参数链曾有少量记录关联不到样品；该记录不能推断为宽表也存在相同缺口。主看板追溯基于宽表入选行；孤立参数链专项诊断不在收缩后的页面范围，不能将无法确认水类型的记录混入水样计数。
- 启动预检核对必需字段/类型、SELECT 权限和固定来源/规则配置；权限不足或结构不兼容明确报错。真实行数/样品数/空值、数值格式、单位与方法分布在首次数据预检及受限诊断中记录，不要求每次启动重复全量画像。
- 用只读连接/事务获取查询结果；检查索引和查询计划，新增索引归共享迁移链。

## 7. 证据与责任

- [staging 代码](../../qc-lims-etl/etl/staging.py)、[staging 建表迁移](../../cmc-schema-migrations/alembic/versions/cmc_analytics/20260929_cmc_analytics_qc_lv_staging.py)。
- [本地首次装载](../../qc-lims-etl/docs/local-staging-load-20260929.md)、[数值补充记录](../../qc-lims-etl/docs/water-numeric-companion-20261001.md)、[筛选原则](../../qc-lims-etl/docs/staging-filter-principles.md)。
- 上游结构/数据/规则问题归 qc-lims-etl 与迁移链；本项目承担消费适配、质量提示、分析规则和结果追溯。

## 8. 独立质量功能撤销后的边界

按用户2026-10-09指令，三scope质量页面/API已删除，历史范围由Git及此前变更记录保留。宽表之外的方法缺口仍归OP-03，由QC ETL查证后版本化处理；功能删除不代表数据问题已解决。趋势继续保留源值、未绘图原因及追溯gaps，不新增候选参数查询。

## 9. 导出原始数据表的范围

用户所需“相应的原始数据表格”指当前趋势筛选和比较组对应的已入选最终结果记录，保留 staging 中的结果原文、源单位、日期及日期来源、状态、方法版本、选择规则与完整 source_key。它不是 Oracle/raw 全库导出，也不是包含全部 LES 中间参数的表。派生数值和解析/绘图状态单独列明，不覆盖源值；未能绘图的入选记录保留并注明原因，图点数和表格结果行数分别计数。


## 10. 取样点当前映射与历史边界

2026-10-08源调查记录确认：MBTK.S_SAMPLEPOINT.LOCATIONLABEL为现场编号，SAMPLEPOINTDESC为描述，主键S_SAMPLEPOINTID；当时361行、39列不是后续固定断言。当前看板消费samplepoint_code、samplepoint_name、samplepoint_mapping_source、samplepoint_mapping_scope、samplepoint_source_moddt、samplepoint_extracted_at六个字段。字段由QC ETL和所属迁移链提供，保留samplepointid内部ID。

current_master表示所观察到的当前主表映射，不是采样时点历史映射；MODDT和抽取时间不代表业务生效期。同号不同内部ID不合并。未知系统/回路/历史有效期明确提示，不能从编号或source_instance拆分推断。

早期“原始快照没有点位主表/零命中”的调查已被后续取样点接入记录覆盖；这些记录仅按当时日期解读。结构升级依据见 [QC升级记录](../../qc-lims-etl/docs/water-point-upgrade-20261008.md)；看板后续发布与验收见本项目STATUS/docs/09，不用上游旧记录替代本项目现状。

旧质量接口曾统一追加映射提示（历史GAP-01）；该接口已随功能收缩删除。当前趋势映射说明按current_master分别展示，不等于系统/历史映射已完成。

## 11. 2026-10-09只读更新核查与mart边界

Linux实际连接为localhost:5432/cmc_analytics、lims_reader，只读消费以上五表。15个raw同步和一个staging刷新作业今日全部成功，错误数0；staging于04:03:48完成，五表的_etl_loaded_at均为事务起始04:00:20.759041，不能把这个装载标记当作刷新结束时间。

context.max_result_at实际为宽表授权水样MAX(trend_dt)=2026-09-18上海零点；主要来源为样品eventdt，不是数据库同步截止或检验完成时间。stg_lv_sample已有10月9日纯化水Initial样品；9月18日之后水样当前为Initial/InProgress/Received/Cancelled，未进入Completed/Reviewed及参数规则入选范围。代码日期不是写死，也未停止每日刷新。API当前source_cutoff/context_id仍为空，新鲜度未自动联动ETL台账；顶部提示按用户指令暂移除。

本轮用lims_reader只读核对mart.v_qc_report_snapshot_preview、v_qc_report_result_preview、v_qc_numeric_result_preview、v_qc_investigation_preview，Linux均0行。它们读取snap_gmp.qc_report_snapshot和staging.qc_report_candidate，是按snapshot_id限定的报告候选预览，validation_status当前限定development_preview；不是每日五表刷新自动生成的全量水样mart。数值预览排除定性/删失和重复规格候选，不能用它代替全部水样计数或趋势原文。

可展示这些视图用于明确版本的报告候选核对；当前水系统看板继续既有staging契约。后续可考虑在现有staging之上建专用水系统mart视图，集中水类型/状态/结果规则/日期/计数口径，并保留来源键、原文和方法1数值/结论去重；正式切换前另确认文档、兼容范围与真实对账，通过cmc-schema-migrations实现。普通视图不额外保存数据或自动加速；仅在性能实测需要时再设计物化视图及刷新顺序。以上为建议，未新建视图或更换数据源。
