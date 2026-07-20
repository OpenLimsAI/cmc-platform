// API 客户端：封装对后端的请求，所有接口调用从此处导出
// 认证：请求自动带 MDM JWT（Bearer）；access 快过期时用 HttpOnly refresh Cookie 无感续期（对齐 labops 接法）
import axios, { AxiosError, type InternalAxiosRequestConfig } from "axios"
import { clearAuth, getToken, setToken } from "@/lib/auth"

const BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8030"

// FastAPI 期望数组参数为 ?groups=TT1&groups=TT5，axios 默认序列化为 groups[]=TT1，需覆盖
const paramsSerializer = (params: Record<string, unknown>) =>
  Object.entries(params)
    .flatMap(([k, v]) =>
      Array.isArray(v) ? v.map((i) => `${k}=${encodeURIComponent(i)}`) : [`${k}=${encodeURIComponent(String(v))}`]
    )
    .join("&")

const api = axios.create({
  baseURL: BASE_URL,
  timeout: 15000,
  withCredentials: true, // 携带 refresh Cookie
  paramsSerializer,
})

// 裸客户端：仅用于调 /auth/refresh，不挂续期拦截器，避免递归
const bare = axios.create({ baseURL: BASE_URL, timeout: 15000, withCredentials: true })

const REFRESH_AHEAD_MS = 5 * 60 * 1000 // access 剩余 < 5 分钟时主动续期

/** 解 JWT 的 exp(毫秒)；解析失败返回 0（当作不过期，交给 401 兜底）。 */
function tokenExpMs(token: string): number {
  try {
    const payload = JSON.parse(atob(token.split(".")[1]))
    return payload?.exp ? payload.exp * 1000 : 0
  } catch {
    return 0
  }
}

function forceLogout() {
  clearAuth()
  if (typeof window !== "undefined" && !window.location.pathname.startsWith("/login")) {
    window.location.href = `/login?redirect=${encodeURIComponent(window.location.pathname + window.location.search)}`
  }
}

// 并发控制：同一时刻只发起一次 refresh，其余请求等待同一个 promise
let refreshPromise: Promise<string> | null = null

function doRefresh(): Promise<string> {
  if (!refreshPromise) {
    refreshPromise = bare
      .post("/api/v1/auth/refresh")
      .then((resp) => {
        const newToken: string | undefined = resp.data?.access_token
        if (!newToken) throw new Error("refresh 未返回 access_token")
        setToken(newToken)
        return newToken
      })
      .finally(() => {
        refreshPromise = null
      })
  }
  return refreshPromise
}

// 请求拦截器：带 token；若 access 快过期则先主动续期
api.interceptors.request.use(async (config: InternalAxiosRequestConfig) => {
  let token = getToken()
  if (token) {
    const exp = tokenExpMs(token)
    if (exp && exp - Date.now() < REFRESH_AHEAD_MS) {
      try {
        token = await doRefresh()
      } catch {
        // 主动续期失败：放行用原 token，由响应 401 兜底再处理
      }
    }
    if (token) config.headers.Authorization = `Bearer ${token}`
  }
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
        const newToken = await doRefresh()
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

export const login = (username: string, password: string) =>
  api.post<LoginResult>("/api/v1/auth/login", { username, password }).then((r) => r.data)

export const logout = async () => {
  try {
    await api.post("/api/v1/auth/logout")
  } catch {
    // best-effort：MDM 不可达也照常清本地登录态
  }
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
