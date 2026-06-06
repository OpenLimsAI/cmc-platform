**CMC LabOps Portal**

**总体架构设计文档**

*CMC Laboratory Operations Portal*

*Architecture Design Document*

| | |
|---|---|
| **文档编号** | ARCH-LABOPS-001 |
| **版本** | V1.4（修订历史见下表；文件名沿用 V1_0 不随版本改名） |
| **状态** | Draft |
| **发布日期** | 2026-05-19 |
| **编制** | CMC IT |
| **审核** | — |
| **批准** | — |
| **分类** | 内部技术文档 |

# 修订记录

| **版本** | **日期** | **修订人** | **修订内容** |
|---|---|---|---|
| V1.0 | 2026-05-19 | CMC IT | 初始版本 |
| V1.1 | 2026-06-04 | CMC IT | 认证方案变更：取消自建 labops_auth schema，改为对接 MDM Portal 统一认证（JWT 共享密钥）；用户管理/改密由 MDM Portal 承担 |
| V1.2 | 2026-06-04 | CMC IT | 主数据边界变更：设备主数据移交 MDM Portal 新建的 eqp 域（eqp.equipment，编码 EQP-yyyyXXXXXX）；LabOps equipment 表保留运营数据 + mdm_equipment_id/data_source 引用快照，照物料 from-mdm 模式按需拉取 |
| V1.3 | 2026-06-04 | CMC IT | 主数据入口治理（标准化决议）：本系统前端不再提供物料/设备主数据的本地新增与身份编辑入口——"物料管理"更名为只读"物料查询"，设备新增仅"从 MDM 引用 + 补运营字段"、编辑仅运营字段；各入口提供"去 MDM 登记"跳转（MDM 新建页 ?code=/?name= 预填，地址由 VITE_MDM_PORTAL_URL 配置）。同步机制明确为"用时拉取"：MDM 登记后无后台同步任务，首次入库/建档时实时拉取落快照。本地建档端点（POST /api/materials、POST /api/equipment）仅保留为后端 API 兜底，前端无入口。MDM 侧设计见 DM-MDM-001 V1.2 §10A、API-MDM-001 V1.2 §5.1.6A |
| V1.4 | 2026-06-06 | CMC IT | 适配 MDM eqp 域 V1.2（迁移 0040~0044）：设备快照承接三标识体系（equipment_no/fixed_asset_no）、5 值分类、工作站配置、额定功率等新增主数据字段；purchase_date/asset_value 归属改为 MDM 快照；新增手动快照刷新端点 sync-mdm 与 mdm_status/mdm_synced_at 追踪；新增批量引用建档端点 batch-from-mdm（台账初始化/增量同步）；修正 MDM_BASE_URL 开发默认值为 18000（§4.2 更新） |

## 适用范围

- 本文档为 CMC LabOps Portal 的总体架构设计
- 覆盖物料库存管理与仪器设备管理两大模块
- 定义系统边界、技术选型、部署架构与演进路线
- 作为数据模型、UI 设计、React 迁移方案的上位参考

# 1. 项目概述

## 1.1 背景

CMC 部门当前运行 cmc-labops v1.2 物料库存管理系统，基于 Streamlit + FastAPI + PostgreSQL 16 构建，运行于 material_mgmt schema 中。系统已实现物料导入、批次级入出库、移库、盘点、库存预警等完整闭环。

部门同时面临仪器设备管理的系统化需求。大量分析仪器和实验设备目前依靠 Excel 和纸质台账管理，缺少系统化的计量校验跟踪、维护记录管理、到期提醒等能力。

公司层面已启动 CMAB MDM Portal（主数据管理平台），采用 React 18 + TypeScript + Ant Design 5 前端和 FastAPI 后端，管理 Substance、Project、Asset、Material、Equipment（V1.2 起）五大主数据域。

## 1.2 系统定位与命名

**推荐名称：CMC LabOps Portal（CMC 部门运营平台）**

定位：面向 CMC 部门全体人员的日常运营管理门户，整合物料库存管理和仪器设备管理两大模块，提供统一入口、统一认证、统一权限、统一审计。

命名理由：
- "LabOps" 明确定位为实验室运营管理，区别于 MDM（主数据管理）
- 未来可扩展更多部门运营模块（如试剂配制管理、样品管理等），而非仅限于"物料"或"设备"
- 与 MDM Portal 名称体系一致（xxxxx Portal）

## 1.3 平台关系全景

