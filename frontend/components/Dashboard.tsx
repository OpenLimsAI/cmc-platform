"use client";

// 看板主体（全站只有这一页）：
//   左栏 = 先选批次（看谁）：项目编号 → 批次年份 → 批号（多选）→ 罐号（多选），全站唯一一份；
//   右栏 = 再选看什么：生长曲线 / 生化曲线 / 工艺参数（按时段）/ 工艺时序（全量）/ 数据表 / 取样明细，
//          可同屏多开，横轴统一培养天（全量时序为培养小时）。板块切换绝不动左栏的批次选择。
import { useEffect, useMemo } from "react";
import { usePersisted } from "@/lib/usePersisted";
import { useQuery, keepPreviousData } from "@tanstack/react-query";
import {
  fetchOverviewBatches,
  fetchGrowth,
  fetchNovaSeries,
  fetchProcessBucketed,
  fetchDailyTable,
  type OverviewBatch,
  type ProcessBucketPoint,
} from "@/lib/api";
import { BatchFilter, type BatchNumOption } from "@/components/BatchFilter";
import { CurveSection, type GapMarker } from "@/components/CurveSection";
import { ProcessTimeseriesSection } from "@/components/ProcessTimeseriesSection";
import { SamplesSection } from "@/components/SamplesSection";
import { OsmolalityEntry } from "@/components/OsmolalityEntry";
import { DailyTable } from "@/components/DailyTable";
import {
  CELL_METRICS,
  CELL_DEFAULT_METRICS,
  NOVA_METRICS,
  NOVA_DEFAULT_METRICS,
  GAS_METRICS,
  GAS_DEFAULT_METRICS,
  PROCESS_METRICS,
  PROCESS_DEFAULT_METRICS,
  BUCKET_OPTIONS,
  DEFAULT_BUCKET_HOURS,
} from "@/lib/metrics";
import {
  projValue,
  reactorValue,
  REACTOR_OTHER,
  runOffsets,
  sortBatchNumberDesc,
  sortProject,
  sortReactor,
  toggleIn,
} from "@/lib/batches";

type Section = "cell" | "nova" | "gas" | "process" | "timeseries" | "table" | "samples" | "entry";
const SECTIONS: { code: Section; label: string; hint: string }[] = [
  { code: "cell", label: "生长曲线", hint: "Vi-CELL 细胞密度 / 活率，按培养天" },
  { code: "nova", label: "生化曲线", hint: "Nova FLEX2 葡萄糖 / 乳酸 / 氨…，按培养天" },
  { code: "gas", label: "血气分析", hint: "Nova FLEX2 pH / 氧分压 / 二氧化碳分压，按培养天" },
  { code: "process", label: "工艺参数（按时段）", hint: "Lucullus 温度 / pH / 溶氧…每 N 小时一格（默认 6h）" },
  { code: "timeseries", label: "工艺时序（全量）", hint: "Lucullus 按小时原始采样，可放大到分钟级" },
  { code: "table", label: "数据表", hint: "一行一个批次一个培养天，三源列并排" },
  { code: "samples", label: "取样明细", hint: "每次取样一行" },
  { code: "entry", label: "渗透压录入", hint: "按日期列出当天取过样的样品，手工填渗透压（本看板唯一的写入功能）" },
];
const DEFAULT_SECTIONS: Section[] = ["cell", "nova", "gas", "process"];

