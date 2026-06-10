# High 发现收敛清单（Triage）

- 日期：2026-06-10（Stage 1 封版后）
- 来源：REVIEW_REPORT_2026-06-10_STAGE1.md / REVIEW_STATUS_2026-06-10.md
- 范围：仅 High 共 19 条；Medium/Low 不在本清单。全部 High 复核未完成（对抗复核被会话限额中断）
- 注：H-05 与 H-06 为两个审查员对同一问题的重复发现，可合并处置

## H-01：[BE-be-auth-01] 锁定期满后可无限暴力破解

- 来源章节：2. 后端代码审查发现（按域）（后端:be-auth）
- 严重程度：High
- 置信度：高
- 原报告位置：REVIEW_REPORT_2026-06-10_STAGE1.md → 2. 后端代码审查发现（按域） → [BE-be-auth-01]
- 涉及文件：`backend/app/domains/auth/services.py:180-186,122`
- 问题摘要：自动解锁只在主 session 内存中改 status/locked_at，密码错时主事务 rollback 丢失；旁路 session 重读 DB 仍是 locked，因 `u.status=='active'` 条件跳过计数与再锁定。用户永远停在 locked+窗口已过状态，每次都走完整密码校验。
- 原报告建议：自动解锁用旁路 session 立即持久化；或旁路计数时对 locked+窗口已过状态也累加并重置 locked_at。
- 当前状态：待复核
- 复核结论：未开始
- 修复状态：未开始
- 是否需要代码修复：待定
- 是否需要 migration：待定
- 是否需要测试：待定
- 人工决策备注：

## H-02：[BE-be-auth-02] auth 域全部表无审计追踪

- 来源章节：2. 后端代码审查发现（按域）（后端:be-auth）
- 严重程度：High
- 置信度：高
- 原报告位置：REVIEW_REPORT_2026-06-10_STAGE1.md → 2. 后端代码审查发现（按域） → [BE-be-auth-02]
- 涉及文件：`backend/alembic/versions/2026_05_11_1200_0001_init_schemas.py:76-165；backend/app/domains/auth/admin_service.py:201-375`
- 问题摘要：auth.user/user_role/role/role_permission/refresh_token 均未挂 audit.fn_audit_trigger，管理员建用户、改角色、锁定、重置密码等安全敏感写操作仅 loguru 日志，不落 audit_log。
- 原报告建议：为 auth 业务表挂 audit trigger 或在 admin service 写应用层审计记录。
- 当前状态：待复核
- 复核结论：未开始
- 修复状态：未开始
- 是否需要代码修复：待定
- 是否需要 migration：待定
- 是否需要测试：待定
- 人工决策备注：

## H-03：[BE-be-auth-03] 软删角色重建触发 500

- 来源章节：2. 后端代码审查发现（按域）（后端:be-auth）
- 严重程度：High
- 置信度：高
- 原报告位置：REVIEW_REPORT_2026-06-10_STAGE1.md → 2. 后端代码审查发现（按域） → [BE-be-auth-03]
- 涉及文件：`backend/app/domains/auth/admin_role_service.py:151-156,234`
- 问题摘要：delete_role 是软删（deleted_at），但 uq_role_role_code 是全表唯一；create_role 预检排除了软删行，重建同名 role_code 时预检通过、INSERT 撞唯一约束抛 IntegrityError 500。
- 原报告建议：唯一约束改 partial（WHERE deleted_at IS NULL），或预检不排除软删行。
- 当前状态：待复核
- 复核结论：未开始
- 修复状态：未开始
- 是否需要代码修复：待定
- 是否需要 migration：待定
- 是否需要测试：待定
- 人工决策备注：

## H-04：[FE-auth+admin-01] 改密旧密码错被强制登出

- 来源章节：3. 前端代码审查发现（按模块）（前端:auth+admin）
- 严重程度：High
- 置信度：高
- 原报告位置：REVIEW_REPORT_2026-06-10_STAGE1.md → 3. 前端代码审查发现（按模块） → [FE-auth+admin-01]
- 涉及文件：`frontend/src/api/client.ts:122-134 + frontend/src/modules/auth/pages/ChangePasswordPage.tsx:45-54`
- 问题摘要：后端 OldPasswordWrongError 是 HTTP 401（error_type=old_password_wrong，exceptions.py:105）。拦截器 401 分流只豁免 signature_invalid，old_password_wrong 落入兜底分支：toast「登录已过期」+ logout + 跳登录。ChangePasswordPage 的字段级报错永远展示不出来。
- 原报告建议：client.ts 401 豁免清单加入 old_password_wrong，交给调用方处理
- 当前状态：已复核（2026-06-11，与 H-06 合并判断——两者为同一问题的重复发现，以本条为主条目）
- 复核结论：**真实**
  - 证据 1：`backend/app/core/exceptions.py:104-110` OldPasswordWrongError = http_status 401 + error_type "old_password_wrong"；`backend/app/domains/auth/services.py:282` change_password 旧密码不符时 raise（注意：原报告引用路径 shared/exceptions.py 有误，实际为 core/exceptions.py，不影响结论）；
  - 证据 2：`frontend/src/api/client.ts:94-100` 静默 refresh 仅针对 errorType=token_expired，old_password_wrong 不走 refresh，直落"401 其他场景"分支；该分支（client.ts:122-134）仅豁免 signature_invalid，其余一律 toast「登录已过期」+ logout() + gotoLogin()；
  - 证据 3：`frontend/src/modules/auth/pages/ChangePasswordPage.tsx:45-54` onError 已实现 old_password_wrong 的字段级处理（setFields 给 old_password 标红"旧密码错误"），但拦截器先行登出并跳转 /login，该提示用户永远看不到；
  - 证据 4：`frontend/src/routes/ProtectedRoute.tsx` 仅做 token 判空跳转，与本问题无关（确认不涉及）。
