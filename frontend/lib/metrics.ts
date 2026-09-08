// 三类曲线的可选指标定义（批次曲线页公用）。
// 不同单位 SeriesChart 会自动左右分坐标轴。
import type { GrowthPoint, NovaPoint, ProcessBucketPoint } from "./api";

export interface MetricDef<P> {
  code: string;
  name: string;
  unit: string;
  pick: (p: P) => number | null;
}

// 细胞（Vi-CELL）
export const CELL_METRICS: MetricDef<GrowthPoint>[] = [
  { code: "total_per_ml", name: "总细胞密度", unit: "×10⁶/ml", pick: (p) => p.total_per_ml },
  { code: "viable_per_ml", name: "活细胞密度", unit: "×10⁶/ml", pick: (p) => p.viable_per_ml },
  { code: "viability_pct", name: "活率", unit: "%", pick: (p) => p.viability_pct },
  { code: "avg_diameter_um", name: "平均直径", unit: "µm", pick: (p) => p.avg_diameter_um },
];
export const CELL_DEFAULT_METRICS = ["viable_per_ml", "viability_pct"];

// 生化（Nova FLEX2；数据没有渗透压列）
export const NOVA_METRICS: MetricDef<NovaPoint>[] = [
  { code: "gluc", name: "葡萄糖", unit: "g/L", pick: (p) => p.gluc },
  { code: "lac", name: "乳酸", unit: "g/L", pick: (p) => p.lac },
  { code: "nh4", name: "氨", unit: "mmol/L", pick: (p) => p.nh4 },
  { code: "gln", name: "谷氨酰胺", unit: "mmol/L", pick: (p) => p.gln },
  { code: "glu", name: "谷氨酸", unit: "mmol/L", pick: (p) => p.glu },
  { code: "na", name: "钠", unit: "mmol/L", pick: (p) => p.na },
  { code: "k", name: "钾", unit: "mmol/L", pick: (p) => p.k },
  { code: "ca", name: "钙", unit: "mmol/L", pick: (p) => p.ca },
  { code: "ph", name: "pH", unit: "", pick: (p) => p.ph },
  { code: "po2", name: "氧分压", unit: "mmHg", pick: (p) => p.po2 },
  { code: "pco2", name: "二氧化碳分压", unit: "mmHg", pick: (p) => p.pco2 },
];
export const NOVA_DEFAULT_METRICS = ["gluc", "lac", "nh4", "gln"];

// 工艺按时段汇总（Lucullus 原始时序按每 N 小时一格；平均值，溶氧另有格内最低，加碱/加酸为格内累计末值）
export const PROCESS_METRICS: MetricDef<ProcessBucketPoint>[] = [
  { code: "temp_c", name: "温度", unit: "°C", pick: (p) => p.temp_c },
  { code: "ph", name: "pH", unit: "", pick: (p) => p.ph },
  { code: "do_pct", name: "溶氧", unit: "%", pick: (p) => p.do_pct },
  { code: "do_pct_min", name: "溶氧最低", unit: "%", pick: (p) => p.do_pct_min },
  { code: "stirrer_rpm", name: "搅拌", unit: "rpm", pick: (p) => p.stirrer_rpm },
  { code: "air_surface", name: "空气(表层)", unit: "mL/min", pick: (p) => p.air_surface },
  { code: "air_sparge", name: "空气(深层)", unit: "mL/min", pick: (p) => p.air_sparge },
  { code: "o2", name: "O₂(0-1000)", unit: "mL/min", pick: (p) => p.o2 },
  { code: "o2_low", name: "O₂(0-100)", unit: "mL/min", pick: (p) => p.o2_low },
  { code: "co2", name: "CO₂", unit: "mL/min", pick: (p) => p.co2 },
  { code: "alkali_cum", name: "加碱累计", unit: "mL", pick: (p) => p.alkali_cum },
  { code: "acid_cum", name: "加酸累计", unit: "mL", pick: (p) => p.acid_cum },
];
export const PROCESS_DEFAULT_METRICS = ["temp_c", "ph", "do_pct"];

// 时段粒度选项（小时），默认 6h（负责人 2026-09-08 定）
export const BUCKET_OPTIONS = [24, 12, 6, 3, 1];
export const DEFAULT_BUCKET_HOURS = 6;
