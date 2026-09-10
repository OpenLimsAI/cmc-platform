/**
 * CMAB 统一会话模块（全公司各子系统前端抄这一份，母本在 cmab-hub/frontend/src/shared/cmabSession.ts）
 *
 * 做四件事，全部直接打 MDM（同源挂在门户 5100 之下，路径 /mdm/api/v1，不写死 host:端口）：
 *   1. mdmLogin / mdmLogout / mdmRefresh / mdmSessionPolicy —— 登录、登出、静默续期、读会话策略
 *   2. 令牌落盘用全公司统一 key：localStorage['cmab_access_token'] / ['cmab_user']；换了新令牌广播 'cmab-token-changed'
 *   3. 活动时间共用 localStorage['cmab_last_active']：在任一系统里有动作，其他系统都算活跃
 *   4. startSessionGuard —— 空闲超时自动登出 + 通行证快到期静默续期 + 多标签页/多系统同步
 *
 * 会话规则由 MDM 系统管理 → 会话策略 在线配置（通行证 15 分钟 / 空闲 30 分钟 / 硬上限 12 小时，展示模式放宽），
 * 前端只读 GET /mdm/api/v1/auth/session-policy，不写死数字。
 *
 * 纯 TS、不依赖 React/axios，Vite 与 Next 项目都能直接用；只在浏览器端调用（Next 里放 useEffect / "use client"）。
 * 2026-09-04 起。
 */

export const TOKEN_KEY = 'cmab_access_token'
export const USER_KEY = 'cmab_user'
export const LAST_ACTIVE_KEY = 'cmab_last_active'
export const TOKEN_CHANGED_EVENT = 'cmab-token-changed'
export const MDM_API = '/mdm/api/v1'

export type LogoutReason = 'idle' | 'expired' | 'other-tab'

/**
 * 拉不到会话策略时的保守兜底（与 MDM 默认值一致：通行证 15 分钟 / 空闲 30 分钟）。
 * 不写进 policy 变量，这样后续 tick 仍会继续尝试取真实策略。
 */
const FALLBACK_POLICY = { access_token_minutes: 15, idle_timeout_minutes: 30 }

export interface MdmUser {
  user_id: number
  username: string // = 员工工号
  full_name: string
  department?: string | null
  title?: string | null
  roles: string[]
  permissions?: string[]
  must_change_password?: boolean
}

export interface MdmLoginResult {
  access_token: string
  token_type: string
  expires_in: number
  user: MdmUser
}

export interface SessionPolicy {
  access_token_minutes: number
  idle_timeout_minutes: number
  absolute_max_hours: number
  display_mode: boolean
}

/** MDM 统一错误：message 是后端原话（如「长时间未操作，已自动退出」/「工号或密码错误」） */
export class MdmError extends Error {
  status: number
  type: string | null
  constructor(message: string, status: number, type: string | null = null) {
    super(message)
    this.name = 'MdmError'
    this.status = status
    this.type = type
  }
}

// ---------------- localStorage 安全读写 ----------------

function safeGet(key: string): string | null {
  try {
    return localStorage.getItem(key)
  } catch {
    return null
  }
}
function safeSet(key: string, value: string): void {
  try {
    localStorage.setItem(key, value)
  } catch {
    /* ignore */
  }
}
function safeRemove(key: string): void {
  try {
    localStorage.removeItem(key)
  } catch {
    /* ignore */
  }
}

export function getStoredToken(): string | null {
  return safeGet(TOKEN_KEY)
}

export function getStoredUser(): MdmUser | null {
  const raw = safeGet(USER_KEY)
  if (!raw) return null
  try {
    return JSON.parse(raw) as MdmUser
  } catch {
    return null
  }
}

/** 写入令牌（与 user），并在本标签页广播 'cmab-token-changed'（storage 事件只发给别的标签页） */
export function storeSession(token: string, user?: MdmUser | null): void {
  safeSet(TOKEN_KEY, token)
  if (user) safeSet(USER_KEY, JSON.stringify(user))
  if (typeof window !== 'undefined') {
    window.dispatchEvent(new CustomEvent(TOKEN_CHANGED_EVENT, { detail: { token } }))
  }
}

export function clearSession(): void {
  safeRemove(TOKEN_KEY)
  safeRemove(USER_KEY)
  if (typeof window !== 'undefined') {
    window.dispatchEvent(new CustomEvent(TOKEN_CHANGED_EVENT, { detail: { token: null } }))
  }
}

// ---------------- 活动时间 ----------------

export function touchActivity(): void {
  safeSet(LAST_ACTIVE_KEY, String(Date.now()))
}

