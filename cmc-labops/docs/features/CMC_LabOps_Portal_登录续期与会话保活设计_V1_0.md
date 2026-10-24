# CMC LabOps Portal — 登录续期与会话保活设计 V1.0

| 项 | 内容 |
|---|---|
| 版本 | V1.0（草案，待审阅） |
| 日期 | 2026-06-16 |
| 状态 | **部分实施**：第 1 步「无感自动续期」已上线；第 2 步「空闲超时登出」、第 3 步「编辑防丢」**未实现**。现状以架构 §5.1 / 需求 FR-PLT-011·014 / UI §4.1 为准 |
| 范围 | **仅 cmc-labops**。MDM 及其它姊妹系统不在本次改动内；待 LabOps 验证通过后再统一推广 |
| 不改动 | 不修改 cmab-mdm-platform（MDM）任何代码；不引入本地用户表 |

---

## 1. 背景与问题

**现象**：用户在使用过程中会突然跳回登录页；正在编辑、未保存的内容随之丢失。

**根因**：
1. MDM 签发的 access token 有效期 **30 分钟**。
2. LabOps 前端登录后**只持有 access token，没有任何续期机制**。
3. 30 分钟一到（或页面空闲后回来），下一个 API 请求即返回 `401`；前端拦截器 `client.ts` 的设定是"遇 401 即清除登录态并跳转 `/login`"。
4. 因此表现为**使用中无故跳登录**，且是**规律性复现**（约每 30 分钟一次），并非偶发 bug。

**关键事实**：MDM 登录其实**已经下发了一张 7 天有效的 refresh token**，但它以 **HttpOnly Cookie** 形式存在，LabOps 后端代理登录时**丢弃了它**，从未转交浏览器，因此白白浪费。

---

## 2. 现状分析

### 2.1 认证架构
- LabOps 登录是**代理给 MDM**：`backend/routers/auth_router.py` 的 `/auth/login` 用 httpx 把 `{username, password}` 转发到 MDM `/auth/login`，并信任返回的 JWT。
- LabOps **无本地用户表**；`username` 仅作审计快照（audit_log）。
- LabOps 后端鉴权：`auth.py` 解码 MDM JWT，取 `sub`(user_id) / `username` / `roles`。

### 2.2 MDM 令牌机制（只读核实所得）
| 项 | 值 |
|---|---|
| access token | JWT，有效期 **30 分钟**（生产 `ACCESS_TOKEN_EXPIRE_MINUTES=30`）；claims：`sub`/`username`/`roles`/`type=access` |
| refresh token | **HttpOnly Cookie** `cmab_refresh_token`，有效期 **7 天**；属性 `httponly=true, secure=is_production, samesite=strict`；**每次 refresh 轮换**（旧的失效，发新的） |
| 登录端点 | `POST /api/v1/auth/login` → body 返回 `access_token`；同时 `Set-Cookie: cmab_refresh_token` |
| 续期端点 | `POST /api/v1/auth/refresh` → 读 Cookie `cmab_refresh_token`，返回新 `access_token` 并轮换 Cookie |
| 登出端点 | `POST /api/v1/auth/logout` → 撤销 refresh token + 清 Cookie |

### 2.3 当前缺陷点（待修）
- `auth_router.login` 仅 `return data`（JSON body），**丢弃了 MDM 的 `Set-Cookie`** → refresh 凭证从未到浏览器。
- 前端 `auth.ts` 的 `TokenResponse` 未声明 refresh，`authStore` 仅存 access token。
- `client.ts` 响应拦截器：`401 → 清 token → 跳 /login`，**无续期、无重试**。
- 无空闲计时；无编辑防丢保护。

---

## 3. 设计目标与原则

**目标**（分三步，可独立交付与验证）：
1. **自动续期** — 消除"使用中突然跳登录"。
2. **空闲超时登出** — 无操作 30 分钟才退出（安全）。
3. **编辑防丢** — 认证状态变化绝不静默丢弃用户已输入内容。

**原则**：
- 只改 LabOps；MDM 零改动。
- refresh token **全程 HttpOnly Cookie，绝不写入 localStorage / JS 可读区**。
- 续期与登出**均由"最后操作时间"驱动**（活动驱动），保证"在用就不退、不用才退"。
- 每步改动可独立回滚。

---

## 4. 详细设计

### 4.1 第一步：自动续期

#### 4.1.1 后端：LabOps 作为 refresh Cookie 的"中转站"

