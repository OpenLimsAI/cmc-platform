import type { NextConfig } from "next";

// Next.js 16 默认只允许 localhost 访问 dev server 资源（HMR/_next/*）。
// 从非 localhost 访问（如 VM IP、其他主机名）时，把主机名用逗号分隔放到 DEV_EXTRA_ORIGINS。
// 示例：DEV_EXTRA_ORIGINS=192.168.1.100,10.0.0.5
const devExtraOrigins = (process.env.DEV_EXTRA_ORIGINS ?? "")
  .split(",")
  .map((s) => s.trim())
  .filter(Boolean);

const nextConfig: NextConfig = {
  // 挂在统一门户 cmab-hub 的 /lims 子路径下（5100/lims → 本 dev server :5130），HUB 不剥前缀，
  // Next 自己靠 basePath 认前缀（页面路由、_next 静态资源、Link/router 全自动带上）。
  // API 走相对路径 /lims/api/v1/...（见 lib/api.ts；HUB 剥掉 /lims 转给后端 :8030/api/）。
  basePath: "/lims",
  // 直连本端口（不经 HUB）时也能用：根路径跳到 /lims；/lims/api/* 由 Next 自己转给后端（经 HUB 时被 HUB 先截走，此条不生效）
  async redirects() {
    return [{ source: "/", destination: "/lims", basePath: false, permanent: false }];
  },
  async rewrites() {
    const backend = process.env.BACKEND_URL ?? "http://localhost:8030";
    return [{ source: "/api/:path*", destination: `${backend}/api/:path*` }]; // source 自动带 basePath → /lims/api/*
  },
  allowedDevOrigins: devExtraOrigins,
};

export default nextConfig;