export function readLastActive(): number {
  const v = Number(safeGet(LAST_ACTIVE_KEY))
  return Number.isFinite(v) && v > 0 ? v : 0
}

/** 解 JWT 的 exp（毫秒）；解析失败返回 0（当作未知，交给 401 兜底） */
export function tokenExpMs(token: string | null): number {
  if (!token) return 0
  try {
    const seg = token.split('.')[1].replace(/-/g, '+').replace(/_/g, '/')
    const json = JSON.parse(atob(seg))
    return typeof json?.exp === 'number' ? json.exp * 1000 : 0
  } catch {
    return 0
  }
}

// ---------------- MDM 接口 ----------------

interface MdmEnvelope<T> {
  code: number
  message: string
  data: T
  meta?: { error?: { type?: string } }
}

async function mdmFetch<T>(path: string, init: RequestInit = {}, token?: string | null): Promise<T> {
  const headers: Record<string, string> = { 'Content-Type': 'application/json', ...(init.headers as Record<string, string>) }
  if (token) headers.Authorization = `Bearer ${token}`
  let resp: Response
  try {
    resp = await fetch(`${MDM_API}${path}`, { credentials: 'include', ...init, headers })
  } catch {
    throw new MdmError('连不上身份中心（MDM），请稍后重试', 0)
  }
  const body = (await resp.json().catch(() => null)) as MdmEnvelope<T> | null
  if (!resp.ok) {
    throw new MdmError(body?.message || `请求失败（${resp.status}）`, resp.status, body?.meta?.error?.type ?? null)
  }
  if (!body) throw new MdmError('身份中心返回了无法解析的响应', resp.status)
  return body.data
}

/** 登录：账号密码原样交给 MDM；成功后落盘令牌 + user，并把活动时间记为现在 */
export async function mdmLogin(username: string, password: string): Promise<MdmLoginResult> {
  const r = await mdmFetch<MdmLoginResult>('/auth/login', { method: 'POST', body: JSON.stringify({ username, password }) })
  storeSession(r.access_token, r.user)
  touchActivity()
  return r
}

// 同一时刻只发起一次 refresh，其余调用等同一个 promise
let refreshPromise: Promise<string> | null = null

/** 静默续期：用 HttpOnly refresh Cookie 换新通行证并落盘；失败抛 MdmError（message 为后端原话） */
export function mdmRefresh(): Promise<string> {
  if (!refreshPromise) {
    refreshPromise = mdmFetch<{ access_token: string }>('/auth/refresh', { method: 'POST' })
      .then((d) => {
        if (!d?.access_token) throw new MdmError('refresh 未返回 access_token', 500)
        storeSession(d.access_token)
        return d.access_token
      })
      .finally(() => {
        refreshPromise = null
      })
  }
  return refreshPromise
}

/** 登出：撤销 MDM 侧 refresh（失败也无所谓），并清本地登录态（全公司共用 key，等于整个门户会话退出） */
export async function mdmLogout(): Promise<void> {
  try {
    await mdmFetch('/auth/logout', { method: 'POST' }, getStoredToken())
  } catch {
    /* ignore */
  }
  clearSession()
}

/** 当前用户生效的会话策略（展示模式账号 idle 已放宽） */
export function mdmSessionPolicy(): Promise<SessionPolicy> {
  return mdmFetch<SessionPolicy>('/auth/session-policy', { method: 'GET' }, getStoredToken())
}

// ---------------- 会话守卫 ----------------

const TICK_MS = 30_000
const ACTIVITY_THROTTLE_MS = 10_000
const ACTIVITY_EVENTS = ['mousemove', 'mousedown', 'keydown', 'touchstart', 'scroll', 'wheel'] as const

export interface SessionGuardOptions {
  /** 被踢出时做什么：清本地态 + 回登录页（可用 logoutToLogin 生成） */
  onLogout: (reason: LogoutReason) => void
  /** 令牌换新（本页 refresh 成功 / 别的标签页换新）时同步到本页 store；不传则只落 localStorage */
  onTokenReplaced?: (token: string) => void
  getToken?: () => string | null
  loadPolicy?: () => Promise<Pick<SessionPolicy, 'access_token_minutes' | 'idle_timeout_minutes'>>
  refresh?: () => Promise<string>
}

/**
 * 启动守卫；返回停止函数（组件卸载时调）。
 *   - 每 30 秒：距最后动作 > 空闲窗口 → onLogout('idle')；通行证快到期（剩余 < min(5 分钟, 时长/3)）→ 静默续期，失败 → onLogout('expired')
 *   - storage 事件：别处清了令牌 → onLogout('other-tab')；别处换了令牌 → onTokenReplaced
 */
