# CLAUDE.md — cmab-hub（统一门户）

> 本项目专属说明。通用铁律见 `~/code/CLAUDE.md`（总纲），端口见 `~/code/PORTS.md`。设计原文：`cmab-hub_设计方案.md`；反代与部署细节：`nginx/README.md`、`deploy/linux/`。

## 一句话定位

公司内部所有系统（MDM / LabOps / 批号管理 / 上游工艺看板 / LIMS 看板…）的**统一总入口**：一墙图标、按权限显隐、对外只开一个端口 **5100**、登录一次进任何子系统不重复登录。形态参照 waters_connect HUB。

## 状态：✅ 已上线（2026-08-17）

- 正式入口 **`http://172.19.0.105:5100`**（Linux `/opt/cmab-hub`，nginx 伺服 `frontend/dist`）；Mac 本地 brew nginx 同样听 5100。
- 已纳入 5 个系统：MDM `/mdm/`、LabOps `/labops/`、批号 `/batch/`、上游看板 `/usp`、LIMS 看板 `/lims`。成本模型在注册表里标 `planned`，未纳入。
- Linux 上这 5 个系统的**前后端全部只听 127.0.0.1**，ufw 防火墙只放行 13568(SSH) / 5100 / 3001(质量分析平台测试，负责人指示暂放行)。老端口内网不可达。
- SSO 已在 Mac 与 Linux 实测通过：门户登录一次，5 个系统全部免登。

## 已拍板的硬决策（别再推翻）

1. **深版**：单一入口 nginx（5100）+ 路径反代到各子系统；不做"图标跳转"浅版。
2. **端口 5100**（禁用 5000，被 macOS AirPlay 占）。门户 Vite dev 用 5101，仅本地调界面。
3. **技术栈** React 18 + Vite + Ant Design 5；门户无后端，登录/用户信息直接打 MDM。
4. **MDM 是唯一身份中心**：登录转发 MDM `/api/v1/auth/login`，图标显隐按 JWT/登录响应里的 MDM 角色码。
5. **统一令牌 key（全公司）**：`localStorage['cmab_access_token']` = MDM access token 原文；`localStorage['cmab_user']` = MDM 登录响应的 `user` 对象 JSON。所有子系统同源挂在 5100 下、都读这两个 key → SSO。门户**不做**按各家旧 key 写副本的桥接。
6. **子系统前端自己认前缀**（Vite `base:'/xxx/'` + Router `basename` + API 相对路径 `/xxx/api`；Next `basePath:'/xxx'`）。HUB nginx 对 `/xxx/` **不剥前缀**（Vite dev server 配了 base 后只认带前缀请求），对 `/xxx/api/` **剥前缀**转后端 `/api/`。
7. **界面定稿**（负责人拍板）：背景 `#1F3864→#264573` 135° 轻渐变；磁贴磨砂玻璃（半透明白+细描边+模糊）、正方形、内容居中、一行 4 个、整块垂直居中；上方按时段问候语（细黑体 44px）+ 登录人姓名；无"我的应用"标题；点图标**新标签页**打开。改样式只动 `frontend/src/styles/global.css`。先功能后界面是负责人的一贯要求。

## 加一个新系统（四步，都有模板可抄）

1. `frontend/src/config/apps.ts` 的 `HUB_APPS` 加一条（`id/name/icon/path/requires/status`）。
2. `nginx/hub-locations.conf` 加两条 location（`/xxx/api/` 剥前缀转后端、`/xxx/` 原样转前端；Next 项目再加 `location = /xxx`）。Mac `nginx -t && brew services restart nginx`。
3. 子系统前端改前缀 + 改读统一 key：Vite 项目抄 `cmc-labops/frontend-react/src/shared/base.ts`（或 rd-batch-registry 同名文件）；Next 项目抄 `cmc-rd-lims-dashboard/frontend/lib/auth.ts` + `next.config.ts`（basePath / redirects / rewrites）。
4. Linux：照 `deploy/linux/NN_xxx.sh` 写一份部署脚本（`00_common.sh` 有备份/只听本机/重启函数），子系统 nginx 加 `location /xxx/ { alias <dist>/; try_files ... /xxx/index.html; }` + `/xxx/api/` 转发，前后端改 `127.0.0.1`。**不要**给它开 ufw 端口——一律走 5100。

## 运维要点

- **改了 Linux 上任何对外服务/新开端口，必须同时加 ufw 规则**（`sudo ufw allow <port>/tcp comment '...'`），否则内网访问不到。ufw 类操作自动模式会拦截，交负责人亲自跑。
- nginx 改 `listen` 地址（0.0.0.0→127.0.0.1）要 `systemctl restart nginx`，reload 会 "Address already in use" 沿用旧监听。
- 上游一律写 `localhost` 不写 `127.0.0.1`（Mac 上 Vite dev 只听 IPv6）。
- 部署改动一律写进 `deploy/linux/*.sh` 再到 Linux 跑（一条龙 ssh 命令会被自动模式拦）。所有被改过的 nginx conf / systemd unit / `.env.local` 都留有 `.bak-20260817-*`。
- 两个 Next 看板的后端地址在各自 `frontend/.env.local`（不进 git）：Linux 上已改为 `/usp`、`/lims`，重装机器要记得重写。
- 老端口（IP:端口直连）在 Linux 上已不可达；配置层面各子系统仍保留了 `location = / → /xxx/` 跳转与 `/xxx/api/` 转发，若将来放开某端口可直接用，但**不免登**（不同端口=不同站点）。

## 已知小问题（与门户无关，记录备查）

- LIMS 看板导航栏有 hydration 告警（当前页高亮 SSR/客户端不一致），老问题。
