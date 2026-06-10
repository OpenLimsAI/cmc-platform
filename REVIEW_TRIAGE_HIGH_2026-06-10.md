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
- 当前状态：已复核（2026-06-11，与 H-10/H-13 同属"软删唯一约束"同类缺陷包）
- 复核结论：**真实**
  - 证据 1：0001 migration:214 全量 `UniqueConstraint("internal_code", name="uq_substance_internal_code")`，后续从未 drop；srs/models.py:34 同样声明全量约束；
  - 证据 2：0028 migration:94-99 建的 `ix_substance_internal_code`（WHERE deleted_at IS NULL）**未加 unique=True**，只是普通 partial 索引，对唯一性无任何作用；docstring S4 引 §7.2.2 表明设计意图是"未删行内唯一"；
  - 证据 3：create 预检（services.py:330-339）与 update 预检（services.py:438-448）均过滤 `deleted_at IS NULL`——软删行占用的 internal_code 预检放行，flush 撞 0001 全量约束抛 IntegrityError；项目约定 service 禁 catch IntegrityError（避免 async session 报废），异常直接冒泡 → 500。
- 根因：0028 实施时漏了两步——partial 索引没加 unique、旧全量约束没 drop；预检口径（active-only）按设计基准写，DB 实际约束停留在 0001 口径，三处不一致。
- 策略建议：**优先策略 B**（软删后允许复用）。依据：0028 S4 注释引设计基准 §7.2.2 partial 口径 + 预检已按 active-only 实现，B 是补完原设计而非改设计。新增 migration：drop uq_substance_internal_code → 重建 ix 为 partial UNIQUE（或新增 uq partial）→ models.py __table_args__ 同步去掉全量 UniqueConstraint。策略 A（预检改全表口径返回 409、编码终身占用）仅在负责人决定 internal_code 走"编码终身制"时选用，无需 migration 但与既有设计基准相悖。
- 修复状态：已修复（2026-06-11，策略 B，负责人拍板；与 H-10 同一 migration）
- 是否需要代码修复：是（已完成）
- 是否需要 migration：是（已新增 `2026_06_11_0100_0045_softdelete_partial_unique.py`：drop uq_substance_internal_code + drop 0028 普通 partial 索引 ix_substance_internal_code + 建 partial UNIQUE `uq_substance_internal_code_active`（WHERE deleted_at IS NULL；internal_code 可 NULL，PG 默认 NULLS DISTINCT 多行 NULL 不冲突））
- 是否需要测试：是（已补 test_substance_crud.py::test_internal_code_reusable_after_soft_delete——软删后复用 201；既有 test_duplicate_internal_code_rejected 覆盖未删行间 409/40902；全量 281 项全绿）
- 人工决策备注：srs/models.py 全量 UniqueConstraint 替换为 partial unique Index 声明；dev/生产库需 `alembic upgrade head` 后生效（本次未动运行态 DB，test DB 由 run_tests.sh bootstrap 验证 migration 可执行）。

## H-09：[BE-be-ref-01] 主数据软删后引用无法解除

- 来源章节：2. 后端代码审查发现（按域）（后端:be-ref）
- 严重程度：High
- 置信度：高
- 原报告位置：REVIEW_REPORT_2026-06-10_STAGE1.md → 2. 后端代码审查发现（按域） → [BE-be-ref-01]
- 涉及文件：`backend/app/domains/ref/services.py:64-73,136-169（三个 service 的 _get_* 与 unlink 同模式）`
- 问题摘要：srs/prs/ars 的 soft_delete 不预检 ref 活动链接；物质/项目/资产软删后链接仍 deleted_at IS NULL。而 unlink 内 _get_substance/_get_project/_get_asset 均过滤 deleted_at，对已删实体直接 404，链接永远无法通过 API 取消。
- 原报告建议：主实体软删前预检活动链接并阻止或级联软删；或 unlink 的 _get_* 放宽 deleted_at 过滤
- 当前状态：已复核（2026-06-11）
- 复核结论：**真实**
  - 证据 1（三 service 同模式）：ref/services.py 的 ProjectSubstanceLinkService（_get_project/_get_substance :53-73）、AssetSubstanceLinkService（_get_asset/_get_substance :238-257）、ProjectAssetLinkService（_get_project/_get_asset :422-441）全部按 `deleted_at IS NULL` 解析实体，未命中即 404（XxxNotFoundError）；
  - 证据 2（unlink 必经 _get_*）：三个 unlink（:136-169 / :319+ / :505+）第一步均先解析两端实体再查 link——任一端已软删即 404，永远走不到 link 软删逻辑；
  - 证据 3（无替代入口）：unlink 路由全部按 code 三元组寻址（如 projects.py:436-452 `DELETE /{code}/substances/{substance_code}/{relation_type}`），不存在按 link_id 解除的端点——"无法定位"与"无法解除"在当前 API 形态下等价；
  - 证据 4（无级联）：ref 三 service 内无任何来自主域软删的级联/预检逻辑；主实体软删后其活动 link 保持 deleted_at IS NULL，成为不可清理的孤儿活动引用（与原报告"srs/prs/ars soft_delete 不预检"的描述自洽——若有预检或级联，该孤儿态不可能形成）；
  - 证据 5（测试空白）：三个 link 测试文件均无"软删主实体后 unlink"用例。
