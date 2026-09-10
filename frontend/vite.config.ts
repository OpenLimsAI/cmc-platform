import path from 'node:path'

import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'
import { execSync } from 'node:child_process';
import { mkdirSync, writeFileSync } from 'node:fs';
import type { Plugin, ResolvedConfig } from 'vite';

// 端口（见 ~/code/PORTS.md）：
//   5100 = nginx，唯一对外门，伺服 dist/ 并按路径反代各子系统（nginx/ 目录）。
//   5101 = 这里的 Vite dev server，只在单独调门户界面时用（不经 nginx）。禁用 5000（macOS AirPlay 占用）。
//
// 单独跑 Vite 时没有 nginx，用 Vite 自带代理模拟 nginx 的路径路由（与 nginx/hub-locations.conf 一致）：
//   /mdm/api/  → MDM 后端 127.0.0.1:18000（去掉 /mdm 前缀，MDM 后端路由是 /api/v1/...）
// 前端代码只写相对路径 /mdm/api/...，走 nginx 还是走 Vite 代理零差异。

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
  base: '/',
  plugins: [react(), buildIdPlugin()],
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
