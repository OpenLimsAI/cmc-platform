"use client";

// 数据录入（独立页面 /entry）——本看板唯一会写数据库的地方（负责人 2026-09-09 定，2026-09-11 从
// 「渗透压录入」扩成「数据录入」）。目前两个指标：渗透压（mOsm/kg）、葡萄糖（g/L，试剂盒法）。
// 葡萄糖为什么也要人工录：摇瓶 / 摇管常常不做生化分析，只用试剂盒单测葡萄糖，仪器不联网、系统采不到。
// 取数优先级：同一批次同一培养天生化仪测了葡萄糖就用仪器值，没测才用人工录的（后端 routers/nova.py、
// overview.py 里做，这里只管录）。有仪器值的格子会灰字显示仪器值，仍可填，填了只留档不上图。
//
// 按日期（默认今天）自动列出当天该取样的全部样品：批号登记系统的"当天样品清单"为准，再并上仪器
// （Nova / Vi-CELL）当天实测到的样品。一行 = 一次取样：取样时刻自动从仪器记录带出，同一样品当天
// 多次取样自动分行（第二次起样品名带 -T1）；时刻和样品名都可改，每行「＋」可再加一次取样。
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
  type ManualMetric,
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
// 一行的身份 = 批次 # 培养天 # 样品名
const rowKey = (r: { batch_key: string; culture_day: number; sample_name: string }) =>
  `${r.batch_key}#${r.culture_day}#${r.sample_name}`;
