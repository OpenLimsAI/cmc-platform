"use client"
// 检验概况页：KPI 卡片 + 月度趋势图 + 项目分布饼图（对应 Streamlit View 1）
export const dynamic = "force-dynamic"
import { useState } from "react"
import { useQuery } from "@tanstack/react-query"
import { useSearchParams } from "next/navigation"
import { fetchKPI, fetchMonthlyTrend, fetchProjectDistribution, fetchMethodDistribution, ProjectDistributionItem } from "@/lib/api"
import { KpiCards } from "@/components/kpi-cards"
import { MonthlyTrendChart } from "@/components/monthly-trend-chart"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import ReactECharts from "echarts-for-react"
import dayjs from "dayjs"

type Metric = "sample_n" | "test_n" | "std_hours"

const METRIC_OPTIONS: { value: Metric; label: string }[] = [
  { value: "sample_n",  label: "样品数" },
  { value: "test_n",    label: "检项数" },
  { value: "std_hours", label: "标准工时" },
]

const THRESHOLD_OPTIONS = [
  { value: 0,    label: "不合并" },
  { value: 0.01, label: "< 1%" },
  { value: 0.02, label: "< 2%" },
  { value: 0.05, label: "< 5%" },
]

function buildPieOption(items: ProjectDistributionItem[], metric: Metric, threshold: number, showPercent: boolean) {
  const metricLabel = METRIC_OPTIONS.find((m) => m.value === metric)!.label

  const total = items.reduce((s, i) => s + Number(i[metric]), 0)
  if (total === 0) return null

  // 按阈值合并小分项
  const above: { name: string; value: number }[] = []
  let othersVal = 0
  for (const item of items) {
    const val = Number(item[metric])
    if (threshold > 0 && val / total < threshold) {
      othersVal += val
    } else {
      above.push({ name: item.project_id, value: val })
    }
  }
  if (othersVal > 0) {
    above.push({ name: "其他", value: othersVal })
  }
  // 扇区按值降序排，配色与表格顺序一致
  above.sort((a, b) => b.value - a.value)

  return {
    tooltip: {
      trigger: "item",
      formatter: (p: { name: string; value: number; percent: number }) =>
        `${p.name}<br/>${metricLabel}：${metric === "std_hours" ? p.value.toFixed(1) + " h" : p.value.toLocaleString()}<br/>占比：${p.percent.toFixed(1)}%`,
    },
    legend: {
      orient: "vertical",
      right: 10,
      top: "center",
      textStyle: { fontSize: 12 },
    },
    series: [
      {
        type: "pie",
        radius: ["38%", "68%"],
        center: ["40%", "50%"],
        data: above,
        label: {
          show: showPercent,
          formatter: (p: { name: string; percent: number }) => `${p.name}  ${p.percent.toFixed(1)}%`,
          fontSize: 12,
          color: "#374151",
        },
        labelLine: { length: 14, length2: 20 },
        emphasis: { label: { show: true, fontSize: 14, fontWeight: "bold" } },
      },
    ],
  }
}

