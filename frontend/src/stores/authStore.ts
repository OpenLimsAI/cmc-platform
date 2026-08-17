import { useSyncExternalStore } from 'react'

// 登录态（抄自 rd-batch-registry 的 authStore 模式：无第三方状态库，localStorage 持久化）。
//
// ★ 全公司统一令牌约定（2026-08-17 拍板，所有子系统前端照此改）：
//   localStorage['cmab_access_token'] = MDM 签发的 access token 原文（JWT 字符串）
//   localStorage['cmab_user']         = MDM 登录响应里的 user 对象 JSON（username/full_name/roles/...）
// 同源（都挂在 5100 之下）时 localStorage 天然共享 → 门户登录一次，各子系统直接读到 → SSO。
// 门户不再替子系统按各家旧 key 写副本；子系统自己改读上面两个 key（设计方案 §7）。

export interface HubUser {
  user_id: number
  username: string // = 员工工号（MDM auth.user.username）
  full_name: string
  department?: string | null
  roles: string[] // MDM 角色码，如 SYS_ADMIN / CMC_USP_RESEARCHER
  permissions: string[]
  must_change_password?: boolean
}

interface AuthState {
  token: string | null
  user: HubUser | null
}

const TOKEN_KEY = 'cmab_access_token'
const USER_KEY = 'cmab_user'

function readUser(): HubUser | null {
  try {
    const raw = localStorage.getItem(USER_KEY)
    return raw ? (JSON.parse(raw) as HubUser) : null
  } catch {
    return null
  }
}

let state: AuthState = {
  token: localStorage.getItem(TOKEN_KEY),
  user: readUser(),
}
const listeners = new Set<() => void>()

export const authStore = {
  get: () => state,
  set(token: string | null, user: HubUser | null) {
    state = { token, user }
    if (token) {
      localStorage.setItem(TOKEN_KEY, token)
      localStorage.setItem(USER_KEY, JSON.stringify(user))
    } else {
      localStorage.removeItem(TOKEN_KEY)
      localStorage.removeItem(USER_KEY)
    }
    listeners.forEach((l) => l())
  },
  subscribe(l: () => void) {
    listeners.add(l)
    return () => listeners.delete(l)
  },
}

export function useAuth(): AuthState {
  return useSyncExternalStore(authStore.subscribe, authStore.get, authStore.get)
}

// 多标签页同步：别的标签登出/重登改了 localStorage，本标签跟着变。
window.addEventListener('storage', (e) => {
  if (e.key === TOKEN_KEY || e.key === USER_KEY) {
    state = { token: localStorage.getItem(TOKEN_KEY), user: readUser() }
    listeners.forEach((l) => l())
  }
})

// 解 JWT 载荷（只用于前端 UX 判断，不验签；真正鉴权在各后端）
export function payloadFromToken(token: string): Record<string, unknown> | null {
  try {
    const part = token.split('.')[1]
    return JSON.parse(atob(part.replace(/-/g, '+').replace(/_/g, '/')))
  } catch {
    return null
  }
}

// 令牌是否已过期（exp 为秒级时间戳；留 30 秒余量）
export function isTokenExpired(token: string | null): boolean {
  if (!token) return true
  const exp = payloadFromToken(token)?.exp
  if (typeof exp !== 'number') return false
  return exp * 1000 < Date.now() + 30_000
}