- 是否重复：是——H-06 与本条位置、描述、建议完全一致（两个审查批次各自发现），应合并为一个修复项，修复落点唯一（client.ts 401 豁免清单）。
- 根因：401 双重语义分流约定（会话失效 vs 业务身份再验证）在拦截器实现时只登记了 signature_invalid 一个业务 401，遗漏了 old_password_wrong。
- 最小修复建议：client.ts:122-126 豁免条件由 `errorType === 'signature_invalid'` 扩为 `['signature_invalid', 'old_password_wrong'].includes(errorType)`，交由调用方处理；ChangePasswordPage 无需改动（字段级处理已就绪）。
- 修复状态：已修复（2026-06-11，与 H-06 合并修复）
- 是否需要代码修复：是（前端最小修复，已完成）
- 是否需要 migration：否
- 是否需要测试：是（手测即可；如项目已有前端测试框架，可后续补）
- 风险说明：现状用户仅输错一次旧密码即丢失整个会话，体验问题且违反项目 401 分流约定；修复仅扩白名单，old_password_wrong 只可能由改密接口返回，对其他 401 场景无影响，风险低。
- 人工决策备注：H-04/H-06 合并修复——修改 `frontend/src/api/client.ts` 401 业务型错误白名单（豁免条件扩为 signature_invalid || old_password_wrong，注释同步更新），ChangePasswordPage 的 onError 字段级处理未动。手测场景：改密输错旧密码 → 不登出、留在改密页、old_password 字段红框"旧密码错误"。

## H-05：[FE-auth+admin-02] 强制改密可被完全绕过

- 来源章节：3. 前端代码审查发现（按模块）（前端:auth+admin）
- 严重程度：High
- 置信度：高
- 原报告位置：REVIEW_REPORT_2026-06-10_STAGE1.md → 3. 前端代码审查发现（按模块） → [FE-auth+admin-02]
- 涉及文件：`backend/app/shared/permissions.py:25-88 + frontend/src/routes/ProtectedRoute.tsx:4-14`
- 问题摘要：force_password_change 仅在 LoginPage 登录成功后跳转一次（LoginPage.tsx:25-28）。改密页在 MainLayout 内，侧边栏可直接导航走；后端 get_current_user 也不校验该标记，持临时密码可正常调用全部 API。
- 原报告建议：后端依赖里拦截 force_password_change=true（仅放行改密/登出）；前端加全局守卫
- 当前状态：已复核（2026-06-11）
- 复核结论：**真实**
  - 证据 1（前端仅一次性跳转）：`LoginPage.tsx:24-29` 登录成功后若 `result.user.must_change_password` 则 navigate 到 `/profile/password?required=1`——这是全前端唯一的强制改密控制点；authStore（zustand persist）虽持久化了 user 对象（含该标记），但无任何守卫读取它；
  - 证据 2（路由无守卫）：`ProtectedRoute.tsx:4-14` 仅做 token 判空；`App.tsx:185` `/profile/password` 是 MainLayout 内普通平级路由，与 /dashboard、/substances 等同层——用户可经侧边栏导航、手动改 URL、或刷新页面直接离开改密页，无任何拦截；
  - 证据 3（后端不校验）：`backend/app/shared/permissions.py:25-88` get_current_user 校验 token 类型、用户存在、status=active、password_changed_at vs iat，**全程未读 force_password_change**；所有业务 API 的权限依赖均建立在其上，故持临时密码的 token 可调用该用户权限内全部接口（含直接 curl 绕过前端）；
  - 证据 4（标记生命周期本身正确）：`admin_service.py:354` reset-password 置 True；`auth/services.py:287` change_password 改密成功后清 False 并撤销全部 refresh token；`services.py:249` 登录响应带 must_change_password、get_me 返回 force_password_change——数据链路完整，缺的只是消费端强制；
  - 证据 5（影响面）：force_password_change=true 时可调用接口 = 该用户全部授权接口（无任何例外收窄），与 ResetPasswordResultModal.tsx:47 的 UI 承诺"首次登录时会被强制跳转到改密页"不符。
