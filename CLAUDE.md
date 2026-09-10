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

## 统一会话 / 自动登出（2026-09-04 起，改登录相关代码必读）

- 规则由 MDM「系统管理 → 会话策略」在线配置（通行证 15 分钟 / 空闲 30 分钟 / 单次登录硬上限 12 小时 / 展示模式空闲 720 分钟），前端不写死数字，登录后读 `GET /mdm/api/v1/auth/session-policy`。
- **母本 `frontend/src/shared/cmabSession.ts`**（纯 TS、不依赖框架）：`mdmLogin / mdmRefresh / mdmLogout / mdmSessionPolicy` 直接打 MDM（同源 `/mdm/api/v1`）+ `startSessionGuard`（空闲超时登出、通行证快到期静默续期、多标签页同步）+ `logoutToLogin` / `logoutReasonText`。**改了母本要同步复制**到 LabOps `src/shared/`、批号 `src/shared/`、USP `lib/`、LIMS `lib/`、LCMS `src/`（MDM 自己用 `frontend/src/shared/sessionGuard.ts`，逻辑相同）。
- 各子系统接法（已全部接上）：登录页调 `mdmLogin`（不再走各自后端代理登录，代理端点保留仅供脚本）；API 客户端 401 → `mdmRefresh` 兜底续一次并重放，续不了回本系统 `/login?reason=expired`；主布局/AuthGate 挂 `startSessionGuard({ onLogout: logoutToLogin('<本系统登录页>') })`；登录页用 `logoutReasonText(?reason)` 显示「长时间未操作」提示。
- 活动时间共用 `localStorage['cmab_last_active']`，令牌换新广播 `cmab-token-changed`（各 store 监听同步）。refresh Cookie 只在 `/mdm/api/v1/auth` 路径下，所以**续期必须直接打 MDM**，不能各自代理。
- 新子系统接入：复制母本 + 照上面三步；登录页可直接复用门户登录（`/login?redirect=/xxx/`）。
- **令牌看不懂就当失效**（2026-09-11）：`tokenExpMs` 解不开或没 exp 返回 0，守卫据此直接续期/登出（`isTokenReadable`），
  门禁 `RequireAuth` 也不认这种令牌。以前这种令牌既不续期也不登出，人挂在假登录状态里，是 2026-09-10 那个毛病的另一半。
  MDM 自己的 `sessionGuard.ts` 同步改过。
- **临时密码不让进业务系统**（2026-09-11）：令牌里带 `must_change_password`，各后端 403 拦（总纲 §8.1），
  门户这边把除 MDM 外的磁贴变灰（`AppTile` 的 `locked`），顶部提示改密码。
- `?redirect=` 只认站内路径（`LoginPage.safeRedirect`），外站地址一律回首页。

## 传输压缩（2026-09-11）

`nginx/compression.conf` 一份，Mac / Linux 两个 server 配置各 include 一次。**压缩开关本来在每台机器
自己的 nginx 主配置里（不进 git，两台各是各的）**——实测 Mac 上是关的，发行版自带的通常只压 html、
不压脚本/样式/JSON，且 `gzip_proxied` 默认 off 会让**转发给子系统的响应完全不压**。写进仓库 = 哪台机器都一样。

实测（Mac，经 5100）：门户主脚本 662 KB → 224 KB；验证部平台一次计算结果 1.2 MB → 157 KB，
计算耗时没有变化（1.65s → 1.67s，在噪声范围内）。

`01_hub.sh` 部署末尾有压缩自检（主脚本必须回 `Content-Encoding`），不过就报警。
没上 Brotli：效果更好但要额外装 nginx 模块，服务器上没有。

## 安全响应头（2026-09-11）

`nginx/security-headers.conf` 一份，Mac / Linux 两个 server 配置各 include 一次。内容只挡「被别人套 iframe」
「浏览器猜文件类型」「地址泄漏给外站」，**不限制脚本来源**（各子系统有内联脚本，收紧会白屏）。

⚠️ nginx 规矩：某个 location 自己写了 `add_header`，上层的 `add_header` 就**全部失效**。所以 `/assets/` 和 `/`
这两个写了 Cache-Control 的 location 里各自又 include 了一次，加新的带 `add_header` 的 location 时记得照做。

> HTTPS 仍未上（对外只有明文 5100），密码在内网是明文传的。要不要上 TLS 是负责人 + IT 的决定，别自作主张改。

## 运维要点

- **改了 Linux 上任何对外服务/新开端口，必须同时加 ufw 规则**（`sudo ufw allow <port>/tcp comment '...'`），否则内网访问不到。ufw 类操作自动模式会拦截，交负责人亲自跑。
- nginx 改 `listen` 地址（0.0.0.0→127.0.0.1）要 `systemctl restart nginx`，reload 会 "Address already in use" 沿用旧监听。
- 上游一律写 `localhost` 不写 `127.0.0.1`（Mac 上 Vite dev 只听 IPv6）。
- 部署改动一律写进 `deploy/linux/*.sh` 再到 Linux 跑（一条龙 ssh 命令会被自动模式拦）。所有被改过的 nginx conf / systemd unit / `.env.local` 都留有 `.bak-20260817-*`。
- 两个 Next 看板的后端地址在各自 `frontend/.env.local`（不进 git）：Linux 上已改为 `/usp`、`/lims`，重装机器要记得重写。
- 老端口（IP:端口直连）在 Linux 上已不可达；配置层面各子系统仍保留了 `location = / → /xxx/` 跳转与 `/xxx/api/` 转发，若将来放开某端口可直接用，但**不免登**（不同端口=不同站点）。

## 已知小问题（与门户无关，记录备查）

- LIMS 看板导航栏有 hydration 告警（当前页高亮 SSR/客户端不一致），老问题。
