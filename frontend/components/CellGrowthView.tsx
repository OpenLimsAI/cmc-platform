"use client";

import { useEffect, useMemo, useState } from "react";
import { useQuery, keepPreviousData } from "@tanstack/react-query";
import {
  fetchVicellBatches,
  fetchGrowth,
  type VicellBatch,
  type GrowthPoint,
} from "@/lib/api";
import { SeriesChart, type ChartSeries } from "@/components/SeriesChart";

// 可选细胞指标（chip 勾选）。不同单位 SeriesChart 会自动左右分坐标轴。
const CELL_METRICS: {
  code: string;
  name: string;
  unit: string;
  pick: (p: GrowthPoint) => number | null;
}[] = [
  { code: "total_per_ml", name: "总细胞密度", unit: "×10⁶/ml", pick: (p) => p.total_per_ml },
  { code: "viable_per_ml", name: "活细胞密度", unit: "×10⁶/ml", pick: (p) => p.viable_per_ml },
  { code: "viability_pct", name: "活率", unit: "%", pick: (p) => p.viability_pct },
  { code: "avg_diameter_um", name: "平均直径", unit: "µm", pick: (p) => p.avg_diameter_um },
];

// 默认勾选：活细胞密度 + 活率（保持原有行为）
const DEFAULT_METRICS = ["viable_per_ml", "viability_pct"];

// 项目编号解析不出的批次归入这个桶
const PROJ_NONE = "__none__";
const projValue = (b: VicellBatch) => b.project_id ?? PROJ_NONE;
const projLabel = (v: string) => (v === PROJ_NONE ? "未识别" : v);

// 项目编号排序：按数字大小升序，"未识别" 垫底
function sortProject(a: string, b: string): number {
  if (a === PROJ_NONE) return 1;
  if (b === PROJ_NONE) return -1;
  const na = parseInt(a, 10);
  const nb = parseInt(b, 10);
  if (!isNaN(na) && !isNaN(nb) && na !== nb) return na - nb;
  return a.localeCompare(b);
}

// 罐号自然排序：先按字母（A/B/R），再按数字（B2 在 B10 前）
function sortReactor(a: string, b: string): number {
  const ma = /^([A-Za-z]+)(\d+)$/.exec(a);
  const mb = /^([A-Za-z]+)(\d+)$/.exec(b);
  if (ma && mb) {
    if (ma[1] !== mb[1]) return ma[1].localeCompare(mb[1]);
    return parseInt(ma[2], 10) - parseInt(mb[2], 10);
  }
  return a.localeCompare(b);
}

