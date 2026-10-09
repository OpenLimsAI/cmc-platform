# 07 · 页面与接口设计

> 版本：0.5｜日期：2026-10-09｜状态：基础应用已在 Mac/Linux 部署；级联修正已实现，实际验收及本次发布记录见 docs/changes/20261009-cascading-filters.md。

## 1. 页面工作方案

所有路径位于 `/water/`。首屏为总览，导航包含“取样点趋势”“结果明细”“期间汇总”“数据质量”。详情通过已有页面侧栏打开，避免重复筛选体系。

| 页面 | 主要内容 |
|---|---|
| 总览 | 环境/来源上下文、统一筛选、样品/数据集/结果计数、精确/删失/定性/缺失分布 |
| 取样点趋势 | 默认截至今天近一年；季度/半年/年度快捷及自定义日期；点位/比较组、散点和已确认限度；点选原值；按权限显示图像/原始数据表/组合包导出 |
| 结果明细 | 分页、稳定排序、原值/单位/状态/方法/时间来源/规则；完整来源抽屉 |
| 期间汇总 | 月/季/年，按点位和可比组汇总；精确数值子集统计及各类样本数量 |
| 数据质量 | 映射缺失、日期回退、解析失败、未知方法/规则、单位冲突和已知覆盖缺口 |

统一 FilterSpec：water_type、samplepoint_code、samplepoint_id、workitem_id（可选）、paramlist_id、paramlist_version_id、variant_id、param_id、unit、date_from/date_to、sample_status。版本与方法字段分别传递；sample_status 为 Reviewed/Completed 的枚举数组，默认值工作设计为 Reviewed。UI 终止日转换为下一日作为不含终点的 date_to，见 docs/04。用户选定筛选后图表、汇总、明细和导出使用同一类型化筛选；GET 用查询参数，POST 导出用相同模型的 JSON body。URL 可保存筛选但不携带令牌。筛选下拉仅返回当前用户可访问的数据。

无结果显示“当前条件无结果”；查询失败显示失败原因/重试入口；未配置限度、未映射名称和未知数据截止分别显示，不能用空白图或“正常”代替。

## 2. API 工作契约

Hub 外部前缀 `/water/api/v1`，后端实际前缀 `/api/v1`。下表为当前接口契约；实际验证记录单独登记，变更同步更新类型与测试。

| 方法/后端路径 | 内容 | 权限 |
|---|---|---|
| GET `/api/health` | 最小服务状态，不返回数据/凭据/详细配置；Hub `/water/api/health` | 可匿名 |
| GET `/api/v1/context` | 环境、规则与数据上下文、可用能力/未确认限度状态；current_date/timezone 供默认和快捷日期解析 | 查看 |
| GET `/api/v1/filters` | 接受同一 FilterSpec；返回按上游条件级联的水类型、点位、检项、方法/版本/阶段/参数/单位候选 | 查看 |
| GET `/api/v1/overview` | 样品、数据集、结果计数和质量分布 | 查看 |
| GET `/api/v1/trends` | 一个比较组的原值/派生值、点位和日期来源 | 查看 |
| GET `/api/v1/results` | 结果分页列表和当前范围总数 | 查看 |
| GET `/api/v1/results/trace` | query result_id，解码完整结果键定位并返回追溯链 | 查看 |
| GET `/api/v1/summaries` | period=month/quarter/year，同比较组汇总 | 查看 |
| GET `/api/v1/data-quality` | scope=selected_results/coverage_candidates/unassigned 的质量分布和分页明细；分别说明筛选与分母 | 查看 |
| POST `/api/v1/exports` | FilterSpec＋比较组/ChartSpec＋export_kind=chart/table/bundle；同步生成 PNG、Excel 或 ZIP | 查看＋导出 |

`/api/health` 不等于就绪检查；业务数据结构/权限就绪情况由受保护 context 与启动预检提供。POST 导出属于只读业务数据操作，可能产生审计事件，不授予 staging 写权限。

