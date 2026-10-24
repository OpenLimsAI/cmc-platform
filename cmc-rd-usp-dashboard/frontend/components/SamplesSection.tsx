"use client";

// 板块：取样记录明细——每个批次一组表（细胞 / 生化），每次取样一行，不按天平均。
import { useQueries } from "@tanstack/react-query";
import { fetchNovaSamples, fetchVicellSamples, type OverviewBatch } from "@/lib/api";
import { batchLabel, fmtDate, fmtNum } from "@/lib/batches";

export function SamplesSection({ batches }: { batches: OverviewBatch[] }) {
  const cellBatches = batches.filter((b) => b.n_vicell > 0);
  const novaBatches = batches.filter((b) => b.n_nova > 0);
  const vQs = useQueries({
    queries: cellBatches.map((b) => ({
      queryKey: ["vicell-samples", b.batch_key],
      queryFn: () => fetchVicellSamples(b.batch_key),
    })),
  });
  const nQs = useQueries({
    queries: novaBatches.map((b) => ({
      queryKey: ["nova-samples", b.batch_key],
      queryFn: () => fetchNovaSamples(b.batch_key),
    })),
  });
  const th = "px-2 py-1.5";
  const td = "px-2 py-1";

  return (
    <section className="rounded-lg border border-slate-200 bg-white">
      <div className="flex items-baseline gap-2 border-b border-slate-100 px-5 py-2.5">
        <h2 className="text-sm font-semibold">取样记录明细</h2>
        <span className="text-xs text-slate-400">每次取样一行（未按天平均）</span>
      </div>
      <div className="space-y-5 p-4">
        {batches.map((b) => {
          const vi = cellBatches.findIndex((x) => x.batch_key === b.batch_key);
          const ni = novaBatches.findIndex((x) => x.batch_key === b.batch_key);
          const vRows = vi >= 0 ? vQs[vi]?.data ?? [] : [];
          const nRows = ni >= 0 ? nQs[ni]?.data ?? [] : [];
          return (
            <div key={b.batch_key}>
              <div className="mb-1.5 text-sm font-semibold text-slate-700">{batchLabel(b)}</div>
              {vRows.length > 0 && (
                <div className="mb-3">
                  <div className="mb-1 text-xs font-medium text-emerald-700">细胞计数（Vi-CELL）</div>
                  <div className="overflow-x-auto">
                    <table className="w-full whitespace-nowrap text-right text-xs">
                      <thead>
                        <tr className="border-b border-slate-200 text-slate-500">
                          <th className={`${th} text-left`}>样本名</th>
                          <th className={th}>培养天</th>
                          <th className={th}>日期</th>
                          <th className={th}>活密度 ×10⁶/ml</th>
                          <th className={th}>活率 %</th>
                          <th className={th}>总密度 ×10⁶/ml</th>
                          <th className={th}>直径 µm</th>
                          <th className={th}>圆度</th>
                        </tr>
                      </thead>
                      <tbody>
                        {vRows.map((s) => (
                          <tr key={s.run_id} className="border-b border-slate-100 text-slate-700">
                            <td className={`${td} text-left`}>{s.sample_id ?? "—"}</td>
                            <td className={td}>{s.culture_day ?? "—"}</td>
                            <td className={td}>{fmtDate(s.run_date)}</td>
                            <td className={td}>{fmtNum(s.viable_per_ml)}</td>
                            <td className={td}>{fmtNum(s.viability_pct, 1)}</td>
                            <td className={td}>{fmtNum(s.total_per_ml)}</td>
                            <td className={td}>{fmtNum(s.avg_diameter_um, 1)}</td>
                            <td className={td}>{fmtNum(s.avg_circularity)}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              )}
              {nRows.length > 0 && (
                <div>
                  <div className="mb-1 text-xs font-medium text-sky-700">生化分析（Nova FLEX2）</div>
                  <div className="overflow-x-auto">
                    <table className="w-full whitespace-nowrap text-right text-xs">
                      <thead>
                        <tr className="border-b border-slate-200 text-slate-500">
                          <th className={`${th} text-left`}>样本名</th>
                          <th className={th}>培养天</th>
                          <th className={th}>日期</th>
                          <th className={th}>葡萄糖 g/L</th>
                          <th className={th}>乳酸 g/L</th>
                          <th className={th}>氨 mmol/L</th>
                          <th className={th}>谷氨酰胺</th>
                          <th className={th}>谷氨酸</th>
                          <th className={th}>钠</th>
                          <th className={th}>钾</th>
                          <th className={th}>钙</th>
                          <th className={th}>pH</th>
                          <th className={th}>pO₂</th>
                          <th className={th}>pCO₂</th>
                        </tr>
                      </thead>
                      <tbody>
                        {nRows.map((s) => (
                          <tr key={s.sample_result_id} className="border-b border-slate-100 text-slate-700">
                            <td className={`${td} text-left`}>{s.sample_id ?? "—"}</td>
                            <td className={td}>{s.culture_day ?? "—"}</td>
                            <td className={td}>{fmtDate(s.measured_at)}</td>
                            <td className={td}>{fmtNum(s.gluc)}</td>
                            <td className={td}>{fmtNum(s.lac)}</td>
                            <td className={td}>{fmtNum(s.nh4)}</td>
                            <td className={td}>{fmtNum(s.gln)}</td>
                            <td className={td}>{fmtNum(s.glu)}</td>
                            <td className={td}>{fmtNum(s.na, 1)}</td>
                            <td className={td}>{fmtNum(s.k)}</td>
                            <td className={td}>{fmtNum(s.ca)}</td>
                            <td className={td}>{fmtNum(s.ph, 3)}</td>
                            <td className={td}>{fmtNum(s.po2, 1)}</td>
                            <td className={td}>{fmtNum(s.pco2, 1)}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              )}
              {vRows.length === 0 && nRows.length === 0 && (
                <div className="text-xs text-slate-400">无取样记录</div>
              )}
            </div>
          );
        })}
      </div>
    </section>
  );
}
