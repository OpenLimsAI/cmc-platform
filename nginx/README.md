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

## 子系统改造进度

| 子系统 | 前端改造 | 统一 key | Linux 子系统 nginx | 备注 |
|---|---|---|---|---|
| MDM | ✅ 2026-08-17 | ✅（旧 key 自动迁移） | 副本在 `cmab-mdm-platform/deploy/nginx/linux-host/`，待部署时 cp | 抄写模板：`frontend/src/shared/base.ts` |
| LabOps | ⬜ | ⬜ | ⬜ | |
| 批号管理 | ⬜ | ⬜ | ⬜ | |
| 上游看板（Next） | ⬜ | — | — | |
| LIMS 看板（Next） | ⬜ | ⬜ | — | |
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
