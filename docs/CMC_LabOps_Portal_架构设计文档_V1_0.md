**CMC LabOps Portal**

**总体架构设计文档**

*CMC Laboratory Operations Portal*

*Architecture Design Document*

| | |
|---|---|
| **文档编号** | ARCH-LABOPS-001 |
| **版本** | V1.0 |
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

## 适用范围

- 本文档为 CMC LabOps Portal 的总体架构设计
- 覆盖物料库存管理与仪器设备管理两大模块
- 定义系统边界、技术选型、部署架构与演进路线
- 作为数据模型、UI 设计、React 迁移方案的上位参考

# 1. 项目概述

## 1.1 背景

CMC 部门当前运行 cmc-inventory v1.2 物料库存管理系统，基于 Streamlit + FastAPI + PostgreSQL 16 构建，运行于 material_mgmt schema 中。系统已实现物料导入、批次级入出库、移库、盘点、库存预警等完整闭环。

部门同时面临仪器设备管理的系统化需求。大量分析仪器和实验设备目前依靠 Excel 和纸质台账管理，缺少系统化的计量校验跟踪、维护记录管理、到期提醒等能力。

公司层面已启动 CMAB MDM Portal（主数据管理平台），采用 React 18 + TypeScript + Ant Design 5 前端和 FastAPI 后端，管理 Substance、Project、Asset、Material 四大主数据域。

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
│   │  - Material (MM Lite)  │   │                        │    │
│   │                        │   │                        │    │
│   │  React + FastAPI + PG  │   │  React + FastAPI + PG  │    │
│   └────────┬───────────────┘   └────────┬───────────────┘    │
│            │                            │                    │
│            └──────────┬─────────────────┘                    │
│                       │                                      │
│              ┌────────▼────────┐                             │
│              │  PostgreSQL 16  │                             │
│              │  (共享实例)     │                             │
│              │                 │                             │
│              │  MDM schemas:   │                             │
│              │   srs/prs/ars/  │                             │
│              │   mm/ref/audit/ │                             │
│              │   auth/meta     │                             │
│              │                 │                             │
│              │  LabOps schemas:│                             │
│              │   material_mgmt │                             │
│              │   equipment_mgmt│                             │
│              │   labops_auth   │                             │
│              │   labops_audit  │                             │
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
| 数据库 | PostgreSQL 16（共享实例，schema 隔离） | 已有环境，运维成本最低 |
| 架构模式 | 多模块单体（物料 + 设备共享后端进程） | 规模适中，运维简单 |
| 认证方式 | 自建用户表 + token（现有），未来可接 SSO | 渐进式升级 |
| 部署目标 | Linux 虚拟机（与现有一致） | 复用现有基础设施 |
| 与 MDM 的关系 | 独立系统，共享 PG 实例，UI 风格对齐 | 避免耦合，保持独立演进 |

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
          │ 共享实例       │  │ (未来 API 引用)   │
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
                        │  material_mgmt│ ← 现有，保留
                        │  equipment_mgmt│ ← 新增
                        │  labops_auth │ ← 升级认证
                        │  labops_audit│ ← 升级审计
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
| 数据库 | PostgreSQL | 16 | 保留现有共享实例 |
| 部署 | Linux VM + systemd | — | 保留现有部署模式 |
| 反向代理 | Nginx（可选） | — | 生产环境建议加入 |

## 3.2 与 MDM 的技术对齐

| **维度** | **MDM Portal** | **LabOps Portal** | **对齐程度** |
|---|---|---|---|
| 前端框架 | React 18 + TS + Vite | React 18 + TS + Vite | 完全一致 |
| UI 组件库 | Ant Design 5 | Ant Design 5 | 完全一致 |
| 状态管理 | Zustand + React Query | Zustand + TanStack Query | 完全一致 |
| 后端框架 | FastAPI + SQLAlchemy 2.0 | FastAPI + SQLAlchemy 2.0 | 完全一致 |
| 数据库 | PostgreSQL 16 | PostgreSQL 16（同实例） | 完全一致 |
| 认证 | JWT + RBAC | token + RBAC（渐进升级） | 部分对齐 |
| 审计 | Part 11 合规级 | 部门操作级 | 精简版 |
| 布局风格 | Header + Sidebar + Content | Header + Sidebar + Content | 完全一致 |
| 组件风格 | 表格 + 详情 Tab + 状态 Tag | 表格 + 详情 Tab + 状态 Tag | 完全一致 |

# 4. 数据架构

## 4.1 Schema 划分

LabOps Portal 在同一 PostgreSQL 实例中使用独立 schema：

| **Schema** | **用途** | **来源** | **主要表** |
|---|---|---|---|
| material_mgmt | 物料库存 | 现有，保留 | material, batch, inventory_txn, location, unit_dict, category_dict, import_log |
| equipment_mgmt | 仪器设备 | 新增 | equipment, calibration, maintenance, repair, warranty, attachment, reminder |
| labops_auth | 认证与权限 | 从 material_mgmt 升级 | user, role, permission, user_role, role_permission, session |
| labops_audit | 审计日志 | 从 material_mgmt 升级 | audit_log（升级版） |

> Schema 隔离原则
> - material_mgmt 保留现有表不动，保证现有 Streamlit 前端在迁移期间继续工作
> - equipment_mgmt 为新建 schema
> - labops_auth 从 material_mgmt.app_user / auth_session 升级，增加 RBAC
> - labops_audit 从 material_mgmt.audit_log 升级
> - 迁移期间 material_mgmt 中的 app_user / auth_session / audit_log 保留，React 前端切换完成后再考虑废弃

## 4.2 数据流向

```text
数据所有权：

  CMAB MDM Portal          CMC LabOps Portal
  ─────────────            ──────────────────
  Substance 身份 ←──(API)──→  物料主数据
  Project 登记              (material_mgmt)
  Asset 登记                
  Material 主数据(R&D)       批次、出入库流水
                            位置、库存计算
                            
                            设备台账
                            (equipment_mgmt)
                            校验、维护、维修
                            保修、附件、提醒

数据引用方向：
  - 当前阶段：两系统独立，无跨系统引用
  - 未来阶段：LabOps 物料可引用 MDM substance_id（可选）
  - 设备数据完全在 LabOps 内部，不与 MDM 交互
```

# 5. 统一能力设计

## 5.1 统一认证

现有认证（token + bcrypt）在迁移期间保留，逐步升级：

| **阶段** | **认证方式** | **说明** |
|---|---|---|
| 当前（Streamlit） | 随机 hex token + 10 分钟滑动过期 | 保留不动 |
| Phase 1（React） | 同上，API 不变 | React 调用相同 /api/auth/* |
| Phase 2 | JWT access token + 长效 refresh token | 前后端分离更适合 JWT |
| Phase 3（可选） | 对接公司 AD / SSO | 需公司 IT 基础设施就绪 |

## 5.2 统一权限（RBAC 升级）

从现有 3 角色硬编码升级为 RBAC 模型：

```text
User ──→ Role ──→ Permission

预设角色：
  - sys_admin      : 系统管理员，全权限
  - warehouse_admin : 库管员，物料模块全权限
  - equipment_admin : 设备管理员，设备模块全权限
  - user           : 普通用户，只读 + 基本出入库

权限粒度：
  - 模块级：material:access / equipment:access
  - 操作级：material:create / material:update / equipment:calibrate
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
│   │   │ labops_auth            │                         │     │
│   │   │ labops_audit           │                         │     │
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
