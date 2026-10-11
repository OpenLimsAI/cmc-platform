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
- [V1.3_draft](./docs/CMAB_MDM_Portal_设计基准偏离说明_V1.3_draft.md) — 历史偏离批次，明确封顶于 migration 0044；0045—0062 的现状以迁移文件、项目 `CLAUDE.md`、`SMP_NUM_alignment_status.md` 和靶点域决策记录为准
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
