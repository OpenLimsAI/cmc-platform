# 水系统审核最终结果与微生物绘图

版本 1.0 · 2026-10-09 · 用户已确认，Mac 已验证

需求：最终结果仅 Reviewed；实际最终数值与文字结论可以并存；微生物限度最终报告值 `<1` 绘图为 0、精确 1 为 1。完整原文、来源键和阈值保留。绘图约定不用于精确实测统计。

依赖：qc-lims-etl 的 water_system_v2 / water_conductivity_method1_numeric_v2；共享迁移追加 plot_value、result_kind、result_operator、result_bound、plot_value_rule、result_role。过渡期兼容原选择规则，但所有接口始终排除 Completed。stg_lv_dataitem 中水系统只保留最终结果完整键，过程溯源仍在 raw；追溯接口显示最终参数及任务/数据集头。

实现范围：趋势/概览/筛选/追溯共用 Reviewed 范围；前端取消 Completed；PNG 与交互图使用同一 plot_value；明细与导出同时保留原文、数值用途、比较符、阈值和规则。数值与结论仍按指标分组，概览按样品去重。只对微生物限度报告值且 `<` 阈值恰为 1 归零；其他删失延续界值绘图。

验收：等价全角和空格写法、精确 1、<=1/≤1/<10、文字、空值分别测试；概览/联动筛选排除 Completed，兼容 v2；PNG 和导出与图表规则一致。纯化水 0681 未核实方法保留缺口。

状态：代码已实现，后端60项和前端9项测试通过、构建通过。本机共享迁移analytics_water_final_20261009已执行、ETL五表已刷新，13,167条真实微生物结果通过只读适配器逐行核对，第四表完整键追溯通过。Linux、commit/push、真实身份浏览器及正式报告验收本轮未完成。现有文档中 Reviewed/Completed、water_chart_v1 和界值绘图的旧说明由本轮更新取代。
