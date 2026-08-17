// 子路径前缀（统一门户 cmab-hub 把本系统挂在 5100/labops/ 之下，见 ~/code/cmab-hub/nginx/README.md）
// 来源是 vite.config.ts 的 base:'/labops/'，这里只是去掉尾斜杠：'/labops'。单独跑也在 :5110/labops/。
export const BASE = import.meta.env.BASE_URL.replace(/\/$/, "");

// 需要绕过 React Router 直接操作 window.location 时，用这两个函数补/去前缀
export const withBase = (p: string) => `${BASE}${p.startsWith("/") ? p : `/${p}`}`;
export const stripBase = (p: string) => (BASE && p.startsWith(BASE) ? p.slice(BASE.length) || "/" : p);

// ── 全公司统一令牌 key（cmab-hub 统一门户 2026-08-17 拍板）────────────────────
// localStorage['cmab_access_token'] = MDM access token 原文（JWT）
// localStorage['cmab_user']         = MDM 登录响应里的 user 对象 JSON
// 所有子系统同源挂在 5100 之下、都读这两个 key → 门户登录一次，到处免登。
export const TOKEN_KEY = "cmab_access_token";
export const USER_KEY = "cmab_user";

// 兼容旧版本：以前存在 'token' / 'user'，读到就迁移一次然后删掉
(() => {
  if (typeof window === "undefined") return;
  const oldT = localStorage.getItem("token");
  if (oldT && !localStorage.getItem(TOKEN_KEY)) {
    localStorage.setItem(TOKEN_KEY, oldT);
    const oldU = localStorage.getItem("user");
    if (oldU) localStorage.setItem(USER_KEY, oldU);
  }
  localStorage.removeItem("token");
  localStorage.removeItem("user");
})();
