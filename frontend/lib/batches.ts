// 批次名单的公用小工具：项目桶 / 排序 / 显示名。全站筛选（Dashboard + BatchFilter）共用。
import type { LucullusRun, OverviewBatch } from "./api";

// 项目编号解析不出的批次归入这个桶（工艺批次名不规范：test610 这类）
export const PROJ_NONE = "__none__";
export const projValue = (b: OverviewBatch) => b.project_id ?? PROJ_NONE;
export const projLabel = (v: string) => (v === PROJ_NONE ? "未识别（不规范名）" : v);

// 项目编号排序（负责人 2026-09-08 定）：按数字从小到大，同一开头的归在一起——
// 4 位的 0071 / 0072 / 0082 / 0092 视为 007 / 008 / 009 的分支，紧跟在主编号后面：
//   007、0071、0072、008、0082、009、0092、015、016、022、515、807、820、2026；
// 非数字的（A10 / CHO 这类假项目）排后，"未识别" 垫底。
function projectRank(code: string): [number, string] | null {
  const m = /^(00\d)(\d)$/.exec(code); // 0071 → 主编号 007 + 分支 1
  if (m) return [parseInt(m[1], 10), m[2]];
  if (/^\d+$/.test(code)) return [parseInt(code, 10), ""];
  return null;
}
export function sortProject(a: string, b: string): number {
  if (a === PROJ_NONE) return 1;
  if (b === PROJ_NONE) return -1;
  const ra = projectRank(a);
  const rb = projectRank(b);
  if (ra && rb) return ra[0] - rb[0] || ra[1].localeCompare(rb[1]);
  if (ra) return -1;
  if (rb) return 1;
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

// 批号排序（负责人 2026-09-08 定，越简单越好）：
//   登记系统新批号（5 位数字，如 26003）全部放最上面，按数字从大到小；
//   老批号 R+数字（如 R2607）放它们下面，按 R 后面的数字从大到小；
//   其它拆不出来的（不规范名）垫底，按字符串倒序。
function batchNumGroup(bn: string): [number, number] {
  let m = /^(\d{5})$/.exec(bn);
  if (m) return [0, parseInt(m[1], 10)];
  m = /^R(\d+)$/i.exec(bn);
  if (m) return [1, parseInt(m[1], 10)];
  return [2, 0];
}
export function sortBatchNumberDesc(a: string, b: string): number {
  const [ga, na] = batchNumGroup(a);
  const [gb, nb] = batchNumGroup(b);
  if (ga !== gb) return ga - gb;
  if (na !== nb) return nb - na;
  return b.localeCompare(a);
}

// 真罐号集合：A1–A10、B1–B8、R1–R4、C1。其余（样本名录错拆出来的 "1"、"demo"、"SF3"…）折叠成「其它」
const REAL_REACTOR = /^(?:A(?:10|[1-9])|B[1-8]|R[1-4]|C1)$/i;
export const REACTOR_OTHER = "__other__";
export const isRealReactor = (code: string | null | undefined) => !!code && REAL_REACTOR.test(code);
// 批次在罐号筛选里的取值：真罐号原样，其余归「其它」
export const reactorValue = (b: OverviewBatch) =>
  isRealReactor(b.bioreactor_id) ? (b.bioreactor_id as string).toUpperCase() : REACTOR_OTHER;
export const reactorLabel = (v: string) => (v === REACTOR_OTHER ? "其它" : v);

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
