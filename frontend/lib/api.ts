import axios from "axios";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE ?? "http://localhost:8070";

export const http = axios.create({ baseURL: API_BASE });

export interface Batch {
  source_instance: string;
  procid: number;
  procname: string;
  starttime: string | null;
  endtime: string | null;
  reactor_name: string | null;
  project_code: string | null; // 项目编号（解析自批次名，保留前导零；解析不出为 null）
  batch_year: number | null; // 批次年份（R2605→2026，无则用开始日期年份）
  batch_number: string | null; // 批号（解析自批次名，R+4位大写；解析不出为 null）
  reactor: string | null; // 罐号（= reactor_name，权威列）
}

export interface Channel {
  channel_code: string;
  channel_name: string | null;
  unitsymbol: string | null;
  n_points: number;
  t_min_h: number | null;
  t_max_h: number | null;
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

export async function fetchBatches(): Promise<Batch[]> {
  const { data } = await http.get<Batch[]>("/api/batches");
  return data;
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

export interface VicellBatch {
  batch_key: string; // 项目_批号_罐，如 0071_R2601_B2
  project_id: string | null;
  batch_number: string | null;
  bioreactor_id: string | null;
  batch_year: number | null; // 批号解析，如 R2601 -> 2026
  n_samples: number;
  day_min: number | null;
  day_max: number | null;
  first_run_date: string | null;
  has_process_link: boolean; // 是否已关联到工艺批次（Phase 2 叠图用）
}

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

export async function fetchVicellBatches(): Promise<VicellBatch[]> {
  const { data } = await http.get<VicellBatch[]>("/api/vicell/batches");
  return data;
}

export async function fetchGrowth(batchKey: string): Promise<Growth> {
  const { data } = await http.get<Growth>("/api/vicell/growth", {
    params: { batch_key: batchKey },
  });
  return data;
}

// 按工艺批次（source_instance + procid）取关联的细胞生长曲线，用于工艺图叠加
export interface GrowthByProcid {
  source_instance: string;
  procid: number;
  points: GrowthPoint[];
}

export async function fetchGrowthByProcid(
  sourceInstance: string,
  procid: number
): Promise<GrowthByProcid> {
  const { data } = await http.get<GrowthByProcid>("/api/vicell/growth-by-procid", {
    params: { source_instance: sourceInstance, procid },
  });
  return data;
}

/** 把工作站编码变成人话，如 rd_ws01_usp_lucullus_01 -> WS01 */
export function workstationLabel(sourceInstance: string): string {
  const m = sourceInstance.match(/ws(\d+)/i);
  return m ? `WS${m[1]}` : sourceInstance;
}

// ============ Nova FLEX2 生化分析趋势 ============

export interface NovaBatch {
  batch_key: string; // 项目_批号_罐，与 Vi-CELL 同一套身份
  project_id: string | null;
  batch_number: string | null;
  bioreactor_id: string | null;
  batch_year: number | null;
  n_samples: number;
  day_min: number | null;
  day_max: number | null;
  first_measured_at: string | null;
  has_process_link: boolean;
}

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

export async function fetchNovaBatches(): Promise<NovaBatch[]> {
  const { data } = await http.get<NovaBatch[]>("/api/nova/batches");
  return data;
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

// ============ 批次总览（一个批号看全部数据源） ============

export interface OverviewBatch {
  batch_key: string;
  project_id: string | null;
  batch_number: string | null;
  bioreactor_id: string | null;
  batch_year: number | null;
  n_vicell: number; // 细胞取样数（0 = 该源没有此批）
  n_nova: number; // 生化取样数
  day_min: number | null;
  day_max: number | null;
  first_at: string | null;
  lucullus_procid: number | null; // 工艺关联（跳转工艺曲线视图用）
  lucullus_source_instance: string | null;
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

// 工艺参数按天汇总（mart.fact_process_daily，总览页嵌图）
export interface ProcessDailyPoint {
  culture_day: number;
  ph_mean: number | null;
  temp_c_mean: number | null; // 温度 °C
  do_pct_mean: number | null; // 溶氧 %
  do_pct_min: number | null;
  stirrer_rpm_mean: number | null; // 搅拌 rpm
  o2_mlmin_mean: number | null; // O₂ 流量 ml/min
  air_mlmin_mean: number | null;
  co2_mlmin_mean: number | null;
  alkali_cum_ml: number | null; // 加碱累计 ml
  acid_cum_ml: number | null;
  n_samples_max: number | null;
}

export interface ProcessDaily {
  source_instance: string;
  procid: number;
  metrics: string[];
  points: ProcessDailyPoint[];
}

export async function fetchProcessDaily(
  sourceInstance: string,
  procid: number
): Promise<ProcessDaily> {
  const { data } = await http.get<ProcessDaily>("/api/overview/process-daily", {
    params: { source_instance: sourceInstance, procid },
  });
  return data;
}
