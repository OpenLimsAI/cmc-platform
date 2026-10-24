# 旧质量看板功能基线与新版核对入口

日期：2026-09-22。旧版源码：`../quality_analysis_dashboard/`；新版源码：本仓库。本文依据实际调用链编写，旧版 README、函数注释、控件标题只作线索；“有代码”不等于页面调用、统计正确或生产已部署。未读取旧版 `data/`、本地凭据和业务记录，未连接数据库。新版相似性文件当前有未提交改动，以下“当前”指本次读取的工作树，后续须重新核对。

## 1. 入口和数据边界

旧版 `app.py:29-113` 用 Streamlit 单页侧栏切换放行、稳定性、相似性、Excel 导入四模块；前三页直接从 `quality.quality_data` 读取，页面查询有十分钟缓存。`dashboards/release_dashboard.py:62-95`、`dashboards/stability_dashboard.py:22-75`、`dashboards/similarity_dashboard.py:45-81` 是实际查询入口。旧版 `CLAUDE.md` 的 2026-09-16 增量和 README 的 Mac 阶段指向本机 `cmc_analytics.quality`；放行函数说明仍写旧库 `cmc_data_platform`，不能据此判断当前连接。旧 README 所述 Mac 导入量是当时快照，不是本次数据库事实。

新版是 FastAPI + React，读 RD/QC staging 或旧 Excel 适配源，来源与旧版 `data_source` 字段不完全同义；数据库和范围见 [来源说明](QAP-DATA-SOURCES-001.md)。对比时必须固定项目、来源、批号、样品、方法、单位、时间/放置条件和**观察行数**；仅比较两张截图无法证明数值一致。

## 2. 旧版实际功能清单

| 模块 | 旧版可由调用链确认的行为 | 代码证据及边界 |
|---|---|---|
| 放行数据 | 取 Release、非空指标和值；清理数值；来源、项目、产线、组别、批号、检验类别依次收窄；空多选通常表示不限制。批号解析推算年份，默认最新一年，历史回顾默认前三年；手选指标优先，否则预设，最后退到前六个已有指标。 | `dashboards/release_dashboard.py:62-95,98-298`；年份来自批号，不能等同检验日期。多项目/多来源可混入一次分析。 |
| 放行图表与统计 | 每项左侧按批号趋势、右侧组均值图（7:3）；趋势以所选年份为当前集，以当前集之前 N 年为历史集；画均值、SD 参考线与字典规格，计算历史汇总及能力指数。`_pct` 指标绘图时统一乘 100。 | `dashboards/release_dashboard.py:300-383`、`analytics/plotly_plots.py:77-~330,644-~740`、`analytics/stat_core.py:873-950`、`components/spec_limits.py:370-~410`。放行 Excel/PDF 按钮整段被注释，不能算页面功能。Plotly 工具栏可下载图。 |
| 稳定性数据与筛选 | 读取 Release + Stability，尝试融合放行零点；按项目、样品、稳定性检验类别、组别、产线、对照/实验批号、指标筛选。放行记录绕开稳定性类别筛选，批号候选来自稳定性记录。参比产线主要给默认批号来源，实际对照身份按选入的批号标记。 | `dashboards/stability_dashboard.py:77-140`、`dashboards/stability_sidebar.py:39-~450`、`analytics/data_fusion.py:73-~175`。融合与单位改写仅为旧逻辑，不代表配对关系已获业务确认。 |
| 稳定性输出 | 每指标四视图：组均值±SD、组拟合、逐批趋势、逐批拟合；折叠统计有 OLS、Cpk、LME、TOST；逐项 Excel 导出，页面末尾显示筛选后的原始表。 | `dashboards/plot_area.py:33-107,156-~370`、`analytics/stability_plots.py:235-~630`。统计结果需检查样本独立性、时间单位及对照定义，不能因旧页面展示就认定正确。 |
| 相似性筛选 | Release 项目、来源、批号、参比及比较产线、指标；默认前六个指标；Tier1 列表、90%/95% CI、BF 阈值、Tier2 命中比例、自动/手动 Δ；点击运行。 | `dashboards/similarity_dashboard.py:45-210`。旧查询未带样品、方法、单位等隔离字段。 |
| 相似性结果 | 逐指标与参比产线计算六图：参比均值 CI、差值 CI/±Δ、个体差、差范围、原值散点、参比均值±kSD 命中带；22 列结果表及 Excel 导出。有效观察行进入统计，未按独立批次汇总。 | `dashboards/similarity_dashboard.py:211-~445`、`analytics/similarity_plot.py:203-716`。结果中包含等效/Tier 文字，但旧公式有已证实缺陷，见第 4 节。 |
| Excel 页面导入 | 多文件 `.xlsx`/`.xlsb` 上传，解析预览、排除记录下载、导入口令+确认；总量限制 100 MB、转换后至多 200 万条。按文件名删除旧 QC 行并在同一事务 COPY 新行，SHA256 查重，登记 `quality.import_history`；成功后清页面缓存。 | `dashboards/import_dashboard.py:29-115`、`etl/import_service.py:57-~295`。同名文件是整体替换，不能用增量文件补几行；原记录不保留版本。命令行 `etl/run_etl.py` 是另一条流程，不能等同页面受控导入。 |
| 配置/辅助 | YAML 控制指标预设、别名、字段映射；`components/batch_utils.py` 解析批号排序和年份；`components/spec_limits.py` 查旧规格字典；`components/utils.py` 清洗文本/百分号；`analytics/transformers.py` 宽表转长表。 | 这些是迁移输入和可测试算法候选，不等于批准的指标字典、现行规格或无损原值模型。 |

