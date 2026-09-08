// 三类曲线的可选指标定义（批次曲线页公用）。
// 不同单位 SeriesChart 会自动左右分坐标轴。
import type { GrowthPoint, NovaPoint, ProcessBucketPoint } from "./api";

// 指标固定配色 / 固定线型（负责人 2026-09-08 定）：颜色跟指标走、不跟点击顺序走，
// 大家看久了就记住"蓝的是活率、红的是活密度"。多批次叠图时颜色归罐，指标改靠线型 + 标记（shape）区分，同样固定。
export const C = {
  blue: "#2563eb",
  red: "#dc2626",
  green: "#16a34a",
  orange: "#ea580c",
  purple: "#7c3aed",
  cyan: "#0891b2",
  pink: "#db2777",
  lime: "#65a30d",
  amber: "#b45309",
  indigo: "#4f46e5",
  teal: "#0d9488",
  crimson: "#be123c",
  slate: "#475569",
  violet: "#9333ea",
  brown: "#92400e",
} as const;

export interface MetricDef<P> {
  code: string;
  name: string;
  unit: string;
  color: string; // 固定颜色（单批次时用）
  shape: number; // 固定线型/标记序号（多批次时用）：0 实线圆点 1 虚线方块 2 点线三角 3 实线菱形 4 虚线大头针 5 点线箭头
  pick: (p: P) => number | null;
}

// 细胞（Vi-CELL）：活率蓝、活细胞密度红、总细胞密度紫、平均直径青
export const CELL_METRICS: MetricDef<GrowthPoint>[] = [
  { code: "total_per_ml", name: "总细胞密度", unit: "×10⁶/ml", color: C.purple, shape: 2, pick: (p) => p.total_per_ml },
  { code: "viable_per_ml", name: "活细胞密度", unit: "×10⁶/ml", color: C.red, shape: 0, pick: (p) => p.viable_per_ml },
  { code: "viability_pct", name: "活率", unit: "%", color: C.blue, shape: 1, pick: (p) => p.viability_pct },
  { code: "avg_diameter_um", name: "平均直径", unit: "µm", color: C.cyan, shape: 3, pick: (p) => p.avg_diameter_um },
];
export const CELL_DEFAULT_METRICS = ["viable_per_ml", "viability_pct"];

// 生化（Nova FLEX2；数据没有渗透压列）
export const NOVA_METRICS: MetricDef<NovaPoint>[] = [
  { code: "gluc", name: "葡萄糖", unit: "g/L", color: C.orange, shape: 0, pick: (p) => p.gluc },
  { code: "lac", name: "乳酸", unit: "g/L", color: C.green, shape: 1, pick: (p) => p.lac },
  { code: "nh4", name: "氨", unit: "mmol/L", color: C.amber, shape: 2, pick: (p) => p.nh4 },
  { code: "gln", name: "谷氨酰胺", unit: "mmol/L", color: C.pink, shape: 3, pick: (p) => p.gln },
  { code: "glu", name: "谷氨酸", unit: "mmol/L", color: C.indigo, shape: 4, pick: (p) => p.glu },
  { code: "na", name: "钠", unit: "mmol/L", color: C.slate, shape: 5, pick: (p) => p.na },
  { code: "k", name: "钾", unit: "mmol/L", color: C.lime, shape: 0, pick: (p) => p.k },
  { code: "ca", name: "钙", unit: "mmol/L", color: C.teal, shape: 1, pick: (p) => p.ca },
  { code: "ph", name: "pH", unit: "", color: C.violet, shape: 2, pick: (p) => p.ph },
  { code: "po2", name: "氧分压", unit: "mmHg", color: C.cyan, shape: 3, pick: (p) => p.po2 },
  { code: "pco2", name: "二氧化碳分压", unit: "mmHg", color: C.crimson, shape: 4, pick: (p) => p.pco2 },
];
export const NOVA_DEFAULT_METRICS = ["gluc", "lac", "nh4", "gln"];

// 工艺按时段汇总（Lucullus 原始时序按每 N 小时一格；平均值，溶氧另有格内最低，加碱/加酸为格内累计末值）
export const PROCESS_METRICS: MetricDef<ProcessBucketPoint>[] = [
  { code: "temp_c", name: "温度", unit: "°C", color: C.orange, shape: 0, pick: (p) => p.temp_c },
  { code: "ph", name: "pH", unit: "", color: C.violet, shape: 1, pick: (p) => p.ph },
  { code: "do_pct", name: "溶氧", unit: "%", color: C.green, shape: 2, pick: (p) => p.do_pct },
  { code: "do_pct_min", name: "溶氧最低", unit: "%", color: C.lime, shape: 3, pick: (p) => p.do_pct_min },
  { code: "stirrer_rpm", name: "搅拌", unit: "rpm", color: C.slate, shape: 4, pick: (p) => p.stirrer_rpm },
  { code: "air_surface", name: "空气(表层)", unit: "mL/min", color: C.cyan, shape: 5, pick: (p) => p.air_surface },
  { code: "air_sparge", name: "空气(深层)", unit: "mL/min", color: C.teal, shape: 0, pick: (p) => p.air_sparge },
  { code: "o2", name: "O₂(0-1000)", unit: "mL/min", color: C.blue, shape: 1, pick: (p) => p.o2 },
  { code: "o2_low", name: "O₂(0-100)", unit: "mL/min", color: C.indigo, shape: 2, pick: (p) => p.o2_low },
  { code: "co2", name: "CO₂", unit: "mL/min", color: C.crimson, shape: 3, pick: (p) => p.co2 },
  { code: "alkali_cum", name: "加碱累计", unit: "mL", color: C.purple, shape: 4, pick: (p) => p.alkali_cum },
  { code: "acid_cum", name: "加酸累计", unit: "mL", color: C.pink, shape: 5, pick: (p) => p.acid_cum },
];
export const PROCESS_DEFAULT_METRICS = ["temp_c", "ph", "do_pct"];

// 时段粒度选项（小时），默认 6h（负责人 2026-09-08 定）
export const BUCKET_OPTIONS = [24, 12, 6, 3, 1];
export const DEFAULT_BUCKET_HOURS = 6;

// 全量时序的通道（78 个）：常用通道按 canonical_key 固定颜色，与上面「工艺参数」同一物理量同色；
// 其余通道按名字散列到调色板，同一通道每次都是同一个颜色（只是没有人为指定）。
const CHANNEL_COLORS: Record<string, string> = {
  temp: C.orange,
  temp_sp: C.amber,
  ph: C.violet,
  ph_sp: C.pink,
  do: C.green,
  do_sp: C.lime,
  do_opt: C.teal,
  stirrer: C.slate,
  mfc1_flow: C.cyan,
  mfc2_flow: C.teal,
  mfc3_flow: C.blue,
  mfc5_flow: C.indigo,
  mfc4_flow: C.crimson,
  dpump2_total: C.purple,
  pressure: C.brown,
  redox: C.pink,
};
const PALETTE = Object.values(C);
function hashStr(s: string): number {
  let h = 0;
  for (let i = 0; i < s.length; i++) h = (h * 31 + s.charCodeAt(i)) >>> 0;
  return h;
}
export function channelColor(key: string): string {
  return CHANNEL_COLORS[key] ?? PALETTE[hashStr(key) % PALETTE.length];
}
export function channelShape(key: string): number {
  return hashStr(key) % 6;
}
