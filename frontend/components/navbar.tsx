"use client"
// 顶部导航栏：各看板页面入口
import Link from "next/link"
import { usePathname, useSearchParams } from "next/navigation"
import { cn } from "@/lib/utils"

const NAV_ITEMS = [
  { href: "/dashboard/overview", label: "检验概况" },
  { href: "/dashboard/cycle-time", label: "检验周期" },
  { href: "/dashboard/overdue", label: "超期未检" },
  { href: "/dashboard/workload", label: "员工工时" },
  { href: "/dashboard/samples", label: "样本总览" },
  { href: "/dashboard/monthly", label: "月度报表" },
]

export function Navbar() {
  const pathname = usePathname()
  const searchParams = useSearchParams()
  const qs = searchParams.toString()

  // dashboard 标签切换时保留 search params（groups、start_date、end_date）
  const dashboardHref = (base: string) => (qs ? `${base}?${qs}` : base)

  return (
    <header className="border-b bg-white shadow-sm">
      <div className="container mx-auto px-4 max-w-7xl h-14 flex items-center gap-8">
        <span className="font-semibold text-gray-900 whitespace-nowrap">TT LIMS</span>
        <nav className="flex gap-1">
          {NAV_ITEMS.map((item) => (
            <Link
              key={item.href}
              href={dashboardHref(item.href)}
              className={cn(
                "px-3 py-1.5 rounded text-sm font-medium transition-colors",
                pathname.startsWith(item.href)
                  ? "bg-blue-50 text-blue-700"
                  : "text-gray-600 hover:text-gray-900 hover:bg-gray-100"
              )}
            >
              {item.label}
            </Link>
          ))}
        </nav>
        <div className="ml-auto">
          <Link
            href="/admin"
            target="_blank"
            rel="noopener noreferrer"
            className="px-3 py-1.5 rounded text-sm font-medium text-gray-400 hover:text-gray-600 hover:bg-gray-100 transition-colors"
          >
            Admin
          </Link>
        </div>
      </div>
    </header>
  )
}
