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

**Phase 0 设计基准 V1.0**（IT 架构组已签批）：
- [CMAB_MDM_Portal_架构设计文档_V1.0.docx](./docs/CMAB_MDM_Portal_架构设计文档_V1.0.docx)（ARCH-MDM-001）
- [CMAB_MDM_Portal_数据模型设计文档_V1.0.docx](./docs/CMAB_MDM_Portal_数据模型设计文档_V1.0.docx)（DM-MDM-001）
- [CMAB_MDM_Portal_API接口规范_V1.0.docx](./docs/CMAB_MDM_Portal_API接口规范_V1.0.docx)（API-MDM-001）
- [CMAB_MDM_Portal_UI信息架构与线框图_V1.0.docx](./docs/CMAB_MDM_Portal_UI信息架构与线框图_V1.0.docx)（UI-MDM-001）

**设计基准偏离说明**（DEV-MDM-001 系列，待 IT 架构组评审）：
- [V1.1_draft](./docs/CMAB_MDM_Portal_设计基准偏离说明_V1.1_draft.md) — 覆盖 Phase 1 / Phase 2 / Phase 2.5 + M3.0 回归
- [V1.2_draft](./docs/CMAB_MDM_Portal_设计基准偏离说明_V1.2_draft.md) — 在 V1.1 基础上叠加 M3.1-M3.4 ARS + 跨域引用 + 跨 4 文档检查（含附录 C 测试覆盖映射表）

**V1.0 → V1.1 修订清单**（基于 V1.2 偏离决议，供评审组逐项决议接受/拒绝/修改，决议后秘书在 Word 修订模式落地）：
- [DM-MDM-001_修订清单](./docs/V1.1_修订清单/DM-MDM-001_修订清单.md)（12 项 · 9 接受 + 2 待决议 + 1 可选）
- [ARCH-MDM-001_修订清单](./docs/V1.1_修订清单/ARCH-MDM-001_修订清单.md)（11 项）
- [API-MDM-001_修订清单](./docs/V1.1_修订清单/API-MDM-001_修订清单.md)（19 项 · 含 errorType 字典补充与 5 个推迟端点路线图）
- [UI-MDM-001_修订清单](./docs/V1.1_修订清单/UI-MDM-001_修订清单.md)（14 项 · 含资产域整章新增与状态变更全局交互模式）

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
├── docs/                     # 设计文档：V1.0 基准（4 份 .docx）+ V1.1/V1.2 偏离说明 + V1.1 修订清单
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
