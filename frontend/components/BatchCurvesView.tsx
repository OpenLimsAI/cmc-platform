"use client";

import { useEffect, useMemo, useState } from "react";
import { useQuery, useQueries, keepPreviousData } from "@tanstack/react-query";
import {
  fetchOverviewBatches,
  fetchGrowth,
  fetchNovaSeries,
  fetchProcessDaily,
  fetchVicellSamples,
  fetchNovaSamples,
  fetchDailyTable,
  type OverviewBatch,
} from "@/lib/api";
import { SeriesChart, type ChartSeries } from "@/components/SeriesChart";
import { DailyTable } from "@/components/DailyTable";
import {
  CELL_METRICS,
  CELL_DEFAULT_METRICS,
  NOVA_METRICS,
  NOVA_DEFAULT_METRICS,
  PROCESS_METRICS,
  PROCESS_DEFAULT_METRICS,
  type MetricDef,
} from "@/lib/metrics";

// 右侧可同开的曲线板块（多选，切换不影响左侧批号筛选）
type Section = "cell" | "nova" | "process" | "table" | "samples";
const SECTIONS: { code: Section; label: string }[] = [
  { code: "cell", label: "生长曲线" },
  { code: "nova", label: "生化曲线" },
  { code: "process", label: "工艺参数" },
  { code: "table", label: "数据表" },
  { code: "samples", label: "取样明细" },
];
const DEFAULT_SECTIONS: Section[] = ["cell", "nova", "process"];

// 项目编号解析不出的批次归入这个桶
const PROJ_NONE = "__none__";
const projValue = (b: OverviewBatch) => b.project_id ?? PROJ_NONE;
const projLabel = (v: string) => (v === PROJ_NONE ? "未识别" : v);

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

const fmtNum = (v: number | null, digits = 2) =>
  v == null ? "—" : v.toFixed(digits);
const fmtDate = (s: string | null) => (s ? s.slice(0, 10) : "—");

