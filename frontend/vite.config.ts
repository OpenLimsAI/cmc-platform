import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import path from 'path';
import { execSync } from 'node:child_process';
import { mkdirSync, writeFileSync } from 'node:fs';
import type { Plugin, ResolvedConfig } from 'vite';


// ── 构建标识（2026-09-10，「部署后旧标签页自动刷新」标准做法）────────────────────────
// 把本次构建的 id 注入前端常量 __APP_BUILD_ID__，并在 dist/ 写 version.json；dev server 伺服同名文件。
// 前端 src/shared/appUpdate.tsx 定时/在切回标签页/别的标签页登录时核对，发现服务器已换版本就提示或自动刷新。
function makeBuildId(): string {
  let sha = 'nogit';
  try {
    sha = execSync('git rev-parse --short HEAD', { stdio: ['ignore', 'pipe', 'ignore'] }).toString().trim();
  } catch {
    /* 无 git 时只用时间戳 */
  }
  const ts = new Date().toISOString().replace(/[-:]/g, '').replace(/\.\d+Z$/, 'Z');
  return `${ts}-${sha}`;
}

function buildIdPlugin(): Plugin {
  const id = makeBuildId();
  let cfg: ResolvedConfig;
  const body = () => JSON.stringify({ build_id: id, built_at: new Date().toISOString() });
  return {
    name: 'cmab-build-id',
    config: () => ({ define: { __APP_BUILD_ID__: JSON.stringify(id) } }),
    configResolved(c) {
      cfg = c;
    },
    configureServer(server) {
      server.middlewares.use((req, res, next) => {
        if ((req.url ?? '').split('?')[0] === `${cfg.base}version.json`) {
          res.setHeader('Content-Type', 'application/json');
          res.setHeader('Cache-Control', 'no-store');
          res.end(body());
          return;
        }
        next();
      });
    },
    closeBundle() {
      const dir = path.resolve(cfg.root, cfg.build.outDir);
      mkdirSync(dir, { recursive: true });
      writeFileSync(path.join(dir, 'version.json'), body());
    },
  };
}

export default defineConfig({
  // 挂在统一门户 cmab-hub 的 /mdm/ 子路径下（5100/mdm/ → 本 dev server / dist），HUB 不剥前缀，
  // 由本前端自己认 /mdm/。API 走相对路径 /mdm/api/v1（HUB 剥掉 /mdm 转给后端 :18000/api/）。
  base: '/mdm/',
  plugins: [react(), buildIdPlugin()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
  server: {
    port: 5173,
    host: true,
    proxy: {
      // 单独跑（不经 HUB nginx）时模拟 HUB 的 /mdm/api → 后端 /api 剥前缀，并把 refresh cookie 的 Path 改写回来
      '/mdm/api': {
        target: process.env.VITE_API_BASE_URL || 'http://localhost:8000',
        changeOrigin: true,
        rewrite: (p) => p.replace(/^\/mdm/, ''),
        cookiePathRewrite: { '/api/': '/mdm/api/' },
      },
    },
  },
  build: {
    outDir: 'dist',
    sourcemap: true,
    // antd / echarts 体量天生就大，已各自拆为独立 vendor chunk 单独缓存；
    // 阈值抬到 1300KB，避免它们反复触发告警，又能让真正的应用代码膨胀露头
    chunkSizeWarningLimit: 1300,
    rollupOptions: {
      output: {
        manualChunks: {
          'react-vendor': ['react', 'react-dom', 'react-router-dom'],
          'antd-vendor': ['antd', '@ant-design/icons'],
          // echarts(~1MB) 拆出独立 chunk：仅访问仪表盘时才下载（配合路由懒加载）
          'echarts-vendor': ['echarts', 'echarts-for-react'],
        },
      },
    },
  },
});
