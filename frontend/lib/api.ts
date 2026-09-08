import axios, { AxiosError, type InternalAxiosRequestConfig } from "axios";
import { clearSession, mdmLogin, mdmRefresh, type MdmUser } from "@/lib/cmabSession";

// 默认 "/usp"：所有 "/api/..." 调用实际发到 /usp/api/...，经统一门户 nginx（5100）剥掉 /usp 到后端 8070。
// 一律相对路径、同源，不写死 host:端口（.env.local 里也请写 /usp）。
const API_BASE = process.env.NEXT_PUBLIC_API_BASE ?? "/usp";

export const http = axios.create({ baseURL: API_BASE });

// ============ 统一认证（MDM 代理登录，规范见 ~/code/CLAUDE.md §8） ============
// ★ 全公司统一令牌 key（cmab-hub 统一门户 2026-08-17 拍板）：
//   localStorage['cmab_access_token'] = MDM access token 原文；localStorage['cmab_user'] = 登录返回的 user 对象
//   各子系统同源挂在 5100 之下、都读同一个 key → 门户登录一次，到处免登。
const TOKEN_KEY = "cmab_access_token";
const USER_KEY = "cmab_user";
const LEGACY_TOKEN_KEY = "usp_dashboard_token"; // 旧 key：读到就迁移一次然后删掉
if (typeof window !== "undefined") {
  const old = localStorage.getItem(LEGACY_TOKEN_KEY);
  if (old && !localStorage.getItem(TOKEN_KEY)) localStorage.setItem(TOKEN_KEY, old);
  localStorage.removeItem(LEGACY_TOKEN_KEY);
}

export function getToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem(TOKEN_KEY);
}
export function setToken(t: string, user?: unknown) {
  localStorage.setItem(TOKEN_KEY, t);
  if (user) localStorage.setItem(USER_KEY, JSON.stringify(user));
}
export function clearToken() {
  clearSession(); // 清全公司共用 key（同时广播 cmab-token-changed）
}

/** 令牌失效 → 清掉并通知 AuthGate 回登录页；reason 供登录页显示提示（idle / expired） */
export function notifyAuthExpired(reason: "idle" | "expired" | "other-tab" = "expired") {
  if (typeof window === "undefined") return;
  try {
    sessionStorage.setItem("cmab_logout_reason", reason);
  } catch {
    /* ignore */
  }
  window.dispatchEvent(new Event("usp-auth-expired"));
}

// 每个请求带上令牌；401 先用 MDM refresh（lib/cmabSession）兜底续一次并重放，续不了再回登录页。
// 主动续期与空闲登出由 AuthGate 里的会话守卫负责（规则由 MDM 会话策略配置，2026-09-04 起）。
http.interceptors.request.use((config) => {
  const t = getToken();
  if (t) config.headers.Authorization = `Bearer ${t}`;
  return config;
});
http.interceptors.response.use(
  (resp) => resp,
  async (error: AxiosError) => {
    if (error.response?.status !== 401 || typeof window === "undefined") {
      return Promise.reject(error);
    }
    const original = error.config as
      | (InternalAxiosRequestConfig & { _retried?: boolean })
      | undefined;
    const isAuthEndpoint = (original?.url ?? "").includes("/auth/login");
    if (original && !original._retried && !isAuthEndpoint && getToken()) {
      original._retried = true;
      try {
        const newToken = await mdmRefresh();
        original.headers.Authorization = `Bearer ${newToken}`;
        return http(original);
      } catch {
        /* 续不了，往下走登出 */
      }
    }
    if (!isAuthEndpoint) {
      clearToken();
      notifyAuthExpired("expired");
    }
    return Promise.reject(error);
  }
);

export interface LoginResult {
  access_token: string;
  user?: MdmUser | null;
}

// 2026-09-04 起登录直接打 MDM（同源 /mdm/api/v1）：refresh Cookie 落在 MDM 路径下，后续静默续期统一处理。
// 后端 /api/auth/login 代理保留仅供脚本/旧客户端。
export async function login(
  username: string,
  password: string
): Promise<LoginResult> {
  const r = await mdmLogin(username, password);
  return { access_token: r.access_token, user: r.user };
}

export interface Me {
  username: string;
  full_name: string | null;
  roles: string[];
  is_system: boolean; // true = 后端开放模式（本地开发，不用登录）
}

