"use client"
// 检验组筛选器：多选，状态写入 URL search params，所有看板页面共享
import { useQuery } from "@tanstack/react-query"
import { useRouter, useSearchParams, usePathname } from "next/navigation"
import { fetchGroups } from "@/lib/api"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { useCallback } from "react"

export function GroupFilter() {
  const router = useRouter()
  const pathname = usePathname()
  const searchParams = useSearchParams()
  const selected = searchParams.getAll("groups")

  const { data: groups = [] } = useQuery({
    queryKey: ["groups"],
    queryFn: fetchGroups,
    staleTime: Infinity, // 检验组列表基本不变
  })

  const toggle = useCallback(
    (g: string) => {
      const params = new URLSearchParams(searchParams.toString())
      const current = params.getAll("groups")
      params.delete("groups")
      if (current.includes(g)) {
        current.filter((v) => v !== g).forEach((v) => params.append("groups", v))
      } else {
        ;[...current, g].forEach((v) => params.append("groups", v))
      }
      router.replace(`${pathname}?${params.toString()}`, { scroll: false })
    },
    [router, pathname, searchParams]
  )

  const clear = useCallback(() => {
    const params = new URLSearchParams(searchParams.toString())
    params.delete("groups")
    router.replace(`${pathname}?${params.toString()}`, { scroll: false })
  }, [router, pathname, searchParams])

  return (
    <div className="flex flex-wrap items-center gap-2 py-3 border-b bg-white px-4">
      <span className="text-xs text-gray-500 whitespace-nowrap">检验组：</span>
      {groups.map((g) => (
        <button
          key={g}
          onClick={() => toggle(g)}
          className={[
            "px-2.5 py-0.5 rounded-full text-xs font-medium border transition-colors",
            selected.includes(g)
              ? "bg-blue-600 text-white border-blue-600"
              : "bg-white text-gray-600 border-gray-300 hover:border-blue-400",
          ].join(" ")}
        >
          {g}
        </button>
      ))}
      {selected.length > 0 && (
        <Button variant="ghost" size="sm" className="h-6 text-xs text-gray-400" onClick={clear}>
          清除
        </Button>
      )}
      {selected.length > 0 && (
        <Badge variant="secondary" className="text-xs">
          已选 {selected.length} 组
        </Badge>
      )}
    </div>
  )
}