```text
┌──────────────────────────────────────────────────────────────┐
│                    CMAB 企业 IT 全景                          │
│                                                              │
│   ┌────────────────────────┐   ┌────────────────────────┐    │
│   │  CMAB MDM Portal       │   │  CMC LabOps Portal     │    │
│   │  公司级主数据权威源    │   │  部门级运营管理工具    │    │
│   │                        │   │                        │    │
│   │  - Substance (SRS)     │   │  - 物料库存管理        │    │
│   │  - Project (PRS)       │   │  - 仪器设备管理        │    │
│   │  - Asset (ARS)         │   │  - 统一门户 / 预警     │    │
│   │  - Material (MM)       │   │                        │    │
│   │  - Equipment (EQP)     │   │  (主数据引用自 MDM)    │    │
│   │                        │   │                        │    │
│   │  React + FastAPI + PG  │   │  React + FastAPI + PG  │    │
│   └────────┬───────────────┘   └────────┬───────────────┘    │
│            │                            │                    │
│            └──────────┬─────────────────┘                    │
│                       │                                      │
│              ┌────────▼────────┐                             │
│              │  PostgreSQL 16  │                             │
│              │ (V1.2: 实际为两 │                             │
│              │  套独立实例,跨  │                             │
│              │  系统仅 API 引用)│                            │
│              │                 │                             │
│              │  MDM schemas:   │                             │
│              │   srs/prs/ars/  │                             │
│              │   mm/eqp/ref/   │                             │
│              │   audit/auth/   │                             │
│              │   meta          │                             │
│              │                 │                             │
│              │  LabOps schemas:│                             │
│              │   material_mgmt │                             │
│              │   equipment_mgmt│                             │
│              │  (认证复用 MDM   │                             │
│              │   auth schema)  │                             │
│              └─────────────────┘                             │
│                                                              │
│   ┌──────┐  ┌──────┐  ┌──────┐  ┌──────┐                    │
│   │ ELN  │  │ LIMS │  │ SAP  │  │ QMS  │                    │
│   └──────┘  └──────┘  └──────┘  └──────┘                    │
│   (未来集成方)                                               │
└──────────────────────────────────────────────────────────────┘
```

## 1.4 关键决策摘要

| **决策项** | **决策结果** | **决策依据** |
|---|---|---|
| 系统名称 | CMC LabOps Portal | 准确定位，可扩展 |
| 前端技术栈 | React 18 + TypeScript + Ant Design 5 | 与 MDM 保持一致，复用视觉规范和组件 |
| 后端技术栈 | FastAPI + SQLAlchemy 2.0 + Pydantic v2 | 保留现有后端，逐步模块化 |
| 数据库 | PostgreSQL 16（V1.2 修订：与 MDM 为两套独立实例，本系统内部按 schema 隔离） | 已有环境，运维成本最低；跨系统解耦 |
| 架构模式 | 多模块单体（物料 + 设备共享后端进程） | 规模适中，运维简单 |
| 认证方式 | **对接 MDM Portal 统一认证（V1.1 变更）**：登录代理 MDM `/auth/login`，后端用共享密钥本地校验 MDM 签发的 JWT；不再自建用户表 | 全公司统一账号，免去用户数据双向同步 |
| 部署目标 | Linux 虚拟机（与现有一致） | 复用现有基础设施 |
| 与 MDM 的关系 | 独立系统、独立 PG 实例（V1.2 修订）；统一认证（JWT）+ 主数据 API 引用 + UI 风格对齐 | 避免耦合，保持独立演进 |

# 2. 系统架构

## 2.1 系统上下文图

```text
                ┌─────────────────────────────┐
                │     CMC 部门用户            │
                │  研发人员 / 库管 / 设备管理 │
                └──────────────┬──────────────┘
                               │ Web 浏览器
                               ▼
            ┌─────────────────────────────────────────┐
            │        CMC LabOps Portal                │
            │                                         │
            │   物料库存管理 │ 仪器设备管理            │
            │   统一认证   │ 统一权限  │ 统一审计     │
            │   Dashboard  │ 预警中心  │ 报表导出     │
            └──────┬──────────────────┬───────────────┘
                   │                  │
                   ▼                  ▼
          ┌────────────────┐  ┌───────────────────┐
          │ PostgreSQL 16  │  │ CMAB MDM Portal   │
          │ (LabOps 专属   │  │ (统一认证 + 物料/ │
          │  实例)         │  │  设备主数据 API)  │
          └────────────────┘  └───────────────────┘
```

