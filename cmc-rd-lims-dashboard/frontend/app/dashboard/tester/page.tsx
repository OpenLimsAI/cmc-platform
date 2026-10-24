"use client"
// 检验员工作台：单个检验员的在手检项 / 超时限 / 本月产出（口径见 docs/tester_workbench.md）
// 左侧边栏的日期范围对本页不生效；检验组只用来缩小检验员下拉名单。
export const dynamic = "force-dynamic"
import { useEffect, useMemo, useState } from "react"
import { useQuery } from "@tanstack/react-query"
import { usePathname, useRouter, useSearchParams } from "next/navigation"
import dayjs from "dayjs"
import ReactECharts from "echarts-for-react"
import {
  fetchTesterList,
  fetchTesterMonthly,
  fetchTesterSummary,
  fetchTesterTasks,
  type TesterTaskItem,
} from "@/lib/api"
import { getUser } from "@/lib/auth"
import { downloadCSV } from "@/lib/utils"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { StatCard } from "@/components/stat-card"

type TaskFilter = "all" | "over" | "soon" | "unauthorized"
type ViewMode = "test" | "sample"

const FILTERS: { key: TaskFilter; label: string }[] = [
  { key: "all", label: "全部" },
  { key: "over", label: "已超时限" },
  { key: "soon", label: "即将超时限" },
  { key: "unauthorized", label: "待授权" },
]

const fmtDate = (v: string | null) => (v ? dayjs(v).format("YYYY-MM-DD") : "—")

function bucketBadge(b: TesterTaskItem["bucket"]) {
  return b === "unauthorized" ? (
    <span className="px-1.5 py-0.5 text-xs rounded bg-blue-100 text-blue-700 whitespace-nowrap">检完待授权</span>
  ) : (
    <span className="px-1.5 py-0.5 text-xs rounded bg-yellow-100 text-yellow-700 whitespace-nowrap">进行中</span>
  )
}

// 剩余工作日：负数 = 已超
function remainingCell(t: { remaining_biz_days: number; is_over_target: boolean; is_due_soon: boolean }) {
  if (t.is_over_target)
    return <span className="font-semibold text-red-600">超 {-t.remaining_biz_days} 天</span>
  if (t.is_due_soon)
    return <span className="font-semibold text-amber-600">{t.remaining_biz_days} 天</span>
  return <span className="text-gray-700">{t.remaining_biz_days} 天</span>
}

const rowClass = (over: boolean, soon: boolean) =>
  over ? "bg-red-50 hover:bg-red-100" : soon ? "bg-amber-50 hover:bg-amber-100" : "hover:bg-gray-50"

// 「按样品看」：同一样品的在手检项合成一行
interface SampleRow {
  sample_id: string
  project_id: string | null
  sample_name: string | null
  batch_number: string | null
  sample_received_dt: string | null
  tests: TesterTaskItem[]
  over_n: number
  soon_n: number
  unauthorized_n: number
  min_remaining: number
  is_over_target: boolean
  is_due_soon: boolean
}

function groupBySample(items: TesterTaskItem[]): SampleRow[] {
  const map = new Map<string, SampleRow>()
  for (const t of items) {
    const key = t.sample_id ?? "（无样品号）"
    let row = map.get(key)
    if (!row) {
      row = {
        sample_id: key,
        project_id: t.project_id,
        sample_name: t.sample_name,
        batch_number: t.batch_number,
        sample_received_dt: t.sample_received_dt,
        tests: [],
        over_n: 0,
        soon_n: 0,
        unauthorized_n: 0,
        min_remaining: Number.POSITIVE_INFINITY,
        is_over_target: false,
        is_due_soon: false,
      }
      map.set(key, row)
    }
    row.tests.push(t)
    if (t.is_over_target) row.over_n++
    if (t.is_due_soon) row.soon_n++
    if (t.bucket === "unauthorized") row.unauthorized_n++
    row.min_remaining = Math.min(row.min_remaining, t.remaining_biz_days)
  }
  const rows = [...map.values()]
  for (const r of rows) {
    r.is_over_target = r.over_n > 0
    r.is_due_soon = !r.is_over_target && r.soon_n > 0
  }
  // 最急的样品在前：先按收样日，再按最差剩余天数
  return rows.sort(
    (a, b) =>
      (a.sample_received_dt ?? "").localeCompare(b.sample_received_dt ?? "") ||
      a.min_remaining - b.min_remaining
  )
}