**(a) 改造 `POST /api/auth/login`**
- httpx 调用 MDM `/auth/login` 后，从 **httpx 响应的 Cookie**（`resp.cookies` 或 `Set-Cookie` 头）提取 `cmab_refresh_token` 的值。
- 用 FastAPI `Response.set_cookie` 把它**转存为 LabOps 自己域的 Cookie**，下发给浏览器：

  | 属性 | 取值 | 说明 |
  |---|---|---|
  | name | `cmab_refresh_token` | 沿用同名，便于排查 |
  | value | MDM 返回的 refresh token | 原样中转 |
  | httponly | `true` | JS 不可读，防 XSS 窃取 |
  | secure | 由环境变量 `COOKIE_SECURE` 控制，**当前 http 内网=false** | 见 §5，HTTPS 后改 true |
  | samesite | `lax` | LabOps 前端与其 API 同源（同 nginx），lax 足够；避免 strict 带来的跨页面首请求不带 Cookie |
  | path | `/api/auth` | 仅在调用 auth 接口时携带，缩小暴露面 |
  | max_age | `7*86400` | 与 MDM refresh 有效期一致 |
- access token 仍照常在 JSON body 返回（现有前端不受影响）。

**(b) 新增 `POST /api/auth/refresh`**
- 从浏览器请求读 Cookie `cmab_refresh_token`；缺失则返回 `401`。
- httpx 携带该 Cookie 调用 MDM `/api/v1/auth/refresh`：
  - 成功：拿到**新 access_token**；MDM 同时轮换 refresh（返回新 `Set-Cookie`）→ 提取新值并**重新 `set_cookie`** 下发浏览器；返回新 access_token（结构同 login 的 token 部分）。
  - 失败（MDM 返回 401/refresh 过期或被撤销）：清除 LabOps 的 refresh Cookie，返回 `401`。
- httpx 一律 `trust_env=False`（本机有 SOCKS 代理，既有约定）。

**(c) 改造 `POST /api/auth/logout`**
- 读 Cookie → httpx 转发 MDM `/auth/logout`（撤销 refresh）→ 清除 LabOps refresh Cookie。
- 即使 MDM 调用失败也要清本地 Cookie（best-effort 撤销）。

**涉及文件**：`backend/routers/auth_router.py`（login/refresh/logout）、`backend/schemas.py`（如需 refresh 响应模型）、`backend/config` 或 env（`COOKIE_SECURE`、`MDM_BASE_URL` 已有）。

#### 4.1.2 前端：续期逻辑（核心）

存储约定：
- access token：仍存 `localStorage`（供请求头携带）。
- refresh token：**只在 HttpOnly Cookie**，前端代码不触碰。
- `lastActivity`：最后操作时间戳（§4.2 共用）。

四套机制（缺一不可）：

1. **主动续期**：请求发出前（或一个轻量定时器）解析 access token 的 `exp`，若**剩余 < 5 分钟**且**用户未空闲超时**，先 `await` 一次 `/api/auth/refresh` 换新 token 再发请求。
2. **被动兜底**：任意 API 响应 `401` → 先尝试 `/api/auth/refresh`：
   - 成功：用新 token **重放原请求**；
   - 失败：清登录态、跳 `/login`。
3. **防重放死循环**：被动重放**只重试一次**（给请求打 `_retried` 标记）；重试后仍 401 即登出，绝不无限刷。
4. **并发控制**：用**单例 `refreshPromise`**——多个请求同时 401 时只发起**一次** refresh，其余请求 `await` 同一个 promise，拿到新 token 后一起重放。

其它：
- axios 实例设 `withCredentials: true`（请求自动携带 refresh Cookie；refresh 接口需要）。
- refresh 成功后更新 `authStore` 的 access token + `localStorage`。
- **多标签页同步**：通过 `localStorage` 的 `storage` 事件广播——某标签登出/换 token 时，其它标签同步登出/更新，避免状态分叉。

**涉及文件**：`frontend-react/src/api/client.ts`（拦截器主体）、`api/auth.ts`（refresh API + 类型）、`stores/authStore.ts`（token 更新/活动时间/多标签同步）。

> 注：refresh 触发**必须判断"未空闲超时"**（见 §4.2），否则人已离开仍不断续期，永远不会空闲登出——这是第 1、2 步的关键衔接点。

### 4.2 第二步：空闲超时登出（无操作 30 分钟）

- **活动追踪**：监听 `mousedown/keydown/click/scroll/touchstart` 等交互事件（**节流**，如每 5–10 秒最多更新一次），以及每次 API 请求，更新 `lastActivity`。
- **空闲判定**：一个轻量定时器（每 30–60 秒）检查 `now - lastActivity`：
  - 超过 **30 分钟（可配置）** → 主动登出（走统一登出流程：清登录态 + 调 logout 撤销 refresh + 跳登录）。
  - 登出前若存在未保存编辑 → 走 §4.3 的防丢提示，不静默清空。
- **与续期衔接**：续期只在"未空闲超时"时进行；空闲超时优先于续期。
- 阈值常量集中可配，测试时可临时调短（如 1–2 分钟）加速验证。

**涉及文件**：`stores/authStore.ts` 或新增 `shared/idleTimer`、应用根组件挂载监听。

### 4.3 第三步：编辑防丢（分级）

**分级策略**（评审采纳：关键表单加草稿，其余仅提示）：