## 2.2 容器图

```text
┌───────────────────────────────────────────────────────────────────┐
│                    用户浏览器（Chrome / Edge）                     │
└────────────────────────────┬──────────────────────────────────────┘
                             │ HTTP(S)
                             ▼
┌───────────────────────────────────────────────────────────────────┐
│                    Nginx 反向代理（可选）                          │
│  - 静态资源服务  - 路由分发  - 限流                               │
└────────┬─────────────────────────────┬────────────────────────────┘
         │ /                           │ /api/*
         ▼                             ▼
┌──────────────────────┐     ┌────────────────────────────────────┐
│ Frontend             │     │ Backend API                        │
│  React 18 + TS       │     │  FastAPI + Uvicorn                 │
│  Ant Design 5        │     │  Python 3.11+                      │
│  Vite 构建产物       │     │                                    │
│  (静态资源)          │     │  ├─ material 物料模块              │
│                      │     │  │   (保留现有 routers)             │
│                      │     │  ├─ equipment 设备模块(新增)        │
│                      │     │  ├─ auth 认证模块                  │
│                      │     │  ├─ audit 审计模块                 │
│                      │     │  └─ shared 共享层                  │
└──────────────────────┘     └──┬─────────────────────────────────┘
                                │
                                ▼
                        ┌──────────────┐
                        │ PostgreSQL 16│
                        │              │
                        │ Schemas:     │
                        │  material_mgmt│ ← 现有，保留(含 audit_log)
                        │  equipment_mgmt│ ← 新增
                        │ (认证由 MDM   │
                        │  Portal 提供) │
                        └──────────────┘
```

## 2.3 后端模块结构

```text
backend/
├── main.py                     FastAPI 应用入口
├── database.py                 数据库连接配置
│
├── shared/                     共享层
│   ├── auth.py                 认证与密码处理
│   ├── audit.py                审计日志服务
│   ├── deps.py                 依赖注入（get_db, get_current_user）
│   └── permissions.py          RBAC 权限守卫
│
├── material/                   物料库存模块（从现有 routers 重组）
│   ├── models.py               ORM: material, batch, inventory_txn, location...
│   ├── schemas.py              Pydantic: 请求/响应模型
│   ├── crud.py                 数据访问层
│   └── router.py               API 路由（合并现有 7 个 router）
│
├── equipment/                  仪器设备模块（新增）
│   ├── models.py               ORM: equipment, calibration, maintenance...
│   ├── schemas.py              Pydantic: 请求/响应模型
│   ├── crud.py                 数据访问层
│   └── router.py               API 路由
│
├── admin/                      管理模块
│   ├── router.py               用户管理、角色管理
│   └── schemas.py
│
└── tests/
    ├── test_material/
    └── test_equipment/
```

后端重组原则：
- 不破坏现有 API 接口（路径、参数、响应格式不变）
- 物料模块代码从 routers/ 平级文件重组为 material/ 包，内部逻辑不变
- 设备模块新建 equipment/ 包
- 共享层从现有 auth.py / audit.py 提取，增加 RBAC 权限守卫

## 2.4 前端模块结构（React）

```text
frontend/
├── src/
│   ├── main.tsx                入口
│   ├── App.tsx                 路由配置
│   │
│   ├── api/                    API 调用层
│   │   ├── client.ts           Axios 实例 + 拦截器
│   │   ├── materials.ts        物料 API
│   │   ├── equipment.ts        设备 API
│   │   ├── auth.ts             认证 API
│   │   └── types.ts            API 类型定义
│   │
│   ├── stores/                 状态管理
│   │   └── authStore.ts        Zustand 认证状态
│   │
│   ├── shared/                 共享组件（参考 MDM）
│   │   ├── layouts/
│   │   │   ├── MainLayout.tsx  主布局（Header + Sidebar + Content）
│   │   │   ├── Header.tsx      顶栏
│   │   │   └── Sidebar.tsx     侧边导航
│   │   └── components/
│   │       ├── StatusBadge.tsx  状态标签
│   │       ├── PermissionGuard.tsx  权限守卫
│   │       └── AuditLogPanel.tsx    审计面板
│   │
│   ├── modules/
│   │   ├── material/           物料模块
│   │   │   ├── MaterialList.tsx
│   │   │   ├── MaterialDetail.tsx
│   │   │   ├── IntakeForm.tsx
│   │   │   ├── OutgoingForm.tsx
│   │   │   └── ...
│   │   │
│   │   ├── equipment/          设备模块
│   │   │   ├── EquipmentList.tsx
│   │   │   ├── EquipmentDetail.tsx
│   │   │   ├── CalibrationTab.tsx
│   │   │   └── ...
│   │   │
│   │   ├── dashboard/          仪表盘
│   │   │   └── Dashboard.tsx
│   │   │
│   │   └── admin/              管理模块
│   │       ├── UserManagement.tsx
│   │       └── AuditLogPage.tsx
│   │
│   └── routes/
│       └── ProtectedRoute.tsx  路由权限守卫
│
├── package.json
├── vite.config.ts
└── tsconfig.json
```

