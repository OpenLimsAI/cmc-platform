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

/** 把工作站编码变成人话，如 rd_ws01_usp_lucullus_01 -> WS01 */
export function workstationLabel(sourceInstance: string): string {
  const m = sourceInstance.match(/ws(\d+)/i);
  return m ? `WS${m[1]}` : sourceInstance;
}
