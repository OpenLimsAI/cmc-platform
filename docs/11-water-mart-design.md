# 11 · 水系统 mart 设计与实现契约

版本：0.3｜日期：2026-10-09｜状态：用户已确认；四普通视图、共享迁移及Mac数据验收完成；看板切换和Linux发布未执行。

## 1. 目标、职责和范围

水系统已审核最终结果的趋势、样品计数、追溯和导出采用一致的业务数据契约。staging负责来源链、最终参数筛选及已确认的源值/绘图元数据；mart将这些结果组织为水系统消费模型，并集中比较组、数值资格、样品计数和异常口径。看板保留身份、筛选、交互及文件渲染职责。

数据归cmc_analytics.mart，不新建业务库或raw对象；共享结构由cmc-schema-migrations管理。业务定义由本看板文档维护；qc-lims-etl继续提供staging，不将看板统计塞进Oracle/raw抽取。现有质量报告候选预览四视图保持独立，不作为本水系统mart的输入。

首版覆盖注射用水、纯化水、纯蒸汽，当前两页总览/取样点趋势及其筛选、追溯、导出。系统/回路/厂区映射、采样计划覆盖率、限度判定、OOS调查采纳、Cpk/Ppk和正式放行用途不在首版确认范围。未知方法不通过mart扩展成最终结果。

## 2. 已核实现状与设计前置

2026-10-09本机cmc_analytics，以lims_reader、REPEATABLE READ READ ONLY查询：

| 项目 | 已核实结果 |
|---|---:|
| 水系统最终结果 | 84,497行，全部Reviewed |
| water_system_v2 | 82,635行 |
| water_conductivity_method1_numeric_v2 | 1,862行 |
| 有入选最终结果的样品 | 13,462个 |
| 精确数值 | 29,642行 |
| 删失报告值 | 9,697行 |
| 文字结论 | 45,109行 |
| 未解析报告值 | 49行 |
| 数值/删失且点位、日期、源单位非空 | 25,373行，其中精确15,676、删失9,697 |

本机水样结果均有内部点位ID、现场编号及趋势日期；同一样品的水类型/点位/名称/日期/状态组合冲突数为0。此检查仅为当前快照，不保证以后恒无缺失。

13,966条精确数值缺源单位：TOC报告值5,324、TOC结果4,111、pH结果3,352、电导率报告值1,179。以上为源单位空值分布，保留为实施前基线。用户随后确认：电导率统一μS/cm、TOC统一ppb、pH无量纲。mart按§5明确派生分析单位，source_unit保持原值；pH的空单位不再视为单位缺失。其他未确认方法不能类推补单位。

创建前检查的QC/水系统范围仅有v_qc_report_snapshot_preview、v_qc_report_result_preview、v_qc_numeric_result_preview、v_qc_investigation_preview四个QC预览视图，没有专用water对象。创建前dim表名检查未发现专用水点/水指标/单位/规格表；不能据此认定公司其他系统没有这些主数据。Linux本轮状态未核对，v2上游发布为实施前置。

## 3. 首版逻辑对象：先普通视图

| 建议对象 | 一行代表什么 | 主要消费 |
|---|---|---|
| mart.v_water_result | 一个已纳入规则的源最终参数结果，完整12列来源键唯一 | 全部最终原文明细、比较组、导出及追溯入口 |
| mart.v_water_numeric_trend | 一个具备绘图资格的数值或删失结果；不是每日平均 | 点位/方法/版本/指标/单位独立趋势 |
| mart.v_water_sample | 一个已审核且具有入选最终结果的样品，source_system/sample_id唯一 | 总览点位数、年度样品计数，避免数值/结论双计数 |
| mart.v_water_review_item | 一个需核对的结果或样品方法事项，明确entity_grain/issue_type | 未解析、缺单位、来源冲突、方法头无入选最终结果等核对 |

普通视图集中契约，不额外复制结果，不声称自动加速；首版不建日/月均值或物化缓存。按实际查询性能决定索引或后续缓存。v_water_review_item仅作为数据核对入口，首版不恢复此前被删除的独立数据质量页面。

v_water_sample从入选结果构造样品范围，与现行总览一致，不直接把stg_lv_sample所有水样计入。样品属性在当前刷新内应一致；不能用MAX/首条消除冲突。实施时须验证该视图实际唯一性，冲突纳入review并阻断切换/发布，不能静默改变样品数。

review事项按实体粒度分开：结果事项完整source_key；无最终结果事项按source_system、完整样品键、workitemid、paramlistid/version标识方法范围。多个issue可属于同一结果，review行数不是样品数或检测次数。方法头无结果可能是参数未发布、被排除或规则未覆盖，不直接判定漏检/错误。

