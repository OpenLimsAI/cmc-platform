# 水系统最终结果与 mart：Linux 发布计划及验收

2026-10-09｜用户已授权Linux部署｜状态：发布前核对完成，实施进行中。

## 已核实前置

Linux 172.19.0.105，prometheus，SSH13568；三个/opt仓库均main、工作区干净、HEAD与Mac发布前基线一致。cmc_analytics及cmc_analytics_training当前均analytics_qc_login_20261009；已有QC五张staging和64列宽表，水系统数据仍为v1，有159条Completed纯化水最终行。QC timer每日04:00，当前ETL没有运行，下一次2026-10-10 04:00。

## 授权范围和执行顺序

1. Mac完成ETL、看板和mart SQL验证；只提交本任务明确文件，通过各自GitHub仓库推送；保留共享迁移仓库其他既有未提交修改。
2. Linux保存正式/培训分析库备份、三个旧SHA、应用dist和受保护配置校验值；敏感目录0700/文件0600，备份不入Git。核对备份清单和SHA256。已有Mac业务数据不复制到Linux。
3. Linux快进拉取明确提交并逐仓库核对SHA。由共享迁移入口同步两库到analytics_water_mart_perf_1009：依次经过analytics_water_final_20261009（6个可空绘图字段）、analytics_water_mart_20261009（4个普通视图与SELECT授权）、analytics_water_mart_perf_1009（样品统计性能）。不使用手工DDL、stamp或upgrade head。
4. 发布兼容v1/v2的水看板Reviewed及微生物绘图规则，使旧staging过渡期间仍可正常消费；按现有固定SHA部署脚本运行。身份/端口/Hub注册不变；无新增登录或账号配置。
5. 在既有QC flock互斥锁下执行 `python -m etl.run --stage-only`，只以Linux raw刷新正式分析库五张staging，五表一个事务；记录qc_lims.staging运行台账。不会触发Oracle/raw同步或推进raw水位。training只同步结构，保留其既有数据，不复制正式库数据或刷新为正式结果。
6. 以只读事务验收正式库完整来源键/源字段、Reviewer状态、单位/0与1、样品计数、第四/第五表水系统键一致、非水源值与既有mart定义保持、reader权限及运行台账、水位；核对培训结构/数据保留、实际服务及前端资源。视图不存储历史，不新增mart刷新任务。

## 回退与剩余边界

失败的迁移事务回滚；五表刷新失败不提交，保留原数据。应用故障按旧固定SHA与构建恢复，新增可空列和派生视图可保留；如需恢复数据或删除依赖对象，先核实当时写入/消费者，按备份专项恢复，不能自动DROP/CASCADE。ETL调度不改动，部署后复核仍为每天04:00。

本轮部署已批准规则与mart对象；水看板仍直接消费staging，补单位的mart消费者切换另行实施。真实人员角色、浏览器交互与文件落盘验收，以及0681纯化水方法验证仍单独保留，不用匿名health或合成身份代替。

## 实际结果

待发布后追加实际SHA、备份、revision、数据和服务证据；不得将计划当作部署事实。