筛选参数用枚举/长度/日期范围校验；点位 ID 当字符串保存。列表默认 page_size=50，工作上限 200，稳定复合键排序。大趋势和导出超过上限时明确返回范围限制/要求缩小范围，不悄悄截断并伪装完整。性能和最大范围经 Mac 实测后确定 OP-11。

追溯 query 参数 result_id 按下文版本化规则解码为完整源键，不只用 s_sampleid 或 sdidataitemid 代替主键；先验证该结果属于授权 QC 水样。非法编码/键类型返回 422，未找到结果返回 404，源关联缺失在返回体保留来源缺口。

### 筛选候选接口

GET `/api/v1/filters` 接受相同 FilterSpec（含 samplepoint_code、日期、状态），执行相同输入与角色校验。顺序为 water_type → samplepoint_code → samplepoint_id → workitem_id → paramlist_id → paramlist_version_id → variant_id → param_id → unit。每个候选列表只应用其前面的非空选择以及日期、状态、授权水样范围，不应用自身及后面的条件。返回 options（既有源字段键）、point_options（value=内部 ID、code=主表水点号、label=编号/名称/内部 ID）、filter（本次解析的筛选）和既有上下文信封；候选和上下文在同一只读事务内读取。编号重复不合并内部 ID。

前端缓存键包含完整 FilterSpec 和身份，等待日期解析后请求候选；请求中禁用旧候选、显示加载状态，失败显示重试，空列表显示“当前范围无可选项”。更改上游清空后续选择，更改日期/状态保留水类型并清空点位及后续选择；至少选择一种状态。URL 恢复重新读取对应候选。

## 3. 返回字段约定

列表响应包含 items、total、page、page_size、data_context、context_id、analysis_rule_version；统计响应包含 metrics/groups、使用口径及相同上下文。result_id 工作设计采用带编码版本的完整源键可逆编码，不使用分页序号或进程内临时 ID；服务端解码后校验每一字段和来源范围。完整 source_key 始终返回，编码规则/数字规范化需固定并验证。标识只是定位信息，不能替代权限检查。

每条结果至少含样品、水类型、取样点编号/映射状态、方法版本/阶段/参数、display_value、source_unit、result_kind、numeric_value/operator/bound（适用时）、趋势时间及其来源、sample_status、selection_rule 和完整 source_key。Decimal 在 JSON 中用可保留精度的字符串，展示层按需要转换；日期时间包含明确时区或源时间语义标识。

错误响应包含 code、message、request_id；导出上下文已改变返回 409（DATA_CONTEXT_CHANGED），无入选结果返回 422（EXPORT_NO_RESULTS）；无效/过期身份 401，权限或临时密码 403，不存在 404，输入校验 422，导出范围超过允许量 413（EXPORT_TOO_LARGE），数据/结构暂不可用 503。详细 SQL/连接错误留服务日志，不返回凭据或敏感配置。

## 4. 导出工作设计

工作格式为 PNG 趋势图和 Excel `.xlsx` 原始数据表；支持单独下载或组合 ZIP。当前选定的一个可比组和实际日期范围同时应用于图与表，不混入其他单位/方法组；多个组分别导出。export_kind=chart 返回 image/png，table 返回 Excel MIME，bundle 返回 application/zip；三个类型均需要导出权限。请求只提交已解析筛选、比较组标识、预期 context_id 和受限展示选项；客户端 ChartSpec 不得提供可信结果值或限度，实际点、统计和限度均由后端授权取数后生成并校验。

组合 ZIP 固定包含五个文件：`trend.png`、`results.xlsx`、`results.csv`、`results.jsonl`、`manifest.json`。Excel 为面向用户的原始数据表，CSV/JSONL 保留既有通用/保真副本。manifest 记录导出 ID/类型、环境、来源/截止依据、已解析 FilterSpec 和比较组、状态与日期口径、生成时间/时区、必要操作者标识、结果行数、绘图点数/未绘图分类计数、选择/分析/图形规则版本及四个内容文件哈希和已知缺口。Excel 增设“导出说明”工作表，记录对应上下文、范围、计数和导出 ID；PNG 标题/脚注标注范围、组别、数据上下文摘要和导出 ID。

### 图与表对应