- 问题定性：本质是"无法通过任何常规接口解除"——link 行本身健在且可软删，卡点仅在 unlink 入口的实体解析；不是数据损坏。
- 根因：_get_* 作为通用实体解析复用了 active-only 口径，未区分"业务引用创建"（应限活动实体）与"引用清理"（软删实体的链接恰恰是最需要清理的对象）两类语义。
- 推荐修复策略（最小）：**仅放宽 unlink 路径的实体解析**——三个 service 的 _get_* 增加 `include_deleted: bool = False` 形参（unlink 调用处传 True，link/list 维持现状），不新增 link_id 端点、不恢复软删主实体、不动 srs/prs/ars 的 soft_delete。中期治理（另立条目、非本条范围）：主实体 soft_delete 时级联软删其活动链接（需统一 change_reason/审计语义，触及三个域），即便做了级联，放宽后的 unlink 仍是历史孤儿链接的兜底清理通道。list/query 默认隐藏软删实体关联属 BE-be-ref-02（Medium，双向列表过滤不对称）范围，不并入本条。
- 修复状态：已修复（2026-06-11）
- 是否需要代码修复：是（ref/services.py 最小修复，已完成：六个 _get_* 增加 `include_deleted: bool = False` 形参；三个 unlink 调用处传 True——grep 确认 include_deleted=True 全文件仅 6 处、全部位于 unlink 方法内，link/list 路径零改动）
- 是否需要 migration：否（无 schema/约束变更）
- 是否需要测试：是（已补三组用例：test_project_substance_link.py::test_unlink_after_substance_soft_deleted（软删 substance 端）、test_asset_substance_link.py::test_unlink_after_asset_soft_deleted（软删 asset 端）、test_project_asset_link.py::test_unlink_after_project_soft_deleted（软删 project 端）——建链→软删一端→unlink 204→active 列表消失；REF 定向 28 项 + 全量 286 项全绿）
- 风险说明：修复仅放宽 unlink 单一路径的实体解析，link 创建仍限活动实体，无引用完整性放松风险；两端均软删的链接同样可清理（两个 _get_* 均放宽）。
- 人工决策备注：include_deleted 仅用于 unlink 清理路径（设计注释已写入 _get_*），创建/list 默认口径不变；主实体软删级联软删链接的中期治理与 BE-be-ref-02 列表过滤问题均未触碰，留待各自条目处理。

## H-10：[BE-be-ars-01] market_id 软删后重建撞唯一约束

- 来源章节：2. 后端代码审查发现（按域）（后端:be-ars）
- 严重程度：High
- 置信度：高
- 原报告位置：REVIEW_REPORT_2026-06-10_STAGE1.md → 2. 后端代码审查发现（按域） → [BE-be-ars-01]
- 涉及文件：`backend/app/domains/ars/services.py:329-364; backend/alembic/versions/2026_05_12_0040_0023_ars_market_id.py:40-43`
- 问题摘要：add_market_id 预检只过滤 deleted_at IS NULL，但 DB 的 uq_asset_market_id 是含软删行的全量约束。软删某注册号后再添加相同 (market_code,id_type,id_value) 预检通过、INSERT 触发 IntegrityError 500。
- 原报告建议：改为 partial unique index（WHERE deleted_at IS NULL），或参照 AssetSubstanceLinkService 复活软删行。
- 当前状态：已复核（2026-06-11，与 H-08/H-13 同属"软删唯一约束"同类缺陷包）
- 复核结论：**真实**
  - 证据 1：0023 migration:40-43 与 ars/models.py:100-106 均为全量 `UniqueConstraint(asset_id, market_code, id_type, id_value, name="uq_asset_market_id")`，无 WHERE 子句、无 partial 索引补丁；
  - 证据 2：add_market_id 预检（services.py:333-346）过滤 `deleted_at IS NULL`——软删的注册号记录占用四元组，预检放行后 INSERT 撞全量约束 → IntegrityError 冒泡 500（项目约定 service 不 catch）；
  - 证据 3：与 H-08 不同，本表连"未完成的 partial 索引"都没有，DB 层从未向 active-only 口径迈步，预检与约束自创建之日即不一致。