# 3. 技术栈选型

## 3.1 技术栈总览

| **层** | **技术** | **版本** | **选型理由** |
|---|---|---|---|
| 前端框架 | React + TypeScript | 18 / 5.x | 与 MDM 一致，工业级生态 |
| 前端构建 | Vite | 5.x | 现代化构建，开发体验好 |
| UI 组件库 | Ant Design | 5.x | 与 MDM 一致，企业级中文友好 |
| 前端状态 | Zustand + TanStack Query | — | 轻量，服务端状态分离 |
| 前端表格 | Ant Design Table | — | 内置排序、筛选、分页 |
| 后端框架 | FastAPI | 0.115+ | 保留现有，性能优秀 |
| 后端 ORM | SQLAlchemy 2.0 | 2.0+ | 保留现有 |
| 数据校验 | Pydantic v2 | 2.x | 保留现有 |
| 认证 | bcrypt + token | — | 保留现有，渐进升级 |
| 数据库 | PostgreSQL | 16 | 本系统专属实例（与 MDM 实例独立，V1.2 修订） |
| 部署 | Linux VM + systemd | — | 保留现有部署模式 |
| 反向代理 | Nginx（可选） | — | 生产环境建议加入 |

## 3.2 与 MDM 的技术对齐

| **维度** | **MDM Portal** | **LabOps Portal** | **对齐程度** |
|---|---|---|---|
| 前端框架 | React 18 + TS + Vite | React 18 + TS + Vite | 完全一致 |
| UI 组件库 | Ant Design 5 | Ant Design 5 | 完全一致 |
| 状态管理 | Zustand + React Query | Zustand + TanStack Query | 完全一致 |
| 后端框架 | FastAPI + SQLAlchemy 2.0 | FastAPI + SQLAlchemy 2.0 | 完全一致 |
| 数据库 | PostgreSQL 16 | PostgreSQL 16（独立实例，V1.2 修订） | 版本一致、实例独立 |
| 认证 | JWT + RBAC | token + RBAC（渐进升级） | 部分对齐 |
| 审计 | Part 11 合规级 | 部门操作级 | 精简版 |
| 布局风格 | Header + Sidebar + Content | Header + Sidebar + Content | 完全一致 |
| 组件风格 | 表格 + 详情 Tab + 状态 Tag | 表格 + 详情 Tab + 状态 Tag | 完全一致 |

# 4. 数据架构

## 4.1 Schema 划分

LabOps Portal 在同一 PostgreSQL 实例中使用独立 schema：

| **Schema** | **用途** | **来源** | **主要表** |
|---|---|---|---|
| material_mgmt | 物料库存 + 审计 | 现有，保留 | material, batch, inventory_txn, location, unit_dict, category_dict, import_log, audit_log |
| equipment_mgmt | 仪器设备 | 新增 | equipment, calibration, maintenance, repair, warranty, attachment, reminder |
| ~~labops_auth~~ | ~~认证与权限~~ | **已取消（V1.1）** | 认证由 MDM Portal 的 auth schema 提供，LabOps 不建用户/角色表 |
| labops_audit | 审计日志 | 规划中（Phase 4 可选） | 当前沿用 material_mgmt.audit_log；如需 module/reason 字段再升级 |

> Schema 隔离原则（V1.1 修订）
> - material_mgmt 保留现有表不动，保证现有 Streamlit 前端在迁移期间继续工作
> - equipment_mgmt 为新建 schema
> - **认证不再建本地 schema**：LabOps 信任 MDM Portal 签发的 JWT（HS256 共享密钥），用户/角色主数据在 MDM 的 auth schema 中维护
> - material_mgmt 中历史遗留的 app_user / auth_session 表已停用，可在确认无引用后删除
> - 审计当前仍写 material_mgmt.audit_log（username 冗余快照，不依赖本地用户表）

## 4.2 数据流向