## 4. 最终结果数据契约

建议v_water_result保留原字段并增加清晰业务别名；最终列清单随实现确认，任何删列先盘点消费者。

| 类别 | 必须表达的字段/语义 |
|---|---|
| 身份 | source_system与完整源键sdcid/keyid1/keyid2/keyid3/paramlistid/paramlistversionid/variantid/dataset/paramid/paramtype/replicateid；sample_id；sdidataitemid |
| 样品/水点 | water_type、sample_status、samplepoint_id（内部身份）、samplepoint_code/name（当前主表属性）、mapping_source/scope及源时间 |
| 方法/指标 | workitemid、方法ID/版本/阶段、参数ID/类型/重复号；不按指标显示名跨方法合并 |
| 原始报告 | display_value、source_unit、enteredvalue、transformvalue；原值保持不变 |
| 分析单位 | analysis_unit、display_unit、unit_status、unit_rule_version；pH的analysis_unit为空且unit_status=dimensionless |
| 结果解释 | result_kind、result_role、exact_numeric_value、result_operator、result_bound |
| 绘图 | plot_value、plot_value_rule、plot_eligible、not_plotted_reason |
| 时间 | trend_at、trend_date_source、原始时间字段及staging_loaded_at；日期按Asia/Shanghai解释 |
| 来源/版本 | selection_rule/reason、mart_rule_version；装载时间与来源截止分别表达，不设置历史数据版本或快照ID |

完整来源键是结果身份；普通视图下不新造一个不可反查的自增ID。source_instance当前不在staging，不能凭source_system猜造；若后续多实例并存，先扩充上游身份契约后设计跨实例键。

新mart入口仅纳入QC来源、sdcid=Sample、三类水、Reviewed且selection_rule为water_system_v2或water_conductivity_method1_numeric_v2。未确认的新规则不会自动纳入；未知规则必须可在检查中识别。既有看板v1/v2兼容用于迁移过渡；新mart不默默把v1解释为v2元数据齐备。

## 5. 数值、结论、微生物及单位

exact_numeric_value仅在result_kind=exact_numeric时有值，并验证与批准解析规则一致；文字结论和删失结果此列为空。plot_value直接消费staging已确认派生值，不在前端/PNG另写不同替换规则。方法1数值与文字结论保留为两行，result_role区分用途，样品/数据集计数不按结果行数重复加一。

微生物最终报告值<1/＜1/等价写法：display_value保持原文，operator=<、bound=1、plot_value=0、plot_value_rule=water_microbiology_lt1_zero_v1；exact_numeric_value为空。精确1保留为1。<=1、≤1、<10及其他检项不套用此归零规则。0不是实测零；不自动进入普通均值、SD、Cpk/Ppk。

### 5.1 已确认单位规则（2026-10-09）

用户明确“不需要历史快照，电导率的单位都是μS/cm”，随后确认“TOC的单位都是ppb”“pH按无量纲显示”。这是本轮单位补充的业务依据，不是从结果数值猜单位。规则仅作用于已命中水系统最终结果白名单的相应数值指标，不扩大方法或参数选择范围。

| 指标与首版来源范围 | analysis_unit | display_unit | 规则版本 |
|---|---|---|---|
| 电导率/电导率-方法1/已纳入的0681第一步方法中的结果或报告值；排除文字结论参数 | μS/cm | μS/cm | water_conductivity_unit_us_cm_v1 |
| 总有机碳v1 TOC报告值、v2结果 | ppb | ppb | water_toc_unit_ppb_v1 |
| pH值v1结果 | NULL（无量纲，不是缺失） | 无量纲 | water_ph_dimensionless_v1 |

- 原unit作为source_unit完整保留；不在raw/staging回填。新增analysis_unit/display_unit供分组、坐标、提示及导出消费，数值不乘除、不改变原报告字符串。
- 电导率源单位为空时按已确认业务规则补分析单位μS/cm；源μS/cm、µS/cm、uS/cm的等价写法统一为μS/cm，首尾空白仅在派生时处理。unit_status分别标记business_confirmed或normalized。
- TOC空单位按已确认规则补ppb；ppb/PPB统一为ppb；unit_status记录依据。ppb不在本轮换算成mg/L、μg/L等其他量纲。
- pH空单位明确标记dimensionless，display_unit显示无量纲，分析单位不编造为浓度或电导率单位。实施前检查其源单位是否存在冲突；若出现未确认的非空标记，保留原文并核对，不直接覆盖。
- 源单位若与确认规则有实质冲突，例如电导率出现mS/cm或TOC出现ppm，应标unit_status=conflict，保留原值并进入review；不把数值不变地强行改单位。当前本机电导率数值仅µS/cm或空、TOC全部空，没有实质冲突。
- 文字结论不通过补单位变成数值结果；49条未解析仍保留并标明原因，不因单位明确而提取文本里的数字。
- 其他有源单位的指标沿用来源单位（unit_status=source）；未确认的缺单位仍为missing。首版三项规则可在版本化视图定义中明确登记，规则ID关联本业务确认记录；需扩大为维护字典时另在cmc_analytics.dim走共享迁移。