- 根因：0023 建表时唯一约束未考虑软删行；预检按项目通行的 active-only 口径写，两层口径错位。
- 策略建议：**优先策略 B**（partial unique index）。依据：注册号软删重录是常见业务操作（错删恢复、注册状态变更重建），且 SRS/MM 同口径统一治理一致性最好。新增 migration：drop uq_asset_market_id → 建 partial UNIQUE INDEX（WHERE deleted_at IS NULL）→ models.py 同步。策略 A（全表预检 + 409 占用提示）无 migration 但会让错删的注册号永久不可重录，需配套"复活软删行"接口（原报告备选，改动更大），不推荐。
- 修复状态：已修复（2026-06-11，策略 B，负责人拍板；与 H-08 同一 migration）
- 是否需要代码修复：是（已完成）
- 是否需要 migration：是（已新增 `2026_06_11_0100_0045_softdelete_partial_unique.py`：drop uq_asset_market_id + 建 partial UNIQUE `uq_asset_market_id_active`(asset_id, market_code, id_type, id_value) WHERE deleted_at IS NULL）
- 是否需要测试：是（已补 test_asset_state_machine.py::test_market_id_reusable_after_soft_delete——软删后重建同四元组 201；既有 test_market_id_duplicate_rejected 覆盖未删行间 409；全量 281 项全绿）
- 人工决策备注：ars/models.py 全量 UniqueConstraint 替换为 partial unique Index 声明；dev/生产库需 `alembic upgrade head` 后生效。

## H-11：[BE-be-ars-02] 幂等缓存先于事务提交写入

- 来源章节：2. 后端代码审查发现（按域）（后端:be-ars）
- 严重程度：High
- 置信度：高
- 原报告位置：REVIEW_REPORT_2026-06-10_STAGE1.md → 2. 后端代码审查发现（按域） → [BE-be-ars-02]
- 涉及文件：`backend/app/api/v1/assets.py:101-105; backend/app/core/database.py:64-73`
- 问题摘要：create_asset 在 IdempotencyService.save 写 Redis 后才由 get_db 在响应后 commit。若 commit 失败（约束/连接），Redis 已缓存 201 成功体，客户端持同一 Idempotency-Key 重试将永远命中缓存假成功，DB 无该资产。
- 原报告建议：按项目强一致约定在 service 内显式 commit 成功后再写幂等缓存。
- 当前状态：已复核（2026-06-11）
- 复核结论：**真实（且波及面比原报告大：五个域的 create 同模式）**
  - 证据 1（commit 时机）：core/database.py:64-73 get_db 的 commit 在 `yield session` 之后——即路由函数 return、响应序列化后才执行（项目已知坑：FastAPI yield 依赖 commit 时机）；
  - 证据 2（service 不显式 commit）：AssetService.create 仅 `flush()`（ars/services.py，create 方法内无 commit；全文件唯一 commit 在 change_status:296）——flush 只把 INSERT 发到 DB 拿回 asset_code，事务并未提交；
  - 证据 3（缓存先行）：assets.py create 路由在 return 前执行 `IdempotencyService.save(...)` 写 Redis（status_code=201 + 完整响应体 + Location）——此时事务未提交；若 get_db 的 commit 失败（约束延迟校验/连接断开/审计触发器异常），Redis 已留下成功记录；
  - 证据 4（影响窗口）：idempotency.py:31-32 IDEM_TTL_SECONDS=24h——同 Idempotency-Key 重试在 24 小时窗口内全部命中缓存假 201（原报告"永远"应修正为"24h 窗口内"，但幂等重试恰恰集中在该窗口，实际危害等同），且 Location 指向不存在的资源；
  - 证据 5（波及面）：grep 确认同模式存在于全部五个 create 路由——assets.py、substances.py:86/104、projects.py:93+、materials.py:74/92、equipments.py:63/80；五个域 service 的 create 均 flush-only（srs/prs 的 commit 在状态机等其他方法，mm 无任何显式 commit）。
