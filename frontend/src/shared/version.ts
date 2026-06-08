// 前端展示版本（单一来源）：Sidebar / MainLayout footer / 登录页页脚统一引用。
// 与后端 settings.APP_VERSION 对称；构建时可经 VITE_APP_VERSION 覆盖。
export const APP_VERSION = (import.meta.env.VITE_APP_VERSION as string) || 'V1.3-draft';
