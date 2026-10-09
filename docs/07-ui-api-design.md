# 07 · 页面与API契约

> 版本：0.8｜日期：2026-10-09｜状态：两页与三卡片已实现，已对照本轮源码及Mac/Linux各49/9测试；Linux服务及资源已核验，真实登录交互待验收。

## 1. 两页与筛选职责

| 路径 | 内容 |
|---|---|
| /water/、/water/overview | WFI/PW/PS三卡片，每项显示点位数和当前自然年样品总数；无筛选 |
| /water/trends | 现有级联筛选、单可比组趋势、对应原文表、来源和三类导出 |

旧results/summaries/quality页面转到overview并提示已移除，清除查询串；其专用API移除。页面用pathname/history管理，趋势URL保存FilterSpec，不保存比较组；刷新趋势需重新选组。总览URL不保存筛选，不继承趋势条件；本次会话从总览返回趋势可继续原筛选。

FilterSpec字段：water_type、samplepoint_code、samplepoint_id、workitem_id、paramlist_id、paramlist_version_id、variant_id、param_id、unit、date_from、date_to、sample_status。water_type仅三类水；sample_status仅Reviewed/Completed且非空，默认Reviewed。字符串按Pydantic长度限制，samplepoint_code非空。日期默认上海今天向前12日历月至明日排他边界；最多3660天。UI两端包含，API为[date_from,date_to)，完整规则见docs/04。

GET状态重复query参数，POST为数组；未知筛选键拒绝，comparison_group只供趋势请求使用。位置和系统归属本轮暂停，等待用户对照表。完整决定见[两页整理记录](changes/20261009-two-page-dashboard.md)。

## 2. 路由与响应

Hub外部业务前缀/water/api/v1，后端/api/v1；health为/water/api/health→/api/health。所有业务需要查看守卫，导出还需导出守卫。

| 方法 / 后端路径 | 请求 | 返回 |
|---|---|---|
| GET /api/health | 无 | 匿名status=ok，仅进程接口，不动态检查DB就绪 |
| GET /api/v1/context | 无 | context为响应根，含capabilities.view/export |
| GET /api/v1/filters | FilterSpec | 信封＋options、point_options、filter |
| GET /api/v1/overview | 无；任何query键422 | 信封＋year、date_from/date_to、sample_status、point_scope、overview_rule_version、water_cards |
| GET /api/v1/comparison-groups | FilterSpec | 信封＋metrics、groups、filter、dataset_digest、count_note |
| GET /api/v1/trends | FilterSpec、必填comparison_group（≤10000字符） | 信封＋items、total、metrics、filter、comparison_group、dataset_digest、limit_status |
| GET /api/v1/results/trace | result_id（必填≤10000字符） | 信封＋chain、gaps、association_note；保留趋势来源查询 |
| POST /api/v1/exports | 第6节ExportRequest | PNG/Excel/ZIP及Content-Disposition，成功Cache-Control=no-store |

信封为data_context、context_id（当前null）、analysis_rule_version；context不套信封。GET /results、/summaries、/data-quality返回404，不改作其他含义。本轮已实现并提交GitHub、部署Linux；实际路由、匿名拒绝和资源核验见[两页Linux发布记录](releases/20261009-two-page-linux.md)。

## 3. 级联候选与缓存

顺序为water_type→samplepoint_code→samplepoint_id→workitem_id→paramlist_id→paramlist_version_id→variant_id→param_id→unit。某字段候选应用日期/状态/固定水样范围及其前面的非空筛选，忽略自身及后面的条件；未选上游不限制下游。

options的键保留源字段samplesubtypeid、samplepoint_code、samplepointid、workitemid、paramlistid、paramlistversionid、variantid、paramid、unit；值为distinct排序的候选数组，可能含null。前端普通下拉过滤null。point_options仅返回非空内部ID，含value=ID、code=现场编号、label=编号/名称/内部ID；同号不同ID独立。

趋势候选、比较组和结果缓存键包含完整FilterSpec和身份版本tokenVersion；总览键只包含overview和身份版本，单独请求无参数接口。日期解析后才请求候选，取数中禁用下拉；失败显示错误及重试；空候选有明确提示。上游改变清空后续；日期/状态改变保留水类型、清空其后字段及旧比较组/分页/导出/追溯。实际最新浏览器交互验收仍见docs/09。

## 4. 结果字段、键和上下文

normalize保留反射得到的源列并增加下列字段，不是固定的全部snake_case响应模型。输入字段与输出字段不能机械等同。

| 当前输出 | 来源或含义 |
|---|---|
| sample_id / sample_status / water_type | s_sampleid / samplestatus / samplesubtypeid别名 |
| samplepoint_id / samplepoint_code / samplepoint_name | samplepointid内部ID别名；当前主表编号/名称 |
| samplepoint_mapping_source、samplepoint_mapping_scope、samplepoint_source_moddt、samplepoint_extracted_at | 映射来源、观察范围、源修改/抽取时间 |
| locationid、workitemid、paramlistid、paramlistversionid、variantid、paramid、paramtype | 仍用源列名；没有location_id/workitem_id/paramlist_id等结果别名 |
| display_value / source_unit | displayvalue / unit别名，原值原单位 |
| trend_at / trend_date_source | trend_dt / trend_dt_source别名，上海时区ISO时间 |
| batch_number | u_batchno别名，源值不改 |
| result_kind / numeric_value / operator / bound / parse_reason | 解析类别、Decimal文本、删失比较符/界值及原因 |
| result_id / source_key / comparison_group | v1编码结果键、完整12列结果键、九字段组编码，见docs/03–04 |
| plot_status / not_plotted_reason / mapping_status / limit_status | 是否绘图、未绘图原因、映射说明、未配置限度 |