// 一个格子的身份 = 行 # 指标
const cellKey = (r: DailySheetRow, code: string) => `${rowKey(r)}#${code}`;
const TIME_RE = /^([01]\d|2[0-3]):[0-5]\d$/;
// 录入时间来自库里的 timestamptz（带 +00:00），直接截字符串会显示成 UTC，要按本机时区（北京）显示
const fmtEnteredAt = (iso: string | null | undefined) => {
  if (!iso) return "";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso.slice(0, 16).replace("T", " ");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`;
};

// 试验员临时加的取样行（本机记住，按日期）
interface ExtraRow {
  batch_key: string;
  culture_day: number;
  sample_name: string;
  sample_time: string | null;
}
// 一行里可编辑的东西：各指标的值 + 取样时刻 + 样品名
interface Draft {
  values?: Record<string, string>;
  time?: string;
  name?: string;
}

export function DataEntry() {
  const qc = useQueryClient();
  const { user } = useAuth();
  const [date, setDate] = useState(today());
  const [draft, setDraft] = useState<Record<string, Draft>>({});
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
  const batchesQ = useQuery({ queryKey: ["overview-batches"], queryFn: fetchOverviewBatches, enabled: adding });

  useEffect(() => {
    setDraft({});
    setMessage(null);
    setAdding(false);
  }, [date]);

  const metrics = useMemo<ManualMetric[]>(() => sheetQ.data?.metrics ?? [], [sheetQ.data]);

  // 最终显示的行 = 清单里的行（去掉删掉的）+ 临时加的行（按样品名去重）
  const rows = useMemo<DailySheetRow[]>(() => {
    const base = (sheetQ.data?.rows ?? []).filter((r) => !removed.has(rowKey(r)));
    const known = new Set(base.map(rowKey));
    // 旧版本本机记的临时行没有样品名，补一个
    const norm = (e: ExtraRow): ExtraRow => ({
      ...e,
      sample_name: e.sample_name || `${e.batch_key.replace(/_/g, "-")}-D${pad(e.culture_day)}`,
      sample_time: e.sample_time ?? null,
    });
    const extraRows: DailySheetRow[] = extras
      .map(norm)
      .filter((e) => !known.has(rowKey(e)) && !removed.has(rowKey(e)))
      .map((e) => {
        const parts = e.batch_key.split("_");
        return {
          batch_key: e.batch_key,
          project_id: parts[0] ?? null,
          batch_number: parts[1] ?? null,
          bioreactor_id: parts.slice(2).join("_") || null,
          culture_day: e.culture_day,
          sample_name: e.sample_name,
          sample_time: e.sample_time,
          kind: "extra",
          planned: false,
          sample_ids: null,
          has_nova: false,
          has_vicell: false,
          nova_gluc: null,
          entries: {},
        };
      });
    const all = [...base, ...extraRows];
    // 同一样品的几次取样排在一起，按时刻先后
    all.sort((a, b) => {
      const ka = `${a.project_id ?? ""}|${a.batch_number ?? ""}|${a.bioreactor_id ?? ""}|${a.culture_day}`;
      const kb = `${b.project_id ?? ""}|${b.batch_number ?? ""}|${b.bioreactor_id ?? ""}|${b.culture_day}`;
      if (ka !== kb) return ka < kb ? -1 : 1;
      return (a.sample_time ?? "99") < (b.sample_time ?? "99") ? -1 : 1;
    });
    return all;
  }, [sheetQ.data, removed, extras]);
  const removedCount = (sheetQ.data?.rows ?? []).filter((r) => removed.has(rowKey(r))).length;

  const effective = (r: DailySheetRow) => {
    const d = draft[rowKey(r)] ?? {};
    return {
      values: d.values ?? {},
      time: d.time ?? r.sample_time ?? "",
      name: d.name ?? r.sample_name ?? "",
    };
  };
  const cellValue = (r: DailySheetRow, code: string) => effective(r).values[code] ?? "";
  // 这一行最近一次录入是谁、什么时候（几个指标取最新的那条）
  const lastEntry = (r: DailySheetRow) =>
    Object.values(r.entries ?? {})
      .filter((e) => e)
      .sort((a, b) => ((a!.entered_at ?? "") < (b!.entered_at ?? "") ? 1 : -1))[0] ?? null;

  // 待保存的格子：填了数、且和已录值不同（或样品名改了，要跟着改存）
  const pending = useMemo(() => {
    const out: { row: DailySheetRow; code: string; value: number; time: string; name: string }[] = [];
    rows.forEach((r) => {
      const e = effective(r);
      metrics.forEach((m) => {
        const raw = (e.values[m.code] ?? "").trim();
        if (raw === "") return;
        const v = Number(raw);
        if (!Number.isFinite(v)) return;
        const cur = r.entries?.[m.code]?.value ?? null;
        if (cur != null && Math.abs(cur - v) < 1e-9 && e.name === r.sample_name) return;
        out.push({ row: r, code: m.code, value: v, time: e.time, name: e.name.trim() });
      });
    });
    return out;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [rows, draft, metrics]);

  const problems = useMemo(() => {
    const out: string[] = [];
    if (metrics.length === 0) return out;
    const names = new Map<string, number>();
    rows.forEach((r) => {
      const e = effective(r);
      const key = `${r.batch_key}#${r.culture_day}#${e.name.trim()}`;
      names.set(key, (names.get(key) ?? 0) + 1);
      metrics.forEach((m) => {
        const raw = (e.values[m.code] ?? "").trim();
        if (raw === "") return;
        const v = Number(raw);
        if (!Number.isFinite(v) || v < m.min || v > m.max)
          out.push(`${e.name} 的${m.name}：要在 ${m.min}–${m.max} ${m.unit}`);
      });
      if (e.time && !TIME_RE.test(e.time)) out.push(`${e.name}：时刻格式应为 HH:MM`);
      if (!e.name.trim()) out.push(`${r.batch_key} 第 ${r.culture_day} 天：样品名不能为空`);
    });
    names.forEach((n, k) => {
      if (n > 1) out.push(`样品名重复：${k.split("#")[2]}`);
    });
    return out;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [rows, draft, metrics]);

  const saveM = useMutation({
    mutationFn: () =>
      saveManualResults(
        date,
        pending.map(({ row, code, value, time, name }) => ({
          batch_key: row.batch_key,
          culture_day: row.culture_day,
          metric_code: code,
          value,
          sample_name: name,
          sample_time: TIME_RE.test(time) ? time : null,
          source_sample_ids: row.sample_ids,
        }))
      ),
    onSuccess: (res) => {
      setMessage(`已保存 ${res.saved} 条${res.skipped ? `，${res.skipped} 条与已录值相同未重复存` : ""}`);
      setDraft({});
      qc.invalidateQueries({ queryKey: ["daily-sheet", date] });
      qc.invalidateQueries({ queryKey: ["nova-series"] });
      qc.invalidateQueries({ queryKey: ["daily-table"] });
    },
    onError: (e: unknown) => {
      const detail = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      setMessage(`保存失败：${detail ?? "请稍后再试"}`);
    },
  });

  function setField(k: string, field: "time" | "name", v: string) {
    setDraft((prev) => ({ ...prev, [k]: { ...(prev[k] ?? {}), [field]: v } }));
  }
  function setValue(k: string, code: string, v: string) {
    setDraft((prev) => ({
      ...prev,
      [k]: { ...(prev[k] ?? {}), values: { ...((prev[k] ?? {}).values ?? {}), [code]: v } },
    }));
  }
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
  function pushExtra(e: ExtraRow) {
    setExtrasByDate((prev) => ({
      ...prev,
      [date]: [...(prev[date] ?? []).filter((x) => rowKey(x) !== rowKey(e)), e],
    }));
    setRemovedByDate((prev) => ({ ...prev, [date]: (prev[date] ?? []).filter((k) => k !== rowKey(e)) }));
    const first = metrics[0]?.code;
    if (first) setTimeout(() => inputs.current[`${rowKey(e)}#${first}`]?.focus(), 50);
  }
  // 同一样品再加一次取样：样品名接着 -T1 / -T2 往下编
  function addResample(r: DailySheetRow) {
    const base = r.sample_name.replace(/-T\d+$/, "");
    const taken = new Set(rows.filter((x) => x.batch_key === r.batch_key && x.culture_day === r.culture_day).map((x) => effective(x).name));
    let i = 1;
    while (taken.has(`${base}-T${i}`)) i++;
    pushExtra({ batch_key: r.batch_key, culture_day: r.culture_day, sample_name: `${base}-T${i}`, sample_time: null });
  }
  function addRow() {
    const key = addKey.trim();
    const day = parseInt(addDay, 10);
    if (!key || !Number.isFinite(day) || day < 0) return;
    pushExtra({ batch_key: key, culture_day: day, sample_name: `${key.replace(/_/g, "-")}-D${pad(day)}`, sample_time: null });
    setAddKey("");
    setAddDay("");
    setAdding(false);
  }

  // 回车 → 同一列的下一行；粘贴多行（从 Excel 复制一列）→ 从当前格往下依次填
  function onKeyDown(e: React.KeyboardEvent<HTMLInputElement>, idx: number, code: string) {
    if (e.key === "Enter") {
      e.preventDefault();
      const next = rows[idx + 1];
      if (next) inputs.current[cellKey(next, code)]?.focus();
    }
  }
  function onPaste(e: React.ClipboardEvent<HTMLInputElement>, idx: number, code: string) {
    const text = e.clipboardData.getData("text");
    const parts = text.split(/\r?\n/).map((t) => t.trim()).filter((t) => t !== "");
    if (parts.length <= 1) return;
    e.preventDefault();
    setDraft((prev) => {
      const next = { ...prev };
      parts.forEach((t, i) => {
        const r = rows[idx + i];
        if (!r) return;
        const k = rowKey(r);
        next[k] = { ...(next[k] ?? {}), values: { ...((next[k] ?? {}).values ?? {}), [code]: t.replace(/[^\d.\-]/g, "") } };
      });
      return next;
    });
  }

  const canWrite = !!user && (user.is_system || user.roles.length > 0);
  const sheet = sheetQ.data;
  const inputCls = "rounded-md border px-2 py-1 text-sm focus:outline-none";

  return (
    <section className="rounded-lg border border-slate-200 bg-white">
      <div className="flex flex-wrap items-center gap-3 border-b border-slate-100 px-5 py-2.5">
        <span className="text-sm font-semibold">取样日期</span>
        <span className="flex items-center gap-1">
          <button onClick={() => setDate((d) => shiftDate(d, -1))} className="rounded border border-slate-200 px-1.5 py-0.5 text-xs text-slate-500 hover:bg-slate-50" title="前一天">
            ‹
          </button>
          <input
            type="date"
            value={date}
            max={today()}
            onChange={(e) => e.target.value && setDate(e.target.value)}
            className="rounded-md border border-slate-300 px-2 py-1 text-sm text-slate-800 focus:border-blue-500 focus:outline-none"
          />
          <button onClick={() => setDate((d) => (d < today() ? shiftDate(d, 1) : d))} className="rounded border border-slate-200 px-1.5 py-0.5 text-xs text-slate-500 hover:bg-slate-50" title="后一天">
            ›
          </button>
          {date !== today() && (
            <button onClick={() => setDate(today())} className="rounded border border-slate-200 px-1.5 py-0.5 text-xs text-slate-500 hover:bg-slate-50">
              今天
            </button>
          )}
        </span>
        {sheet && (
          <span className="text-xs text-slate-400">
            {sheet.registry_used ? "样品清单来自批号登记系统，并已合并仪器实测样品" : "样品清单来自仪器实测（Nova / Vi-CELL）"}
            {" · 取样时刻自动取自仪器记录，可改 · 葡萄糖当天做了生化分析就用仪器值，只有没做的才填"}
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
                  <button onClick={restoreRemoved} className="text-blue-600 underline">恢复</button>。
                </>
              ) : (
                "批号登记系统里这天没有该取样的样品，仪器上也没有实测记录；可用下面的「添加一行」录临时样品。"
              )}
            </div>
          )}
          {rows.length > 0 && (
            <div className="overflow-x-auto p-4">
              <table className="w-full text-sm">
                <thead>
                  <tr className="whitespace-nowrap border-b border-slate-200 text-left text-xs text-slate-500">
                    <th className="px-2 py-1.5">#</th>
                    <th className="px-2 py-1.5">项目</th>
                    <th className="px-2 py-1.5">批号</th>
                    <th className="px-2 py-1.5">罐 / 阶段</th>
                    <th className="px-2 py-1.5 text-right">培养天</th>
                    <th className="w-full px-2 py-1.5">样品名</th>
                    <th className="px-2 py-1.5">取样时刻</th>
                    <th className="px-2 py-1.5">来源</th>
                    {metrics.map((m) => (
                      <th key={m.code} className="px-2 py-1.5" title={`合理范围 ${m.min}–${m.max} ${m.unit}`}>
                        {m.name} ({m.unit})
                      </th>
                    ))}
                    <th className="px-2 py-1.5">录入人 / 时间</th>
                    <th className="px-2 py-1.5"></th>
                  </tr>
                </thead>
                <tbody>
                  {rows.map((r, i) => {
                    const k = rowKey(r);
                    const e = effective(r);
                    const timeBad = e.time !== "" && !TIME_RE.test(e.time);
                    const isResample = /-T\d+$/.test(r.sample_name);
                    const last = lastEntry(r);
                    return (
                      <tr key={k} className={`whitespace-nowrap border-b border-slate-100 text-slate-700 ${isResample ? "bg-slate-50/60" : ""}`}>
                        <td className="px-2 py-1 text-xs text-slate-400">{i + 1}</td>
                        <td className="px-2 py-1">{isResample ? "" : r.project_id ?? "—"}</td>
                        <td className="px-2 py-1">{isResample ? "" : r.batch_number ?? "—"}</td>
                        <td className="px-2 py-1 font-medium">{isResample ? <span className="text-xs text-slate-400">↳ 再次取样</span> : r.bioreactor_id ?? "—"}</td>
                        <td className="px-2 py-1 text-right">{r.culture_day}</td>
                        <td className="w-full px-2 py-1">
                          <input
                            type="text"
                            value={e.name}
                            disabled={!canWrite}
                            onChange={(ev) => setField(k, "name", ev.target.value)}
                            title={r.sample_ids ? `仪器上的样本名：${r.sample_ids}` : "样品名可改，如加 -T1 尾缀"}
                            className={`${inputCls} w-full min-w-[13rem] font-mono text-xs ${draft[k]?.name != null && draft[k]?.name !== r.sample_name ? "border-blue-400 bg-blue-50" : "border-slate-200 text-slate-600 focus:border-blue-500"}`}
                          />
                        </td>
                        <td className="px-2 py-1">
                          <input
                            type="text"
                            inputMode="numeric"
                            value={e.time}
                            placeholder="HH:MM"
                            disabled={!canWrite}
                            onChange={(ev) => setField(k, "time", ev.target.value)}
                            className={`${inputCls} w-20 text-center tabular-nums ${timeBad ? "border-red-400 bg-red-50" : draft[k]?.time != null && draft[k]?.time !== (r.sample_time ?? "") ? "border-blue-400 bg-blue-50" : "border-slate-200 focus:border-blue-500"}`}
                          />
                        </td>
                        <td className="px-2 py-1">
                          <span className="flex gap-1 whitespace-nowrap">
                            {r.planned && <Badge cls="bg-blue-50 text-blue-700">计划</Badge>}
                            {r.has_nova && <Badge cls="bg-sky-50 text-sky-700">生化</Badge>}
                            {r.has_vicell && <Badge cls="bg-emerald-50 text-emerald-700">细胞</Badge>}
                            {r.kind === "extra" && <Badge cls="bg-amber-50 text-amber-700">临时</Badge>}
                          </span>
                        </td>
                        {metrics.map((m) => {
                          const raw = cellValue(r, m.code);
                          const v = raw.trim() === "" ? null : Number(raw);
                          const bad = v != null && (!Number.isFinite(v) || v < m.min || v > m.max);
                          const cur = r.entries?.[m.code]?.value ?? null;
                          const changed = v != null && Number.isFinite(v) && (cur == null || Math.abs(cur - v) >= 1e-9);
                          // 葡萄糖：当天做了生化分析就以仪器值为准，这里只灰字提示，格子仍可填
                          const instrument = m.code === "gluc" ? r.nova_gluc : null;
                          return (
                            <td key={m.code} className="px-2 py-1 align-top">
                              <input
                                ref={(el) => {
                                  inputs.current[cellKey(r, m.code)] = el;
                                }}
                                type="text"
                                inputMode="decimal"
                                value={raw}
                                placeholder={instrument != null ? "仪器已测" : cur != null ? "改数在此填新值" : "填数值"}
                                disabled={!canWrite}
                                onChange={(ev) => setValue(k, m.code, ev.target.value)}
                                onKeyDown={(ev) => onKeyDown(ev, i, m.code)}
                                onPaste={(ev) => onPaste(ev, i, m.code)}
                                className={`${inputCls} w-32 text-right tabular-nums ${
                                  bad
                                    ? "border-red-400 bg-red-50 text-red-700"
                                    : changed
                                      ? "border-blue-400 bg-blue-50"
                                      : instrument != null
                                        ? "border-slate-200 bg-slate-50 focus:border-blue-500"
                                        : "border-slate-300 focus:border-blue-500"
                                }`}
                              />
                              <div className="px-1 pt-0.5 text-[10px] leading-tight text-slate-400">
                                {instrument != null ? (
                                  <span title="生化分析仪当天实测值，曲线和数据表以它为准">仪器 {instrument.toFixed(m.digits)}</span>
                                ) : cur != null ? (
                                  <span title="已录入的最新值">已录 {cur.toFixed(m.digits)}</span>
                                ) : (
                                  ""
                                )}
                              </div>
                            </td>
                          );
                        })}
                        <td className="whitespace-nowrap px-2 py-1 align-top text-xs text-slate-400">
                          {last ? `${last.entered_by_name || last.entered_by} · ${fmtEnteredAt(last.entered_at)}` : ""}
                        </td>
                        <td className="whitespace-nowrap px-2 py-1 align-top">
                          <button
                            onClick={() => addResample(r)}
                            title="这个样品当天再加一次取样（样品名自动接 -T1 / -T2）"
                            className="rounded px-1.5 py-0.5 text-xs text-slate-400 hover:bg-blue-50 hover:text-blue-600"
                          >
                            ＋
                          </button>
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
              disabled={!canWrite || pending.length === 0 || problems.length > 0 || saveM.isPending}
              className="rounded-md bg-blue-600 px-4 py-1.5 text-sm text-white transition hover:bg-blue-700 disabled:opacity-40"
            >
              {saveM.isPending ? "保存中…" : `保存${pending.length ? `（${pending.length} 条）` : ""}`}
            </button>
            {!adding ? (
              <button onClick={() => setAdding(true)} className="rounded-md border border-slate-300 px-3 py-1.5 text-sm text-slate-600 transition hover:bg-slate-50">
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
                <button onClick={addRow} disabled={!addKey.trim() || addDay === ""} className="rounded-md bg-slate-700 px-3 py-1 text-sm text-white disabled:opacity-40">
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
            {problems.length > 0 && <span className="text-xs text-red-600">{problems[0]}{problems.length > 1 ? ` 等 ${problems.length} 处` : ""}</span>}
            {message && <span className="text-xs text-slate-600">{message}</span>}
            <span className="ml-auto text-xs text-slate-400">回车跳同一列下一行 · 可从 Excel 复制一列直接粘贴 · 每行「＋」= 再加一次取样</span>
          </div>
        </>
      )}
    </section>
  );
}

function Badge({ cls, children }: { cls: string; children: React.ReactNode }) {
  return <span className={`rounded px-1 py-0.5 text-[10px] ${cls}`}>{children}</span>;
}
