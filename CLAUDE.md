# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 项目概览

CMAB MDM Portal —— 生物制药 CMC 主数据平台,五域:SRS(物质)/PRS(项目)/ARS(资产)/MM(物料)/EQP(设备) + auth/audit/search 横切域。后端 FastAPI(async SQLAlchemy 2.0 + asyncpg + Pydantic v2),前端 React 18 + Vite + Ant Design + Zustand + React Query。

**当前为原型阶段,未进入 GxP/GMP。** 不走正式评审会/合规产物暂缓;原本"需评审"的事项由负责人直接决策。不要主动要求走 GMP 流程或补合规产物——除非用户明确说进入 GMP。

## ⚠️ 数据安全:已上线测试运行,严禁灌 demo / 清库(2026-06-15 起)

项目已进入**上线测试运行**,dev 库里的数据**部分是真实生产数据**,不可破坏:

- **物料(MM)、设备(EQP)= 真实数据**(物料 ~3770、设备 ~461),绝不能被覆盖/清空/灌假数据。
- **物质(SRS)、项目(PRS)、资产(ARS)= 真实即为 0 条**(尚未录入,空是正常状态,不是数据丢失)。若看到物质里有 `audit test...` 之类记录,那是历史污染,清理需用户确认,不要自行 seed 补数。
- **禁止运行任何会灌 demo 或重置库的命令**:`make seed-demo`、`make seed --demo`、`make reset-db`、`app.scripts.seed_real_demo` 等——除非用户**明确**要求。`make seed`(基线种子)同样先确认。
- **测试只能走 `make test-be`**(隔离 `cmab_test` 库)。**绝对禁止** `make test-be-dev` 或在容器里直跑 `pytest`——会打到 dev 库 `cmab_mdm`,污染真实物料/设备数据。

## 工具链全在 Docker 容器里

ruff / mypy / eslint / pytest / alembic **都不装在宿主机**,只在容器内。一律通过 `make`(底层 `docker compose -f deploy/docker-compose.dev.yml exec`)或 `docker exec <容器名> ...` 调用,不要在宿主机直接跑这些命令。容器名:`cmab-mdm-backend` / `cmab-mdm-frontend` / `cmab-mdm-postgres` / `cmab-mdm-redis`。

## 常用命令

```bash
make up / down / logs-be / logs-fe   # 起停/看日志
make migrate          # alembic upgrade head(容器内)
make seed             # 基线种子数据;make seed-demo 带演示数据
make test-be          # ✅ 跑后端测试(见下方坑)
make lint-be          # ruff check . && mypy app
make lint-fe          # pnpm lint(eslint,--max-warnings 0)
make gen-types        # 前端从后端 OpenAPI 生成 src/api/schema.d.ts(需后端在跑)
make docs-extract     # 从 .docx 派生 .md(见文档双轨)
make docs-check       # CI 文档一致性校验
```

## 测试(关键坑)

- **永远用 `make test-be`**,不要在容器里直接 `pytest`。`make test-be` 走 `scripts/run_tests.sh`:重建独立测试库 `cmab_test` + 8001 端口测试服务 + redis db15,与 dev 数据隔离。
- `make test-be-dev`(直跑 `pytest`)会打到 **dev 库 `cmab_mdm`**,造成数据漂移、且缺 seed 用户时登录 fixture 报 401。仅在明知后果时用。
- 单测:`make test-be ARGS` 不支持,直接 `docker exec cmab-mdm-backend bash scripts/run_tests.sh tests/test_x.py::test_y` 或在隔离环境下传参给 run_tests.sh。
- pytest 配置 `asyncio_mode=auto`,测试文件 `test_*.py`,放 `backend/tests/`。

## 数据库变更

- 所有 schema 变更走 **alembic**,不要手改表。迁移文件 `backend/alembic/versions/`,命名 `YYYY_MM_DD_HHMM_NNNN_desc.py`。
- alembic 用同步驱动:`DATABASE_URL_SYNC`(与 app 的异步 `DATABASE_URL` 分开);两者指向不同逻辑库(dev `cmab_mdm` / test `cmab_test`),配错会静默失败。
- 涉及合规字段的库变更,改前先与用户确认。

