"use client";

import { useEffect, useMemo, useState } from "react";
import { useQuery, useQueries, keepPreviousData } from "@tanstack/react-query";
import {
  fetchBatches,
  fetchChannels,
  fetchSeries,
  fetchGrowthByProcid,
  workstationLabel,
  type Batch,
  type Channel,
  type GrowthPoint,
} from "@/lib/api";
import {
  SeriesChart,
  type ChartSeries,
  type ViewWindow,
} from "@/components/SeriesChart";
import { CellGrowthView } from "@/components/CellGrowthView";

type ViewMode = "process" | "cell";

const DEFAULT_CHANNELS = ["m_temp", "m_ph", "m_do"];

// 工艺图里可叠加的细胞指标（虚拟通道，数据来自 Vi-CELL 按 procid 关联）
// 横轴用培养小时 = culture_day × 24，好和工艺时序对齐叠画
const CELL_OVERLAYS: {
  code: string;
  name: string;
  unit: string;
  pick: (p: GrowthPoint) => number | null;
}[] = [
  { code: "total_per_ml", name: "总细胞密度", unit: "×10⁶/ml", pick: (p) => p.total_per_ml },
  { code: "viable_per_ml", name: "活细胞密度", unit: "×10⁶/ml", pick: (p) => p.viable_per_ml },
  { code: "viability_pct", name: "活率", unit: "%", pick: (p) => p.viability_pct },
];

// 项目编号解析不出的批次归入这个桶
const PROJ_NONE = "__none__";
const projValue = (b: Batch) => b.project_code ?? PROJ_NONE;
const projLabel = (v: string) => (v === PROJ_NONE ? "未识别" : v);

function fmtDate(s: string | null): string {
  if (!s) return "—";
  return s.slice(0, 10);
}

function pad2(n: number): string {
  return n < 10 ? `0${n}` : String(n);
}

// 按 UTC 格式化为「YYYY-MM-DD HH:mm」（与批次时间的 UTC 存储/显示一致）
function fmtDateTime(d: Date): string {
  return (
    `${d.getUTCFullYear()}-${pad2(d.getUTCMonth() + 1)}-${pad2(d.getUTCDate())} ` +
    `${pad2(d.getUTCHours())}:${pad2(d.getUTCMinutes())}`
  );
}

// 批次数据起止时间 = 开始时刻 + fullRange（培养小时）的 min/max。缺数据返回 null。
function dataRangeLabel(
  start: string | null,
  range: ViewWindow | null
): string | null {
  if (!start || !range) return null;
  const base = new Date(start);
  if (isNaN(base.getTime())) return null;
  const from = new Date(base.getTime() + range.min * 3600_000);
  const to = new Date(base.getTime() + range.max * 3600_000);
  return `数据 ${fmtDateTime(from)} → ${fmtDateTime(to)}`;
}

function batchKey(b: Batch) {
  return `${b.source_instance}#${b.procid}`;
}

// 项目编号排序：按数字大小升序，"未识别" 垫底
function sortProject(a: string, b: string): number {
  if (a === PROJ_NONE) return 1;
  if (b === PROJ_NONE) return -1;
  const na = parseInt(a, 10);
  const nb = parseInt(b, 10);
  if (!isNaN(na) && !isNaN(nb) && na !== nb) return na - nb;
  return a.localeCompare(b);
}

// 罐号自然排序：先按字母（A/B/R/C），再按数字（A2 在 A10 前）
function sortReactor(a: string, b: string): number {
  const ma = /^([A-Za-z]+)(\d+)$/.exec(a);
  const mb = /^([A-Za-z]+)(\d+)$/.exec(b);
  if (ma && mb) {
    if (ma[1] !== mb[1]) return ma[1].localeCompare(mb[1]);
    return parseInt(ma[2], 10) - parseInt(mb[2], 10);
  }
  return a.localeCompare(b);
}

