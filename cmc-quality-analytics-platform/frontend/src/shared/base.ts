// QAP 通过 cmab-hub 挂在 /qap/；Vite 开发与 Linux 静态构建使用同一前缀。
export const BASE = import.meta.env.BASE_URL.replace(/\/$/, '')
export const APP_ROOT = `${BASE}/`

export const withBase = (path: string): string =>
  `${BASE}${path.startsWith('/') ? path : `/${path}`}`

/** 未登录或会话结束时统一回到 Hub 登录页，再由 Hub 跳回 QAP。 */
export function hubLoginUrl(): string {
  return `/login?redirect=${encodeURIComponent(APP_ROOT)}`
}
