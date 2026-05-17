import type { NextConfig } from "next";

// Next.js 16 默认只允许 localhost 访问 dev server 资源（HMR/_next/*）。
// 从非 localhost 访问（如 VM IP、其他主机名）时，把主机名用逗号分隔放到 DEV_EXTRA_ORIGINS。
// 示例：DEV_EXTRA_ORIGINS=192.168.1.100,10.0.0.5
const devExtraOrigins = (process.env.DEV_EXTRA_ORIGINS ?? "")
  .split(",")
  .map((s) => s.trim())
  .filter(Boolean);

const nextConfig: NextConfig = {
  allowedDevOrigins: devExtraOrigins,
};

export default nextConfig;