- 根因：强制改密只实现了"登录后跳转提示"这一 UX 层，未在权威层（后端依赖）和路由层（前端守卫）落地；属功能实现不完整，非回归。
- 推荐修复策略（后端为权威，前端为体验）：
  1. 后端：get_current_user 末段（status 校验之后）加拦截——`user.force_password_change` 为 true 且请求路径不在放行清单时，raise 403（建议新增 error_type=`password_change_required`，勿复用 401 以免触发前端会话失效分流）；
  2. 后端放行接口建议：`POST /api/v1/auth/change-password`（改密本身）、`POST /api/v1/auth/logout`（允许放弃会话）、`GET /api/v1/auth/me`（前端守卫/刷新需读标记）、`POST /api/v1/auth/refresh`（改密页停留超 token 期需续期）；其余一律拦截；
  3. 前端：ProtectedRoute 加全局守卫——`user.must_change_password === true` 且当前路径非 `/profile/password` 时 `<Navigate to="/profile/password?required=1" replace />`；改密成功后既有逻辑已 logout 重登，标记自然刷新，无残留态问题；
  4. 前端拦截器对新 403 error_type 可不特判（落入既有 403 toast 分支即可，守卫已保证正常流程到不了这里）。
- 是否需要代码修复：是（后端认证依赖 + 前端路由守卫，已完成）
- 是否需要 migration：否（force_password_change 字段已存在，models.py:52）
- 是否需要测试：是（已补 pytest，见备注）
- 风险说明：现状临时密码可长期当正式密码使用，违背 UI 承诺与 Part 11 密码生命周期意图（原型阶段不阻断，但属安全债）。修复时注意：放行清单遗漏 refresh 会导致改密页停留超时后死锁；error_type 若复用 401 会被拦截器登出分流吞掉（与 H-04 同坑）。
- 修复状态：已修复（2026-06-11）
- 人工决策备注：实施记录——
  1. 后端：`core/exceptions.py` 新增 PasswordChangeRequiredError（40307 / 403 / error_type=password_change_required）；`shared/permissions.py` get_current_user 在 password_changed_at 校验后拦截 force_password_change=true，放行清单 FORCE_PASSWORD_CHANGE_ALLOWED_PATHS = {/api/v1/auth/change-password, /api/v1/auth/logout, /api/v1/auth/me, /api/v1/auth/refresh}（refresh/logout 当前不走该依赖，列入防御未来变更）；
  2. 前端：`ProtectedRoute.tsx` 加守卫——must_change_password=true 且路径非 /profile/password 时强制 Navigate 到 /profile/password?required=1；client.ts 未改（403 落既有 toast 分支）；
  3. 测试：新增 `backend/tests/test_force_password_change_gate.py`（临时密码→业务 API 403 password_change_required；/auth/me 放行；改密放行；改密后业务 API 恢复），已通过；回归 test_admin_users.py + test_auth_security.py 共 17 项全过；
  4. 建议手测：临时密码登录后侧边栏导航/手动 URL/刷新均被拉回改密页；改密页停留超 token 期后 refresh 正常续期。

## H-06：[FE-dashboard+pr-01] 改密输错旧密码被强制登出

- 来源章节：3. 前端代码审查发现（按模块）（前端:dashboard+profile+common）
- 严重程度：High
- 置信度：高
- 原报告位置：REVIEW_REPORT_2026-06-10_STAGE1.md → 3. 前端代码审查发现（按模块） → [FE-dashboard+pr-01]
- 涉及文件：`frontend/src/api/client.ts:122-134, frontend/src/modules/auth/pages/ChangePasswordPage.tsx:45-54`
- 问题摘要：后端 OldPasswordWrongError 返回 401 + errorType=old_password_wrong（exceptions.py:105-109），但 axios 拦截器 401 分支只豁免 signature_invalid，old_password_wrong 落入会话失效分支：弹"登录已过期"、logout 并跳 /login。
- 原报告建议：拦截器 401 豁免清单加入 old_password_wrong，交由调用方处理。
- 当前状态：已复核（2026-06-11）
- 复核结论：**真实，但与 H-04 完全重复**（同一位置、同一根因、同一修复建议；两个审查批次各自发现）。证据、根因、最小修复建议、测试要求见 H-04 条目，不重复展开。
- 修复状态：已修复（2026-06-11，随 H-04 合并修复）
- 是否需要代码修复：是（见 H-04，修复落点唯一：client.ts 401 豁免清单，已完成）
- 是否需要 migration：否
- 是否需要测试：是（见 H-04，手测即可）
- 人工决策备注：H-04 的重复项，已随 H-04 修复（client.ts 401 业务错误白名单加入 old_password_wrong），本条同步关闭，无独立工作量。

## H-07：[FE-dashboard+pr-02] 新密码最小长度前后端不一致