### 5.2 趋势资格与比较组

比较组仍保留现行九个维度，但单位维度由source_unit调整为analysis_unit：water_type、samplepoint_id、workitemid、paramlistid、paramlistversionid、variantid、paramid、paramtype、analysis_unit。同号不同内部点位、不同方法/版本/阶段分别处理；cfu/ml与cfu/100ml仍分组。

unit_status=dimensionless的pH允许analysis_unit为空并按明确指标身份比较；unit_status=missing/conflict或缺点位时追加完整来源键并禁止趋势聚合，不能与明确无量纲混淆。数值趋势资格要求结果为exact_numeric/censored、plot_value有效、点位/日期有效，并且单位已提供、已按批准规则统一/补充或明确无量纲。

看板单位筛选、坐标标签与提示、PNG和导出均采用同一分析/展示单位；原文表和导出同时显示source_unit及规则依据。旧comparison_group的电导率符号和缺单位分组标识会变化，不能要求这些ID逐字不变；切换时重建比较组、清空旧组选择并明确拒绝失效组，按来源键和数值对账。

本机只读影响核对：电导率空单位精确值1,179条，TOC空单位精确值9,435条，pH无量纲精确值3,352条。补齐后预计新增可绘图13,966条；目前仅按非空源单位判定的25,373条将增至39,339条（精确29,642、删失9,697），最终以新视图实际对账为准。没有新增最终结果或改变84,497条来源键/原值。

## 6. 计数与日期

- 样品数：唯一source_system/sample_id；即使一个检项同时有数值与结论也只计一个样品。
- 方法数据集数：唯一source_system加完整前8列数据集源键；保留现标签，不在检项实例/桥接未核实前称检测次数。
- 结果行数：完整结果键计数；与图点数分开。
- 总览点位数：每种水全部已有入选最终结果中的非空内部ID去重，范围不限当前年度；不是系统数或台账全部水点数。
- 总览年度样品：上海当前自然年1月1日至今天，API上界为明日排他边界；沿用trend_at，缺趋势日期不计年度样品但明细保留。
- 趋势默认近12日历月，可选近3/6个月及自定义日期；不同于总览自然年。日期由一次请求固定后传给查询，不在不同模块分别跨午夜计算。

视图不隐藏固定年度或滚动天数；API用绑定参数查询同一关系。样品计数视图用于总览，附带指标筛选的计数仍应从该筛选对应结果集去重，不能把全样品视图的计数直接当某指标样品数。

## 7. 追溯、异常与覆盖

mart结果完整键 → staging同键dataitem → dataset完整键 →选定workitem实例；sample关联继续保留。水系统过程记录在raw，由受控溯源另查，本看板不扩大访问raw。新mart不修复或掩盖staging选定桥接的历史局限。

未解析原文、缺单位、缺日期/点位、多候选/重复身份、样品属性冲突、未兼容选择规则均应有可检查的计数/事项；异常不是0或正常均值。实际复测/replicate不擅自合并、平均或取最新。

已知电导率-<通则0681>纯化水测定法v1的3个Reviewed样品仍待方法/报告确认。前轮方法头无入选结果清单有25个方法版本/水类型聚合组，不能把25解释为25个样品或25条错误。mart设计可继续，但完整方法覆盖验收仍需逐项关闭。

## 8. 一致性与新鲜度（已确认不建历史快照）

用户已明确本水系统mart不需要历史快照。首版及本轮实施采用普通视图，读取当前staging，不建追加式水结果快照、快照目录、历史版本保留或快照发布流程；既有独立报告候选预览不受此决定影响。

继承五表事务刷新与单查询REPEATABLE READ只读一致性；同一次导出的图/表来自同一次取数。跨请求发生刷新时数据可能变化，沿用比较组dataset_digest检查页面与导出是否一致，不承诺按历史快照ID复现。规则版本继续保留，用于解释数据口径，不等同于历史数据版本。

staging_loaded_at是装载线索，不是Oracle截止或staging刷新结束时点。最新结果日期与同步时间分别展示；若读取QC作业新鲜度，按具体成功staging作业核对。不能用MAX(trend_at)、NOW()或装载时间伪造source_cutoff/context_id；不设置无数据支撑的快照ID。

