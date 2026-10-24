import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // 挂在统一门户 cmab-hub 的 /usp 子路径下（5100/usp → 本 dev server :5170），HUB 不剥前缀，
  // Next 自己靠 basePath 认前缀（页面路由、_next 静态资源、Link/router 全自动带上）。
  // API 走相对路径 /usp/api/...（见 lib/api.ts；HUB 剥掉 /usp 转给后端 :8070/api/）。
  basePath: "/usp",
  // 直连本端口（不经 HUB）时也能用：根路径跳到 /usp；/usp/api/* 由 Next 自己转给后端（经 HUB 时被 HUB 先截走，此条不生效）
  async redirects() {
    return [{ source: "/", destination: "/usp", basePath: false, permanent: false }];
  },
  async rewrites() {
    const backend = process.env.BACKEND_URL ?? "http://localhost:8070";
    return [{ source: "/api/:path*", destination: `${backend}/api/:path*` }]; // source 自动带 basePath → /usp/api/*
  },
};

export default nextConfig;
