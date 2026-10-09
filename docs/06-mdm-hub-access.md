# 06 · MDM 身份、权限与 Hub 接入

> 版本：0.4｜日期：2026-10-02｜状态：Mac 已实现，验收部分完成；Linux 未发布。

## 1. 已确定的接入边界

用户唯一入口为 Hub。Mac 开发验收经 `http://localhost:5100/water/`，Linux 工作路径为 `http://172.19.0.105:5100/water/`，路径尚未注册。前后端监听本机固定端口，端口分配前核对 PORTS、实际监听、LaunchAgent/systemd/nginx。

MDM 维护账号与角色并签发令牌；本项目本地验签和检查业务角色。Hub `requires` 控制磁贴可见性，后端守卫保护业务 API。应用用户不能通过绕过磁贴获取未授权数据。

## 2. 角色矩阵工作方案

用户已确定新增两档权限：“仅查看”和“查看＋导出”。依据现有 MDM access token 的 roles 契约，工作设计以两个下游业务角色承载；角色码和实际分配配置见 OP-04，MDM 尚未建立。一期不设业务编辑/审批权限。

| 身份/拟议角色码 | Hub 磁贴 | 查看趋势/汇总/明细/追溯 | 导出 |
|---|---|---|---|
| 未登录/令牌无效 | 需登录 | 401 | 401 |
| 已登录且无水系统角色 | 隐藏 | 403 | 403 |
| `CMC_WATER_VIEWER`（仅查看） | 可见 | 允许 | 全部导出类型 403 |
| `CMC_WATER_EXPORTER`（查看＋导出） | 可见 | 允许 | 趋势图、原始数据表、组合包均允许 |
| `SYS_ADMIN` | 可见 | 工作方案：允许 | 工作方案：允许 |
| 任意临时密码账号 | 按 Hub 现有规则拦截 | 403，提示先去 MDM 改密码 | 同左 |

角色码确认后由 MDM 管理界面或受控幂等配置建立并分配；不要重新灌种子数据。角色名称相同不意味着两环境已经配置相同，Mac/Linux 各自核对。当前 MDM access token 提供 roles；不假设 token 含全部细粒度 permissions。

如果要求部门负责人分配角色，需要单独确认 DEPT_ADMIN 的同部门范围和 `dept_admin.delegable_role_prefixes`；不能因为建立 `CMC_WATER_*` 角色就推断部门管理员已可分配。维护账号授权的人不因此需要看板内“管理页面”。

## 3. 验签与会话

后端使用当前 MDM 验签配置及受信算法，依次检查签名、有效期、`type='access'`、用户标识、`must_change_password` 和角色；SYS_ADMIN 同样先通过身份和临时密码检查。查看/导出白名单为空或非法时启动配置校验失败，导出角色集合必须包含于查看角色集合，禁止隐式开放。验签密钥未配或无效时验收/生产服务启动失败。

MDM 支持的签名算法和实际部署配置应实时核对；不假设有 JWKS/introspection 或固定采用 HS256。当前认证代码的 access claims 无既定 iss/aud 契约，新增校验前与 MDM 协调。

前端复用 Hub `frontend/src/shared/cmabSession.ts`：

- 统一 `cmab_access_token`、`cmab_user`、`cmab_last_active`。
- 登录和刷新直接走 `/mdm/api/v1/auth/`，401 最多续一次并重放；失败回 Hub 登录。
- 403 权限拒绝/临时密码不能进入刷新循环。
- 会话时长读 MDM session-policy，空闲/硬上限/多标签同步退出使用统一守卫。
- 登录后返回本站 `/water/...`，redirect 只接受合法站内路径；调用 MDM logout 撤销当前 refresh token，并清理本机共享登录态。MDM 不可达时仍完成本地退出，但不声称服务端撤销已成功。

签名密钥、Cookie 和 token 不写入文档、Git、导出或日志。

## 4. Hub 四项接入

