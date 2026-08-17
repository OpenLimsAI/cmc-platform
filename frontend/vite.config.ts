import path from 'node:path'

import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// 端口（见 ~/code/PORTS.md）：
//   5100 = nginx，唯一对外门，伺服 dist/ 并按路径反代各子系统（nginx/ 目录）。
//   5101 = 这里的 Vite dev server，只在单独调门户界面时用（不经 nginx）。禁用 5000（macOS AirPlay 占用）。
//
// 单独跑 Vite 时没有 nginx，用 Vite 自带代理模拟 nginx 的路径路由（与 nginx/hub-locations.conf 一致）：
//   /mdm/api/  → MDM 后端 127.0.0.1:18000（去掉 /mdm 前缀，MDM 后端路由是 /api/v1/...）
// 前端代码只写相对路径 /mdm/api/...，走 nginx 还是走 Vite 代理零差异。
export default defineConfig({
  base: '/',
  plugins: [react()],
  resolve: { alias: { '@': path.resolve(__dirname, 'src') } },
  server: {
    port: 5101,
    strictPort: true,
    proxy: {
      '/mdm/api': {
        target: 'http://127.0.0.1:18000',
        changeOrigin: true,
        rewrite: (p) => p.replace(/^\/mdm/, ''),
      },
    },
  },
})
