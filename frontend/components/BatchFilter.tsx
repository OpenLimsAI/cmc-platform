"use client";

// 全站唯一的批次筛选面板（左栏）：项目编号 → 批次年份 → 批号（多选）→ 罐号（多选）。
// 选出来的批次集合就是"要看的对象"，右侧所有板块共用；板块切换绝不动这里的选择。
// 状态由 Dashboard 持有，这里只是受控展示。
import type { OverviewBatch } from "@/lib/api";
import { batchLabel, fmtDate, PROJ_NONE, projLabel, reactorLabel, REACTOR_OTHER, toggleIn } from "@/lib/batches";

export interface BatchNumOption {
  value: string;
  count: number; // 该批号下有几个罐（批次）
  hasCell: boolean;
  hasNova: boolean;
  hasProc: boolean;
}

export function BatchFilter({
  loading,
  error,
  project,
  year,
  batchNums,
  reactors,
  excluded,
  projectOptions,
  yearOptions,
  batchNumOptions,
  reactorOptions,
  matched,
  onProject,
  onYear,
  onBatchNums,
  onReactors,
  onExcluded,
}: {
  loading: boolean;
  error: boolean;
  project: string;
  year: string;
  batchNums: string[];
  reactors: string[];
  excluded: string[];
  projectOptions: string[];
  yearOptions: number[];
  batchNumOptions: BatchNumOption[];
  reactorOptions: string[];
  matched: OverviewBatch[];
  onProject: (v: string) => void;
  onYear: (v: string) => void;
  onBatchNums: (v: string[]) => void;
  onReactors: (v: string[]) => void;
  onExcluded: (v: string[]) => void;
}) {
  const selectedCount = matched.filter((b) => !excluded.includes(b.batch_key)).length;
  const selectCls =
    "w-full rounded-md border border-slate-300 bg-white px-2 py-1.5 text-sm text-slate-800 focus:border-blue-500 focus:outline-none";

  return (
    <aside className="flex w-80 shrink-0 flex-col border-r border-slate-200 bg-white">
      <div className="space-y-3 border-b border-slate-200 px-4 py-3">
        <div className="text-xs font-semibold text-slate-600">先选批次（看谁）</div>

        {/* ① 项目  ② 年份 */}
        <div className="grid grid-cols-2 gap-2">
          <label className="block">
            <span className="mb-1 block text-xs font-medium text-slate-500">① 项目编号</span>
            <select value={project} onChange={(e) => onProject(e.target.value)} className={selectCls}>
              <option value="">全部项目</option>
              {projectOptions.map((p) => (
                <option key={p} value={p}>
                  {projLabel(p)}
                </option>
              ))}
            </select>
          </label>
          <label className="block">
            <span className="mb-1 block text-xs font-medium text-slate-500">② 批次年份</span>
            <select value={year} onChange={(e) => onYear(e.target.value)} className={selectCls}>
              <option value="">全部年份</option>
              {yearOptions.map((y) => (
                <option key={y} value={String(y)}>
                  {y}
                </option>
              ))}
            </select>
          </label>
        </div>

        {/* ③ 批号多选 */}
        <div>
          <div className="mb-1 flex items-center justify-between">
            <span className="text-xs font-medium text-slate-500">
              ③ 批号 <span className="text-slate-400">（可多选，叠加对比）</span>
            </span>
            <span className="flex gap-1">
              <button
                onClick={() => onBatchNums(batchNumOptions.map((o) => o.value))}
                className="rounded border border-slate-200 px-1.5 py-0.5 text-xs text-slate-500 hover:bg-slate-50"
              >
                全选
              </button>
              <button
                onClick={() => onBatchNums([])}
                className="rounded border border-slate-200 px-1.5 py-0.5 text-xs text-slate-500 hover:bg-slate-50"
              >
                清空
              </button>
            </span>
          </div>
          <div className="max-h-52 overflow-y-auto rounded-md border border-slate-200">
            {loading && <div className="p-2 text-xs text-slate-400">加载批次名单中…</div>}
            {!loading && batchNumOptions.length === 0 && (
              <div className="p-2 text-xs text-slate-400">当前项目 / 年份下没有批号</div>
            )}
            {batchNumOptions.map((o) => {
              const on = batchNums.includes(o.value);
              return (
                <label
                  key={o.value}
                  className={`flex cursor-pointer items-center gap-2 border-b border-slate-100 px-2.5 py-1.5 text-sm last:border-b-0 ${
                    on ? "bg-blue-50 text-blue-700" : "text-slate-700 hover:bg-slate-50"
                  }`}
                >
                  <input
                    type="checkbox"
                    checked={on}
                    onChange={() => onBatchNums(toggleIn(batchNums, o.value))}
                    className="accent-blue-500"
                  />
                  <span className={`truncate ${project === PROJ_NONE ? "font-mono text-xs" : ""}`}>
                    {o.value}
                  </span>
                  <span className="ml-auto flex shrink-0 items-center gap-1 text-[10px]">
                    {/* 三个小点 = 该批号有哪几种数据：细胞 / 生化 / 工艺 */}
                    <Dot on={o.hasCell} cls="bg-emerald-500" title="有细胞计数" />
                    <Dot on={o.hasNova} cls="bg-sky-500" title="有生化分析" />
                    <Dot on={o.hasProc} cls="bg-violet-500" title="有工艺数据" />
                    <span className="ml-1 text-slate-400">{o.count} 罐</span>
                  </span>
                </label>
              );
            })}
          </div>
        </div>

        {/* ④ 罐号：默认全部，点选收窄 */}
        <div>
          <div className="mb-1 flex items-center justify-between">
            <span className="text-xs font-medium text-slate-500">
              ④ 罐号 <span className="text-slate-400">（默认全部，点选收窄）</span>
            </span>
            {reactors.length > 0 && (
              <button
                onClick={() => onReactors([])}
                className="rounded border border-slate-200 px-1.5 py-0.5 text-xs text-slate-500 hover:bg-slate-50"
              >
                全部罐
              </button>
            )}
          </div>
          <div className="flex flex-wrap gap-1">
            {reactorOptions.map((r) => {
              const on = reactors.includes(r);
              return (
                <button
                  key={r}
                  onClick={() => onReactors(toggleIn(reactors, r))}
                  title={r === REACTOR_OTHER ? "不是标准罐号的批次（样本名录入不规范拆出来的），统一归这里" : undefined}
                  className={`rounded border px-1.5 py-0.5 text-xs transition ${
                    on
                      ? "border-blue-500 bg-blue-500 text-white"
                      : r === REACTOR_OTHER
                        ? "border-dashed border-slate-300 bg-white text-slate-400 hover:border-slate-400"
                        : "border-slate-200 bg-white text-slate-600 hover:border-slate-300"
                  }`}
                >
                  {reactorLabel(r)}
                </button>
              );
            })}
            {reactorOptions.length === 0 && (
              <span className="text-xs text-slate-400">先勾选批号</span>
            )}
          </div>
        </div>
      </div>

      {/* 命中的批次（罐粒度 = 一条曲线）；点某一项可临时排除 */}
      <div className="flex items-center justify-between border-b border-slate-100 px-4 py-2 text-xs font-medium text-slate-400">
        <span className="uppercase tracking-wide">
          将显示的批次（{selectedCount}
          {excluded.length > 0 ? ` / 命中 ${matched.length}` : ""}）
        </span>
        {excluded.length > 0 && (
          <button
            onClick={() => onExcluded([])}
            className="rounded border border-slate-200 px-1.5 py-0.5 text-slate-500 hover:bg-slate-50"
          >
            恢复排除
          </button>
        )}
      </div>
      <div className="min-h-0 flex-1 overflow-y-auto">
        {error && (
          <div className="p-4 text-sm text-red-500">
            连不上后端，或未配置 cmc_analytics 连接。
          </div>
        )}
        {!loading && !error && batchNums.length === 0 && (
          <div className="p-4 text-sm text-slate-400">
            ↑ 先勾选批号。选一个批号 = 看它所有罐；选多个 = 跨批次对比。
          </div>
        )}
        {matched.map((b) => {
          const off = excluded.includes(b.batch_key);
          const runs = b.lucullus_runs.length;
          return (
            <button
              key={b.batch_key}
              onClick={() => onExcluded(toggleIn(excluded, b.batch_key))}
              title={off ? "已排除，点击恢复" : "点击临时排除这个批次"}
              className={`block w-full border-b border-slate-100 px-4 py-2 text-left transition ${
                off ? "opacity-40" : "hover:bg-slate-50"
              }`}
            >
              <div className="flex items-center gap-2">
                <span className={`truncate text-sm font-medium text-slate-800 ${off ? "line-through" : ""}`}>
                  {batchLabel(b)}
                </span>
                {b.unparsed && b.bioreactor_id && (
                  <span className="text-xs text-slate-400">罐 {b.bioreactor_id}</span>
                )}
              </div>
              <div className="mt-0.5 flex items-center gap-1.5 text-xs text-slate-400">
                {b.n_vicell > 0 && (
                  <span className="rounded bg-emerald-50 px-1.5 py-0.5 text-emerald-700">细胞 {b.n_vicell}</span>
                )}
                {b.n_nova > 0 && (
                  <span className="rounded bg-sky-50 px-1.5 py-0.5 text-sky-700">生化 {b.n_nova}</span>
                )}
                {runs > 0 && (
                  <span className="rounded bg-violet-50 px-1.5 py-0.5 text-violet-700">
                    工艺{runs > 1 ? ` ×${runs}` : ""}
                  </span>
                )}
                <span className="ml-auto">
                  {b.day_min != null ? `${b.day_min}–${b.day_max} 天` : fmtDate(b.first_at)}
                </span>
              </div>
            </button>
          );
        })}
      </div>
    </aside>
  );
}

function Dot({ on, cls, title }: { on: boolean; cls: string; title: string }) {
  return (
    <span
      title={on ? title : undefined}
      className={`inline-block h-1.5 w-1.5 rounded-full ${on ? cls : "bg-slate-200"}`}
    />
  );
}
