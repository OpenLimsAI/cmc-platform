# CMAB HUB · 统一门户设计方案

> **用途**：本文件是「统一门户（HUB）」的设计交接材料，供**后续单独开的窗口**冷启动直接开工。
> **成文**：2026-07-10，由 `rd-batch-registry`（批号管理）窗口顺带产出；批号系统与本门户**各自独立开发**。
> **上位约束**：先读 `~/code/CLAUDE.md`（总纲铁律）、`~/code/PORTS.md`（端口）、`cmab-mdm-platform`（身份中心）。本文只写门户专属设计，通用规矩不重复。
> **已拍板决策**：① **一步到位做深版**（单一入口 + 反向代理），不做浅版过渡；② 端口 **5100**；③ 技术栈 React + Vite + Ant Design；④ **MDM 当统一身份中心**。

---

## 1. 它是什么（一句话）

一个总入口——**一墙图标**，点进公司各内部系统（MDM 主数据、LabOps 实验室运营、上游工艺看板、批号管理…）。**有权限的图标才显示，没权限的不出现**。用户**只开一个端口 5100、只登录一次**，进任何子系统都不用再记端口、不用重复登录。形态参照 waters_connect HUB。

## 2. 为什么直接做深版（不做浅版过渡）

| | 浅版（图标墙跳转） | **深版（单一入口 + 反代）← 采用** |
|---|---|---|
| 端口 | 图标跳到各系统的 `host:端口`，用户仍会看到多个端口 | 全世界只看到 `5100` 一个门 |
| 重复登录 | 各系统不同端口 = 浏览器认作不同站点，**跳过去要重登** | 全部同源 → 登录令牌天然共享 → **单点登录几乎白送** |
| 工作量 | 小（一个登录页 + 图标墙） | 大（要把每个子系统改成"挂在子路径下"） |

深版把"不用记端口"和"不用重复登录"**两件事一次解决**，代价是要动每个现有前端的路径配置——所以负责人决定"一次性到位"，把这些改造一起做完。

## 3. 端口：5100（5000 禁用）

- **对外唯一端口 = `5100`**（HUB 前端 + nginx 反代入口）。按 `PORTS.md` 前端 `51N0` 规则，5100 是"00 号"前端位，空着，合规好记。已在 `PORTS.md` 登记为「规划中」。
- ⚠️ **禁用 5000**：macOS 自带 AirPlay（隔空播放接收）默认占 `127.0.0.1:5000`，会时好时坏地冲突。
- **各子系统内部端口不变**（MDM 18000/15173、LabOps 8010/5110、批号 8080/5180、usp 看板 8070/5170…），只是**不再对用户暴露**，全部藏在 5100 后面。

## 4. 架构（深版）

一台 nginx **只监听 5100**，按路径前缀反向代理到各子系统：

```
5100/              → HUB 前端（React + Vite + AntD 静态站）
5100/mdm/          → MDM 前端        →（内部）127.0.0.1:15173
5100/mdm/api/      → MDM 后端        →（内部）127.0.0.1:18000
5100/labops/       → LabOps 前端     →（内部）127.0.0.1:5110
5100/labops/api/   → LabOps 后端     →（内部）127.0.0.1:8010
5100/batch/        → 批号前端        →（内部）127.0.0.1:5180
5100/batch/api/    → 批号后端        →（内部）127.0.0.1:8080
5100/usp/          → 上游工艺看板    →（内部）127.0.0.1:5170（Next）
```

**关键红利**：所有子系统都成了 `localhost:5100` 的**同源**内容 → 浏览器的 `localStorage` / cookie 在各子路径间天然共享 → 登录一次，令牌所有子系统都读得到，**单点登录基本免费**。这正是深版的价值所在。

## 5. 身份与权限（MDM = 统一身份中心）

- **登录**：走 MDM `/auth/login`（LabOps 等已在用这套，顺理成章）。
- **权限**：HUB 登录后向 MDM 拿当前用户的角色/权限清单。
- **图标显隐**：每个应用在**配置**里声明"需要什么角色/权限"；HUB 据此决定图标亮不亮、能不能点。
- **令牌存放（2026-08-17 拍板：统一 key）**：同源下 `localStorage` 跨子路径共享。全公司统一约定：
  - `localStorage['cmab_access_token']` = MDM 签发的 access token 原文（JWT）
  - `localStorage['cmab_user']` = MDM 登录响应里的 `user` 对象 JSON（`username / full_name / department / roles / permissions / must_change_password`）
  - 门户按此写入；**各子系统前端改成读这两个 key**（现状：MDM `cmab-mdm-auth`、LabOps `token`、批号 `rbr_token`，各改各的），门户**不做**按旧 key 写副本的桥接。
