"use client"
export const dynamic = "force-dynamic"
import { useState, useMemo } from "react"
import { useQuery } from "@tanstack/react-query"
import { useSearchParams } from "next/navigation"
import { fetchMethodMonthly, MethodMonthlyItem } from "@/lib/api"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import ReactECharts from "echarts-for-react"

const MONTH_OPTIONS = [6, 12, 18, 24]
const METRIC_OPTIONS = [
  { value: "test_n" as const, label: "检项数" },
  { value: "std_hours" as const, label: "标准工时 (h)" },
]

type Metric = "test_n" | "std_hours"

// 将扁平行列表转为 { method → { ym → value } } 的透视结构
function pivot(items: MethodMonthlyItem[], metric: Metric) {
  const months = [...new Set(items.map((i) => i.ym))].sort()
  const methodMap = new Map<string, Map<string, number>>()
  for (const item of items) {
    if (!methodMap.has(item.method_name)) methodMap.set(item.method_name, new Map())
    methodMap.get(item.method_name)!.set(item.ym, Number(item[metric]))
  }
  // 按总量降序排列方法
  const methods = [...methodMap.keys()].sort((a, b) => {
    const sumA = [...methodMap.get(a)!.values()].reduce((s, v) => s + v, 0)
    const sumB = [...methodMap.get(b)!.values()].reduce((s, v) => s + v, 0)
    return sumB - sumA
  })
  return { months, methods, methodMap }
}