- 来源章节：3. 前端代码审查发现（按模块）（前端:dashboard+profile+common）
- 严重程度：High
- 置信度：高
- 原报告位置：REVIEW_REPORT_2026-06-10_STAGE1.md → 3. 前端代码审查发现（按模块） → [FE-dashboard+pr-02]
- 涉及文件：`frontend/src/modules/auth/pages/ChangePasswordPage.tsx:111-114`
- 问题摘要：前端校验 min:8、tooltip 写"至少 8 位"；后端 ChangePasswordRequest new_password min_length=12（auth/schemas.py:70）。8-11 位密码前端放行后端 422 拒绝。
- 原报告建议：前端规则改为 min:12，tooltip 同步改为"至少 12 位"。
- 当前状态：已复核（2026-06-11，与 H-04/H-06 同属改密页前后端契约问题包）
- 复核结论：**真实**
  - 证据 1：`frontend/src/modules/auth/pages/ChangePasswordPage.tsx:114` 为 `{ min: 8, message: '新密码至少 8 位' }`，:111 tooltip 写"至少 8 位，建议包含大小写字母 + 数字 + 特殊字符"；
  - 证据 2：`backend/app/domains/auth/schemas.py:70` ChangePasswordRequest `new_password: str = Field(..., min_length=12, max_length=128)`——8-11 位密码前端放行、后端 422 拒绝；
  - 证据 3（连带确认）：后端 422 为 pydantic 校验错误，ChangePasswordPage onError（:45-54）只分流 old_password_wrong，其余落入泛化 `message.error`，用户只见笼统报错、无字段定位——与原报告"为什么是问题"描述一致；
  - 证据 4：max 一侧前后端一致（前端 :115 `{ max: 128 }` = 后端 max_length=128），不一致仅在 min。
- 根因：后端密码策略升级到 12 位（M2.5.x 安全基线）时，前端改密页校验规则与 tooltip 文案未同步。
- 最小修复建议：ChangePasswordPage.tsx 两处文本——:114 `min: 8` 改 `min: 12`、message 改"新密码至少 12 位"；:111 tooltip 改"至少 12 位，建议包含大小写字母 + 数字 + 特殊字符"。无需动后端。
- 修复状态：已修复（2026-06-11，与 H-04/H-06 同批前端改密包修复）
- 是否需要代码修复：是（前端最小修复，已完成）
- 是否需要 migration：否
- 是否需要测试：是（手测即可；如项目已有前端测试框架，可后续补）
- 风险说明：现状用户按前端提示设 8-11 位密码必然提交失败且无字段级定位；修复为收紧前端校验对齐后端，无放宽风险。注意检查管理员侧建用户/重置密码表单是否存在同样的 min 不一致（本轮未扫描，超出范围，留给后续 Medium/Low 复核或修复时顺带确认）。
- 人工决策备注：修改 `ChangePasswordPage.tsx`——min: 8→12、校验 message"新密码至少 8 位"→"新密码至少 12 位"、tooltip"至少 8 位…"→"至少 12 位…"；确认"确认新密码"字段无独立 min 规则（仅一致性校验），无需同步。后端 schemas.py 未动。手测场景：新密码输 8-11 位 → 前端直接拦截提示"新密码至少 12 位"，不发请求。

## H-08：[BE-be-srs-01] internal_code 软删后无法复用且 500

- 来源章节：2. 后端代码审查发现（按域）（后端:be-srs）
- 严重程度：High
- 置信度：高
- 原报告位置：REVIEW_REPORT_2026-06-10_STAGE1.md → 2. 后端代码审查发现（按域） → [BE-be-srs-01]
- 涉及文件：`backend/app/domains/srs/services.py:329-339 + alembic/versions/2026_05_12_1000_0028_srs_baseline_align.py:94-99`
- 问题摘要：0028 想用 partial 索引让 internal_code 仅在未删行唯一，但新建索引未加 unique=True（仅普通索引），且 0001 的全量 UniqueConstraint uq_substance_internal_code 从未 drop。create/update 的 pre-check 只查 deleted_at IS NULL 会放行，DB 全量唯一约束却拒绝，复用已软删 internal_code 直接 IntegrityError 500。
- 原报告建议：0028 索引补 unique=True 并 drop 全量 uq_substance_internal_code。
- 当前状态：待复核
- 复核结论：未开始
- 修复状态：未开始
- 是否需要代码修复：待定
- 是否需要 migration：待定
- 是否需要测试：待定
- 人工决策备注：

## H-09：[BE-be-ref-01] 主数据软删后引用无法解除