## 9. 权限、迁移、切换和验收

建视图与授权走cmc-schema-migrations的cmc_analytics链，前置analytics_water_final_20261009与QC v2数据到位。生产/培训库分别核对，不复制本机数据。查询角色仅新视图SELECT；后端继续MDM验签、角色/导出守卫和只读事务，不因mart放宽权限。

顺序建议：确认本草案 → 完整SQL/字段与单元契约 → 共享迁移Mac验证 → 同一只读事务内新旧结果/比较组/趋势/概览/追溯/导出对账 → 看板数据适配器切换 → 固定提交GitHub/Linux迁移及代码发布、当地数据验收。保留旧staging消费路径直至切换验收；回退应用无需删除staging/mart对象。

验收必须覆盖：结果完整键/原值无增减；样品粒度唯一且13,462基线一致；微生物0/1区分、三项批准单位与pH无量纲、源单位保留；新增可绘图范围与按完整来源键对账；分组变化符合单位统一规则、总览基线保持；数值/结论不双计；49条未解析可识别；失败不伪装空数据；角色与图/表/导出一致；普通视图性能实测及真实登录浏览器验收。基线数字随目标环境数据时点重新查询，不能固定为测试常量。

## 10. 已确认决定、剩余设计与完成状态

已确认：本水系统mart采用普通视图，不建历史快照；电导率μS/cm、TOCppb、pH无量纲；源单位与原报告/数值保留，单位统一在mart消费字段完成。

四个对象、完整字段/SQL与异常粒度已落实；消费者切换仍待实施。系统/回路、限度、未覆盖0681方法保持原待确认边界，不能由单位确认推定已解决。

本轮Mac已创建四个普通视图并验证84,497结果、39,339趋势结果、13,462样品及129核对事项；15项隔离测试和全部70个源字段/键双向对账通过。未刷新数据、未切换看板、未提交或发布Linux。完整数量、性能、权限及剩余边界见[实施与验收](changes/20261009-water-mart-views.md)。

## 11. 首版 SQL 契约补充（2026-10-09 用户已授权创建）

首个迁移revision为analytics_water_mart_20261009，接analytics_water_final_20261009；样品性能优化追加analytics_water_mart_perf_1009，本机最终版本为后者。四视图不写raw/staging，不建立快照或缓存；保留宽表全部现有源字段，并增加§4别名、source_key（12键JSON对象）、comparison_key（9维JSON数组，缺单位/冲突/缺点位时追加来源键）、单位及资格字段。内部解析辅助列source_unit_clean、numeric_match、censored_match、approved_unit_scope不替代原字段。

plot_metadata_valid验证原报告全文与staging绘图规则是否一致；exact_numeric_value仅在精确数值且元数据一致时取plot_value。趋势进一步要求reported_result、有效样品身份/点位ID及编号/日期、已确认单位或明确无量纲。not_plotted_reason为稳定代码：invalid_sample_identity、non_numeric_result、invalid_plot_metadata、missing_samplepoint、missing_trend_date、unit_conflict、missing_unit。多个问题可通过review逐项识别，不只保留第一个原因。

样品视图列出唯一的来源/样品、水类型、状态、名称、点位及映射、日期组合，附result_count、trend_result_count、conclusion_count、dataset_count和装载时间。来源属性不同的样品不任取MAX/首条：排除出该计数视图，并生成sample_attributes_conflict事项；验收检测到此类事项必须阻断消费者切换/发布并核查。max(staging_loaded_at)仅为装载线索，不能解释为源截止。

核对视图字段为entity_grain、issue_type、source_system、sample_id、water_type、sample_status、workitemid、paramlistid/version、source_key、display_value、source_unit、unit_status、trend_at、details与mart_rule_version。结果问题的source_key包含完整12键；样品属性问题为2键；方法问题为来源加完整样品键、workitemid、方法和版本，跨阶段/数据集合并为一个方法事项。issue_type覆盖unparsed_result、missing_result、invalid_sample_identity、invalid_plot_metadata、missing_unit、unit_conflict、missing_samplepoint、missing_trend_date、sample_attributes_conflict、unsupported_selection_rule、no_selected_final_result。正常文字结论不因空单位进入缺单位事项。

只向已存在的lims_reader/analytics_reader授予四视图SELECT；清除四视图对PUBLIC和这些角色的默认额外权限，不创建账号或扩大staging/raw权限。security_barrier保护视图范围。SQL和回滚均由共享迁移管理；回滚仅删本次派生视图且使用RESTRICT，依赖对象存在时拒绝删除。

本轮不切换看板数据适配器、不执行Linux迁移；消费者切换、真实登录与图表/导出验收仍是后续独立步骤。
