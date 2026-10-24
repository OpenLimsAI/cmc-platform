// API 客户端：封装对后端的请求，所有接口调用从此处导出
// 认证：请求自动带 MDM JWT（Bearer）；access 快过期时用 HttpOnly refresh Cookie 无感续期（对齐 labops 接法）
import axios, { AxiosError, type InternalAxiosRequestConfig } from "axios"
import { BASE, clearAuth, getToken, setToken, stripBase, withBase } from "@/lib/auth"
import { mdmLogin, mdmLogout, mdmRefresh } from "@/lib/cmabSession"

// 默认 "/lims"：所有 "/api/v1/..." 调用实际发到 /lims/api/v1/...，经统一门户 nginx（5100）剥掉 /lims 到后端 8030。
// 一律相对路径、同源，不写死 host:端口（.env.local 里也请写 /lims）。
const BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL || BASE

// FastAPI 期望数组参数为 ?groups=TT1&groups=TT5，axios 默认序列化为 groups[]=TT1，需覆盖。
// axios 会把 params 对象原样交给自定义 serializer，必须自己滤掉 undefined/null，
// 否则 String(undefined) 变成字面文字 "undefined" 发给后端（曾导致样品搜索/全部检验组查无数据）
const paramsSerializer = (params: Record<string, unknown>) =>
  Object.entries(params)
    .filter(([, v]) => v !== undefined && v !== null)
    .flatMap(([k, v]) =>
      Array.isArray(v)
        ? v.filter((i) => i !== undefined && i !== null).map((i) => `${k}=${encodeURIComponent(i)}`)
        : [`${k}=${encodeURIComponent(String(v))}`]
    )
    .join("&")

const api = axios.create({
  baseURL: BASE_URL,
  timeout: 15000,
  withCredentials: true, // 携带 refresh Cookie
  paramsSerializer,
})

// 认证（2026-09-04 起）：登录/续期/登出统一直接打 MDM（lib/cmabSession.ts）；本客户端只负责带令牌 +
// 401 时用 MDM refresh 兜底续一次并重放。主动续期与空闲登出由 AuthGuard 里的会话守卫负责。
function forceLogout() {
  clearAuth()
  if (typeof window !== "undefined") {
    const path = stripBase(window.location.pathname) // 去掉 /lims 前缀，redirect 只存站内相对路径
    if (!path.startsWith("/login")) {
      window.location.href = withBase(`/login?reason=expired&redirect=${encodeURIComponent(path + window.location.search)}`)
    }
  }
}

// 请求拦截器：带 token
api.interceptors.request.use((config: InternalAxiosRequestConfig) => {
  const token = getToken()
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})

// 响应拦截器：401 兜底续期 + 重放原请求（只重试一次，防死循环）
api.interceptors.response.use(
  (resp) => resp,
  async (error: AxiosError) => {
    const status = error.response?.status
    const original = error.config as (InternalAxiosRequestConfig & { _retried?: boolean }) | undefined
    // 登录/续期接口自身的 401 不触发续期重放（否则登录密码错会被误当作会话失效）
    const url = original?.url ?? ""
    const isAuthEndpoint = url.includes("/auth/login") || url.includes("/auth/refresh")

    if (status === 401 && original && !original._retried && !isAuthEndpoint) {
      original._retried = true
      try {
        const newToken = await mdmRefresh()
        original.headers.Authorization = `Bearer ${newToken}`
        return api(original) // 用新 token 重放原请求
      } catch {
        forceLogout()
        return Promise.reject(error)
      }
    }
    if (status === 401 && !isAuthEndpoint) {
      forceLogout()
    }
    return Promise.reject(error)
  }
)

export default api

// ---------- 认证 ----------

export interface LoginResult {
  access_token: string
  [k: string]: unknown
}

// 2026-09-04 起登录直接打 MDM（同源 /mdm/api/v1）：refresh Cookie 落在 MDM 路径下，后续静默续期统一处理。
// 后端 /api/v1/auth/login 代理保留仅供脚本/旧客户端。
export const login = (username: string, password: string): Promise<LoginResult> =>
  mdmLogin(username, password).then((r) => ({ access_token: r.access_token, user: r.user }))

export const logout = async () => {
  await mdmLogout() // 撤销 MDM refresh（best-effort）+ 清全公司共用令牌
  clearAuth()
}

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