export function BatchCurvesView({
  onOpenProcess,
}: {
  // 跳到「工艺曲线（全量时序）」页签并选中对应工艺批次
  onOpenProcess?: (sourceInstance: string, procid: number) => void;
}) {
  // ---- 第一层：全局筛选（项目 → 年份 → 批号多选 → 罐号多选）----
  const [fProject, setFProject] = useState<string>("");
  const [fYear, setFYear] = useState<string>("");
  const [selBatchNums, setSelBatchNums] = useState<string[]>([]);
  const [selReactors, setSelReactors] = useState<string[]>([]); // 空 = 全部罐
  // 从匹配结果里手动排除的个别 batch_key（点列表项切换）
  const [excluded, setExcluded] = useState<string[]>([]);

  // ---- 第二层：曲线板块开关 + 各板块指标（与批号筛选完全独立）----
  const [sections, setSections] = useState<Section[]>(DEFAULT_SECTIONS);
  const [cellMetrics, setCellMetrics] = useState<string[]>(CELL_DEFAULT_METRICS);
  const [novaMetrics, setNovaMetrics] = useState<string[]>(NOVA_DEFAULT_METRICS);
  const [procMetrics, setProcMetrics] = useState<string[]>(PROCESS_DEFAULT_METRICS);

  function toggleIn<T>(arr: T[], v: T): T[] {
    return arr.includes(v) ? arr.filter((x) => x !== v) : [...arr, v];
  }

  const batchesQ = useQuery({
    queryKey: ["overview-batches"],
    queryFn: fetchOverviewBatches,
  });
  const allBatches = batchesQ.data ?? [];

  // 级联选项
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

  // 批号选项（当前项目+年份范围内）
  const batchNumOptions = useMemo(() => {
    const s = new Set<string>();
    allBatches.forEach((b) => {
      if (fProject && projValue(b) !== fProject) return;
      if (fYear && String(b.batch_year) !== fYear) return;
      if (b.batch_number) s.add(b.batch_number);
    });
    return [...s].sort();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [batchesQ.data, fProject, fYear]);

  // 罐号选项（已选批号范围内）
  const reactorOptions = useMemo(() => {
    const s = new Set<string>();
    allBatches.forEach((b) => {
      if (fProject && projValue(b) !== fProject) return;
      if (fYear && String(b.batch_year) !== fYear) return;
      if (selBatchNums.length && !selBatchNums.includes(b.batch_number ?? "")) return;
      if (b.bioreactor_id) s.add(b.bioreactor_id);
    });
    return [...s].sort(sortReactor);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [batchesQ.data, fProject, fYear, selBatchNums]);

  // 匹配的批次（= 要画曲线的对象；再减去手动排除的）
  const matched = useMemo(() => {
    if (!selBatchNums.length) return [];
    return allBatches.filter((b) => {
      if (fProject && projValue(b) !== fProject) return false;
      if (fYear && String(b.batch_year) !== fYear) return false;
      if (!selBatchNums.includes(b.batch_number ?? "")) return false;
      if (selReactors.length && !selReactors.includes(b.bioreactor_id ?? ""))
        return false;
      return true;
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [batchesQ.data, fProject, fYear, selBatchNums, selReactors]);

  const selected = useMemo(
    () => matched.filter((b) => !excluded.includes(b.batch_key)),
    [matched, excluded]
  );

  // 上层筛选变了 → 失效的下层选择自动剔除（级联一致）
  useEffect(() => {
    setSelBatchNums((prev) => prev.filter((n) => batchNumOptions.includes(n)));
  }, [batchNumOptions]);
  useEffect(() => {
    setSelReactors((prev) => prev.filter((r) => reactorOptions.includes(r)));
  }, [reactorOptions]);
  useEffect(() => {
    const keys = new Set(matched.map((b) => b.batch_key));
    setExcluded((prev) => prev.filter((k) => keys.has(k)));
  }, [matched]);

  // ---- 数据：每个选中批次各取三源曲线 ----
  const cellBatches = selected.filter((b) => b.n_vicell > 0);
  const novaBatches = selected.filter((b) => b.n_nova > 0);
  const procBatches = selected.filter(
    (b) => b.lucullus_procid != null && b.lucullus_source_instance
  );

  const growthQs = useQueries({
    queries: cellBatches.map((b) => ({
      queryKey: ["vicell-growth", b.batch_key],
      queryFn: () => fetchGrowth(b.batch_key),
      enabled: sections.includes("cell"),
      placeholderData: keepPreviousData,
    })),
  });
  const novaQs = useQueries({
    queries: novaBatches.map((b) => ({
      queryKey: ["nova-series", b.batch_key],
      queryFn: () => fetchNovaSeries(b.batch_key),
      enabled: sections.includes("nova"),
      placeholderData: keepPreviousData,
    })),
  });
  const procQs = useQueries({
    queries: procBatches.map((b) => ({
      queryKey: [
        "overview-process-daily",
        b.lucullus_source_instance,
        b.lucullus_procid,
      ],
      queryFn: () =>
        fetchProcessDaily(b.lucullus_source_instance!, b.lucullus_procid!),
      enabled: sections.includes("process"),
      placeholderData: keepPreviousData,
    })),
  });
  const vSamplesQs = useQueries({
    queries: cellBatches.map((b) => ({
      queryKey: ["vicell-samples", b.batch_key],
      queryFn: () => fetchVicellSamples(b.batch_key),
      enabled: sections.includes("samples"),
      placeholderData: keepPreviousData,
    })),
  });
  const nSamplesQs = useQueries({
    queries: novaBatches.map((b) => ({
      queryKey: ["nova-samples", b.batch_key],
      queryFn: () => fetchNovaSamples(b.batch_key),
      enabled: sections.includes("samples"),
      placeholderData: keepPreviousData,
    })),
  });
  // 数据表板块：所有选中批次一次请求，后端按 (批次, 培养天) 合并三源
  const selectedKeys = useMemo(
    () => selected.map((b) => b.batch_key).sort(),
    [selected]
  );
  const tableQ = useQuery({
    queryKey: ["daily-table", selectedKeys.join(",")],
    queryFn: () => fetchDailyTable(selectedKeys),
    enabled: sections.includes("table") && selectedKeys.length > 0,
    placeholderData: keepPreviousData,
  });

  // 组曲线：每个批次 × 每个勾选指标一条；多批次时名字带批号前缀
  const multi = selected.length > 1;
  function buildSeries<P>(
    keys: string[],
    datas: ({ points: P[] } | undefined)[],
    defs: MetricDef<P>[],
    chosen: string[],
    dayOf: (p: P) => number
  ): ChartSeries[] {
    const out: ChartSeries[] = [];
    keys.forEach((key, i) => {
      const pts = datas[i]?.points ?? [];
      if (!pts.length) return;
      defs
        .filter((m) => chosen.includes(m.code))
        .forEach((m) => {
          out.push({
            code: `${key}:${m.code}`,
            name: multi ? `${key} ${m.name}` : m.name,
            unit: m.unit || null,
            points: pts
              .filter((p) => m.pick(p) != null)
              .map((p) => ({
                time_hours: dayOf(p), // 复用 SeriesChart：横轴此处是培养天
                ts: "",
                value: m.pick(p) as number,
              })),
          });
        });
    });
    return out;
  }

  const cellSeries = useMemo(
    () =>
      buildSeries(
        cellBatches.map((b) => b.batch_key),
        growthQs.map((q) => q.data),
        CELL_METRICS,
        cellMetrics,
        (p) => p.culture_day
      ),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [selected, growthQs.map((q) => q.dataUpdatedAt).join(","), cellMetrics, multi]
  );
  const novaSeries = useMemo(
    () =>
      buildSeries(
        novaBatches.map((b) => b.batch_key),
        novaQs.map((q) => q.data),
        NOVA_METRICS,
        novaMetrics,
        (p) => p.culture_day
      ),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [selected, novaQs.map((q) => q.dataUpdatedAt).join(","), novaMetrics, multi]
  );
  const procSeries = useMemo(
    () =>
      buildSeries(
        procBatches.map((b) => b.batch_key),
        procQs.map((q) => q.data),
        PROCESS_METRICS,
        procMetrics,
        (p) => p.culture_day
      ),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [selected, procQs.map((q) => q.dataUpdatedAt).join(","), procMetrics, multi]
  );

  const showSection = (s: Section) => sections.includes(s);

  // 指标 chip 行（三个板块公用样式）
  function MetricChips<P>({
    defs,
    chosen,
    onToggle,
  }: {
    defs: MetricDef<P>[];
    chosen: string[];
    onToggle: (code: string) => void;
  }) {
    return (
      <div className="mt-1.5 flex flex-wrap gap-1.5">
        {defs.map((m) => {
          const on = chosen.includes(m.code);
          return (
            <button
              key={m.code}
              onClick={() => onToggle(m.code)}
              className={`rounded-full border px-2 py-0.5 text-xs transition ${
                on
                  ? "border-blue-500 bg-blue-500 text-white"
                  : "border-slate-200 bg-white text-slate-600 hover:border-slate-300"
              }`}
            >
              {m.name}
              {m.unit && (
                <span className={on ? "opacity-80" : "text-slate-400"}>
                  {" "}
                  {m.unit}
                </span>
              )}
            </button>
          );
        })}
      </div>
    );
  }

  return (
    <div className="flex min-h-0 flex-1">
      {/* 左侧：第一层全局筛选（批号多选 → 罐号），选出的批次全局共用 */}
      <aside className="flex w-80 flex-col border-r border-slate-200 bg-white">
        <div className="space-y-2 border-b border-slate-200 px-4 py-3">
          <div className="grid grid-cols-2 gap-2">
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
          </div>

          {/* 批号多选：不同批次可叠加对比 */}
          <div>
            <div className="mb-1 flex items-center justify-between">
              <span className="text-xs font-medium text-slate-500">
                批号（可多选，叠加对比）
              </span>
              <span className="flex gap-1">
                <button
                  onClick={() => setSelBatchNums(batchNumOptions)}
                  className="rounded border border-slate-200 px-1.5 py-0.5 text-xs text-slate-500 hover:bg-slate-50"
                >
                  全选
                </button>
                <button
                  onClick={() => setSelBatchNums([])}
                  className="rounded border border-slate-200 px-1.5 py-0.5 text-xs text-slate-500 hover:bg-slate-50"
                >
                  清空
                </button>
              </span>
            </div>
            <div className="max-h-40 overflow-y-auto rounded-md border border-slate-200">
              {batchNumOptions.length === 0 && (
                <div className="p-2 text-xs text-slate-400">
                  当前项目/年份下没有批号
                </div>
              )}
              {batchNumOptions.map((bn) => {
                const on = selBatchNums.includes(bn);
                return (
                  <label
                    key={bn}
                    className={`flex cursor-pointer items-center gap-2 border-b border-slate-100 px-2.5 py-1.5 text-sm last:border-b-0 ${
                      on ? "bg-blue-50 text-blue-700" : "text-slate-700 hover:bg-slate-50"
                    }`}
                  >
                    <input
                      type="checkbox"
                      checked={on}
                      onChange={() => setSelBatchNums((prev) => toggleIn(prev, bn))}
                      className="accent-blue-500"
                    />
                    {bn}
                  </label>
                );
              })}
            </div>
          </div>

          {/* 罐号：默认全部，点选收窄 */}
          <div>
            <div className="mb-1 flex items-center justify-between">
              <span className="text-xs font-medium text-slate-500">
                罐号（默认全部，点选收窄）
              </span>
              {selReactors.length > 0 && (
                <button
                  onClick={() => setSelReactors([])}
                  className="rounded border border-slate-200 px-1.5 py-0.5 text-xs text-slate-500 hover:bg-slate-50"
                >
                  全部罐
                </button>
              )}
            </div>
            <div className="flex flex-wrap gap-1">
              {reactorOptions.map((r) => {
                const on = selReactors.includes(r);
                return (
                  <button
                    key={r}
                    onClick={() => setSelReactors((prev) => toggleIn(prev, r))}
                    className={`rounded border px-1.5 py-0.5 text-xs transition ${
                      on
                        ? "border-blue-500 bg-blue-500 text-white"
                        : "border-slate-200 bg-white text-slate-600 hover:border-slate-300"
                    }`}
                  >
                    {r}
                  </button>
                );
              })}
              {reactorOptions.length === 0 && (
                <span className="text-xs text-slate-400">先选批号</span>
              )}
            </div>
          </div>
        </div>

        {/* 命中的批次（罐粒度曲线单位）；点某一项可临时排除 */}
        <div className="flex items-center justify-between border-b border-slate-100 px-4 py-2 text-xs font-medium text-slate-400">
          <span className="uppercase tracking-wide">
            将画曲线的批次 ({selected.length}
            {excluded.length > 0 ? ` / 命中 ${matched.length}` : ""})
          </span>
          {excluded.length > 0 && (
            <button
              onClick={() => setExcluded([])}
              className="rounded border border-slate-200 px-1.5 py-0.5 text-slate-500 hover:bg-slate-50"
            >
              恢复排除
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
          {batchesQ.data && selBatchNums.length === 0 && (
            <div className="p-4 text-sm text-slate-400">
              ↑ 先勾选批号（可多选）。选一个批号 = 看它所有罐；选多个 = 跨批次对比。
            </div>
          )}
          {matched.map((b) => {
            const off = excluded.includes(b.batch_key);
            return (
              <button
                key={b.batch_key}
                onClick={() => setExcluded((prev) => toggleIn(prev, b.batch_key))}
                title={off ? "已排除，点击恢复" : "点击临时排除这条曲线"}
                className={`block w-full border-b border-slate-100 px-4 py-2 text-left transition ${
                  off ? "opacity-40" : "hover:bg-slate-50"
                }`}
              >
                <div className="flex items-center gap-2">
                  <span
                    className={`truncate text-sm font-medium ${
                      off ? "line-through" : ""
                    } text-slate-800`}
                  >
                    {b.batch_key}
                  </span>
                </div>
                <div className="mt-0.5 flex items-center gap-1.5 text-xs text-slate-400">
                  {b.n_vicell > 0 && (
                    <span className="rounded bg-emerald-50 px-1.5 py-0.5 text-emerald-700">
                      细胞 {b.n_vicell}
                    </span>
                  )}
                  {b.n_nova > 0 && (
                    <span className="rounded bg-sky-50 px-1.5 py-0.5 text-sky-700">
                      生化 {b.n_nova}
                    </span>
                  )}
                  {b.lucullus_procid != null && (
                    <span className="rounded bg-violet-50 px-1.5 py-0.5 text-violet-700">
                      工艺✓
                    </span>
                  )}
                  <span className="ml-auto">
                    {b.day_min}–{b.day_max} 天
                  </span>
                </div>
              </button>
            );
          })}
        </div>
      </aside>

      {/* 右侧：曲线板块（可同开多块；开关/指标勾选不影响左侧批号） */}
      <main className="min-w-0 flex-1 overflow-y-auto bg-slate-50">
        {/* 板块开关 */}
        <div className="sticky top-0 z-10 flex items-center gap-2 border-b border-slate-200 bg-white px-5 py-2.5">
          <span className="text-xs font-medium text-slate-500">显示板块：</span>
          {SECTIONS.map((s) => {
            const on = showSection(s.code);
            return (
              <button
                key={s.code}
                onClick={() => setSections((prev) => toggleIn(prev, s.code))}
                className={`rounded-md border px-2.5 py-1 text-xs transition ${
                  on
                    ? "border-blue-500 bg-blue-500 text-white"
                    : "border-slate-200 bg-white text-slate-600 hover:border-slate-300"
                }`}
              >
                {s.label}
              </button>
            );
          })}
          {selected.length > 0 && (
            <span className="ml-auto text-xs text-slate-400">
              已选 {selected.length} 条批次曲线 · 横轴统一培养天
            </span>
          )}
        </div>

        {selected.length === 0 ? (
          <div className="flex h-96 items-center justify-center text-slate-400">
            ← 左侧选好批号（可多选）后，这里按板块显示叠加曲线
          </div>
        ) : (
          <div className="mx-auto max-w-6xl space-y-4 px-5 py-4">
            {/* 生长曲线 */}
            {showSection("cell") && (
              <section className="rounded-lg border border-slate-200 bg-white">
                <div className="border-b border-slate-100 px-5 py-2.5">
                  <div className="flex items-baseline gap-2">
                    <h2 className="text-sm font-semibold">生长曲线</h2>
                    <span className="text-xs text-slate-400">
                      Vi-CELL · {cellBatches.length}/{selected.length} 批有数据
                    </span>
                  </div>
                  <MetricChips
                    defs={CELL_METRICS}
                    chosen={cellMetrics}
                    onToggle={(c) => setCellMetrics((prev) => toggleIn(prev, c))}
                  />
                </div>
                <div className="h-80 p-3">
                  {cellBatches.length ? (
                    <SeriesChart
                      series={cellSeries}
                      loading={growthQs.some((q) => q.isFetching)}
                      xName="培养天 (day)"
                    />
                  ) : (
                    <div className="flex h-full items-center justify-center text-sm text-slate-400">
                      所选批次都没有细胞计数数据
                    </div>
                  )}
                </div>
              </section>
            )}

            {/* 生化曲线 */}
            {showSection("nova") && (
              <section className="rounded-lg border border-slate-200 bg-white">
                <div className="border-b border-slate-100 px-5 py-2.5">
                  <div className="flex items-baseline gap-2">
                    <h2 className="text-sm font-semibold">生化曲线</h2>
                    <span className="text-xs text-slate-400">
                      Nova FLEX2 · {novaBatches.length}/{selected.length} 批有数据
                    </span>
                  </div>
                  <MetricChips
                    defs={NOVA_METRICS}
                    chosen={novaMetrics}
                    onToggle={(c) => setNovaMetrics((prev) => toggleIn(prev, c))}
                  />
                </div>
                <div className="h-80 p-3">
                  {novaBatches.length ? (
                    <SeriesChart
                      series={novaSeries}
                      loading={novaQs.some((q) => q.isFetching)}
                      xName="培养天 (day)"
                    />
                  ) : (
                    <div className="flex h-full items-center justify-center text-sm text-slate-400">
                      所选批次都没有生化分析数据
                    </div>
                  )}
                </div>
              </section>
            )}

            {/* 工艺参数（按天汇总） */}
            {showSection("process") && (
              <section className="rounded-lg border border-slate-200 bg-white">
                <div className="border-b border-slate-100 px-5 py-2.5">
                  <div className="flex flex-wrap items-baseline gap-2">
                    <h2 className="text-sm font-semibold">工艺参数</h2>
                    <span className="text-xs text-slate-400">
                      Lucullus · 按培养天汇总 · {procBatches.length}/
                      {selected.length} 批有关联
                    </span>
                    {/* 每个关联批次一个全量时序入口（小时级细节去那边看） */}
                    <span className="ml-auto flex flex-wrap gap-1">
                      {procBatches.map((b) => (
                        <button
                          key={b.batch_key}
                          onClick={() =>
                            onOpenProcess?.(
                              b.lucullus_source_instance!,
                              b.lucullus_procid!
                            )
                          }
                          className="rounded border border-blue-300 px-1.5 py-0.5 text-xs text-blue-600 transition hover:bg-blue-50"
                          title="跳到工艺曲线（全量时序）页签"
                        >
                          {b.batch_key} 全量→
                        </button>
                      ))}
                    </span>
                  </div>
                  <MetricChips
                    defs={PROCESS_METRICS}
                    chosen={procMetrics}
                    onToggle={(c) => setProcMetrics((prev) => toggleIn(prev, c))}
                  />
                </div>
                <div className="h-80 p-3">
                  {procBatches.length ? (
                    <SeriesChart
                      series={procSeries}
                      loading={procQs.some((q) => q.isFetching)}
                      xName="培养天 (day)"
                    />
                  ) : (
                    <div className="flex h-full items-center justify-center text-sm text-slate-400">
                      所选批次都未关联 Lucullus 工艺批次（多数历史批次如此）
                    </div>
                  )}
                </div>
              </section>
            )}

            {/* 数据表：《项目第一表》样式的按天合并宽表 */}
            {showSection("table") && (
              <section className="rounded-lg border border-slate-200 bg-white">
                <div className="flex items-baseline gap-2 border-b border-slate-100 px-5 py-2.5">
                  <h2 className="text-sm font-semibold">数据表</h2>
                  <span className="text-xs text-slate-400">
                    一行 = 一个批次一个培养天 · 工艺 / 细胞 / 生化 列并排（对齐《项目第一表》）
                  </span>
                </div>
                <DailyTable
                  rows={tableQ.data?.rows ?? []}
                  batches={selected}
                  loading={tableQ.isFetching}
                />
              </section>
            )}

            {/* 取样明细：每个批次一组表 */}
            {showSection("samples") && (
              <section className="rounded-lg border border-slate-200 bg-white">
                <div className="flex items-baseline gap-2 border-b border-slate-100 px-5 py-2.5">
                  <h2 className="text-sm font-semibold">取样记录明细</h2>
                  <span className="text-xs text-slate-400">
                    每次取样一行（未按天平均）
                  </span>
                </div>
                <div className="space-y-5 p-4">
                  {selected.map((b) => {
                    const vi = cellBatches.findIndex(
                      (x) => x.batch_key === b.batch_key
                    );
                    const ni = novaBatches.findIndex(
                      (x) => x.batch_key === b.batch_key
                    );
                    const vRows = vi >= 0 ? vSamplesQs[vi]?.data ?? [] : [];
                    const nRows = ni >= 0 ? nSamplesQs[ni]?.data ?? [] : [];
                    return (
                      <div key={b.batch_key}>
                        <div className="mb-1.5 text-sm font-semibold text-slate-700">
                          {b.batch_key}
                        </div>
                        {vRows.length > 0 && (
                          <div className="mb-3">
                            <div className="mb-1 text-xs font-medium text-emerald-700">
                              细胞计数（Vi-CELL）
                            </div>
                            <div className="overflow-x-auto">
                              <table className="w-full whitespace-nowrap text-right text-xs">
                                <thead>
                                  <tr className="border-b border-slate-200 text-slate-500">
                                    <th className="px-2 py-1.5 text-left">样本名</th>
                                    <th className="px-2 py-1.5">培养天</th>
                                    <th className="px-2 py-1.5">日期</th>
                                    <th className="px-2 py-1.5">活密度 ×10⁶/ml</th>
                                    <th className="px-2 py-1.5">活率 %</th>
                                    <th className="px-2 py-1.5">总密度 ×10⁶/ml</th>
                                    <th className="px-2 py-1.5">直径 µm</th>
                                    <th className="px-2 py-1.5">圆度</th>
                                  </tr>
                                </thead>
                                <tbody>
                                  {vRows.map((s) => (
                                    <tr
                                      key={s.run_id}
                                      className="border-b border-slate-100 text-slate-700"
                                    >
                                      <td className="px-2 py-1 text-left">
                                        {s.sample_id ?? "—"}
                                      </td>
                                      <td className="px-2 py-1">
                                        {s.culture_day ?? "—"}
                                      </td>
                                      <td className="px-2 py-1">
                                        {fmtDate(s.run_date)}
                                      </td>
                                      <td className="px-2 py-1">
                                        {fmtNum(s.viable_per_ml)}
                                      </td>
                                      <td className="px-2 py-1">
                                        {fmtNum(s.viability_pct, 1)}
                                      </td>
                                      <td className="px-2 py-1">
                                        {fmtNum(s.total_per_ml)}
                                      </td>
                                      <td className="px-2 py-1">
                                        {fmtNum(s.avg_diameter_um, 1)}
                                      </td>
                                      <td className="px-2 py-1">
                                        {fmtNum(s.avg_circularity)}
                                      </td>
                                    </tr>
                                  ))}
                                </tbody>
                              </table>
                            </div>
                          </div>
                        )}
                        {nRows.length > 0 && (
                          <div>
                            <div className="mb-1 text-xs font-medium text-sky-700">
                              生化分析（Nova FLEX2）
                            </div>
                            <div className="overflow-x-auto">
                              <table className="w-full whitespace-nowrap text-right text-xs">
                                <thead>
                                  <tr className="border-b border-slate-200 text-slate-500">
                                    <th className="px-2 py-1.5 text-left">样本名</th>
                                    <th className="px-2 py-1.5">培养天</th>
                                    <th className="px-2 py-1.5">日期</th>
                                    <th className="px-2 py-1.5">葡萄糖 g/L</th>
                                    <th className="px-2 py-1.5">乳酸 g/L</th>
                                    <th className="px-2 py-1.5">氨 mmol/L</th>
                                    <th className="px-2 py-1.5">谷氨酰胺</th>
                                    <th className="px-2 py-1.5">谷氨酸</th>
                                    <th className="px-2 py-1.5">钠</th>
                                    <th className="px-2 py-1.5">钾</th>
                                    <th className="px-2 py-1.5">钙</th>
                                    <th className="px-2 py-1.5">pH</th>
                                    <th className="px-2 py-1.5">pO₂</th>
                                    <th className="px-2 py-1.5">pCO₂</th>
                                  </tr>
                                </thead>
                                <tbody>
                                  {nRows.map((s) => (
                                    <tr
                                      key={s.sample_result_id}
                                      className="border-b border-slate-100 text-slate-700"
                                    >
                                      <td className="px-2 py-1 text-left">
                                        {s.sample_id ?? "—"}
                                      </td>
                                      <td className="px-2 py-1">
                                        {s.culture_day ?? "—"}
                                      </td>
                                      <td className="px-2 py-1">
                                        {fmtDate(s.measured_at)}
                                      </td>
                                      <td className="px-2 py-1">{fmtNum(s.gluc)}</td>
                                      <td className="px-2 py-1">{fmtNum(s.lac)}</td>
                                      <td className="px-2 py-1">{fmtNum(s.nh4)}</td>
                                      <td className="px-2 py-1">{fmtNum(s.gln)}</td>
                                      <td className="px-2 py-1">{fmtNum(s.glu)}</td>
                                      <td className="px-2 py-1">{fmtNum(s.na, 1)}</td>
                                      <td className="px-2 py-1">{fmtNum(s.k)}</td>
                                      <td className="px-2 py-1">{fmtNum(s.ca)}</td>
                                      <td className="px-2 py-1">
                                        {fmtNum(s.ph, 3)}
                                      </td>
                                      <td className="px-2 py-1">
                                        {fmtNum(s.po2, 1)}
                                      </td>
                                      <td className="px-2 py-1">
                                        {fmtNum(s.pco2, 1)}
                                      </td>
                                    </tr>
                                  ))}
                                </tbody>
                              </table>
                            </div>
                          </div>
                        )}
                        {vRows.length === 0 && nRows.length === 0 && (
                          <div className="text-xs text-slate-400">无取样记录</div>
                        )}
                      </div>
                    );
                  })}
                </div>
              </section>
            )}
          </div>
        )}
      </main>
    </div>
  );
}
