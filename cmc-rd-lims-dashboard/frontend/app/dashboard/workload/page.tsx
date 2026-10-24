"use client"
export const dynamic = "force-dynamic"
import { useState } from "react"
import { useQuery } from "@tanstack/react-query"
import { useSearchParams } from "next/navigation"
import {
  fetchWorkload,
  fetchWorkloadKPI,
  fetchWorkloadByMethod,
  WorkloadByMethodItem,
  WorkloadItem,
} from "@/lib/api"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { StatCard } from "@/components/stat-card"
import ReactECharts from "echarts-for-react"
import dayjs from "dayjs"
import { downloadCSV } from "@/lib/utils"

type Scope = "submitted" | "completed" | "pending"

const SCOPE_LABELS: Record<Scope, string> = {
  submitted: "送检口径",
  completed: "已完成口径",
  pending: "未完成口径",
}

export default function WorkloadPage() {
  const searchParams = useSearchParams()
  const groups = searchParams.getAll("groups")
  const startDate = searchParams.get("start_date") ?? dayjs().subtract(30, "day").format("YYYY-MM-DD")
  const endDate = searchParams.get("end_date") ?? dayjs().format("YYYY-MM-DD")

  const [scope, setScope] = useState<Scope>("completed")
  const [methodThreshold, setMethodThreshold] = useState(0)
  const [employeeThreshold, setEmployeeThreshold] = useState(0)

  const commonParams = {
    start_date: startDate,
    end_date: endDate,
    groups: groups.length ? groups : undefined,
  }

  const kpiQuery = useQuery({
    queryKey: ["workload-kpi", startDate, endDate, groups],
    queryFn: () => fetchWorkloadKPI(commonParams),
  })

  const workloadQuery = useQuery({
    queryKey: ["workload", startDate, endDate, groups, scope],
    queryFn: () => fetchWorkload({ ...commonParams, scope }),
  })

  const methodQuery = useQuery({
    queryKey: ["workload-by-method", startDate, endDate, groups, scope],
    queryFn: () => fetchWorkloadByMethod({ ...commonParams, scope }),
  })

  const kpi = kpiQuery.data
  const items: WorkloadItem[] = workloadQuery.data?.items ?? []
  const methodItems: WorkloadByMethodItem[] = methodQuery.data?.items ?? []

  const filteredItems = items.filter((i) => i.total_hours >= employeeThreshold)
  const filteredMethodItems = methodItems.filter((i) => i.total_hours >= methodThreshold)

  const totalMethodHours = filteredMethodItems.reduce((s, i) => s + i.total_hours, 0)

  const barOption = (rows: WorkloadItem[]) => {
    const sorted = [...rows].sort((a, b) => a.total_hours - b.total_hours)
    return {
      tooltip: {
        trigger: "axis",
        axisPointer: { type: "shadow" },
        formatter: (params: { name: string; value: number; dataIndex: number }[]) => {
          const p = params[0]
          // 用 dataIndex 定位而非按显示名反查：同名员工按名字查会串数据
          const item = sorted[p.dataIndex]
          const dept = item?.department ? ` · ${item.department}` : ""
          return `${p.name}${dept}<br/>标准工时：<b>${p.value.toFixed(1)} 小时</b><br/>检项数：${item?.test_n ?? "—"}`
        },
      },
      grid: { left: 120, right: 60, top: 16, bottom: 20 },
      xAxis: {
        type: "value",
        name: "标准工时（小时）",
        nameLocation: "end",
        nameTextStyle: { fontSize: 11, color: "#9ca3af" },
        axisLabel: { fontSize: 11 },
      },
      yAxis: {
        type: "category",
        data: sorted.map((i) => i.employee_name ?? i.tester),
        axisLabel: { fontSize: 12 },
      },
      series: [
        {
          type: "bar",
          data: sorted.map((i) => i.total_hours),
          itemStyle: {
            color: scope === "pending" ? "#f59e0b" : scope === "submitted" ? "#8b5cf6" : "#3b82f6",
            borderRadius: [0, 3, 3, 0],
          },
          label: {
            show: true,
            position: "right",
            formatter: (p: { value: number }) => p.value.toFixed(1),
            fontSize: 11,
            color: "#374151",
          },
        },
      ],
    }
  }

  const pieOption = (rows: WorkloadByMethodItem[]) => {
    const data = rows.map((i) => ({
      name: i.method_name,
      value: i.total_hours,
    }))
    return {
      tooltip: {
        trigger: "item",
        formatter: (p: { name: string; value: number; percent: number }) =>
          `${p.name}<br/>工时：<b>${p.value.toFixed(1)} 小时</b>（${p.percent.toFixed(1)}%）`,
      },
      legend: { type: "scroll", orient: "vertical", right: 10, top: "middle", textStyle: { fontSize: 11 } },
      series: [
        {
          type: "pie",
          radius: ["40%", "70%"],
          center: ["38%", "50%"],
          data,
          label: {
            show: true,
            formatter: (p: { percent: number }) => `${p.percent.toFixed(1)}%`,
            fontSize: 11,
          },
          emphasis: { itemStyle: { shadowBlur: 10, shadowOffsetX: 0, shadowColor: "rgba(0,0,0,0.2)" } },
        },
      ],
    }
  }

  const barHeight = Math.max(300, filteredItems.length * 32 + 60)
  const isLoading = kpiQuery.isLoading || workloadQuery.isLoading
  const isError = kpiQuery.isError || workloadQuery.isError

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-semibold text-gray-900">员工工时汇总</h1>
        <p className="text-sm text-gray-500 mt-1">
          {startDate} ~ {endDate}
          {groups.length > 0 && (
            <span className="ml-2 text-blue-600">· 已筛选 {groups.join("、")}</span>
          )}
        </p>
      </div>

      {isLoading && <p className="text-sm text-gray-400">加载中…</p>}
      {isError && <p className="text-sm text-red-500">数据加载失败，请确认后端服务已启动</p>}

      {/* KPI Cards */}
      {kpi && (
        <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
          <StatCard label="送检工时"   value={kpi.submitted_hours.toFixed(1)}  unit="小时" scheme="blue"   />
          <StatCard label="已完成工时" value={kpi.completed_hours.toFixed(1)}  unit="小时" scheme="green"  />
          <StatCard label="未完成工时" value={kpi.pending_hours.toFixed(1)}    unit="小时" scheme="orange" />
          <StatCard
            label="检验效率"
            value={kpi.efficiency != null ? (kpi.efficiency * 100).toFixed(1) : "—"}
            unit={kpi.efficiency != null ? "%" : undefined}
            sub="已完成 / 送检"
            scheme="lapis"
          />
        </div>
      )}

      {/* 未定义标准工时警告（与原版 st.warning 一致） */}
      {kpi && kpi.missing_methods.length > 0 && (
        <div className="rounded border border-amber-300 bg-amber-50 px-4 py-2 text-sm text-amber-800">
          以下 method_code 未定义标准工时，已按 0 计入：{kpi.missing_methods.join("、")}
        </div>
      )}

      {/* 方法统计口径切换（与原版一致，在图表上方全局生效） */}
      {(workloadQuery.data || methodQuery.data) && (
        <div className="flex items-center gap-3">
          <span className="text-sm text-gray-600 font-medium">方法统计口径</span>
          <div className="flex rounded border overflow-hidden text-sm">
            {(["submitted", "completed", "pending"] as Scope[]).map((s) => (
              <button
                key={s}
                onClick={() => setScope(s)}
                className={`px-3 py-1.5 transition-colors ${
                  scope === s ? "bg-blue-600 text-white" : "bg-white text-gray-600 hover:bg-gray-50"
                }`}
              >
                {SCOPE_LABELS[s]}
              </button>
            ))}
          </div>
        </div>
      )}

      {/* 员工工时条形图（原版中在方法饼图之前） */}
      {workloadQuery.data && items.length > 0 && (
        <Card>
          <CardHeader className="pb-2">
            <div className="flex items-center justify-between flex-wrap gap-2">
              <CardTitle className="text-sm font-medium text-gray-700">
                员工工时排行（{SCOPE_LABELS[scope]}）
              </CardTitle>
              <div className="flex items-center gap-1 text-xs text-gray-500">
                <span>≥</span>
                <input
                  type="number"
                  min={0}
                  step={1}
                  value={employeeThreshold}
                  onChange={(e) => setEmployeeThreshold(Number(e.target.value))}
                  className="w-14 border rounded px-1 py-0.5 text-xs text-center"
                />
                <span>小时</span>
              </div>
            </div>
          </CardHeader>
          <CardContent>
            {filteredItems.length === 0 ? (
              <p className="text-sm text-gray-400 py-4 text-center">无满足阈值的人员数据</p>
            ) : (
              <ReactECharts option={barOption(filteredItems)} style={{ height: barHeight }} />
            )}
          </CardContent>
        </Card>
      )}

      {/* 方法工时占比饼图（原版中在员工图之后） */}
      {methodQuery.data && methodItems.length > 0 && (
        <Card>
          <CardHeader className="pb-2">
            <div className="flex items-center justify-between">
              <CardTitle className="text-sm font-medium text-gray-700">检验方法工时占比（{SCOPE_LABELS[scope]}）</CardTitle>
              <div className="flex items-center gap-2 text-xs text-gray-500">
                <span>最小显示</span>
                <input
                  type="number"
                  min={0}
                  step={1}
                  value={methodThreshold}
                  onChange={(e) => setMethodThreshold(Number(e.target.value))}
                  className="w-16 border rounded px-1 py-0.5 text-xs text-center"
                />
                <span>小时</span>
                <span className="text-gray-400 ml-1">
                  共 {totalMethodHours.toFixed(1)} h / {filteredMethodItems.length} 项
                </span>
              </div>
            </div>
          </CardHeader>
          <CardContent>
            {filteredMethodItems.length === 0 ? (
              <p className="text-sm text-gray-400 py-4 text-center">无满足阈值的方法数据</p>
            ) : (
              <ReactECharts option={pieOption(filteredMethodItems)} style={{ height: 320 }} />
            )}
          </CardContent>
        </Card>
      )}

      {/* 明细表 */}
      {workloadQuery.data && items.length > 0 && (
        <Card>
          <CardHeader className="pb-2">
            <div className="flex items-center justify-between">
              <CardTitle className="text-sm font-medium text-gray-700">
                明细数据 · {SCOPE_LABELS[scope]}
              </CardTitle>
              <button
                onClick={() =>
                  downloadCSV(
                    items.map((i) => ({
                      员工ID: i.tester,
                      姓名: i.employee_name ?? "",
                      部门: i.department ?? "",
                      检项数: i.test_n,
                      "标准工时(h)": i.total_hours.toFixed(1),
                    })),
                    `workload_${scope}_${startDate}_${endDate}.csv`
                  )
                }
                className="text-xs text-indigo-600 hover:text-indigo-800 border border-indigo-200 rounded px-2 py-0.5 transition-colors"
              >
                导出 CSV
              </button>
            </div>
          </CardHeader>
          <CardContent className="p-0">
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b bg-gray-50 text-gray-500 text-xs">
                    <th className="text-left px-4 py-2 font-medium">员工 ID</th>
                    <th className="text-left px-4 py-2 font-medium">姓名</th>
                    <th className="text-left px-4 py-2 font-medium">部门</th>
                    <th className="text-right px-4 py-2 font-medium">检项数</th>
                    <th className="text-right px-4 py-2 font-medium">标准工时（小时）</th>
                  </tr>
                </thead>
                <tbody>
                  {items.map((item, idx) => (
                    <tr key={item.tester} className={idx % 2 === 0 ? "bg-white" : "bg-gray-50"}>
                      <td className="px-4 py-2 text-gray-500 tabular-nums">{item.tester}</td>
                      <td className="px-4 py-2 font-medium text-gray-800">
                        {item.employee_name ?? "—"}
                      </td>
                      <td className="px-4 py-2 text-gray-500">{item.department ?? "—"}</td>
                      <td className="px-4 py-2 text-right tabular-nums">{item.test_n.toLocaleString()}</td>
                      <td className="px-4 py-2 text-right tabular-nums font-medium text-blue-700">
                        {item.total_hours.toFixed(1)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  )
}