## 后端代码约定

- 域分层:每个 `app/domains/<域>/` 含 `models.py`(ORM)/`schemas.py`(Pydantic I/O)/`services.py`(业务逻辑);路由在 `app/api/v1/`;横切在 `app/shared/`。
- ruff 选用规则 E,W,F,I,B,C4,UP,N,SIM;忽略 E501/B008/N805;`alembic/versions/*` 忽略 E501,F401。无 `ruff format`(不要擅自引入格式化器,会造成大面积 churn)。
- **async SQLAlchemy 坑**:service 内禁 `try/except IntegrityError + rollback`,用 pre-check 替代;强一致场景在 service 内显式 `commit`(FastAPI yield 依赖的 commit 在 response 之后才跑);登录/签名等失败路径的计数与审计必须用独立旁路 session(`AsyncSessionLocal`)commit,避免主事务 rollback 丢失。

## 前端代码约定

- 包管理器 **pnpm**(禁 npm)。依赖装在容器内:宿主 `pnpm install` + `docker exec -e CI=1 cmab-mdm-frontend pnpm install`;坏了重启容器。
- API 类型由 `make gen-types` 从后端 OpenAPI 生成到 `src/api/schema.d.ts`,不要手改。
- eslint `--max-warnings 0`,提交前需零告警。

## 文档双轨

`docs/*.docx` 是源(Word 编辑),`docs/*.md` 由 `make docs-extract` 自动派生。**不要手改 .md**——CI `make docs-check` 会因不一致而失败。派生工具走 `make docs-extract`,不要在 `scripts/` 另写 pandoc 包装。

## 提交约定

- 中文 conventional commits:`fix(auth): ...` / `feat(mm): ...` / `style(tests): ...`。
- 默认在 `main` 上开发;**仅在用户要求时**才 commit/push;要开 PR 时才建分支。
- commit message 末尾加 `Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>`。

## 端口与账号(dev)

- 宿主端口:前端 15173 / 后端 18000 / postgres 15432 / redis 16379(可被 `HOST_*_PORT` 覆盖)。
- dev 种子账号:`admin/__REDACTED_SEED_PASSWORD_1__`、`qingcheng/__REDACTED_SEED_PASSWORD_2__`、`researcher/__REDACTED_SEED_PASSWORD_5__`、`qa_reviewer/__REDACTED_SEED_PASSWORD_3__`、`readonly/__REDACTED_SEED_PASSWORD_4__`。

## 靶点域（tgt / ref.molecule_target）

- 靶点域设计决策见 `docs/decisions/2026-08-17-target-domain.md`，**开发前必读**（7 项拍板决策 + PoC 实测结论 + 一期改动边界）。PoC 产物在 `poc/target_prefill/`。
- 一期已落地（2026-08-18，migration 0050/0051）：靶点字段按 UniProt 标准自动维护（无自定义类型/定位枚举）；`tgt.target` / `tgt.target_source_snapshot` / `ref.molecule_target`；后端 `app/domains/target/`（`prefill.py` 为链路纯逻辑）+ `api/v1/targets.py`；前端 `src/modules/targets/`；外部只读 HTTP 封装 `app/shared/http_client.py`（httpx+tenacity，域名白名单）。
- 新权限码 `target:{create,read,update,approve}`：dev/prod 库用 `python -m app.scripts.seed_target_permissions` 幂等补齐（禁重跑 make seed）。
- 批量预填：`python -m app.scripts.prefill_targets --inn <INN...> --out data/target_prefill`（离线出 prefill_form.json + summary.md/csv，人工在表单核对录入；Mac 上加 `--no-proxy`）；录完后 `--attach-snapshots` 回填快照。测试用 MockTransport 打桩，不许真出网。

## 会话策略 / 自动登出（2026-09-04 起，migration 0054）

