# nginx · 统一入口 5100

| 文件 | 用途 |
|---|---|
| `hub-locations.conf` | **子系统路由表**（Mac / Linux 共用）——加系统改这里 |
| `cmab-hub.mac.conf` | Mac 本地 server 块（brew nginx） |
| `cmab-hub.linux.conf` | Linux 正式 server 块（`/opt/cmab-hub`） |

两份 server 文件只差 `root` / `include` 的绝对路径，其余一模一样；公共代理参数写在 server 层自动继承。

## 路由约定（改子系统前先看）

```
5100/                → 门户静态包 frontend/dist（SPA 回落 index.html）
5100/<app>/api/      → 该系统后端 :80N0/api/     剥掉 /<app>；后端零改动；Set-Cookie 的 Path 自动改写
5100/<app>/          → 该系统前端 :51N0     不剥前缀，前端自己认 /<app>/：
                       Vite 项目：base:'/<app>/' + Router basename + API 走 /<app>/api + 读统一 key
                                 Linux 静态伺服的子系统 nginx 加 location /<app>/ { alias <dist>/; try_files $uri $uri/ /<app>/index.html; }
                       Next 项目：basePath:'/<app>'，HUB 另加 location = /<app> 接尾斜杠跳转
```

> 为什么前端不剥前缀：Mac 上子系统前端是 Vite dev server，配了 `base` 后只认带前缀的请求，剥了就拒收。

## 老网址（IP:端口 直连）还能用吗

能，作为过渡/兜底保留，但**不免登**（不同端口 = 不同站点，SSO 只在 5100 门内有效）。要点：
- 根路径自动跳到子路径：`IP:5110/` → `/labops/`（子系统 nginx `location = /` 302）；Next 看板由 `next.config redirects` 跳到 `/usp`、`/lims`。
- 直连时前端调的是 `/xxx/api/...`，所以子系统自己也得会转：Vite 项目在子系统 nginx 加 `location /xxx/api/ { proxy_pass 后端/api/; }`（MDM/LabOps 片段已含）；Next 项目用 `next.config rewrites`（已加）。
- Mac 上 Vite dev 直连根路径会显示 Vite 的"请访问 /xxx/"提示页而非自动跳转，属开发态正常。

## 子系统改造进度

| 子系统 | 前端改造 | 统一 key | Linux 子系统 nginx | 备注 |
|---|---|---|---|---|
| MDM | ✅ 2026-08-17 | ✅（旧 key 自动迁移） | 副本在 `cmab-mdm-platform/deploy/nginx/linux-host/`，待部署时 cp | 抄写模板：`frontend/src/shared/base.ts` |
| LabOps | ✅ 2026-08-17 | ✅（旧 key 自动迁移） | 片段在 `cmc-labops/DEPLOY.md` §4b，部署时改 `/etc/nginx/conf.d/cmc-labops.conf` | Mac 上 SSO 实测通过（门户登录→LabOps 免登） |
| 批号管理 | ✅ 2026-08-17 | ✅（旧 rbr_* 自动迁移） | ✅ 已部署（`deploy/linux/25_batch.sh`，5180 只听本机） | |
| 上游看板（Next） | ✅ 2026-08-17 basePath:'/usp' | ✅（旧 key 自动迁移） | —（Linux 也是 next dev/start，自认前缀） | 本机 `.env.local` 已改 `/usp`；Linux 上 `.env.local` 也要改 |
| LIMS 看板（Next） | ✅ 2026-08-17 basePath:'/lims' | ✅（旧 key 自动迁移） | —（同上） | 本机 `.env.local` 已改 `/lims`；Linux 上也要改 |
| 成本模型 | ⬜ | ⬜ | ⬜ | |

上游一律写 `localhost` 不写 `127.0.0.1`（Mac 上 Vite dev 只听 IPv6）。

## Mac 本地（已完成 2026-08-17）

```bash
brew install nginx
# brew 自带示例站点听 8080（撞批号后端），已在 /opt/homebrew/etc/nginx/nginx.conf 里注释掉，备份 nginx.conf.bak-*
ln -sfn ~/code/cmab-hub/nginx/cmab-hub.mac.conf /opt/homebrew/etc/nginx/servers/cmab-hub.conf
cd ~/code/cmab-hub/frontend && pnpm build      # 生成 dist/，nginx 直接伺服
nginx -t && brew services start nginx           # 开机自启（launchd: homebrew.mxcl.nginx）
```

改了 `nginx/*.conf` 后：`nginx -t && brew services restart nginx`。日志：`/opt/homebrew/var/log/nginx/{access,error}.log`。

## Linux 正式（待 GitHub 仓库建好、`/opt/cmab-hub` 拉下来后执行）

```bash
sudo mkdir -p /opt/cmab-hub && sudo chown prometheus:prometheus /opt/cmab-hub
git clone <repo> /opt/cmab-hub
cd /opt/cmab-hub/frontend && pnpm install && pnpm build
sudo ln -sfn /opt/cmab-hub/nginx/cmab-hub.linux.conf /etc/nginx/conf.d/cmab-hub.conf
sudo nginx -t && sudo systemctl reload nginx
```

Linux 现有 `/etc/nginx/conf.d/{cmab-mdm,cmc-labops,rd-batch-registry}.conf` 各听自己端口伺服静态包，**不用动**；HUB 只是在前面再加一道门。
