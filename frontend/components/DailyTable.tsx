"use client";

// 数据表板块：把选中批次的三源数据按「批次 × 培养天」合并成一张宽表，
// 列的分组与命名对齐《项目第一表》（Cell Culture Sciences Raw_Data），
// 方便习惯看 Excel 的同事直接读数 / 导出 CSV 回 Excel。
import { useMemo } from "react";
import type { DailyTableRow, OverviewBatch } from "@/lib/api";
import { useAuth } from "@/components/AuthGate";

// 允许导出 CSV 的角色（负责人 2026-08-17 定：仅上游经理；SYS_ADMIN 是 MDM 规范超管）
const EXPORT_ROLES = new Set(["SYS_ADMIN", "CMC_USP_MANAGER"]);

// 列定义：key 对齐后端返回字段；label/unit 给表头；digits 控制小数位
interface Col {
  key: keyof DailyTableRow;
  label: string;
  unit?: string;
  digits: number;
}

// 三个来源的列分组（表头第一行），配色与曲线板块徽标一致
const PROC_COLS: Col[] = [
  { key: "ph_mean", label: "pH在线", digits: 2 },
  { key: "do_pct_mean", label: "溶氧均值", unit: "%", digits: 1 },
  { key: "do_pct_min", label: "溶氧最低", unit: "%", digits: 1 },
  { key: "temp_c_mean", label: "温度", unit: "°C", digits: 1 },
  { key: "stirrer_rpm_mean", label: "搅拌", unit: "rpm", digits: 0 },
  { key: "air_mlmin_mean", label: "空气流量", unit: "ml/min", digits: 1 },
  { key: "o2_mlmin_mean", label: "O₂流量", unit: "ml/min", digits: 1 },
  { key: "co2_mlmin_mean", label: "CO₂流量", unit: "ml/min", digits: 1 },
  { key: "alkali_cum_ml", label: "加碱累计", unit: "ml", digits: 1 },
  { key: "acid_cum_ml", label: "加酸累计", unit: "ml", digits: 1 },
];
const CELL_COLS: Col[] = [
  { key: "density_tcd", label: "总密度TCD", unit: "×10⁶/ml", digits: 2 },
  { key: "density_vcd", label: "活密度VCD", unit: "×10⁶/ml", digits: 2 },
  { key: "viability_pct", label: "活率", unit: "%", digits: 1 },
  { key: "avg_diameter_um", label: "直径", unit: "µm", digits: 1 },
];
const NOVA_COLS: Col[] = [
  { key: "gluc", label: "葡萄糖", unit: "g/L", digits: 2 },
  { key: "lac", label: "乳酸", unit: "g/L", digits: 2 },
  { key: "gln", label: "谷氨酰胺", unit: "mmol/L", digits: 2 },
  { key: "glu", label: "谷氨酸", unit: "mmol/L", digits: 2 },
  { key: "nh4", label: "氨", unit: "mmol/L", digits: 2 },
  { key: "na", label: "钠", unit: "mmol/L", digits: 1 },
  { key: "k", label: "钾", unit: "mmol/L", digits: 2 },
  { key: "ca", label: "钙", unit: "mmol/L", digits: 2 },
  { key: "ph_nova", label: "pH离线", digits: 3 },
  { key: "po2", label: "pO₂", unit: "mmHg", digits: 1 },
  { key: "pco2", label: "pCO₂", unit: "mmHg", digits: 1 },
];
const METRIC_COLS = [...PROC_COLS, ...CELL_COLS, ...NOVA_COLS];

const fmt = (v: number | null, digits: number) =>
  v == null ? "" : v.toFixed(digits);

// 解析状态是否有问题（非 ok 就标黄提醒，如 suspect / unparseable / non_standard）
const statusBad = (s: string | null) =>
  !!s && s.split(",").some((x) => x.trim() !== "ok");

// 来源徽标（细胞/生化/工艺），配色与曲线板块一致
function SourceBadges({ r }: { r: DailyTableRow }) {
  return (
    <span className="flex gap-1">
      {r.n_vicell > 0 && (
        <span className="rounded bg-emerald-50 px-1 py-0.5 text-[10px] text-emerald-700">
          细胞
        </span>
      )}
      {r.n_nova > 0 && (
        <span className="rounded bg-sky-50 px-1 py-0.5 text-[10px] text-sky-700">
          生化
        </span>
      )}
      {r.has_process && (
        <span className="rounded bg-violet-50 px-1 py-0.5 text-[10px] text-violet-700">
          工艺
        </span>
      )}
    </span>
  );
}