- 三个时长**不在 .env**，在 `meta.system_config` 的 `session.*` 键：通行证 15 分钟 / 空闲超时 30 分钟 / 单次登录硬上限 12 小时 / 展示模式空闲 720 分钟。管理员在 **系统管理 → 会话策略**（`/admin/session-policy`，权限 `system:config`）在线改，立即生效，变更进 audit_log + change_history。
- 机制：滑动会话。refresh token 每次换证只续到 `min(现在+空闲窗口, 会话开始+硬上限)`（`refresh_token.session_started_at` 轮换时原样传递）；没人换证就自然过期 = 空闲登出。核心代码 `app/domains/auth/session_policy.py`、`services.py` 的 `_refresh_deadline`。
- `GET /api/v1/auth/session-policy` 给各子系统前端读当前用户生效值；前端会话守卫 `frontend/src/shared/sessionGuard.ts`（通用，各子系统抄这一份）+ `useSessionGuard.ts`（MDM 接入，挂在 MainLayout）。活动时间共用 `localStorage['cmab_last_active']`。
- 角色 `DISPLAY_MODE`（展示模式，墙屏/看板，无业务权限）+ 权限 `system:config`：dev/prod 库用 `python -m app.scripts.seed_session_policy` 幂等补齐（禁重跑 make seed）。
- 门户/LabOps/批号/USP/LIMS/LCMS 各前端接守卫、统一改打 MDM 换证：见 `~/code/cmab-hub` 侧后续改造（截至 2026-09-04 尚未做）。

## 统一门户 cmab-hub（2026-08-17 起，改前端必读）

- 本系统已挂在统一门户之下：正式入口 **http://172.19.0.105:5100/mdm/**（Linux 上本系统前后端只听 127.0.0.1，老端口内网不可达）。Mac 本地同样经 `localhost:5100/mdm/`。
- 前端**自己认前缀** `/mdm/`：`vite.config` `base:'/mdm/'` + `main.tsx` `basename` + `src/shared/base.ts`（BASE/withBase/stripBase）。API 一律相对路径 `/mdm/api/...`，由门户 nginx 剥掉前缀转给后端（后端路由不变）。**不要**写死 host:端口，**不要**用不带前缀的绝对路径跳转/引资源。
- 登录态用**全公司统一 key**：`localStorage['cmab_access_token']`（MDM JWT）+ `localStorage['cmab_user']`（MDM 登录响应 user 对象）；同源共享 → 门户登录一次这里免登。别再改回私有 key。 authStore 用 zustand 自定义 storage 落到这两个 key。Linux 主机 nginx 受管副本在 `deploy/nginx/linux-host/cmab-mdm.conf`。
- 门户侧配置/路由/部署脚本在 `~/code/cmab-hub`（`nginx/hub-locations.conf`、`deploy/linux/`），约定见其 `CLAUDE.md`。

## 设备域 EQP：全公司设备清单（2026-09-10 起，migration 0057）