result_id为v1.＋无尾部等号的URL-safe Base64紧凑JSON编码。结果键数字dataset/replicateid序列化为字符串，解码后查询转Decimal；服务端校验键集合/字段类型/有限数字及授权来源。先定位授权水样宽表再按完整键追溯，关联缺口通过gaps返回；不是任意样品查询。

趋势及比较组选项的metrics含sample_count/dataset_count/result_count/kinds/plot_count。总览独立采用water_cards，不能把点位数当系统数。

context含environment/source_system/source_description/staging_data_origin、上海current_date/timezone、全授权水样min_result_at/max_result_at/loaded_at_hint、source_cutoff/context_id（均null）、规则、映射/限度/新鲜度和一致性说明。日期范围不应用用户筛选或状态；这些线索不等于当前筛选结果范围或来源截止。STAGING_DATA_ORIGIN由已核实配置提供，不是自动探测。

## 5. 总览聚合契约

water_cards按WFI=注射用水、PW=纯化水、PS=纯蒸汽排列，各含code、water_type、point_count、annual_sample_count。year及date_from/date_to在本次响应按上海今天固定：当年1月1日至明日（排他）。sample_status固定[Reviewed,Completed]，point_scope=all_available_selected_results，overview_rule_version=water_overview_counts_v1。

点位统计不限年度，在该水类型全部可用入选宽表范围中按非空内部ID去重；年度样品按有效trend_dt落入年内的source_system/s_sampleid去重。来源固定，SQL按水类型聚合COUNT DISTINCT，并将缺失水类型补零；缺日期不计年度，缺点位仍可计年度样品。原有数值/结论、多个replicate不增加重复计数。单响应内卡片/context由同一REPEATABLE READ只读事务返回；不依赖趋势选项/用户筛选，也不读取全集原文。

此样品总数仅包括已有两条来源规则入选结果的Reviewed/Completed样品，不是全部待检样品总量；点位也不是主表完整台账。页面展示统计年度、截至日期和简要口径。查询失败返回503及重试提示，不补零伪装成功。详见docs/04和两页整理记录。

## 6. 导出请求与文件

ExportRequest禁止额外顶层键，字段为：filter必填FilterSpec、comparison_group必填且≤10000字符、export_kind必填chart/table/bundle、context_id可空、dataset_digest必填64字符、chart_spec默认为空dict。chart_spec当前不参与处理，没有受限选项或类型化展示契约；不信任客户端数值/限度。

后端读取FilterSpec全集后选组，对所选组规范化完整结果计算SHA256；context_id非null或digest不符先返回409。随后无结果为422；因此无结果且digest已变化时先得到409。当前摘要不是不可变版本，不覆盖全部context元数据。前端缩放不改变导出范围，实际日期沿用请求，不重新计算今天。

| 类型 | MIME | 文件内容 |
|---|---|---|
| chart | image/png | water-trend.png；当前组散点、删失界值/运算符、日期/单位/点位、导出ID与未知上下文说明 |
| table | application/vnd.openxmlformats-officedocument.spreadsheetml.sheet | water-results.xlsx；导出说明和原始结果两张表 |
| bundle | application/zip | water-bundle.zip；trend.png、results.xlsx、results.csv、results.jsonl、manifest.json |

所有内容基于一次固定结果集，渲染前释放事务。Excel列由export.COLUMNS定义，包含原文/源单位/来源键/时间/规则/当前映射及派生字段；不是raw全列导出。Excel结果单元格为文本以保留原串并防公式。CSV对以=、+、-、@开头（忽略左侧空白）的文本加单引号；JSONL保留规范化行的原字符串及完整键。

manifest含export_id/kind/generated_at/actor_id、filter/comparison_group、data_context/context_id、分析/图形/来源规则、metrics/未绘图计数/已知缺口。ZIP manifest附四个内容文件SHA256；Excel说明在ZIP哈希计算前写入，不含最终四文件哈希；独立PNG/Excel也不另附manifest或外部哈希文件。图形版本water_chart_v1不代表已实现共享ChartSpec。

PNG当前无实际限度；没有可绘图值也可以导出有原文说明的图；无绘图点本身不触发拒绝，空结果按前述digest检查顺序处理。生成失败不返回部分文件。图表原文表范围按docs/03第9节定义，绘图状态/统计按docs/04。

## 7. 错误与实现限制

已处理业务错误返回code/message/request_id并带X-Request-ID。401 UNAUTHORIZED、403 FORBIDDEN、404 NOT_FOUND、409 DATA_CONTEXT_CHANGED、422 INVALID_REQUEST或EXPORT_NO_RESULTS、413 EXPORT_TOO_LARGE、503 DATA_UNAVAILABLE。当前413名称也用于趋势结果查询超限，不只用于导出。SQLAlchemy异常及文件生成失败有处理；未捕获异常/启动失败不保证同一错误信封（GAP-04/05）。

趋势/导出稳定排序按完整键，但当前仍先读取全集；单SQL超时30秒、默认上限100000行，限制在选比较组之前执行（OP-11/GAP-05）。前端响应大量any和方法/位置标准别名尚未补齐（GAP-02），不把构建通过等同端到端接口类型验证。缓存当前没有analysis_rule_version/context_id维度，身份观察能力的边界见docs/06。