export default function Home() {
  // 顶部视图切换：工艺曲线（Lucullus）/ 细胞生长曲线（Vi-CELL）
  const [view, setView] = useState<ViewMode>("process");
  const [selected, setSelected] = useState<Batch | null>(null);
  const [channels, setChannels] = useState<string[]>([]);
  // 叠加到工艺图上的细胞指标（虚拟通道 code，见 CELL_OVERLAYS）
  const [cellMetrics, setCellMetrics] = useState<string[]>([]);
  // 当前可见时间窗口（放大后按此窗口向后端要更精细的数据）；null = 全览
  const [viewWindow, setViewWindow] = useState<ViewWindow | null>(null);

  // 三个级联筛选：项目编号 / 批次年份 / 罐号（"" = 全部）
  const [fProject, setFProject] = useState<string>("");
  const [fYear, setFYear] = useState<string>("");
  const [fReactor, setFReactor] = useState<string>("");

  const batchesQ = useQuery({ queryKey: ["batches"], queryFn: fetchBatches });

  const channelsQ = useQuery({
    queryKey: ["channels", selected?.source_instance, selected?.procid],
    queryFn: () => fetchChannels(selected!.source_instance, selected!.procid),
    enabled: !!selected,
  });

  // 选中批次关联的细胞生长曲线（按 source_instance + procid 关联），供叠图用
  const cellGrowthQ = useQuery({
    queryKey: ["process-cell-growth", selected?.source_instance, selected?.procid],
    queryFn: () =>
      fetchGrowthByProcid(selected!.source_instance, selected!.procid),
    enabled: !!selected && cellMetrics.length > 0,
  });

  // 选新批次后，自动勾选默认通道（存在的话）
  useEffect(() => {
    if (!channelsQ.data) return;
    const codes = new Set(channelsQ.data.map((c) => c.channel_code));
    setChannels((prev) => {
      const stillValid = prev.filter((c) => codes.has(c));
      if (stillValid.length) return stillValid;
      const defaults = DEFAULT_CHANNELS.filter((c) => codes.has(c));
      return defaults.length
        ? defaults
        : channelsQ.data!.slice(0, 1).map((c) => c.channel_code);
    });
  }, [channelsQ.data]);

  // 该批次通道的完整时间范围（小时），把缩放百分比换算成时间窗口时要用
  const fullRange = useMemo<ViewWindow | null>(() => {
    const data = channelsQ.data;
    if (!data?.length) return null;
    let min = Infinity;
    let max = -Infinity;
    for (const c of data) {
      if (c.t_min_h != null && c.t_min_h < min) min = c.t_min_h;
      if (c.t_max_h != null && c.t_max_h > max) max = c.t_max_h;
    }
    if (!Number.isFinite(min) || !Number.isFinite(max) || min === max) return null;
    return { min, max };
  }, [channelsQ.data]);

  // 窗口 key：变了就按新窗口重新取数（放大→取该段更精细的点）
  const winKey = viewWindow
    ? `${viewWindow.min.toFixed(3)}_${viewWindow.max.toFixed(3)}`
    : "full";

  const seriesQs = useQueries({
    queries: channels.map((ch) => ({
      queryKey: ["series", selected?.source_instance, selected?.procid, ch, winKey],
      queryFn: () =>
        fetchSeries(
          selected!.source_instance,
          selected!.procid,
          ch,
          2000,
          viewWindow?.min,
          viewWindow?.max
        ),
      enabled: !!selected,
      // 取新窗口数据时先保留旧数据，避免图闪空
      placeholderData: keepPreviousData,
    })),
  });

  const chMeta = useMemo(() => {
    const m = new Map<string, Channel>();
    channelsQ.data?.forEach((c) => m.set(c.channel_code, c));
    return m;
  }, [channelsQ.data]);

  const chartSeries: ChartSeries[] = useMemo(() => {
    const out: ChartSeries[] = [];
    channels.forEach((ch, i) => {
      const data = seriesQs[i]?.data;
      if (!data) return;
      const meta = chMeta.get(ch);
      out.push({
        code: ch,
        name: meta?.channel_name || ch,
        unit: meta?.unitsymbol ?? null,
        points: data.points,
      });
    });
    // 追加勾选的细胞指标：培养天 ×24 → 培养小时，叠到工艺时序上
    const cellPts = cellGrowthQ.data?.points ?? [];
    CELL_OVERLAYS.forEach((m) => {
      if (!cellMetrics.includes(m.code)) return;
      out.push({
        code: m.code,
        name: m.name,
        unit: m.unit,
        points: cellPts
          .filter((p) => m.pick(p) != null)
          .map((p) => ({
            time_hours: p.culture_day * 24,
            ts: "",
            value: m.pick(p) as number,
          })),
      });
    });
    return out;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [
    channels,
    seriesQs.map((q) => q.dataUpdatedAt).join(","),
    chMeta,
    cellMetrics,
    cellGrowthQ.dataUpdatedAt,
  ]);

  const chartLoading =
    seriesQs.some((q) => q.isFetching) || cellGrowthQ.isFetching;

  // 原始采集点数 / 抽稀后显示点数（让用户知道图上不是全量点）
  const counts = useMemo(() => {
    let raw = 0;
    let shown = 0;
    for (const q of seriesQs) {
      if (q.data) {
        raw += q.data.raw_count;
        shown += q.data.returned;
      }
    }
    return { raw, shown };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [seriesQs.map((q) => q.dataUpdatedAt).join(",")]);

  // ---- 级联筛选：项目编号 → 批次年份 → 罐号 ----
  const allBatches = batchesQ.data ?? [];

  // 项目下拉：全部批次里的不同项目编号
  const projectOptions = useMemo(() => {
    const s = new Set<string>();
    allBatches.forEach((b) => s.add(projValue(b)));
    return [...s].sort(sortProject);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [batchesQ.data]);

  // 年份下拉：只显示当前项目下有的年份
  const yearOptions = useMemo(() => {
    const s = new Set<number>();
    allBatches.forEach((b) => {
      if (fProject && projValue(b) !== fProject) return;
      if (b.batch_year != null) s.add(b.batch_year);
    });
    return [...s].sort((a, b) => b - a);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [batchesQ.data, fProject]);

  // 罐号下拉：只显示当前项目+年份下有的罐号
  const reactorOptions = useMemo(() => {
    const s = new Set<string>();
    allBatches.forEach((b) => {
      if (fProject && projValue(b) !== fProject) return;
      if (fYear && String(b.batch_year) !== fYear) return;
      if (b.reactor) s.add(b.reactor);
    });
    return [...s].sort(sortReactor);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [batchesQ.data, fProject, fYear]);

  // 三个筛选都应用后，剩下的批次
  const filteredBatches = useMemo(() => {
    return allBatches.filter((b) => {
      if (fProject && projValue(b) !== fProject) return false;
      if (fYear && String(b.batch_year) !== fYear) return false;
      if (fReactor && b.reactor !== fReactor) return false;
      return true;
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [batchesQ.data, fProject, fYear, fReactor]);

  // 上层筛选变了 → 下层若已失效则自动清空（保证级联一致）
  useEffect(() => {
    if (fYear && !yearOptions.map(String).includes(fYear)) setFYear("");
  }, [yearOptions, fYear]);
  useEffect(() => {
    if (fReactor && !reactorOptions.includes(fReactor)) setFReactor("");
  }, [reactorOptions, fReactor]);

  const hasFilter = !!(fProject || fYear || fReactor);
  function clearFilters() {
    setFProject("");
    setFYear("");
    setFReactor("");
  }

  function pickBatch(b: Batch) {
    setSelected(b);
    setChannels([]);
    setCellMetrics([]);
    setViewWindow(null);
  }

  function toggleChannel(code: string) {
    setChannels((prev) =>
      prev.includes(code) ? prev.filter((c) => c !== code) : [...prev, code]
    );
  }

  function toggleCellMetric(code: string) {
    setCellMetrics((prev) =>
      prev.includes(code) ? prev.filter((c) => c !== code) : [...prev, code]
    );
  }

  return (
    <div className="flex h-screen flex-col">
      {/* 顶栏 */}
      <header className="flex items-center gap-3 border-b border-slate-200 bg-white px-5 py-3">
        <h1 className="text-lg font-semibold">USP 上游分析看板</h1>
        {/* 视图切换：工艺曲线 / 细胞生长曲线 */}
        <div className="flex rounded-md border border-slate-200 p-0.5">
          {(
            [
              ["process", "工艺曲线"],
              ["cell", "细胞生长曲线"],
            ] as [ViewMode, string][]
          ).map(([v, label]) => (
            <button
              key={v}
              onClick={() => setView(v)}
              className={`rounded px-3 py-1 text-sm transition ${
                view === v
                  ? "bg-blue-500 text-white"
                  : "text-slate-600 hover:bg-slate-50"
              }`}
            >
              {label}
            </button>
          ))}
        </div>
        <span className="text-sm text-slate-400">
          {view === "process"
            ? "Lucullus 生物反应器 · 工艺时序曲线"
            : "Vi-CELL 细胞计数 · 生长曲线"}
        </span>
        <span className="ml-auto rounded bg-amber-50 px-2 py-0.5 text-xs text-amber-700">
          本地测试环境 · 样本批次
        </span>
      </header>

      {view === "cell" && <CellGrowthView />}

      <div className={`${view === "process" ? "flex" : "hidden"} min-h-0 flex-1`}>
        {/* 左侧：批次列表 */}
        <aside className="flex w-72 flex-col border-r border-slate-200 bg-white">
          {/* 级联筛选：项目编号 → 批次年份 → 罐号 */}
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
                连不上后端。确认后端在 http://localhost:8070 运行。
              </div>
            )}
            {batchesQ.data && filteredBatches.length === 0 && (
              <div className="p-4 text-sm text-slate-400">
                没有符合筛选的批次。
              </div>
            )}
            {filteredBatches.map((b) => {
              const active = selected && batchKey(selected) === batchKey(b);
              return (
                <button
                  key={batchKey(b)}
                  onClick={() => pickBatch(b)}
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
                      {b.procname || `批次 ${b.procid}`}
                    </span>
                  </div>
                  <div className="mt-0.5 flex items-center gap-2 text-xs text-slate-400">
                    <span className="rounded bg-slate-100 px-1.5 py-0.5 text-slate-600">
                      {workstationLabel(b.source_instance)}
                    </span>
                    {b.reactor_name && <span>反应器 {b.reactor_name}</span>}
                    <span className="ml-auto">{fmtDate(b.starttime)}</span>
                  </div>
                </button>
              );
            })}
          </div>
        </aside>

        {/* 右侧：通道选择 + 图表 */}
        <main className="flex min-w-0 flex-1 flex-col bg-slate-50">
          {!selected ? (
            <div className="flex flex-1 items-center justify-center text-slate-400">
              ← 先从左边选一个批次
            </div>
          ) : (
            <>
              <div className="border-b border-slate-200 bg-white px-5 py-3">
                <div className="mb-2 flex items-baseline gap-2">
                  <span className="font-medium">
                    {selected.procname || `批次 ${selected.procid}`}
                  </span>
                  <span className="text-xs text-slate-400">
                    {dataRangeLabel(selected.starttime, fullRange) ?? "数据 —"}
                  </span>
                </div>
                <div className="flex flex-wrap gap-1.5">
                  {channelsQ.isLoading && (
                    <span className="text-sm text-slate-400">加载通道中…</span>
                  )}
                  {channelsQ.data
                    ?.slice()
                    .sort((a, b) => a.channel_code.localeCompare(b.channel_code))
                    .map((c) => {
                      const on = channels.includes(c.channel_code);
                      return (
                        <button
                          key={c.channel_code}
                          onClick={() => toggleChannel(c.channel_code)}
                          title={`${c.channel_name ?? ""} · ${c.n_points} 点`}
                          className={`rounded-full border px-2.5 py-1 text-xs transition ${
                            on
                              ? "border-blue-500 bg-blue-500 text-white"
                              : "border-slate-200 bg-white text-slate-600 hover:border-slate-300"
                          }`}
                        >
                          {c.channel_code}
                          {c.unitsymbol ? (
                            <span
                              className={on ? "opacity-80" : "text-slate-400"}
                            >
                              {" "}
                              {c.unitsymbol}
                            </span>
                          ) : null}
                        </button>
                      );
                    })}
                  {/* 细胞指标虚拟通道：叠到工艺趋势图上一起看 */}
                  {!channelsQ.isLoading && (
                    <span className="mx-1 self-center text-xs text-slate-300">
                      细胞
                    </span>
                  )}
                  {CELL_OVERLAYS.map((m) => {
                    const on = cellMetrics.includes(m.code);
                    return (
                      <button
                        key={m.code}
                        onClick={() => toggleCellMetric(m.code)}
                        title={`Vi-CELL 细胞指标 · ${m.name}`}
                        className={`rounded-full border border-dashed px-2.5 py-1 text-xs transition ${
                          on
                            ? "border-emerald-500 bg-emerald-500 text-white"
                            : "border-emerald-300 bg-white text-emerald-700 hover:border-emerald-400"
                        }`}
                      >
                        {m.name}
                        <span className={on ? "opacity-80" : "text-emerald-400"}>
                          {" "}
                          {m.unit}
                        </span>
                      </button>
                    );
                  })}
                </div>
                {cellMetrics.length > 0 &&
                  cellGrowthQ.isSuccess &&
                  (cellGrowthQ.data?.points.length ?? 0) === 0 && (
                    <div className="mt-1.5 text-xs text-amber-600">
                      该批次暂无关联的细胞数据（生产环境有关联时自动叠加显示）
                    </div>
                  )}
              </div>

              <div className="flex items-center gap-3 px-5 pt-2 text-xs text-slate-400">
                {counts.raw > 0 && (
                  <span>
                    原始 {counts.raw.toLocaleString()} 点 · 显示{" "}
                    {counts.shown.toLocaleString()} 点（按可见范围抽稀）
                  </span>
                )}
                {viewWindow ? (
                  <button
                    onClick={() => setViewWindow(null)}
                    className="rounded border border-slate-200 px-2 py-0.5 text-slate-600 hover:bg-slate-50"
                  >
                    ↺ 全览
                  </button>
                ) : (
                  <span className="text-slate-300">滚轮 / 拖底部滑块放大，自动加载更精细数据</span>
                )}
              </div>
              <div className="min-h-0 flex-1 px-4 pb-4 pt-2">
                <div className="h-full rounded-lg border border-slate-200 bg-white p-3">
                  <SeriesChart
                    series={chartSeries}
                    loading={chartLoading}
                    fullRange={fullRange}
                    viewWindow={viewWindow}
                    onWindowChange={setViewWindow}
                  />
                </div>
              </div>
            </>
          )}
        </main>
      </div>
    </div>
  );
}
