"use client"
export const dynamic = "force-dynamic"
import { useState } from "react"
import { useQuery } from "@tanstack/react-query"
import { useSearchParams } from "next/navigation"
import { fetchSampleList, SampleListItem } from "@/lib/api"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import dayjs from "dayjs"

const STATUS_FILTERS = [
  { value: "", label: "全部（排除取消）" },
  { value: "inprogress", label: "进行中" },
  { value: "completed", label: "已完结" },
  { value: "unsubmitted", label: "未送样" },
]

const PAGE_SIZE_OPTIONS = [25, 50, 100]

function statusBadge(status: string | null) {
  const s = (status ?? "").toUpperCase()
  if (s === "A") return <span className="px-1.5 py-0.5 text-xs rounded bg-green-100 text-green-700">已授权</span>
  if (s === "C") return <span className="px-1.5 py-0.5 text-xs rounded bg-blue-100 text-blue-700">已完成</span>
  if (s === "V") return <span className="px-1.5 py-0.5 text-xs rounded bg-yellow-100 text-yellow-700">进行中</span>
  if (s === "U") return <span className="px-1.5 py-0.5 text-xs rounded bg-gray-100 text-gray-500">未送样</span>
  if (s === "X") return <span className="px-1.5 py-0.5 text-xs rounded bg-red-100 text-red-400">已取消</span>
  return <span className="px-1.5 py-0.5 text-xs rounded bg-gray-100 text-gray-400">{status ?? "—"}</span>
}

function fmtDate(d: string | null) {
  return d ? dayjs(d).format("YYYY-MM-DD") : "—"
}

