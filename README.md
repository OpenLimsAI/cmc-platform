# CMAB MDM Portal

> 生物制药主数据管理平台 / Master Data Management Portal for Biopharmaceutical R&D

[![Status](https://img.shields.io/badge/status-scaffold-blue)]()
[![Backend](https://img.shields.io/badge/backend-FastAPI-009688)]()
[![Frontend](https://img.shields.io/badge/frontend-React%2018-61DAFB)]()
[![Database](https://img.shields.io/badge/database-PostgreSQL%2016-336791)]()

## 项目简介

CMAB MDM Portal 是 CMAB 公司内部的主数据管理系统，覆盖：

- **SRS** (Substance Registration System) - 物质身份登记
- **PRS** (Project Registration System) - 项目登记与生命周期
- **ARS** (Asset Registration System) - 资产登记
- **MM** (Material Master) - R&D 物料管理
- 跨域引用、审计追踪、电子签名

设计依据见 [docs/](./docs/) 下的设计文档：

**设计文档 V1.1**（当前活跃版本 · IT 架构组已签批 · 2026-05-12）：
- [CMAB_MDM_Portal_架构设计文档_V1_1.docx](./docs/CMAB_MDM_Portal_架构设计文档_V1_1.docx)（ARCH-MDM-001）
- [CMAB_MDM_Portal_数据模型设计文档_V1_1.docx](./docs/CMAB_MDM_Portal_数据模型设计文档_V1_1.docx)（DM-MDM-001）
- [CMAB_MDM_Portal_API接口规范_V1_1.docx](./docs/CMAB_MDM_Portal_API接口规范_V1_1.docx)（API-MDM-001）
- [CMAB_MDM_Portal_UI信息架构与线框图_V1_1.docx](./docs/CMAB_MDM_Portal_UI信息架构与线框图_V1_1.docx)（UI-MDM-001）

> 注：文档版本号管理采用渐进式策略 — 4 份 docx 当前内容为 V1.1 签字基线 + V1.2 修订记录登记（修订内容已在 md 派生与代码中落地，docx 封面字段保留 V1.1）；正式 V1.2/V1.3 docx 修订批次将在进入 GMP 准备阶段时一次性处理。原型阶段以 md 派生 + 偏离说明 V1.3_draft 为代码侧的唯一权威来源（详见文末「原型阶段文档使用约定」）。

每份 docx 旁都有同名 `.md` 派生副本（由 `make docs-extract` 自动生成，**不可手工修改**），方便程序读取与 grep。

**Phase 0 设计基准 V1.0**（已归档基线，保留作 V1.1 修订溯源）：
- [V1.0 docx × 4](./docs/) — 文件命名 `*_V1.0.docx`

**设计基准偏离说明**（DEV-MDM-001 系列）：
- [V1.3_draft](./docs/CMAB_MDM_Portal_设计基准偏离说明_V1.3_draft.md) — 历史偏离批次，明确封顶于 migration 0044；0045—0063 的现状以迁移文件、本 README 变更记录、项目 `CLAUDE.md`、`SMP_NUM_alignment_status.md` 和靶点域决策记录为准
- [V1.2_draft](./docs/CMAB_MDM_Portal_设计基准偏离说明_V1.2_draft.md) — 已封版归档（cap 0036，见其 §1B）：覆盖 Phase 1-4 + V1.2 评审 13 项决议 + §1A 勘误索引 E1-E12

**V1.0 → V1.1 修订清单**（评审决议过程档，决议已全部落地至 V1.1 docx）：
- [DM-MDM-001_修订清单](./docs/V1.1_修订清单/DM-MDM-001_修订清单.md)（12 项 · 9 接受 + 2 已决议 + 1 可选）
- [ARCH-MDM-001_修订清单](./docs/V1.1_修订清单/ARCH-MDM-001_修订清单.md)（11 项）
- [API-MDM-001_修订清单](./docs/V1.1_修订清单/API-MDM-001_修订清单.md)（21 项 · 含 `meta.error.type` 字典 / `require_all_permissions` 示例 / SET LOCAL GUC 修订）
- [UI-MDM-001_修订清单](./docs/V1.1_修订清单/UI-MDM-001_修订清单.md)（14 项 · 含资产域整章新增与状态变更全局交互模式）

### 双轨文档同步（docx 是源、markdown 是派生）

为了让"人读 docx、程序读 markdown"同时成立且保持一致，本项目采用**单源派生**模式：

| 角色 | 文件 | 维护方式 |
|---|---|---|
| **源** | `docs/*_V1_1.docx` | 走 Word 修订模式 + GxP 签字定稿 |
| **派生** | `docs/*_V1_1.md` | 由 `make docs-extract` 从 docx 自动提取，**不能手工修改** |
| **CI 门禁** | — | `make docs-check` 重新提取后 diff，不一致就 fail |

**派生处理**（封装在 `scripts/docs/extract_md.py` + `_blocks.py`）：
- pandoc 跑 `docx → gfm`
- 用 docx XML 原文（`xml:space="preserve"`）重建单单元格表为 ``` 代码围栏（sql/json/http/python/tsx/text）或 `>` blockquote callout — 因为 pandoc 转 HTML `<p>` 时会按 HTML 标准压缩连续空格，丢失 ASCII 框图对齐与代码缩进
- 清掉 pandoc attribute id、折叠空行、去行尾空白
- 文件头加自动生成警告注释

**变更流程**：
1. 内容变更先在 docx 里走 Word 修订模式
2. 评审签字定稿
3. 跑 `make docs-extract` 重新生成 markdown
4. `git add docs/*.md && git commit`
5. CI 自动跑 `make docs-check` 校验一致性

**当前状态**：V1.1 已定稿，4 份 docx + 4 份 md 派生已入库（2026-05-12）。

工具依赖：
- 优先用本地 `pandoc`（macOS: `brew install pandoc` / Linux: `apt install pandoc`）
- 没有则自动 fallback 用 `docker run pandoc/core:3.1`（项目已依赖 docker）

例外：以下 markdown 文档是**原生 markdown**，**不**走双轨派生：
- 设计基准偏离说明 V1.2_draft（评审材料，markdown 原生）
- V1.0 → V1.1 修订清单 4 份（评审对照表，markdown 原生）

## 技术栈

| 层 | 技术 |
|---|---|
| 前端 | React 18 + TypeScript + Vite + Ant Design 5 |
| 后端 | FastAPI + SQLAlchemy 2.0 (async) + Pydantic v2 |
| 数据库 | PostgreSQL 16 |
| 缓存/队列 | Redis 7 |
| 部署 | 本地 Docker Compose；Linux 原生 venv + systemd + nginx |

## 快速开始

### 前置要求

- Docker Desktop 或 Docker Engine + Docker Compose v2
- Node.js 20+ (本地前端开发)
- Python 3.12+ (本地后端开发)

### 一键启动（推荐）

```bash
# 1. 克隆项目
git clone <repo-url> cmab-mdm-platform
cd cmab-mdm-platform

# 2. 复制环境变量
cp .env.example .env
# 编辑 .env，至少修改 SECRET_KEY 和数据库密码

# 3. 启动所有服务
docker compose -f deploy/docker-compose.dev.yml up -d --build

# 4. 等待服务启动（约 30-60 秒），查看状态
docker compose -f deploy/docker-compose.dev.yml ps

# 5. 初始化数据库（仅全新空库）
docker compose -f deploy/docker-compose.dev.yml run --rm --no-deps -T backend \
    alembic upgrade head
docker compose -f deploy/docker-compose.dev.yml restart backend
# 已有开发库含真实物料/设备数据；执行 seed 前必须确认目标确为空库
docker compose -f deploy/docker-compose.dev.yml exec backend \
    python -m app.scripts.seed_data

# 6. 访问（宿主侧默认端口，可用 HOST_*_PORT 环境变量覆盖；容器内为 5173/8000/5432/6379）
# 前端：       http://localhost:15173
# 后端 API：   http://localhost:18000
# API 文档：   http://localhost:18000/api/v1/docs
# 数据库：     localhost:15432 (用户/库见 .env)
```

### 默认账号

种子数据脚本会创建以下测试账号（仅 dev/test 环境）：

| 用户名 | 密码 | 角色 |
|--------|------|------|
| admin | __REDACTED_SEED_PASSWORD_1__ | SYS_ADMIN |
| qingcheng | __REDACTED_SEED_PASSWORD_2__ | SUBSTANCE_STEWARD, PROJECT_MANAGER |
| researcher | __REDACTED_SEED_PASSWORD_5__ | CMC_RESEARCHER |
| qa_reviewer | __REDACTED_SEED_PASSWORD_3__ | QA_REVIEWER |
| readonly | __REDACTED_SEED_PASSWORD_4__ | READ_ONLY_USER |

⚠️ **生产环境部署前必须修改所有默认密码与 SECRET_KEY**

## 目录结构

```
cmab-mdm-platform/
├── backend/                  # FastAPI 后端
│   ├── app/
│   │   ├── api/              # API 路由层
│   │   ├── core/             # 配置、安全、数据库
│   │   ├── domains/          # 业务域（srs/prs/ars/mm）
│   │   ├── shared/           # 共享层（编码生成器、权限、审计）
│   │   ├── scripts/          # 工具脚本（种子数据等）
│   │   └── main.py           # 应用入口
│   ├── alembic/              # 数据库迁移
│   ├── tests/                # 测试
│   ├── pyproject.toml
│   └── Dockerfile
│
├── frontend/                 # React 前端
│   ├── src/
│   │   ├── api/              # API 客户端
│   │   ├── modules/          # 业务模块
│   │   ├── shared/           # 共享组件、布局
│   │   ├── stores/           # Zustand 状态
│   │   └── routes/           # 路由配置
│   ├── package.json
│   ├── vite.config.ts
│   └── Dockerfile
│
├── deploy/                   # 部署配置
│   ├── docker-compose.dev.yml
│   ├── docker-compose.prod.yml
│   └── nginx/
│
├── docs/                     # 设计文档：V1.1 活跃（4 docx + md 派生）/ V1.0 归档 / V1.2 偏离说明 / V1.1 修订清单
│
├── .env.example
├── .gitignore
├── Makefile                  # 常用命令
└── README.md
```

## 常用命令

项目根目录提供 Makefile：

```bash
make up          # 启动所有 dev 服务
make down        # 停止所有服务
make logs        # 查看日志
make logs-be     # 仅看后端日志
make logs-fe     # 仅看前端日志
make migrate     # Mac 业务库预检 → 备份 → 迁移 → 字段/计数/就绪验收；不操作 Linux
make db-status   # 只读核对 Mac 业务库（后端停止时仍可使用）
make seed        # 仅全新空库加载基线种子；已有库先确认
make reset-db    # ⚠️ 删除开发库全部数据；默认禁止
make test-be     # 在独立 cmab_test 库运行后端测试
make lint-be     # 后端代码检查
make lint-fe     # 前端代码检查
make gen-types   # 从后端 OpenAPI 生成前端 TS 类型
```

## 本地开发模式（不用 Docker）

适合需要 IDE 调试的场景：

### 后端

```bash
cd backend
uv venv
source .venv/bin/activate           # Windows: .venv\Scripts\activate
uv pip install -e ".[dev]"

# 启动 PostgreSQL（仍用 Docker）
docker compose -f deploy/docker-compose.dev.yml up -d postgres redis

# 应用迁移
alembic upgrade head

# 加载种子数据
# 仅限全新空库；已有开发库不要执行
python -m app.scripts.seed_data

# 启动 API
uvicorn app.main:app --reload --port 8000
```

### 前端

```bash
cd frontend
pnpm install
pnpm dev    # 默认 5173
```

## 开发流程

```
本地开发 (Mac/PC)
    │
    ├─ 后端：修改代码 → uvicorn 自动 reload
    ├─ 前端：修改代码 → Vite HMR
    ├─ 数据库变更：alembic revision --autogenerate -m "..."
    │             → 隔离自动化测试 → make migrate（业务库备份/迁移/验收）
    │
git push
    │
Linux 服务器（生产 = 原生 venv+systemd+nginx，非 Docker）
    │
    ├─ 检出已审核的提交，准备匹配依赖
    └─ bash deploy/deploy.sh <完整commit-SHA>
          → 明确目标 → 构建 → 停服务/备份 → migration → 字段/计数/就绪验收
```

## 部署

> **Docker 仅用于本地开发**（`deploy/docker-compose.*.yml`、`make up`）。
> **Linux 生产服务器是原生部署**：后端 venv + systemd，前端 `pnpm build` 后由 **nginx** 伺服，
> PostgreSQL 是宿主机**原生 PG 集群**(本服务器 MDM 用 `:5433` 的 `mdm` 集群、库 `cmab_mdm`)，Redis 原生。
> 目录 `/opt/cmab-mdm-platform`，运行身份 `prometheus`。

### 生产环境（Linux 服务器，原生）

```bash
# 在生产服务器；先检出已审核的提交（不发布过程中隐式 git pull）
cd /opt/cmab-mdm-platform
# 准备该提交匹配的依赖；发生不兼容变更时先安排维护窗口
backend/.venv/bin/pip install -q -e backend
# 参数填此次批准发布的完整 SHA；工作区不干净或 SHA 不匹配会拒绝
bash deploy/deploy.sh <完整commit-SHA>
```

发布报告与备份在 `backups/releases/linux-*`。Mac 的 `make migrate` 和 Linux 发布相互独立，
不能用测试库迁移成功代替业务库验收；没有跨环境业务数据复制。
启动时会核对实际连接库的迁移版本和关键设备列；版本/字段不匹配时拒绝启动。
`/health` 与 `/api/v1/health` 会实时检查数据库就绪状态，不匹配或不可连接返回 503。
检查不执行迁移，也不修改版本记录。

**服务拓扑（本服务器实际）：**

| 组件 | 形态 |
|---|---|
| 后端 | systemd `cmab-backend.service`(venv `uvicorn app.main:app --port 18000`，依赖 redis + postgresql) |
| 前端 | nginx `/etc/nginx/conf.d/cmab-mdm.conf`：`listen 15173` → root `/opt/cmab-mdm-platform/frontend/dist`，`/api` 反代 `127.0.0.1:18000` |
| 数据库 | 宿主机原生 PG16 集群 `mdm` :5433，库 `cmab_mdm`，用户 `cmab_app` |
| Redis | 宿主机原生 `redis-server` |

> 同机另有 CMC LabOps Portal(`/opt/cmc-labops`，原生 systemd `cmc-backend` :8010 + nginx :5110，PG 集群 :5432)，
> 通过 MDM 的 `/api/v1/auth/login` 做登录鉴权、按需引用主数据。
>
> 备份/恢复见 `docs/RUNBOOK_BACKUP_RESTORE.md`。

## 原型阶段文档使用约定

本项目当前为原型阶段，文档体系按"够用即可"原则简化：

1. **代码侧权威源**：
   - 4 份 V1.1 派生 md（`docs/CMAB_MDM_Portal_*_V1_1.md`）
   - 偏离说明 V1.3_draft（`docs/CMAB_MDM_Portal_设计基准偏离说明_V1.3_draft.md`）
   - 各文档 V1.3 勘误登记段（`docs/V1.1_修订清单/*.md` 末尾，E1-E12）

2. **暂不维护项**（待 GMP 准备阶段一次性补）：
   - docx 封面版本号 / 文件名重命名
   - V1.3 docx 正文修订批次（Word 修订模式 + 会签）
   - OQ 追溯矩阵 +104 测试用例定级（`docs/csv_oq_traceability.md` §0 已登记缺口）

3. **新发现的偏离**：直接登记到 V1.3_draft，无需走评审；代码可先行，文档登记不晚于本周 commit。

4. **进入 GMP 准备阶段的触发条件**（任一满足即本节作废，立即切换完整文档控制 SOP——docx 重命名、Word 修订、QA 会签、CSV 验证全套）：
   - 任一商业化产品的 CMC 申报涉及本系统数据；或
   - QA 部门提出"系统进入 GxP 范围"决议。

## License

Internal use only · CMAB Confidential

## 数据中台运维看板接入

按负责人已确认的本地配套开发范围，整条任务成功或失败结束后，向独立 `cmc-platform-monitor` 发送一次更新提示。通知不报告“成功”，看板重新只读核对台账、日志和产物；通知失败不改变原任务结果。每天北京时间07:00由看板兜底检查。原定时、业务步骤和既有失败告警保持原语义。

systemd任务通过受管service中的 `OnSuccess` / `OnFailure` 调用观察单元；观察单元和发送助手的唯一维护位置是 `cmc-platform-monitor/deploy/linux/ops-notify-*.service` 与 `scripts/notify_completion.py`。协调发布时先安装对应观察单元及socket权限，再安装本仓service；不运行ETL做安装验证，不同时安装旧审阅drop-in。cron在原顶层入口使用EXIT处理，保存原退出码；不在子步骤重复通知。

接入代码已纳入仓库；代码同步不代表观察单元、socket权限或调度配置已经安装。真实通知、源读取权限和Linux运行仍须独立验收。详情及跨仓验证记录见 [监控接入与验收](../cmc-platform-monitor/docs/DEPLOYMENT.md)（仓库间路径按所在文档目录解析）。

本地验证：静态核对每日备份与隔离恢复验证单元均配置了完成通知；本次仅同步文档和lint技能说明，不修改任务命令、User或timer；未执行MDM数据库测试、备份、权限修改或部署。此变更不修改docs下Word派生文件。

## 审计日志人员展示调整（2026-10-12，已确认并实现）

需求来源：负责人要求将系统管理 → 审计日志（全局）中的「操作人」列改名为「工号」，紧邻新增「姓名」，便于识别操作人员。

改动前已核实：页面使用审计记录的 `username`；`audit.audit_log` 有 `user_id`、`username`，没有姓名快照；用户姓名由 `auth.user.full_name` 维护。原全局审计查询接口未返回姓名。

负责人已确认的实施范围及规则：

- 全局列表列顺序调整为「时间 / 工号 / 姓名 / 动作 / …」；原工号值原样保留，筛选框提示同步改为「工号」。特殊账号（如 `admin`）仍显示原账号值。
- 全局审计查询响应新增可空字段 `full_name`，按审计记录的 `user_id` 批量只读查询 `auth.user` 获取姓名；锁定、停用或软删除的账号仍按其 ID 匹配，不因账号状态隐藏历史日志。没有用户 ID、账号已不存在或姓名为空时，接口返回空值，页面显示「—」。
- 姓名表示用户资料中的当前姓名，属于阅读辅助信息；用户资料更名后展示会随之变化，不表示操作发生时的姓名快照。审计记录中的原工号、时间、动作和字段变更内容保持原值。
- 本次只调整截图中的全局审计页及其查询响应/前端类型；详情页通用审计面板、电子签名和 CSV 导出维持现有契约。保留 `audit:read` 权限及现有筛选、排序、分页；不增加用户管理权限要求、不增加人员库、不修改数据库结构或回填历史日志。

验收标准：有匹配账号的日志显示正确工号和姓名；无法匹配的日志保留并显示「—」；现有筛选、分页、展开和权限行为保持正确。

变更记录：2026-10-12 负责人确认上述方案后，修改全局审计查询服务、响应模型、前端类型与页面，补充账号状态、缺失资料及更名场景的回归用例。通过 `docker exec cmab-mdm-backend bash scripts/run_tests.sh tests/test_admin_audit.py -q` 在独立 `cmab_test` 库验证，19 项全部通过（含既有筛选、字段展开、CSV 和权限用例）；修改文件的后端 ruff、前端 ESLint 与前端 `pnpm type-check` 均通过。后端修改文件使用 `mypy --follow-imports=silent` 检查通过；常规 mypy 导入检查仍有未修改的 `app/core/config.py`（3 项）和 `app/core/db_release.py`（1 项）既有错误。使用本地门户在隔离浏览器中以模拟接口响应核对「工号 / 姓名」列顺序、中文姓名和缺失姓名显示，页面无运行错误；此检查不代表 Linux 真实账号验收。文档与代码已完成；未提交/push、未部署，未修改开发或 Linux 业务数据、审计表结构及历史记录。

发布安排：负责人随后授权提交/push 到 GitHub 并同步 Linux。提交前再次核对本地/GitHub/Linux 基线、Linux 干净工作区及发布工具；发布采用 `bash deploy/deploy.sh <完整SHA>`，含备份、前端构建、版本/字段/业务计数核验和服务恢复。此次没有新数据库迁移或业务数据回填；三端核对以完整 SHA、Linux 健康状态、实际提供的首页与构建文件一致性为准，发布过程和结果保存在 Linux `backups/releases/linux-*`，最终状态以该报告及发布后实测为准。

## 账号审计与物料批号复用（2026-10-13，设计已确认）

需求来源：负责人确认补齐账号审计，物料批号采用方案 B；先修改本地文档、代码并完成隔离测试，随后授权按项目流程备份、升级本地业务库并恢复服务验收。暂不提交、推送或部署到 Linux。

账号审计沿用应用层机制和已有 `audit.audit_log` / `audit.change_history`，覆盖创建用户、实际资料变更、管理员重置密码、用户自行改密，以及自定义角色创建、资料/权限修改和删除。既有角色分配、锁定/解锁记录保持单次操作一条日志，并补充字段明细；登录/登录失败和已有批量用户导入审计保持原有路径。写入使用字段白名单，记录操作者、目标、请求/IP 与真实前后值；密码、密码哈希、临时密码和令牌不得进入审计。业务与审计同事务，响应前提交；同一账号/角色的变更读取前值时加行锁。失败操作不留下成功变更记录；历史缺失日志不补造。复用现有审计查询、字段展开和 CSV，不新增审计表、权限或 API 必填参数。

物料批号方案 B：同一 `material_id` 下，仅 `deleted_at IS NULL` 的批次要求 `batch_number` 唯一。软删除后可同号新建或将其他批次改为该号，旧记录及其审计保留，新建使用新的 `batch_id`；未删除批次重号仍返回 HTTP 409 / 业务码 44001，不同物料可同号。新建/修改/删除批次以物料行锁串行化，同一物料的写操作短暂排队，其他物料并行。数据库通过本仓新 Alembic 迁移替换全表唯一约束为部分唯一索引，不删除、合并或回填业务记录。发生复用后，全表唯一约束的恢复必须先查历史重复；存在重复时拒绝降级，不自动清理历史。下游历史关联仍以 `batch_id` 区分记录，不能仅按物料和批号假定历史唯一。

验收：账号/角色各成功路径的审计、字段前后值、秘密信息排除、权限拒绝、事务失败回滚、现有登录/部门管理员回归；批次当前重号、软删除后重建/改号、不同物料同号、历史与审计保留、并发创建/改号，以及隔离库的迁移升级和降级阻断。数据库测试只经 `scripts/run_tests.sh` 在 `cmab_test` / 8001 / Redis db15 运行，不对开发业务库运行 pytest 或 seed；经负责人授权的本地业务库升级另走 `make migrate` 的备份、迁移和恢复流程。

实现状态（本地验收时）：设计已确认、代码已实现、完整隔离回归已通过；新增迁移为 `0063_mm_batch_partial_unique`，已在后续授权下应用到 Mac 本地业务库，服务恢复且本地验收通过。该时点代码仍是未提交工作区，Linux 未部署。后续发布授权和执行结果见本节末尾及发布报告。

回归中发现并独立复现登录成功返回前 refresh 台账尚未提交：另一连接立即查询新 jti 为 0，紧接换证偶发 401。沿用登录日志内容和认证规则，将 LOGIN 审计与 refresh 台账的同事务提交移至响应前；不通过延时或重试掩盖。新增跨连接即时可读用例；登录失败旁路持久化保持原实现。

验证记录：最终经 `docker exec -e TEST_DB=cmab_test cmab-mdm-backend bash scripts/run_tests.sh -q` 完整运行，**472 passed / 2 个既有依赖弃用警告**。新增 26 项回归覆盖审计成功/拒绝、10 类审计失败回滚、秘密排除、账号/角色并发前后值连续性、登录跨连接即时可读、批号复用与历史保留、并发创建/改号、无重复时迁移升降级保留样本、发生复用后的降级阻断。新增审计模块的 mypy 和账号审计/ORM/迁移/测试文件 Ruff 通过；`mm/services.py` 未改动的第 171 行仍有既有 C416（dict comprehension）提示，不在本次修复范围；`git diff --check` 通过。完整测试日志保存在本地 Git 忽略目录 `.tmp/20261013-account-audit-batch/full-tests.log`。

业务库保护复核（隔离开发阶段）：测试前后本地 `cmab_mdm` 都为 0062，用户 6、角色 26、物料 3770、批次 0、审计 10356，计数一致，原 `uq_material_batch` 全表唯一约束仍在；该阶段未对业务库执行迁移或写入。`cmab_test` 已验证为 0063 且有 `WHERE deleted_at IS NULL` 的部分唯一索引。

本地升级记录（2026-10-13，负责人后续授权）：执行 `make migrate` / `scripts/upgrade_local_db.sh`，明确目标为 Mac Docker `postgres:5432/cmab_mdm`，停后端、完整备份并校验后，通过 Alembic 从 0062 升到 0063，再核验版本/字段/计数、恢复后端。升级前后 **37 张表、114820 行的全部字段内容 SHA256 和行数完全一致**；物料 3770、设备 461、批次 0，历史审计 10356、字段明细 93548、电子签名 318 均保留。真实部分唯一索引有效，旧全表约束已替换，无业务数据删除、合并或回填。

备份可恢复性：升级前 dump 的 SHA256 为 `4e91b4909437f3a446d0f0fdd5fb00b61c546273ebc955f22873aa2a2e0f5068`，已在同一 PostgreSQL 镜像的临时容器实际恢复，关闭网络、无宿主端口或业务卷；37 张表全部内容与升级前相同，序列状态一致，恢复版本为备份时的 0062。验证容器已删除，未覆盖业务库。报告与备份位于 Git 忽略目录 [`backups/releases/mac-20261013T005741Z.n8Yo2S/`](./backups/releases/mac-20261013T005741Z.n8Yo2S/)。

本地服务验收：门户 `/mdm/` 首页及两个实际脚本资源 HTTP 200；健康接口 `healthy`、数据库 `ready`，当前/预期版本均为 0063，无就绪问题。通过真实本地门户完成一次管理员登录、立即续期、只读业务/账号/角色/审计/签名查询及登出，28 项核验通过；物料与设备各抽查 5 条详情，200 条审计的工号/姓名/字段明细与数据库一致，匿名业务与审计访问均为 401。验收后 34 张非会话变更表（审计按升级前已有记录范围比较）的全部字段和行数保持一致；历史登录与 refresh 会话也未改动，账号除正常登录时间外字段不变。仅新增正常 LOGIN/LOGOUT 两条审计（总数 10358）、一条成功登录历史及两条已经轮换/登出撤销的会话记录。真实业务库批次仍为 0，批号复用写入行为由隔离回归验证，未注入测试业务记录。该验收时点源码/文档未提交、未推送，Linux 未操作，`outputs/` 保留原状。

发布安排（2026-10-13，负责人后续授权）：提交并推送上述已验证修改到 GitHub，再在 Linux `/opt/cmab-mdm-platform` 拉取同一完整 SHA，执行 `bash deploy/deploy.sh <完整SHA>`，由脚本完成前端构建、停服务、完整备份、0062→0063 迁移和服务恢复。发布验收比较 Linux 升级前后全表行数与全部字段摘要，保留历史审计；核对 Mac/GitHub/Linux 完整 SHA、服务、数据库实际索引及门户提供的资源。此发布不 seed、回填或跨环境同步业务数据。最终执行结果、备份及实际版本以 Linux `backups/releases/linux-*` 报告和发布后实测为准；前述本地状态保留为阶段记录。

## 密码策略、管理员底线与主表编辑保护（2026-10-13，设计已确认）

需求来源：负责人确认三项方案，并将密码最低长度改为 **8 位**；只在本地修改文档/代码和完成隔离测试，暂不提交、推送或部署 Linux。本节是本批业务规则与验收范围的权威记录，不手改 Word 派生文档。

密码规则：新建账号和设置新密码时至少 8 位，包含大写、小写、数字及符号；密码有效期 90 天，不得复用最近 5 次密码（含当前密码）。读取既有 `meta.system_config` 的密码配置，迁移将最低长度改为 8；界面与后端统一口径。当前密码不批量重置、不追补未知旧密码；新增 `auth.password_history` 只保留不可还原的校验记录，迁移以当前已知密码作为基线，记录基线采集时间，不冒充历史改密时间。历史记录不进入 API、审计明细或日志。新建、批量导入、管理员重置和自行改密共用策略；超过密码校验算法支持的输入长度时明确拒绝，避免截断后把不同密码当成同一个。

密码过渡：普通密码到期后可以用正确旧密码进入改密闭环，业务接口拦截；临时密码仍为 7 天，超期需管理员重新发放。迁移只给原到期日为空的账号设置迁移日起 90 天；已过期日期不延长。登录、续期、当前用户资料及 MDM 业务入口使用同一到期判断，复用既有强制改密标记和跳转；普通通行证有效期不超过密码到期日，避免其他独立验签系统拿新发通行证继续业务。既有通行证至其原到期日仍可能在下游生效，后续发布须验证门户/各看板改密跳转，本地验证不冒充全公司上线验收。改密成功沿用撤销旧会话、重新登录；输入不合法/失败操作不误写账号或成功审计。此结构和账号过渡迁移不做自动 downgrade，以免删除密码历史或伪造还原日期；需要回退时单独评估备份与代码配套。

管理员底线：人工撤销角色或锁定账号前，始终保留至少一个 `status=active`、未删除且持 `SYS_ADMIN` 的用户；密码需要修改但仍能自行恢复的账号计入，部门管理员不计入。自身/他人使用同一保护，涉及管理员减少的操作先取得同一管理锁再读取目标和人数，避免两个管理员同时各自看到“还有另一人”而一起消失。自动连续输错锁定仍按原安全规则执行，不放宽；原有不能人工锁定自己的规则、部门范围和保护角色规则不变。被拒绝操作不写成功审计，成功操作复用现有账号审计。

编辑保护：本次覆盖 SRS/PRS/ARS 三个主编辑页及随主表单提交的内容，保留现有版本参数；保存前排队读取同一主记录的最新内容，再核对开页版本，成功响应前完成资料与审计提交。后来保存者即使修改不同字段也收到现有版本冲突提示，不自动合并。表单保留开页版本与输入，不因后台重新获取记录而偷偷采用新版本；冲突后可新开详情页对照，并经明确确认丢弃未保存输入后重新载入。各主表的状态机仍沿用已有加锁机制。

验收范围：8 位/不足 8 位、四类字符、重复最近 5 次及超过窗口后可复用；密码到期前后、临时密码超期、无到期日期过渡、旧会话失效、各密码写入口、历史与审计秘密排除、失败回滚；唯一/多个管理员、操作自己/他人、部门管理员、并发撤销/互锁、自动安全锁定；三域两连接同时保存、旧版本、状态变化、失败回滚及审计前后值连续；前端冲突保留输入与确认重新载入。数据库测试只通过 `scripts/run_tests.sh` 在 `cmab_test` / 8001 / Redis db15；不升级或写入 `cmab_mdm`；原 `outputs/` 保留。

实现记录（2026-10-13，仅本地）：新增 `0064_auth_password_policy` 迁移及密码历史校验，补齐新建/导入/重置/自行改密入口，登录和续期共用到期判断；新发 MDM 通行证携带改密时间，修复同一秒改密后旧通行证未失效的边界。新增管理员统一管理锁，人工锁定/撤销身份复用账号审计。三域普通更新持锁重读最新记录并在响应前提交；物质主表单只改蛋白子属性时也推进主版本，防止下一次旧版本保存覆盖。前端保存开页版本，后台查询、冲突、取消重载及重载失败都保留填写内容；成功确认重载才换成最新记录。变更不新增权限、外部依赖或下游仓库修改。

实际验证：最终完整隔离测试 **512 passed，2 项既有依赖弃用提示**，包括密码写入口、最近 5 次窗口、到期/临时密码闭环、迁移基线与审计、管理员并发减少、三域编辑排队、状态变化和失败回滚；新增批量导入测试使用独立连接，避免测试之间互相影响。前端类型检查、零告警 ESLint 和生产构建通过；浏览器使用独立测试登录态，所有 API 请求均拦截并模拟，三域后台刷新/冲突/取消重载/读取失败保留输入、确认重载换版并清空最新记录为空的字段，以及 7 位拒绝/8 位放行/字符要求/到期改密跳转均通过。该页面测试不写真实业务库，也不代表 Linux 或下游系统已验收。

代码检查范围：本次账号、密码、权限、迁移及相关测试主要文件 Ruff 通过，新密码策略和管理员保护模块 mypy 通过。三域编辑服务与基线脚本仍有 **9 项未改动代码的既有提示**（F821 6、C416 2、SIM108 1），未扩修；排除这些已核对的旧规则后，本次相关服务与脚本检查通过。`git diff --check` 通过；不将局部检查写成全仓库 lint/mypy 已通过。完整测试和浏览器报告保存在本地 Git 忽略目录 `.tmp/20261013-password-admin-edit/`。

真实业务库保护复核：全部测试完成后再次使用只读事务，比对测试前后的 **37 张表、114825 行，全部字段内容摘要、行数及序列状态完全一致**；物料 3770、设备 461、批次 0，审计 10358、字段明细 93548、电子签名 318 均保留，没有新增测试业务记录、删改审计或业务数据互拷。比对报告为 `.tmp/20261013-password-admin-edit/business-comparison.json`。

隔离开发阶段状态（升级前）：设计已确认、代码已实现、隔离测试已通过；只在 `cmab_test` 验证 0064。当时 Mac 真实业务库保持 0063，新增迁移尚未在业务库执行；本地后端按既有版本保护拒绝启动，日志为当前 `0063_mm_batch_partial_unique`、预期 `0064_auth_password_policy`，不能记为当时业务服务已恢复或新功能已上线。代码和文档未提交、未推送，Linux 未操作；Word 源文件及其派生文档未手工改动。随后获授权的本地升级结果如下。

本地升级记录（2026-10-13，负责人后续授权）：明确目标为 Mac Docker `postgres:5432/cmab_mdm`，停止后端后留存完整只读基线，调用项目备份脚本并在独立临时容器实际恢复验证；再执行 `make migrate` / `scripts/upgrade_local_db.sh`，由现有流程另留发布备份、通过 Alembic 将业务库从 0063 升至 **0064_auth_password_policy**、核对结构和计数、恢复后端。没有手工 SQL 绕过迁移、seed、跨环境同步或修改实际账号密码。

迁移数据验收：升级前为 37 张表、114825 行；升级后为 38 张表、114837 行。6 个账号各新增一条当前密码校验基线，哈希与现有密码逐一相符；只有原到期日为空的 2 个账号补为迁移日起 90 天，原有非空到期日保持原样。最低长度从 12 改为 8；这三项变更对应新增 **3 条迁移审计和 3 条字段明细**，逐条验证实体、字段与新旧值一致。除允许的账号到期日、该配置和审计新增外，其他 **33 张原有表的全部内容及行数一致**，账号其他字段及其他配置一致，无关序列保持原样；原 **10358 条审计、93548 条字段明细、318 条电子签名全部内容保留**，密码哈希未进入应用审计。

备份实际恢复验收：升级流程生成的发布备份 SHA256 为 `6bed17bd3ac2876d78467acd23ce91f6dda5a25f7ba95460f3001e8fbd5def3f`，已使用业务库同一 PostgreSQL 镜像、无网络/宿主端口/业务卷的临时容器实际恢复；37 张表完整内容摘要、行数、序列及备份时版本 0063 全部相符，验证容器已删除，没有覆盖业务库。升级前预验证备份也通过同样检查。正式备份及专项验收报告位于 Git 忽略目录 `backups/releases/mac-20261013T084100Z.jrpYe0/`。

本地服务验收：四个服务容器运行，PostgreSQL/Redis 健康；真实门户 `/mdm/` 及两项实际脚本资源 HTTP 200，后端 `healthy`、数据库 `ready`，当前/预期版本均为 0064，无就绪问题。真实登录/续期/只读业务和审计/登出的 API 验收 **28 项通过**，物料及设备各抽查 5 条详情，200 条审计的身份与字段明细同数据库一致，匿名业务/审计访问为 401；独立浏览器使用真实登录态的验收 **24 项通过**，物料/设备表、已有物质/资产编辑表单、审计页面及实际接口的 8 位密码要求均有效，项目当前 0 条如实显示，没有为验收录入假数据。普通编辑并发、管理员底线及真实密码变更的破坏性操作仍由前述隔离回归覆盖，未改动真实业务记录或账号身份来测试。

验收后完整性复核 **22 项通过**：38 张表共 114850 行，其中 34 张表在迁移完成后的内容和行数完全不变；账号除正常登录时间外字段保持不变，原登录历史、会话记录以及迁移前全部审计明细和签名保留。验收共完成 3 次正常登录/登出（一次 API 验收及两次页面验收尝试；首次页面等待定位重试，不是登录失败），追加 6 条 LOGIN/LOGOUT 审计、3 条成功登录历史和 4 条已轮换/登出撤销的会话；无失败登录、无测试业务记录。最终审计 **10367**、字段明细 **93551**、电子签名 **318**、物料 **3770**、设备 **461**、物料批次 **0**、密码历史基线 **6**。30 个本批变更源码文件的摘要保持一致，HEAD 仍为 `fbb8dc132b8a273c7b692c0a86baf70c8920d9a1`。

本地升级验收时点状态（发布前）：设计已确认、代码已实现、隔离测试已通过、本地业务库 0064 已升级、本地服务已恢复并验收；当时代码/文档未提交、未推送，Linux 未操作。原 `outputs/`、受控 Word 源文件及派生文档保持原样。

Linux 发布安排（2026-10-13，负责人后续授权）：将本批已验证源码、0064 迁移及文档一起提交并推送 GitHub；Linux `/opt/cmab-mdm-platform` 拉取同一完整 SHA 后执行 `bash deploy/deploy.sh <完整SHA>`，按既有流程备份、升级业务库到 0064、恢复服务和验收。发布前在 Linux 自身库留存全部字段/行数及历史审计基线，实际恢复验证升级前备份；分别核对密码基线、原空到期日过渡和迁移审计，保留所有原业务数据、旧密码值、原非空到期日和历史审计。运行验收仅追加正常登录/续期/登出记录，不录入测试业务、不跨环境复制业务数据。

本批发布的实际完整 SHA、迁移前后计数/摘要、备份 SHA256 和恢复验证、服务健康及所提供前端文件的核验结果，以 Linux `backups/releases/linux-*` 中的发布和专项验收报告为准；Mac/GitHub/Linux 三端完整 SHA 须一致，实际库版本均为 0064，服务和资源另行核验。上述本地记录是已完成的阶段证据，发布安排不预先写成 Linux 已成功；独立下游系统的其他功能仍按其自身验收范围确认。

Linux 页面验收发现及修复（2026-10-13）：直接打开资产详情/编辑页时，`/mdm/assets/<资产编号>` 与构建文件目录 `/mdm/assets/<文件名>.js` 共用前缀，既有 nginx 静态目录规则将业务页面误判为文件，返回 nginx 404；真实资产 API 返回 200，原数据不受影响。受管配置改为仅匹配构建文件的扩展名并去除 `/mdm/` 前缀后查找文件，资产页面走既有单页入口；文件仍长缓存，缺失脚本仍返回 404。该修复不改业务规则、API、权限或数据库结构，不新增迁移；先使用私有 Unix 套接字验证页面、缓存、实际脚本和缺失文件，再提交推送同一配置并备份/校验/恢复 nginx，重新验收三端版本。

Linux 首次发布实测（2026-10-13）：业务功能提交 `2ce91f3fe9d7a1bcc3369ba0e0fa2c846560b922` 已按部署脚本完成 0063→0064，后端/nginx 运行，实际库 `ready`，两个 MDM 端口仅监听本机。升级前 37 张表、54296 行；30 个账号各保留一条密码校验基线，仅 1 个原空到期日补 90 天，最低长度改为 8，对应 2 条迁移审计和 2 条字段明细。原 4933 条审计、38471 条字段明细、0 条电子签名全部字段保留，物料 3770、设备 2036、批次 0；31 张非账号/会话/配置/审计表的完整内容一致，账号及配置的其他字段、旧非空日期、原登录历史分别核对一致。恢复后已有用户正常登录和续期，原会话不可变字段及旧撤销记录保留，新会话与其前序续期或登录审计相符；不把在线用户活动误记为迁移写入。Linux 日期审计按实际时点核对，保留原时区表示。

Linux 备份及阶段验收：正式备份在 `backups/releases/linux-20261013T092059Z.72SFoG/`，dump SHA256 为 `86e8ce32af48c5c61f4609e354b4a7dcd41fffc879de93d84abf47b6e50637e5`；在无网络、无宿主端口/业务卷的独立临时容器实际恢复，37 张表的全部内容、行数、序列及原版本 0063 一致，验证容器已删除。迁移专项 15 项及真实接口验收 28 项通过；API 验收抽查物料/设备各 5 条、200 条审计身份和字段明细，匿名访问正确拒绝。补充的资产路由配置在私有 Unix 套接字上 5 项验证通过（资产详情、资产编辑、其他页面、实际脚本缓存、缺失脚本 404），临时 nginx 已停止。此后配置补充发布仅涉及受管 nginx 和本文档，Python/前端源码与已部署业务提交相同，不重复执行数据库迁移；当前三端最终 SHA、实际配置和完整浏览器复验结论保存在同一发布目录的专项报告中。