export function CellGrowthView() {
  const [selected, setSelected] = useState<VicellBatch | null>(null);
  // 勾选要看的细胞指标（code 见 CELL_METRICS）
  const [metrics, setMetrics] = useState<string[]>(DEFAULT_METRICS);

  function toggleMetric(code: string) {
    setMetrics((prev) =>
      prev.includes(code) ? prev.filter((c) => c !== code) : [...prev, code]
    );
  }

  // 四个级联筛选：项目编号 / 批次年份 / 批号 / 罐号（"" = 全部）
  const [fProject, setFProject] = useState<string>("");
  const [fYear, setFYear] = useState<string>("");
  const [fBatch, setFBatch] = useState<string>("");
  const [fReactor, setFReactor] = useState<string>("");

  const batchesQ = useQuery({
    queryKey: ["vicell-batches"],
    queryFn: fetchVicellBatches,
  });

  const growthQ = useQuery({
    queryKey: ["vicell-growth", selected?.batch_key],
    queryFn: () => fetchGrowth(selected!.batch_key),
    enabled: !!selected,
    placeholderData: keepPreviousData,
  });

  const allBatches = batchesQ.data ?? [];

  const projectOptions = useMemo(() => {
    const s = new Set<string>();
    allBatches.forEach((b) => s.add(projValue(b)));
    return [...s].sort(sortProject);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [batchesQ.data]);

  const yearOptions = useMemo(() => {
    const s = new Set<number>();
    allBatches.forEach((b) => {
      if (fProject && projValue(b) !== fProject) return;
      if (b.batch_year != null) s.add(b.batch_year);
    });
    return [...s].sort((a, b) => b - a);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [batchesQ.data, fProject]);

  const batchOptions = useMemo(() => {
    const s = new Set<string>();
    allBatches.forEach((b) => {
      if (fProject && projValue(b) !== fProject) return;
      if (fYear && String(b.batch_year) !== fYear) return;
      if (b.batch_number) s.add(b.batch_number);
    });
    return [...s].sort();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [batchesQ.data, fProject, fYear]);

  const reactorOptions = useMemo(() => {
    const s = new Set<string>();
    allBatches.forEach((b) => {
      if (fProject && projValue(b) !== fProject) return;
      if (fYear && String(b.batch_year) !== fYear) return;
      if (fBatch && b.batch_number !== fBatch) return;
      if (b.bioreactor_id) s.add(b.bioreactor_id);
    });
    return [...s].sort(sortReactor);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [batchesQ.data, fProject, fYear, fBatch]);

  const filteredBatches = useMemo(() => {
    return allBatches.filter((b) => {
      if (fProject && projValue(b) !== fProject) return false;
      if (fYear && String(b.batch_year) !== fYear) return false;
      if (fBatch && b.batch_number !== fBatch) return false;
      if (fReactor && b.bioreactor_id !== fReactor) return false;
      return true;
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [batchesQ.data, fProject, fYear, fBatch, fReactor]);

  // 上层筛选变了 → 下层若已失效则自动清空（保证级联一致）
  useEffect(() => {
    if (fYear && !yearOptions.map(String).includes(fYear)) setFYear("");
  }, [yearOptions, fYear]);
  useEffect(() => {
    if (fBatch && !batchOptions.includes(fBatch)) setFBatch("");
  }, [batchOptions, fBatch]);
  useEffect(() => {
    if (fReactor && !reactorOptions.includes(fReactor)) setFReactor("");
  }, [reactorOptions, fReactor]);

  const hasFilter = !!(fProject || fYear || fBatch || fReactor);
  function clearFilters() {
    setFProject("");
    setFYear("");
    setFBatch("");
    setFReactor("");
  }

  // 生长曲线：按勾选的指标各画一条，不同单位自动分左右坐标轴
  const chartSeries: ChartSeries[] = useMemo(() => {
    const pts = growthQ.data?.points ?? [];
    if (!pts.length) return [];
    return CELL_METRICS.filter((m) => metrics.includes(m.code)).map((m) => ({
      code: m.code,
      name: m.name,
      unit: m.unit,
      points: pts
        .filter((p) => m.pick(p) != null)
        .map((p) => ({
          time_hours: p.culture_day, // 复用 SeriesChart：横轴此处是培养天
          ts: "",
          value: m.pick(p) as number,
        })),
    }));
  }, [growthQ.data, metrics]);

  return (
    <div className="flex min-h-0 flex-1">
      {/* 左侧：级联筛选 + 批次列表 */}
      <aside className="flex w-72 flex-col border-r border-slate-200 bg-white">
        <div className="space-y-2 border-b border-slate-200 px-4 py-3">
          <label className="block">
            <span className="mb-1 block text-xs font-medium text-slate-500">
              项目编号
            </span>
            <select
              value={fProject}
              onChange={(e) => setFProject(e.target.value)}
              className="w-full rounded-md border border-slate-300 bg-white px-2 py-1.5 text-sm text-slate-800 focus:border-blue-500 focus:outline-none"
            >
              <option value="">全部项目</option>
              {projectOptions.map((p) => (
                <option key={p} value={p}>
                  {projLabel(p)}
                </option>
              ))}
            </select>
          </label>
          <label className="block">
            <span className="mb-1 block text-xs font-medium text-slate-500">
              批次年份
            </span>
            <select
              value={fYear}
              onChange={(e) => setFYear(e.target.value)}
              className="w-full rounded-md border border-slate-300 bg-white px-2 py-1.5 text-sm text-slate-800 focus:border-blue-500 focus:outline-none"
            >
              <option value="">全部年份</option>
              {yearOptions.map((y) => (
                <option key={y} value={String(y)}>
                  {y}
                </option>
              ))}
            </select>
          </label>
          <label className="block">
            <span className="mb-1 block text-xs font-medium text-slate-500">
              批号
            </span>
            <select
              value={fBatch}
              onChange={(e) => setFBatch(e.target.value)}
              className="w-full rounded-md border border-slate-300 bg-white px-2 py-1.5 text-sm text-slate-800 focus:border-blue-500 focus:outline-none"
            >
              <option value="">全部批号</option>
              {batchOptions.map((bn) => (
                <option key={bn} value={bn}>
                  {bn}
                </option>
              ))}
            </select>
          </label>
          <label className="block">
            <span className="mb-1 block text-xs font-medium text-slate-500">
              罐号
            </span>
            <select
              value={fReactor}
              onChange={(e) => setFReactor(e.target.value)}
              className="w-full rounded-md border border-slate-300 bg-white px-2 py-1.5 text-sm text-slate-800 focus:border-blue-500 focus:outline-none"
            >
              <option value="">全部罐号</option>
              {reactorOptions.map((r) => (
                <option key={r} value={r}>
                  {r}
                </option>
              ))}
            </select>
          </label>
        </div>
        <div className="flex items-center justify-between border-b border-slate-100 px-4 py-2 text-xs font-medium text-slate-400">
          <span className="uppercase tracking-wide">
            批次 {batchesQ.data ? `(${filteredBatches.length})` : ""}
          </span>
          {hasFilter && (
            <button
              onClick={clearFilters}
              className="rounded border border-slate-200 px-1.5 py-0.5 text-slate-500 hover:bg-slate-50"
            >
              清除筛选
            </button>
          )}
        </div>
        <div className="min-h-0 flex-1 overflow-y-auto">
          {batchesQ.isLoading && (
            <div className="p-4 text-sm text-slate-400">加载批次中…</div>
          )}
          {batchesQ.isError && (
            <div className="p-4 text-sm text-red-500">
              连不上后端，或未配置 cmc_analytics 连接。
            </div>
          )}
          {batchesQ.data && filteredBatches.length === 0 && (
            <div className="p-4 text-sm text-slate-400">没有符合筛选的批次。</div>
          )}
          {filteredBatches.map((b) => {
            const active = selected?.batch_key === b.batch_key;
            return (
              <button
                key={b.batch_key}
                onClick={() => setSelected(b)}
                className={`block w-full border-b border-slate-100 px-4 py-2.5 text-left transition ${
                  active ? "bg-blue-50" : "hover:bg-slate-50"
                }`}
              >
                <div className="flex items-center gap-2">
                  <span
                    className={`truncate text-sm font-medium ${
                      active ? "text-blue-700" : "text-slate-800"
                    }`}
                  >
                    {b.batch_key}
                  </span>
                </div>
                <div className="mt-0.5 flex items-center gap-2 text-xs text-slate-400">
                  {b.bioreactor_id && (
                    <span className="rounded bg-slate-100 px-1.5 py-0.5 text-slate-600">
                      罐 {b.bioreactor_id}
                    </span>
                  )}
                  <span>{b.n_samples} 样本</span>
                  <span className="ml-auto">
                    {b.day_min}–{b.day_max} 天
                  </span>
                </div>
              </button>
            );
          })}
        </div>
      </aside>

      {/* 右侧：生长曲线 */}
      <main className="flex min-w-0 flex-1 flex-col bg-slate-50">
        {!selected ? (
          <div className="flex flex-1 items-center justify-center text-slate-400">
            ← 先从左边选一个批次
          </div>
        ) : (
          <>
            <div className="border-b border-slate-200 bg-white px-5 py-3">
              <div className="mb-2 flex items-baseline gap-2">
                <span className="font-medium">{selected.batch_key}</span>
                <span className="text-xs text-slate-400">
                  细胞生长曲线 · 横轴培养天 · 选指标（不同单位自动分坐标轴）
                </span>
              </div>
              <div className="flex flex-wrap gap-1.5">
                {CELL_METRICS.map((m) => {
                  const on = metrics.includes(m.code);
                  return (
                    <button
                      key={m.code}
                      onClick={() => toggleMetric(m.code)}
                      title={m.name}
                      className={`rounded-full border px-2.5 py-1 text-xs transition ${
                        on
                          ? "border-blue-500 bg-blue-500 text-white"
                          : "border-slate-200 bg-white text-slate-600 hover:border-slate-300"
                      }`}
                    >
                      {m.name}
                      <span className={on ? "opacity-80" : "text-slate-400"}>
                        {" "}
                        {m.unit}
                      </span>
                    </button>
                  );
                })}
              </div>
            </div>
            <div className="min-h-0 flex-1 px-4 pb-4 pt-2">
              <div className="h-full rounded-lg border border-slate-200 bg-white p-3">
                <SeriesChart
                  series={chartSeries}
                  loading={growthQ.isFetching}
                  xName="培养天 (day)"
                />
              </div>
            </div>
          </>
        )}
      </main>
    </div>
  );
}
