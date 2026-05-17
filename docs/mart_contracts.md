# cmc_analytics.mart 契约 — TT LIMS 看板取数层

> 本文是看板（cmc-rd-lims-dashboard）与数据侧（mart 建设者）的接口约定。
> 看板代码按本文实现，mart 表/视图按本文落地，两边并行。
> **mart 表的 DDL 落地后请回填 §6 状态表。**

## 0. 设计原则

1. **看板只读 `cmc_analytics`**，不直接连 `cmc_rd` 或 `cmc_data_platform`。
2. **主数据全部来自 `cmc_mdm`**，通过 `cmc_analytics.snap_mdm.*` 每日快照或 `ext_mdm.*` FDW 视图引入 mart（按 v0.1 FDW 分级，字典类高频低变更走 snap）。
3. **mart 同时提供"维度建模 + 兼容视图"两层**：
   - 维度建模层：`dim_*` / `fct_*`（v0.1 规范要求）
   - 兼容视图层：`vw_*`（以 join 表达原 `app_rd.v_*` 的语义，看板直接消费，避免一次性重写 30+ SQL）
4. **粒度严格分离**：sample 与 test 各成事实表；宽表只在 view 层呈现。

## 1. 数据来源

| 上游 | 下游 mart 对象 | 同步方式 |
|---|---|---|
| `cmc_rd.raw_rd_lims_samplemanager.{sample, test, result}` | `cmc_analytics.staging.stg_{sample,test,result}` → `mart.fct_*` | ETL（lucullus_etl 团队负责到 staging；mart 建模由本项目用户自建） |
| `cmc_mdm.mdm_quality.{method_master, test_item_master, spec_master}` | `cmc_analytics.snap_mdm.method_master` | 日级快照 |
| `cmc_mdm.mdm_core.{project_master, employee_master, group_master}` | `cmc_analytics.snap_mdm.{project_master, employee_master, group_master}` | 日级快照 |

> 注：现存旧库 `cmc_data_platform.staging_rd.{sample_clean, test_clean}` 与新库
> `cmc_rd.raw_rd_lims_samplemanager.*` 是否同源、字段是否一致，需要 ETL 团队确认。

## 2. 事实表

### 2.1 `mart.fct_sample`（样品事实，约 16k 行）

粒度：每条样品一行（`sample_id` PK）。

| 字段 | 类型 | 说明 | 来源 |
|---|---|---|---|
| sample_id | text PK | 样品唯一 ID | sample_clean.sample_id |
| project_id | text FK→dim_project | 项目号 | sample_clean.project_id |
| sample_name | text | 样品名称 | sample_clean.sample_name |
| batch_number | text | 批号（公司全局 batch_id） | sample_clean.batch_number |
| sample_type | text | 样品类型 | sample_clean.sample_type |
| test_type | text | 检测类型 | sample_clean.test_type |
| request_dt | timestamp | 请样时间 | sample_clean.request_dt |
| request_person | text | 请样人 | sample_clean.request_person |
| sampled_dt | timestamp | 取样时间 | sample_clean.sampled_dt |
| received_dt | timestamp | 收样时间 | sample_clean.received_dt |
| started_dt | timestamp | 开始检测时间（样品级） | sample_clean.started_dt |
| completed_dt | timestamp | 完成时间（样品级） | sample_clean.completed_dt |
| authorised_dt | timestamp | 授权时间 | sample_clean.authorised_dt |
| tester | text FK→dim_employee | 检测人（样品级） | sample_clean.tester |
| completer | text FK→dim_employee | 完成人 | sample_clean.completer |
| authoriser | text FK→dim_employee | 授权人 | sample_clean.authoriser |
| group_id | text FK→dim_group | 课题组 | sample_clean.group_id |
| status | text | 样品状态（U/V/C/A/X 等编码） | sample_clean.status |
| production_line_id | text | 产线 ID（CMC 多产线场景预留） | sample_clean.production_line_id |
| timepoint | numeric | 稳定性时间点 | sample_clean.timepoint |
| timepoint_unit | text | 时间点单位（month/week） | sample_clean.timepoint_unit |

**索引建议**：`(received_dt)`、`(request_dt)`、`(status)`、`(project_id)`、`(group_id)`、`(batch_number)`。

### 2.2 `mart.fct_test`（检验任务事实，约 37k 行）

粒度：每条检验任务一行（`test_id` PK），通过 `sample_id` 关联 fct_sample。

