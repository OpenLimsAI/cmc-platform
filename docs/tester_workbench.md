# 检验员工作台（/dashboard/tester）需求与口径

> 2026-09-09 负责人确认。给每位检验员一个"自己的工作台"：手上有哪些活、哪些最急、哪些已拖过时限、本月干了多少。
> 数据只读 `cmc_analytics.mart.v_test_task_monitor` + `mart.dim_employee` + `mart.dim_method`，不新增任何表/视图。
> 口径尽量复用检验周期页（`rd-lims-etl/docs/口径_检验周期.md`），不另起一套。

## 1. 入口与选人

- 顶部导航栏新增「检验员」标签，位于「检验概况」之后。
- 页面顶部下拉框选检验员（显示姓名，不显示工号；字典无姓名时回落工号）。
- **默认选中登录人自己**：登录令牌里的 `username` = 工号 = `dim_employee.employee_id`（总纲 §8.3 对齐键）。登录人不在检验员名单里时默认选名单第一位。
- 所有能登录看板的人都可切换看任何检验员（负责人决定 1）。
- 左侧边栏：「检验组」只用来缩小下拉框的人员范围（按该员工在手/近期完成检项的 `group_id`，不用 `dim_employee.group_id`，那列基本为空）；**日期范围对本页不生效**（本页看"当前在手"和"本月"）。
- 检验员名单 = 有在手检项、或近 12 个月有完成检项的 `tester`（排除空值）。
- URL 带 `?tester=<工号>` 可直达某人。

## 2. 顶部汇总卡（6 张）

| 卡片 | 口径 |
|---|---|
| 在手检项 | `tester = 本人` 且 `test_authorised_dt IS NULL` 且已收样（`sample_received_dt ≤ 今天`）且样品/检项状态均排除 X、U → 结存口径（V + C） |
| 已超时限 | 在手检项中，`收样日 → 今天` 的**工作日** > 该方法检验时限（`dim_method.target_days`，无则默认 14）。与检验周期页「当前超时限检项数」口径一致（负责人决定 1） |
| 即将超时限 | 在手且未超时限，剩余工作日 ≤ 2（页面可调，负责人决定 2） |
| 本月已完成 | 本月 1 日 ~ 今天 `test_authorised_dt` 落在区间内、`tester = 本人`、排除 X 的检项数（完结口径） |
| 本月标准工时 | 本月已完成检项 × `dim_method.std_minutes / 60`，小时；字典没有的方法按 0 计 |
| 本月平均周期 | 本月已完成检项的平均周期（收样→授权，工作日），副标注"较上月 ±x"（上月 = 上个整月） |

另附小字：待授权（C）数量、名单里最老一条的收样日期。

## 3. 在手任务清单（主体）

- 范围同"在手检项"卡；默认按 `sample_received_dt` 升序（最老的检品在最前）。
- 每行：样品编号、项目、样品名称、批号、检验方法、收样日、分配日、已耗时（工作日）、时限、剩余（工作日）、状态。
  - 状态：`test_completed_dt` 非空 → 「检完待授权」；否则 → 「进行中」。
  - 已超时限整行红底，即将超时限橙底。
- 快捷筛选：全部 / 已超时限 / 即将超时限 / 待授权。
- 「按样品看」开关：同一 `sample_id` 的多个在手检项合成一行，显示剩余检项数与方法列表（最急的样品在前，按该样品最早收样日 + 最差剩余天数排）。
- 导出 CSV（前端导出当前筛选结果，不需要导出角色——这是本人自己的清单）。

## 4. 辅助区块

- **在手检项按方法汇总**：条形图，方便批量安排仪器（前端从任务清单聚合，不另开接口）。
- **近 6 个月完成趋势**：柱 = 每月完成检项数，折线 = 标准工时（小时）；tooltip 带当月平均周期。

## 5. 接口（后端，全部挂 `require_view`）

| 接口 | 参数 | 返回 |
|---|---|---|
| `GET /api/v1/lims/tester/list` | `groups[]` | `[{employee_id, employee_name, group_ids[], pending_n}]`，按在手数降序 |
| `GET /api/v1/lims/tester/summary` | `tester`、`as_of`(默认今天)、`default_target`(默认 14)、`soon_days`(默认 2) | 6 张卡数据 + `unauthorized_n` + `oldest_received_dt` |
| `GET /api/v1/lims/tester/tasks` | 同上 | 在手检项明细（含 `elapsed_biz_days / target_days / remaining_biz_days / is_over_target / is_due_soon / bucket`） |
| `GET /api/v1/lims/tester/monthly` | `tester`、`months`(默认 6) | `[{ym, completed_n, std_hours, avg_cycle_days}]` |

代码位置：`backend/app/api/v1/lims/tester.py`（路由）、`services/lims/tester_service.py`（SQL）、`schemas/lims/tester.py`（响应模型）；前端 `frontend/app/dashboard/tester/page.tsx`，取数函数在 `lib/api.ts`。

## 6. 已知限制

- 方法检验时限 `target_days` 目前仅 11/79 已填，其余按 14 个工作日兜底，"超时限"判断偏松。上线后请在 admin 面板补全常用方法的时限（负责人决定 4）。
- 工作日只排周末，不排法定节假日（与检验周期页一致）。
- `tester` 是 LIMS 里的"开检人"，未分配的检项（tester 为空）不属于任何人，不在本页出现；它们的积压看「超期未检」页的"收样未分配"卡。