export default function MonthlyPage() {
  const searchParams = useSearchParams()
  const groups = searchParams.getAll("groups")

  const [trendMonths, setTrendMonths] = useState(12)
  const [metric, setMetric] = useState<Metric>("test_n")
  const [topN, setTopN] = useState(10)

  const { data, isLoading, isError } = useQuery({
    queryKey: ["method-monthly", trendMonths, groups],
    queryFn: () => fetchMethodMonthly({ months: trendMonths, groups: groups.length ? groups : undefined }),
  })

  const { months, methods, methodMap } = useMemo(
    () => (data ? pivot(data.items, metric) : { months: [], methods: [], methodMap: new Map() }),
    [data, metric]
  )

  const displayMethods = methods.slice(0, topN)

  const totalTests = data ? data.items.reduce((s, i) => s + i.test_n, 0) : 0
  const totalHours = data ? data.items.reduce((s, i) => s + i.std_hours, 0) : 0

  // ECharts stacked bar option
  const chartOption = useMemo(() => {
    if (!months.length || !displayMethods.length) return null
    return {
      tooltip: {
        trigger: "axis",
        axisPointer: { type: "shadow" },
      },
      legend: {
        bottom: 0,
        type: "scroll",
        textStyle: { fontSize: 10 },
      },
      grid: { left: 60, right: 20, top: 20, bottom: 80 },
      xAxis: {
        type: "category",
        data: months,
        axisLabel: { fontSize: 11, rotate: months.length > 12 ? 30 : 0 },
      },
      yAxis: {
        type: "value",
        name: metric === "test_n" ? "检项数" : "工时 (h)",
        axisLabel: { fontSize: 11 },
      },
      series: displayMethods.map((method) => ({
        name: method,
        type: "bar",
        stack: "total",
        data: months.map((ym) => {
          const v = methodMap.get(method)?.get(ym) ?? 0
          return metric === "std_hours" ? parseFloat(v.toFixed(1)) : v
        }),
        emphasis: { focus: "series" },
      })),
    }
  }, [months, displayMethods, methodMap, metric])

  const chartHeight = Math.max(320, Math.min(500, displayMethods.length * 18 + 120))

  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-xl font-semibold text-gray-900">方法月度报表</h1>
        <p className="text-sm text-gray-500 mt-1">
          统计口径：完结（已授权）检项，近 {trendMonths} 个月
          {groups.length > 0 && <span className="ml-2 text-blue-600">· 已筛选 {groups.join("、")}</span>}
        </p>
      </div>

      {/* 控制栏 */}
      <Card>
        <CardContent className="pt-4 pb-3">
          <div className="flex flex-wrap gap-4 items-center">
            {/* 月数选择 */}
            <div className="flex items-center gap-2 text-xs text-gray-600">
              <span className="whitespace-nowrap font-medium">统计月数</span>
              <div className="flex rounded border text-xs overflow-hidden">
                {MONTH_OPTIONS.map((m, idx) => (
                  <button
                    key={m}
                    onClick={() => setTrendMonths(m)}
                    className={`px-3 py-1.5 transition-colors ${idx > 0 ? "border-l" : ""} ${
                      trendMonths === m ? "bg-indigo-600 text-white" : "text-gray-500 hover:bg-gray-50"
                    }`}
                  >
                    {m}M
                  </button>
                ))}
              </div>
            </div>

            {/* 指标切换 */}
            <div className="flex items-center gap-2 text-xs text-gray-600">
              <span className="whitespace-nowrap font-medium">统计指标</span>
              <div className="flex rounded border text-xs overflow-hidden">
                {METRIC_OPTIONS.map((o, idx) => (
                  <button
                    key={o.value}
                    onClick={() => setMetric(o.value)}
                    className={`px-3 py-1.5 transition-colors ${idx > 0 ? "border-l" : ""} ${
                      metric === o.value ? "bg-indigo-600 text-white" : "text-gray-500 hover:bg-gray-50"
                    }`}
                  >
                    {o.label}
                  </button>
                ))}
              </div>
            </div>

            {/* Top N */}
            <div className="flex items-center gap-1.5 text-xs text-gray-600">
              <span className="whitespace-nowrap font-medium">显示前</span>
              <input
                type="number"
                min={1}
                max={50}
                value={topN}
                onChange={(e) => setTopN(Math.max(1, Math.min(50, parseInt(e.target.value) || 10)))}
                className="w-14 border rounded px-2 py-0.5 text-xs text-gray-700 focus:outline-none focus:ring-1 focus:ring-blue-400"
              />
              <span>个方法</span>
            </div>

            {/* 汇总数据 */}
            {data && (
              <div className="ml-auto text-xs text-gray-400 space-x-3">
                <span>合计检项：<strong className="text-gray-700">{totalTests.toLocaleString()}</strong></span>
                <span>合计工时：<strong className="text-gray-700">{totalHours.toFixed(1)} h</strong></span>
              </div>
            )}
          </div>
        </CardContent>
      </Card>

      {isLoading && <p className="text-sm text-gray-400 py-8 text-center">加载中…</p>}
      {isError && <p className="text-sm text-red-500 py-8 text-center">数据加载失败</p>}

      {/* 堆叠柱状图 */}
      {chartOption && (
        <Card>
          <CardHeader className="pb-1">
            <CardTitle className="text-sm font-medium text-gray-700">
              月度{metric === "test_n" ? "检项数" : "标准工时"}堆叠图（前 {topN} 个方法）
            </CardTitle>
          </CardHeader>
          <CardContent>
            <ReactECharts option={chartOption} style={{ height: chartHeight }} />
          </CardContent>
        </Card>
      )}

      {/* 透视表 */}
      {data && months.length > 0 && displayMethods.length > 0 && (
        <Card>
          <CardHeader className="pb-1">
            <CardTitle className="text-sm font-medium text-gray-700">
              明细透视表（前 {topN} 个方法 × 月份）
            </CardTitle>
          </CardHeader>
          <CardContent className="px-0 pb-4">
            <div className="overflow-x-auto">
              <table className="w-full text-xs border-collapse">
                <thead>
                  <tr className="border-b bg-gray-50 text-gray-500">
                    <th className="px-4 py-2 text-left font-medium sticky left-0 bg-gray-50 whitespace-nowrap min-w-[160px]">
                      方法名称
                    </th>
                    {months.map((ym) => (
                      <th key={ym} className="px-3 py-2 text-right font-medium whitespace-nowrap">
                        {ym}
                      </th>
                    ))}
                    <th className="px-3 py-2 text-right font-medium whitespace-nowrap bg-gray-100">合计</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-100">
                  {displayMethods.map((method) => {
                    const row = methodMap.get(method)!
                    const total = [...row.values()].reduce((s, v) => s + v, 0)
                    return (
                      <tr key={method} className="hover:bg-gray-50 transition-colors">
                        <td className="px-4 py-2 text-gray-700 sticky left-0 bg-white font-medium whitespace-nowrap max-w-[200px] truncate" title={method}>
                          {method}
                        </td>
                        {months.map((ym) => {
                          const v = row.get(ym) ?? 0
                          return (
                            <td key={ym} className={`px-3 py-2 text-right whitespace-nowrap ${v > 0 ? "text-gray-700" : "text-gray-300"}`}>
                              {v > 0
                                ? metric === "std_hours"
                                  ? v.toFixed(1)
                                  : v.toLocaleString()
                                : "—"}
                            </td>
                          )
                        })}
                        <td className="px-3 py-2 text-right font-medium text-indigo-700 bg-indigo-50 whitespace-nowrap">
                          {metric === "std_hours" ? total.toFixed(1) : total.toLocaleString()}
                        </td>
                      </tr>
                    )
                  })}
                  {/* 合计行 */}
                  <tr className="border-t-2 border-gray-300 bg-gray-50 font-semibold text-gray-600">
                    <td className="px-4 py-2 sticky left-0 bg-gray-50">月度合计</td>
                    {months.map((ym) => {
                      const sum = displayMethods.reduce((s, m) => s + (methodMap.get(m)?.get(ym) ?? 0), 0)
                      return (
                        <td key={ym} className="px-3 py-2 text-right whitespace-nowrap">
                          {metric === "std_hours" ? sum.toFixed(1) : sum.toLocaleString()}
                        </td>
                      )
                    })}
                    <td className="px-3 py-2 text-right bg-indigo-100 text-indigo-800 whitespace-nowrap">
                      {metric === "std_hours"
                        ? displayMethods.reduce((s, m) => s + [...(methodMap.get(m)?.values() ?? [])].reduce((a, b) => a + b, 0), 0).toFixed(1)
                        : displayMethods.reduce((s, m) => s + [...(methodMap.get(m)?.values() ?? [])].reduce((a, b) => a + b, 0), 0).toLocaleString()
                      }
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  )
}
