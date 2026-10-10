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

## 加一个新系统（四步）

1. `frontend/src/config/apps.ts` 的 `HUB_APPS` 加一条：`id / name / icon / path / requires / status`
   （`requires` 填 `'authenticated'` 或 MDM 角色码数组；`status` 填 `live` / `planned`（标灰）/ `hidden`）。
2. `nginx/hub-locations.conf` 加两条 location（`/xxx/api/` 剥前缀转后端、`/xxx/` 原样转前端；独立健康地址按需加精确 location）。
3. 子系统前端自己认前缀 + 改读统一 key（Vite 抄 `cmc-labops/frontend-react/src/shared/base.ts`；Next 抄 `cmc-rd-lims-dashboard/frontend/lib/auth.ts` + `next.config.ts`）。
4. Linux 照 `deploy/linux/NN_xxx.sh` 写部署脚本跑一遍（子系统 nginx 加 `/xxx/` 伺服、前后端只听 127.0.0.1）。不开新的 ufw 端口。

详细约定见 `nginx/README.md`，完整清单见项目 `CLAUDE.md`。

## Linux 部署

正式环境 `172.19.0.105:/opt/cmab-hub`，nginx 听 5100（配置软链自 `nginx/cmab-hub.linux.conf`）。
门户前端改动上线：`ssh -p 13568 prometheus@172.19.0.105 'cd /opt/cmab-hub && git pull && cd frontend && pnpm build'`（静态包立即生效，不用重启 nginx）。
子系统上门户 / 只听本机 / 防火墙：`deploy/linux/*.sh`（按编号顺序，可重复跑；`50_firewall.sh` 需负责人亲自执行）。

CMC 质量分析看板使用 `/qap/`，磁贴仅对 `QAP_QC_GENERAL`、`QAP_QA_RELEASE` 显示；后端在 8040 独立验签，部署入口为 `deploy/linux/45_qap.sh`。QAP 的 5140/8040 不对内网开放。

## 数据中台运维入口

本地注册“数据中台运维”磁贴 `/ops/`，仅MDM `SYS_ADMIN` 可见，临时密码仍按统一规则锁定。独立监控后端再次验签与限制SYS_ADMIN，不能靠磁贴显隐保护数据。固定端口8025/5125；代理API剥 `/ops`，前端保留前缀，公开health路径不转发。统一会话母本不变，既有磁贴顺序不变。Linux正式协调发布须先准备真实监控后端及非模拟前端。2026-10-10按用户本地上线授权，Mac在用Hub构建与/ops路由已发布，5125由monitor LaunchAgent托管明确标注的模拟预览；8025未启动、无真实数据。模拟页可直接查看合成数据，真实数据仍受后端鉴权；当前浏览器未登录，真实角色磁贴点击未验收。未提交/push或部署Linux。

本地验证：已做本地类型检查、Vite构建（产物在临时目录，不覆盖在用dist）、纯角色显隐检查及临时nginx配置的nginx -t；SYS_ADMIN可见，普通/部门管理员/QA/展示/匿名不可见，旧磁贴和顺序保持。真实账号浏览器验收未执行。 本地变更均未提交/push。
