"use client"
// 看板左侧边栏：日期范围 + 检验组多选下拉，写入 URL search params 全局共享
import { useEffect, useRef, useState } from "react"
import { useQuery } from "@tanstack/react-query"
import { useRouter, useSearchParams, usePathname } from "next/navigation"
import { fetchGroups, fetchDataFreshness } from "@/lib/api"
import dayjs from "dayjs"

const DEFAULT_GROUP = "TT7"

export function DashboardSidebar() {
  const router = useRouter()
  const pathname = usePathname()
  const searchParams = useSearchParams()
  const [open, setOpen] = useState(false)
  const dropdownRef = useRef<HTMLDivElement>(null)

  const today = dayjs().format("YYYY-MM-DD")
  const defaultStart = dayjs().subtract(30, "day").format("YYYY-MM-DD")

  const urlGroups = searchParams.getAll("groups")
  const urlStart = searchParams.get("start_date") ?? defaultStart
  const urlEnd = searchParams.get("end_date") ?? today

  const { data: groupOptions = [] } = useQuery({
    queryKey: ["groups"],
    queryFn: fetchGroups,
    staleTime: Infinity,
  })

  const { data: freshness } = useQuery({
    queryKey: ["data-freshness"],
    queryFn: fetchDataFreshness,
    refetchInterval: 5 * 60 * 1000,
  })

  // 初次加载：若 URL 无 groups/dates，写入默认值
  useEffect(() => {
    const params = new URLSearchParams(searchParams.toString())
    let changed = false
    if (params.getAll("groups").length === 0) {
      params.append("groups", DEFAULT_GROUP)
      changed = true
    }
    if (!params.has("start_date")) {
      params.set("start_date", defaultStart)
      changed = true
    }
    if (!params.has("end_date")) {
      params.set("end_date", today)
      changed = true
    }
    if (changed) {
      router.replace(`${pathname}?${params.toString()}`, { scroll: false })
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  // 点击外部关闭下拉
  useEffect(() => {
    function handler(e: MouseEvent) {
      if (dropdownRef.current && !dropdownRef.current.contains(e.target as Node)) {
        setOpen(false)
      }
    }
    document.addEventListener("mousedown", handler)
    return () => document.removeEventListener("mousedown", handler)
  }, [])

  const update = (key: string, value: string | string[]) => {
    const params = new URLSearchParams(searchParams.toString())
    params.delete(key)
    if (Array.isArray(value)) {
      value.forEach((v) => params.append(key, v))
    } else {
      params.set(key, value)
    }
    router.replace(`${pathname}?${params.toString()}`, { scroll: false })
  }

  const toggleGroup = (g: string) => {
    const current = searchParams.getAll("groups")
    update("groups", current.includes(g) ? current.filter((v) => v !== g) : [...current, g])
  }

  const selectedLabel =
    urlGroups.length === 0
      ? "全部检验组"
      : urlGroups.length === 1
      ? urlGroups[0]
      : `已选 ${urlGroups.length} 组`

  return (
    <aside className="w-52 shrink-0 border-r bg-white px-4 py-6 space-y-6">
      {/* 统计区间 */}
      <div className="space-y-3">
        <p className="text-xs font-semibold text-gray-400 uppercase tracking-wide">统计区间</p>
        <div className="space-y-2">
          <div>
            <label className="text-xs text-gray-500 mb-1 block">开始日期</label>
            <input
              type="date"
              value={urlStart}
              max={urlEnd}
              onChange={(e) => update("start_date", e.target.value)}
              className="w-full border rounded px-2 py-1 text-xs text-gray-700 bg-white focus:outline-none focus:ring-1 focus:ring-blue-400"
            />
          </div>
          <div>
            <label className="text-xs text-gray-500 mb-1 block">结束日期</label>
            <input
              type="date"
              value={urlEnd}
              min={urlStart}
              max={today}
              onChange={(e) => update("end_date", e.target.value)}
              className="w-full border rounded px-2 py-1 text-xs text-gray-700 bg-white focus:outline-none focus:ring-1 focus:ring-blue-400"
            />
          </div>
        </div>
      </div>

      {/* 检验组 */}
      <div className="space-y-2">
        <p className="text-xs font-semibold text-gray-400 uppercase tracking-wide">检验组</p>
        <div ref={dropdownRef} className="relative">
          <button
            onClick={() => setOpen((v) => !v)}
            className="w-full flex items-center justify-between border rounded px-2 py-1.5 text-xs bg-white text-gray-700 hover:border-blue-400 focus:outline-none focus:ring-1 focus:ring-blue-400 transition-colors"
          >
            <span className="truncate">{selectedLabel}</span>
            <svg
              className={`w-3.5 h-3.5 ml-1 shrink-0 text-gray-400 transition-transform ${open ? "rotate-180" : ""}`}
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
              strokeWidth={2}
            >
              <path strokeLinecap="round" strokeLinejoin="round" d="M19 9l-7 7-7-7" />
            </svg>
          </button>

          {open && (
            <div className="absolute z-50 mt-1 w-full bg-white border rounded shadow-lg py-1">
              <button
                onClick={() => { update("groups", []); setOpen(false) }}
                className={`w-full text-left px-3 py-1.5 text-xs hover:bg-gray-50 ${
                  urlGroups.length === 0 ? "text-blue-600 font-medium" : "text-gray-600"
                }`}
              >
                全部检验组
              </button>
              <div className="border-t my-1" />
              {groupOptions.map((g) => (
                <label
                  key={g}
                  className="flex items-center gap-2 px-3 py-1.5 text-xs hover:bg-gray-50 cursor-pointer"
                >
                  <input
                    type="checkbox"
                    checked={urlGroups.includes(g)}
                    onChange={() => toggleGroup(g)}
                    className="accent-blue-600 shrink-0"
                  />
                  <span className={urlGroups.includes(g) ? "text-blue-700 font-medium" : "text-gray-700"}>
                    {g}
                  </span>
                </label>
              ))}
            </div>
          )}
        </div>

        {urlGroups.length > 0 && (
          <button
            onClick={() => update("groups", [])}
            className="text-xs text-gray-400 hover:text-gray-600 transition-colors"
          >
            清除筛选
          </button>
        )}

        {freshness && (
          <div className="pt-3 mt-3 border-t border-gray-100 text-[11px] text-gray-400 leading-relaxed space-y-0.5">
            <div>数据库：{freshness.db_name}</div>
            <div>
              最后更新：
              {freshness.last_etl_at
                ? dayjs(freshness.last_etl_at).format("MM-DD HH:mm")
                : "—"}
            </div>
          </div>
        )}
      </div>
    </aside>
  )
}
