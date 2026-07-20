"use client"
// 顶部导航栏：各看板页面入口 + 登录用户信息/退出；Admin 入口仅管理员角色可见
import { useEffect, useState } from "react"
import Link from "next/link"
import { usePathname, useSearchParams } from "next/navigation"
import { logout } from "@/lib/api"
import { getUser, isAdmin, type AuthUser } from "@/lib/auth"
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
  // localStorage 只能在客户端读，挂载后再取用户，避免 SSR 水合不一致
  const [user, setUser] = useState<AuthUser | null>(null)
  useEffect(() => {
    setUser(getUser())
  }, [pathname])

  // dashboard 标签切换时保留 search params（groups、start_date、end_date）
  const dashboardHref = (base: string) => (qs ? `${base}?${qs}` : base)

  // 登录页不显示导航栏
  if (pathname.startsWith("/login")) return null

  const handleLogout = async () => {
    await logout()
    window.location.href = "/login"
  }

  return (
    <header className="border-b bg-white shadow-sm">
      <div className="container mx-auto px-4 max-w-7xl h-14 flex items-center gap-8">
        <span className="font-semibold text-gray-900 whitespace-nowrap">CMC R&amp;D LIMS</span>
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
        <div className="ml-auto flex items-center gap-2">
          {isAdmin(user) && (
            <Link
              href="/admin"
              target="_blank"
              rel="noopener noreferrer"
              className="px-3 py-1.5 rounded text-sm font-medium text-gray-400 hover:text-gray-600 hover:bg-gray-100 transition-colors"
            >
              Admin
            </Link>
          )}
          {user && (
            <>
              <span className="text-sm text-gray-500">{user.full_name || user.username}</span>
              <button
                onClick={handleLogout}
                className="px-2 py-1.5 rounded text-sm text-gray-400 hover:text-gray-600 hover:bg-gray-100 transition-colors"
              >
                退出
              </button>
            </>
          )}
        </div>
      </div>
    </header>
  )
}
