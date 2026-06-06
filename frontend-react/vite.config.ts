import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// 后端地址:开发默认 8010;Linux 生产由 systemd EnvironmentFile 注入 BACKEND_PORT
const backendTarget = `http://localhost:${process.env.BACKEND_PORT || 8010}`;

export default defineConfig({
  plugins: [react()],
  server: {
    // 本项目固定端口(编号 10):前端 5110 / 后端 8010。strictPort:被占则直接报错,
    // 不自动漂移到别的号,避免和其它项目混淆。详见 ~/code/PORTS.md
    port: 5110,
    strictPort: true,
    proxy: {
      "/api": {
        target: backendTarget,
        changeOrigin: true,
      },
    },
  },
  // Linux 生产: npm run build 后用 `npm run preview` 伺服 dist,
  // preview 同样代理 /api 到后端,保持同源、无需 nginx
  preview: {
    port: 5110,
    strictPort: true,
    proxy: {
      "/api": {
        target: backendTarget,
        changeOrigin: true,
      },
    },
  },
});
