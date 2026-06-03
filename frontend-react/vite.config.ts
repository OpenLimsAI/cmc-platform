import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    // 本项目固定端口(编号 10):前端 5110 / 后端 8010。strictPort:被占则直接报错,
    // 不自动漂移到别的号,避免和其它项目混淆。详见 ~/code/PORTS.md
    port: 5110,
    strictPort: true,
    proxy: {
      "/api": {
        target: "http://localhost:8010",
        changeOrigin: true,
      },
    },
  },
});
