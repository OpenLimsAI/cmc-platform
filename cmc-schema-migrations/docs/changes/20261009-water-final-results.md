# 水系统结果绘图字段

2026-10-09 · v1.0 · 用户已确认，Mac 已执行与核对

目标 revision analytics_water_final_20261009，前置 analytics_qc_login_20261009。仅在 cmc_analytics / cmc_analytics_training 追加 staging.stg_lv_test_result_wide 六个可空字段，不改来源字段、权限或产品行。字段表示绘图值、结果性质、比较符、阈值、转换规则和结果用途。微生物报告值 <1 绘图为0，不是精确测量，不自动用于统计。

消费者：qc-lims-etl、cmc-water-system-dashboard、本机 staging 浏览器。应用兼容旧规则，仅 Reviewed 水样。先备份本机 staging、迁移指定版本，再事务刷新；失败整体回滚。恢复旧应用时保留新增列，不通过降级删除证据。

本机cmc_analytics由analytics_qc_login_20261009升级至指定revision analytics_water_final_20261009并确认current；新增列通过ETL和只读消费者逐行核对，ETL44项、消费者后端60项、前端9项通过及构建通过；本机未发现培训库，不创建。Linux正式/培训迁移与发布另行验收。