export default function OverviewPage() {
  const searchParams = useSearchParams()
  const groups = searchParams.getAll("groups")
  const [metric, setMetric] = useState<Metric>("sample_n")
  const [threshold, setThreshold] = useState(0.01)
  const [showPercent, setShowPercent] = useState(true)
  const [methodThreshold, setMethodThreshold] = useState(10)

  const today = dayjs().format("YYYY-MM-DD")
  const startDate = searchParams.get("start_date") ?? dayjs().subtract(30, "day").format("YYYY-MM-DD")
  const endDate = searchParams.get("end_date") ?? today

  const kpiQuery = useQuery({
    queryKey: ["kpi", startDate, endDate, groups],
    queryFn: () => fetchKPI({ start_date: startDate, end_date: endDate, groups: groups.length ? groups : undefined }),
  })

  const trendQuery = useQuery({
    queryKey: ["monthly-trend", 12, groups],
    queryFn: () => fetchMonthlyTrend({ months: 12, groups: groups.length ? groups : undefined }),
  })

  const projectQuery = useQuery({
    queryKey: ["project-distribution", startDate, endDate, groups],
    queryFn: () => fetchProjectDistribution({ start_date: startDate, end_date: endDate, groups: groups.length ? groups : undefined }),
  })

  const methodQuery = useQuery({
    queryKey: ["method-distribution", startDate, endDate, groups],
    queryFn: () => fetchMethodDistribution({ start_date: startDate, end_date: endDate, groups: groups.length ? groups : undefined }),
  })

  const pieOption = projectQuery.data
    ? buildPieOption(projectQuery.data.items, metric, threshold, showPercent)
    : null

  const total = projectQuery.data
    ? projectQuery.data.items.reduce((s, i) => s + Number(i[metric]), 0)
    : 0

  const totalLabel = metric === "std_hours" ? total.toFixed(1) + " h" : total.toLocaleString()

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-semibold text-gray-900">检验基本情况汇总</h1>
        <p className="text-sm text-gray-500 mt-1">
          KPI 区间：{startDate} ~ {endDate}
          {groups.length > 0 && <span className="ml-2 text-blue-600">· 已筛选 {groups.join("、")}</span>}
        </p>
      </div>

      {kpiQuery.isLoading && <p className="text-sm text-gray-400">加载中…</p>}
      {kpiQuery.isError && <p className="text-sm text-red-500">数据加载失败，请确认后端服务已启动</p>}
      {kpiQuery.data && <KpiCards data={kpiQuery.data} />}

      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-sm font-medium text-gray-700">近 12 个月趋势</CardTitle>
        </CardHeader>
        <CardContent>
          {trendQuery.isLoading && <p className="text-sm text-gray-400 py-8 text-center">加载中…</p>}
          {trendQuery.data && <MonthlyTrendChart data={trendQuery.data.items} />}
        </CardContent>
      </Card>

      <Card>
        <CardHeader className="pb-2">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <CardTitle className="text-sm font-medium text-gray-700">项目分布</CardTitle>
            <div className="flex items-center gap-3">
              {/* 百分比标签开关 */}
              <label className="flex items-center gap-1.5 text-xs text-gray-500 cursor-pointer select-none">
                <input
                  type="checkbox"
                  checked={showPercent}
                  onChange={(e) => setShowPercent(e.target.checked)}
                  className="accent-indigo-600"
                />
                显示百分比
              </label>
              {/* 合并阈值 */}
              <div className="flex items-center gap-1.5 text-xs text-gray-500">
                <span className="whitespace-nowrap">合并小分项</span>
                <select
                  value={threshold}
                  onChange={(e) => setThreshold(Number(e.target.value))}
                  className="border rounded px-1.5 py-0.5 text-xs text-gray-700 bg-white focus:outline-none focus:ring-1 focus:ring-blue-400"
                >
                  {THRESHOLD_OPTIONS.map((o) => (
                    <option key={o.value} value={o.value}>{o.label}</option>
                  ))}
                </select>
              </div>
              {/* 维度切换 */}
              <div className="flex rounded border text-xs overflow-hidden">
                {METRIC_OPTIONS.map((o, idx) => (
                  <button
                    key={o.value}
                    onClick={() => setMetric(o.value)}
                    className={`px-2.5 py-1 transition-colors ${idx > 0 ? "border-l" : ""} ${
                      metric === o.value ? "bg-indigo-600 text-white" : "text-gray-500 hover:bg-gray-50"
                    }`}
                  >
                    {o.label}
                  </button>
                ))}
              </div>
            </div>
          </div>
        </CardHeader>
        <CardContent>
          {projectQuery.isLoading && <p className="text-sm text-gray-400 py-8 text-center">加载中…</p>}
          {projectQuery.data && projectQuery.data.items.length === 0 && (
            <p className="text-sm text-gray-400 py-8 text-center">暂无数据</p>
          )}
          {pieOption && projectQuery.data && (
            <>
              <ReactECharts option={pieOption} style={{ height: 480 }} />
              <p className="text-xs text-gray-400 text-center mt-1">合计 {totalLabel}</p>
              <div className="mt-4 border-t pt-3 overflow-auto">
                <table className="w-full text-xs">
                  <thead className="bg-gray-50 text-[11px] text-gray-500 uppercase">
                    <tr>
                      <th className="px-3 py-1.5 text-left w-10">#</th>
                      <th className="px-3 py-1.5 text-left">项目编号</th>
                      <th className="px-3 py-1.5 text-right w-32">{METRIC_OPTIONS.find((m) => m.value === metric)!.label}</th>
                      <th className="px-3 py-1.5 text-right w-20">占比</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y">
                    {[...projectQuery.data.items]
                      .sort((a, b) => Number(b[metric]) - Number(a[metric]))
                      .map((item, idx) => {
                        const val = Number(item[metric])
                        const pct = total > 0 ? (val / total) * 100 : 0
                        return (
                          <tr key={item.project_id} className="hover:bg-gray-50">
                            <td className="px-3 py-1.5 text-gray-400 tabular-nums">{idx + 1}</td>
                            <td className="px-3 py-1.5 font-mono text-gray-700">{item.project_id}</td>
                            <td className="px-3 py-1.5 text-right tabular-nums">
                              {metric === "std_hours" ? val.toFixed(1) + " h" : val.toLocaleString()}
                            </td>
                            <td className="px-3 py-1.5 text-right tabular-nums">{pct.toFixed(1)}%</td>
                          </tr>
                        )
                      })}
                  </tbody>
                </table>
              </div>
            </>
          )}
        </CardContent>
      </Card>
      {/* 检项分布条形图 */}
      <Card>
        <CardHeader className="pb-2">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <CardTitle className="text-sm font-medium text-gray-700">检项分布（按方法）</CardTitle>
            <div className="flex items-center gap-1.5 text-xs text-gray-500">
              <span className="whitespace-nowrap">仅显示检项数 ≥</span>
              <input
                type="number"
                min={1}
                value={methodThreshold}
                onChange={(e) => setMethodThreshold(Math.max(1, parseInt(e.target.value) || 1))}
                className="w-16 border rounded px-2 py-0.5 text-xs text-gray-700 focus:outline-none focus:ring-1 focus:ring-blue-400"
              />
            </div>
          </div>
        </CardHeader>
        <CardContent>
          {methodQuery.isLoading && <p className="text-sm text-gray-400 py-8 text-center">加载中…</p>}
          {methodQuery.data && (() => {
            const filtered = methodQuery.data.items.filter((i) => i.test_count >= methodThreshold)
            if (filtered.length === 0) return <p className="text-sm text-gray-400 py-8 text-center">无满足条件的数据</p>
            const sorted = [...filtered].sort((a, b) => a.test_count - b.test_count)
            const chartHeight = Math.max(300, sorted.length * 28)
            const option = {
              tooltip: {
                trigger: "axis",
                axisPointer: { type: "shadow" },
                formatter: (params: { name: string; value: number }[]) =>
                  `${params[0].name}<br/>检项数：<b>${params[0].value.toLocaleString()}</b>`,
              },
              grid: { left: 220, right: 60, top: 8, bottom: 20 },
              xAxis: { type: "value", name: "检项数", axisLabel: { fontSize: 11 } },
              yAxis: {
                type: "category",
                data: sorted.map((i) => i.method_name),
                axisLabel: {
                  fontSize: 11,
                  width: 200,
                  overflow: "truncate",
                },
              },
              series: [{
                type: "bar",
                data: sorted.map((i) => i.test_count),
                itemStyle: { color: "#6366f1", borderRadius: [0, 3, 3, 0] },
                label: { show: true, position: "right", fontSize: 11, formatter: "{c}" },
              }],
            }
            return <ReactECharts option={option} style={{ height: chartHeight }} />
          })()}
        </CardContent>
      </Card>

      {/* 数据导出（对应原版 Streamlit 导出区块） */}
      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-sm font-medium text-gray-700">数据导出</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex flex-wrap gap-3">
            <a
              href={`${process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8030"}/api/v1/lims/stats/pending-tests-csv${groups.length ? "?" + groups.map((g) => `groups=${encodeURIComponent(g)}`).join("&") : ""}`}
              download
              className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-indigo-600 text-white text-xs font-medium rounded hover:bg-indigo-700 transition-colors"
            >
              导出 待检测检项.csv
            </a>
            <span className="text-xs text-gray-400 self-center">（口径：test_authorised_dt IS NULL，排除 X/U）</span>
          </div>
        </CardContent>
      </Card>
    </div>
  )
}
