# CLAUDE.md — cmab-hub（统一门户）

> 本项目专属说明。通用铁律见 `~/code/CLAUDE.md`（总纲），端口见 `~/code/PORTS.md`。**先读完整设计：`cmab-hub_设计方案.md`。**

## 一句话定位

公司内部所有系统（MDM / LabOps / 上游工艺看板 / 批号管理…）的**统一总入口**：一墙图标、按权限显隐、只开一个端口 5100、登录一次进任何子系统不重复登录。形态参照 waters_connect HUB。

## 已拍板的硬决策（别再推翻）

1. **一步到位做深版**：单一入口 nginx（`5100`）+ 路径反向代理到各子系统，不做"图标跳转"的浅版过渡。深版才能同时解决"不用记端口"和"不用重复登录"。
2. **端口 = 5100**。⚠️ **禁用 5000**（macOS AirPlay 占用）。已在 `PORTS.md` 登记为「规划中」，上线后改「在用」。
3. **技术栈 = React + Vite + Ant Design**（对齐总纲 §6 与 MDM）。
4. **MDM 当统一身份中心**：登录走 MDM `/auth/login`，权限清单向 MDM 拿，据此决定图标显隐。

## 干活前必须知道的坑

- **同源是 SSO 的关键**：所有子系统都反代到 `localhost:5100` 之下 → 令牌天然共享。**动手前先和各子系统对齐令牌形态**（都用 localStorage 还是 cookie），别一半一半。
- **深版主要工作量在改子系统**，不在门户本身：每个现有前端要支持"挂子路径"（Vite `base`/Router `basename`/相对 API；Next 用 `basePath`）。详见设计方案 §7。
- **批号系统**从一开始就按 `/batch/` 子路径 + 相对 API 写，接门户零改动——不用你替它改。

## 现状（2026-08-17）

- ✅ 前端脚手架 `frontend/`（登录页转 MDM + 图标墙 + 按角色显隐）、应用注册表 `src/config/apps.ts`。
- ✅ nginx 反代 `nginx/`：5100 唯一入口，路由表两边共用；**Mac brew nginx 已上线**。约定：`/xxx/api/` 剥前缀转后端；`/xxx/` **不剥**，前端自己认前缀（Vite `base` / Next `basePath`）。
- ✅ 统一令牌 key `cmab_access_token` + `cmab_user`（设计方案 §5）；子系统旧 key 自动迁移。
- ✅ 子系统已改完并推 GitHub：**MDM**(`/mdm/`)、**LabOps**(`/labops/`)、**usp 看板**(`/usp`)、**LIMS 看板**(`/lims`)。Mac 上 SSO 实测：门户登录一次，四个系统全部免登。
- ⬜ **批号管理**由批号窗口自己改（`/batch/` + 统一 key，抄 LabOps `src/shared/base.ts`）——门户不替它改。
- ⬜ 成本模型未纳入本轮（注册表里标 planned）。
- ✅ **Linux 已上线（2026-08-17）**：`/opt/cmab-hub` + nginx 5100；MDM/LabOps/usp/LIMS 已 pull+build 并挂上，**前后端全部改为只听 127.0.0.1**（内网老端口不可达）。部署脚本 `deploy/linux/*.sh`（可重复跑）。
- ⬜ 防火墙 `deploy/linux/50_firewall.sh`（只放行 13568/5100/5180）待负责人亲自执行（自动模式不允许我改防火墙）。
- ⬜ 5180 批号系统临时仍对外；批号窗口按 `/batch/` 改完部署后：其 nginx 改 listen 127.0.0.1 + `sudo ufw delete allow 5180/tcp`。
- ⬜ 界面美化放最后（负责人拍板：先功能后界面）。
- 已知：LIMS 看板导航栏有个 hydration 告警（当前页高亮 SSR/客户端不一致），老问题，与门户无关。