- 根因：幂等缓存写入被放在"业务成功"（service 返回）时点，而项目的事务边界在 yield 依赖里晚于该时点；二者之间存在 commit 失败窗口。与既有约定"强一致场景 service 内显式 commit"未对齐。
- 推荐修复策略（最小）：五个 create 路由在 `IdempotencyService.save(...)` 之前显式 `await db.commit()`（get_db 收尾的 commit 对已提交会话是无害 no-op；与 ref 域 link/unlink 的显式 commit 先例一致）。备选（更厚重，不推荐本轮做）：把 commit 下沉进各 service.create。仅修 assets 不修其余四个会留同型残缺，应五处同批。
- 修复状态：已修复（2026-06-11）
- 是否需要代码修复：是（五个 create 路由显式 commit 后再 save 幂等缓存，已完成）
- 是否需要 migration：否
- 是否需要测试：是（已运行：test_idempotency.py 6 项全过——material/substance 同 Key 重放命中缓存、异 body 409、无 Key 正常路径、非法 Key 400、跨用户隔离；全量 286 项全绿，覆盖五域 create 正常 201 回归。commit 失败注入未做，按决策以顺序评审替代）
- 风险说明：现状为低概率高危害（commit 失败罕见，但一旦发生客户端将拿到指向不存在资源的 201 并在 24h 内无法重试成功）；修复后 commit 提前至响应前，与 ref 域显式 commit 先例一致。
- 人工决策备注：五个 create 路由（assets/substances/projects/materials/equipments）统一插入 `await db.commit()`——顺序为 service.create → 构造 Location/body（model_dump 完成）→ **commit** → IdempotencyService.save → return；"先 dump 再 commit"保证 ORM expire 不影响响应体；get_db 收尾 commit 对已提交会话为 no-op，未改 get_db/IdempotencyService/service 层。update/delete/状态机路由未动（H-12 另行处理）。

## H-12：[BE-be-ars-03] 状态机并发竞态可复活已终止资产

- 来源章节：2. 后端代码审查发现（按域）（后端:be-ars）
- 严重程度：High
- 置信度：中
- 原报告位置：REVIEW_REPORT_2026-06-10_STAGE1.md → 2. 后端代码审查发现（按域） → [BE-be-ars-03]
- 涉及文件：`backend/app/domains/ars/services.py:234-275`
- 问题摘要：change_status 先 SELECT（无 FOR UPDATE）在 Python 校验转移合法性，再无条件 UPDATE status。并发下 T1 terminate 提交后，T2 基于陈旧 active 读的 hold 仍会执行，把 terminated 改回 on_hold。
- 原报告建议：查询加 with_for_update()，或 UPDATE ... WHERE status=:old 校验影响行数。
- 当前状态：已复核（2026-06-11）
- 复核结论：**真实**（置信度可由原报告的"中"上调为"高"——竞态路径完整确认）
  - 证据 1（无锁读）：change_status（ars/services.py:218-300）经 `_get_asset_or_404`（:119-126）取实体——普通 SELECT，无 with_for_update（grep 确认 ars/srs/prs 三域 services 全文无 with_for_update）；
  - 证据 2（Python 侧校验 + 无条件写）：转移合法性在 Python 内存中基于读到的 old_status 判定（:236-242），随后 `asset.status = next_status` 经 ORM flush 生成 `UPDATE ... WHERE asset_id = :pk`——WHERE 不含 status 旧值，也不带 version 乐观锁（change_status 不接收 version 参数，乐观锁仅存在于 update() 方法）；
  - 证据 3（竞态时序）：READ COMMITTED 下 T1 terminate（active→terminated）commit:296 后，T2 hold 此前已读到 active 并通过校验，其 UPDATE 在行锁释放后执行，把 terminated 覆写为 on_hold——**被电子签名保护的不可逆 terminate 被一个无签名的 hold 动作事实撤销**，状态机约束被绕过；audit/status_history 会留下两条记录但终态错误；
  - 证据 4（同型兄弟）：srs/prs 状态机同样无锁（grep 证据 1），修复时应一并排查（原报告仅点名 ars）。
