"use client"
// 检验周期页：KPI + 月度趋势 + 5重点检项趋势 + 方法明细表（对应 Streamlit View 3）
// 注意：左侧边栏的日期范围对本页不生效，由页面内「趋势月数」滑块控制统计区间
export const dynamic = "force-dynamic"
import { useState, useMemo } from "react"
import { useQuery } from "@tanstack/react-query"
import { useSearchParams } from "next/navigation"
import dayjs from "dayjs"
import {
  fetchCycleTimeByMethod,
  fetchCycleTimeMonthlyTrend,
  fetchCycleTimeTrendByMethod,
  fetchMethodTargets,
  CycleTimeTrendByMethodItem,
  MethodTargetItem,
} from "@/lib/api"
import { downloadCSV } from "@/lib/utils"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { StatCard } from "@/components/stat-card"
import type { CardScheme } from "@/components/stat-card"
import ReactECharts from "echarts-for-react"

// 5 个重点检项（目标天数从 meta.dim_method.target_days 读取，不再硬编码）
const KEY_METHODS = [
  { fallback: "表达量",                    include: "表达量",    exclude: null        },
  { fallback: "分子排阻色谱法（SEC）",       include: "分子排阻",  exclude: null        },
  { fallback: "离子交换高效液相色谱（IEX）",  include: "离子交换",  exclude: null        },
  { fallback: "R-CE-SDS",                include: "R-CE-SDS", exclude: "NR-CE-SDS" },
  { fallback: "NR-CE-SDS",               include: "NR-CE-SDS",exclude: null        },
]

function matchMethod(name: string, include: string, exclude: string | null) {
  const n = name.toLowerCase()
  if (!n.includes(include.toLowerCase())) return false
  if (exclude && n.includes(exclude.toLowerCase())) return false
  return true
}

// 将多个 method_name 按月合并（完成数加权平均周期）
function mergeByMonth(items: CycleTimeTrendByMethodItem[]) {
  const map: Record<string, { completed_n: number; wsum: number }> = {}
  for (const item of items) {
    if (!map[item.ym]) map[item.ym] = { completed_n: 0, wsum: 0 }
    map[item.ym].completed_n += item.completed_n
    map[item.ym].wsum += (item.avg_cycle_days ?? 0) * item.completed_n
  }
  return Object.entries(map)
    .sort(([a], [b]) => a.localeCompare(b))
    .map(([ym, v]) => ({
      ym,
      completed_n: v.completed_n,
      avg_cycle_days: v.completed_n > 0 ? parseFloat((v.wsum / v.completed_n).toFixed(1)) : null,
    }))
}

function trendLabel(delta: number | null) {
  if (delta === null || isNaN(delta)) return "—"
  if (delta > 1) return "↑ 延长"
  if (delta < -1) return "↓ 缩短"
  return "→ 持平"
}

function trendClass(delta: number | null) {
  if (delta === null || isNaN(delta)) return "text-gray-400"
  if (delta > 1) return "text-red-600 font-bold"
  if (delta < -1) return "text-green-600 font-bold"
  return "text-gray-500"
}

