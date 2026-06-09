/**
 * MDM Portal 前端地址 — 用于"去 MDM 登记/新增"跳转。
 * 默认按当前浏览器访问的主机名推导(MDM 与 LabOps 同机、固定端口 15173):
 * 从 172.19.0.105:5110 打开 → http://172.19.0.105:15173;localhost 打开 → localhost:15173。
 * 若 MDM 部署在另一台主机,用 VITE_MDM_PORTAL_URL 显式覆盖。
 */
const MDM_PORT = "15173";

function defaultMdmPortalUrl(): string {
  if (typeof window !== "undefined" && window.location?.hostname) {
    return `${window.location.protocol}//${window.location.hostname}:${MDM_PORT}`;
  }
  return `http://127.0.0.1:${MDM_PORT}`;
}

const MDM_PORTAL_URL: string =
  import.meta.env.VITE_MDM_PORTAL_URL || defaultMdmPortalUrl();

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