- 根因：check-then-act 竞态——状态机校验与状态写入之间无并发控制（行锁/条件 UPDATE/乐观锁三者皆缺）。
- 推荐修复策略（最小）：change_status 的实体读取改 `select(...).with_for_update()`（仅此一处调用点，_get_asset_or_404 可加形参或 change_status 内联带锁查询）——T2 的 SELECT 将阻塞至 T1 提交，随后基于新状态（terminated）校验自然失败，抛 StateInvalidError 业务错误。该方案锁窗口短（单行、单事务内），且签名/审计逻辑无需变动。备选：UPDATE ... WHERE status=:old + rowcount 校验，但 ORM flush 路径需改写为手写 UPDATE，侵入更大。srs/prs 状态机若确认同型，宜同批修复或另立条目。
- 修复状态：未开始
- 是否需要代码修复：是（ars change_status 读取加行锁；srs/prs 同型确认后同批处理）
- 是否需要 migration：否
- 是否需要测试：是（并发竞态难以在 HTTP 层稳定复现，最小验证：单元/集成层并发两个 change_status（asyncio.gather 双 session）断言后到者失败；或至少回归既有状态机测试全绿 + 代码评审确认锁语义）
- 风险说明：原型阶段并发低、实际触发概率小，但 terminate 属签名保护的 GxP 不可逆动作，竞态后果是合规性事故级别；修复用单行 FOR UPDATE，死锁风险可忽略（单表单行、无嵌套锁序）。注意 ESignatureService.sign 在锁内执行（密码校验含 bcrypt 开销）会拉长持锁时间——可接受（同一资产的并发状态变更本就该串行）。
- 人工决策备注：

## H-13：[BE-be-mm-01] 软删批次后复用批号触发500

- 来源章节：2. 后端代码审查发现（按域）（后端:be-mm）
- 严重程度：High
- 置信度：高
- 原报告位置：REVIEW_REPORT_2026-06-10_STAGE1.md → 2. 后端代码审查发现（按域） → [BE-be-mm-01]
- 涉及文件：`backend/app/domains/mm/services.py:380-391, 440-454; backend/alembic/versions/2026_05_13_0500_0033_mm_material_batch.py:72`
- 问题摘要：uq_material_batch 是全表唯一约束（含软删行），但 add_batch/update_batch 的重复预检均过滤 deleted_at IS NULL。软删某批次后再以同批号新建/改名，预检通过、flush 时撞 DB 唯一约束抛 IntegrityError。
- 原报告建议：将 uq_material_batch 改为 partial unique index（WHERE deleted_at IS NULL），或预检改为全表口径并提示编码占用。
- 当前状态：已复核（2026-06-11，与 H-08/H-10 同属"软删唯一约束"同类缺陷包）
- 复核结论：**真实**
  - 证据 1：0033 migration:72 与 mm/models.py:109 均为全量 `UniqueConstraint("material_id", "batch_number", name="uq_material_batch")`，含软删行；
  - 证据 2：add_batch 预检（services.py:380-391）与 update_batch 改批号预检（services.py:441-454）均过滤 `deleted_at IS NULL`——软删批次占用的批号预检放行，flush 撞全量约束 → IntegrityError 冒泡 500，绕过了已定义的业务错误 MaterialBatchNumberDuplicateError（44001 族）；
  - 证据 3：触发路径有两条（新建批次 / 改名撞已删批号），与原报告所述一致。
- 根因：0033 建表时唯一约束未考虑软删行，与预检 active-only 口径错位（与 H-08/H-10 同模式）。
- 策略建议：**倾向策略 B，但批号口径属合规敏感，需负责人先拍板**。考量：错删批次后重录同批号是主要业务场景（B 支持）；但 GxP 视角下"同一物料同一批号出现一活一删两行"对批次追溯/审计报表有歧义风险——若合规口径要求批号终身唯一，则选策略 A（预检去掉 deleted_at 过滤、改全表口径，命中时返回 MaterialBatchNumberDuplicateError 并提示"批号已被已删除批次占用"），A 无需 migration、改动仅 services.py 两处查询。原型阶段两者皆可行，区别在口径承诺。
- 修复状态：未开始
- 是否需要代码修复：是（B：migration + models.py；A：services.py 两处预检）
- 是否需要 migration：策略 B 需要；策略 A 不需要
- 是否需要测试：是（软删批次后复用批号：按选定口径断言 201 或 409；改名撞已删批号同口径；未删行间重复仍 409）
- 人工决策备注：批号复用口径必须负责人确认（合规敏感，参照原型阶段姿态由负责人直接决策）。2026-06-11 决策：暂不与 H-08/H-10 同批修复（H-08/H-10 已按策略 B 走 migration 0045），本条保持未修，待批号复用口径确认后单独处理。

