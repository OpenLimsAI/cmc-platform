// API 客户端：封装对后端的请求，所有接口调用从此处导出
import axios from "axios"

const api = axios.create({
  baseURL: process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8030",
  timeout: 15000,
  // FastAPI 期望数组参数为 ?groups=TT1&groups=TT5，axios 默认序列化为 groups[]=TT1，需覆盖
  paramsSerializer: (params) =>
    Object.entries(params)
      .flatMap(([k, v]) =>
        Array.isArray(v) ? v.map((i) => `${k}=${encodeURIComponent(i)}`) : [`${k}=${encodeURIComponent(v)}`]
      )
      .join("&"),
})

export default api

// ---------- 类型定义 ----------

export interface KPIResponse {
  sample_n: number
  test_n: number
  done_test_n: number
  pending_test_n: number
  start_date: string
  end_date: string
}

export interface MonthlyTrendItem {
  ym: string
  month_end: string
  sample_n: number
  test_n: number
  pending_test_n: number
}

export interface OverdueSummary {
  unsubmitted: number
  unassigned: number
  inprogress: number
  unauthorized: number
}

export interface OverdueMethodItem {
  method_name: string | null
  test_count: number
}

export interface OverdueResponse {
  as_of: string
  summary: OverdueSummary
  incomplete_distribution: OverdueMethodItem[]
  unsubmitted_distribution: OverdueMethodItem[]
}

export interface CycleTimeMonthlyTrendItem {
  ym: string
  completed_n: number
  avg_cycle_days: number | null
  median_cycle_days: number | null
}

export interface CycleTimeByMethodItem {
  method_name: string
  method_code: string | null
  completed_n: number
  avg_cycle_days: number | null
  median_cycle_days: number | null
  max_cycle_days: number | null
}

export interface CycleTimeByMethodResponse {
  start_date: string
  end_date: string
  items: CycleTimeByMethodItem[]
}

export interface CycleTimeTrendByMethodItem {
  ym: string
  method_name: string
  completed_n: number
  avg_cycle_days: number | null
  median_cycle_days: number | null
}

// 4 段细分（alloc=分配前 / wait=待检 / test=检验中 / review=复核授权）
export type CycleStage = "alloc" | "wait" | "test" | "review"

export interface CycleTimeStagesByMethodItem {
  method_name: string
  method_code: string | null
  completed_n: number
  alloc_n: number
  alloc_avg_days: number | null
  wait_n: number
  wait_avg_days: number | null
  test_n: number
  test_avg_days: number | null
  review_n: number
  review_avg_days: number | null
  bottleneck_stage: CycleStage | null
}

export interface CycleTimeStagesByMethodResponse {
  start_date: string
  end_date: string
  items: CycleTimeStagesByMethodItem[]
}

export interface CycleTimeStagesTrendItem {
  ym: string
  method_name: string
  method_code: string | null
  completed_n: number
  alloc_n: number
  alloc_avg_days: number | null
  wait_n: number
  wait_avg_days: number | null
  test_n: number
  test_avg_days: number | null
  review_n: number
  review_avg_days: number | null
}

export interface CycleTimeStagesTrendResponse {
  months: number
  items: CycleTimeStagesTrendItem[]
}

export interface ProjectDistributionItem {
  project_id: string
  sample_n: number
  test_n: number
  std_hours: number
}

export interface ProjectDistributionResponse {
  start_date: string
  end_date: string
  items: ProjectDistributionItem[]
}

export interface WorkloadItem {
  tester: string
  employee_name: string | null
  department: string | null
  test_n: number
  total_minutes: number
  total_hours: number
}

export interface WorkloadResponse {
  start_date: string
  end_date: string
  scope: string
  items: WorkloadItem[]
}

export interface WorkloadKPIResponse {
  start_date: string
  end_date: string
  submitted_hours: number
  completed_hours: number
  pending_hours: number
  efficiency: number | null
  missing_methods: string[]
}

export interface WorkloadByMethodItem {
  method_name: string
  method_code: string | null
  test_n: number
  total_hours: number
}

export interface WorkloadByMethodResponse {
  start_date: string
  end_date: string
  items: WorkloadByMethodItem[]
}

// ---------- 查询函数 ----------

export const fetchKPI = (params: {
  start_date?: string
  end_date?: string
  groups?: string[]
}) => api.get<KPIResponse>("/api/v1/lims/stats/kpi", { params }).then((r) => r.data)

export const fetchMonthlyTrend = (params: { months?: number; groups?: string[] }) =>
  api
    .get<{ months: number; items: MonthlyTrendItem[] }>("/api/v1/lims/stats/monthly-trend", { params })
    .then((r) => r.data)

export const fetchOverdue = (params: { as_of?: string; groups?: string[] }) =>
  api.get<OverdueResponse>("/api/v1/lims/stats/overdue", { params }).then((r) => r.data)

