"use client"
// 前端路由守卫：未登录一律跳 /login（带回跳地址）。
// 仅 UX 层拦截；数据接口在后端逐一验签，绕过此守卫也拿不到数据。
import { useEffect, useState } from "react"
import { usePathname, useRouter } from "next/navigation"
import { getToken, withBase } from "@/lib/auth"
import { logoutToLogin, startSessionGuard } from "@/lib/cmabSession"

export function AuthGuard({ children }: { children: React.ReactNode }) {
  const pathname = usePathname()
  const router = useRouter()
  const isLogin = pathname.startsWith("/login")
  const [ready, setReady] = useState(false)

  useEffect(() => {
    if (isLogin) {
      // eslint-disable-next-line react-hooks/set-state-in-effect -- 登录态只能在客户端读 localStorage 确认，挂载后放行是 SSR 水合安全的标准写法
      setReady(true)
      return
    }
    if (!getToken()) {
      // pathname 来自 usePathname（不含 basePath），别用 window.location.pathname（含 /lims，回跳会双前缀）
      router.replace(`/login?redirect=${encodeURIComponent(pathname + window.location.search)}`)
      return
    }
    setReady(true)
  }, [pathname, isLogin, router])

  // 会话守卫（2026-09-04）：空闲超时自动登出 / 通行证快到期静默续期 / 别的标签页或系统登出跟着退
  useEffect(() => {
    if (isLogin || !ready) return
    return startSessionGuard({ onLogout: logoutToLogin(withBase("/login")) })
  }, [isLogin, ready])

  // 未确认登录态前不渲染内容，避免闪一下再跳登录
  if (!ready && !isLogin) return null
  return <>{children}</>
}
