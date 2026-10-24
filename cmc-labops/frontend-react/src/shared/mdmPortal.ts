/**
 * MDM Portal 前端地址 — 用于"去 MDM 登记/新增"跳转。
 * 2026-08-17 起 LabOps 与 MDM 都挂在统一门户 cmab-hub 之下（同源、同端口 5100）：
 * MDM = 当前站点的 /mdm/ 子路径，直接同源跳转，令牌共享、免登（老端口 15173 已对外关闭）。
 * 若 MDM 部署在另一台主机，用 VITE_MDM_PORTAL_URL 显式覆盖（填到主机根，如 http://host:5100）。
 */
const MDM_PREFIX = "/mdm";

const MDM_PORTAL_URL: string =
  import.meta.env.VITE_MDM_PORTAL_URL ||
  (typeof window !== "undefined" && window.location?.origin ? window.location.origin : "http://127.0.0.1:5100");

/** 拼 MDM 门户页面地址，如 mdmPortalUrl("/materials/new", { code: "R-001" }) → /mdm/materials/new?code=R-001 */
export function mdmPortalUrl(path: string, params?: Record<string, string>): string {
  const p = path.startsWith("/") ? path : `/${path}`;
  const url = new URL(`${MDM_PREFIX}${p}`, MDM_PORTAL_URL);
  if (params) {
    for (const [k, v] of Object.entries(params)) {
      if (v) url.searchParams.set(k, v);
    }
  }
  return url.toString();
}