| 级别 | 适用 | 保护手段 |
|---|---|---|
| **关键表单** | 批次编辑 + 双人复核弹窗（`BatchEditModal`）——字段多、含第二人电子签名，丢失代价最高 | ① dirty 标记；② 离开/刷新前提示；③ **localStorage 草稿**：表单变更即存草稿，重开/登录失效/保存失败后可恢复；成功提交后清草稿。**复核人密码绝不写入草稿**（敏感） |
| **普通表单** | 其它录入/编辑 | ① dirty 标记；② 离开/刷新/路由跳转前提示"有未保存内容" |

- **dirty 标记**：表单字段变更后置 `dirty = true`，提交成功或重置后清除。
- **离开提示**：`beforeunload`（刷新/关页）+ 路由守卫（SPA 内跳转）+ 登出前检查。
- **草稿键设计**：按 `用户ID + 表单类型 + 业务主键`（如批次 ID）区分，避免串号。
- **安全**：草稿**只存非敏感业务字段**；密码、token 一律不入草稿。

**涉及文件**：`BatchEditModal.tsx`（草稿+dirty）、通用 `useUnsavedGuard` hook、路由层守卫。

---

## 5. 安全考量

- **refresh token 始终 HttpOnly Cookie**，JS 不可读，降低 XSS 窃取风险；不进 localStorage。
- **Cookie 作用域收敛**：`path=/api/auth`、`samesite=lax`，仅认证接口携带。
- **登出撤销**：logout 调用 MDM 撤销 refresh（jti 失效），而非仅清本地。
- **HTTPS（后续整改项）**：当前生产为**内网 http**（nginx `listen 5110`），故 `secure=false` 才能让 Cookie 生效。**内网不等于可信，登录态 Cookie 仍建议加密传输**——列入后续整改：上 HTTPS 后将 `COOKIE_SECURE=true`。本设计用环境变量预留开关，HTTPS 落地即可切换，无需改码。
- 草稿不含敏感字段（密码/令牌）。

---

## 6. 验收标准（Definition of Done）

| 模块 | 必达效果 |
|---|---|
| 登录 | LabOps 正确转存 MDM 的 refresh Cookie（HttpOnly，不进 localStorage）|
| 自动续期 | access 快过期前（提前 3–5 分钟）自动 refresh，且**活动驱动** |
| 401 兜底 | 任意 401 → 先 refresh → 重放原请求（**只重试一次**）|
| 并发控制 | 多请求同时 401，只续一次，其余排队等待后重放 |
| 空闲登出 | **无操作** 30 分钟才退，不是固定踢人 |
| 编辑保护 | 有未保存内容不得静默跳登录；离开/刷新前提示 |
| 草稿恢复 | **关键表单**（批次编辑/复核）做草稿，登录失效/保存失败可恢复 |
| 安全 | refresh 始终 HttpOnly Cookie；HTTPS 列后续整改 |
| 多标签 | 多标签页登录/登出/续期状态一致 |

---

## 7. 测试方案

**本地加速**：临时把 `ACCESS_TOKEN_EXPIRE_MINUTES` 调小（如 2 分钟）、空闲阈值调到 1–2 分钟。

| 场景 | 预期 |
|---|---|
| 登录后持续操作，跨过 access 有效期 | 无感续期，**不跳登录** |
| 令牌已过期后首次操作（被动） | 自动 refresh + 重放，操作成功，不跳登录 |
| refresh 也失效（7 天到期/被撤销） | 干净登出到登录页 |
| 多个请求同时遇 401 | 只发一次 refresh，全部重放成功 |
| 登录后无任何操作 30 分钟 | 自动登出 |
| 编辑弹窗填一半触发登出/刷新 | 提示拦截；关键表单可从草稿恢复 |
| 多标签页：一个登出 | 其它标签同步登出 |
| 复核人密码 | 不出现在草稿/localStorage 中 |

**生产验证**：第 1 步部署后，在生产实测"使用中不再跳登录"，确认通过后再进入第 2、3 步。

---

## 8. 影响范围、交付与回滚

- **影响范围**：仅 cmc-labops（前端 + 后端 auth 接口）。数据库无改动。
- **姊妹系统**：MDM 续期机制为各系统共性问题；**LabOps 验证通过后，再把同套前端方案统一推广**到其它系统（本设计可作为模板）。
- **分步交付**：第 1 步（自动续期）→ 生产验证 → 第 2 步（空闲登出）→ 第 3 步（编辑防丢）。每步独立提交。
- **回滚**：前端拦截器改动、后端 refresh 接口均可独立回退；login 的 Cookie 中转为新增行为，回退即恢复旧逻辑（access-only）。

---

## 9. 待审阅确认点

1. 空闲超时阈值：**30 分钟无操作**（确认或调整）。
2. 编辑防丢范围：**关键表单加草稿 + 其余简单提示**（评审推荐方案，确认或调整）。
3. HTTPS：确认列入后续整改、当前先 http 跑通。
4. 文档其余技术细节是否认可，认可后据此施工第 1 步。
