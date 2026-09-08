"use client";

// 渗透压录入（独立页面 /entry）——本看板唯一会写数据库的地方（负责人 2026-09-09 定）。
// 按日期（默认今天）自动列出当天该取样的全部样品：批号登记系统的"当天样品清单"为准，再并上仪器
// （Nova / Vi-CELL）当天实测到的样品；批次 / 罐 / 培养天 / 样品名自动带出，试验员只填渗透压数值。
// 没取样的行点 × 删掉（只影响本机这一天的列表，可恢复）；临时样品用"添加一行"。
// 保存 = 追加一行，改数再存即可，历史都留着。
import { useEffect, useMemo, useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  fetchDailySheet,
  fetchManualStatus,
  fetchOverviewBatches,
  saveManualResults,
  type DailySheetRow,
} from "@/lib/api";
import { useAuth } from "@/components/AuthGate";
import { usePersisted } from "@/lib/usePersisted";

const pad = (n: number) => (n < 10 ? `0${n}` : String(n));
const today = () => {
  const d = new Date();
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
};
const shiftDate = (s: string, days: number) => {
  const d = new Date(s + "T00:00:00");
  d.setDate(d.getDate() + days);
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
};
const rowKey = (r: { batch_key: string; culture_day: number }) => `${r.batch_key}#${r.culture_day}`;

// 试验员临时加的样品行（本机记住，按日期）
interface ExtraRow {
  batch_key: string;
  culture_day: number;
}