## H-14：[TEST-be-tests-01] 硬编码 8000 绕过隔离 test DB

- 来源章节：5. 测试覆盖缺口（后端:be-tests）
- 严重程度：High
- 置信度：高
- 原报告位置：REVIEW_REPORT_2026-06-10_STAGE1.md → 5. 测试覆盖缺口 → [TEST-be-tests-01]
- 涉及文件：`backend/tests/test_smoke.py:8 / test_rate_limit.py:14 / test_refresh_token.py:13`
- 问题摘要：这三个文件模块级 BASE_URL='http://localhost:8000'，用自建 AsyncClient 直打 dev 服务；run_tests.sh 把测试服务起在 8001 并经 TEST_BASE_URL 隔离 cmab_test，这些用例完全绕过隔离，读写/污染 dev 库或在 dev 未起时失败。
- 原报告建议：改用 conftest 的 BASE_URL/http_client fixture，统一读 TEST_BASE_URL
- 当前状态：已复核（2026-06-11）
- 复核结论：**真实**
  - 证据 1（隔离机制确认）：`backend/scripts/run_tests.sh:18-20,61-62`——引导 cmab_test → 8001 起独立 uvicorn（test DB + 独立 redis db）→ `export TEST_BASE_URL=http://localhost:8001` → pytest；`conftest.py:26` 正确模式为 `BASE_URL = os.getenv("TEST_BASE_URL", "http://localhost:8000")`；
  - 证据 2（三处硬编码确认）：`test_smoke.py:8`、`test_rate_limit.py:14`、`test_refresh_token.py:13` 均为模块级 `BASE_URL = "http://localhost:8000"`，且全部用自建 `AsyncClient(base_url=BASE_URL)`（smoke 2 处、rate_limit 2 处、refresh_token 8 处），不经 conftest 的 BASE_URL/http_client fixture，完全绕过 TEST_BASE_URL；
  - 证据 3（影响分级）：test_smoke 仅只读 /health + 401 探测（污染轻微但目标错误）；test_rate_limit 反复打 dev 服务登录接口——在 dev redis 留限流桶、向 dev 库写登录失败审计；test_refresh_token 在 dev 库真实创建 refresh token / 登录历史 / 审计日志——实质性污染 dev 数据（即此前"pytest 18k+ 垃圾累积"问题在这三个文件上的残留）；
  - 证据 4（确定性风险）：dev 服务未起（纯 CI / 仅 test 环境）时这三个文件必然连接失败；dev 起着时则测限流等行为受 dev 数据/状态漂移影响，结果不确定。
- 根因：test DB 隔离改造（run_tests.sh + conftest 读 TEST_BASE_URL）落地时，这三个早期 Phase 1 测试文件的模块级常量未随迁，仍是改造前的直连写法。
- 最小修复建议：三个文件各删 1 行硬编码，改为 `from tests.conftest import BASE_URL`（与 test_admin_users.py 导入 pg_connect_kwargs 的既有模式一致）；自建 AsyncClient 写法可保留（rate_limit/refresh_token 需要无状态裸客户端，不必强迁 http_client fixture）。
- 修复状态：已修复（2026-06-11）
- 是否需要代码修复：是（测试代码最小修复，已完成）
- 是否需要 migration：否
- 是否需要测试：是（已运行，见备注）
- 风险说明：修复前 make test-be 的"全绿"对这三个文件而言测的是 dev 服务而非隔离环境，且持续向 dev 库/redis 注入测试数据；修复仅改测试侧 URL 来源，零业务风险。
- 人工决策备注：三个文件（test_smoke.py / test_rate_limit.py / test_refresh_token.py）模块级硬编码 `BASE_URL = "http://localhost:8000"` 均改为 `from tests.conftest import BASE_URL`（统一经 TEST_BASE_URL 指向 8001 隔离服务），自建 AsyncClient 写法保留；run_tests.sh / conftest.py / Makefile 未动。验证：① grep 确认 tests/ 下硬编码 :8000 已清零（仅剩 conftest 的 env 兜底默认值与注释，属正确模式本身）；② 三文件 11 项隔离环境全过；③ 全量 run_tests.sh 跑 3 次——首次 test_refresh_old_token_rejected_after_rotation 偶发失败 1 次（单测重跑即过），后两次全量 279 项均全绿。遗留观察项：该用例在全量下存在偶发 flake（旧 refresh 重放预期 401 偶现不满足），系本修复将其迁入共享隔离环境后新暴露的时序/顺序敏感问题，与 URL 修复本身无关，建议后续单独排查（不属 H-14 范围）。