export const fetchCycleTimeMonthlyTrend = (params: { months?: number; groups?: string[] }) =>
  api
    .get<{ months: number; items: CycleTimeMonthlyTrendItem[] }>(
      "/api/v1/lims/stats/cycle-time/monthly-trend",
      { params }
    )
    .then((r) => r.data)

export const fetchCycleTimeByMethod = (params: {
  start_date?: string
  end_date?: string
  groups?: string[]
}) =>
  api
    .get<CycleTimeByMethodResponse>("/api/v1/lims/stats/cycle-time/by-method", { params })
    .then((r) => r.data)

export const fetchCycleTimeTrendByMethod = (params: { months?: number; groups?: string[] }) =>
  api
    .get<{ months: number; items: CycleTimeTrendByMethodItem[] }>(
      "/api/v1/lims/stats/cycle-time/trend-by-method",
      { params }
    )
    .then((r) => r.data)

export const fetchCycleTimeStagesByMethod = (params: {
  start_date?: string
  end_date?: string
  groups?: string[]
}) =>
  api
    .get<CycleTimeStagesByMethodResponse>(
      "/api/v1/lims/stats/cycle-time/stages-by-method",
      { params }
    )
    .then((r) => r.data)

export const fetchCycleTimeStagesTrendByMethod = (params: {
  months?: number
  groups?: string[]
}) =>
  api
    .get<CycleTimeStagesTrendResponse>(
      "/api/v1/lims/stats/cycle-time/stages-trend-by-method",
      { params }
    )
    .then((r) => r.data)

export const fetchProjectDistribution = (params: {
  start_date?: string
  end_date?: string
  groups?: string[]
}) =>
  api
    .get<ProjectDistributionResponse>("/api/v1/lims/stats/project-distribution", { params })
    .then((r) => r.data)

export const fetchWorkload = (params: {
  start_date?: string
  end_date?: string
  groups?: string[]
  scope?: string
}) => api.get<WorkloadResponse>("/api/v1/lims/stats/workload", { params }).then((r) => r.data)

export const fetchWorkloadKPI = (params: {
  start_date?: string
  end_date?: string
  groups?: string[]
}) => api.get<WorkloadKPIResponse>("/api/v1/lims/stats/workload-kpi", { params }).then((r) => r.data)

export const fetchWorkloadByMethod = (params: {
  start_date?: string
  end_date?: string
  groups?: string[]
  scope?: string
}) =>
  api
    .get<WorkloadByMethodResponse>("/api/v1/lims/stats/workload-by-method", { params })
    .then((r) => r.data)

export interface MethodDistributionItem {
  method_name: string
  method_code: string | null
  test_count: number
}

export interface MethodDistributionResponse {
  start_date: string
  end_date: string
  items: MethodDistributionItem[]
}

export const fetchMethodDistribution = (params: {
  start_date?: string
  end_date?: string
  groups?: string[]
}) =>
  api
    .get<MethodDistributionResponse>("/api/v1/lims/stats/method-distribution", { params })
    .then((r) => r.data)

export interface MethodTargetItem {
  method_code: string
  method_name: string | null
  target_days: number | null
}

export const fetchGroups = () =>
  api.get<string[]>("/api/v1/lims/meta/groups").then((r) => r.data)

export interface DataFreshnessResponse {
  db_name: string
  etl_last_run_at: string | null  // ETL 跑完时间（cmc_rd.meta.etl_run.run_finished_at），无配 raw 库时为 null
  data_max_at: string | null      // 业务数据最新时间（staging.stg_result.updated_at 的 MAX）
}

export const fetchDataFreshness = () =>
  api.get<DataFreshnessResponse>("/api/v1/lims/stats/data-freshness").then((r) => r.data)

export const fetchMethodTargets = () =>
  api.get<MethodTargetItem[]>("/api/v1/lims/meta/method-targets").then((r) => r.data)

// ---------- 样本总览 ----------

export interface SampleListItem {
  sample_id: string
  project_id: string | null
  sample_name: string | null
  batch_number: string | null
  sample_type: string | null
  received_dt: string | null
  completed_dt: string | null
  authorised_dt: string | null
  tester: string | null
  group_id: string | null
  status: string | null
}

export interface SampleListResponse {
  total: number
  page: number
  page_size: number
  items: SampleListItem[]
}

export const fetchSampleList = (params: {
  start_date?: string
  end_date?: string
  groups?: string[]
  status_filter?: string
  project_search?: string
  page?: number
  page_size?: number
}) => api.get<SampleListResponse>("/api/v1/lims/stats/sample-list", { params }).then((r) => r.data)

// ---------- 方法月度报表 ----------

export interface MethodMonthlyItem {
  ym: string
  method_name: string
  method_code: string | null
  test_n: number
  std_hours: number
}

export interface MethodMonthlyResponse {
  months: number
  items: MethodMonthlyItem[]
}

export const fetchMethodMonthly = (params: { months?: number; groups?: string[] }) =>
  api.get<MethodMonthlyResponse>("/api/v1/lims/stats/method-monthly", { params }).then((r) => r.data)
