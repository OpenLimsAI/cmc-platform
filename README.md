# cmab-hub · 统一门户

公司内部所有系统的统一入口：一墙图标、按权限显隐、只开 **5100** 一个端口、登录一次进任何子系统。
完整设计见 `cmab-hub_设计方案.md`，通用铁律见 `~/code/CLAUDE.md`。

## 目录

```
nginx/               统一入口 5100 的反代配置（路由表 + mac/linux server 块），见 nginx/README.md
frontend/            React 18 + Vite + Ant Design 5（门户前端，无独立后端）
  src/config/apps.ts   应用注册表：加系统只改这一个文件（nginx/hub-locations.conf 里同步加两条 location）
  src/auth/access.ts   图标显隐规则（按 MDM 角色码）
  src/stores/authStore.ts  登录态；统一 key cmab_access_token / cmab_user（各子系统照此读 → SSO）
  src/pages/LoginPage.tsx  登录页（账号密码原样转给 MDM）
  src/pages/HubPage.tsx    图标墙
```

## 本地开发

```bash
cd frontend
pnpm install
pnpm build        # tsc 类型检查 + 打包到 dist/ → nginx（5100）直接伺服，改完界面重新 build 即生效
pnpm dev          # http://localhost:5101 只在单独调门户界面时用（自带 /mdm/api 代理，不经 nginx）
```

**正式入口永远是 nginx 的 5100**（配置与安装见 `nginx/README.md`）；Vite dev 的 5101 只是调试用。
前端代码只写相对路径（`/mdm/api/...`），走 nginx 还是走 Vite 代理零差异。

## 加一个新系统

在 `frontend/src/config/apps.ts` 的 `HUB_APPS` 里加一条：`id / name / icon / path / requires / status`。
`requires` 填 `'authenticated'`（登录即可见）或 MDM 角色码数组；`status` 填 `live` / `planned`（标灰）/ `hidden`。
