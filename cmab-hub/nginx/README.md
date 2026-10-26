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

配置层面保留了兼容（下面三点），但 **2026-08-17 起 Linux 上各子系统已只听 127.0.0.1 + ufw 只放行 5100，老网址在内网实际已不可达**——这是负责人的决定（不留后门、逼大家用 5100）。若将来要放开某个端口：改回监听 0.0.0.0 + `ufw allow`，且**不免登**（不同端口 = 不同站点）。要点：
- 根路径自动跳到子路径：`IP:5110/` → `/labops/`（子系统 nginx `location = /` 302）；Next 看板由 `next.config redirects` 跳到 `/usp`、`/lims`。
- 直连时前端调的是 `/xxx/api/...`，所以子系统自己也得会转：Vite 项目在子系统 nginx 加 `location /xxx/api/ { proxy_pass 后端/api/; }`（MDM/LabOps 片段已含）；Next 项目用 `next.config rewrites`（已加）。
- Mac 上 Vite dev 直连根路径会显示 Vite 的"请访问 /xxx/"提示页而非自动跳转，属开发态正常。

## 子系统改造进度

| 子系统 | 前端改造 | 统一 key | Linux 子系统 nginx / 监听 | 部署脚本 |
|---|---|---|---|---|
| MDM | ✅ `/mdm/` | ✅（旧 `cmab-mdm-auth` 自动迁移） | ✅ 受管副本 `cmab-mdm-platform/deploy/nginx/linux-host/`；15173/18000 只听本机 | `deploy/linux/10_mdm.sh` |
| LabOps | ✅ `/labops/` | ✅（旧 `token/user` 自动迁移） | ✅ conf 由脚本写入（对齐 `cmc-labops/DEPLOY.md` §4b）；5110 只听本机 | `deploy/linux/20_labops.sh` |
| 批号管理 | ✅ `/batch/` | ✅（旧 `rbr_*` 自动迁移） | ✅ conf 由脚本写入；5180 只听本机 | `deploy/linux/25_batch.sh` |
| 上游看板（Next） | ✅ `basePath:'/usp'` | ✅（旧 `usp_dashboard_token` 自动迁移） | ✅ next start `-H 127.0.0.1`；`.env.local` = `/usp`；5170/8070 只听本机 | `deploy/linux/30_usp.sh` |
| LIMS 看板（Next） | ✅ `basePath:'/lims'` | ✅（旧 `lims_token` 自动迁移） | ✅ 同上；`.env.local` = `/lims`；5130/8030 只听本机 | `deploy/linux/40_lims.sh` |
| CMC 质量分析看板 | ✅ `/qap/` | ✅ `cmab_access_token` | ⏳ 代码已就绪，待首次部署；5140/8040 只听本机 | `deploy/linux/45_qap.sh` |
| 成本模型 | ⬜ 未纳入（注册表 planned） | ⬜ | ⬜ | — |

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

## Linux 正式（已完成 2026-08-17）

```bash
# 首次（已做）：
sudo mkdir -p /opt/cmab-hub && sudo chown prometheus:prometheus /opt/cmab-hub
git clone git@github.com:qingcheng81/cmab-hub.git /opt/cmab-hub
cd /opt/cmab-hub/frontend && pnpm install && pnpm build
sudo ln -sfn /opt/cmab-hub/nginx/cmab-hub.linux.conf /etc/nginx/conf.d/cmab-hub.conf
sudo nginx -t && sudo systemctl restart nginx
# 日常更新门户前端：
cd /opt/cmab-hub && git pull && cd frontend && pnpm build     # 静态包立即生效
# 改了 nginx/*.conf：sudo nginx -t && sudo systemctl restart nginx（改 listen 地址必须 restart，reload 不生效）
```

各子系统的 Linux 改造（拉码、重建、子系统 nginx 加 `/xxx/`、前后端只听 127.0.0.1）在 `deploy/linux/10~40_*.sh`，可重复跑；
`50_firewall.sh` 是 ufw 规则（只开放 13568/5100，并清理已退役旧看板的 3001），需负责人亲自执行。所有被改的 conf / unit / `.env.local` 都有 `.bak-20260817-*`。

## 2026-10-10 Mac运维看板模拟预览

`/ops/` → 本机5125静态模拟预览；`/ops/api/` → 8025（真实API尚未启动），公开health路径返回404。当前Mac在用frontend/dist已更新，真实nginx -t通过并平滑reload，监听地址保持；没有执行Linux发布。SYS_ADMIN入口规则已检查，真实账号磁贴点击尚未验收。监控前端由 `com.qingcheng.cmc-platform-monitor.frontend` LaunchAgent托管；配置、备份和真实数据未接入范围以monitor/docs/DEPLOYMENT.md为准。