## H-15：[MATCH-数据模型↔ORM+迁移-01] milestone_type 空约束 ORM↔DB 冲突

- 来源章节：4. 文档与代码匹配性审查发现（匹配性:数据模型↔ORM+迁移）
- 严重程度：High
- 置信度：高
- 原报告位置：REVIEW_REPORT_2026-06-10_STAGE1.md → 4. 文档与代码匹配性审查发现 → [MATCH-数据模型↔ORM+迁移-01]
- 涉及文件：`backend/app/domains/prs/models.py:144 ; backend/alembic/versions/2026_05_11_1700_0006_prs_init.py:117 ; 2026_05_11_2310_0014_prs_milestone_v2.py`
- 问题摘要：迁移 0006 建 milestone_type 为 NOT NULL，0014 未改其可空性；但 ORM(models.py:144) 与 Pydantic(schemas.py:187 `milestone_type: MilestoneType|None=None`) 均可空，service:395 直接透传 None。创建里程碑省略 type 时 DB 抛 NOT NULL 违例。
- 原报告建议：迁移将该列改可空，或 schema 设为必填
- 当前状态：已复核（2026-06-11）
- 复核结论：**真实**
  - 证据 1（DB NOT NULL）：0006 migration:117 `milestone_type String(32) nullable=False`；0014 的 alter_column 仅动 planned_date（改 NOT NULL）与 status server_default，未触碰 milestone_type 可空性——DB 至今 NOT NULL；
  - 证据 2（应用层三处全可空）：prs/models.py:144 `Mapped[str | None]`；schemas.py:187 Create `milestone_type: MilestoneType | None = None`、:202 Update 同；services.py add_milestone（:388-405）将 payload.milestone_type 直接透传；
  - 证据 3（触发路径）：POST /projects/{code}/milestones 省略 milestone_type → INSERT NULL → NOT NULL 违例 IntegrityError 500（service 不 catch，项目约定）；Update 路径显式传 milestone_type=null 同样可触发（exclude_unset 只挡"未传"，挡不住"传 null"）；
  - 证据 4（设计口径）：0014 docstring 明确"milestone_type 收敛到 §9.3 三值（gate/deliverable/decision）"且同次把 planned_date 收紧为 NOT NULL——设计基准意图是必填三值，可空是应用层笔误而非设计；现有 CHECK 约束（models.py:127）也按三值写。
- 根因：0014 按 §9.3 重构时收紧了 DB 与 CHECK，但 Pydantic/ORM 的 Optional 标注未同步收紧。
- 推荐修复策略：**方案 A（收紧应用层为必填）**。依据：设计基准 §9.3 + DB 现状 + 既有 demo 数据（26 条里程碑均有 type）一致指向必填；方案 B（放宽 DB）违背 0014 的明确收敛意图。最小改动：schemas.py:187 Create 改 `milestone_type: MilestoneType`（必填，缺省 422）；models.py:144 改 `Mapped[str]`（对齐 DB，无需 migration）；Update 保持 Optional 但需防显式 null（validator 拒绝或 service 忽略 None）。
- 修复状态：已修复（2026-06-11，方案 A，与 H-16 同批）
- 是否需要代码修复：是（已完成：schemas.py Create 的 milestone_type 改必填并注明三值；Update 加 field_validator 拒绝显式 null；models.py:144 改 `Mapped[str]` nullable=False 对齐 DB；services.py 未动——validator 已挡住 null 透传）
- 是否需要 migration：否（DB 现状即目标状态）
- 是否需要测试：是（已补 test_milestone_type_required——缺省 type → 400 validation_failed（本项目 422 统一映射 400，V1.1 §4.1）；test_milestone_type_update_explicit_null_rejected——显式 null → 400；定向 21 项 + 全量 283 项全绿）
- 风险说明：现状是 500 而非数据风险（DB 约束兜住了）；修复后 API 契约收紧（缺省 type 从 500 变 400）。
- 人工决策备注：前端已只读确认无需改——MilestoneTable.tsx 创建表单 milestone_type 本就 required + openCreate 预填 'gate'（:144、:243），编辑回填 `?? undefined` 经 axios 序列化丢弃不会发显式 null。

