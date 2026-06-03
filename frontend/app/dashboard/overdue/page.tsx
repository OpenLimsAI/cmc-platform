"use client"
// 超期未检页：4类计数 + 未完成/未送样检项方法分布饼图（对应 Streamlit View 4）
//   + 超期未检明细表（已分配未授权检项，按超期天数倒序）
// 口径见 rd-lims-etl/docs/指标口径.md §4 / §4.1
export const dynamic = "force-dynamic"
import { useQuery } from "@tanstack/react-query"
import { useSearchParams } from "next/navigation"
import { useEffect, useMemo, useState } from "react"
import { fetchOverdue, fetchOverdueList, type OverdueListItem } from "@/lib/api"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { StatCard } from "@/components/stat-card"
import { FilterCombo } from "@/components/filter-combo"
import ReactECharts from "echarts-for-react"
import dayjs from "dayjs"

// 明细表的 4 个联动筛选字段（key 对应 OverdueListItem 字段）
const DETAIL_FILTERS = [
  { key: "project_id", label: "项目编号" },
  { key: "sample_id", label: "样品编号" },
  { key: "starter", label: "检验员" },
  { key: "method_name", label: "检验方法" },
] as const
type FilterKey = (typeof DETAIL_FILTERS)[number]["key"]
type FilterState = Record<FilterKey, string | null>

const fmtDate = (v: string | null) => (v ? dayjs(v).format("YYYY-MM-DD") : "—")

// 默认超期阈值（自然日）；方法有检验时限(target_days)时以其为准
const DEFAULT_OVERDUE_LIMIT = 14

// 饼图标签缩写：仅用于图中标识（label / legend），tooltip 与明细表仍显示全称
// 顺序敏感：NR-CE-SDS 必须排在 R-CE-SDS 之前（前者串含后者）
const PIE_ABBR: [RegExp, string][] = [
  [/NR-CE-SDS/i, "NR-CE"],
  [/R-CE-SDS/i, "R-CE"],
  [/IEX/i, "IEX"],
  [/SEC/i, "SEC"],
]
const abbrMethod = (name: string): string => {
  for (const [re, abbr] of PIE_ABBR) if (re.test(name)) return abbr
  return name
}

// 超期桶标签：inprogress=分配未完成 / unauthorized=检毕未授权
const bucketBadge = (b: string | null) => {
  if (b === "inprogress")
    return <span className="px-1.5 py-0.5 text-xs rounded bg-yellow-100 text-yellow-700">分配未完成</span>
  if (b === "unauthorized")
    return <span className="px-1.5 py-0.5 text-xs rounded bg-blue-100 text-blue-700">检毕未授权</span>
  return <span className="px-1.5 py-0.5 text-xs rounded bg-gray-100 text-gray-400">{b ?? "—"}</span>
}

