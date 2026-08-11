"use client";

import { useEffect, useMemo, useState } from "react";
import { useQuery, keepPreviousData } from "@tanstack/react-query";
import {
  fetchOverviewBatches,
  fetchGrowth,
  fetchNovaSeries,
  fetchVicellSamples,
  fetchNovaSamples,
  fetchProcessDaily,
  type OverviewBatch,
  type GrowthPoint,
  type ProcessDailyPoint,
} from "@/lib/api";
import { SeriesChart, type ChartSeries } from "@/components/SeriesChart";
import { NOVA_METRICS, NOVA_DEFAULT_METRICS } from "@/components/NovaView";

// 总览页细胞曲线固定画：活细胞密度 + 活率（要更多指标去「细胞生长曲线」视图）
const CELL_METRICS: {
  code: string;
  name: string;
  unit: string;
  pick: (p: GrowthPoint) => number | null;
}[] = [
  { code: "viable_per_ml", name: "活细胞密度", unit: "×10⁶/ml", pick: (p) => p.viable_per_ml },
  { code: "viability_pct", name: "活率", unit: "%", pick: (p) => p.viability_pct },
];

// 工艺按天汇总的可选指标（chip 勾选）。日均值；加碱/加酸是当天累计末值。
const PROCESS_METRICS: {
  code: string;
  name: string;
  unit: string;
  pick: (p: ProcessDailyPoint) => number | null;
}[] = [
  { code: "temp_c_mean", name: "温度", unit: "°C", pick: (p) => p.temp_c_mean },
  { code: "ph_mean", name: "pH", unit: "", pick: (p) => p.ph_mean },
  { code: "do_pct_mean", name: "溶氧", unit: "%", pick: (p) => p.do_pct_mean },
  { code: "do_pct_min", name: "溶氧最低", unit: "%", pick: (p) => p.do_pct_min },
  { code: "stirrer_rpm_mean", name: "搅拌", unit: "rpm", pick: (p) => p.stirrer_rpm_mean },
  { code: "o2_mlmin_mean", name: "O₂流量", unit: "ml/min", pick: (p) => p.o2_mlmin_mean },
  { code: "air_mlmin_mean", name: "空气流量", unit: "ml/min", pick: (p) => p.air_mlmin_mean },
  { code: "co2_mlmin_mean", name: "CO₂流量", unit: "ml/min", pick: (p) => p.co2_mlmin_mean },
  { code: "alkali_cum_ml", name: "加碱累计", unit: "ml", pick: (p) => p.alkali_cum_ml },
  { code: "acid_cum_ml", name: "加酸累计", unit: "ml", pick: (p) => p.acid_cum_ml },
];

// 工艺区默认勾选：温度 / pH / 溶氧
const PROCESS_DEFAULT_METRICS = ["temp_c_mean", "ph_mean", "do_pct_mean"];

// 项目编号解析不出的批次归入这个桶
const PROJ_NONE = "__none__";
const projValue = (b: OverviewBatch) => b.project_id ?? PROJ_NONE;
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

const fmtNum = (v: number | null, digits = 2) =>
  v == null ? "—" : v.toFixed(digits);
const fmtDate = (s: string | null) => (s ? s.slice(0, 10) : "—");