## 3. 按旧版基线核对当前新版工作树

| 主题 | 当前新版代码证据 | 结论 / 下一步 |
|---|---|---|
| 放行 | `frontend/src/pages/ReleaseTrendPage.tsx`、`backend/app/services/dashboards/release_service.py` 已有服务端筛选、趋势/组图、历史参考模式及统计；[专项核对](QAP-RELEASE-PARITY-20260916.md)记录了公式和显示差异。 | 核对已覆盖主要页面，但旧规格、百分数、能力指数仍须按批准文件和单位验收；多项目合并不是目标。 |
| 稳定性 | `frontend/src/pages/StabilityPage.tsx`、`backend/app/services/dashboards/stability_service.py` 有四视图、统计和拟合；[实施记录](QAP-STABILITY-001.md)列出未迁移对照批号、Day-0、LME/TOST、规格及 Excel 导出。 | 不能按旧说明直接补零点或套用旧统计；先确定研究条件、配对、单位和独立样本。 |
| 相似性 | 当前 `frontend/src/pages/SimilarityPage.tsx` 有参数筛选、自动分析及 Excel 探索报告；`SimilarityChart.tsx` 画六图；`backend/app/services/dashboards/similarity_service.py` 调用修正的统计函数，`backend/app/api/v1/similarity.py` 导出旧 22 列加范围/状态列。 | 当前工作树比 [2026-09-16 逐项表](QAP-SIMILARITY-PARITY-AUDIT-20260916.md)正文新；该文首段有 2026-09-22 更新。仍需同来源、同观察集逐项核对，当前结果标为探索/未批准。 |
| 导入 | `backend/app/api/v1/imports.py` 的 `/capabilities` 显示 `can_commit: false`，只有模板及内存结构预览；页面 `ImportPreviewPage.tsx` 与之对应。 | 新版还不能确认写入。旧版按文件名删除重导模式不满足拟议的可追溯版本要求，不能直接搬过来。 |

## 4. 旧版中不应继承的错误与不确定性

1. **放行当前年份 SD 开关无效**：`release_dashboard.py:255-266` 接收选项，但 `:321-332` 调 `plot_release_batch_trend` 时未传 `sd_current_year_mode`，函数 `analytics/plotly_plots.py:85,126` 使用默认 `False`。新版已显式传参考模式；应以相同原始观察核对“当前/历史”两组数值。
2. **相似性显著性与方差法**：`similarity_dashboard.py:277-321` 将 `alpha=1-conf_level` 传给 TOST，而 `analytics/stat_core.py:847-852` 使用 `1-2*alpha` 算 CI；90% 选择实际得到 80% CI。界面 BF 阈值 `bf_p_th` 未传入函数，TOST1/2 名称切换不等于计算方差法切换；Tier1 与主结果可能相反。见 [独立统计审计](QAP-SIMILARITY-STATISTICS-AUDIT-20260916.md)与 [修正](QAP-SIMILARITY-STATISTICS-FIX-20260916.md)。新版应统一差值方向、Δ、置信度和算法，不追求错误数值一致。
3. **旧注释与运行路径不符**：旧 README 宣称导出 PDF/多图 ZIP、方差法自动选择等，应逐页看按钮及调用；放行报告按钮实际注释。`release_dashboard.py:62-74` 的旧库名说明与 Mac 阶段配置不一致；运行数据库需另行确认。
4. **数据混合风险**：旧相似性以项目/产线/指标聚合，查询未携带样品、方法、单位、放置状态；旧稳定性可将放行零点改写时间单位，甚至据稳定性数据整体唯一单位赋值。新版分面及保留原值属于必要修正，不能把旧图数值当合格基准。
5. **旧规格和百分数**：`analytics/plotly_plots.py:110-144` 自动用旧字典规格，并以 `_pct` 后缀放大数值；没有逐项目批准版本和单位保证。优先逐项确认原始单位、规格来源及版本，才可计算能力或合格结论。
6. **旧版导入是破坏性替换**：`etl/import_service.py:218-~266` 同事务删除旧文件行并 COPY，能回滚本次失败，却不能让被替换的历史版本供事后复核。新版正式导入应按设计记录文件哈希、原始文本、行/列位置、问题、版本和操作人；数据库结构走中央迁移。

## 5. 复用建议和可执行验收办法

可以复用**确定的规则和样例**：批号解析（对照现行命名）、中文别名与组合列表、图表颜色、部分不涉及业务批准的绘图细节。Python 纯函数可移植到新版后端时，应先做输入输出契约和边界算例，再改造为不依赖 Streamlit、不读写数据库的函数。新版 React 无法直接调用旧 Streamlit 页面函数；旧 PostgreSQL 查询、导入写入、规格字典、百分数自动换算及 TOST/Tier 判断都不能整段复制。现有新版统计模块已经包含经过修正的等效性函数，应以它及独立算例为基础。

每项对账留一行可复核记录：`来源/项目/样品/条件/方法/单位/批号集合 → 原始观察 ID 或行数 → 清洗/排除原因 → 计算公式及参数 → 旧值/新值 → 差异归类（缺功能、来源不同、旧错已修、待业务确认）`。先用合成边界例验证公式，再用**同一份脱敏数据**验证图与报表；最终以批准规格、业务定义和可追溯来源判定正确性。旧代码是行为基线，不是统计或合规验收标准。

本文为第一轮静态源码清单；未执行旧看板、未做同数据结果对账、未验证 Mac/Linux 服务或实际库。下一轮优先形成相似性同数据样本对账、稳定性 Day-0/对照定义与放行规格/单位三份可签认清单。已有分模块审计文档保留详细证据，变更新版时以代码和本日最新状态为准更新本表。