```text
数据所有权（V1.4 修订,对齐 MDM eqp 域 V1.2）：

  CMAB MDM Portal              CMC LabOps Portal
  ─────────────                ──────────────────
  Substance 身份               物料运营快照(material_mgmt.material,
  Project / Asset 登记           data_source 标记 mdm/local)
  物料主数据 mm.material  ──→   批次、出入库流水、位置、库存计算
  设备主数据 eqp.equipment ──→  设备运营台账(equipment_mgmt.equipment,
   三标识:equipment_code/        mdm_equipment_id + data_source
   equipment_no/fixed_asset_no   + 身份字段快照 + mdm_status/mdm_synced_at)
   5 值分类、工作站配置、       校验、维护、维修、保修、附件、提醒
   购入日期、资产价值、
   active/retired

数据引用方向（均通过 API 按需拉取,不跨库外键 —— 两套 PG 实例独立）：
  - 物料：入库时按 material_code 查 MDM,本地落快照(已实现)
  - 设备：建台账时按 equipment_code 查 MDM,身份字段以 MDM 为准,
          运营字段(状态/位置/负责人)本地维护(已实现)
  - 设备快照刷新(V1.4)：详情页"从 MDM 刷新"→ POST /api/equipment/{id}/sync-mdm,
    整体覆盖快照字段并更新 mdm_synced_at;MDM 侧 retire 仅置 mdm_status,
    不联动本地运营状态,前端提示人工处置
  - 设备批量引用建档(V1.4)：列表页"从 MDM 批量同步"→ POST /api/equipment/batch-from-mdm,
    台账初始化用:遍历 MDM 设备列表,本地不存在的逐台建档(运营字段留空待补),
    默认跳过已存在与 MDM 已退役,可按分类过滤;后续 MDM 新登记可重复执行增量同步
  - 本地建档(data_source='local')仅保留为后端 API 兜底(V1.3 起前端无入口),
    使用后须在 MDM 补登;补登后 sync-mdm 可回挂(回填 mdm_equipment_id
    并转 data_source='mdm')
  - 同步机制 = 用时拉取 + 手动刷新:MDM 登记后无后台同步任务
  - MDM 后端地址由 MDM_BASE_URL 配置,开发环境默认 127.0.0.1:18000/api/v1
```

# 5. 统一能力设计

## 5.1 统一认证（V1.1 已落地：对接 MDM）

LabOps 不自建用户体系，复用 MDM Portal 统一认证：

| **环节** | **实现** | **说明** |
|---|---|---|
| 登录 | POST /api/auth/login 代理 MDM `/auth/login` | 返回 MDM 签发的 JWT access token |
| 校验 | 后端用共享密钥（MDM_SECRET_KEY, HS256）本地解码 JWT | 无需每请求回调 MDM，零额外延迟 |
| 登出 | JWT 无状态，客户端丢弃 token | 服务端无 session 表 |
| 用户管理 / 改密 / 首登强制改密 | 由 MDM Portal 承担 | LabOps 不提供相关页面 |
| 会话过期 | 由 MDM token 有效期控制 | 过期后 401 → 前端跳转登录 |

## 5.2 统一权限（V1.1 修订：角色随 JWT 下发）

角色主数据在 MDM 维护，随 JWT 的 roles claim 下发；LabOps 后端按角色做模块级守卫：

```text
MDM User ──→ MDM Role ──(JWT roles claim)──→ LabOps 权限守卫

角色映射（MDM role_code → LabOps 权限）：
  - SYS_ADMIN           : 全权限（含审计查询）→ require_admin
  - CMC_WAREHOUSE_ADMIN : 物料模块写权限（入出库/移库/盘点/导入）→ require_warehouse
  - CMC_EQUIPMENT_ADMIN : 设备模块写权限（台账/校验/维护/维修）→ require_equipment
  - 其他登录用户         : 只读（库存/预警/物料/设备查询）

权限粒度：
  - 模块级守卫在后端 router dependency 实现
  - 前端按 roles 隐藏无权限菜单（FR-PLT-003）
  - 操作级细粒度 RBAC（permission 表）暂不建设，按角色硬映射够用
```

## 5.3 统一审计

从现有 audit_log 升级，增加：
- 模块字段（material / equipment / auth / admin）
- 变更原因字段（reason）
- 更规范的 action 命名

审计数据保留 ≥ 3 年，管理员可查询、可导出。

# 6. 部署架构

## 6.1 部署拓扑