export function OverviewView({
  onOpenProcess,
}: {
  // 跳转「工艺曲线」视图并选中对应工艺批次（Lucullus 工作站 + procid）
  onOpenProcess?: (sourceInstance: string, procid: number) => void;
}) {
  const [selected, setSelected] = useState<OverviewBatch | null>(null);
  // 生化区勾选的指标（默认与生化视图一致）
  const [novaMetrics, setNovaMetrics] = useState<string[]>(NOVA_DEFAULT_METRICS);

  function toggleNovaMetric(code: string) {
    setNovaMetrics((prev) =>
      prev.includes(code) ? prev.filter((c) => c !== code) : [...prev, code]
    );
  }

  // 工艺区勾选的指标
  const [procMetrics, setProcMetrics] = useState<string[]>(PROCESS_DEFAULT_METRICS);

  function toggleProcMetric(code: string) {
    setProcMetrics((prev) =>
      prev.includes(code) ? prev.filter((c) => c !== code) : [...prev, code]
    );
  }

  // 四个级联筛选：项目编号 / 批次年份 / 批号 / 罐号（"" = 全部）
  const [fProject, setFProject] = useState<string>("");
  const [fYear, setFYear] = useState<string>("");
  const [fBatch, setFBatch] = useState<string>("");
  const [fReactor, setFReactor] = useState<string>("");

  const batchesQ = useQuery({
    queryKey: ["overview-batches"],
    queryFn: fetchOverviewBatches,
  });

  const bk = selected?.batch_key;
  const hasVicell = (selected?.n_vicell ?? 0) > 0;
  const hasNova = (selected?.n_nova ?? 0) > 0;

  const growthQ = useQuery({
    queryKey: ["vicell-growth", bk],
    queryFn: () => fetchGrowth(bk!),
    enabled: !!bk && hasVicell,
    placeholderData: keepPreviousData,
  });
  const novaQ = useQuery({
    queryKey: ["nova-series", bk],
    queryFn: () => fetchNovaSeries(bk!),
    enabled: !!bk && hasNova,
    placeholderData: keepPreviousData,
  });
  const vSamplesQ = useQuery({
    queryKey: ["vicell-samples", bk],
    queryFn: () => fetchVicellSamples(bk!),
    enabled: !!bk && hasVicell,
    placeholderData: keepPreviousData,
  });
  const nSamplesQ = useQuery({
    queryKey: ["nova-samples", bk],
    queryFn: () => fetchNovaSamples(bk!),
    enabled: !!bk && hasNova,
    placeholderData: keepPreviousData,
  });
  // 工艺按天汇总（有 Lucullus 关联才取；procid 撞号，必须带工作站消歧）
  const hasProcessLink =
    selected?.lucullus_procid != null && !!selected?.lucullus_source_instance;
  const processQ = useQuery({
    queryKey: [
      "overview-process-daily",
      selected?.lucullus_source_instance,
      selected?.lucullus_procid,
    ],
    queryFn: () =>
      fetchProcessDaily(
        selected!.lucullus_source_instance!,
        selected!.lucullus_procid!
      ),
    enabled: hasProcessLink,
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

  // 细胞生长曲线（密度 + 活率）
  const cellSeries: ChartSeries[] = useMemo(() => {
    const pts = growthQ.data?.points ?? [];
    if (!pts.length) return [];
    return CELL_METRICS.map((m) => ({
      code: m.code,
      name: m.name,
      unit: m.unit,
      points: pts
        .filter((p) => m.pick(p) != null)
        .map((p) => ({
          time_hours: p.culture_day,
          ts: "",
          value: m.pick(p) as number,
        })),
    }));
  }, [growthQ.data]);

  // 工艺按天趋势（勾选指标）
  const processSeries: ChartSeries[] = useMemo(() => {
    const pts = processQ.data?.points ?? [];
    if (!pts.length) return [];
    return PROCESS_METRICS.filter((m) => procMetrics.includes(m.code)).map(
      (m) => ({
        code: m.code,
        name: m.name,
        unit: m.unit || null,
        points: pts
          .filter((p) => m.pick(p) != null)
          .map((p) => ({
            time_hours: p.culture_day,
            ts: "",
            value: m.pick(p) as number,
          })),
      })
    );
  }, [processQ.data, procMetrics]);

  // 生化趋势（勾选指标）
  const novaSeries: ChartSeries[] = useMemo(() => {
    const pts = novaQ.data?.points ?? [];
    if (!pts.length) return [];
    return NOVA_METRICS.filter((m) => novaMetrics.includes(m.code)).map((m) => ({
      code: m.code,
      name: m.name,
      unit: m.unit || null,
      points: pts
        .filter((p) => m.pick(p) != null)
        .map((p) => ({
          time_hours: p.culture_day,
          ts: "",
          value: m.pick(p) as number,
        })),
    }));
  }, [novaQ.data, novaMetrics]);

  return (
    <div className="flex min-h-0 flex-1">
      {/* 左侧：级联筛选 + 合并批次列表（细胞∪生化） */}
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

      {/* 右侧：一页纵排 细胞 → 生化 → 工艺 → 明细 */}
      <main className="min-w-0 flex-1 overflow-y-auto bg-slate-50">
        {!selected ? (
          <div className="flex h-full items-center justify-center text-slate-400">
            ← 先从左边选一个批次，一页看全该批的细胞、生化、工艺数据
          </div>
        ) : (
          <div className="mx-auto max-w-5xl space-y-4 px-5 py-4">
            {/* 批次头信息 */}
            <div className="rounded-lg border border-slate-200 bg-white px-5 py-3">
              <div className="flex flex-wrap items-baseline gap-x-4 gap-y-1">
                <span className="text-lg font-semibold">{selected.batch_key}</span>
                <span className="text-sm text-slate-500">
                  项目 {selected.project_id ?? "—"} · 批号{" "}
                  {selected.batch_number ?? "—"} · 罐{" "}
                  {selected.bioreactor_id ?? "—"}
                </span>
                <span className="text-sm text-slate-400">
                  培养 {selected.day_min}–{selected.day_max} 天 · 始于{" "}
                  {fmtDate(selected.first_at)}
                </span>
                {growthQ.data?.generation != null && (
                  <span className="rounded bg-slate-100 px-2 py-0.5 text-xs text-slate-600">
                    代次 {growthQ.data.generation}
                  </span>
                )}
                {growthQ.data?.seeded_from_stages && (
                  <span className="rounded bg-slate-100 px-2 py-0.5 text-xs text-slate-600">
                    分自 {growthQ.data.seeded_from_stages}
                  </span>
                )}
              </div>
            </div>

            {/* 1. 细胞生长曲线 */}
            <section className="rounded-lg border border-slate-200 bg-white">
              <div className="flex items-baseline gap-2 border-b border-slate-100 px-5 py-2.5">
                <h2 className="text-sm font-semibold">细胞生长曲线</h2>
                <span className="text-xs text-slate-400">
                  Vi-CELL · 活细胞密度 + 活率
                </span>
              </div>
              <div className="h-72 p-3">
                {hasVicell ? (
                  <SeriesChart
                    series={cellSeries}
                    loading={growthQ.isFetching}
                    xName="培养天 (day)"
                  />
                ) : (
                  <div className="flex h-full items-center justify-center text-sm text-slate-400">
                    该批次没有细胞计数数据
                  </div>
                )}
              </div>
            </section>

            {/* 2. 生化趋势 */}
            <section className="rounded-lg border border-slate-200 bg-white">
              <div className="border-b border-slate-100 px-5 py-2.5">
                <div className="flex items-baseline gap-2">
                  <h2 className="text-sm font-semibold">生化趋势</h2>
                  <span className="text-xs text-slate-400">
                    Nova FLEX2 · 勾选指标
                  </span>
                </div>
                {hasNova && (
                  <div className="mt-1.5 flex flex-wrap gap-1.5">
                    {NOVA_METRICS.map((m) => {
                      const on = novaMetrics.includes(m.code);
                      return (
                        <button
                          key={m.code}
                          onClick={() => toggleNovaMetric(m.code)}
                          className={`rounded-full border px-2 py-0.5 text-xs transition ${
                            on
                              ? "border-blue-500 bg-blue-500 text-white"
                              : "border-slate-200 bg-white text-slate-600 hover:border-slate-300"
                          }`}
                        >
                          {m.name}
                        </button>
                      );
                    })}
                  </div>
                )}
              </div>
              <div className="h-72 p-3">
                {hasNova ? (
                  <SeriesChart
                    series={novaSeries}
                    loading={novaQ.isFetching}
                    xName="培养天 (day)"
                  />
                ) : (
                  <div className="flex h-full items-center justify-center text-sm text-slate-400">
                    该批次没有生化分析数据
                  </div>
                )}
              </div>
            </section>

            {/* 3. 工艺参数（按天汇总；跳转看全量时序） */}
            <section className="rounded-lg border border-slate-200 bg-white">
              <div className="border-b border-slate-100 px-5 py-2.5">
                <div className="flex items-baseline gap-2">
                  <h2 className="text-sm font-semibold">工艺参数</h2>
                  <span className="text-xs text-slate-400">
                    Lucullus · 按培养天汇总（日均值；加碱/加酸为当天累计）
                  </span>
                  {hasProcessLink && (
                    <button
                      onClick={() =>
                        onOpenProcess?.(
                          selected.lucullus_source_instance!,
                          selected.lucullus_procid!
                        )
                      }
                      className="ml-auto shrink-0 rounded-md border border-blue-500 px-2.5 py-1 text-xs text-blue-600 transition hover:bg-blue-50"
                    >
                      看全量时序曲线 →
                    </button>
                  )}
                </div>
                {hasProcessLink && (
                  <div className="mt-1.5 flex flex-wrap gap-1.5">
                    {PROCESS_METRICS.map((m) => {
                      const on = procMetrics.includes(m.code);
                      return (
                        <button
                          key={m.code}
                          onClick={() => toggleProcMetric(m.code)}
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
                )}
              </div>
              {hasProcessLink ? (
                <div className="h-72 p-3">
                  {processQ.isSuccess &&
                  (processQ.data?.points.length ?? 0) === 0 ? (
                    <div className="flex h-full items-center justify-center text-sm text-slate-400">
                      该工艺批次还没有按天汇总数据（ETL 每日物化，稍后再看）
                    </div>
                  ) : (
                    <SeriesChart
                      series={processSeries}
                      loading={processQ.isFetching}
                      xName="培养天 (day)"
                    />
                  )}
                </div>
              ) : (
                <div className="px-5 py-4 text-sm text-slate-400">
                  该批次未关联到 Lucullus 工艺批次（多数历史批次如此，属数据本身限制）。
                </div>
              )}
            </section>

            {/* 4. 取样记录明细 */}
            <section className="rounded-lg border border-slate-200 bg-white">
              <div className="flex items-baseline gap-2 border-b border-slate-100 px-5 py-2.5">
                <h2 className="text-sm font-semibold">取样记录明细</h2>
                <span className="text-xs text-slate-400">
                  每次取样一行（未按天平均）
                </span>
              </div>
              <div className="space-y-4 p-4">
                {hasVicell && (
                  <div>
                    <div className="mb-1.5 text-xs font-medium text-emerald-700">
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
                          {(vSamplesQ.data ?? []).map((s) => (
                            <tr
                              key={s.run_id}
                              className="border-b border-slate-100 text-slate-700"
                            >
                              <td className="px-2 py-1 text-left">
                                {s.sample_id ?? "—"}
                              </td>
                              <td className="px-2 py-1">{s.culture_day ?? "—"}</td>
                              <td className="px-2 py-1">{fmtDate(s.run_date)}</td>
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
                {hasNova && (
                  <div>
                    <div className="mb-1.5 text-xs font-medium text-sky-700">
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
                          {(nSamplesQ.data ?? []).map((s) => (
                            <tr
                              key={s.sample_result_id}
                              className="border-b border-slate-100 text-slate-700"
                            >
                              <td className="px-2 py-1 text-left">
                                {s.sample_id ?? "—"}
                              </td>
                              <td className="px-2 py-1">{s.culture_day ?? "—"}</td>
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
                              <td className="px-2 py-1">{fmtNum(s.ph, 3)}</td>
                              <td className="px-2 py-1">{fmtNum(s.po2, 1)}</td>
                              <td className="px-2 py-1">{fmtNum(s.pco2, 1)}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  </div>
                )}
                {!hasVicell && !hasNova && (
                  <div className="py-6 text-center text-sm text-slate-400">
                    该批次没有取样记录
                  </div>
                )}
              </div>
            </section>
          </div>
        )}
      </main>
    </div>
  );
}
