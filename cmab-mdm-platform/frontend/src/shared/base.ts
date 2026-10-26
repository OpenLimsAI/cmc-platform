// 子路径前缀（统一门户 cmab-hub 把本系统挂在 5100/mdm/ 之下，见 ~/code/cmab-hub/nginx/README.md）
// 来源是 vite.config.ts 的 base:'/mdm/'，这里只是去掉尾斜杠：'/mdm'。单独跑也在 :15173/mdm/。
export const BASE = import.meta.env.BASE_URL.replace(/\/$/, '');

// 需要绕过 React Router 直接操作 window.location 时，用这两个函数补/去前缀
export const withBase = (p: string) => `${BASE}${p.startsWith('/') ? p : `/${p}`}`;
export const stripBase = (p: string) => (BASE && p.startsWith(BASE) ? p.slice(BASE.length) || '/' : p);