export function Dashboard() {
  // 所有筛选与板块设置都记在浏览器本地，刷新页面后原样恢复（负责人 2026-09-08 要求）
  // ---- 第一层：批次筛选（全站唯一）----
  const [fProject, setFProject, restored] = usePersisted("project", "");
  const [fYear, setFYear] = usePersisted("year", "");
  const [selBatchNums, setSelBatchNums] = usePersisted<string[]>("batch_nums", []);
  const [selReactors, setSelReactors] = usePersisted<string[]>("reactors", []); // 空 = 全部罐
  const [excluded, setExcluded] = usePersisted<string[]>("excluded", []); // 从命中结果里手动排除的批次

  // ---- 第二层：板块开关 + 各板块指标（与批次筛选完全独立）----
  const [sections, setSections] = usePersisted<Section[]>("sections", DEFAULT_SECTIONS);
  const [cellMetrics, setCellMetrics] = usePersisted<string[]>("cell_metrics", CELL_DEFAULT_METRICS);
  const [novaMetrics, setNovaMetrics] = usePersisted<string[]>("nova_metrics", NOVA_DEFAULT_METRICS);
  const [gasMetrics, setGasMetrics] = usePersisted<string[]>("gas_metrics", GAS_DEFAULT_METRICS);
  const [procMetrics, setProcMetrics] = usePersisted<string[]>("proc_metrics", PROCESS_DEFAULT_METRICS);
  const [bucketHours, setBucketHours] = usePersisted<number>("bucket_hours", DEFAULT_BUCKET_HOURS); // 工艺参数每格几小时

  const batchesQ = useQuery({ queryKey: ["overview-batches"], queryFn: fetchOverviewBatches });
  const all = useMemo(() => batchesQ.data ?? [], [batchesQ.data]);

  // 级联选项：每一层只列上一层范围内真实存在的值
  const projectOptions = useMemo(() => {
    const s = new Set<string>();
    all.forEach((b) => s.add(projValue(b)));
    return [...s].sort(sortProject);
  }, [all]);

  const yearOptions = useMemo(() => {
    const s = new Set<number>();
    all.forEach((b) => {
      if (fProject && projValue(b) !== fProject) return;
      if (b.batch_year != null) s.add(b.batch_year);
    });
    return [...s].sort((a, b) => b - a);
  }, [all, fProject]);

  const batchNumOptions = useMemo<BatchNumOption[]>(() => {
    const m = new Map<string, BatchNumOption>();
    all.forEach((b) => {
      if (fProject && projValue(b) !== fProject) return;
      if (fYear && String(b.batch_year) !== fYear) return;
      if (!b.batch_number) return;
      const o = m.get(b.batch_number) ?? {
        value: b.batch_number,
        count: 0,
        hasCell: false,
        hasNova: false,
        hasProc: false,
      };
      o.count += 1;
      o.hasCell ||= b.n_vicell > 0;
      o.hasNova ||= b.n_nova > 0;
      o.hasProc ||= b.lucullus_runs.length > 0;
      m.set(b.batch_number, o);
    });
    // 新批号（26003）在上、R 批号在下，各自数字从大到小
    return [...m.values()].sort((a, b) => sortBatchNumberDesc(a.value, b.value));
  }, [all, fProject, fYear]);

  // 罐号选项只在勾了批号之后才列；只认真罐号 A1–A10/B1–B8/R1–R4/C1，其余折成「其它」放末尾
  const reactorOptions = useMemo(() => {
    const s = new Set<string>();
    if (!selBatchNums.length) return [];
    all.forEach((b) => {
      if (fProject && projValue(b) !== fProject) return;
      if (fYear && String(b.batch_year) !== fYear) return;
      if (!selBatchNums.includes(b.batch_number ?? "")) return;
      s.add(reactorValue(b));
    });
    const real = [...s].filter((r) => r !== REACTOR_OTHER).sort(sortReactor);
    return s.has(REACTOR_OTHER) ? [...real, REACTOR_OTHER] : real;
  }, [all, fProject, fYear, selBatchNums]);

  // 命中的批次（= 要看的对象）
  const matched = useMemo(() => {
    if (!selBatchNums.length) return [];
    return all.filter((b) => {
      if (fProject && projValue(b) !== fProject) return false;
      if (fYear && String(b.batch_year) !== fYear) return false;
      if (!selBatchNums.includes(b.batch_number ?? "")) return false;
      if (selReactors.length && !selReactors.includes(reactorValue(b))) return false;
      return true;
    });
  }, [all, fProject, fYear, selBatchNums, selReactors]);

  const selected = useMemo(
    () => matched.filter((b) => !excluded.includes(b.batch_key)),
    [matched, excluded]
  );

  // 上层筛选变了 → 失效的下层选择自动剔除（级联一致）。
  // 批次名单还没加载、或本地记忆还没读回时不剔（否则会把刷新前存的选择清空）。
  const canPrune = !!batchesQ.data && restored;
  useEffect(() => {
    if (!canPrune) return;
    const ok = new Set(batchNumOptions.map((o) => o.value));
    setSelBatchNums((prev) => (prev.every((n) => ok.has(n)) ? prev : prev.filter((n) => ok.has(n))));
  }, [batchNumOptions, canPrune, setSelBatchNums]);
  useEffect(() => {
    if (!canPrune) return;
    setSelReactors((prev) =>
      prev.every((r) => reactorOptions.includes(r)) ? prev : prev.filter((r) => reactorOptions.includes(r))
    );
  }, [reactorOptions, canPrune, setSelReactors]);
  useEffect(() => {
    if (!canPrune) return;
    const keys = new Set(matched.map((b) => b.batch_key));
    setExcluded((prev) => (prev.every((k) => keys.has(k)) ? prev : prev.filter((k) => keys.has(k))));
  }, [matched, canPrune, setExcluded]);

  // 数据表板块：所有选中批次一次请求，后端按 (批次, 培养天) 合并三源
  const selectedKeys = useMemo(() => selected.map((b) => b.batch_key).sort(), [selected]);
  const tableOn = sections.includes("table");
  const tableQ = useQuery({
    queryKey: ["daily-table", selectedKeys.join(",")],
    queryFn: () => fetchDailyTable(selectedKeys),
    enabled: tableOn && selectedKeys.length > 0,
    placeholderData: keepPreviousData,
  });

  const show = (s: Section) => sections.includes(s);
  const hasProc = (b: OverviewBatch) => b.lucullus_runs.length > 0;

  // 按时段工艺参数：该批次几段工艺记录各取一份，按真实开始时间往后挪再拼成一条（中途重开不是并行）
  async function fetchProcessForBatch(b: OverviewBatch, bucket: number) {
    const parts = await Promise.all(
      runOffsets(b).map(async ({ run, offsetHours }) => {
        const d = await fetchProcessBucketed(run.source_instance, run.procid, bucket);
        return d.points.map((p) => ({
          ...p,
          time_hours: p.time_hours + offsetHours,
          culture_day: (p.time_hours + offsetHours) / 24,
        }));
      })
    );
    // 段与段之间插一个断线标记，避免空档被画成一条斜线
    const points: (ProcessBucketPoint & GapMarker)[] = [];
    parts.forEach((seg, i) => {
      if (i > 0 && seg.length && points.length) {
        const last = points[points.length - 1];
        points.push({ ...last, culture_day: last.culture_day + 1e-6, __gap: true });
      }
      points.push(...seg);
    });
    return { points };
  }

  return (
    <div className="flex min-h-0 flex-1">
      <BatchFilter
        loading={batchesQ.isLoading}
        error={batchesQ.isError}
        project={fProject}
        year={fYear}
        batchNums={selBatchNums}
        reactors={selReactors}
        excluded={excluded}
        projectOptions={projectOptions}
        yearOptions={yearOptions}
        batchNumOptions={batchNumOptions}
        reactorOptions={reactorOptions}
        matched={matched}
        onProject={setFProject}
        onYear={setFYear}
        onBatchNums={setSelBatchNums}
        onReactors={setSelReactors}
        onExcluded={setExcluded}
      />

      <main className="min-w-0 flex-1 overflow-y-auto bg-slate-50">
        {/* 第二层：看什么（可同开多块） */}
        <div className="sticky top-0 z-10 flex flex-wrap items-center gap-2 border-b border-slate-200 bg-white px-5 py-2.5">
          {SECTIONS.map((s) => {
            const on = show(s.code);
            return (
              <button
                key={s.code}
                onClick={() => setSections((prev) => toggleIn(prev, s.code))}
                title={s.hint}
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
              已选 {selected.length} 个批次 · 横轴统一培养天
            </span>
          )}
        </div>

        {/* 渗透压录入不依赖左侧批次选择：按日期列当天全部样品 */}
        {show("entry") && (
          <div className="px-5 pt-4">
            <OsmolalityEntry />
          </div>
        )}

        {selected.length === 0 ? (
          <div className="flex h-96 flex-col items-center justify-center gap-1 text-slate-400">
            <div>← 左侧选好项目 / 年份 / 批号 / 罐号</div>
            <div className="text-xs text-slate-300">上方按钮选要看的曲线，可多个板块同屏、多批次叠加</div>
          </div>
        ) : (
          <div className="space-y-4 px-5 py-4">
            {show("cell") && (
              <CurveSection
                title="生长曲线"
                source="Vi-CELL"
                batches={selected}
                hasData={(b) => b.n_vicell > 0}
                queryKey={(b) => ["vicell-growth", b.batch_key]}
                fetch={(b) => fetchGrowth(b.batch_key)}
                defs={CELL_METRICS}
                chosen={cellMetrics}
                onChosen={setCellMetrics}
                emptyText="所选批次都没有细胞计数数据"
                scheme="metric"
              />
            )}
            {show("nova") && (
              <CurveSection
                title="生化曲线"
                source="Nova FLEX2"
                batches={selected}
                hasData={(b) => b.n_nova > 0}
                queryKey={(b) => ["nova-series", b.batch_key]}
                fetch={(b) => fetchNovaSeries(b.batch_key)}
                defs={NOVA_METRICS}
                chosen={novaMetrics}
                onChosen={setNovaMetrics}
                emptyText="所选批次都没有生化分析数据"
                scheme="metric"
              />
            )}
            {show("gas") && (
              <CurveSection
                title="血气分析"
                source="Nova FLEX2"
                batches={selected}
                hasData={(b) => b.n_nova > 0}
                queryKey={(b) => ["nova-series", b.batch_key]}
                fetch={(b) => fetchNovaSeries(b.batch_key)}
                defs={GAS_METRICS}
                chosen={gasMetrics}
                onChosen={setGasMetrics}
                emptyText="所选批次都没有血气数据"
                scheme="metric"
              />
            )}
            {show("process") && (
              <CurveSection
                title="工艺参数（按时段）"
                source={`Lucullus · 每 ${bucketHours} 小时一格取平均`}
                batches={selected}
                hasData={hasProc}
                queryKey={(b) => ["process-bucketed", b.batch_key, bucketHours]}
                fetch={(b) => fetchProcessForBatch(b, bucketHours)}
                defs={PROCESS_METRICS}
                chosen={procMetrics}
                onChosen={setProcMetrics}
                emptyText="所选批次都没有 Lucullus 工艺数据"
                scheme="metric"
                extra={
                  <span className="ml-auto flex items-center gap-2">
                    {/* 时段粒度：一格几小时 */}
                    <span className="flex items-center gap-0.5 rounded-md border border-slate-200 p-0.5">
                      {BUCKET_OPTIONS.map((h) => (
                        <button
                          key={h}
                          onClick={() => setBucketHours(h)}
                          title={`每 ${h} 小时一个点`}
                          className={`rounded px-1.5 py-0.5 text-xs transition ${
                            bucketHours === h ? "bg-slate-700 text-white" : "text-slate-500 hover:bg-slate-100"
                          }`}
                        >
                          {h}h
                        </button>
                      ))}
                    </span>
                    {!show("timeseries") && selected.some(hasProc) && (
                      <button
                        onClick={() => setSections((prev) => [...prev, "timeseries"])}
                        className="rounded border border-blue-300 px-1.5 py-0.5 text-xs text-blue-600 transition hover:bg-blue-50"
                      >
                        看全量时序 →
                      </button>
                    )}
                  </span>
                }
              />
            )}
            {show("timeseries") && <ProcessTimeseriesSection batches={selected} />}
            {show("table") && (
              <section className="rounded-lg border border-slate-200 bg-white">
                <div className="flex items-baseline gap-2 border-b border-slate-100 px-5 py-2.5">
                  <h2 className="text-sm font-semibold">数据表</h2>
                  <span className="text-xs text-slate-400">
                    一行 = 一个批次一个培养天 · 工艺 / 细胞 / 生化 列并排（对齐《项目第一表》）
                  </span>
                </div>
                <DailyTable rows={tableQ.data?.rows ?? []} batches={selected} loading={tableQ.isFetching} />
              </section>
            )}
            {show("samples") && <SamplesSection batches={selected} />}
          </div>
        )}
      </main>
    </div>
  );
}