| 部位 | 工作设计 | 验收 |
|---|---|---|
| `cmab-hub/frontend/src/config/apps.ts` | id `water`，名称“制药用水看板”，path `/water/`，requires 对齐已确认角色 | 有权可见/无权隐藏/临时密码锁定 |
| `cmab-hub/nginx/hub-locations.conf` | `/water/api/` 去掉 `/water` 转后端 `/api/`；`/water/` 保留前缀转前端 | API/资源/深链均通过 |
| 本项目前端 | Vite base `/water/`，Router basename `/water`，API `/water/api/v1` | 刷新深链、登录返回、导出地址正确 |
| Linux 服务及 Hub 发布脚本 | 前后端本机监听，静态资源回落正确，脚本记录 Hub/应用各自 SHA | 只经 Hub 提供用户访问 |

Hub 母本变更前盘点下游；新项目通常复制现有母本并记录其版本，不为新看板改全局会话策略。nginx 上游 Mac 解析/IPv6 约定按 Hub 文件核对，不能机械套用 Linux 配置。

## 5. 参考与验收

[Hub 指引](../../cmab-hub/AGENTS.md)、[nginx 约定](../../cmab-hub/nginx/README.md)、[会话母本](../../cmab-hub/frontend/src/shared/cmabSession.ts)、[MDM 指引](../../cmab-mdm-platform/AGENTS.md)。这些文件有历史状态，当前角色/服务仍需实测。

权限验收使用隔离或专用测试账号，覆盖矩阵每行以及真实 API；不能仅截图磁贴或只测 health。见 docs/09。

## 6. 权限变化的生效时点

当前 MDM 刷新接口重新读取用户状态和角色并签发 access token；本项目本地验签不逐请求查询 MDM。已签发的有效 access token 含旧角色快照，移除角色、停用用户或退出后，并不因此在所有下游 API 立即失效；新 token 采用更新后的角色，旧 token 到 exp 后被拒绝。有效期来自实际 MDM 策略，不在本项目另写固定时长。

前端磁贴/按钮权限以当前 access token 的角色快照更新，不长期依赖可能未随刷新更新的 cmab_user.roles；角色变化后清理相关缓存与旧权限页面。若用途要求即时撤销，需与 MDM 协调额外机制并记录决定，不能把现有本地验签描述为实时授权查询。

将导出角色同时纳入查看/导出集合，仅查看角色只纳入查看集合；SYS_ADMIN 按确认后的矩阵配置；Hub requires 对齐查看角色，SYS_ADMIN 的门户短路规则单独核对。实际有效角色名仍以 OP-04 确认为准。

## 7. 导出权限执行

页面只为有导出权限的用户显示“导出趋势图”“导出原始数据表”“导出图表组合包”。后端对 POST exports 的 chart/table/bundle 每一种类型独立执行同一导出守卫；不提供绕过该守卫的文件下载路由或 ECharts 内置另行导出入口。仅查看用户依然可以正常查看和筛选图表、明细与来源。

同时持有两个角色时按查看＋导出权限处理。MDM 中角色展示名称体现两档用途；角色分配与回收沿用 MDM 流程，按第 6 节验证刷新和旧 token 的生效窗口。权限限制针对应用提供的导出功能，不承诺阻止操作系统截图或浏览器手工复制。


## Mac 实施状态（2026-10-02）

V0.3 的工作设计和历史复核记录保留用于追踪；当前事实以 [Mac 验收记录](acceptance/mac-20261002.md) 和 docs/10 新决定为准。基础应用已运行，不能据此将所有验收项或 Linux 发布登记为通过。


## 实际Mac配置

两个角色已由正常admin会话建立，没有绑定人员或MDM管理权限，既有授权不变。应用查看白名单为Viewer/Exporter/SYS_ADMIN，导出为Exporter/SYS_ADMIN。Hub磁贴包含两个业务角色（既有SYS_ADMIN可见规则仍适用）；/water/api/代理8015、/water/代理5115，裸/water重定向。前端共享会话文件与Hub母本一致，未另建账号/密码流程。020104档位待确认，真实两档权限尚未完成验收。