export function OsmolalityEntry() {
  const qc = useQueryClient();
  const { user } = useAuth();
  const [date, setDate] = useState(today());
  // 每行输入框里的文字（key = 批次#培养天）；只记用户改过的
  const [draft, setDraft] = useState<Record<string, string>>({});
  const [message, setMessage] = useState<string | null>(null);
  const inputs = useRef<Record<string, HTMLInputElement | null>>({});
  // 本机记住：这一天删掉的行、临时加的行（换电脑不带，明天不影响）
  const [removedByDate, setRemovedByDate] = usePersisted<Record<string, string[]>>("entry_removed", {});
  const [extrasByDate, setExtrasByDate] = usePersisted<Record<string, ExtraRow[]>>("entry_extras", {});
  const removed = useMemo(() => new Set(removedByDate[date] ?? []), [removedByDate, date]);
  const extras = useMemo(() => extrasByDate[date] ?? [], [extrasByDate, date]);
  // 添加一行的小表单
  const [adding, setAdding] = useState(false);
  const [addKey, setAddKey] = useState("");
  const [addDay, setAddDay] = useState("");

  const statusQ = useQuery({ queryKey: ["manual-status"], queryFn: fetchManualStatus, staleTime: 5 * 60_000 });
  const sheetQ = useQuery({
    queryKey: ["daily-sheet", date],
    queryFn: () => fetchDailySheet(date),
    enabled: !!statusQ.data?.enabled,
  });
  // 加行时给批次身份做候选（全部已知批次）
  const batchesQ = useQuery({ queryKey: ["overview-batches"], queryFn: fetchOverviewBatches, enabled: adding });

  // 换了日期就清掉未保存的草稿
  useEffect(() => {
    setDraft({});
    setMessage(null);
    setAdding(false);
  }, [date]);

  const metric = sheetQ.data?.metric;

  // 最终显示的行 = 清单里的行（去掉删掉的）+ 临时加的行
  const rows = useMemo<DailySheetRow[]>(() => {
    const base = (sheetQ.data?.rows ?? []).filter((r) => !removed.has(rowKey(r)));
    const known = new Set(base.map(rowKey));
    const extraRows: DailySheetRow[] = extras
      .filter((e) => !known.has(rowKey(e)) && !removed.has(rowKey(e)))
      .map((e) => {
        const parts = e.batch_key.split("_");
        return {
          batch_key: e.batch_key,
          project_id: parts[0] ?? null,
          batch_number: parts[1] ?? null,
          bioreactor_id: parts.slice(2).join("_") || null,
          culture_day: e.culture_day,
          sample_name: null,
          kind: "extra",
          planned: false,
          sample_ids: null,
          has_nova: false,
          has_vicell: false,
          existing_value: null,
          existing_by: null,
          existing_by_name: null,
          existing_at: null,
          existing_note: null,
        };
      });
    return [...base, ...extraRows];
  }, [sheetQ.data, removed, extras]);
  const removedCount = (sheetQ.data?.rows ?? []).filter((r) => removed.has(rowKey(r))).length;

  // 待保存的行：填了数、且和已录值不同
  const pending = useMemo(() => {
    const out: { row: DailySheetRow; value: number }[] = [];
    rows.forEach((r) => {
      const t = draft[rowKey(r)];
      if (t == null || t.trim() === "") return;
      const v = Number(t);
      if (!Number.isFinite(v)) return;
      if (r.existing_value != null && Math.abs(r.existing_value - v) < 1e-9) return;
      out.push({ row: r, value: v });
    });
    return out;
  }, [rows, draft]);

  const invalid = useMemo(() => {
    if (!metric) return [];
    return rows.filter((r) => {
      const t = draft[rowKey(r)];
      if (t == null || t.trim() === "") return false;
      const v = Number(t);
      return !Number.isFinite(v) || v < metric.min || v > metric.max;
    });
  }, [rows, draft, metric]);

  const saveM = useMutation({
    mutationFn: () =>
      saveManualResults(
        date,
        pending.map(({ row, value }) => ({
          batch_key: row.batch_key,
          culture_day: row.culture_day,
          value,
          source_sample_ids: row.sample_name ?? row.sample_ids,
        }))
      ),
    onSuccess: (res) => {
      setMessage(`已保存 ${res.saved} 条${res.skipped ? `，${res.skipped} 条与已录值相同未重复存` : ""}`);
      setDraft({});
      qc.invalidateQueries({ queryKey: ["daily-sheet", date] });
      // 生化曲线 / 数据表里的渗透压跟着刷新
      qc.invalidateQueries({ queryKey: ["nova-series"] });
      qc.invalidateQueries({ queryKey: ["daily-table"] });
    },
    onError: (e: unknown) => {
      const detail = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      setMessage(`保存失败：${detail ?? "请稍后再试"}`);
    },
  });

  function removeRow(r: DailySheetRow) {
    const k = rowKey(r);
    if (r.kind === "extra") {
      setExtrasByDate((prev) => ({ ...prev, [date]: (prev[date] ?? []).filter((e) => rowKey(e) !== k) }));
    } else {
      setRemovedByDate((prev) => ({ ...prev, [date]: [...(prev[date] ?? []), k] }));
    }
    setDraft((prev) => {
      const next = { ...prev };
      delete next[k];
      return next;
    });
  }
  function restoreRemoved() {
    setRemovedByDate((prev) => ({ ...prev, [date]: [] }));
  }
  function addRow() {
    const key = addKey.trim();
    const day = parseInt(addDay, 10);
    if (!key || !Number.isFinite(day) || day < 0) return;
    setExtrasByDate((prev) => ({
      ...prev,
      [date]: [...(prev[date] ?? []).filter((e) => rowKey(e) !== `${key}#${day}`), { batch_key: key, culture_day: day }],
    }));
    setRemovedByDate((prev) => ({ ...prev, [date]: (prev[date] ?? []).filter((k) => k !== `${key}#${day}`) }));
    setAddKey("");
    setAddDay("");
    setAdding(false);
    setTimeout(() => inputs.current[`${key}#${day}`]?.focus(), 50);
  }

  // 回车 → 跳到下一行的输入框；粘贴多行（从 Excel 复制一列）→ 从当前行往下依次填
  function onKeyDown(e: React.KeyboardEvent<HTMLInputElement>, idx: number) {
    if (e.key === "Enter") {
      e.preventDefault();
      const next = rows[idx + 1];
      if (next) inputs.current[rowKey(next)]?.focus();
    }
  }
  function onPaste(e: React.ClipboardEvent<HTMLInputElement>, idx: number) {
    const text = e.clipboardData.getData("text");
    const parts = text.split(/\r?\n/).map((t) => t.trim()).filter((t) => t !== "");
    if (parts.length <= 1) return; // 单个值走默认粘贴
    e.preventDefault();
    setDraft((prev) => {
      const next = { ...prev };
      parts.forEach((t, i) => {
        const r = rows[idx + i];
        if (r) next[rowKey(r)] = t.replace(/[^\d.\-]/g, "");
      });
      return next;
    });
  }

  const canWrite = !!user && (user.is_system || user.roles.length > 0);
  const sheet = sheetQ.data;

  return (
    <section className="rounded-lg border border-slate-200 bg-white">
      <div className="flex flex-wrap items-center gap-3 border-b border-slate-100 px-5 py-2.5">
        <span className="text-sm font-semibold">取样日期</span>
        <span className="flex items-center gap-1">
          <button
            onClick={() => setDate((d) => shiftDate(d, -1))}
            className="rounded border border-slate-200 px-1.5 py-0.5 text-xs text-slate-500 hover:bg-slate-50"
            title="前一天"
          >
            ‹
          </button>
          <input
            type="date"
            value={date}
            max={today()}
            onChange={(e) => e.target.value && setDate(e.target.value)}
            className="rounded-md border border-slate-300 px-2 py-1 text-sm text-slate-800 focus:border-blue-500 focus:outline-none"
          />
          <button
            onClick={() => setDate((d) => (d < today() ? shiftDate(d, 1) : d))}
            className="rounded border border-slate-200 px-1.5 py-0.5 text-xs text-slate-500 hover:bg-slate-50"
            title="后一天"
          >
            ›
          </button>
          {date !== today() && (
            <button
              onClick={() => setDate(today())}
              className="rounded border border-slate-200 px-1.5 py-0.5 text-xs text-slate-500 hover:bg-slate-50"
            >
              今天
            </button>
          )}
        </span>
        {sheet && (
          <span className="text-xs text-slate-400">
            {sheet.registry_used ? "样品清单来自批号登记系统，并已合并仪器实测样品" : "样品清单来自仪器实测（Nova / Vi-CELL）"}
            {" · 单位 "}
            {metric?.unit}
          </span>
        )}
        <span className="ml-auto text-xs text-slate-400">录入人：{user?.full_name || user?.username || "—"}</span>
      </div>

      {sheet?.registry_error && (
        <div className="border-b border-amber-100 bg-amber-50 px-5 py-2 text-xs text-amber-700">{sheet.registry_error}</div>
      )}

      {statusQ.data && !statusQ.data.enabled && (
        <div className="p-6 text-sm text-amber-600">后端未配置写库账号，暂不能录入（联系管理员）。</div>
      )}

      {statusQ.data?.enabled && (
        <>
          {sheetQ.isLoading && <div className="p-6 text-sm text-slate-400">加载当天样品中…</div>}
          {sheet && rows.length === 0 && (
            <div className="p-6 text-sm text-slate-400">
              {date} 没有样品。
              {removedCount > 0 ? (
                <>
                  已删掉 {removedCount} 行，
                  <button onClick={restoreRemoved} className="text-blue-600 underline">
                    恢复
                  </button>
                  。
                </>
              ) : (
                "批号登记系统里这天没有该取样的样品，仪器上也没有实测记录；可用下面的「添加一行」录临时样品。"
              )}
            </div>
          )}
          {rows.length > 0 && (
            <div className="p-4">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-slate-200 text-left text-xs text-slate-500">
                    <th className="px-2 py-1.5">#</th>
                    <th className="px-2 py-1.5">项目</th>
                    <th className="px-2 py-1.5">批号</th>
                    <th className="px-2 py-1.5">罐 / 阶段</th>
                    <th className="px-2 py-1.5 text-right">培养天</th>
                    <th className="px-2 py-1.5">样品名</th>
                    <th className="px-2 py-1.5">来源</th>
                    <th className="px-2 py-1.5 text-right">已录值</th>
                    <th className="px-2 py-1.5">录入人 / 时间</th>
                    <th className="px-2 py-1.5">渗透压 ({metric?.unit})</th>
                    <th className="px-2 py-1.5"></th>
                  </tr>
                </thead>
                <tbody>
                  {rows.map((r, i) => {
                    const k = rowKey(r);
                    const t = draft[k] ?? "";
                    const v = t.trim() === "" ? null : Number(t);
                    const bad = v != null && metric && (!Number.isFinite(v) || v < metric.min || v > metric.max);
                    const changed =
                      v != null && Number.isFinite(v) && (r.existing_value == null || Math.abs(r.existing_value - v) >= 1e-9);
                    return (
                      <tr key={k} className="border-b border-slate-100 text-slate-700">
                        <td className="px-2 py-1 text-xs text-slate-400">{i + 1}</td>
                        <td className="px-2 py-1">{r.project_id ?? "—"}</td>
                        <td className="px-2 py-1">{r.batch_number ?? "—"}</td>
                        <td className="px-2 py-1 font-medium">{r.bioreactor_id ?? "—"}</td>
                        <td className="px-2 py-1 text-right">{r.culture_day}</td>
                        <td className="max-w-72 truncate px-2 py-1 text-xs text-slate-600" title={r.sample_ids ?? r.sample_name ?? ""}>
                          {r.sample_name ?? r.sample_ids ?? "—"}
                        </td>
                        <td className="px-2 py-1">
                          <span className="flex gap-1">
                            {r.planned && <Badge cls="bg-blue-50 text-blue-700">计划</Badge>}
                            {r.has_nova && <Badge cls="bg-sky-50 text-sky-700">生化</Badge>}
                            {r.has_vicell && <Badge cls="bg-emerald-50 text-emerald-700">细胞</Badge>}
                            {r.kind === "extra" && <Badge cls="bg-amber-50 text-amber-700">临时</Badge>}
                          </span>
                        </td>
                        <td className="px-2 py-1 text-right tabular-nums">
                          {r.existing_value != null ? r.existing_value.toFixed(0) : <span className="text-slate-300">未录</span>}
                        </td>
                        <td className="px-2 py-1 text-xs text-slate-400">
                          {r.existing_by ? `${r.existing_by_name || r.existing_by} · ${r.existing_at?.slice(0, 16).replace("T", " ")}` : ""}
                        </td>
                        <td className="px-2 py-1">
                          <input
                            ref={(el) => {
                              inputs.current[k] = el;
                            }}
                            type="text"
                            inputMode="decimal"
                            value={t}
                            placeholder={r.existing_value != null ? "改数在此填新值" : "填数值"}
                            disabled={!canWrite}
                            onChange={(e) => setDraft((prev) => ({ ...prev, [k]: e.target.value }))}
                            onKeyDown={(e) => onKeyDown(e, i)}
                            onPaste={(e) => onPaste(e, i)}
                            className={`w-32 rounded-md border px-2 py-1 text-right text-sm tabular-nums focus:outline-none ${
                              bad
                                ? "border-red-400 bg-red-50 text-red-700"
                                : changed
                                  ? "border-blue-400 bg-blue-50"
                                  : "border-slate-300 focus:border-blue-500"
                            }`}
                          />
                        </td>
                        <td className="px-2 py-1">
                          <button
                            onClick={() => removeRow(r)}
                            title="没取样 / 不录这一行：从今天的清单里删掉（只影响本机显示，可恢复）"
                            className="rounded px-1.5 py-0.5 text-xs text-slate-400 hover:bg-red-50 hover:text-red-600"
                          >
                            ×
                          </button>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}

          <div className="flex flex-wrap items-center gap-3 border-t border-slate-100 px-4 py-3">
            <button
              onClick={() => saveM.mutate()}
              disabled={!canWrite || pending.length === 0 || invalid.length > 0 || saveM.isPending}
              className="rounded-md bg-blue-600 px-4 py-1.5 text-sm text-white transition hover:bg-blue-700 disabled:opacity-40"
            >
              {saveM.isPending ? "保存中…" : `保存${pending.length ? `（${pending.length} 条）` : ""}`}
            </button>
            {!adding ? (
              <button
                onClick={() => setAdding(true)}
                className="rounded-md border border-slate-300 px-3 py-1.5 text-sm text-slate-600 transition hover:bg-slate-50"
              >
                ＋ 添加一行（临时样品）
              </button>
            ) : (
              <span className="flex items-center gap-2 rounded-md border border-slate-200 bg-slate-50 px-2 py-1">
                <input
                  list="entry-batch-keys"
                  value={addKey}
                  onChange={(e) => setAddKey(e.target.value)}
                  placeholder="批次身份，如 016_26003_A6"
                  className="w-56 rounded-md border border-slate-300 px-2 py-1 text-sm focus:border-blue-500 focus:outline-none"
                />
                <datalist id="entry-batch-keys">
                  {(batchesQ.data ?? []).filter((b) => !b.unparsed).map((b) => (
                    <option key={b.batch_key} value={b.batch_key} />
                  ))}
                </datalist>
                <input
                  type="number"
                  min={0}
                  value={addDay}
                  onChange={(e) => setAddDay(e.target.value)}
                  placeholder="培养天"
                  className="w-24 rounded-md border border-slate-300 px-2 py-1 text-sm focus:border-blue-500 focus:outline-none"
                />
                <button
                  onClick={addRow}
                  disabled={!addKey.trim() || addDay === ""}
                  className="rounded-md bg-slate-700 px-3 py-1 text-sm text-white disabled:opacity-40"
                >
                  加入
                </button>
                <button onClick={() => setAdding(false)} className="px-2 text-sm text-slate-500">
                  取消
                </button>
              </span>
            )}
            {removedCount > 0 && (
              <button onClick={restoreRemoved} className="text-xs text-slate-500 underline">
                恢复已删的 {removedCount} 行
              </button>
            )}
            {invalid.length > 0 && metric && (
              <span className="text-xs text-red-600">
                有 {invalid.length} 个数值不在 {metric.min}–{metric.max} {metric.unit} 范围内，请检查
              </span>
            )}
            {message && <span className="text-xs text-slate-600">{message}</span>}
            <span className="ml-auto text-xs text-slate-400">回车跳下一行 · 可从 Excel 复制一列直接粘贴</span>
          </div>
        </>
      )}
    </section>
  );
}

function Badge({ cls, children }: { cls: string; children: React.ReactNode }) {
  return <span className={`rounded px-1 py-0.5 text-[10px] ${cls}`}>{children}</span>;
}