export default function TesterPage() {
  const router = useRouter()
  const pathname = usePathname()
  const searchParams = useSearchParams()
  const groups = searchParams.getAll("groups")
  const urlTester = searchParams.get("tester")

  const today = dayjs().format("YYYY-MM-DD")
  const [soonDays, setSoonDays] = useState(2)
  const [defaultTarget, setDefaultTarget] = useState(14)
  const [filter, setFilter] = useState<TaskFilter>("all")
  const [viewMode, setViewMode] = useState<ViewMode>("test")

  // 登录人工号（localStorage 只能客户端读，挂载后再取，避免 SSR 水合不一致）
  const [me, setMe] = useState<string | null>(null)
  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- 客户端挂载后读 localStorage 的标准写法
    setMe(getUser()?.username ?? null)
  }, [])

  const listQuery = useQuery({
    queryKey: ["tester-list", groups],
    queryFn: () => fetchTesterList({ groups: groups.length ? groups : undefined }),
    staleTime: 5 * 60 * 1000,
  })
  const testers = useMemo(() => listQuery.data ?? [], [listQuery.data])

  // 默认选中：URL 指定 > 登录人自己（在名单里） > 名单第一位
  const selectedTester = useMemo(() => {
    if (urlTester) return urlTester
    if (!testers.length) return null
    if (me && testers.some((t) => t.employee_id === me)) return me
    return testers[0].employee_id
  }, [urlTester, testers, me])

  const selectTester = (id: string) => {
    const params = new URLSearchParams(searchParams.toString())
    params.set("tester", id)
    router.replace(`${pathname}?${params.toString()}`, { scroll: false })
    setFilter("all")
  }

  const q = selectedTester
    ? { tester: selectedTester, as_of: today, default_target: defaultTarget, soon_days: soonDays }
    : null

  const summaryQuery = useQuery({
    queryKey: ["tester-summary", q],
    queryFn: () => fetchTesterSummary(q!),
    enabled: !!q,
  })
  const tasksQuery = useQuery({
    queryKey: ["tester-tasks", q],
    queryFn: () => fetchTesterTasks(q!),
    enabled: !!q,
  })
  const monthlyQuery = useQuery({
    queryKey: ["tester-monthly", selectedTester],
    queryFn: () => fetchTesterMonthly({ tester: selectedTester!, months: 6 }),
    enabled: !!selectedTester,
  })

  const summary = summaryQuery.data
  const allTasks = useMemo(() => tasksQuery.data?.items ?? [], [tasksQuery.data])

  const counts = useMemo(
    () => ({
      all: allTasks.length,
      over: allTasks.filter((t) => t.is_over_target).length,
      soon: allTasks.filter((t) => t.is_due_soon).length,
      unauthorized: allTasks.filter((t) => t.bucket === "unauthorized").length,
    }),
    [allTasks]
  )

  const filteredTasks = useMemo(
    () =>
      allTasks.filter((t) =>
        filter === "all"
          ? true
          : filter === "over"
          ? t.is_over_target
          : filter === "soon"
          ? t.is_due_soon
          : t.bucket === "unauthorized"
      ),
    [allTasks, filter]
  )
  const sampleRows = useMemo(() => groupBySample(filteredTasks), [filteredTasks])

  // 显示名：名单里的姓名 > summary 里的姓名 > 工号
  const selectedOption = testers.find((t) => t.employee_id === selectedTester)
  const displayName = selectedOption?.employee_name ?? summary?.employee_name ?? selectedTester ?? ""

  // 在手检项按方法（堆叠：已超 / 即将 / 正常）
  const methodChartOption = useMemo(() => {
    if (!allTasks.length) return null
    const agg = new Map<string, { over: number; soon: number; ok: number }>()
    for (const t of allTasks) {
      const k = t.method_name ?? t.method_code ?? "（未知）"
      const a = agg.get(k) ?? { over: 0, soon: 0, ok: 0 }
      if (t.is_over_target) a.over++
      else if (t.is_due_soon) a.soon++
      else a.ok++
      agg.set(k, a)
    }
    const rows = [...agg.entries()]
      .map(([name, v]) => ({ name, ...v, total: v.over + v.soon + v.ok }))
      .sort((a, b) => a.total - b.total) // ECharts 类目轴自下而上，升序排让最多的在最上面
    return {
      height: Math.max(220, rows.length * 26 + 60),
      option: {
        tooltip: { trigger: "axis", axisPointer: { type: "shadow" } },
        legend: { bottom: 0, textStyle: { fontSize: 10 } },
        grid: { left: 200, right: 40, top: 8, bottom: 52 },
        xAxis: { type: "value", minInterval: 1, axisLabel: { fontSize: 10 } },
        yAxis: {
          type: "category",
          data: rows.map((r) => r.name),
          axisLabel: { fontSize: 10, width: 190, overflow: "truncate" },
        },
        series: [
          { name: "已超时限", type: "bar", stack: "t", data: rows.map((r) => r.over), itemStyle: { color: "#ef4444" } },
          { name: "即将超时限", type: "bar", stack: "t", data: rows.map((r) => r.soon), itemStyle: { color: "#f59e0b" } },
          {
            name: "正常",
            type: "bar",
            stack: "t",
            data: rows.map((r) => r.ok),
            itemStyle: { color: "#3b82f6" },
            label: {
              show: true,
              position: "right",
              fontSize: 10,
              formatter: (p: { dataIndex: number }) => String(rows[p.dataIndex].total),
            },
          },
        ],
      },
    }
  }, [allTasks])

  // 近 6 个月：柱 = 完成检项数，线 = 标准工时；tooltip 带平均周期
  const monthlyOption = useMemo(() => {
    const items = monthlyQuery.data?.items ?? []
    if (!items.length) return null
    return {
      tooltip: {
        trigger: "axis",
        formatter: (params: { name: string }[]) => {
          const it = items.find((d) => d.ym === params[0]?.name)
          if (!it) return ""
          return `<b>${it.ym}</b><br/>完成检项：${it.completed_n}<br/>标准工时：${it.std_hours.toFixed(1)} 小时<br/>平均周期：${
            it.avg_cycle_days != null ? it.avg_cycle_days.toFixed(1) + " 工作日" : "—"
          }`
        },
      },
      legend: { bottom: 0, textStyle: { fontSize: 10 } },
      grid: { left: 44, right: 48, top: 16, bottom: 36 },
      xAxis: { type: "category", data: items.map((d) => d.ym), axisLabel: { fontSize: 10 } },
      yAxis: [
        { type: "value", name: "检项", minInterval: 1, axisLabel: { fontSize: 10 } },
        { type: "value", name: "小时", axisLabel: { fontSize: 10 }, splitLine: { show: false } },
      ],
      series: [
        {
          name: "完成检项",
          type: "bar",
          data: items.map((d) => d.completed_n),
          itemStyle: { color: "#28B463", borderRadius: [3, 3, 0, 0] },
          label: { show: true, position: "top", fontSize: 10 },
        },
        {
          name: "标准工时",
          type: "line",
          yAxisIndex: 1,
          data: items.map((d) => d.std_hours),
          itemStyle: { color: "#1B6EC2" },
          lineStyle: { color: "#1B6EC2", width: 2 },
          symbol: "circle",
          symbolSize: 6,
        },
      ],
    }
  }, [monthlyQuery.data])

  const cycleDelta =
    summary && summary.month_avg_cycle_days != null && summary.prev_month_avg_cycle_days != null
      ? summary.month_avg_cycle_days - summary.prev_month_avg_cycle_days
      : null

  const exportCsv = () => {
    if (viewMode === "test") {
      downloadCSV(
        filteredTasks.map((t) => ({
          样品编号: t.sample_id ?? "",
          项目编号: t.project_id ?? "",
          样品名称: t.sample_name ?? "",
          批号: t.batch_number ?? "",
          检验方法: t.method_name ?? "",
          收样日期: fmtDate(t.sample_received_dt),
          分配日期: fmtDate(t.assigned_dt),
          "已耗时(工作日)": t.elapsed_biz_days,
          "时限(工作日)": t.target_days,
          "剩余(工作日)": t.remaining_biz_days,
          状态: t.bucket === "unauthorized" ? "检完待授权" : "进行中",
          是否超时限: t.is_over_target ? "是" : "",
        })),
        `tester_${selectedTester}_tasks_${today}.csv`
      )
    } else {
      downloadCSV(
        sampleRows.map((r) => ({
          样品编号: r.sample_id,
          项目编号: r.project_id ?? "",
          样品名称: r.sample_name ?? "",
          批号: r.batch_number ?? "",
          收样日期: fmtDate(r.sample_received_dt),
          剩余检项数: r.tests.length,
          已超时限检项: r.over_n,
          待授权检项: r.unauthorized_n,
          "最紧剩余(工作日)": r.min_remaining,
          检验方法: r.tests.map((t) => t.method_name ?? t.method_code ?? "").join("；"),
        })),
        `tester_${selectedTester}_samples_${today}.csv`
      )
    }
  }

  const isLoading = listQuery.isLoading || (!!q && (summaryQuery.isLoading || tasksQuery.isLoading))
  const isError = listQuery.isError || summaryQuery.isError || tasksQuery.isError

  return (
    <div className="space-y-6">
      {/* 标题 + 选人 + 阈值 */}
      <div className="flex flex-col gap-3 lg:flex-row lg:items-end lg:justify-between">
        <div>
          <h1 className="text-xl font-semibold text-gray-900">
            检验员工作台{displayName && <span className="ml-2 text-indigo-600">· {displayName}</span>}
          </h1>
          <p className="text-xs text-gray-500 mt-1">
            基准日 {today} · 在手 = 分配给本人、尚未授权放行的检项（排除取消/未到样）
            {groups.length > 0 && <span className="ml-2 text-blue-600">· 名单已按 {groups.join("、")} 过滤</span>}
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-4 text-sm">
          <label className="flex items-center gap-2 text-gray-600 whitespace-nowrap">
            检验员
            <select
              value={selectedTester ?? ""}
              onChange={(e) => selectTester(e.target.value)}
              className="min-w-[180px] border rounded px-2 py-1 text-sm text-gray-800 bg-white focus:outline-none focus:ring-1 focus:ring-blue-400"
            >
              {selectedTester && !selectedOption && (
                <option value={selectedTester}>{displayName}（不在当前名单）</option>
              )}
              {testers.map((t) => (
                <option key={t.employee_id} value={t.employee_id}>
                  {t.employee_name ?? t.employee_id}
                  {t.employee_id === me ? "（我）" : ""}
                  {t.pending_n > 0 ? ` · 在手 ${t.pending_n}` : ""}
                </option>
              ))}
            </select>
          </label>
          <label className="flex items-center gap-1.5 text-gray-600 whitespace-nowrap" title="剩余工作日 ≤ 此值即算「即将超时限」">
            即将超时限 ≤
            <input
              type="number"
              min={0}
              max={30}
              value={soonDays}
              onChange={(e) => setSoonDays(Math.max(0, parseInt(e.target.value) || 0))}
              className="w-14 border rounded px-2 py-1 text-sm text-gray-700 focus:outline-none focus:ring-1 focus:ring-blue-400"
            />
            工作日
          </label>
          <label className="flex items-center gap-1.5 text-gray-600 whitespace-nowrap" title="方法未设检验时限时按此值判断">
            默认时限
            <input
              type="number"
              min={1}
              max={365}
              value={defaultTarget}
              onChange={(e) => setDefaultTarget(Math.max(1, parseInt(e.target.value) || 1))}
              className="w-14 border rounded px-2 py-1 text-sm text-gray-700 focus:outline-none focus:ring-1 focus:ring-blue-400"
            />
            工作日
          </label>
        </div>
      </div>

      {isLoading && <p className="text-sm text-gray-400">加载中…</p>}
      {isError && <p className="text-sm text-red-500">数据加载失败，请确认后端服务已启动</p>}
      {!listQuery.isLoading && testers.length === 0 && !urlTester && (
        <p className="text-sm text-gray-400">当前检验组下没有检验员记录，请在左侧切换检验组或选「全部检验组」。</p>
      )}

      {/* 6 张汇总卡 */}
      {summary && (
        <>
          <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 xl:grid-cols-6">
            <StatCard
              label="在手检项"
              value={summary.pending_n.toLocaleString()}
              sub={`其中待授权 ${summary.unauthorized_n}`}
              scheme="blue"
            />
            <StatCard
              label="已超时限"
              value={summary.over_target_n.toLocaleString()}
              sub={summary.pending_n > 0 ? `占在手 ${((summary.over_target_n / summary.pending_n) * 100).toFixed(0)}%` : "—"}
              scheme={summary.over_target_n > 0 ? "red" : "green"}
            />
            <StatCard
              label="即将超时限"
              value={summary.due_soon_n.toLocaleString()}
              sub={`剩余 ≤ ${soonDays} 个工作日`}
              scheme={summary.due_soon_n > 0 ? "orange" : "green"}
            />
            <StatCard
              label="本月已完成"
              value={summary.month_completed_n.toLocaleString()}
              sub={`上月整月 ${summary.prev_month_completed_n}`}
              scheme="green"
            />
            <StatCard label="本月标准工时" value={summary.month_std_hours.toFixed(1)} unit="小时" scheme="lapis" />
            <StatCard
              label="本月平均周期"
              value={summary.month_avg_cycle_days != null ? summary.month_avg_cycle_days.toFixed(1) : "—"}
              unit={summary.month_avg_cycle_days != null ? "工作日" : undefined}
              sub={
                cycleDelta != null
                  ? `较上月 ${cycleDelta > 0 ? "+" : ""}${cycleDelta.toFixed(1)}${cycleDelta > 0.5 ? " ↑" : cycleDelta < -0.5 ? " ↓" : ""}`
                  : "上月无数据"
              }
              scheme={cycleDelta != null && cycleDelta > 0.5 ? "red" : cycleDelta != null && cycleDelta < -0.5 ? "green" : "purple"}
            />
          </div>
          <p className="text-xs text-gray-400">
            口径：超时限 = 收样至今工作日 &gt; 该方法检验时限（未设则 {defaultTarget} 个工作日），与「检验周期」页一致；
            本月 = {dayjs(today).startOf("month").format("MM-DD")} ~ {dayjs(today).format("MM-DD")}，按授权放行日计；
            在手最老一条收样于 {summary.oldest_received_dt ? fmtDate(summary.oldest_received_dt) : "—"}。
          </p>
        </>
      )}

      {/* 在手任务清单 */}
      {tasksQuery.data && (
        <Card>
          <CardHeader className="pb-2">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <CardTitle className="text-sm font-medium text-gray-700">
                在手任务清单
                <span className="ml-2 text-xs font-normal text-gray-400">
                  {viewMode === "test" ? `${filteredTasks.length} 项检项` : `${sampleRows.length} 个样品 / ${filteredTasks.length} 项检项`}
                  {filter !== "all" && <span className="text-gray-300"> / 全部 {allTasks.length}</span>}
                </span>
              </CardTitle>
              <div className="flex flex-wrap items-center gap-3">
                <div className="flex rounded border text-xs overflow-hidden">
                  {FILTERS.map((f, idx) => (
                    <button
                      key={f.key}
                      onClick={() => setFilter(f.key)}
                      className={`px-2.5 py-1 transition-colors ${idx > 0 ? "border-l" : ""} ${
                        filter === f.key ? "bg-indigo-600 text-white" : "text-gray-500 hover:bg-gray-50"
                      }`}
                    >
                      {f.label}
                      <span className={`ml-1 tabular-nums ${filter === f.key ? "text-indigo-200" : "text-gray-400"}`}>
                        {counts[f.key]}
                      </span>
                    </button>
                  ))}
                </div>
                <div className="flex rounded border text-xs overflow-hidden">
                  {(["test", "sample"] as ViewMode[]).map((m, idx) => (
                    <button
                      key={m}
                      onClick={() => setViewMode(m)}
                      className={`px-2.5 py-1 transition-colors ${idx > 0 ? "border-l" : ""} ${
                        viewMode === m ? "bg-gray-700 text-white" : "text-gray-500 hover:bg-gray-50"
                      }`}
                    >
                      {m === "test" ? "按检项" : "按样品"}
                    </button>
                  ))}
                </div>
                <button
                  onClick={exportCsv}
                  disabled={filteredTasks.length === 0}
                  className="text-xs text-indigo-600 hover:text-indigo-800 border border-indigo-200 rounded px-2 py-0.5 transition-colors disabled:opacity-40"
                >
                  导出 CSV
                </button>
              </div>
            </div>
            <p className="text-xs text-gray-400 mt-1">
              最老收样的在前 · <span className="inline-block w-3 h-3 align-middle rounded-sm bg-red-100 border border-red-200" /> 已超时限
              <span className="ml-2 inline-block w-3 h-3 align-middle rounded-sm bg-amber-100 border border-amber-200" /> 即将超时限
              · 时限后带 * 表示该方法未设时限，按默认 {defaultTarget} 天
            </p>
          </CardHeader>
          <CardContent className="px-0 pb-4">
            <div className="overflow-x-auto max-h-[640px] overflow-y-auto">
              {viewMode === "test" ? (
                <table className="w-full text-xs">
                  <thead className="sticky top-0 z-10 bg-gray-50">
                    <tr className="border-b bg-gray-50 text-gray-500">
                      <th className="px-3 py-2 text-left font-medium whitespace-nowrap">样品编号</th>
                      <th className="px-3 py-2 text-left font-medium whitespace-nowrap">项目</th>
                      <th className="px-3 py-2 text-left font-medium whitespace-nowrap">样品名称</th>
                      <th className="px-3 py-2 text-left font-medium whitespace-nowrap">批号</th>
                      <th className="px-3 py-2 text-left font-medium whitespace-nowrap">检验方法</th>
                      <th className="px-3 py-2 text-left font-medium whitespace-nowrap">收样日</th>
                      <th className="px-3 py-2 text-left font-medium whitespace-nowrap">分配日</th>
                      <th className="px-3 py-2 text-right font-medium whitespace-nowrap">已耗时</th>
                      <th className="px-3 py-2 text-right font-medium whitespace-nowrap">时限</th>
                      <th className="px-3 py-2 text-right font-medium whitespace-nowrap">剩余</th>
                      <th className="px-3 py-2 text-left font-medium whitespace-nowrap">状态</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-100">
                    {filteredTasks.length === 0 ? (
                      <tr>
                        <td colSpan={11} className="px-4 py-8 text-center text-gray-400">
                          {allTasks.length === 0 ? "当前没有在手检项 🎉" : "无匹配数据"}
                        </td>
                      </tr>
                    ) : (
                      filteredTasks.map((t) => (
                        <tr key={t.test_id} className={`transition-colors ${rowClass(t.is_over_target, t.is_due_soon)}`}>
                          <td className="px-3 py-2 font-mono text-gray-800 whitespace-nowrap">{t.sample_id ?? "—"}</td>
                          <td className="px-3 py-2 text-gray-600 whitespace-nowrap">{t.project_id ?? "—"}</td>
                          <td className="px-3 py-2 text-gray-700 max-w-[160px] truncate" title={t.sample_name ?? ""}>{t.sample_name ?? "—"}</td>
                          <td className="px-3 py-2 text-gray-600 whitespace-nowrap">{t.batch_number ?? "—"}</td>
                          <td className="px-3 py-2 text-gray-700 max-w-[200px] truncate" title={t.method_name ?? ""}>{t.method_name ?? "—"}</td>
                          <td className="px-3 py-2 text-gray-600 whitespace-nowrap">{fmtDate(t.sample_received_dt)}</td>
                          <td className="px-3 py-2 text-gray-600 whitespace-nowrap">{fmtDate(t.assigned_dt)}</td>
                          <td className="px-3 py-2 text-right tabular-nums text-gray-700 whitespace-nowrap">{t.elapsed_biz_days} 天</td>
                          <td className="px-3 py-2 text-right tabular-nums text-gray-500 whitespace-nowrap" title={t.target_is_default ? "方法未设时限，按默认" : undefined}>
                            {t.target_days}{t.target_is_default ? "*" : ""}
                          </td>
                          <td className="px-3 py-2 text-right tabular-nums whitespace-nowrap">{remainingCell(t)}</td>
                          <td className="px-3 py-2">{bucketBadge(t.bucket)}</td>
                        </tr>
                      ))
                    )}
                  </tbody>
                </table>
              ) : (
                <table className="w-full text-xs">
                  <thead className="sticky top-0 z-10 bg-gray-50">
                    <tr className="border-b bg-gray-50 text-gray-500">
                      <th className="px-3 py-2 text-left font-medium whitespace-nowrap">样品编号</th>
                      <th className="px-3 py-2 text-left font-medium whitespace-nowrap">项目</th>
                      <th className="px-3 py-2 text-left font-medium whitespace-nowrap">样品名称</th>
                      <th className="px-3 py-2 text-left font-medium whitespace-nowrap">批号</th>
                      <th className="px-3 py-2 text-left font-medium whitespace-nowrap">收样日</th>
                      <th className="px-3 py-2 text-right font-medium whitespace-nowrap">剩余检项</th>
                      <th className="px-3 py-2 text-right font-medium whitespace-nowrap">已超</th>
                      <th className="px-3 py-2 text-right font-medium whitespace-nowrap">待授权</th>
                      <th className="px-3 py-2 text-right font-medium whitespace-nowrap">最紧剩余</th>
                      <th className="px-3 py-2 text-left font-medium">待做方法</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-100">
                    {sampleRows.length === 0 ? (
                      <tr>
                        <td colSpan={10} className="px-4 py-8 text-center text-gray-400">
                          {allTasks.length === 0 ? "当前没有在手检项 🎉" : "无匹配数据"}
                        </td>
                      </tr>
                    ) : (
                      sampleRows.map((r) => (
                        <tr key={r.sample_id} className={`transition-colors ${rowClass(r.is_over_target, r.is_due_soon)}`}>
                          <td className="px-3 py-2 font-mono text-gray-800 whitespace-nowrap">{r.sample_id}</td>
                          <td className="px-3 py-2 text-gray-600 whitespace-nowrap">{r.project_id ?? "—"}</td>
                          <td className="px-3 py-2 text-gray-700 max-w-[160px] truncate" title={r.sample_name ?? ""}>{r.sample_name ?? "—"}</td>
                          <td className="px-3 py-2 text-gray-600 whitespace-nowrap">{r.batch_number ?? "—"}</td>
                          <td className="px-3 py-2 text-gray-600 whitespace-nowrap">{fmtDate(r.sample_received_dt)}</td>
                          <td className="px-3 py-2 text-right tabular-nums font-medium text-gray-800">{r.tests.length}</td>
                          <td className={`px-3 py-2 text-right tabular-nums ${r.over_n > 0 ? "text-red-600 font-semibold" : "text-gray-400"}`}>{r.over_n}</td>
                          <td className={`px-3 py-2 text-right tabular-nums ${r.unauthorized_n > 0 ? "text-blue-700" : "text-gray-400"}`}>{r.unauthorized_n}</td>
                          <td className="px-3 py-2 text-right tabular-nums whitespace-nowrap">
                            {remainingCell({ remaining_biz_days: r.min_remaining, is_over_target: r.is_over_target, is_due_soon: r.is_due_soon })}
                          </td>
                          <td className="px-3 py-2 text-gray-600">
                            <div className="flex flex-wrap gap-1">
                              {r.tests.map((t) => (
                                <span
                                  key={t.test_id}
                                  title={`${t.method_name ?? ""} · 剩余 ${t.remaining_biz_days} 工作日`}
                                  className={`px-1.5 py-0.5 rounded border text-[11px] whitespace-nowrap ${
                                    t.is_over_target
                                      ? "bg-red-100 border-red-200 text-red-700"
                                      : t.is_due_soon
                                      ? "bg-amber-100 border-amber-200 text-amber-700"
                                      : t.bucket === "unauthorized"
                                      ? "bg-blue-50 border-blue-200 text-blue-700"
                                      : "bg-white border-gray-200 text-gray-600"
                                  }`}
                                >
                                  {t.method_name ?? t.method_code ?? "—"}
                                </span>
                              ))}
                            </div>
                          </td>
                        </tr>
                      ))
                    )}
                  </tbody>
                </table>
              )}
            </div>
          </CardContent>
        </Card>
      )}

      {/* 辅助：在手按方法 + 近 6 月趋势 */}
      {selectedTester && (
        <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
          <Card>
            <CardHeader className="pb-1">
              <CardTitle className="text-sm font-medium text-gray-700">在手检项按方法汇总</CardTitle>
              <p className="text-xs text-gray-400">同一方法可以攒在一起上仪器；数字为该方法在手总数</p>
            </CardHeader>
            <CardContent>
              {methodChartOption ? (
                <ReactECharts option={methodChartOption.option} style={{ height: methodChartOption.height }} />
              ) : (
                <p className="text-sm text-gray-400 py-8 text-center">当前没有在手检项</p>
              )}
            </CardContent>
          </Card>
          <Card>
            <CardHeader className="pb-1">
              <CardTitle className="text-sm font-medium text-gray-700">近 6 个月完成趋势</CardTitle>
              <p className="text-xs text-gray-400">柱 = 当月授权放行的检项数，线 = 标准工时（小时）；悬停看当月平均周期</p>
            </CardHeader>
            <CardContent>
              {monthlyOption ? (
                <ReactECharts option={monthlyOption} style={{ height: 300 }} />
              ) : (
                <p className="text-sm text-gray-400 py-8 text-center">{monthlyQuery.isLoading ? "加载中…" : "暂无数据"}</p>
              )}
            </CardContent>
          </Card>
        </div>
      )}
    </div>
  )
}