export function startSessionGuard(opts: SessionGuardOptions): () => void {
  if (typeof window === 'undefined') return () => undefined
  const getToken = opts.getToken ?? getStoredToken
  const loadPolicy = opts.loadPolicy ?? mdmSessionPolicy
  const refresh = opts.refresh ?? mdmRefresh

  let policy: Pick<SessionPolicy, 'access_token_minutes' | 'idle_timeout_minutes'> | null = null
  let loadingPolicy = false
  let refreshing = false
  let stopped = false
  let lastTouch = 0

  const onActivity = () => {
    const now = Date.now()
    if (now - lastTouch < ACTIVITY_THROTTLE_MS) return
    lastTouch = now
    touchActivity()
  }

  const ensurePolicy = async () => {
    if (policy || loadingPolicy) return
    loadingPolicy = true
    try {
      policy = await loadPolicy()
    } catch {
      /* 下一 tick 再试 */
    } finally {
      loadingPolicy = false
    }
  }

  /** 续期一次；失败即按「会话已失效」登出 */
  const tryRefresh = async () => {
    if (refreshing || stopped) return
    refreshing = true
    try {
      const t = await refresh()
      opts.onTokenReplaced?.(t)
    } catch {
      if (!stopped) {
        stopped = true
        opts.onLogout('expired')
      }
    } finally {
      refreshing = false
    }
  }

  const tick = async () => {
    if (stopped) return
    const token = getToken()
    if (!token) return
    const now = Date.now()
    const exp = tokenExpMs(token)

    // 通行证已经过期：此刻去拉会话策略必然 401，不能等拿到策略再决定。
    // 旧写法是「拉不到策略就 return」，于是令牌失效后守卫既不续期也不登出，
    // 页面就一直停在已登录的样子（2026-09-10 负责人反馈「打开门户直接就进来了」，已实测复现）。
    if (exp && exp <= now) {
      await tryRefresh()
      return
    }

    await ensurePolicy()
    if (stopped) return
    // 策略暂时拉不到（后端抖动等）就先用保守默认值，保证空闲登出照常生效
    const p = policy ?? FALLBACK_POLICY

    const lastActive = readLastActive() || now
    if (now - lastActive > p.idle_timeout_minutes * 60_000) {
      stopped = true
      opts.onLogout('idle')
      return
    }

    if (!exp) return
    const aheadMs = Math.min(5 * 60_000, (p.access_token_minutes * 60_000) / 3)
    if (exp - now > aheadMs) return
    await tryRefresh()
  }

  const onStorage = (e: StorageEvent) => {
    if (e.key !== TOKEN_KEY) return
    if (!e.newValue) {
      if (!stopped) {
        stopped = true
        opts.onLogout('other-tab')
      }
      return
    }
    if (e.newValue !== getToken()) opts.onTokenReplaced?.(e.newValue)
  }

  const onVisible = () => {
    if (document.visibilityState === 'visible') void tick()
  }

  if (!readLastActive()) touchActivity()
  ACTIVITY_EVENTS.forEach((ev) => window.addEventListener(ev, onActivity, { passive: true }))
  window.addEventListener('storage', onStorage)
  document.addEventListener('visibilitychange', onVisible)
  const timer = window.setInterval(() => void tick(), TICK_MS)
  void tick()

  return () => {
    stopped = true
    window.clearInterval(timer)
    ACTIVITY_EVENTS.forEach((ev) => window.removeEventListener(ev, onActivity))
    window.removeEventListener('storage', onStorage)
    document.removeEventListener('visibilitychange', onVisible)
  }
}

/**
 * 生成最常用的 onLogout：撤销 MDM 会话（别处已登出则不重复）、清本地态、整页跳到登录页并带 ?reason=。
 * loginUrl 传本系统登录页完整路径（含前缀），如 '/labops/login'、'/lims/login'、'/#/login'（HashRouter）。
 */
export function logoutToLogin(loginUrl: string): (reason: LogoutReason) => void {
  return (reason) => {
    const go = () => {
      const sep = loginUrl.includes('?') ? '&' : '?'
      window.location.href = `${loginUrl}${sep}reason=${reason}`
    }
    if (reason === 'other-tab') {
      clearSession()
      go()
      return
    }
    void mdmLogout().finally(go)
  }
}

/** 登录页用：把 ?reason= 翻译成提示语；不认识的返回 null */
export function logoutReasonText(reason: string | null | undefined): string | null {
  switch (reason) {
    case 'idle':
      return '长时间未操作，已自动退出登录，请重新登录'
    case 'expired':
      return '登录已过期，请重新登录'
    default:
      return null
  }
}