- 来源章节：2. 后端代码审查发现（按域）（后端:be-ref）
- 严重程度：High
- 置信度：高
- 原报告位置：REVIEW_REPORT_2026-06-10_STAGE1.md → 2. 后端代码审查发现（按域） → [BE-be-ref-01]
- 涉及文件：`backend/app/domains/ref/services.py:64-73,136-169（三个 service 的 _get_* 与 unlink 同模式）`
- 问题摘要：srs/prs/ars 的 soft_delete 不预检 ref 活动链接；物质/项目/资产软删后链接仍 deleted_at IS NULL。而 unlink 内 _get_substance/_get_project/_get_asset 均过滤 deleted_at，对已删实体直接 404，链接永远无法通过 API 取消。
- 原报告建议：主实体软删前预检活动链接并阻止或级联软删；或 unlink 的 _get_* 放宽 deleted_at 过滤
- 当前状态：待复核
- 复核结论：未开始
- 修复状态：未开始
- 是否需要代码修复：待定
- 是否需要 migration：待定
- 是否需要测试：待定
- 人工决策备注：

## H-10：[BE-be-ars-01] market_id 软删后重建撞唯一约束

- 来源章节：2. 后端代码审查发现（按域）（后端:be-ars）
- 严重程度：High
- 置信度：高
- 原报告位置：REVIEW_REPORT_2026-06-10_STAGE1.md → 2. 后端代码审查发现（按域） → [BE-be-ars-01]
- 涉及文件：`backend/app/domains/ars/services.py:329-364; backend/alembic/versions/2026_05_12_0040_0023_ars_market_id.py:40-43`
- 问题摘要：add_market_id 预检只过滤 deleted_at IS NULL，但 DB 的 uq_asset_market_id 是含软删行的全量约束。软删某注册号后再添加相同 (market_code,id_type,id_value) 预检通过、INSERT 触发 IntegrityError 500。
- 原报告建议：改为 partial unique index（WHERE deleted_at IS NULL），或参照 AssetSubstanceLinkService 复活软删行。
- 当前状态：待复核
- 复核结论：未开始
- 修复状态：未开始
- 是否需要代码修复：待定
- 是否需要 migration：待定
- 是否需要测试：待定
- 人工决策备注：

## H-11：[BE-be-ars-02] 幂等缓存先于事务提交写入

- 来源章节：2. 后端代码审查发现（按域）（后端:be-ars）
- 严重程度：High
- 置信度：高
- 原报告位置：REVIEW_REPORT_2026-06-10_STAGE1.md → 2. 后端代码审查发现（按域） → [BE-be-ars-02]
- 涉及文件：`backend/app/api/v1/assets.py:101-105; backend/app/core/database.py:64-73`
- 问题摘要：create_asset 在 IdempotencyService.save 写 Redis 后才由 get_db 在响应后 commit。若 commit 失败（约束/连接），Redis 已缓存 201 成功体，客户端持同一 Idempotency-Key 重试将永远命中缓存假成功，DB 无该资产。
- 原报告建议：按项目强一致约定在 service 内显式 commit 成功后再写幂等缓存。
- 当前状态：待复核
- 复核结论：未开始
- 修复状态：未开始
- 是否需要代码修复：待定
- 是否需要 migration：待定
- 是否需要测试：待定
- 人工决策备注：

## H-12：[BE-be-ars-03] 状态机并发竞态可复活已终止资产

- 来源章节：2. 后端代码审查发现（按域）（后端:be-ars）
- 严重程度：High
- 置信度：中
- 原报告位置：REVIEW_REPORT_2026-06-10_STAGE1.md → 2. 后端代码审查发现（按域） → [BE-be-ars-03]
- 涉及文件：`backend/app/domains/ars/services.py:234-275`
- 问题摘要：change_status 先 SELECT（无 FOR UPDATE）在 Python 校验转移合法性，再无条件 UPDATE status。并发下 T1 terminate 提交后，T2 基于陈旧 active 读的 hold 仍会执行，把 terminated 改回 on_hold。
- 原报告建议：查询加 with_for_update()，或 UPDATE ... WHERE status=:old 校验影响行数。
- 当前状态：待复核
- 复核结论：未开始
- 修复状态：未开始
- 是否需要代码修复：待定
- 是否需要 migration：待定
- 是否需要测试：待定
- 人工决策备注：

## H-13：[BE-be-mm-01] 软删批次后复用批号触发500

- 来源章节：2. 后端代码审查发现（按域）（后端:be-mm）
- 严重程度：High
- 置信度：高
- 原报告位置：REVIEW_REPORT_2026-06-10_STAGE1.md → 2. 后端代码审查发现（按域） → [BE-be-mm-01]
- 涉及文件：`backend/app/domains/mm/services.py:380-391, 440-454; backend/alembic/versions/2026_05_13_0500_0033_mm_material_batch.py:72`
- 问题摘要：uq_material_batch 是全表唯一约束（含软删行），但 add_batch/update_batch 的重复预检均过滤 deleted_at IS NULL。软删某批次后再以同批号新建/改名，预检通过、flush 时撞 DB 唯一约束抛 IntegrityError。
- 原报告建议：将 uq_material_batch 改为 partial unique index（WHERE deleted_at IS NULL），或预检改为全表口径并提示编码占用。
- 当前状态：待复核
- 复核结论：未开始
- 修复状态：未开始
- 是否需要代码修复：待定
- 是否需要 migration：待定
- 是否需要测试：待定
- 人工决策备注：