```text
┌────────────────────────────────────────────────────────────────┐
│           公司内网 Linux 虚拟机                                 │
│                                                                │
│   ┌──────────────────────────────────────────────────────┐     │
│   │                                                      │     │
│   │   ┌────────────────┐  ┌────────────────────────┐     │     │
│   │   │ Nginx (可选)   │  │ React 静态资源         │     │     │
│   │   │ :80            │  │ (由 Nginx 或独立服务)  │     │     │
│   │   └────────┬───────┘  └────────────────────────┘     │     │
│   │            │ /api/*                                  │     │
│   │            ▼                                         │     │
│   │   ┌────────────────────────┐                         │     │
│   │   │ FastAPI Backend        │                         │     │
│   │   │ :8000                  │                         │     │
│   │   │ material + equipment   │                         │     │
│   │   └────────┬───────────────┘                         │     │
│   │            │                                         │     │
│   │   ┌────────▼───────────────┐                         │     │
│   │   │ PostgreSQL 16          │                         │     │
│   │   │ :5432                  │                         │     │
│   │   │ material_mgmt          │                         │     │
│   │   │ equipment_mgmt         │                         │     │
│   │   │ (认证复用 MDM auth)    │                         │     │
│   │   └────────────────────────┘                         │     │
│   │                                                      │     │
│   │   迁移期间 Streamlit 仍在运行:                       │     │
│   │   ┌────────────────────────┐                         │     │
│   │   │ Streamlit Frontend     │                         │     │
│   │   │ :8501 (旧前端)         │                         │     │
│   │   └────────────────────────┘                         │     │
│   │                                                      │     │
│   └──────────────────────────────────────────────────────┘     │
└────────────────────────────────────────────────────────────────┘
```

## 6.2 迁移期间双前端共存

迁移期间 Streamlit 和 React 前端并行运行，共享同一后端和数据库：

| **前端** | **端口** | **状态** | **说明** |
|---|---|---|---|
| Streamlit（旧） | 8501 | 运行中 → 逐步退役 | 现有用户继续使用 |
| React（新） | 80 或 3000 | 逐步上线 | 新页面优先在 React 实现 |
| FastAPI（共享） | 8000 | 持续运行 | 两个前端调用同一后端 |

# 7. 实施路线图

## 7.1 总体节奏

| **Phase** | **时间** | **主要交付** |
|---|---|---|
| Phase 0: 设计与规划 | 第 1-2 周 | 本文档 + 数据模型 + UI 线框 + 迁移方案 |
| Phase 1: React 脚手架 + 核心页面 | 第 3-6 周 | React 项目初始化、登录页、布局、物料查询/入库/出库 |
| Phase 2: 物料模块完整迁移 | 第 7-10 周 | 物料管理、导入、盘点、移库、预警全部迁移到 React |
| Phase 3: 设备管理模块 | 第 11-16 周 | 设备表设计、后端 API、React 前端（台账+校验+维护+维修+附件） |
| Phase 4: 统一门户 + 收尾 | 第 17-20 周 | Dashboard、预警中心、RBAC 升级、Streamlit 退役 |

## 7.2 风险与应对

| **风险** | **影响** | **应对** |
|---|---|---|
| React 迁移期间新旧前端不一致 | 中 | 共享同一后端 API，数据始终一致 |
| 前端开发资源不足 | 高 | AI 辅助 + 参考 MDM 现有组件 |
| 设备管理需求不明确 | 中 | Phase 0 充分调研，分步交付 |
| 数据库 schema 迁移复杂 | 低 | 新 schema 独立建表，不改现有表 |
| 用户习惯迁移阻力 | 中 | 保持 Streamlit 可用直到 React 功能覆盖 |

# 8. 附录

## 8.1 关键缩略语

| **缩略语** | **全称** |
|---|---|
| LabOps | Laboratory Operations |
| MDM | Master Data Management |
| RBAC | Role-Based Access Control |
| SRS | Substance Registration System |
| PRS | Project Registration System |
| ARS | Asset Registration System |
| MM | Material Master |

## 8.2 后续文档清单

| **文档编号** | **文档名称** | **状态** |
|---|---|---|
| URD-LABOPS-001 | 用户需求文档 | V1.0 Draft |
| DM-LABOPS-001 | 数据模型设计文档 | V1.0 Draft |
| UI-LABOPS-001 | UI 信息架构与线框图 | V1.0 Draft |
| MIG-LABOPS-001 | React 前端迁移方案 | V1.0 Draft |