| 字段 | 类型 | 说明 | 来源 |
|---|---|---|---|
| test_id | text PK | 检验任务唯一 ID | test_clean.test_id |
| sample_id | text FK→fct_sample | 所属样品 | test_clean.sample_id |
| method_code | text FK→dim_method | 检测方法编码 | test_clean.method_code |
| method_name | text | 检测方法名称（冗余便于查询） | test_clean.method_name |
| groupleader_received_dt | timestamp | 组长接样时间 | test_clean.groupleader_received_dt |
| assigned_dt | timestamp | 分配时间 | test_clean.assigned_dt |
| started_dt | timestamp | 开始检验时间 | test_clean.started_dt |
| completed_dt | timestamp | 完成时间 | test_clean.completed_dt |
| authorised_dt | timestamp | 授权时间 | test_clean.authorised_dt |
| tester | text FK→dim_employee | 检测人 | test_clean.tester |
| authoriser | text FK→dim_employee | 授权人 | test_clean.authoriser |
| group_id | text FK→dim_group | 课题组 | test_clean.group_id |
| status | text | 任务状态：A=已授权, C=已完成, U=未提交, V=已校验, P=待检, X=取消 | test_clean.status |

**索引建议**：`(completed_dt)`、`(authorised_dt)`、`(sample_id)`、`(method_code)`、`(tester)`、`(group_id)`、`(status)`。

## 3. 维度表

> 维度均来自 `cmc_mdm`，通过 `snap_mdm` 每日快照镜像进 `cmc_analytics`；mart 内的 `dim_*` 是消费层视图或物化表（看你选择）。SCD type 1（latest-wins）。

### 3.1 `mart.dim_method`

| 字段 | 类型 | 说明 |
|---|---|---|
| method_code | text PK | 方法编码 |
| method_name | text | 方法名称 |
| std_minutes | numeric(6,2) | 标准检测工时（分钟） |
| target_days | integer | 目标周转天数（用于超期判定） |

来源：`cmc_mdm.mdm_quality.method_master`（迁移自旧 `meta.dim_method`，约 79 条）。

### 3.2 `mart.dim_employee`

| 字段 | 类型 | 说明 |
|---|---|---|
| employee_id | text PK | 员工 ID（= tester / authoriser 字段值） |
| employee_name | text | 姓名 |
| department | text | 部门，默认"药学及技术转移部" |
| group_id | text FK→dim_group | 所属课题组 |
| status | text | active / inactive |

来源：`cmc_mdm.mdm_core.employee_master`（迁移自旧 `meta.dim_employee`，约 29 条）。

### 3.3 `mart.dim_project`

| 字段 | 类型 | 说明 |
|---|---|---|
| project_id | text PK | 项目号 |
| project_name | text | 项目名称（如有） |
| product_code | text | 关联产品（如有） |
| is_active | boolean | 是否在研 |

来源：`cmc_mdm.mdm_core.project_master`（**当前旧库不存在**，需新建）。
若 MDM 暂无，看板降级方案：`SELECT DISTINCT project_id FROM mart.fct_sample`。

### 3.4 `mart.dim_group`

| 字段 | 类型 | 说明 |
|---|---|---|
| group_id | text PK | 课题组 ID（TT1/TT5/PD/TT7/RD_GROUP_*/QD/RD 等） |
| group_name | text | 课题组中文名 |
| sort_order | int | 显示顺序 |

来源：`cmc_mdm.mdm_core.group_master`（**当前旧库不存在**，需新建）。
若 MDM 暂无，看板降级方案：硬编码或 `SELECT DISTINCT group_id FROM mart.fct_sample`。

## 4. 兼容视图（看板直接消费）

每张视图都是上面 fct/dim 的 join + 派生列。语义与旧 `app_rd.v_*` 严格一致，保证看板 SQL 改最少。

### 4.1 `mart.vw_test_task_monitor`（核心宽表，对应旧 `v_test_task_monitor`）

```sql
CREATE VIEW mart.vw_test_task_monitor AS
SELECT
  t.test_id,
  t.sample_id,
  s.project_id,
  s.sample_name,
  s.batch_number,
  s.sample_type,
  s.test_type,
  t.method_code,
  t.method_name,
  s.request_dt,
  s.received_dt           AS sample_received_dt,
  t.groupleader_received_dt,
  t.assigned_dt,
  t.started_dt            AS test_started_dt,
  t.completed_dt          AS test_completed_dt,
  t.authorised_dt         AS test_authorised_dt,
  t.tester,
  t.authoriser,
  t.group_id,
  s.status                AS sample_status,
  t.status                AS test_status,
  CASE
    WHEN t.status = ANY(ARRAY['A','C']) THEN 'completed'
    WHEN t.status = ANY(ARRAY['U','V','P']) THEN 'pending'
    WHEN t.status = 'X' THEN 'cancelled'
    ELSE 'unknown'
  END AS task_bucket
FROM mart.fct_test t
LEFT JOIN mart.fct_sample s ON t.sample_id = s.sample_id;
```

### 4.2 `mart.vw_sample_overview`（对应旧 `v_sample_overview`）

`SELECT ... FROM mart.fct_sample`（字段集见 §2.1，但保留旧视图列顺序）。

### 4.3 `mart.vw_completed_tests` / `vw_pending_tests`

`SELECT ... FROM mart.vw_test_task_monitor WHERE task_bucket = 'completed'` / `'pending'`。