export async function fetchMe(): Promise<Me> {
  const { data } = await http.get<Me>("/api/auth/me");
  return data;
}

export interface Channel {
  channel_code: string;
  channel_name: string | null; // 源系统长名（Lucullus logiportname）
  unitsymbol: string | null;
  n_points: number;
  t_min_h: number | null;
  t_max_h: number | null;
  // 以下来自通道字典 cmc_analytics.dim.channel_dict（后端合并；字典缺行时 display_name = channel_code）
  display_name: string; // 人话名，如「溶氧设定值」
  category: string | null; // 分组：培养参数 / 气路 / 加料泵 / 液位/压力 / 阶段/其它
  canonical_key: string | null; // 同一物理量归并键（跨站/别名共用）
  is_preferred: boolean; // 同 canonical_key 内首选通道；别名为 false
  is_active: boolean; // false = 字典标记为看板不列（与其它通道逐点重复又无法归并的冗余通道）
  sort_order: number; // 字典排序
  notes: string | null;
}

export interface SeriesPoint {
  time_hours: number;
  ts: string;
  value: number;
}

export interface Series {
  source_instance: string;
  procid: number;
  channel: string;
  raw_count: number; // 该时间窗口内的原始采集点数
  returned: number; // 抽稀后返回的点数
  points: SeriesPoint[];
}

export async function fetchChannels(
  sourceInstance: string,
  procid: number
): Promise<Channel[]> {
  const { data } = await http.get<Channel[]>(
    `/api/batches/${encodeURIComponent(sourceInstance)}/${procid}/channels`
  );
  return data;
}

export async function fetchSeries(
  sourceInstance: string,
  procid: number,
  channel: string,
  maxPoints = 2000,
  tMin?: number | null,
  tMax?: number | null
): Promise<Series> {
  const { data } = await http.get<Series>("/api/series", {
    params: {
      source_instance: sourceInstance,
      procid,
      channel,
      max_points: maxPoints,
      t_min: tMin ?? undefined,
      t_max: tMax ?? undefined,
    },
  });
  return data;
}

// ============ Vi-CELL 细胞计数生长曲线 ============

export interface GrowthPoint {
  culture_day: number;
  viable_per_ml: number | null; // 活细胞密度 ×10⁶/ml
  viability_pct: number | null; // 活率 %
  total_per_ml: number | null;
  avg_diameter_um: number | null;
  n: number; // 该培养天取样次数（>1 表示已取平均）
}

export interface Growth {
  batch_key: string;
  project_id: string | null;
  batch_number: string | null;
  bioreactor_id: string | null;
  n_samples: number;
  generation: number | null; // 代次（来自 rd-batch-registry 登记表，新格式批次才有）
  seeded_from_stages: string | null; // 父容器（谁分自谁）
  points: GrowthPoint[];
}

export async function fetchGrowth(batchKey: string): Promise<Growth> {
  const { data } = await http.get<Growth>("/api/vicell/growth", {
    params: { batch_key: batchKey },
  });
  return data;
}

/** 把工作站编码变成人话，如 rd_ws01_usp_lucullus_01 -> WS01 */
export function workstationLabel(sourceInstance: string): string {
  const m = sourceInstance.match(/ws(\d+)/i);
  return m ? `WS${m[1]}` : sourceInstance;
}

// ============ Nova FLEX2 生化分析趋势 ============

// 一个培养天的全部生化指标（同天多次取样已平均）
export interface NovaPoint {
  culture_day: number;
  gluc: number | null; // 葡萄糖 g/L
  lac: number | null; // 乳酸 g/L
  gln: number | null; // 谷氨酰胺 mmol/L
  glu: number | null; // 谷氨酸 mmol/L
  nh4: number | null; // 氨 mmol/L
  na: number | null; // 钠 mmol/L
  k: number | null; // 钾 mmol/L
  ca: number | null; // 钙 mmol/L
  ph: number | null;
  po2: number | null; // 氧分压 mmHg
  pco2: number | null; // 二氧化碳分压 mmHg
  osmolality: number | null; // 渗透压 mOsm/kg（人工录入，manual.sample_result 最新值）
  n: number;
}

export interface NovaSeries {
  batch_key: string;
  project_id: string | null;
  batch_number: string | null;
  bioreactor_id: string | null;
  n_samples: number;
  metrics: string[];
  points: NovaPoint[];
}

