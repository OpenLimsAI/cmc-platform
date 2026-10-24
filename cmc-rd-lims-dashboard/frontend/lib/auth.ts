// 登录态存储与角色判断。
// token 由 MDM 签发，前端只 base64 解 payload 取展示信息/角色（仅 UX 用途，真鉴权在后端验签）。
export interface AuthUser {
  username: string
  full_name: string | null
  roles: string[]
}

// ★ 全公司统一令牌 key（cmab-hub 统一门户 2026-08-17 拍板）：
//   localStorage['cmab_access_token'] = MDM access token 原文；localStorage['cmab_user'] = 登录返回的 user 对象
//   各子系统同源挂在 5100 之下、都读同一个 key → 门户登录一次，到处免登。
const TOKEN_KEY = "cmab_access_token"
const USER_KEY = "cmab_user"
const LEGACY_TOKEN_KEY = "lims_token" // 旧 key：读到就迁移一次然后删掉
if (typeof window !== "undefined") {
  const old = localStorage.getItem(LEGACY_TOKEN_KEY)
  if (old && !localStorage.getItem(TOKEN_KEY)) localStorage.setItem(TOKEN_KEY, old)
  localStorage.removeItem(LEGACY_TOKEN_KEY)
}

// 子路径前缀（= next.config basePath "/lims"）。Next 的 Link/router 会自动带上，
// 只有直接操作 window.location 时才需要手动补/去前缀。
export const BASE = "/lims"
export const withBase = (p: string) => `${BASE}${p.startsWith("/") ? p : `/${p}`}`
export const stripBase = (p: string) => (p.startsWith(BASE) ? p.slice(BASE.length) || "/" : p)

export const getToken = (): string | null =>
  typeof window === "undefined" ? null : localStorage.getItem(TOKEN_KEY)

export const setToken = (token: string, user?: unknown) => {
  localStorage.setItem(TOKEN_KEY, token)
  if (user) localStorage.setItem(USER_KEY, JSON.stringify(user))
}

export const clearAuth = () => {
  localStorage.removeItem(TOKEN_KEY)
  localStorage.removeItem(USER_KEY)
}

/** 解 JWT payload（不验签）；解析失败返回 null。
 * JWT 是 base64url（-/_、无填充），atob 只认标准 base64，必须先转换；
 * 再按 UTF-8 解码，防 payload 含非转义中文时乱码。 */
export function decodeJwtPayload(token: string): Record<string, unknown> | null {
  try {
    const b64 = token.split(".")[1].replace(/-/g, "+").replace(/_/g, "/")
    const bin = atob(b64.padEnd(b64.length + ((4 - (b64.length % 4)) % 4), "="))
    return JSON.parse(new TextDecoder().decode(Uint8Array.from(bin, (c) => c.charCodeAt(0))))
  } catch {
    return null
  }
}

export function getUser(): AuthUser | null {
  const token = getToken()
  if (!token) return null
  const payload = decodeJwtPayload(token)
  if (!payload) return null
  return {
    username: String(payload.username ?? payload.sub ?? ""),
    full_name: (payload.full_name as string | null) ?? null,
    roles: Array.isArray(payload.roles) ? (payload.roles as string[]) : [],
  }
}

// 角色分级需与后端 app/core/auth.py 保持一致
const ADMIN_ROLES = ["SYS_ADMIN", "CMC_LIMS_ADMIN"]
const EXPORT_ROLES = ["SYS_ADMIN", "CMC_LIMS_ADMIN", "CMC_LIMS_CHEMIST"]

export const isAdmin = (u: AuthUser | null = getUser()): boolean =>
  !!u && u.roles.some((r) => ADMIN_ROLES.includes(r))

export const canExport = (u: AuthUser | null = getUser()): boolean =>
  !!u && u.roles.some((r) => EXPORT_ROLES.includes(r))
