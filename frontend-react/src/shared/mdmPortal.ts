/**
 * MDM Portal 前端地址 — 用于"本地/MDM 都没有 → 去 MDM 登记"的跳转。
 * 生产环境通过 VITE_MDM_PORTAL_URL 指到实际部署地址。
 */
const MDM_PORTAL_URL: string =
  import.meta.env.VITE_MDM_PORTAL_URL || "http://127.0.0.1:15173";

/** 拼 MDM 门户页面地址，如 mdmPortalUrl("/materials/new", { code: "R-001" }) */
export function mdmPortalUrl(path: string, params?: Record<string, string>): string {
  const url = new URL(path, MDM_PORTAL_URL);
  if (params) {
    for (const [k, v] of Object.entries(params)) {
      if (v) url.searchParams.set(k, v);
    }
  }
  return url.toString();
}