## H-14：[TEST-be-tests-01] 硬编码 8000 绕过隔离 test DB

- 来源章节：5. 测试覆盖缺口（后端:be-tests）
- 严重程度：High
- 置信度：高
- 原报告位置：REVIEW_REPORT_2026-06-10_STAGE1.md → 5. 测试覆盖缺口 → [TEST-be-tests-01]
- 涉及文件：`backend/tests/test_smoke.py:8 / test_rate_limit.py:14 / test_refresh_token.py:13`
- 问题摘要：这三个文件模块级 BASE_URL='http://localhost:8000'，用自建 AsyncClient 直打 dev 服务；run_tests.sh 把测试服务起在 8001 并经 TEST_BASE_URL 隔离 cmab_test，这些用例完全绕过隔离，读写/污染 dev 库或在 dev 未起时失败。
- 原报告建议：改用 conftest 的 BASE_URL/http_client fixture，统一读 TEST_BASE_URL
- 当前状态：待复核
- 复核结论：未开始
- 修复状态：未开始
- 是否需要代码修复：待定
- 是否需要 migration：待定
- 是否需要测试：待定
- 人工决策备注：

## H-15：[MATCH-数据模型↔ORM+迁移-01] milestone_type 空约束 ORM↔DB 冲突

- 来源章节：4. 文档与代码匹配性审查发现（匹配性:数据模型↔ORM+迁移）
- 严重程度：High
- 置信度：高
- 原报告位置：REVIEW_REPORT_2026-06-10_STAGE1.md → 4. 文档与代码匹配性审查发现 → [MATCH-数据模型↔ORM+迁移-01]
- 涉及文件：`backend/app/domains/prs/models.py:144 ; backend/alembic/versions/2026_05_11_1700_0006_prs_init.py:117 ; 2026_05_11_2310_0014_prs_milestone_v2.py`
- 问题摘要：迁移 0006 建 milestone_type 为 NOT NULL，0014 未改其可空性；但 ORM(models.py:144) 与 Pydantic(schemas.py:187 `milestone_type: MilestoneType|None=None`) 均可空，service:395 直接透传 None。创建里程碑省略 type 时 DB 抛 NOT NULL 违例。
- 原报告建议：迁移将该列改可空，或 schema 设为必填
- 当前状态：待复核
- 复核结论：未开始
- 修复状态：未开始
- 是否需要代码修复：待定
- 是否需要 migration：待定
- 是否需要测试：待定
- 人工决策备注：

## H-16：[DOC-架构设计+数据模型(内部-01] EQP 范围自相矛盾