export interface OverdueListItem {
  sample_id: string | null
  sample_name: string | null
  batch_number: string | null
  project_id: string | null
  group_id: string | null
  method_code: string | null
  method_name: string | null
  sample_received_dt: string | null
  assigned_dt: string | null
  starter: string | null         // 检验员姓名（工号已转姓名，无字典记录时回落工号）
  test_status: string | null
  sample_status: string | null
  target_days: number | null     // 检验时限（dim_method.target_days），飘红阈值
  overdue_bucket: string | null  // inprogress / unauthorized
  overdue_days: number | null    // 超期未检天数 = as_of − assigned_dt（自然日）
}

export interface OverdueListResponse {
  as_of: string
  items: OverdueListItem[]
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

export const fetchOverdueList = (params: { as_of?: string; groups?: string[] }) =>
  api.get<OverdueListResponse>("/api/v1/lims/stats/overdue/list", { params }).then((r) => r.data)

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

export interface OverTargetPendingResponse {
  as_of: string
  pending_n: number      // 当前未检完检项总数（结存 V+C）
  over_target_n: number  // 其中收样至今工作日 > 检验时限(无则默认) 的检项数
}

export const fetchOverTargetPending = (params: {
  as_of?: string
  groups?: string[]
  default_target?: number
}) =>
  api
    .get<OverTargetPendingResponse>("/api/v1/lims/stats/cycle-time/overtarget-pending", { params })
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

// 导出待检测检项 CSV。必须走 api 实例（带 Bearer + 无感续期）：
// 裸 <a href> 不带令牌，AUTH_REQUIRED=true 的环境点了必 401
export const downloadPendingTestsCsv = async (groups?: string[]) => {
  const resp = await api.get<Blob>("/api/v1/lims/stats/pending-tests-csv", {
    params: { groups: groups?.length ? groups : undefined },
    responseType: "blob",
  })
  const cd = String(resp.headers["content-disposition"] ?? "")
  const filename = /filename="?([^";]+)"?/.exec(cd)?.[1] ?? "pending_tests.csv"
  const url = URL.createObjectURL(resp.data)
  const a = document.createElement("a")
  a.href = url
  a.download = filename
  a.click()
  URL.revokeObjectURL(url)
}

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

// ---------- 检验员工作台（docs/tester_workbench.md） ----------

export interface TesterOption {
  employee_id: string
  employee_name: string | null
  group_ids: string[]
  pending_n: number
}

export interface TesterSummary {
  tester: string
  employee_name: string | null
  as_of: string
  default_target: number
  soon_days: number
  pending_n: number
  over_target_n: number
  due_soon_n: number
  unauthorized_n: number
  oldest_received_dt: string | null
  month_completed_n: number
  month_std_hours: number
  month_avg_cycle_days: number | null
  prev_month_completed_n: number
  prev_month_avg_cycle_days: number | null
}

export interface TesterTaskItem {
  test_id: string
  sample_id: string | null
  project_id: string | null
  sample_name: string | null
  batch_number: string | null
  group_id: string | null
  method_code: string | null
  method_name: string | null
  sample_received_dt: string | null
  assigned_dt: string | null
  test_completed_dt: string | null
  test_status: string | null
  bucket: "inprogress" | "unauthorized"
  elapsed_biz_days: number
  target_days: number
  target_is_default: boolean
  remaining_biz_days: number
  is_over_target: boolean
  is_due_soon: boolean
}

export interface TesterTasksResponse {
  tester: string
  as_of: string
  items: TesterTaskItem[]
}

export interface TesterMonthlyItem {
  ym: string
  completed_n: number
  std_hours: number
  avg_cycle_days: number | null
}

export interface TesterMonthlyResponse {
  tester: string
  months: number
  items: TesterMonthlyItem[]
}

export interface TesterQueryParams {
  tester: string
  as_of?: string
  default_target?: number
  soon_days?: number
}

export const fetchTesterList = (params: { groups?: string[] }) =>
  api.get<TesterOption[]>("/api/v1/lims/tester/list", { params }).then((r) => r.data)

export const fetchTesterSummary = (params: TesterQueryParams) =>
  api.get<TesterSummary>("/api/v1/lims/tester/summary", { params }).then((r) => r.data)

export const fetchTesterTasks = (params: TesterQueryParams) =>
  api.get<TesterTasksResponse>("/api/v1/lims/tester/tasks", { params }).then((r) => r.data)

export const fetchTesterMonthly = (params: { tester: string; months?: number }) =>
  api.get<TesterMonthlyResponse>("/api/v1/lims/tester/monthly", { params }).then((r) => r.data)