后端只读 REPEATABLE READ 取数一次，固定数据集后生成全部文件；分页不限制导出总量。趋势 PNG 展示所选完整日期范围、中文检项/点位、单位、图例、精确值/删失标记、已确认限度及趋势日期来源说明；图像不能隐藏部分组别或点却称为完整导出。页面缩放仅作浏览，不改变导出范围；修改日期筛选后才改变图与表的共同范围。图像不必与前端截图逐像素相同，必须保留相同数据与分析语义。

原始数据表为 docs/03 第 9 节定义的最终结果原文表，包含样品、水类型、取样点编号/名称、方法/参数/版本、display_value、source_unit、趋势日期/来源、样品状态、选择规则、完整 source_key，并单列派生值、解析分类、plot_status 与未绘图原因。入选但不能绘图的行仍保留；表格行数与图点数分别说明，不强行相等。定性或删失结果按 docs/04 展示，不转为普通数值。

导出沿用已解析的页面日期，不在生成时重新计算“近一年”。上下文可信且导出取数发现与页面 context_id 不同时，提示刷新并重新确认范围，不能把旧页面图像与新数据表拼包；上下文未知时明确提示，文件内部仍使用本次同一取数。导出无结果或超上限明确报错，不生成含糊的空图或截断文件。

### 原值与文件完整性

Excel 的源显示值、源编号、源单位和来源键字符串以文本单元格写入，禁止变成公式或自动数值；保留前导零、尾部零、`<1` 和中文，派生数值独立列。CSV 对可能解释为公式的文本作安全输出并说明转义；JSONL 保留原字符串和完整源键，供独立核对。不能声称任意软件打开 CSV 都保持原类型/原文。导出不包含口令、token、Cookie、连接串或完整人员资料。

完成图像渲染、Excel/数据文件生成及数量/哈希核对后再发送响应；任何步骤失败均不返回部分下载。OP-11 确定行数/图片尺寸/耗时限制、PNG 渲染和 Excel 依赖及 Mac/Linux 中文字体；OP-09/11 确定临时文件清理和审计。ZIP 与 JSONL 可用标准库，不因此增加后台任务或新服务。

## 5. 实现约束

前端 API 类型与后端 OpenAPI/Pydantic 对齐。图表点数限制、聚合和缓存不能改变结果含义；任何降采样提示都保留真实点数和算法。缓存键包含全部筛选、分析版本和可用数据上下文，不将某个用户的授权结果无条件共享给其他用户。

## 6. 来源字段到 API 的明确映射

| API 字段 | 来源/含义 |
|---|---|
| sample_id / sample_status / water_type | s_sampleid / samplestatus / samplesubtypeid |
| samplepoint_id / location_id | samplepointid / locationid；字符串编号，保留前导零 |
| workitem_id / paramlist_id / paramlist_version_id / variant_id / param_id | 对应源 workitemid/paramlistid/paramlistversionid/variantid/paramid |
| display_value / source_unit | displayvalue / unit，源值原样保留 |
| trend_at / trend_date_source | trend_dt / trend_dt_source；来源标签映射见 docs/04 |
| numeric_value / operator / bound / result_kind | 本应用派生，单独标注解析规则和失败原因 |
| source_key | docs/03 的 12 列完整结果主键；保持原字段名及约定类型 |
| data_context / context_id | 来源/环境/截止依据/装载线索/规则与映射版本；未知 context_id 为 null |

数据质量 scope=selected_results 使用主看板 FilterSpec；coverage_candidates 使用同源候选方法名单，输出候选数/已入选数及核对身份，不输出自动“最终结果完整率”；unassigned 专门显示不能归入日期或点位的记录，返回实际生效/未生效筛选说明。主看板指定日期范围会排除缺日期，指定点位会排除缺编号；用户可从质量页进入对应未归属分区，而不是通过修改日期猜测归属。


## Mac 实施状态（2026-10-02）

V0.3 的工作设计和历史复核记录保留用于追踪；当前事实以 [Mac 验收记录](acceptance/mac-20261002.md) 和 docs/10 新决定为准。基础应用已运行，不能据此将所有验收项或 Linux 发布登记为通过。