export async function fetchNovaSeries(batchKey: string): Promise<NovaSeries> {
  const { data } = await http.get<NovaSeries>("/api/nova/series", {
    params: { batch_key: batchKey },
  });
  return data;
}

// Nova 取样明细（总览页明细表）
export interface NovaSample {
  sample_result_id: number;
  sample_id: string | null;
  culture_day: number | null;
  measured_at: string | null;
  gluc: number | null;
  lac: number | null;
  gln: number | null;
  glu: number | null;
  nh4: number | null;
  na: number | null;
  k: number | null;
  ca: number | null;
  ph: number | null;
  po2: number | null;
  pco2: number | null;
  parse_status: string;
}

export async function fetchNovaSamples(batchKey: string): Promise<NovaSample[]> {
  const { data } = await http.get<NovaSample[]>("/api/nova/samples", {
    params: { batch_key: batchKey },
  });
  return data;
}

// ============ 批次总名单（三源合并：细胞 / 生化 / 工艺，全站唯一的筛选数据源） ============

// 一段 Lucullus 工艺记录。同一批次中途重开会有 2~3 段（按开始时间倒序，[0] 为主记录）
export interface LucullusRun {
  source_instance: string; // Lucullus 工作站编码（rd_ws01_usp_lucullus_01）
  procid: number;
  procname: string | null; // 原始批次名（工作站里录的）
  starttime: string | null;
  endtime: string | null;
}

export interface OverviewBatch {
  batch_key: string; // 批次身份 项目_批号_罐；不规范名批次为 lucullus:<工作站>#<procid>
  project_id: string | null; // null = 拆不出项目（前端归入「未识别」）
  batch_number: string | null; // 批号；不规范名批次这里放原始批次名
  bioreactor_id: string | null;
  batch_year: number | null;
  n_vicell: number; // 细胞取样数（0 = 该源没有此批）
  n_nova: number; // 生化取样数
  day_min: number | null;
  day_max: number | null;
  first_at: string | null; // 最早的取样 / 工艺开始时间
  unparsed: boolean; // true = 工艺批次名不规范（test610 这类），只能按原始名字选
  lucullus_runs: LucullusRun[]; // 全部工艺记录；空 = 没有工艺数据
  lucullus_procid: number | null; // 主工艺记录（= runs[0]），日均工艺参数板块用
  lucullus_source_instance: string | null;
  lucullus_procname: string | null;
}

export async function fetchOverviewBatches(): Promise<OverviewBatch[]> {
  const { data } = await http.get<OverviewBatch[]>("/api/overview/batches");
  return data;
}

// Vi-CELL 取样明细（总览页明细表）
export interface VicellSample {
  run_id: number;
  sample_id: string | null;
  culture_day: number | null;
  run_date: string | null;
  viable_per_ml: number | null;
  viability_pct: number | null;
  total_per_ml: number | null;
  avg_diameter_um: number | null;
  avg_circularity: number | null;
  parse_status: string;
}

export async function fetchVicellSamples(batchKey: string): Promise<VicellSample[]> {
  const { data } = await http.get<VicellSample[]>("/api/vicell/samples", {
    params: { batch_key: batchKey },
  });
  return data;
}

// 数据表板块（《项目第一表》样式）：一行 = 某批次某培养天，三源列并排
export interface DailyTableRow {
  batch_key: string;
  culture_day: number | null;
  sample_date: string | null; // 取样日期（细胞/生化侧最早一次）
  // 工艺（Lucullus 按天汇总）
  ph_mean: number | null;
  do_pct_mean: number | null;
  do_pct_min: number | null;
  temp_c_mean: number | null;
  stirrer_rpm_mean: number | null;
  air_mlmin_mean: number | null;
  o2_mlmin_mean: number | null;
  co2_mlmin_mean: number | null;
  alkali_cum_ml: number | null;
  acid_cum_ml: number | null;
  // 细胞（Vi-CELL，同天多次取样已平均）
  density_tcd: number | null; // 总细胞密度 ×10⁶/ml
  density_vcd: number | null; // 活细胞密度 ×10⁶/ml
  viability_pct: number | null;
  avg_diameter_um: number | null;
  // 生化（Nova FLEX2，同天多次取样已平均）
  gluc: number | null;
  lac: number | null;
  gln: number | null;
  glu: number | null;
  nh4: number | null;
  na: number | null;
  k: number | null;
  ca: number | null;
  ph_nova: number | null;
  po2: number | null;
  pco2: number | null;
  osmolality: number | null; // 渗透压（人工录入）
  n_vicell: number; // 当天细胞取样次数（>1 = 已平均）
  n_nova: number;
  // 溯源：原始样本名（仪器录入）与解析状态；项目/批号/罐号都拆自样本名
  vicell_sample_ids: string | null;
  vicell_status: string | null; // ok / suspect / unparseable…（多个用逗号连）
  nova_sample_ids: string | null;
  nova_status: string | null;
  has_process: boolean; // 该天有 Lucullus 工艺汇总数据
}

