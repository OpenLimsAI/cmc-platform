"use client";

// 通用曲线板块：生长曲线 / 生化曲线 / 工艺参数（日均）三个板块共用。
// 每个选中批次取一条按培养天的数据，× 勾选的指标 = 图上的线；横轴统一培养天。
import { useMemo, type ReactNode } from "react";
import { useQueries, keepPreviousData } from "@tanstack/react-query";
import type { OverviewBatch } from "@/lib/api";
import { SeriesChart, type ChartSeries } from "@/components/SeriesChart";
import type { MetricDef } from "@/lib/metrics";
import { batchLabel, toggleIn } from "@/lib/batches";

// 数据点可带 __gap=true 表示"这里是两段记录之间的空档"，画成断线而不是连一条斜线
export type GapMarker = { __gap?: boolean };

export function CurveSection<P extends { culture_day: number } & GapMarker>({
  title,
  source,
  batches,
  hasData,
  queryKey,
  fetch,
  defs,
  chosen,
  onChosen,
  emptyText,
  extra,
}: {
  title: string;
  source: string; // 副标题里的数据来源说明
  batches: OverviewBatch[]; // 当前选中的全部批次
  hasData: (b: OverviewBatch) => boolean; // 该批次在本源有没有数据
  queryKey: (b: OverviewBatch) => unknown[];
  fetch: (b: OverviewBatch) => Promise<{ points: P[] }>;
  defs: MetricDef<P>[];
  chosen: string[];
  onChosen: (v: string[]) => void;
  emptyText: string;
  extra?: ReactNode; // 标题行右侧的附加内容
}) {
  const withData = batches.filter(hasData);
  const qs = useQueries({
    queries: withData.map((b) => ({
      queryKey: queryKey(b),
      queryFn: () => fetch(b),
      placeholderData: keepPreviousData,
    })),
  });
  const multi = batches.length > 1;

  const series = useMemo<ChartSeries[]>(() => {
    const out: ChartSeries[] = [];
    withData.forEach((b, i) => {
      const pts = qs[i]?.data?.points ?? [];
      if (!pts.length) return;
      defs
        .filter((m) => chosen.includes(m.code))
        .forEach((m) => {
          out.push({
            code: `${b.batch_key}:${m.code}`,
            name: multi ? `${batchLabel(b)} ${m.name}` : m.name,
            unit: m.unit || null,
            points: pts
              .filter((p) => p.__gap || m.pick(p) != null)
              .map((p) => ({ time_hours: p.culture_day, value: p.__gap ? null : (m.pick(p) as number) })),
          });
        });
    });
    return out;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [withData, qs.map((q) => q.dataUpdatedAt).join(","), chosen, multi]);

  return (
    <section className="rounded-lg border border-slate-200 bg-white">
      <div className="border-b border-slate-100 px-5 py-2.5">
        <div className="flex flex-wrap items-baseline gap-2">
          <h2 className="text-sm font-semibold">{title}</h2>
          <span className="text-xs text-slate-400">
            {source} · {withData.length}/{batches.length} 批有数据
          </span>
          {extra}
        </div>
        <div className="mt-1.5 flex flex-wrap gap-1.5">
          {defs.map((m) => {
            const on = chosen.includes(m.code);
            return (
              <button
                key={m.code}
                onClick={() => onChosen(toggleIn(chosen, m.code))}
                className={`rounded-full border px-2 py-0.5 text-xs transition ${
                  on
                    ? "border-blue-500 bg-blue-500 text-white"
                    : "border-slate-200 bg-white text-slate-600 hover:border-slate-300"
                }`}
              >
                {m.name}
                {m.unit && <span className={on ? "opacity-80" : "text-slate-400"}> {m.unit}</span>}
              </button>
            );
          })}
        </div>
      </div>
      <div className="h-[clamp(24rem,60vh,44rem)] p-3">
        {withData.length ? (
          <SeriesChart series={series} loading={qs.some((q) => q.isFetching)} xName="培养天 (day)" />
        ) : (
          <div className="flex h-full items-center justify-center text-sm text-slate-400">{emptyText}</div>
        )}
      </div>
    </section>
  );
}
