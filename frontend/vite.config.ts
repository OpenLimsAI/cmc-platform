import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import { fileURLToPath, URL } from 'node:url'

// 端口写死 5140（PORTS.md 约定，编号 40）；strictPort 禁止漂移。
// 开发期把 /api 代理到后端 8040，避免 CORS 与硬编码地址。
export default defineConfig({
  plugins: [react()],
  base: '/qap/',
  resolve: {
    alias: { '@': fileURLToPath(new URL('./src', import.meta.url)) },
  },
  server: {
    port: 5140,
    strictPort: true,
    proxy: {
      '/mdm': {
        target: 'http://127.0.0.1:18000',
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/mdm/, ''),
        // MDM 实际 set_cookie / delete_cookie 的 Path，必须连同门户前缀改写。
        cookiePathRewrite: { '/api/v1/auth': '/mdm/api/v1/auth' },
      },
      '/qap/api': {
        target: 'http://127.0.0.1:8040', changeOrigin: true,
        rewrite: (path) => path.replace(/^\/qap/, ''),
      },
      '/qap/health': {
        target: 'http://127.0.0.1:8040', changeOrigin: true,
        rewrite: (path) => path.replace(/^\/qap/, ''),
      },
    },
  },
})
