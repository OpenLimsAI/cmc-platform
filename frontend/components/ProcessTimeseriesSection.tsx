"use client";

// 板块：工艺时序（全量）——Lucullus 按小时的原始采样曲线，支持多批次叠加。
// 一个批次可能对应多段工艺记录（中途重开），每段各画一条；横轴培养小时，
// 放大时按可见窗口向后端要更精细的点（后端抽稀，每条线恒 ≤2000 点）。
import { useEffect, useMemo, useState } from "react";
import { useQueries, keepPreviousData } from "@tanstack/react-query";
import {
  fetchChannels,
  fetchGrowth,
  fetchSeries,
  workstationLabel,
  type Channel,
  type GrowthPoint,
  type LucullusRun,
  type OverviewBatch,
} from "@/lib/api";
import { SeriesChart, type ChartSeries, type ViewWindow } from "@/components/SeriesChart";
import { batchLabel, toggleIn } from "@/lib/batches";

// 首次打开默认勾选的通道（温度 / pH / 溶氧）
const DEFAULT_CHANNELS = ["m_temp", "m_ph", "m_do"];

// 可叠到工艺时序上的细胞指标（横轴培养天 ×24 → 培养小时）
const CELL_OVERLAYS: { code: string; name: string; unit: string; pick: (p: GrowthPoint) => number | null }[] = [
  { code: "viable_per_ml", name: "活细胞密度", unit: "×10⁶/ml", pick: (p) => p.viable_per_ml },
  { code: "total_per_ml", name: "总细胞密度", unit: "×10⁶/ml", pick: (p) => p.total_per_ml },
  { code: "viability_pct", name: "活率", unit: "%", pick: (p) => p.viability_pct },
];

// 一段要画的工艺记录
interface Run {
  key: string; // 工作站#procid
  batch: OverviewBatch;
  run: LucullusRun;
  label: string; // 图例前缀：批次身份（多段时再带原始批次名）
}

// 通道选项：同一物理量（canonical_key 相同）跨工作站 / 别名归并成一个选项
interface ChanOption {
  key: string; // canonical_key，没有则 channel_code
  display_name: string;
  category: string;
  unit: string | null;
  sort_order: number;
  codeByRun: Map<string, Channel>; // 每段记录里对应的实际通道
}

const pad2 = (n: number) => (n < 10 ? `0${n}` : String(n));
function fmtUtc(d: Date): string {
  return `${d.getUTCFullYear()}-${pad2(d.getUTCMonth() + 1)}-${pad2(d.getUTCDate())} ${pad2(d.getUTCHours())}:${pad2(d.getUTCMinutes())}`;
}