- **待 MDM 侧配合**：需要 MDM 能吐"这个用户能访问哪些应用/有哪些角色"——用现有权限接口拼或新开一个聚合接口，二选一（在门户窗口里和 MDM 窗口协调）。

## 6. 应用注册表（配置驱动，加系统不改代码）

图标墙由一张**配置**渲染（JSON/YAML 文件或一张小表）。加新系统 = 加一条配置：

```yaml
apps:
  - id: mdm
    name: 主数据 MDM
    icon: database          # 图标名/或内置 svg
    path: /mdm/
    requires: [authenticated]      # 只要登录就能进
    status: live
  - id: labops
    name: 实验室运营 LabOps
    path: /labops/
    requires: [LABOPS_USER]        # 需要该角色/权限
    status: live
  - id: batch
    name: 批号管理
    path: /batch/
    requires: [BATCH_USER]
    status: planned                # 开发中，可先隐藏或标灰
  - id: usp
    name: 上游工艺看板
    path: /usp/
    requires: [USP_VIEWER]
    status: live
```

## 7. 各子系统要做的改造（深版的主要工作量）

深版最花时间的不是门户本身，而是**把每个现有前端改成能"挂在子路径下"**。逐个清点：

| 子系统 | 栈 | 要改什么 |
|---|---|---|
| MDM | React + Vite | `vite.config` 设 `base: '/mdm/'`；React Router `basename='/mdm'`；API baseURL 改相对 `/mdm/api` |
| LabOps | React + Vite | 同上，前缀 `/labops/` |
| 批号管理 | React + Vite | 同上，前缀 `/batch/`（新项目，建议**一开始就按子路径写**，省得回头改） |
| 上游工艺看板 | Next.js | `next.config` 设 `basePath: '/usp'`、`assetPrefix` |

**通用铁律**：所有 API 调用**一律用相对路径**（`/xxx/api/...`），**绝不写死 `host:端口`**；各后端确认反代下的路径前缀、CORS、cookie domain 都对得上。

> 提示：批号系统是新写的，**从第一行就按 `/batch/` 子路径 + 相对 API 来写**，将来接门户零改动——这条已同步给批号窗口。

## 8. 技术栈

- 前端：**React 18 + Vite + Ant Design 5**（对齐总纲 §6 与 MDM）。
- 反代：**nginx**（单入口 5100，path 路由）。
- 后端：可**极薄或无**——HUB 主要是静态站 + 调 MDM 接口；若要做"应用注册表 + 权限聚合"可加一个很小的 FastAPI，但优先无后端。

## 9. 部署（对齐总纲 §7）

- **Mac 本地**：nginx 监听 5100 反代各 LaunchAgent 托管的子系统；HUB 静态产物由 nginx 伺服。
- **Linux 正式**：`/opt/cmab-hub`，nginx 监听 5100，path 反代到各 systemd 子服务；属主 `prometheus`。
- 独立 GitHub repo。

## 10. 待办清单（交给门户窗口）

- [x] HUB 前端脚手架：登录页（走 MDM）+ 图标墙 + 按权限显隐图标。（2026-08-17 完成，见 `frontend/`）
- [ ] 与 MDM 窗口对齐：提供"我可访问的应用/角色"接口 + 统一令牌形态。
- [x] 应用注册表配置（§6）落地。（已随脚手架落地为 `frontend/src/config/apps.ts`）
- [x] nginx 单入口反代配置（§4 的 5100 path 路由）。（2026-08-17 完成：`nginx/` 目录；Mac brew nginx 已上线 5100，Linux 待仓库落地后软链，见 `nginx/README.md`）
- [ ] 逐个子系统改子路径 base（§7：MDM / LabOps / 批号 / usp…）。
- [ ] **SSO 验证**：登录一次，点各图标进子系统全部免登。
- [ ] `PORTS.md` 把 5100 状态从「规划中」改「在用」。
- [ ] 部署（Mac nginx + Linux `/opt/cmab-hub` nginx/systemd）。

## 11. 与批号系统的关系

批号系统（`rd-batch-registry`）是门户里的**一块图标**（`/batch/`）。两者**独立开发**：批号窗口只管把系统做出来、并按 `/batch/` 子路径 + 相对 API 写好；门户窗口把它列进注册表即可。

---

> **速记**：一个门（5100）、一次登录（认 MDM）、一墙图标（按权限显隐）、藏起所有端口（nginx 反代）。深版一步到位，代价是把每个前端改成能挂子路径。