// 原始样本名单元格：仪器上录入的名字，解析可疑时标黄 + ⚠
function SampleIdCell({ r }: { r: DailyTableRow }) {
  const parts: { text: string; bad: boolean }[] = [];
  if (r.vicell_sample_ids)
    parts.push({ text: r.vicell_sample_ids, bad: statusBad(r.vicell_status) });
  if (r.nova_sample_ids)
    parts.push({ text: r.nova_sample_ids, bad: statusBad(r.nova_status) });
  if (!parts.length)
    return <span className="text-slate-300">（来自工艺批次名）</span>;
  return (
    <span className="flex flex-col">
      {parts.map((p, i) => (
        <span
          key={i}
          title={p.text + (p.bad ? "（样本名不规范，解析结果存疑）" : "")}
          className={`max-w-56 truncate ${p.bad ? "text-amber-600" : ""}`}
        >
          {p.bad && "⚠ "}
          {p.text}
        </span>
      ))}
    </span>
  );
}

export function DailyTable({
  rows,
  batches,
  loading,
}: {
  rows: DailyTableRow[];
  batches: OverviewBatch[]; // 选中批次的元信息（项目/批号/罐号按 batch_key 补进行首）
  loading: boolean;
}) {
  const metaByKey = useMemo(() => {
    const m = new Map<string, OverviewBatch>();
    batches.forEach((b) => m.set(b.batch_key, b));
    return m;
  }, [batches]);

  // 导出权限：仅上游经理/超管可见导出按钮（本地开放模式不限）
  const { user } = useAuth();
  const canExport =
    !!user && (user.is_system || user.roles.some((r) => EXPORT_ROLES.has(r)));

  // 导出 CSV（Excel 直接能开；加 BOM 防中文乱码）
  function exportCsv() {
    const head = [
      "source",
      "raw_sample_ids",
      "parse_status",
      "sample_date",
      "project_id",
      "batch_number",
      "bioreactor_id",
      "batch_key",
      "culture_day",
      ...METRIC_COLS.map((c) => c.key as string),
    ];
    // 样本名里可能有逗号/引号，CSV 字段统一转义
    const esc = (v: string | number) => {
      const s = String(v);
      return /[",\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
    };
    const lines = [head.join(",")];
    rows.forEach((r) => {
      const b = metaByKey.get(r.batch_key);
      const src = [
        r.n_vicell > 0 ? "细胞" : "",
        r.n_nova > 0 ? "生化" : "",
        r.has_process ? "工艺" : "",
      ]
        .filter(Boolean)
        .join("+");
      const rawIds = [r.vicell_sample_ids, r.nova_sample_ids]
        .filter(Boolean)
        .join(" ｜ ");
      const status = [r.vicell_status, r.nova_status].filter(Boolean).join(",");
      lines.push(
        [
          src,
          esc(rawIds),
          esc(status),
          r.sample_date ?? "",
          b?.project_id ?? "",
          b?.batch_number ?? "",
          b?.bioreactor_id ?? "",
          r.batch_key,
          r.culture_day ?? "",
          ...METRIC_COLS.map((c) => r[c.key] ?? ""),
        ].join(",")
      );
    });
    const blob = new Blob(["﻿" + lines.join("\n")], {
      type: "text/csv;charset=utf-8",
    });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `批次数据表_${new Date().toISOString().slice(0, 10)}.csv`;
    a.click();
    URL.revokeObjectURL(url);
  }

  if (!rows.length) {
    return (
      <div className="flex h-40 items-center justify-center text-sm text-slate-400">
        {loading ? "加载数据表中…" : "所选批次没有可列表的数据"}
      </div>
    );
  }

  return (
    <div>
      <div className="flex items-center justify-between px-4 pt-3">
        <span className="text-xs text-slate-400">
          共 {rows.length} 行 · 同天多次取样已平均 · 空格 = 该源当天无数据 ·
          项目/批号/罐号拆自「原始样本名」，
          <span className="text-amber-600">⚠ 黄色</span>
          = 样本名不规范、解析存疑（错在录入还是解析，看原始样本名即可判断）
        </span>
        {canExport ? (
          <button
            onClick={exportCsv}
            className="rounded border border-slate-200 px-2 py-1 text-xs text-slate-600 transition hover:bg-slate-50"
          >
            ⬇ 导出 CSV（Excel 可开）
          </button>
        ) : (
          <span className="text-xs text-slate-300">导出功能仅限上游经理</span>
        )}
      </div>
      <div className="max-h-[32rem] overflow-auto p-4 pt-2">
        <table className="w-full whitespace-nowrap text-right text-xs">
          <thead className="sticky top-0 z-10 bg-white">
            {/* 第一行：来源分组 */}
            <tr className="text-[11px]">
              <th colSpan={7} className="px-2 pb-0.5 text-left font-normal text-slate-400">
                批次 / 时间 / 溯源
              </th>
              <th
                colSpan={PROC_COLS.length}
                className="border-l border-violet-200 px-2 pb-0.5 text-left font-medium text-violet-600"
              >
                工艺（Lucullus 日均）
              </th>
              <th
                colSpan={CELL_COLS.length}
                className="border-l border-emerald-200 px-2 pb-0.5 text-left font-medium text-emerald-600"
              >
                细胞（Vi-CELL）
              </th>
              <th
                colSpan={NOVA_COLS.length}
                className="border-l border-sky-200 px-2 pb-0.5 text-left font-medium text-sky-600"
              >
                生化（Nova FLEX2）
              </th>
            </tr>
            {/* 第二行：列名 + 单位 */}
            <tr className="border-b border-slate-200 text-slate-500">
              <th className="px-2 py-1.5 text-left">来源</th>
              <th className="px-2 py-1.5 text-left">原始样本名（仪器录入）</th>
              <th className="px-2 py-1.5 text-left">取样日期</th>
              <th className="px-2 py-1.5 text-left">项目</th>
              <th className="px-2 py-1.5 text-left">批号</th>
              <th className="px-2 py-1.5 text-left">罐号</th>
              <th className="px-2 py-1.5">培养天</th>
              {METRIC_COLS.map((c, i) => (
                <th
                  key={c.key}
                  className={`px-2 py-1.5 ${
                    i === 0 || i === PROC_COLS.length || i === PROC_COLS.length + CELL_COLS.length
                      ? "border-l border-slate-200"
                      : ""
                  }`}
                >
                  {c.label}
                  {c.unit && (
                    <span className="block font-normal text-slate-400">{c.unit}</span>
                  )}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((r, ri) => {
              const b = metaByKey.get(r.batch_key);
              // 同批次第一行加粗上边框，视觉上把批次分组
              const firstOfBatch = ri === 0 || rows[ri - 1].batch_key !== r.batch_key;
              return (
                <tr
                  key={`${r.batch_key}_${r.culture_day}`}
                  className={`text-slate-700 ${
                    firstOfBatch ? "border-t-2 border-slate-200" : "border-t border-slate-100"
                  }`}
                >
                  <td className="px-2 py-1 text-left">
                    <SourceBadges r={r} />
                  </td>
                  <td className="px-2 py-1 text-left">
                    <SampleIdCell r={r} />
                  </td>
                  <td className="px-2 py-1 text-left">{r.sample_date ?? ""}</td>
                  <td className="px-2 py-1 text-left">{b?.project_id ?? ""}</td>
                  <td className="px-2 py-1 text-left">{b?.batch_number ?? ""}</td>
                  <td className="px-2 py-1 text-left">{b?.bioreactor_id ?? ""}</td>
                  <td className="px-2 py-1 font-medium">{r.culture_day ?? ""}</td>
                  {METRIC_COLS.map((c, i) => (
                    <td
                      key={c.key}
                      className={`px-2 py-1 ${
                        i === 0 || i === PROC_COLS.length || i === PROC_COLS.length + CELL_COLS.length
                          ? "border-l border-slate-100"
                          : ""
                      }`}
                    >
                      {fmt(r[c.key] as number | null, c.digits)}
                    </td>
                  ))}
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
