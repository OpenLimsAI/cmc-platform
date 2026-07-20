"use client"
// 前端路由守卫：未登录一律跳 /login（带回跳地址）。
// 仅 UX 层拦截；数据接口在后端逐一验签，绕过此守卫也拿不到数据。
import { useEffect, useState } from "react"
import { usePathname, useRouter } from "next/navigation"
import { getToken } from "@/lib/auth"

export function AuthGuard({ children }: { children: React.ReactNode }) {
  const pathname = usePathname()
  const router = useRouter()
  const isLogin = pathname.startsWith("/login")
  const [ready, setReady] = useState(false)

  useEffect(() => {
    if (isLogin) {
      setReady(true)
      return
    }
    if (!getToken()) {
      router.replace(
        `/login?redirect=${encodeURIComponent(window.location.pathname + window.location.search)}`
      )
      return
    }
    setReady(true)
  }, [pathname, isLogin, router])

  // 未确认登录态前不渲染内容，避免闪一下再跳登录
  if (!ready && !isLogin) return null
  return <>{children}</>
}
