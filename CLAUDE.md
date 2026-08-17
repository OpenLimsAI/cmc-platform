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

- ✅ §10 ① 前端脚手架：`frontend/`（登录页转 MDM + 图标墙 + 按角色显隐 + 退出），`pnpm build` 通过、浏览器验证过。
- ✅ §10 ③ 应用注册表：`frontend/src/config/apps.ts`；显隐规则 `src/auth/access.ts`。
- ✅ §10 ④ nginx 反代：`nginx/`（`hub-locations.conf` 路由表两边共用 + mac/linux 两份 server）。**Mac 已上线**：brew nginx 听 5100、伺服 dist、`/mdm/*` `/labops/*` 全通。Linux 待仓库落地后软链（`nginx/README.md`）。
- **令牌统一 key 已拍板**：`cmab_access_token` + `cmab_user`（设计方案 §5），门户已按此写；子系统各自改读，门户不做桥接。
- 端口：**5100 = nginx（唯一对外门）**；`5101` = 门户 Vite dev（只在单独调界面时用）。
- ✅ MDM 前端已改完（子路径 + 统一 key），本地经 5100/mdm/ 验证通过；MDM 仓库已本地提交待 push。**nginx 前端一路不剥前缀**（Vite dev 只认带前缀请求），已更新路由表。
- **下一步**：§10 ② 与 MDM 窗口对齐 → ⑤ 逐个子系统改子路径（Vite：base/basename/API 相对路径 + 读统一 key；Next：basePath）→ ⑥ SSO 验证 → PORTS.md 改「在用」→ Linux 部署。
- 已知待拍板：`apps.ts` 里各应用 `requires` 角色码是按子系统现有代码填的默认值，最终以 MDM 后台为准。
