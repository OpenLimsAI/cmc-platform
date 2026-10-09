# 06 · MDM身份、权限与Hub接入

> 版本：0.6｜日期：2026-10-09｜状态：现行配置与代码契约；真实环境验收见 STATUS/docs/09。

## 1. 入口与职责

Hub唯一入口：Mac `http://localhost:5100/water/`，Linux `http://172.19.0.105:5100/water/`。应用后端/前端分别回环8015/5115；MDM是账号/角色权威源。本系统没有登录密码接口、用户表或签发令牌能力。

Hub注册和代理代码已有water配置，磁贴requires包含两个水系统角色，门户SYS_ADMIN可见规则单独由Hub执行。下游业务API始终独立鉴权；身份/角色配置动作和真实API验收分别登记。

## 2. 角色契约与实际配置范围

| 身份 | 查看API | chart/table/bundle导出 |
|---|---|---|
| 无令牌、无效/过期、refresh类型 | 401 | 401 |
| 有效access但无查看角色 | 403 | 403 |
| CMC_WATER_VIEWER | 允许 | 403 |
| CMC_WATER_EXPORTER | 允许 | 允许 |
| SYS_ADMIN | 在查看/导出白名单内时允许 | 在导出白名单内时允许 |
| must_change_password=true | 403先改密码 | 403先改密码 |

环境模板的查看集合为Viewer/Exporter/SYS_ADMIN，导出为Exporter/SYS_ADMIN；代码按实际环境白名单检查，不按用户名放行、不对SYS_ADMIN另作无条件短路。两集合非空合法，导出必须为查看子集。不同于应用代码，角色建立/人员分配是MDM环境配置；历史Mac记录建立两个空业务角色，Linux及真实两档身份仍待验收（OP-04）。

不重新灌种子。若要部门负责人分配，另核对DEPT_ADMIN范围和可委派前缀，不能推断业务角色已可委派。

## 3. 后端身份检查

core.py配置固定受信算法HS256或RS256、JWT_VERIFY_KEY；缺失/短密钥、非法算法或角色配置使加载失败。RS256公钥通过JWT_VERIFY_KEY配置，当前没有独立公钥路径设置或JWKS访问。

JWT要求exp/sub/type，验证签名/到期、type=access、数字形式sub及字符串roles数组；must_change_password=true返回403。verify_aud关闭，当前没有另配issuer/audience契约。角色守卫应用于全部业务路由，匿名仅health。

本地验签不逐次读取MDM用户状态。已签发access携旧角色直至到期；MDM刷新重读状态/角色。权限移除、停用和退出不保证下游旧access立即失效。若要求即时撤销，先协调MDM，不擅自引入新身份系统。

## 4. 前端会话现状和未完成点

共享键cmab_access_token/cmab_user/cmab_last_active，MDM同源路径/mdm/api/v1/auth。transport遇401只续一次并重放；仍401或刷新失败清本地会话并跳Hub登录；403不续期。并发刷新复用母本promise。

显式退出按钮调用mdmLogout，尝试撤销refresh后清本地共享态；MDM失败仍清本地，但不声称服务端撤销成功。登录由Hub处理，本项目回跳/login?redirect=当前站内路径；redirect安全验证归Hub。

守卫读取MDM会话策略，母本自带取不到策略时的保守兜底，不另建固定业务会话时长。母本与本地副本本轮cmp一致，但应用onLogout回调目前只跳转；不能等同母本logoutToLogin完成的清理/撤销流程。跨标签角色变化回调也尚未可靠验证（GAP-06）。同页观察到身份/角色变化时，会清查询缓存、追溯和旧导出；单纯到期续期不重建查询。

导出按钮按context.capabilities.export显示；真正授权由后端守卫。权限限制针对应用导出功能，不承诺阻止系统截图或手工复制。

## 5. 四项接入契约

| 部位 | 当前代码 |
|---|---|
| Hub apps.ts | id=water，path=/water/，requires两个业务角色 |
| Hub hub-locations.conf | 裸/water转带斜杠；/water/api/→127.0.0.1:8015/api/；/water/→127.0.0.1:5115并保留前缀 |
| 本项目前端 | Vite base=/water/，API=/water/api/v1；pathname/history实现页面切换，没有React Router basename |
| Linux | water-backend.service及water.conf回环监听；部署不自动修改Hub注册、配置MDM角色 |

母本变更先盘点下游，部署使用实际Hub配置核对，不能把旧IPv6/localhost描述套用到当前水看板的127.0.0.1代理。

依据：[Hub指引](../../cmab-hub/AGENTS.md)、[nginx说明](../../cmab-hub/nginx/README.md)、[母本](../../cmab-hub/frontend/src/shared/cmabSession.ts)、[MDM指引](../../cmab-mdm-platform/AGENTS.md)。环境角色、策略和运行事实须另外核验。
