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

每份 docx 旁都有同名 `.md` 派生副本（由 `make docs-extract` 自动生成，**不可手工修改**），方便程序读取与 grep。

**Phase 0 设计基准 V1.0**（已归档基线，保留作 V1.1 修订溯源）：
- [V1.0 docx × 4](./docs/) — 文件命名 `*_V1.0.docx`

**设计基准偏离说明**（DEV-MDM-001 系列，待 IT 架构组评审）：
- [V1.2_draft](./docs/CMAB_MDM_Portal_设计基准偏离说明_V1.2_draft.md) — 覆盖 Phase 1 / Phase 2 / Phase 2.5 + M3.0 回归 + M3.1-M3.4 ARS + 跨域引用 + 跨 4 文档检查（含附录 C 测试覆盖映射表）

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
| 部署 | Docker + Docker Compose |

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

# 5. 初始化数据库（首次运行必须）
docker compose -f deploy/docker-compose.dev.yml exec backend \
    alembic upgrade head
docker compose -f deploy/docker-compose.dev.yml exec backend \
    python -m app.scripts.seed_data

# 6. 访问
# 前端：       http://localhost:5173
# 后端 API：   http://localhost:8000
# API 文档：   http://localhost:8000/api/v1/docs
# 数据库：     localhost:5432 (用户/库见 .env)
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
make migrate     # 应用数据库迁移
make seed        # 加载种子数据
make reset-db    # 重置数据库（⚠️ 删除全部数据）
make test-be     # 运行后端测试
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
    │             → alembic upgrade head
    │
git push
    │
Linux 服务器
    │
    ├─ git pull
    ├─ docker compose up -d --build
    ├─ alembic upgrade head
    └─ 测试运行
```

## 部署

### 生产环境（Linux 虚拟机）

```bash
# 在生产服务器
cd /opt/cmab-mdm-platform
git pull origin main
cp .env.production .env

docker compose -f deploy/docker-compose.prod.yml down
docker compose -f deploy/docker-compose.prod.yml up -d --build

# 应用迁移（DBA 手动执行，不自动）
docker compose -f deploy/docker-compose.prod.yml exec backend \
    alembic upgrade head
```

详见 `docs/DEPLOY-MDM-001`（待编制）。

## License

Internal use only · CMAB Confidential