## H-16：[DOC-架构设计+数据模型(内部-01] EQP 范围自相矛盾

- 来源章节：1. 文档审查发现（文档:架构设计+数据模型(内部质量)）
- 严重程度：High
- 置信度：高
- 原报告位置：REVIEW_REPORT_2026-06-10_STAGE1.md → 1. 文档审查发现 → [DOC-架构设计+数据模型(内部-01]
- 涉及文件：`docs/CMAB_MDM_Portal_架构设计文档_V1_1.md:120 与 41/73`
- 问题摘要：§1.3.2 范围外明确写'设备主数据（未来纳入 CMMS 或独立 Equipment Master）'，但适用范围(§41)、§1.2.1/§1.2.2 已将 Equipment(EQP) 列为 V1.2 新增的第五业务域。
- 原报告建议：§1.3.2 删除或改写设备主数据条目，§1.3.1 In-Scope 表补 EQP 行。
- 当前状态：已复核（2026-06-11）
- 复核结论：**真实**
  - 证据 1（已纳入的三处）：ARCH V1_1.md:35 修订记录 V1.2 条目明确"新增 EQP 设备主数据域（第五个业务域）"；:41 适用范围与 :73 业务目标均列五域含 Equipment Master（EQP，V1.2 新增）；
  - 证据 2（仍排除的两处）：:120 §1.3.2 Out-of-Scope 仍列"设备主数据（未来纳入 CMMS 或独立 Equipment Master）"；§1.3.1 In-Scope 表（:108-114）只有 SRS/PRS/ARS/MM/REF/AUDIT 六行，无 EQP 行——同一文档内自相矛盾；
  - 证据 3（事实口径）：EQP 已实装（migration 0040-0044、横切全局搜索/仪表盘、批量导入、测试全过），项目真实口径=EQP 已进入当前范围；
  - 证据 4（已被自家勘误登记）：V1.3 偏离说明 draft:71 已记录"§1.3.2 仍把设备主数据列范围外（与自身修订记录矛盾）、§3.2 无 EQP 子节、§6.1 无 eqp 行 → 勘误 E7/E8/E9（ARCH 修订清单）"——本条与勘误体系是同一问题，修复时应对齐 E7/E8/E9 编号销项。
- 根因：V1.2 增补 EQP 时只更新了修订记录和范围综述段，§1.3.1/1.3.2 范围明细表漏改（md 单轨期文档维护遗漏，docx 停 V1.1 的双轨现状放大了漏检）。
- 推荐修复策略：最小文档修复两处——① §1.3.2 该条**改写而非删除**（保留历史语境）："设备主数据：V1.1 原列范围外（拟纳入 CMMS），V1.2 起已纳入本系统为第五业务域 EQP，见修订记录与 §1.3.1"；② §1.3.1 In-Scope 表补一行：Equipment Master | EQP | 全公司仪器设备身份注册（V1.2 新增） | 仪器设备。同时在 V1.1_修订清单勘误段把 E7 对应项标记落实（E8 §3.2 子节、E9 §6.1 eqp 行属更大篇幅增补，可与 V1.3 批次一起做，不必本条捆绑）。
- 修复状态：已修复（2026-06-11，与 H-15 同批）
- 是否需要代码修复：否（纯文档）
- 是否需要 migration：否
- 是否需要测试：否（grep 验证：ARCH md 中 EQP 四处提及已一致——修订记录:35、适用范围:41、§1.3.1 表:113 新增行、§1.3.2:121 改写条目，无矛盾语境残留）
- 风险说明：纯文档矛盾，无运行时影响；但范围表是对外沟通/审计的第一入口，矛盾会误导评审与 CSV 验证范围界定。修复仅改 md（docx 停 V1.1 为已知双轨现状，不动 docx）。
- 人工决策备注：ARCH md §1.3.1 补 EQP 行（Equipment Master | EQP | 全公司仪器设备身份注册（V1.2 新增）| 仪器设备）；§1.3.2 改写为"V1.1 原列范围外；V1.2 起已纳入第五业务域 EQP"（保留历史语境）。勘误 E7 已在 ARCH-MDM-001_修订清单.md 标记**已落实**（注明负责人决策直接改 md、未采用"设备运营数据"备选措辞——该语义留给 E8）；E8/E9 未动，随 V1.3 批次处理。

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

