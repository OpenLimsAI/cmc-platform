import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import { execSync } from "node:child_process";
import { mkdirSync, writeFileSync } from "node:fs";
import path from "node:path";
import type { Plugin, ResolvedConfig } from "vite";

// 后端地址:开发默认 8010;Linux 生产由 systemd EnvironmentFile 注入 BACKEND_PORT
const backendTarget = `http://localhost:${process.env.BACKEND_PORT || 8010}`;

// 单独跑（不经 HUB nginx）时模拟 HUB 的 /labops/api → 后端 /api 剥前缀，并把 refresh cookie 的 Path 改写回来
const apiProxy = {
  "/labops/api": {
    target: backendTarget,
    changeOrigin: true,
    rewrite: (p: string) => p.replace(/^\/labops/, ""),
    cookiePathRewrite: { "/api/": "/labops/api/" },
  },
  // 单独跑（不经 HUB nginx）时模拟 HUB 的 /mdm/api → MDM 后端（登录/续期/登出直接打 MDM，见 shared/cmabSession.ts）
  "/mdm/api": {
    target: process.env.MDM_TARGET || "http://localhost:18000",
    changeOrigin: true,
    rewrite: (p: string) => p.replace(/^\/mdm/, ""),
    cookiePathRewrite: { "/api/": "/mdm/api/" },
  },
};


// ── 构建标识（2026-09-10，「部署后旧标签页自动刷新」标准做法）────────────────────────
// 把本次构建的 id 注入前端常量 __APP_BUILD_ID__，并在 dist/ 写 version.json；dev server 伺服同名文件。
// 前端 src/shared/appUpdate.tsx 定时/在切回标签页/别的标签页登录时核对，发现服务器已换版本就提示或自动刷新。
function makeBuildId(): string {
  let sha = "nogit";
  try {
    sha = execSync("git rev-parse --short HEAD", { stdio: ["ignore", "pipe", "ignore"] }).toString().trim();
  } catch {
    /* 无 git 时只用时间戳 */
  }
  const ts = new Date().toISOString().replace(/[-:]/g, "").replace(/\.\d+Z$/, "Z");
  return `${ts}-${sha}`;
}

function buildIdPlugin(): Plugin {
  const id = makeBuildId();
  let cfg: ResolvedConfig;
  const body = () => JSON.stringify({ build_id: id, built_at: new Date().toISOString() });
  return {
    name: "cmab-build-id",
    config: () => ({ define: { __APP_BUILD_ID__: JSON.stringify(id) } }),
    configResolved(c) {
      cfg = c;
    },
    configureServer(server) {
      server.middlewares.use((req, res, next) => {
        if ((req.url ?? "").split("?")[0] === `${cfg.base}version.json`) {
          res.setHeader("Content-Type", "application/json");
          res.setHeader("Cache-Control", "no-store");
          res.end(body());
          return;
        }
        next();
      });
    },
    closeBundle() {
      const dir = path.resolve(cfg.root, cfg.build.outDir);
      mkdirSync(dir, { recursive: true });
      writeFileSync(path.join(dir, "version.json"), body());
    },
  };
}

export default defineConfig({
  // 挂在统一门户 cmab-hub 的 /labops/ 子路径下（5100/labops/ → 本 dev server / dist），HUB 不剥前缀，
  // 由本前端自己认 /labops/。API 走相对路径 /labops/api（HUB 剥掉 /labops 转给后端 :8010/api/）。
  base: "/labops/",
  plugins: [react(), buildIdPlugin()],
  server: {
    // 本项目固定端口(编号 10):前端 5110 / 后端 8010。strictPort:被占则直接报错,
    // 不自动漂移到别的号,避免和其它项目混淆。详见 ~/code/PORTS.md
    port: 5110,
    strictPort: true,
    proxy: apiProxy,
  },
  // Linux 生产: npm run build 后用 `npm run preview` 伺服 dist,
  // preview 同样代理 /labops/api 到后端,保持同源、无需 nginx
  preview: {
    port: 5110,
    strictPort: true,
    proxy: apiProxy,
  },
});