export default function SamplesPage() {
  const searchParams = useSearchParams()
  const groups = searchParams.getAll("groups")
  const startDate = searchParams.get("start_date") ?? dayjs().subtract(30, "day").format("YYYY-MM-DD")
  const endDate = searchParams.get("end_date") ?? dayjs().format("YYYY-MM-DD")

  const [statusFilter, setStatusFilter] = useState("")
  const [projectSearch, setProjectSearch] = useState("")
  const [searchInput, setSearchInput] = useState("")
  const [page, setPage] = useState(1)
  const [pageSize, setPageSize] = useState(50)

  const { data, isLoading, isError } = useQuery({
    queryKey: ["sample-list", startDate, endDate, groups, statusFilter, projectSearch, page, pageSize],
    queryFn: () =>
      fetchSampleList({
        start_date: startDate,
        end_date: endDate,
        groups: groups.length ? groups : undefined,
        status_filter: statusFilter || undefined,
        project_search: projectSearch || undefined,
        page,
        page_size: pageSize,
      }),
  })

  const totalPages = data ? Math.ceil(data.total / pageSize) : 1

  const handleSearch = () => {
    setProjectSearch(searchInput)
    setPage(1)
  }

  const handleStatusChange = (v: string) => {
    setStatusFilter(v)
    setPage(1)
  }

  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-xl font-semibold text-gray-900">样本总览</h1>
        <p className="text-sm text-gray-500 mt-1">
          到样区间：{startDate} ~ {endDate}
          {groups.length > 0 && <span className="ml-2 text-blue-600">· 已筛选 {groups.join("、")}</span>}
        </p>
      </div>

      {/* 筛选栏 */}
      <Card>
        <CardContent className="pt-4 pb-3">
          <div className="flex flex-wrap gap-3 items-center">
            {/* 状态筛选 */}
            <div className="flex rounded border text-xs overflow-hidden">
              {STATUS_FILTERS.map((sf, idx) => (
                <button
                  key={sf.value}
                  onClick={() => handleStatusChange(sf.value)}
                  className={`px-3 py-1.5 transition-colors ${idx > 0 ? "border-l" : ""} ${
                    statusFilter === sf.value ? "bg-indigo-600 text-white" : "text-gray-500 hover:bg-gray-50"
                  }`}
                >
                  {sf.label}
                </button>
              ))}
            </div>

            {/* 项目/样品搜索 */}
            <div className="flex gap-1.5">
              <input
                type="text"
                value={searchInput}
                onChange={(e) => setSearchInput(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && handleSearch()}
                placeholder="搜索项目编号 / 样品编号"
                className="border rounded px-2.5 py-1 text-xs text-gray-700 w-52 focus:outline-none focus:ring-1 focus:ring-blue-400"
              />
              <button
                onClick={handleSearch}
                className="px-3 py-1 bg-blue-600 text-white text-xs rounded hover:bg-blue-700 transition-colors"
              >
                搜索
              </button>
              {projectSearch && (
                <button
                  onClick={() => { setProjectSearch(""); setSearchInput(""); setPage(1) }}
                  className="px-2 py-1 text-xs text-gray-400 hover:text-gray-600 border rounded transition-colors"
                >
                  清除
                </button>
              )}
            </div>

            {/* 每页条数 */}
            <div className="flex items-center gap-1.5 text-xs text-gray-500 ml-auto">
              <span>每页</span>
              <select
                value={pageSize}
                onChange={(e) => { setPageSize(Number(e.target.value)); setPage(1) }}
                className="border rounded px-1.5 py-0.5 text-xs text-gray-700 bg-white focus:outline-none"
              >
                {PAGE_SIZE_OPTIONS.map((n) => (
                  <option key={n} value={n}>{n} 条</option>
                ))}
              </select>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* 数据表格 */}
      <Card>
        <CardHeader className="pb-2">
          <div className="flex items-center justify-between">
            <CardTitle className="text-sm font-medium text-gray-700">
              样本列表
              {data && (
                <span className="ml-2 text-xs font-normal text-gray-400">
                  共 {data.total.toLocaleString()} 条
                </span>
              )}
            </CardTitle>
          </div>
        </CardHeader>
        <CardContent className="px-0 pb-4">
          {isLoading && <p className="text-sm text-gray-400 py-8 text-center">加载中…</p>}
          {isError && <p className="text-sm text-red-500 py-8 text-center">数据加载失败</p>}
          {data && (
            <div className="overflow-x-auto">
              <table className="w-full text-xs">
                <thead>
                  <tr className="border-b bg-gray-50 text-gray-500">
                    <th className="px-4 py-2 text-left font-medium whitespace-nowrap">样品编号</th>
                    <th className="px-4 py-2 text-left font-medium whitespace-nowrap">项目编号</th>
                    <th className="px-4 py-2 text-left font-medium whitespace-nowrap">样品名称</th>
                    <th className="px-4 py-2 text-left font-medium whitespace-nowrap">批号</th>
                    <th className="px-4 py-2 text-left font-medium whitespace-nowrap">样品类型</th>
                    <th className="px-4 py-2 text-left font-medium whitespace-nowrap">到样日期</th>
                    <th className="px-4 py-2 text-left font-medium whitespace-nowrap">完成日期</th>
                    <th className="px-4 py-2 text-left font-medium whitespace-nowrap">授权日期</th>
                    <th className="px-4 py-2 text-left font-medium whitespace-nowrap">检测员</th>
                    <th className="px-4 py-2 text-left font-medium whitespace-nowrap">组别</th>
                    <th className="px-4 py-2 text-left font-medium whitespace-nowrap">状态</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-100">
                  {data.items.length === 0 ? (
                    <tr>
                      <td colSpan={11} className="px-4 py-8 text-center text-gray-400">暂无数据</td>
                    </tr>
                  ) : (
                    data.items.map((item: SampleListItem, idx: number) => (
                      <tr key={`${item.sample_id}-${idx}`} className="hover:bg-gray-50 transition-colors">
                        <td className="px-4 py-2 font-mono text-gray-800 whitespace-nowrap">{item.sample_id}</td>
                        <td className="px-4 py-2 text-gray-600 whitespace-nowrap">{item.project_id ?? "—"}</td>
                        <td className="px-4 py-2 text-gray-700 max-w-[160px] truncate" title={item.sample_name ?? ""}>{item.sample_name ?? "—"}</td>
                        <td className="px-4 py-2 text-gray-600 whitespace-nowrap">{item.batch_number ?? "—"}</td>
                        <td className="px-4 py-2 text-gray-600 whitespace-nowrap">{item.sample_type ?? "—"}</td>
                        <td className="px-4 py-2 text-gray-600 whitespace-nowrap">{fmtDate(item.received_dt)}</td>
                        <td className="px-4 py-2 text-gray-600 whitespace-nowrap">{fmtDate(item.completed_dt)}</td>
                        <td className="px-4 py-2 text-gray-600 whitespace-nowrap">{fmtDate(item.authorised_dt)}</td>
                        <td className="px-4 py-2 text-gray-600 whitespace-nowrap">{item.tester ?? "—"}</td>
                        <td className="px-4 py-2 text-gray-500 whitespace-nowrap">{item.group_id ?? "—"}</td>
                        <td className="px-4 py-2 whitespace-nowrap">{statusBadge(item.status)}</td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>
          )}

          {/* 分页控件 */}
          {data && data.total > 0 && (
            <div className="flex items-center justify-between px-4 pt-3 border-t mt-2">
              <span className="text-xs text-gray-400">
                第 {(page - 1) * pageSize + 1}–{Math.min(page * pageSize, data.total)} 条，共 {data.total} 条
              </span>
              <div className="flex gap-1">
                <button
                  disabled={page <= 1}
                  onClick={() => setPage((p) => p - 1)}
                  className="px-2.5 py-1 text-xs border rounded disabled:opacity-40 hover:bg-gray-50 transition-colors"
                >
                  上一页
                </button>
                <span className="px-3 py-1 text-xs text-gray-500">
                  {page} / {totalPages}
                </span>
                <button
                  disabled={page >= totalPages}
                  onClick={() => setPage((p) => p + 1)}
                  className="px-2.5 py-1 text-xs border rounded disabled:opacity-40 hover:bg-gray-50 transition-colors"
                >
                  下一页
                </button>
              </div>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  )
}