### 4.4 `mart.vw_overdue_snapshot`（对应旧 `v_overdue_snapshot`）

```sql
CREATE VIEW mart.vw_overdue_snapshot AS
SELECT *,
  CASE
    WHEN sample_status = 'U' THEN 'unsubmitted'
    WHEN sample_status = ANY(ARRAY['V','C','A']) AND assigned_dt IS NULL THEN 'unassigned'
    WHEN assigned_dt IS NOT NULL AND test_completed_dt IS NULL AND test_status <> 'X' THEN 'inprogress'
    WHEN test_completed_dt IS NOT NULL AND test_authorised_dt IS NULL THEN 'unauthorized'
    ELSE 'other'
  END AS overdue_bucket
FROM mart.vw_test_task_monitor
WHERE test_status <> 'X';
```

### 4.5 `mart.vw_turnaround_time`（对应旧 `v_turnaround_time`）

在 `vw_test_task_monitor` 基础上加 6 个小时数列：`hr_receive_to_grouplead` / `hr_grouplead_to_assign` / `hr_assign_to_start` / `hr_start_to_complete` / `hr_complete_to_authorise` / `hr_total_tat`，公式见旧视图定义。

### 4.6 `mart.vw_daily_workload`（对应旧 `v_daily_workload`）

```sql
CREATE VIEW mart.vw_daily_workload AS
SELECT
  date(test_completed_dt) AS stat_date,
  project_id, group_id, tester, method_code, method_name,
  COUNT(*) AS completed_test_count
FROM mart.vw_test_task_monitor
WHERE test_completed_dt IS NOT NULL
GROUP BY 1,2,3,4,5,6;
```

## 5. 权限

| 账号 | 用途 | 授权范围 |
|---|---|---|
| `analytics_reader` | 看板只读 | `cmc_analytics.mart.*` SELECT；`cmc_analytics.snap_mdm.*` SELECT（如需） |
| `mdm_admin` | 看板 admin 写主数据 | `cmc_mdm.mdm_quality.*` / `mdm_core.*` SELECT + 必要写权限 |

看板 `.env`：
```
ANALYTICS_DATABASE_URL=postgresql+asyncpg://analytics_reader:***@<rd_pg>:5432/cmc_analytics
MDM_DATABASE_URL=postgresql+asyncpg://mdm_admin:***@<mdm_pg>:5433/cmc_mdm
```

## 6. 落地清单与状态

数据侧建好一项请把状态改成 `✅`，并标注完成日期。

| # | 对象 | 类型 | 状态 | 完成日期 | 备注 |
|---|---|---|---|---|---|
| 1 | `mart.fct_sample` | TABLE | ⬜ | | |
| 2 | `mart.fct_test` | TABLE | ⬜ | | |
| 3 | `mart.dim_method` | TABLE/VIEW | ⬜ | | 上游 `cmc_mdm.mdm_quality.method_master` |
| 4 | `mart.dim_employee` | TABLE/VIEW | ⬜ | | 上游 `cmc_mdm.mdm_core.employee_master` |
| 5 | `mart.dim_project` | TABLE/VIEW | ⬜ | | 上游待建；或先 `DISTINCT` 兜底 |
| 6 | `mart.dim_group` | TABLE/VIEW | ⬜ | | 上游待建；或先 `DISTINCT` 兜底 |
| 7 | `mart.vw_test_task_monitor` | VIEW | ⬜ | | 看板第一依赖 |
| 8 | `mart.vw_sample_overview` | VIEW | ⬜ | | |
| 9 | `mart.vw_completed_tests` | VIEW | ⬜ | | |
| 10 | `mart.vw_pending_tests` | VIEW | ⬜ | | |
| 11 | `mart.vw_overdue_snapshot` | VIEW | ⬜ | | |
| 12 | `mart.vw_turnaround_time` | VIEW | ⬜ | | |
| 13 | `mart.vw_daily_workload` | VIEW | ⬜ | | |
| 14 | `analytics_reader` 账号 + 授权 | ROLE | ⬜ | | |
| 15 | `mdm_admin` 账号 + 授权 | ROLE | ⬜ | | |

## 7. 已知开放问题

1. `cmc_rd.raw_rd_lims_samplemanager` 目前只有 sample/test/result 3 张原表，**字段是否与旧库 `staging_rd.sample_clean/test_clean` 完全对齐？** 若新 raw 缺字段（例如 production_line_id / timepoint / status 编码），ETL 需要补齐到 staging 才能进 mart。
2. `dim_project` / `dim_group` 在 cmc_mdm 是否已建？若未建，是先在 mart 内 `DISTINCT` 兜底，还是同步推动 MDM 团队建表？
3. `tester` / `authoriser` 字段值在 `test_clean` 里有 47/21 种，但 `dim_employee` 只有 29 条——有未注册员工。**join 用 LEFT 还是 INNER？** 看板默认 LEFT（保留未注册的人），但需要在 mart 视图里也保持一致。
