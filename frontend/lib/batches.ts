// 批次名单的公用小工具：项目桶 / 排序 / 显示名。全站筛选（Dashboard + BatchFilter）共用。
import type { LucullusRun, OverviewBatch } from "./api";

// 项目编号解析不出的批次归入这个桶（工艺批次名不规范：test610 这类）
export const PROJ_NONE = "__none__";
export const projValue = (b: OverviewBatch) => b.project_id ?? PROJ_NONE;
export const projLabel = (v: string) => (v === PROJ_NONE ? "未识别（不规范名）" : v);

// 项目编号排序：按数字大小升序，"未识别" 垫底
export function sortProject(a: string, b: string): number {
  if (a === PROJ_NONE) return 1;
  if (b === PROJ_NONE) return -1;
  const na = parseInt(a, 10);
  const nb = parseInt(b, 10);
  if (!isNaN(na) && !isNaN(nb) && na !== nb) return na - nb;
  return a.localeCompare(b);
}

// 罐号自然排序：先按字母（A/B/R/C），再按数字（A2 在 A10 前）
export function sortReactor(a: string, b: string): number {
  const ma = /^([A-Za-z]+)(\d+)$/.exec(a);
  const mb = /^([A-Za-z]+)(\d+)$/.exec(b);
  if (ma && mb) {
    if (ma[1] !== mb[1]) return ma[1].localeCompare(mb[1]);
    return parseInt(ma[2], 10) - parseInt(mb[2], 10);
  }
  return a.localeCompare(b);
}

// 批号排序：新的在前。老批号 R2607 / 新批号 26003 都是「年 2 位 + 流水」，
// 按 (年份 desc, 流水 desc) 排；拆不出的按字符串倒序垫后。
function batchNumRank(bn: string): [number, number] | null {
  const m = /^R(\d{2})(\d{2})$/i.exec(bn) ?? /^(\d{2})(\d{3})$/.exec(bn);
  return m ? [parseInt(m[1], 10), parseInt(m[2], 10)] : null;
}
export function sortBatchNumberDesc(a: string, b: string): number {
  const ra = batchNumRank(a);
  const rb = batchNumRank(b);
  if (ra && rb) return rb[0] - ra[0] || rb[1] - ra[1];
  if (ra) return -1;
  if (rb) return 1;
  return b.localeCompare(a);
}

// 批次在图例 / 列表里的显示名：正常批次用 batch_key；不规范名批次直接用原始批次名
export function batchLabel(b: OverviewBatch): string {
  return b.unparsed ? b.lucullus_procname ?? b.batch_key : b.batch_key;
}

export const fmtDate = (s: string | null) => (s ? s.slice(0, 10) : "—");
export const fmtNum = (v: number | null, digits = 2) =>
  v == null ? "—" : v.toFixed(digits);

export function toggleIn<T>(arr: T[], v: T): T[] {
  return arr.includes(v) ? arr.filter((x) => x !== v) : [...arr, v];
}

// 同一批次的多段工艺记录（中途重开）不是并行而是先后发生的：
// 以最早一段的开始时刻为 0，其余各段按真实开始时间往后挪（小时），拼成一条连续时间轴。
// 开始时间缺失的段偏移记 0。返回按时间升序排好的 [段, 偏移小时]。
export function runOffsets(b: OverviewBatch): { run: LucullusRun; offsetHours: number }[] {
  const runs = [...b.lucullus_runs].sort((x, y) => {
    const tx = x.starttime ? Date.parse(x.starttime) : Infinity;
    const ty = y.starttime ? Date.parse(y.starttime) : Infinity;
    return tx - ty;
  });
  const t0 = runs.length && runs[0].starttime ? Date.parse(runs[0].starttime) : NaN;
  return runs.map((run) => {
    const t = run.starttime ? Date.parse(run.starttime) : NaN;
    const off = Number.isFinite(t0) && Number.isFinite(t) ? (t - t0) / 3600_000 : 0;
    return { run, offsetHours: Math.max(0, off) };
  });
}