- 来源章节：1. 文档审查发现（文档:架构设计+数据模型(内部质量)）
- 严重程度：High
- 置信度：高
- 原报告位置：REVIEW_REPORT_2026-06-10_STAGE1.md → 1. 文档审查发现 → [DOC-架构设计+数据模型(内部-01]
- 涉及文件：`docs/CMAB_MDM_Portal_架构设计文档_V1_1.md:120 与 41/73`
- 问题摘要：§1.3.2 范围外明确写'设备主数据（未来纳入 CMMS 或独立 Equipment Master）'，但适用范围(§41)、§1.2.1/§1.2.2 已将 Equipment(EQP) 列为 V1.2 新增的第五业务域。
- 原报告建议：§1.3.2 删除或改写设备主数据条目，§1.3.1 In-Scope 表补 EQP 行。
- 当前状态：待复核
- 复核结论：未开始
- 修复状态：未开始
- 是否需要代码修复：待定
- 是否需要 migration：待定
- 是否需要测试：待定
- 人工决策备注：

## H-17：[DOC-README+QUICK-01] 引用不存在的 requirements.txt

- 来源章节：1. 文档审查发现（文档:README+QUICKSTART+Makefile）
- 严重程度：High
- 置信度：中
- 原报告位置：REVIEW_REPORT_2026-06-10_STAGE1.md → 1. 文档审查发现 → [DOC-README+QUICK-01]
- 涉及文件：`README.md:248,269`
- 问题摘要：开发流程图与生产部署步骤均写 `pip install -r backend/requirements.txt`，但仓库内无该文件，依赖实为 pyproject.toml（uv/pip install -e）。
- 原报告建议：改为 `uv pip install -e backend` 或补生成 requirements.txt 的步骤。
- 当前状态：已复核（2026-06-11，人工指定单项只读复核）
- 复核结论：**真实**
  - 证据 1：README.md:248（开发→生产流程图）与 README.md:269（生产部署步骤）均为 `backend/.venv/bin/pip install -r backend/requirements.txt`；
  - 证据 2：`ls backend/requirements.txt` → No such file or directory；仓库根 `requirements.txt`、根 `pyproject.toml` 亦不存在；
  - 证据 3：`backend/pyproject.toml` 存在且含完整 `[project].dependencies`（fastapi/sqlalchemy/alembic/redis 等），后端依赖实际以 pyproject.toml 为唯一权威来源；
  - 证据 4：QUICKSTART.md 与 Makefile 中无任何 requirements.txt 引用，问题仅限 README 两处。
  - 根因：依赖管理已迁移到 pyproject.toml，README 的生产部署段未同步更新。
- 修复状态：已修复（2026-06-11；README.md:248 改为 `backend/.venv/bin/pip install -e backend`，README.md:269 改为 `backend/.venv/bin/pip install -q -e backend`，未新增 requirements.txt、未引入 pip/uv compile 流程）
- 是否需要代码修复：否
- 是否需要 migration：否
- 是否需要测试：否
- 人工决策备注：README 两处命令已替换；建议后续生产部署前人工验证一次该命令（并顺手核查生产机是否残留手工生成、未入库的 requirements.txt）。

## H-18：[DOC-RUNBOOK+OQ追溯-01] alembic 校验跑错容器

- 来源章节：1. 文档审查发现（文档:RUNBOOK+OQ追溯）
- 严重程度：High
- 置信度：高
- 原报告位置：REVIEW_REPORT_2026-06-10_STAGE1.md → 1. 文档审查发现 → [DOC-RUNBOOK+OQ追溯-01]
- 涉及文件：`docs/RUNBOOK_BACKUP_RESTORE.md:101 与 scripts/restore_db.sh:75`
- 问题摘要：恢复校验命令为 `docker exec cmab-mdm-postgres alembic current`，但 postgres:16-alpine 容器内没有 alembic；restore_db.sh 完成提示同样写错容器。
- 原报告建议：改为在 backend 容器或一次性 docker run（backend 镜像）中执行 alembic current。
- 当前状态：已复核（2026-06-11）
- 复核结论：**真实**
  - 证据 1：`docs/RUNBOOK_BACKUP_RESTORE.md:101` 为 `docker exec cmab-mdm-postgres alembic current`；`scripts/restore_db.sh:75` 完成提示为 `docker exec ${PG_CONTAINER} alembic current`，而 `PG_CONTAINER` 默认值为 `cmab-mdm-postgres`（restore_db.sh:23）；
  - 证据 2：`deploy/docker-compose.prod.yml:18-19` 确认 `cmab-mdm-postgres` 使用官方 `postgres:16-alpine` 镜像，内无 Python/alembic，该命令必然报 executable not found；
  - 证据 3：`backend/Dockerfile` production stage 安装了 pyproject 依赖（含 alembic）并 COPY `alembic/` + `alembic.ini`（行 49/70-76），`deploy/docker-compose.prod.yml:70` 确认 backend 容器名为 `cmab-mdm-backend` —— alembic current 的正确执行位置是 backend 容器（或 backend 镜像一次性容器）；
  - 证据 4（叠加缺陷）：RUNBOOK 4.1 step 1 已 `stop backend`，step 3 才校验，此时 `docker exec cmab-mdm-backend ...` 对已停止容器同样失败；故单纯换容器名仍不可执行，需用一次性容器或调整步骤顺序。
- 根因：编写 RUNBOOK/脚本时把"数据库版本校验"误归类为数据库容器操作；且未考虑校验时点 backend 已被 step 1 停止。
- 最小修复建议（仅改文档与 echo 提示，2 处）：
  1. `docs/RUNBOOK_BACKUP_RESTORE.md:101` 改为 `docker compose -f deploy/docker-compose.prod.yml run --rm backend alembic current`（一次性容器，不依赖 backend 运行中；DATABASE_URL 由 compose env 注入）；
  2. `scripts/restore_db.sh:75` 的 echo 同步改为上述命令（或提示"在 backend 容器/镜像中执行"），不再引用 `${PG_CONTAINER}`；
  3. 顺带核对 RUNBOOK §5 恢复演练表第 3 行措辞（`alembic current`）补充执行位置说明。
- 修复状态：已修复（2026-06-11，与 H-19 同一次合并修复）
- 是否需要代码修复：否（仅文档与脚本提示文本）
- 是否需要 migration：否
- 是否需要测试：否
- 风险说明：当前 SOP 在灾难恢复演练时该校验步骤必然失败；若执行人误以为"校验工具缺失=跳过校验"，可能在未确认 schema 版本一致的情况下恢复业务流量。修复本身零运行时风险（纯文档/提示文本）。
- 人工决策备注：本次修改 docs/RUNBOOK_BACKUP_RESTORE.md:101（改为 `docker compose -f deploy/docker-compose.prod.yml run --rm backend alembic current`，附"backend 已 stop 不能 docker exec"说明）、§5 演练表第 3 行（补充一次性容器执行方式）、scripts/restore_db.sh 完成提示第 1 条（同步改为一次性 backend 容器命令）。建议下次恢复演练时人工验证命令可执行。

## H-19：[DOC-RUNBOOK+OQ追溯-02] 生产恢复 pytest 校验不可行

- 来源章节：1. 文档审查发现（文档:RUNBOOK+OQ追溯）
- 严重程度：High
- 置信度：高
- 原报告位置：REVIEW_REPORT_2026-06-10_STAGE1.md → 1. 文档审查发现 → [DOC-RUNBOOK+OQ追溯-02]
- 涉及文件：`docs/RUNBOOK_BACKUP_RESTORE.md:94,102`
- 问题摘要：step 1 已 stop backend，step 3 却 `docker exec cmab-mdm-backend pytest tests/ -q`；且生产镜像（Dockerfile production stage）只 COPY app/alembic，无 tests/，pytest 属 dev optional-dependencies 未安装。
- 原报告建议：删除生产环境 pytest 步骤，改为只读 SQL 抽检；回归测试仅在 UAT 用 make test-be（隔离 test DB）。
- 当前状态：已复核（2026-06-11）
- 复核结论：**真实**（且校验语义本身错误，问题比原报告描述更深）
  - 证据 1：`docs/RUNBOOK_BACKUP_RESTORE.md:102` 为 `docker exec cmab-mdm-backend pytest tests/ -q`，而同段 step 1（RUNBOOK:94）已 `stop backend`——对已停止容器 docker exec 必然失败（与 H-18 同型缺陷）；
  - 证据 2：`backend/Dockerfile` production stage 仅 COPY `app/`、`alembic/`、`alembic.ini`（行 74-76），无 `tests/`；builder 阶段 `uv pip install --system .`（行 49）不带 `[dev]`，而 pytest 全家在 `backend/pyproject.toml:48-53` 的 `[project.optional-dependencies] dev` 组——生产镜像既无 tests 目录也无 pytest 可执行文件，命令双重不可行；
  - 证据 3：`scripts/restore_db.sh:76` 的完成提示为 `make test-be`，但 Makefile:3 硬编码 `COMPOSE := docker compose -f deploy/docker-compose.dev.yml`，在生产机上同样不可执行；
  - 证据 4（语义错误）：`make test-be` 走 `scripts/run_tests.sh`，跑在隔离的 cmab_test 库（8001 测试服务 + redis db15），**根本不读取刚恢复的 cmab_mdm 数据**——即使能跑通，它校验的是代码回归而非恢复数据完整性，作为"恢复校验步骤"语义不成立；反之若直接对恢复库跑 pytest，会向生产数据写入大量测试垃圾（历史上曾累积 18k+ 行），属破坏性操作；
  - 证据 5：同样问题还出现在 §5 恢复演练表第 4 行（RUNBOOK:133 `pytest tests/ -q` 全量通过）。
- 根因：编写 RUNBOOK 时把"代码回归测试"与"数据恢复完整性校验"两类目标混在同一步骤，且未对照生产镜像内容物（production stage 裁剪了 tests 与 dev 依赖）。
- 最小修复建议（仅改文档与 echo，3 处）：
  1. 删除 RUNBOOK:102 的 pytest 行，恢复校验只保留 alembic current（按 H-18 修法）+ 既有只读 SQL 计数抽检（RUNBOOK:103-111 已有）+ 业务侧抽检；
  2. RUNBOOK:133（演练表第 4 行）改为"UAT 环境另行 `make test-be`（隔离 test DB，验证代码回归，与恢复数据无关）"或直接删除；
  3. `scripts/restore_db.sh:76` 的 echo 删去 `make test-be`，改为提示"业务侧只读 SQL 抽检 + 关键记录比对"。
- 修复状态：已修复（2026-06-11，与 H-18 同一次合并修复）
- 是否需要代码修复：否（仅文档与脚本提示文本）
- 是否需要 migration：否
- 是否需要测试：否
- 风险说明：现状双重风险——（a）SOP 在生产灾备时该步骤必然失败，执行人可能跳过校验直接恢复流量；（b）若执行人"变通"在恢复库上直跑 pytest，会向刚恢复的生产数据注入测试垃圾，造成二次数据事故。修复本身零运行时风险（纯文档/提示文本）。
- 人工决策备注：本次修改 docs/RUNBOOK_BACKUP_RESTORE.md:102（删除 pytest 校验行，替换为"禁止对恢复库跑 pytest + 代码回归仅在 UAT/test DB 另行 make test-be"注释；保留 alembic current 修正版与既有只读 SQL 计数抽检、业务侧抽检）、§5 演练表第 4 行（改为 UAT/隔离 test DB 另行 make test-be，不对恢复库直接跑 pytest）、scripts/restore_db.sh 完成提示（删去 make test-be，改为只读 SQL 抽检 + 关键记录逐字段比对，附禁止事项说明）。