export function ProcessTimeseriesSection({ batches }: { batches: OverviewBatch[] }) {
  const [chosen, setChosen] = useState<string[]>([]);
  const [cellMetrics, setCellMetrics] = useState<string[]>([]);
  const [viewWindow, setViewWindow] = useState<ViewWindow | null>(null);

  // 展开成"段"：一个批次几段工艺记录就几条曲线
  const runs = useMemo<Run[]>(() => {
    const out: Run[] = [];
    batches.forEach((b) => {
      const multi = b.lucullus_runs.length > 1;
      b.lucullus_runs.forEach((r) => {
        out.push({
          key: `${r.source_instance}#${r.procid}`,
          batch: b,
          run: r,
          // 同一批次多段记录：图例后缀带开始日期（如 ·08-12）区分，比整个原始批次名短
          label:
            multi && !b.unparsed
              ? `${batchLabel(b)}·${r.starttime ? r.starttime.slice(5, 10) : r.procid}`
              : batchLabel(b),
        });
      });
    });
    return out;
  }, [batches]);
  const runsKey = runs.map((r) => r.key).join(",");

  // 换了批次集合 → 缩放窗口回全览
  useEffect(() => {
    setViewWindow(null);
  }, [runsKey]);

  const channelsQs = useQueries({
    queries: runs.map((r) => ({
      queryKey: ["channels", r.run.source_instance, r.run.procid],
      queryFn: () => fetchChannels(r.run.source_instance, r.run.procid),
      staleTime: 10 * 60_000,
    })),
  });
  const channelsLoaded = channelsQs.map((q) => q.dataUpdatedAt).join(",");

  // 通道选项：每段先按原规则挑可见通道（去别名 / 去字典标记冗余），再跨段按 canonical_key 归并
  const options = useMemo<ChanOption[]>(() => {
    const map = new Map<string, ChanOption>();
    runs.forEach((r, i) => {
      const all = channelsQs[i]?.data ?? [];
      const preferredKeys = new Set(
        all.filter((c) => c.is_preferred && c.canonical_key).map((c) => c.canonical_key!)
      );
      all
        .filter(
          (c) =>
            c.is_active !== false &&
            (c.is_preferred || !c.canonical_key || !preferredKeys.has(c.canonical_key))
        )
        .forEach((c) => {
          const key = c.canonical_key ?? c.channel_code;
          let o = map.get(key);
          if (!o) {
            o = {
              key,
              display_name: c.display_name || c.channel_code,
              category: c.category ?? "其它",
              unit: c.unitsymbol,
              sort_order: c.sort_order,
              codeByRun: new Map(),
            };
            map.set(key, o);
          }
          if (!o.codeByRun.has(r.key)) o.codeByRun.set(r.key, c);
          if (c.sort_order < o.sort_order) o.sort_order = c.sort_order;
        });
    });
    return [...map.values()].sort((a, b) => a.sort_order - b.sort_order || a.key.localeCompare(b.key));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [runsKey, channelsLoaded]);

  // 选项变化：已勾的失效项去掉；一个都没勾时补默认通道
  useEffect(() => {
    if (!options.length) return;
    const keys = new Set(options.map((o) => o.key));
    setChosen((prev) => {
      const still = prev.filter((k) => keys.has(k));
      if (still.length) return still;
      const defaults = options
        .filter((o) => [...o.codeByRun.values()].some((c) => DEFAULT_CHANNELS.includes(c.channel_code)))
        .map((o) => o.key);
      return defaults.length ? defaults : options.slice(0, 1).map((o) => o.key);
    });
  }, [options]);

  const groups = useMemo(() => {
    const out: { category: string; items: ChanOption[] }[] = [];
    const idx = new Map<string, number>();
    options.forEach((o) => {
      let i = idx.get(o.category);
      if (i === undefined) {
        i = out.length;
        idx.set(o.category, i);
        out.push({ category: o.category, items: [] });
      }
      out[i].items.push(o);
    });
    return out;
  }, [options]);

  // 全部段的完整时间范围（小时）：缩放百分比 ↔ 时间窗口换算用
  const fullRange = useMemo<ViewWindow | null>(() => {
    let min = Infinity;
    let max = -Infinity;
    channelsQs.forEach((q) => {
      q.data?.forEach((c) => {
        if (c.t_min_h != null && c.t_min_h < min) min = c.t_min_h;
        if (c.t_max_h != null && c.t_max_h > max) max = c.t_max_h;
      });
    });
    if (!Number.isFinite(min) || !Number.isFinite(max) || min === max) return null;
    return { min, max };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [channelsLoaded]);

  const winKey = viewWindow ? `${viewWindow.min.toFixed(3)}_${viewWindow.max.toFixed(3)}` : "full";

  // 要取的曲线 = 每段 × 每个勾选通道（该段有这个通道才取）
  const tasks = useMemo(
    () =>
      runs.flatMap((r) =>
        chosen.flatMap((k) => {
          const o = options.find((x) => x.key === k);
          const c = o?.codeByRun.get(r.key);
          return o && c ? [{ run: r, opt: o, ch: c }] : [];
        })
      ),
    [runs, chosen, options]
  );
  const seriesQs = useQueries({
    queries: tasks.map((t) => ({
      queryKey: ["series", t.run.run.source_instance, t.run.run.procid, t.ch.channel_code, winKey],
      queryFn: () =>
        fetchSeries(t.run.run.source_instance, t.run.run.procid, t.ch.channel_code, 2000, viewWindow?.min, viewWindow?.max),
      placeholderData: keepPreviousData,
    })),
  });

  // 细胞叠加：按批次身份取生长曲线（不规范名批次没有细胞数据）
  const cellBatches = cellMetrics.length ? batches.filter((b) => b.n_vicell > 0) : [];
  const growthQs = useQueries({
    queries: cellBatches.map((b) => ({
      queryKey: ["vicell-growth", b.batch_key],
      queryFn: () => fetchGrowth(b.batch_key),
      placeholderData: keepPreviousData,
    })),
  });

  const multi = runs.length > 1;
  const chartSeries = useMemo<ChartSeries[]>(() => {
    const out: ChartSeries[] = [];
    tasks.forEach((t, i) => {
      const data = seriesQs[i]?.data;
      if (!data) return;
      out.push({
        code: `${t.run.key}:${t.ch.channel_code}`,
        name: multi ? `${t.run.label} ${t.opt.display_name}` : t.opt.display_name,
        unit: t.ch.unitsymbol,
        points: data.points,
      });
    });
    cellBatches.forEach((b, i) => {
      const pts = growthQs[i]?.data?.points ?? [];
      CELL_OVERLAYS.filter((m) => cellMetrics.includes(m.code)).forEach((m) => {
        out.push({
          code: `${b.batch_key}:${m.code}`,
          name: batches.length > 1 ? `${batchLabel(b)} ${m.name}` : m.name,
          unit: m.unit,
          points: pts
            .filter((p) => m.pick(p) != null)
            .map((p) => ({ time_hours: p.culture_day * 24, ts: "", value: m.pick(p) as number })),
        });
      });
    });
    return out;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [tasks, seriesQs.map((q) => q.dataUpdatedAt).join(","), cellMetrics, growthQs.map((q) => q.dataUpdatedAt).join(",")]);

  const counts = useMemo(() => {
    let raw = 0;
    let shown = 0;
    seriesQs.forEach((q) => {
      if (q.data) {
        raw += q.data.raw_count;
        shown += q.data.returned;
      }
    });
    return { raw, shown };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [seriesQs.map((q) => q.dataUpdatedAt).join(",")]);

  const loading = channelsQs.some((q) => q.isLoading) || seriesQs.some((q) => q.isFetching) || growthQs.some((q) => q.isFetching);
  const single = runs.length === 1 ? runs[0] : null;

  return (
    <section className="rounded-lg border border-slate-200 bg-white">
      <div className="border-b border-slate-100 px-5 py-2.5">
        <div className="flex flex-wrap items-baseline gap-2">
          <h2 className="text-sm font-semibold">工艺时序（全量）</h2>
          <span className="text-xs text-slate-400">
            Lucullus · 按小时原始采样 · {runs.length} 段工艺记录
            {single && single.run.starttime
              ? ` · ${workstationLabel(single.run.source_instance)} · 开始 ${fmtUtc(new Date(single.run.starttime))}`
              : ""}
          </span>
        </div>
        {runs.length === 0 ? (
          <div className="mt-1.5 text-xs text-slate-400">所选批次都没有 Lucullus 工艺数据</div>
        ) : (
          <div className="mt-1.5 flex flex-col gap-1.5">
            {channelsQs.some((q) => q.isLoading) && (
              <span className="text-xs text-slate-400">加载通道中…</span>
            )}
            {groups.map((g) => (
              <div key={g.category} className="flex flex-wrap items-center gap-1.5">
                <span className="w-14 text-xs text-slate-300">{g.category}</span>
                {g.items.map((o) => {
                  const on = chosen.includes(o.key);
                  const n = o.codeByRun.size;
                  const codes = [...new Set([...o.codeByRun.values()].map((c) => c.channel_code))].join(" / ");
                  return (
                    <button
                      key={o.key}
                      onClick={() => setChosen((prev) => toggleIn(prev, o.key))}
                      title={`${codes}${multi ? ` · ${n}/${runs.length} 段有此通道` : ""}`}
                      className={`rounded-full border px-2.5 py-0.5 text-xs transition ${
                        on
                          ? "border-blue-500 bg-blue-500 text-white"
                          : "border-slate-200 bg-white text-slate-600 hover:border-slate-300"
                      }`}
                    >
                      {o.display_name}
                      {o.unit && <span className={on ? "opacity-80" : "text-slate-400"}> {o.unit}</span>}
                      {multi && n < runs.length && (
                        <span className={on ? "opacity-70" : "text-amber-500"}> {n}/{runs.length}</span>
                      )}
                    </button>
                  );
                })}
              </div>
            ))}
            {/* 细胞指标叠加（虚线绿色 chip） */}
            <div className="flex flex-wrap items-center gap-1.5">
              <span className="w-14 text-xs text-slate-300">细胞叠加</span>
              {CELL_OVERLAYS.map((m) => {
                const on = cellMetrics.includes(m.code);
                return (
                  <button
                    key={m.code}
                    onClick={() => setCellMetrics((prev) => toggleIn(prev, m.code))}
                    title="Vi-CELL 细胞指标，按培养天 ×24 叠到小时轴上"
                    className={`rounded-full border border-dashed px-2.5 py-0.5 text-xs transition ${
                      on
                        ? "border-emerald-500 bg-emerald-500 text-white"
                        : "border-emerald-300 bg-white text-emerald-700 hover:border-emerald-400"
                    }`}
                  >
                    {m.name}
                    <span className={on ? "opacity-80" : "text-emerald-400"}> {m.unit}</span>
                  </button>
                );
              })}
              {cellMetrics.length > 0 && cellBatches.length === 0 && (
                <span className="text-xs text-amber-600">所选批次没有细胞数据可叠加</span>
              )}
            </div>
          </div>
        )}
      </div>
      {runs.length > 0 && (
        <>
          <div className="flex items-center gap-3 px-5 pt-2 text-xs text-slate-400">
            {counts.raw > 0 && (
              <span>
                原始 {counts.raw.toLocaleString()} 点 · 显示 {counts.shown.toLocaleString()} 点（按可见范围抽稀）
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
          <div className="h-[30rem] p-3">
            <SeriesChart
              series={chartSeries}
              loading={loading}
              fullRange={fullRange}
              viewWindow={viewWindow}
              onWindowChange={setViewWindow}
              xTickInterval={24}
              hoursAxis
              startTime={single?.run.starttime ?? null}
            />
          </div>
        </>
      )}
    </section>
  );
}
