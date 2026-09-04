"use client"
// 登录页：工号 + 密码 → 后端转发 MDM 校验换 JWT。账号密码在 MDM Portal 统一维护。
export const dynamic = "force-dynamic"

import { Suspense, useState } from "react"
import { useRouter, useSearchParams } from "next/navigation"
import { login } from "@/lib/api"
import { setToken } from "@/lib/auth"
import { logoutReasonText } from "@/lib/cmabSession"
import { Button } from "@/components/ui/button"

function LoginInner() {
  const router = useRouter()
  const searchParams = useSearchParams()
  const [username, setUsername] = useState("")
  const [password, setPassword] = useState("")
  const [error, setError] = useState("")
  const [loading, setLoading] = useState(false)
  const reasonNotice = logoutReasonText(searchParams.get("reason")) // 被会话守卫踢回来时的说明

  const submit = async () => {
    if (loading) return // 防登录中重复提交（连按 Enter 会发多个请求）
    if (!username.trim() || !password) {
      setError("请输入工号和密码")
      return
    }
    setLoading(true)
    setError("")
    try {
      const data = await login(username.trim(), password)
      setToken(data.access_token, data.user) // 同时落 cmab_user，供门户/其他子系统共用
      // redirect 只允许站内相对路径，防开放重定向（"//evil.com" 也要挡）
      const raw = searchParams.get("redirect") || "/dashboard/overview"
      router.replace(raw.startsWith("/") && !raw.startsWith("//") ? raw : "/dashboard/overview")
    } catch (e: unknown) {
      setError(e instanceof Error && e.message ? e.message : "登录失败，请稍后重试")
      setLoading(false)
    }
  }

  return (
    <div className="min-h-[70vh] flex items-center justify-center">
      <div className="bg-white rounded-xl shadow p-8 w-96 space-y-4">
        <div>
          <h1 className="text-lg font-semibold text-gray-800">CMC R&amp;D LIMS 看板登录</h1>
          <p className="text-xs text-gray-400 mt-1">账号与权限在 MDM Portal 统一管理，如无账号请联系管理员</p>
        </div>
        <input
          placeholder="工号"
          value={username}
          autoComplete="username"
          onChange={(e) => setUsername(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && submit()}
          className="w-full border rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-400"
        />
        <input
          type="password"
          placeholder="密码"
          value={password}
          autoComplete="current-password"
          onChange={(e) => setPassword(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && submit()}
          className="w-full border rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-400"
        />
        {reasonNotice && !error && <p className="text-sm text-blue-600">{reasonNotice}</p>}
        {error && <p className="text-sm text-red-500">{error}</p>}
        <Button onClick={submit} disabled={loading} className="w-full">
          {loading ? "登录中…" : "登录"}
        </Button>
      </div>
    </div>
  )
}

export default function LoginPage() {
  return (
    <Suspense>
      <LoginInner />
    </Suspense>
  )
}
