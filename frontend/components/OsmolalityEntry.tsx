"use client";

// 板块：渗透压录入——本看板唯一会写数据库的地方（负责人 2026-09-09 定）。
// 按日期（默认今天）自动列出当天在 Nova / Vi-CELL 上跑过的全部样品（批次 / 罐 / 培养天自动带出），
// 试验员只在对应行填渗透压数值。保存 = 追加一行，改数再存即可，历史都留着。
import { useEffect, useMemo, useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { fetchDailySheet, fetchManualStatus, saveManualResults, type DailySheetRow } from "@/lib/api";
import { useAuth } from "@/components/AuthGate";

const today = () => {
  const d = new Date();
  const p = (n: number) => (n < 10 ? `0${n}` : String(n));
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}`;
};
const shiftDate = (s: string, days: number) => {
  const d = new Date(s + "T00:00:00");
  d.setDate(d.getDate() + days);
  const p = (n: number) => (n < 10 ? `0${n}` : String(n));
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}`;
};
const rowKey = (r: DailySheetRow) => `${r.batch_key}#${r.culture_day}`;

export function OsmolalityEntry() {
  const qc = useQueryClient();
  const { user } = useAuth();
  const [date, setDate] = useState(today());
  // 每行输入框里的文字（key = 批次#培养天）；只记用户改过的
  const [draft, setDraft] = useState<Record<string, string>>({});
  const [message, setMessage] = useState<string | null>(null);
  const inputs = useRef<Record<string, HTMLInputElement | null>>({});

  const statusQ = useQuery({ queryKey: ["manual-status"], queryFn: fetchManualStatus, staleTime: 5 * 60_000 });
  const sheetQ = useQuery({
    queryKey: ["daily-sheet", date],
    queryFn: () => fetchDailySheet(date),
    enabled: !!statusQ.data?.enabled,
  });

  // 换了日期就清掉未保存的草稿
  useEffect(() => {
    setDraft({});
    setMessage(null);
  }, [date]);

  const rows = useMemo(() => sheetQ.data?.rows ?? [], [sheetQ.data]);
  const metric = sheetQ.data?.metric;

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
          source_sample_ids: row.sample_ids,
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

  return (
    <section className="rounded-lg border border-slate-200 bg-white">
      <div className="flex flex-wrap items-center gap-3 border-b border-slate-100 px-5 py-2.5">
        <h2 className="text-sm font-semibold">渗透压录入</h2>
        <span className="text-xs text-slate-400">
          按日期列出当天在生化仪 / 细胞计数仪上跑过的全部样品，只需填数值 · 单位 mOsm/kg
        </span>
        <span className="ml-auto flex items-center gap-1">
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
      </div>

      {statusQ.data && !statusQ.data.enabled && (
        <div className="p-6 text-sm text-amber-600">后端未配置写库账号，暂不能录入（联系管理员）。</div>
      )}

      {statusQ.data?.enabled && (
        <>
          {sheetQ.isLoading && <div className="p-6 text-sm text-slate-400">加载当天样品中…</div>}
          {sheetQ.data && rows.length === 0 && (
            <div className="p-6 text-sm text-slate-400">
              {date} 没有在仪器上跑过的样品。渗透压只能录在当天有取样记录的样品上——请确认生化仪 / 细胞计数仪的数据已同步，或换个日期。
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
                    <th className="px-2 py-1.5">罐</th>
                    <th className="px-2 py-1.5 text-right">培养天</th>
                    <th className="px-2 py-1.5">仪器上的样本名</th>
                    <th className="px-2 py-1.5 text-right">已录值</th>
                    <th className="px-2 py-1.5">录入人 / 时间</th>
                    <th className="px-2 py-1.5">渗透压 (mOsm/kg)</th>
                  </tr>
                </thead>
                <tbody>
                  {rows.map((r, i) => {
                    const k = rowKey(r);
                    const t = draft[k] ?? "";
                    const v = t.trim() === "" ? null : Number(t);
                    const bad = v != null && metric && (!Number.isFinite(v) || v < metric.min || v > metric.max);
                    const changed = v != null && Number.isFinite(v) && (r.existing_value == null || Math.abs(r.existing_value - v) >= 1e-9);
                    return (
                      <tr key={k} className="border-b border-slate-100 text-slate-700">
                        <td className="px-2 py-1 text-xs text-slate-400">{i + 1}</td>
                        <td className="px-2 py-1">{r.project_id ?? "—"}</td>
                        <td className="px-2 py-1">{r.batch_number ?? "—"}</td>
                        <td className="px-2 py-1 font-medium">{r.bioreactor_id ?? "—"}</td>
                        <td className="px-2 py-1 text-right">{r.culture_day}</td>
                        <td className="max-w-72 truncate px-2 py-1 text-xs text-slate-500" title={r.sample_ids ?? ""}>
                          {r.sample_ids ?? "—"}
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
                      </tr>
                    );
                  })}
                </tbody>
              </table>

              <div className="mt-3 flex flex-wrap items-center gap-3">
                <button
                  onClick={() => saveM.mutate()}
                  disabled={!canWrite || pending.length === 0 || invalid.length > 0 || saveM.isPending}
                  className="rounded-md bg-blue-600 px-4 py-1.5 text-sm text-white transition hover:bg-blue-700 disabled:opacity-40"
                >
                  {saveM.isPending ? "保存中…" : `保存${pending.length ? `（${pending.length} 条）` : ""}`}
                </button>
                {invalid.length > 0 && metric && (
                  <span className="text-xs text-red-600">
                    有 {invalid.length} 个数值不在 {metric.min}–{metric.max} {metric.unit} 范围内，请检查
                  </span>
                )}
                {message && <span className="text-xs text-slate-600">{message}</span>}
                <span className="ml-auto text-xs text-slate-400">
                  回车跳下一行 · 可从 Excel 复制一列直接粘贴 · 录入人：{user?.full_name || user?.username || "—"}
                </span>
              </div>
            </div>
          )}
        </>
      )}
    </section>
  );
}