export default function CycleTimePage() {
  const searchParams = useSearchParams()
  const groups = searchParams.getAll("groups")

  const [targetDays, setTargetDays] = useState(14)
  const [trendMonths, setTrendMonths] = useState(12)

  // 统计区间（与原版逻辑完全一致）
  const today = dayjs().format("YYYY-MM-DD")
  const tableEnd = today
  const tableStart = dayjs().subtract(trendMonths - 1, "month").startOf("month").format("YYYY-MM-DD")
  const durationDays = dayjs(tableEnd).diff(dayjs(tableStart), "day") + 1
  const prevEnd = dayjs(tableStart).subtract(1, "day").format("YYYY-MM-DD")
  const prevStart = dayjs(prevEnd).subtract(durationDays - 1, "day").format("YYYY-MM-DD")

  const groupsKey = groups.join(",")

  const trendQuery = useQuery({
    queryKey: ["cycle-trend", trendMonths, groupsKey],
    queryFn: () => fetchCycleTimeMonthlyTrend({ months: trendMonths, groups: groups.length ? groups : undefined }),
  })

  const currQuery = useQuery({
    queryKey: ["cycle-by-method-curr", tableStart, tableEnd, groupsKey],
    queryFn: () => fetchCycleTimeByMethod({ start_date: tableStart, end_date: tableEnd, groups: groups.length ? groups : undefined }),
  })

  const prevQuery = useQuery({
    queryKey: ["cycle-by-method-prev", prevStart, prevEnd, groupsKey],
    queryFn: () => fetchCycleTimeByMethod({ start_date: prevStart, end_date: prevEnd, groups: groups.length ? groups : undefined }),
  })

  const methodTrendQuery = useQuery({
    queryKey: ["cycle-trend-by-method", trendMonths, groupsKey],
    queryFn: () => fetchCycleTimeTrendByMethod({ months: trendMonths, groups: groups.length ? groups : undefined }),
  })

  const methodTargetsQuery = useQuery({
    queryKey: ["method-targets"],
    queryFn: fetchMethodTargets,
    staleTime: Infinity,
  })

  // KPI 计算
  const kpi = useMemo(() => {
    const curr = currQuery.data?.items ?? []
    const prev = prevQuery.data?.items ?? []
    if (curr.length === 0) return null

    const validCurr = curr.filter((i) => i.avg_cycle_days !== null)
    const overallAvg = validCurr.length > 0
      ? validCurr.reduce((s, i) => s + (i.avg_cycle_days ?? 0), 0) / validCurr.length
      : null
    const overallCompleted = curr.reduce((s, i) => s + i.completed_n, 0)
    const overTargetN = validCurr.filter((i) => (i.avg_cycle_days ?? 0) > targetDays).length

    const validPrev = prev.filter((i) => i.avg_cycle_days !== null)
    const prevAvg = validPrev.length > 0
      ? validPrev.reduce((s, i) => s + (i.avg_cycle_days ?? 0), 0) / validPrev.length
      : null

    const delta = overallAvg !== null && prevAvg !== null ? overallAvg - prevAvg : null

    return { overallAvg, overallCompleted, overTargetN, delta }
  }, [currQuery.data, prevQuery.data, targetDays])

  // 趋势评语
  const verdict = useMemo(() => {
    const items = (trendQuery.data?.items ?? []).filter((i) => i.avg_cycle_days !== null)
    if (items.length < 6) return null
    const recent3 = items.slice(-3).reduce((s, i) => s + (i.avg_cycle_days ?? 0), 0) / 3
    const prior3 = items.slice(-6, -3).reduce((s, i) => s + (i.avg_cycle_days ?? 0), 0) / 3
    const delta = recent3 - prior3
    if (delta > 1) return { type: "warning", msg: `近3个月均值 ${recent3.toFixed(1)} 天，较前3个月延长 ${delta > 0 ? "+" : ""}${delta.toFixed(1)} 天，需关注！` }
    if (delta < -1) return { type: "success", msg: `近3个月均值 ${recent3.toFixed(1)} 天，较前3个月缩短 ${Math.abs(delta).toFixed(1)} 天，持续改善！` }
    return { type: "info", msg: `近3个月均值 ${recent3.toFixed(1)} 天，较前3个月基本持平（${delta > 0 ? "+" : ""}${delta.toFixed(1)} 天）。` }
  }, [trendQuery.data])

  // 月度趋势图配置
  const trendOption = useMemo(() => {
    const items = trendQuery.data?.items ?? []
    if (!items.length) return null
    return {
      tooltip: {
        trigger: "axis",
        formatter: (params: { name: string; seriesName: string; value: number | null }[]) => {
          const item = items.find((d) => d.ym === params[0]?.name)
          if (!item) return ""
          return `<b>${item.ym}</b><br/>平均周期：${item.avg_cycle_days?.toFixed(1) ?? "—"} 天<br/>中位数：${item.median_cycle_days?.toFixed(1) ?? "—"} 天<br/>完成检项：${item.completed_n.toLocaleString()}`
        },
      },
      legend: { data: ["平均周期（天）", "中位数周期"], bottom: 0 },
      grid: { left: 48, right: 100, top: 24, bottom: 48 },
      xAxis: { type: "category", data: items.map((d) => d.ym), axisLabel: { fontSize: 11 } },
      yAxis: { type: "value", name: "工作日", axisLabel: { fontSize: 11 } },
      series: [
        {
          name: "平均周期（天）",
          type: "bar",
          data: items.map((d) => ({
            value: d.avg_cycle_days,
            itemStyle: { color: d.avg_cycle_days !== null && d.avg_cycle_days > targetDays ? "#E74C3C" : "#2ECC71" },
          })),
          label: { show: true, position: "top", formatter: (p: { value: number | null }) => p.value !== null ? p.value.toFixed(1) : "", fontSize: 10 },
          markLine: {
            silent: true,
            lineStyle: { color: "#E74C3C", type: "dashed", width: 1.5 },
            data: [{ yAxis: targetDays, name: `目标 ${targetDays} 天` }],
            label: { formatter: `目标 ${targetDays} 天`, color: "#E74C3C", position: "end" },
          },
        },
        {
          name: "中位数周期",
          type: "line",
          smooth: false,
          data: items.map((d) => d.median_cycle_days),
          lineStyle: { color: "#3498DB", type: "dotted", width: 2 },
          itemStyle: { color: "#3498DB" },
          symbol: "circle",
          symbolSize: 5,
        },
      ],
    }
  }, [trendQuery.data, targetDays])

  // 重点检项图表（target_days 从数据库读取，NULL 表示未设定）
  const keyMethodCharts = useMemo(() => {
    const allItems = methodTrendQuery.data?.items ?? []
    const targets = methodTargetsQuery.data ?? []

    return KEY_METHODS.map(({ fallback, include, exclude }) => {
      const matching = allItems.filter((i) => matchMethod(i.method_name, include, exclude))
      if (matching.length === 0) return { title: fallback, data: [], target: null }

      const chartTitle = Object.entries(
        matching.reduce((acc, i) => {
          acc[i.method_name] = (acc[i.method_name] ?? 0) + i.completed_n
          return acc
        }, {} as Record<string, number>)
      ).sort((a, b) => b[1] - a[1])[0][0]

      // 从 dim_method 中找匹配该关键词的方法的 target_days（取最小值，存在多个时）
      const matchedTargets = targets
        .filter((t) => matchMethod(t.method_name ?? "", include, exclude) && t.target_days !== null)
        .map((t) => t.target_days as number)
      const target = matchedTargets.length > 0 ? Math.min(...matchedTargets) : null

      return { title: chartTitle, data: mergeByMonth(matching), target }
    })
  }, [methodTrendQuery.data, methodTargetsQuery.data])

  // 明细表（合并上期 delta）
  const tableData = useMemo(() => {
    const curr = currQuery.data?.items ?? []
    const prev = prevQuery.data?.items ?? []
    const prevMap = Object.fromEntries(prev.map((i) => [i.method_code, i.avg_cycle_days]))
    return curr.map((item) => {
      const prevAvg = item.method_code ? prevMap[item.method_code] ?? null : null
      const delta = item.avg_cycle_days !== null && prevAvg !== null
        ? parseFloat((item.avg_cycle_days - prevAvg).toFixed(1))
        : null
      return { ...item, delta }
    })
  }, [currQuery.data, prevQuery.data])

  const isLoading = trendQuery.isLoading || currQuery.isLoading
  const isError = trendQuery.isError || currQuery.isError

  return (
    <div className="space-y-6">
      {/* 标题 + 控制行 */}
      <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <h1 className="text-xl font-semibold text-gray-900">项目检验平均周期</h1>
          <p className="text-xs text-amber-600 mt-1">
            ⚠ 本页日期由「趋势月数」滑块控制，左侧边栏日期对本页不生效
            {groups.length > 0 && <span className="ml-2 text-blue-600">· 已筛选 {groups.join("、")}</span>}
          </p>
        </div>
        <div className="flex items-center gap-4 text-sm">
          <label className="flex items-center gap-2 text-gray-600 whitespace-nowrap">
            目标周期（天）
            <input
              type="number"
              min={1} max={365}
              value={targetDays}
              onChange={(e) => setTargetDays(Math.max(1, parseInt(e.target.value) || 1))}
              className="w-16 border rounded px-2 py-1 text-sm text-gray-700 focus:outline-none focus:ring-1 focus:ring-blue-400"
            />
          </label>
          <label className="flex items-center gap-2 text-gray-600">
            趋势月数
            <input
              type="range"
              min={3} max={24}
              value={trendMonths}
              onChange={(e) => setTrendMonths(parseInt(e.target.value))}
              className="w-28 accent-blue-600"
            />
            <span className="w-6 text-center tabular-nums font-medium text-gray-700">{trendMonths}</span>
          </label>
        </div>
      </div>

      {isLoading && <p className="text-sm text-gray-400">加载中…</p>}
      {isError && <p className="text-sm text-red-500">数据加载失败，请确认后端服务已启动</p>}

      {/* KPI 卡片 */}
      {kpi && (
        <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
          <StatCard
            label="平均检验周期"
            value={kpi.overallAvg !== null ? kpi.overallAvg.toFixed(1) : "—"}
            unit={kpi.overallAvg !== null ? "工作日" : undefined}
            scheme="blue"
          />
          <StatCard
            label="较上期变化"
            value={kpi.delta !== null ? (kpi.delta > 0 ? "+" : "") + kpi.delta.toFixed(1) : "—"}
            unit={kpi.delta !== null ? "天" : undefined}
            sub={kpi.delta !== null
              ? kpi.delta > 0.5 ? "↑ 周期延长" : kpi.delta < -0.5 ? "↓ 周期缩短" : "→ 基本持平"
              : "无前期数据"}
            scheme={(kpi.delta === null ? "gray" : kpi.delta > 0.5 ? "red" : kpi.delta < -0.5 ? "green" : "gray") as CardScheme}
          />
          <StatCard
            label="完成检项数"
            value={kpi.overallCompleted.toLocaleString()}
            sub={`近 ${trendMonths} 个月累计`}
            scheme="green"
          />
          <StatCard
            label="超目标检项数"
            value={kpi.overTargetN}
            sub={`目标 ≤ ${targetDays} 天`}
            scheme={kpi.overTargetN > 0 ? "red" : "green"}
          />
        </div>
      )}

      <p className="text-xs text-gray-400">
        口径：KPI 与明细表统计区间 {tableStart} ～ {tableEnd}（与趋势月数联动）；
        检验周期 = 工作日（收样日不含，授权完成日含）；上期为相同天数的前序区间；排除 status=&apos;X&apos;/&apos;U&apos;。
      </p>

      {/* 月度趋势图 */}
      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-sm font-medium text-gray-700">
            月度平均检验周期趋势（近 {trendMonths} 个月，工作日）｜绿色 = 达标 &nbsp; 红色 = 超目标
          </CardTitle>
        </CardHeader>
        <CardContent>
          {trendOption && <ReactECharts option={trendOption} style={{ height: 360 }} />}
        </CardContent>
      </Card>

      {/* 趋势评语 */}
      {verdict && (
        <div className={`rounded-lg px-4 py-3 text-sm font-medium border ${
          verdict.type === "warning" ? "bg-amber-50 border-amber-200 text-amber-800" :
          verdict.type === "success" ? "bg-green-50 border-green-200 text-green-800" :
          "bg-blue-50 border-blue-200 text-blue-800"
        }`}>
          {verdict.type === "warning" ? "⚠️ " : verdict.type === "success" ? "✅ " : "ℹ️ "}
          {verdict.msg}
        </div>
      )}

      {/* 5 个重点检项月度趋势 */}
      <div>
        <h2 className="text-base font-semibold text-gray-800 mb-1">日常检项月度平均周期趋势</h2>
        <p className="text-xs text-gray-400 mb-4">
          以下 5 个检项独立展示月度平均检验周期；口径与整体趋势一致：以 test_authorised_dt 归属月份，周期 = 工作日。
        </p>
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
          {keyMethodCharts.map(({ title, data, target }) => {
            if (data.length === 0) {
              return (
                <Card key={title}>
                  <CardHeader className="pb-1"><CardTitle className="text-sm text-gray-600">{title}</CardTitle></CardHeader>
                  <CardContent><p className="text-xs text-gray-400 py-4 text-center">此月份范围内无数据</p></CardContent>
                </Card>
              )
            }
            const opt = {
              tooltip: {
                trigger: "axis",
                formatter: (params: { name: string; value: number | null; data: { customdata: number } }[]) => {
                  const p = params[0]
                  const targetStr = target !== null ? `<br/>目标：${target} 工作日` : ""
                  return `<b>${p.name}</b><br/>平均周期：${p.value?.toFixed(1) ?? "—"} 工作日${targetStr}<br/>完成检项：${p.data?.customdata ?? "—"}`
                },
              },
              grid: { left: 44, right: 88, top: 28, bottom: 52 },
              xAxis: { type: "category", data: data.map((d) => d.ym), axisLabel: { fontSize: 10, rotate: -30 } },
              yAxis: { type: "value", name: "工作日", axisLabel: { fontSize: 10 } },
              series: [{
                type: "bar",
                data: data.map((d) => ({
                  value: d.avg_cycle_days,
                  customdata: d.completed_n,
                  itemStyle: {
                    color: target !== null
                      ? (d.avg_cycle_days !== null && d.avg_cycle_days > target ? "#E74C3C" : "#2ECC71")
                      : "#6366f1",
                  },
                  label: { show: true, position: "top", formatter: (p: { value: number | null }) => p.value?.toFixed(1) ?? "", fontSize: 10 },
                })),
                ...(target !== null ? {
                  markLine: {
                    silent: true,
                    lineStyle: { color: "#E74C3C", type: "dashed", width: 1.2 },
                    data: [{ yAxis: target, name: `目标 ${target} 工作日` }],
                    label: { formatter: `目标 ${target} 天`, color: "#E74C3C", position: "end", fontSize: 10 },
                  },
                } : {}),
              }],
            }
            return (
              <Card key={title}>
                <CardHeader className="pb-1">
                  <CardTitle className="text-sm font-medium text-gray-700">{title}</CardTitle>
                </CardHeader>
                <CardContent>
                  <ReactECharts option={opt} style={{ height: 280 }} />
                </CardContent>
              </Card>
            )
          })}
        </div>
      </div>

      {/* 各检项明细表 */}
      <Card>
        <CardHeader className="pb-2">
          <div className="flex items-center justify-between">
            <CardTitle className="text-sm font-medium text-gray-700">各检项平均周期明细</CardTitle>
            {tableData.length > 0 && (
              <button
                onClick={() =>
                  downloadCSV(
                    tableData.map((i) => ({
                      检项名称: i.method_name,
                      完成数: i.completed_n,
                      "平均周期(天)": i.avg_cycle_days?.toFixed(1) ?? "",
                      "中位数(天)": i.median_cycle_days?.toFixed(1) ?? "",
                      "最长(天)": i.max_cycle_days ?? "",
                      "较上期(天)": i.delta?.toFixed(1) ?? "",
                      趋势: trendLabel(i.delta),
                      达标: (i.avg_cycle_days ?? 0) <= targetDays ? "✓" : "✗",
                    })),
                    `cycle_time_${tableStart}_${tableEnd}.csv`
                  )
                }
                className="text-xs text-indigo-600 hover:text-indigo-800 border border-indigo-200 rounded px-2 py-0.5 transition-colors"
              >
                导出 CSV
              </button>
            )}
          </div>
        </CardHeader>
        <CardContent className="p-0">
          {tableData.length === 0 ? (
            <p className="text-sm text-gray-400 px-4 py-6">当前时间段内无已完成检项数据</p>
          ) : (
            <>
              <p className="text-xs text-gray-400 px-4 py-2">
                共 {tableData.length} 个检项，其中 {tableData.filter((i) => (i.avg_cycle_days ?? 0) > targetDays).length} 个均值超目标周期（{targetDays} 天）；红色 = 超目标或较上期延长，绿色 = 达标或改善。
              </p>
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b bg-gray-50 text-gray-500 text-xs">
                      <th className="text-left px-4 py-2 font-medium">检项名称</th>
                      <th className="text-right px-4 py-2 font-medium">完成数</th>
                      <th className="text-right px-4 py-2 font-medium">平均周期(天)</th>
                      <th className="text-right px-4 py-2 font-medium">中位数(天)</th>
                      <th className="text-right px-4 py-2 font-medium">最长(天)</th>
                      <th className="text-right px-4 py-2 font-medium">较上期(天)</th>
                      <th className="text-center px-4 py-2 font-medium">趋势</th>
                      <th className="text-center px-4 py-2 font-medium">达标</th>
                    </tr>
                  </thead>
                  <tbody>
                    {tableData.map((item, idx) => {
                      const overTarget = (item.avg_cycle_days ?? 0) > targetDays
                      const pass = !overTarget
                      return (
                        <tr key={idx} className={idx % 2 === 0 ? "bg-white" : "bg-gray-50"}>
                          <td className="px-4 py-2 text-gray-800">{item.method_name}</td>
                          <td className="px-4 py-2 text-right tabular-nums">{item.completed_n.toLocaleString()}</td>
                          <td className={`px-4 py-2 text-right tabular-nums font-bold ${overTarget ? "text-red-600" : "text-green-600"}`}>
                            {item.avg_cycle_days?.toFixed(1) ?? "—"}
                          </td>
                          <td className="px-4 py-2 text-right tabular-nums text-gray-600">
                            {item.median_cycle_days?.toFixed(1) ?? "—"}
                          </td>
                          <td className="px-4 py-2 text-right tabular-nums text-gray-600">
                            {item.max_cycle_days ?? "—"}
                          </td>
                          <td className={`px-4 py-2 text-right tabular-nums ${trendClass(item.delta)}`}>
                            {item.delta !== null ? (item.delta > 0 ? "+" : "") + item.delta.toFixed(1) : "—"}
                          </td>
                          <td className={`px-4 py-2 text-center font-bold ${trendClass(item.delta)}`}>
                            {trendLabel(item.delta)}
                          </td>
                          <td className={`px-4 py-2 text-center font-bold ${pass ? "text-green-600" : "text-red-600"}`}>
                            {pass ? "✓" : "✗"}
                          </td>
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
    </div>
  )
}