export interface DailyTable {
  rows: DailyTableRow[];
  columns: string[];
}

export async function fetchDailyTable(batchKeys: string[]): Promise<DailyTable> {
  const { data } = await http.post<DailyTable>("/api/overview/daily-table", {
    batch_keys: batchKeys,
  });
  return data;
}

// ============ 工艺参数按时段汇总（直接从原始时序算，每 N 小时一格；板块「工艺参数（按时段）」用） ============

export interface ProcessBucketPoint {
  bucket: number;
  time_hours: number; // 该格起点（培养小时）
  culture_day: number; // 该格起点换算成培养天（6h 一格 = 0, 0.25, 0.5…），与生长/生化同轴
  temp_c: number | null;
  ph: number | null;
  do_pct: number | null;
  do_pct_min: number | null; // 格内最低
  stirrer_rpm: number | null;
  air_surface: number | null; // 表层空气 mL/min
  air_sparge: number | null; // 深层空气 mL/min
  o2: number | null; // O₂(0-1000) mL/min
  o2_low: number | null; // O₂(0-100) mL/min
  co2: number | null;
  alkali_cum: number | null; // 格内末值（累计量）
  acid_cum: number | null;
}

export interface ProcessBucketed {
  source_instance: string;
  procid: number;
  bucket_hours: number;
  metrics: { code: string; name: string; unit: string; agg: string; channel: string | null }[];
  points: ProcessBucketPoint[];
}

export async function fetchProcessBucketed(
  sourceInstance: string,
  procid: number,
  bucketHours: number
): Promise<ProcessBucketed> {
  const { data } = await http.get<ProcessBucketed>("/api/process-bucketed", {
    params: { source_instance: sourceInstance, procid, bucket_hours: bucketHours },
  });
  return data;
}

// ============ 人工录入（渗透压等）——本看板唯一的写入点 ============

export interface ManualStatus {
  enabled: boolean; // 后端配了写账号才能录
  metrics: Record<string, { name: string; unit: string; min: number; max: number }>;
}

export interface DailySheetRow {
  batch_key: string;
  project_id: string | null;
  batch_number: string | null;
  bioreactor_id: string | null;
  culture_day: number;
  sample_ids: string | null; // 当天该样品在仪器上的样本名
  has_nova: boolean;
  has_vicell: boolean;
  existing_value: number | null; // 已录的最新值
  existing_by: string | null;
  existing_by_name: string | null;
  existing_at: string | null;
  existing_note: string | null;
}

export interface DailySheet {
  sample_date: string;
  metric: { code: string; name: string; unit: string; min: number; max: number };
  rows: DailySheetRow[];
}

export async function fetchManualStatus(): Promise<ManualStatus> {
  const { data } = await http.get<ManualStatus>("/api/manual/status");
  return data;
}

export async function fetchDailySheet(sampleDate: string, metricCode = "osmolality"): Promise<DailySheet> {
  const { data } = await http.get<DailySheet>("/api/manual/daily-sheet", {
    params: { sample_date: sampleDate, metric_code: metricCode },
  });
  return data;
}

export interface ManualResultRow {
  batch_key: string;
  culture_day: number;
  value: number;
  note?: string | null;
  source_sample_ids?: string | null;
}

export async function saveManualResults(
  sampleDate: string,
  rows: ManualResultRow[],
  metricCode = "osmolality"
): Promise<{ saved: number; skipped: number }> {
  const { data } = await http.post<{ saved: number; skipped: number }>("/api/manual/results", {
    sample_date: sampleDate,
    metric_code: metricCode,
    rows,
  });
  return data;
}
