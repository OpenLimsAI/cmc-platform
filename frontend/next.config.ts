import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // 挂在统一门户 cmab-hub 的 /usp 子路径下（5100/usp → 本 dev server :5170），HUB 不剥前缀，
  // Next 自己靠 basePath 认前缀（页面路由、_next 静态资源、Link/router 全自动带上）。
  // API 走相对路径 /usp/api/...（见 lib/api.ts；HUB 剥掉 /usp 转给后端 :8070/api/）。
  basePath: "/usp",
};

export default nextConfig;
