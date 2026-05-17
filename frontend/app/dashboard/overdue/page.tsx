"use client"
// 超期未检页：4类计数 + 未完成检项方法分布饼图（对应 Streamlit View 4）
export const dynamic = "force-dynamic"
import { useQuery } from "@tanstack/react-query"
import { useSearchParams } from "next/navigation"
import { fetchOverdue } from "@/lib/api"
import { Card, CardContent } from "@/components/ui/card"
import { StatCard } from "@/components/stat-card"
import ReactECharts from "echarts-for-react"
import dayjs from "dayjs"

export default function OverduePage() {
  const searchParams = useSearchParams()
  const groups = searchParams.getAll("groups")
  const today = dayjs().format("YYYY-MM-DD")
  const asOf = searchParams.get("end_date") ?? today

  const { data, isLoading, isError } = useQuery({
    queryKey: ["overdue", asOf, groups],
    queryFn: () => fetchOverdue({ as_of: asOf, groups: groups.length ? groups : undefined }),
  })

  const pieOption = (
    title: string,
    items: { method_name: string | null; test_count: number }[]
  ) => ({
    tooltip: { trigger: "item", formatter: "{b}: {c} ({d}%)" },
    legend: { orient: "vertical", right: 10, top: "center", textStyle: { fontSize: 11 } },
    title: { text: title, textStyle: { fontSize: 13, fontWeight: "normal" } },
    series: [
      {
        type: "pie",
        radius: ["35%", "65%"],
        center: ["38%", "55%"],
        data: items.map((d) => ({ name: d.method_name ?? "（未知）", value: d.test_count })),
        label: { show: false },
        emphasis: { label: { show: true, fontSize: 12 } },
      },
    ],
  })

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-semibold text-gray-900">超期未检情况汇总</h1>
        <p className="text-sm text-gray-500 mt-1">
          截止日期：{asOf}
          {groups.length > 0 && <span className="ml-2 text-blue-600">· 已筛选 {groups.join("、")}</span>}
        </p>
      </div>

      {isLoading && <p className="text-sm text-gray-400">加载中…</p>}
      {isError && <p className="text-sm text-red-500">数据加载失败，请确认后端服务已启动</p>}

      {data && (
        <>
          <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
            <StatCard label="请验未送样" value={data.summary.unsubmitted.toLocaleString()}  scheme="green"  />
            <StatCard label="收样未分配" value={data.summary.unassigned.toLocaleString()}   scheme="blue"   />
            <StatCard label="分配未完成" value={data.summary.inprogress.toLocaleString()}   scheme="orange" />
            <StatCard label="检毕未授权" value={data.summary.unauthorized.toLocaleString()} scheme="lapis"  />
          </div>
          <p className="text-xs text-gray-400">
            口径说明：截至 {asOf} 前所有已收样样品（received_dt ≤ {asOf}），统计有效检项（去重 test_id），排除 status=&apos;X&apos;。
          </p>

          <div className="grid grid-cols-1 gap-4">
            <Card>
              <CardContent className="pt-4">
                <ReactECharts
                  option={pieOption("未完成检项分布", data.incomplete_distribution)}
                  style={{ height: 380 }}
                />
              </CardContent>
            </Card>
            <Card>
              <CardContent className="pt-4">
                <ReactECharts
                  option={pieOption("未送样检项分布", data.unsubmitted_distribution)}
                  style={{ height: 380 }}
                />
              </CardContent>
            </Card>
          </div>
        </>
      )}
    </div>
  )
}