- **定位变了**：`eqp.equipment` 从「研发设备身份注册表」升级为**全公司设备清单**，由**设备部**维护（负责人 2026-09-10 拍板）。分工：设备部管清单和设备状态、计量专员管校准、验证部平台（`cmab_qv`，门户 `/qv/`）管验证，LabOps 只留研发自己的领用/维修。设备状态于 2026-09-15 正式收口 MDM（migration 0060）：保留 `status=active/retired` 表示主数据在册状态，新增 `equipment_status=enabled/sealed/scrapped` 表示启用/封存/报废；历史记录的设备状态默认启用，交由设备专员复核，不根据主数据状态自动猜测。LabOps 不再作为设备状态权威源。LabOps 现有的校准表与位置字段属于历史遗留，后续迁出，本次未动。
- **0057 新增 6 个字段**：`department`(使用部门，与 `auth.user.department` 同口径)、`site`(厂区)、`room`(房间/存放位置)、`criticality`(分级)、`criticality_basis`(分级依据)、`commission_date`(首次启用日期，与 `purchase_date` 购入日期分开)。迁移把已有 463 台（全是研发设备）的 `department` 回填为「研发部」。
- **分级字典跟着分类走**（别写死成一个列表）：`分析仪器`（检验设备）= **A/B/C**（USP 口径）；其他分类（工艺制备=生产设备、公用工程、通用实验室、IT）= **关键/一般**。三处同口径校验：DB `ck_equipment_criticality` CHECK、Pydantic `EquipmentCreate` 校验器、service 层 update（改分类时按**新**分类判，不合法回 400 提示一并调整）。前端 `criticalityOptions(category)` 出选项，换分类自动清空不合法的旧值。
- **不加「用途类型」字段**（生产/检验设备）：与现有 5 分类重叠。冰箱等归通用/公用，分级规则按分类区分即可。
- **导入设备部台账**（受控表单 SMP-PES-001-F13，各部门一份，格式一致）：
  ```bash
  docker cp 台账.xlsx cmab-mdm-backend:/tmp/l.xlsx
  docker exec cmab-mdm-backend python -m app.scripts.import_equipment_excel \
    --xlsx /tmp/l.xlsx --dry-run --department 生产一部 --site 南楼 --report /tmp/r.csv
  ```
  台账**没有分类列** → 脚本按设备名称关键词预归类，报告列「需人工核对分类」=Y，**必须人工核一遍再去掉 --dry-run**。台账把「英文名/中文名」写在一格（`Bioreactor/225L生物反应器`）**原样入库，不拆**（2026-09-11 负责人拍板：设备名称是一个整体，台账没有独立英文名列，拆开等于擅自改写主数据；此前版本会拆，正式库 13 台已还原）；单元格里的折行会去掉；「别名/曾用名」进正式列 `alias`（migration 0059，2026-09-11 转正，此前塞在 extra 里界面看不到也搜不到；列表搜索会一并匹配别名）；日期只到年月（`2016.05`）按当月 1 日入库；别名/出厂日期/总重等无正式列的信息进 `extra`，不丢。
- **关键词表顺序敏感**（`CATEGORY_ALIASES`）：强信号（层析/装柱/压缩柱/轴向）排在最前，否则「装柱工作站」会被 IT 的「工作站」抢走；工艺物料罐只写具体名（补料罐/培养基罐…），不用泛词「罐」，否则抢走「液氮罐」。改这张表后跑 `tests/test_import_equipment_excel.py`。

## 部门管理员 DEPT_ADMIN（2026-09-10 起，migration 0055）

- 背景：验证部平台（qv-validation-platform，门户 `/qv/`）登录/角色走 MDM，验证部负责人要能自己管本部门的人。
- 角色码 `DEPT_ADMIN` 是身份标签（系统角色，不挂 permission），能力由 `app/domains/auth/dept_admin.py` 按角色码判定：范围 = `auth.user.department` 与自己**完全相同**的用户；可 查看 / 锁定解锁 / 挂摘「白名单角色」；不能 新建用户 / 改资料 / 改部门 / 重置密码，不能碰 `SYS_ADMIN`、`DEPT_ADMIN`（持有者也不能被其锁定）。
- 白名单 = 角色码前缀，存 `meta.system_config` 键 `dept_admin.delegable_role_prefixes`（默认 `QV_`），系统管理 → 部门管理员（`/admin/dept-admin-policy`，权限 `system:config`）在线改。验证部四角色 `QV_ADMIN / QV_ENGINEER / QV_REVIEWER / QV_VIEWER` 由 0055 迁移建好（MDM 内不挂权限，下游按 JWT.roles 解释）。
- 后端：`/users` 的 list/detail/roles/lock/unlock 用 `user_admin_scope()` 依赖（SYS_ADMIN 或 `user:manage` = 全公司，行为不变；DEPT_ADMIN = 本部门），create/update/reset-password 仍只认 `user:manage`；`GET /roles` 对 DEPT_ADMIN 只回白名单角色。跨部门 → 40303，非白名单角色 → 40301。角色分配 / 锁定 / 解锁**无论谁做**都写应用层 `audit_log`（auth 表没有触发器审计）。
- 前端：`authStore.userAdminScope`（`'all' | 'department' | null`）驱动 Sidebar / AdminTabs / UserListPage / UserRoleAssignModal 的显隐；`routes/FullAdminRoute.tsx` 把部门管理员挡在角色/权限/策略页之外。测试 `tests/test_dept_admin.py`（只能 `make test-be`）。