export default function OverduePage() {
  const searchParams = useSearchParams()
  const groups = searchParams.getAll("groups")
  const today = dayjs().format("YYYY-MM-DD")
  const asOf = searchParams.get("end_date") ?? today

  const { data, isLoading, isError } = useQuery({
    queryKey: ["overdue", asOf, groups],
    queryFn: () => fetchOverdue({ as_of: asOf, groups: groups.length ? groups : undefined }),
  })

  const { data: listData, isLoading: listLoading, isError: listError } = useQuery({
    queryKey: ["overdue-list", asOf, groups],
    queryFn: () => fetchOverdueList({ as_of: asOf, groups: groups.length ? groups : undefined }),
  })

  // ---- 明细表联动筛选（纯前端，全量数据已在内存）----
  const [filters, setFilters] = useState<FilterState>({
    project_id: null,
    sample_id: null,
    starter: null,
    method_name: null,
  })

  const allItems = useMemo(() => listData?.items ?? [], [listData])

  // 应用全部筛选，但可排除某个字段（算该字段自身的可选项时用，实现联动）
  const matchExcept = (items: OverdueListItem[], exclude: FilterKey | null) =>
    items.filter((it) =>
      DETAIL_FILTERS.every(({ key }) => {
        if (key === exclude) return true
        const fv = filters[key]
        return !fv || it[key] === fv
      })
    )

  // 表格数据：应用全部筛选
  const filteredItems = useMemo(
    () => matchExcept(allItems, null),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [allItems, filters]
  )

  // 每个筛选框的可选项 = 在「其他筛选条件」下出现过的去重值（联动核心）
  const optionsByField = useMemo(() => {
    const r = {} as Record<FilterKey, string[]>
    for (const { key } of DETAIL_FILTERS) {
      const vals = new Set<string>()
      for (const it of matchExcept(allItems, key)) {
        const v = it[key]
        if (v != null && v !== "") vals.add(String(v))
      }
      r[key] = Array.from(vals).sort((a, b) => a.localeCompare(b, "zh"))
    }
    return r
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [allItems, filters])

  // 联动副作用：某个已选值因其他筛选变化而不再可选时，自动清空它
  useEffect(() => {
    let changed = false
    const next = { ...filters }
    for (const { key } of DETAIL_FILTERS) {
      if (filters[key] && !optionsByField[key].includes(filters[key]!)) {
        next[key] = null
        changed = true
      }
    }
    if (changed) setFilters(next)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [optionsByField])

  const hasActiveFilter = DETAIL_FILTERS.some(({ key }) => filters[key])
  const setFilter = (key: FilterKey, v: string | null) =>
    setFilters((prev) => ({ ...prev, [key]: v }))
  const clearFilters = () =>
    setFilters({ project_id: null, sample_id: null, starter: null, method_name: null })

  const pieOption = (
    title: string,
    items: { method_name: string | null; test_count: number }[]
  ) => ({
    tooltip: { trigger: "item", formatter: "{b}: {c} ({d}%)" }, // tooltip 用全称
    legend: {
      orient: "vertical",
      right: 10,
      top: "center",
      textStyle: { fontSize: 11 },
      formatter: abbrMethod, // 图例用缩写
    },
    title: { text: title, textStyle: { fontSize: 13, fontWeight: "normal" } },
    series: [
      {
        type: "pie",
        radius: ["35%", "65%"],
        center: ["38%", "55%"],
        data: items.map((d) => ({ name: d.method_name ?? "（未知）", value: d.test_count })),
        // 只标注占比 ≥5%（18°）的检项，避免小切片标签堆叠；小于 5% 的切片仍计入但不显示标签/引线
        minShowLabelAngle: 18,
        // 标签用缩写（仅图中标识简化）
        label: {
          show: true,
          fontSize: 11,
          formatter: (p: { name: string; percent: number }) => `${abbrMethod(p.name)}: ${p.percent}%`,
        },
        labelLine: { show: true, length: 8, length2: 8 },
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

      {/* 超期未检明细表（已分配未授权检项，按超期天数倒序） */}
      <Card>
        <CardHeader className="pb-2">
          <div className="flex items-center justify-between">
            <CardTitle className="text-sm font-medium text-gray-700">
              超期未检明细
              {listData && (
                <span className="ml-2 text-xs font-normal text-gray-400">
                  共 {filteredItems.length} 项
                  {hasActiveFilter && <span className="text-gray-300"> / 全部 {listData.items.length}</span>}
                </span>
              )}
            </CardTitle>
            <span className="text-xs text-gray-400">
              已分配未授权检项 · 超期天数 = {asOf} − 分配日期（自然日）· 倒序 · <span className="text-red-600">红色</span>=超检验时限（无时限按 {DEFAULT_OVERDUE_LIMIT} 天）
            </span>
          </div>
        </CardHeader>
        <CardContent className="px-0 pb-4">
          {listLoading && <p className="text-sm text-gray-400 py-8 text-center">加载中…</p>}
          {listError && <p className="text-sm text-red-500 py-8 text-center">数据加载失败</p>}
          {listData && (
            <>
              {/* 联动筛选框：任一筛选会缩小其他筛选框的可选项 */}
              <div className="flex flex-wrap items-end gap-3 px-4 pb-3">
                {DETAIL_FILTERS.map(({ key, label }) => (
                  <FilterCombo
                    key={key}
                    label={label}
                    value={filters[key]}
                    options={optionsByField[key]}
                    onChange={(v) => setFilter(key, v)}
                  />
                ))}
                {hasActiveFilter && (
                  <button
                    type="button"
                    onClick={clearFilters}
                    className="h-8 shrink-0 rounded-md px-2.5 text-xs text-gray-400 hover:text-gray-600"
                  >
                    清除筛选
                  </button>
                )}
              </div>
              <div className="overflow-x-auto max-h-[640px] overflow-y-auto">
              <table className="w-full text-xs">
                <thead className="sticky top-0 z-10">
                  <tr className="border-b bg-gray-50 text-gray-500">
                    <th className="px-4 py-2 text-right font-medium whitespace-nowrap">超期天数</th>
                    <th className="px-4 py-2 text-left font-medium whitespace-nowrap">状态</th>
                    <th className="px-4 py-2 text-left font-medium whitespace-nowrap">样品编号</th>
                    <th className="px-4 py-2 text-left font-medium whitespace-nowrap">检验员</th>
                    <th className="px-4 py-2 text-left font-medium whitespace-nowrap">项目编号</th>
                    <th className="px-4 py-2 text-left font-medium whitespace-nowrap">样品名称</th>
                    <th className="px-4 py-2 text-left font-medium whitespace-nowrap">批号</th>
                    <th className="px-4 py-2 text-left font-medium whitespace-nowrap">检验方法</th>
                    <th className="px-4 py-2 text-left font-medium whitespace-nowrap">组别</th>
                    <th className="px-4 py-2 text-left font-medium whitespace-nowrap">收样日期</th>
                    <th className="px-4 py-2 text-left font-medium whitespace-nowrap">分配日期</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-100">
                  {filteredItems.length === 0 ? (
                    <tr>
                      <td colSpan={11} className="px-4 py-8 text-center text-gray-400">
                        {hasActiveFilter ? "无匹配数据" : "暂无数据"}
                      </td>
                    </tr>
                  ) : (
                    filteredItems.map((item: OverdueListItem, idx: number) => (
                      <tr key={`${item.sample_id}-${item.method_code}-${idx}`} className="hover:bg-gray-50 transition-colors">
                        <td
                          className={`px-4 py-2 text-right font-semibold whitespace-nowrap ${
                            item.overdue_days != null &&
                            item.overdue_days > (item.target_days ?? DEFAULT_OVERDUE_LIMIT)
                              ? "text-red-600"
                              : "text-gray-800"
                          }`}
                          title={item.target_days != null ? `检验时限 ${item.target_days} 天` : undefined}
                        >
                          {item.overdue_days ?? "—"}
                        </td>
                        <td className="px-4 py-2 whitespace-nowrap">{bucketBadge(item.overdue_bucket)}</td>
                        <td className="px-4 py-2 font-mono text-gray-800 whitespace-nowrap">{item.sample_id ?? "—"}</td>
                        <td className="px-4 py-2 text-gray-600 whitespace-nowrap">{item.starter ?? "—"}</td>
                        <td className="px-4 py-2 text-gray-600 whitespace-nowrap">{item.project_id ?? "—"}</td>
                        <td className="px-4 py-2 text-gray-700 max-w-[160px] truncate" title={item.sample_name ?? ""}>{item.sample_name ?? "—"}</td>
                        <td className="px-4 py-2 text-gray-600 whitespace-nowrap">{item.batch_number ?? "—"}</td>
                        <td className="px-4 py-2 text-gray-600 max-w-[180px] truncate" title={item.method_name ?? ""}>{item.method_name ?? "—"}</td>
                        <td className="px-4 py-2 text-gray-500 whitespace-nowrap">{item.group_id ?? "—"}</td>
                        <td className="px-4 py-2 text-gray-600 whitespace-nowrap">{fmtDate(item.sample_received_dt)}</td>
                        <td className="px-4 py-2 text-gray-600 whitespace-nowrap">{fmtDate(item.assigned_dt)}</td>
                      </tr>
                    ))
                  )}
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
