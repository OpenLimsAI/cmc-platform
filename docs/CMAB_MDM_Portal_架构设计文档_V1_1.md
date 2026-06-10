<!--
  本文件由 scripts/docs/extract_md.py 从 docx 自动派生，请勿手工修改。
  源文件:CMAB_MDM_Portal_架构设计文档_V1_1.docx
  重新生成:make docs-extract
  一致性校验:make docs-check
-->

**CMAB MDM Portal**

**总体架构设计文档**

*Master Data Management Platform*

*Architecture Design Document*

|              |               |
|--------------|---------------|
| **文档编号** | ARCH-MDM-001  |
| **版本**     | V1.1          |
| **状态**     | Draft         |
| **发布日期** | 2026-05-11    |
| **编制**     | CMC IT 架构组 |
| **审核**     | —             |
| **批准**     | —             |
| **分类**     | 内部技术文档  |

# 修订记录

本文档遵循版本化管理，所有修订记录如下表：

| **版本** | **日期** | **修订人** | **修订内容** |
|----|----|----|----|
| V1.0 | 2026-05-11 | CMC IT 架构组 | 初始版本，定义平台总体架构、技术栈选型、域分治模型与分阶段实施路线 |
| V1.1 | 2026-05-12 | CMC IT 架构组 | V1.0→V1.1：11 项修订（§4.3 service commit / §6.5 bypass session+parent_ref / §7.1 \`meta.error.type\`+iat 精度 / §7.2.1 失败计数+JWT 黑名单 / §7.2.2 权限组合+GUC 禁用 / §7.4 备份状态 / §10.6 路线图） |
| V1.2 | 2026-06-04 | CMC IT | 新增 EQP 设备主数据域（第五个业务域）：eqp.equipment 为全公司仪器设备身份注册表，定位为下游 CMC LabOps Portal（部门运营系统）设备模块的数据上游；LabOps 同期将物料/设备主数据维护入口统一收敛到本系统（其前端仅保留"去 MDM 登记"跳转，/materials/new 与 /equipments/new 支持 ?code=/?name= 预填）。 |

## 适用范围

- 本文档适用于 CMAB MDM Portal 的总体架构设计、技术选型与实施规划

- 覆盖 Substance Registration（SRS）、Project Registration（PRS）、Asset Registration（ARS）、Material Master（MM）、Equipment Master（EQP，V1.2 新增）五大主数据域

- 作为后续详细设计文档（数据模型、API 规范、UI 设计）的上位参考

- 作为 Computer System Validation（CSV）的输入文档之一

# 1. 项目概述

## 1.1 背景

CMAB 公司是一家专注于单抗、双抗、融合蛋白与 ADC 的生物制药企业，目前拥有 3 款商业化产品和 4–5 个并行在研管线。随着公司从 NMPA/CDE 体系向 FDA/EMA 法规体系转型，研发与生产规模持续扩大，研发团队达 49 人，跨 CMC、QA、生产、注册多个部门。

当前公司在主数据管理上面临以下核心问题：

- Substance（物质 / 分子）信息分散在 Excel、ELN、各类项目文档中，缺少全公司唯一权威源

- 项目编号、资产编号缺少标准化登记机制，跨部门引用混乱

- 内部代号、INN、CAS、UNII 等内外部标识符之间缺少统一映射

- ADC 等复合物质的「父—子 substance」血缘关系无法系统化追踪

- 现有系统不满足 21 CFR Part 11 与 EU GMP Annex 11 的电子记录与审计追踪要求

- CMC R&D 资产的编码体系（SMP-RD-NUM-001 V2.1）已制定但未落地为信息系统

## 1.2 目标

CMAB MDM Portal 项目旨在建设一套企业级主数据管理平台，实现以下目标：

### 1.2.1 业务目标

- 建立 Substance、Project、Asset、Material、Equipment（V1.2 新增）五大核心主数据域的唯一权威源

- 落地 SMP-RD-NUM-001 V2.1 中的四层编码架构（Substance / Asset / Project / Study）

- 支持研发全生命周期主数据管理：从早期分子立项到上市产品维护

- 为转型 FDA/EMA 法规体系提供 IDMP-aligned 的 substance 数据基础

- 为后续 ELN、LIMS、SAP、QMS 等系统集成提供统一主数据接口

### 1.2.2 技术目标

- 采用前后端分离的工业级架构，前端 React + 后端 FastAPI + PostgreSQL 16

- 域分治后端 + 统一前端门户，单点登录，统一审计

- API-First 设计，OpenAPI 3.0 标准化，便于下游系统集成

- 从第一天起内置 21 CFR Part 11 / Annex 11 合规能力

- 可水平扩展、可平滑接入商业 MDM 与 ERP 系统

### 1.2.3 组织目标

- 建立 Data Owner / Data Steward / Data Custodian 三层数据治理角色

- 形成跨 CMC、QA、生产、IT、注册的主数据治理委员会

- 沉淀主数据管理 SOP 与制度，纳入 DQS 体系

## 1.3 范围

### 1.3.1 本期范围（In-Scope）

| **域**                 | **缩写** | **建设范围**       | **覆盖模态**             |
|------------------------|----------|--------------------|--------------------------|
| Substance Registration | SRS      | 完整建设           | mAb（第一版优先）        |
| Project Registration   | PRS      | 完整建设           | 全部研发项目类型         |
| Asset Registration     | ARS      | 完整建设           | 已商业化产品 + 在研管线  |
| Material Master        | MM       | 全公司物料身份注册 | 试剂、耗材、标准品、色谱柱 |
| Equipment Master       | EQP      | 全公司仪器设备身份注册（V1.2 新增） | 仪器设备                 |
| Cross-Reference Layer  | REF      | 完整建设           | 跨域引用关系管理         |
| Audit & Compliance     | AUDIT    | 完整建设           | Part 11 / Annex 11 合规  |

### 1.3.2 本期范围外（Out-of-Scope）

- GMP 物料主数据（保留在现有商业系统，未来由 SAP / 商业 ERP 接管）

- 设备主数据：V1.1 原列范围外（拟纳入 CMMS 或独立 Equipment Master）；V1.2 起已纳入本系统作为第五业务域 EQP，见修订记录与 §1.3.1

- 供应商主数据（未来纳入 ERP / SRM）

- 人员主数据（保留在 HR 系统）

- 文档管理（DMS）、电子实验记录（ELN）、实验室信息系统（LIMS）：作为下游集成方

- eCTD 提交自动化、IDMP 完整对齐：作为本期之后的扩展项

- AI 辅助 sameness 判定、复杂 fuzzy matching：本期采用规则化简化版

## 1.4 关键决策摘要

| **决策项** | **决策结果** | **决策依据** |
|----|----|----|
| 前端技术栈 | React 18 + TypeScript + Ant Design 5 | 工业级 UI、长期可维护、团队招聘容易 |
| 后端技术栈 | FastAPI + SQLAlchemy 2.0 + Pydantic v2 | Python 生态契合团队、自动 OpenAPI、性能优秀 |
| 数据库 | PostgreSQL 16（已部署） | 已有环境、JSONB 适合异构 substance 结构 |
| 架构模式 | Modular Monolith（域分治单体） | 规模适中、运维简单、可演进至微服务 |
| 第一版优先模态 | 仅 mAb | MVP 最快可达、覆盖现有核心业务 |
| 认证方式 | 系统自建用户表 + JWT | PoC 阶段最简、未来可平滑切换 LDAP/SSO |
| 部署目标 | Linux 虚拟机（公司现有） | 与现有 cmc_data_platform 部署模式一致 |
| 代码仓库 | cmab-mdm-platform（Monorepo） | 前后端一起管理、便于 CI/CD |
| 对外名称 | CMAB MDM Portal | 对应业务定位与品牌 |

# 2. 关键概念与术语

## 2.1 主数据相关术语

| **术语** | **英文** | **定义** |
|----|----|----|
| 主数据 | Master Data | 在企业范围内被多个业务流程共享、相对稳定、需要统一治理的核心业务实体数据 |
| 主数据管理 | MDM | 对主数据的唯一性、一致性、权威性进行系统化治理的体系 |
| 物质 | Substance | 概念意义上的「分子」，具有唯一身份，区别于具体批次产物 |
| 资产 | Asset | 公司商业化或拟商业化的产品资产，对应一个或多个 substance |
| 项目 | Project | 为研发某 asset 而组织的研发活动，有明确时间、资源、目标 |
| 研究 | Study | 项目下具体的实验或研究活动 |
| 物料 | Material | 物理存在的物质批次产物，对应一个 substance |
| 数据所有者 | Data Owner | 对主数据准确性负最终责任的业务负责人（如 CMC Head） |
| 数据管家 | Data Steward | 执行主数据日常维护、审核的业务专家 |
| 数据保管员 | Data Custodian | 负责主数据系统技术运维的 IT 人员 |

## 2.2 法规与标准术语

| **术语** | **全称** | **适用范围** |
|----|----|----|
| 21 CFR Part 11 | Title 21 Code of Federal Regulations Part 11 | FDA 电子记录与电子签名规范 |
| EU GMP Annex 11 | EU GMP Guidelines Annex 11 - Computerised Systems | EU GMP 计算机化系统要求 |
| IDMP | Identification of Medicinal Products (ISO 11238/11239/11240/11615/11616) | 国际药品标识标准 |
| GSRS | Global Substance Registration System | FDA 与 EMA 共建的开源 substance 注册系统 |
| GxP | Good x Practice | GMP/GLP/GCP 等良好实践规范的统称 |
| CSV | Computer System Validation | 计算机化系统验证 |
| ALCOA+ | Attributable, Legible, Contemporaneous, Original, Accurate + Complete, Consistent, Enduring, Available | 数据完整性核心原则 |
| eCTD | electronic Common Technical Document | 电子通用技术文件，用于 FDA/EMA 等监管机构的注册申报 |

> ⚠ 法规版本核对
> 本文档引用的法规与标准请按以下原则核对最新版本：
> • 21 CFR Part 11：FDA 官网最新版本
> • EU GMP Annex 11：欧盟委员会官网，注意 2024–2026 年期间正在修订
> • ICH Q9(R1)、Q14、Q2(R2)、Q12、Q5E：ICH 官网确认当前生效版本
> • IDMP ISO 11238 系列：ISO 官网确认最新修订
> • GSRS：GitHub 开源项目当前数据模型版本

## 2.3 技术架构术语

| **术语** | **说明** |
|----|----|
| C4 模型 | 软件架构可视化方法，分为 Context、Container、Component、Code 四级 |
| Modular Monolith | 模块化单体架构，介于纯单体与微服务之间，物理上单一部署、逻辑上模块隔离 |
| 域分治 | Domain-Driven Design 思想，按业务域划分代码与数据边界 |
| API-First | 先定义 API 契约（OpenAPI），再开发前后端的工程实践 |
| RBAC | Role-Based Access Control，基于角色的访问控制 |
| JWT | JSON Web Token，无状态认证令牌 |
| RESTful | 基于 HTTP 的 REST 风格 API 设计原则 |
| ORM | Object-Relational Mapping，对象关系映射 |
| Schema | PostgreSQL 数据库内的逻辑命名空间，用于域隔离 |

# 3. 业务架构

## 3.1 主数据域分治模型

基于 SMP-RD-NUM-001 V2.1 的四层架构与 MDM 域分治原则，CMAB MDM Portal 划分为以下主数据域：

```text
┌──────────────────────────────────────────────────────────────────┐
│                    CMAB MDM Portal                               │
│                                                                  │
│  ┌────────────┐  ┌────────────┐  ┌────────────┐  ┌────────────┐  │
│  │    SRS     │  │    PRS     │  │    ARS     │  │    MM      │  │
│  │ Substance  │  │  Project   │  │   Asset    │  │  Material  │  │
│  │ 物质身份   │  │  研发活动  │  │  商业资产  │  │  物理批次  │  │
│  └─────┬──────┘  └─────┬──────┘  └─────┬──────┘  └─────┬──────┘  │
│        │                │               │                │       │
│        └────────────────┴───────────────┴────────────────┘       │
│                            │                                     │
│              ┌─────────────┴──────────────┐                      │
│              │   Cross-Reference Layer    │                      │
│              │   (REF) 跨域引用关系       │                      │
│              └────────────────────────────┘                      │
│                                                                  │
│              ┌────────────────────────────┐                      │
│              │   Audit & Compliance       │                      │
│              │   统一审计追踪与电子签名   │                      │
│              └────────────────────────────┘                      │
│                                                                  │
└──────────────────────────────────────────────────────────────────┘
```

## 3.2 各域职责定义

### 3.2.1 Substance Registration System (SRS)

职责：物质（分子）身份的唯一权威登记与管理。

核心功能：

- Substance 唯一编码生成（按 SMP-RD-NUM-001 规则）

- 多模态结构化信息管理：mAb / 双抗 / ADC / 融合蛋白 / 小分子（本期仅 mAb）

- 内外部标识符交叉映射（内部代号、INN、USAN、CAS、UNII、GSRS UUID 等）

- Sameness 同一性判定（序列比对、结构比较）

- 生命周期与状态管理（Draft → Registered → Active → Restricted → Deprecated）

- ADC 父子 substance 血缘关系建模（本期之后扩展）

- 法规对接基础：IDMP / GSRS 数据模型对齐

### 3.2.2 Project Registration System (PRS)

职责：研发项目的唯一登记与全生命周期管理。

核心功能：

- Project 唯一编码生成（按 SMP-RD-NUM-001 规则）

- 项目元数据管理（名称、类型、阶段、时间线、团队、预算）

- 项目层级与关系（Program → Project → Sub-project）

- 跨域引用：Project → Substance、Project → Asset、Project → Studies

- 项目状态机（Proposed → Initiated → Active → On-Hold → Completed/Terminated）

- 项目衍生关系（合并、拆分、衍生项目的血缘）

### 3.2.3 Asset Registration System (ARS)

职责：商业化或拟商业化产品资产的登记与管理。

核心功能：

- Asset 唯一编码生成

- 资产基本信息（商品名、目标市场、剂型、规格）

- Asset → Substance 关联（一个资产可对应多个 substance，如 ADC 包含抗体 + linker + payload）

- 注册状态跟踪（Pre-clinical / IND / Phase I-III / NDA-BLA / Approved / Marketed）

- 多市场注册标识符管理（NDC、EMA Procedure Number、NMPA 批准号等）

### 3.2.4 Material Master (MM)

职责：全公司物料身份注册表，作为下游 cmc-inventory（实验室运营平台）的物料数据上游。

核心功能：

- 物料身份注册：
  - `material_code` 由用户输入公司既有编码（max 20 chars），非系统生成
  - `material_type` 4 值（reagent / consumable / standard / column）— 系统视角
  - `category` 公司分类体系 15 值扁平枚举（中文）— 业务视角，与 type 解耦
  - 两个维度独立：例如 `material_type=column` 的物料其 `category` 可能是「一般耗材」

- 供应商 & 规格管理（生产商、货号、规格型号、包装规格、默认计量单位）

- 危化品分类标记（多选：危化品 / 易燃 / 易制毒 / 易制爆 / 剧毒品）

- Material → Substance 关联（一个 substance 可对应多个 material）

- Material Batch 批次登记（批号、数量、有效期、存储位置）

- 批量导入：支持公司既有 Excel「物流-物料代码表」一次性导入，
  脚本 `app/scripts/import_materials_excel.py`（已落地 3702 条真实物料，2026-05-19）

> ⚠ 范围说明
> MM 只管"这个物料是什么"（身份户口本），不管库存 / 位置 / 出入库（那是下游 cmc-inventory 的事）。

### 3.2.5 Cross-Reference Layer (REF)

职责：管理跨域引用关系，提供统一关联查询能力。

核心功能：

- 引用关系表的维护（Project ↔ Substance、Asset ↔ Substance、Material ↔ Substance 等）

- 引用关系类型与基数定义（一对多、多对多）

- 反向查询 API（如「该 substance 关联哪些项目」）

- 引用完整性约束（被引用的实体不可物理删除，仅可 deprecate）

### 3.2.6 Audit & Compliance Layer (AUDIT)

职责：跨所有域的统一合规能力。

核心功能：

- 所有 CRUD 操作的审计追踪（who、when、what、why）

- 电子签名（密码二次确认 + 签名记录）

- 数据变更前后值记录（基于 PostgreSQL UPDATE 触发器）

- 软删除策略（禁止物理删除）

- 用户权限与角色管理（RBAC）

- 操作日志查询与导出（满足审计核查需求）

## 3.3 数据流向与引用方向

各域之间通过 ID 引用建立关联，引用方向遵循以下规则：

```text
引用方向规则：

  Project    ──→ Substance     (Project 知道自己研究什么分子)
  Project    ──→ Asset         (Project 知道自己服务于哪个商业资产)
  Asset      ──→ Substance     (Asset 知道自己基于什么分子)
  Material   ──→ Substance     (Material 知道自己是什么分子的物理形态)
  Study      ──→ Project       (Study 隶属于 Project)

  ★ Substance 不反向引用任何其他实体（避免循环依赖）

  反向查询通过 API 实现，例如：
    GET /api/v1/substances/{id}/projects
    GET /api/v1/substances/{id}/assets
    GET /api/v1/substances/{id}/materials
```

## 3.4 典型业务场景

### 3.4.1 场景一：新分子立项

1.  研究人员在 SRS 申请注册新 substance（如新单抗）

2.  Substance Steward 审核通过，系统分配 Substance ID（如 SUB-0000123）

3.  立项后在 PRS 创建项目，引用该 SUB-0000123，得到 Project ID（如 PRJ-2026-0123）

4.  如该项目目标是商业化产品，在 ARS 创建 asset 记录，关联 SUB-0000123，得到 Asset ID（如 AST-0045）

5.  项目下创建 Studies（如药学研究、稳定性研究）

6.  研发推进过程中产生的物料批次在 MM 登记，关联 SUB-0000123

### 3.4.2 场景二：跨部门信息查询

7.  注册部门需要查询某分子的所有信息以准备 IND 申报

8.  通过全局搜索输入分子内部代号或 INN

9.  系统返回 Substance 详情页，右侧关联标签显示该分子关联的所有 Project / Asset / Material / Studies

10. 点击进入相关项目或资产查看详情，无需切换系统

### 3.4.3 场景三：分子合并与去重

11. Substance Steward 发现两个 Substance 实际为同一分子（如来源不同表达体系但序列相同）

12. 发起合并工作流，将其中一个 Substance 状态置为 Deprecated 并指向 master substance

13. 系统自动更新所有引用该 Deprecated substance 的 Project / Asset / Material 的引用关系

14. 操作全程记录审计日志，可追溯合并依据与决策

# 4. 系统架构（C4 模型）

## 4.1 C4 Level 1：系统上下文图

CMAB MDM Portal 在企业 IT 全景中的位置：

```text
                    ┌─────────────────────────────┐
                    │     用户群体                │
                    │  CMC R&D / QA / 注册        │
                    │  生产 / IT / 管理层         │
                    └──────────────┬──────────────┘
                                   │ Web 浏览器
                                   ▼
        ┌─────────────────────────────────────────────────┐
        │           CMAB MDM Portal                       │
        │   (Substance / Project / Asset / Material)      │
        │                                                 │
        │   核心能力：主数据登记、查询、生命周期管理       │
        │            跨域关联、审计、合规、API 服务        │
        └──┬──────────┬──────────┬──────────┬─────────────┘
           │          │          │          │
           ▼          ▼          ▼          ▼
        ┌──────┐  ┌──────┐  ┌──────┐  ┌──────────┐
        │ ELN  │  │ LIMS │  │ DMS  │  │   QMS    │
        │      │  │      │  │      │  │          │
        └──────┘  └──────┘  └──────┘  └──────────┘
        (下游业务系统，通过 API 引用 MDM 主数据)

           未来集成：
           ┌──────────┐  ┌──────────┐  ┌──────────┐
           │ SAP/ERP  │  │ Veeva RIM│  │ FDA GSRS │
           └──────────┘  └──────────┘  └──────────┘
```

### 外部系统说明

| **系统** | **类型** | **本期集成方式** |
|----|----|----|
| ELN（电子实验记录） | 下游消费方 | 本期暴露 API，下游可调用查询 substance/project |
| LIMS（实验室信息系统） | 下游消费方 | 本期暴露 API |
| DMS（文档管理） | 下游消费方 | 本期暴露 API |
| QMS（质量管理） | 下游消费方 | 本期暴露 API |
| RAGFlow（知识库） | 下游消费方 | 本期暴露 API（用于知识库索引） |
| cmc_data_platform | 同级数据平台 | 共享 PostgreSQL，schema 隔离 |
| SAP / 商业 ERP | 未来集成 | 本期预留集成接口 |
| Veeva Vault RIM | 未来集成 | 本期预留集成接口 |
| FDA GSRS | 未来集成 | 本期数据模型对齐为目标 |

## 4.2 C4 Level 2：容器图

系统内部主要部署单元（容器）：

```text
┌───────────────────────────────────────────────────────────────────┐
│                    用户浏览器（Chrome/Edge/Firefox）              │
└────────────────────────────┬──────────────────────────────────────┘
                             │ HTTPS
                             ▼
┌───────────────────────────────────────────────────────────────────┐
│                    Nginx 反向代理                                 │
│  - 静态资源服务  - HTTPS 终止  - 路由分发  - 限流                 │
└────────┬─────────────────────────────────┬────────────────────────┘
         │ /                               │ /api/*
         ▼                                 ▼
┌──────────────────────┐         ┌────────────────────────────────┐
│ Frontend Container   │         │ Backend API Container          │
│  React 18 + TS       │         │  FastAPI + Uvicorn             │
│  Ant Design 5        │         │  Python 3.12                   │
│  Vite 构建产物       │         │  ├─ srs 域模块                 │
│  (静态资源)          │         │  ├─ prs 域模块                 │
│                      │         │  ├─ ars 域模块                 │
│                      │         │  ├─ mm 域模块                  │
│                      │         │  └─ shared 共享层              │
└──────────────────────┘         └──┬─────────────┬───────────────┘
                                    │             │
                                    ▼             ▼
                            ┌──────────────┐ ┌────────────┐
                            │ PostgreSQL 16│ │  Redis 7   │
                            │ (主数据库)   │ │ (缓存/队列)│
                            │              │ │            │
                            │ Schemas:     │ │            │
                            │  ├─ srs      │ │            │
                            │  ├─ prs      │ │            │
                            │  ├─ ars      │ │            │
                            │  ├─ mm       │ │            │
                            │  ├─ ref      │ │            │
                            │  ├─ audit    │ │            │
                            │  └─ auth     │ │            │
                            └──────────────┘ └────────────┘

                            ┌──────────────────────────┐
                            │   MinIO（可选）          │
                            │   对象存储（附件、序列） │
                            └──────────────────────────┘
```

### 容器职责说明

| **容器** | **技术栈** | **职责** |
|----|----|----|
| Nginx | Nginx 1.25+ | 静态资源、HTTPS 终止、反向代理、限流 |
| Frontend | React 18 + TS + Vite | 用户界面渲染、状态管理、API 调用 |
| Backend API | FastAPI + Uvicorn | 业务逻辑、数据访问、认证授权、审计 |
| PostgreSQL | PostgreSQL 16 | 主数据持久化、事务、审计日志 |
| Redis | Redis 7 | 会话缓存、JWT 黑名单、Celery 队列 |
| MinIO（可选） | MinIO RELEASE | 附件、序列文件、报告存储 |
| Celery Worker（可选） | Celery + Python | 异步任务（批量导入、序列比对） |

## 4.3 C4 Level 3：后端组件图

Backend API 容器内部组件结构（域分治）：

```text
┌──────────────────────────────────────────────────────────────┐
│                  FastAPI Application                         │
│                                                              │
│  ┌────────────────────────────────────────────────────────┐  │
│  │              API Layer (路由层)                        │  │
│  │  /api/v1/substances  /api/v1/projects                  │  │
│  │  /api/v1/assets      /api/v1/materials                 │  │
│  │  /api/v1/references  /api/v1/auth                      │  │
│  └────────────────────────────────────────────────────────┘  │
│                          │                                   │
│  ┌────────────────────────────────────────────────────────┐  │
│  │       Middleware Layer (中间件层)                      │  │
│  │  - JWT 认证                                            │  │
│  │  - RBAC 权限                                           │  │
│  │  - 审计拦截器                                          │  │
│  │  - 请求 ID / 链路追踪                                  │  │
│  │  - CORS / 限流                                         │  │
│  └────────────────────────────────────────────────────────┘  │
│                          │                                   │
│  ┌────────────────────────────────────────────────────────┐  │
│  │       Domain Layer (域层 - 业务逻辑)                   │  │
│  │  ┌───────┐  ┌───────┐  ┌───────┐  ┌────┐              │  │
│  │  │ SRS   │  │ PRS   │  │ ARS   │  │ MM │              │  │
│  │  │Service│  │Service│  │Service│  │Svc │              │  │
│  │  └───────┘  └───────┘  └───────┘  └────┘              │  │
│  └────────────────────────────────────────────────────────┘  │
│                          │                                   │
│  ┌────────────────────────────────────────────────────────┐  │
│  │       Shared Layer (共享层)                            │  │
│  │  - 编码生成器（SMP-RD-NUM-001）                        │  │
│  │  - 工作流引擎（状态机）                                │  │
│  │  - 审计日志服务                                        │  │
│  │  - 通知服务                                            │  │
│  │  - 权限服务                                            │  │
│  └────────────────────────────────────────────────────────┘  │
│                          │                                   │
│  ┌────────────────────────────────────────────────────────┐  │
│  │       Repository Layer (数据访问层)                    │  │
│  │  SQLAlchemy 2.0 Async ORM                              │  │
│  │  各域 Repository 隔离                                  │  │
│  └────────────────────────────────────────────────────────┘  │
│                          │                                   │
└──────────────────────────┼───────────────────────────────────┘
                           ▼
                  ┌────────────────┐
                  │  PostgreSQL    │
                  └────────────────┘
```

**Service 层事务提交规则（V1.1 新增）**

① 适用范围（强制显式 commit）：状态机变更（status / current_phase 变化）、电子签名生效写入（status_history.e_signature_id 回填）、跨域引用写入（ref.\* 三表 link / unlink）等强一致性写操作，service 必须在所有数据库变更完成后显式 await self.db.commit()，不依赖 FastAPI yield 依赖（get_db）的 cleanup commit。

② 不适用范围（沿用统一 transaction pattern）：普通 CRUD（读、单表 INSERT / UPDATE / soft-delete）、列表查询、详情查询等无强一致性约束的端点，按 FastAPI yield 依赖默认 commit 即可，不必引入 service 显式 commit。

③ 原因：FastAPI 异步 yield 依赖的 cleanup 在 HTTP response 已发送给客户端之后执行，客户端紧接的下一请求可能在 pre-commit 状态下读到旧快照（pytest 全集实测 ~10% 失败率）。Service 显式 commit 后，yield cleanup 的 commit 退化为空操作。

④ 判断准则：端点是否触发后续读操作必须看到本次写入结果？若是 → 强一致性，显式 commit；若否 → 沿用统一 pattern。

## 4.4 C4 Level 3：前端组件图

```text
┌────────────────────────────────────────────────────────────────┐
│                    React App (CMAB MDM Portal)                 │
│                                                                │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │           Layout 主布局                                 │   │
│  │  ┌──────────────────────────────────────────────────┐   │   │
│  │  │ Header (Logo / 全局搜索 / 用户 / 通知)           │   │   │
│  │  ├──────────────────────────────────────────────────┤   │   │
│  │  │ Sidebar │  Content Area                          │   │   │
│  │  │ 模块导航│  当前模块的页面渲染区                  │   │   │
│  │  └──────────────────────────────────────────────────┘   │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                │
│  ┌────────────┐  ┌────────────┐  ┌────────────┐  ┌────────┐    │
│  │ Substances │  │  Projects  │  │   Assets   │  │Materials│   │
│  │   Module   │  │   Module   │  │   Module   │  │ Module  │   │
│  │            │  │            │  │            │  │         │   │
│  │ - List     │  │ - List     │  │ - List     │  │ - List  │   │
│  │ - Detail   │  │ - Detail   │  │ - Detail   │  │ - Detail│   │
│  │ - Form     │  │ - Form     │  │ - Form     │  │ - Form  │   │
│  │ - Hooks    │  │ - Hooks    │  │ - Hooks    │  │ - Hooks │   │
│  └────────────┘  └────────────┘  └────────────┘  └────────┘    │
│                                                                │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │           Shared Components                             │   │
│  │  - GlobalSearch        - DataTable                      │   │
│  │  - EntityRefSelector   - StatusBadge                    │   │
│  │  - AuditTrailViewer    - WorkflowStepper                │   │
│  │  - SignaturePad        - PermissionGuard                │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │           Stores（Zustand）+ React Query                │   │
│  │  - authStore           - uiStore                        │   │
│  │  - 各模块的 Server State 由 React Query 管理            │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │           API Client (Axios + 拦截器)                   │   │
│  └─────────────────────────────────────────────────────────┘   │
└────────────────────────────────────────────────────────────────┘
```

## 4.5 部署视图

Linux 虚拟机部署拓扑：

```text
┌────────────────────────────────────────────────────────────────┐
│           公司内网（Linux 虚拟机）                              │
│                                                                │
│   ┌──────────────────────────────────────────────────────┐     │
│   │                Docker Engine                         │     │
│   │                                                      │     │
│   │   ┌────────┐  ┌──────────┐  ┌──────────────┐         │     │
│   │   │ Nginx  │  │ Frontend │  │   Backend    │         │     │
│   │   │        │  │ (静态)   │  │   FastAPI    │         │     │
│   │   │ :80    │  │          │  │   :8000      │         │     │
│   │   │ :443   │  │          │  │              │         │     │
│   │   └────────┘  └──────────┘  └──────┬───────┘         │     │
│   │                                    │                 │     │
│   │   ┌──────────────┐  ┌──────────────┐                 │     │
│   │   │ PostgreSQL 16│  │  Redis 7     │                 │     │
│   │   │ :5432        │  │  :6379       │                 │     │
│   │   └──────────────┘  └──────────────┘                 │     │
│   │                                                      │     │
│   │   docker-compose 统一编排                            │     │
│   └──────────────────────────────────────────────────────┘     │
│                                                                │
│   备份目录：/backup/cmab-mdm/                                  │
│   日志目录：/var/log/cmab-mdm/                                 │
│   数据目录：/data/cmab-mdm/postgres                            │
└────────────────────────────────────────────────────────────────┘

   开发环境：MacBook Pro / 办公 PC（Docker Desktop）
   测试环境：Linux 虚拟机
   生产环境：Linux 虚拟机（独立实例，未来可考虑双机）
   代码同步：Git push / pull
```

# 5. 技术栈选型

## 5.1 技术栈总览

| **层** | **技术** | **版本** | **选型理由** |
|----|----|----|----|
| 前端框架 | React + TypeScript | 18 / 5.x | 工业级、生态完善、长期可维护 |
| 前端构建 | Vite | 5.x | 现代化构建工具、开发体验优秀 |
| UI 组件库 | Ant Design + Pro Components | 5.x | 企业级中文友好、组件丰富 |
| 前端状态 | Zustand + TanStack Query | — | 轻量、服务端状态分离 |
| 前端表单 | React Hook Form + Zod | — | 性能好、类型安全 |
| 前端图表 | ECharts / Recharts | — | 大量图表场景 |
| 前端图形 | React Flow | — | 血缘图、流程图、依赖图 |
| 后端框架 | FastAPI | 0.110+ | 现代异步、自动 OpenAPI、性能优秀 |
| 后端 ORM | SQLAlchemy 2.0 (async) | 2.0+ | 事实标准、async 支持、迁移工具成熟 |
| 数据校验 | Pydantic v2 | 2.x | 性能大幅提升、类型驱动 |
| 数据库迁移 | Alembic | — | SQLAlchemy 官方迁移工具 |
| 认证 | python-jose + passlib | — | JWT 标准实现 |
| 任务队列 | Celery + Redis | — | 成熟方案，异步任务支持 |
| 数据库 | PostgreSQL | 16 | 已部署、JSONB 支持异构数据 |
| 缓存 | Redis | 7 | 成熟、性能优秀 |
| 对象存储（可选） | MinIO | — | S3 兼容、私有部署 |
| 反向代理 | Nginx | 1.25+ | 成熟、性能优秀 |
| 容器化 | Docker + Compose | — | 已有部署经验 |

## 5.2 开发工具链

| **工具** | **用途** | **备注** |
|----|----|----|
| uv | Python 包管理 | 替代 pip / poetry，极快 |
| pnpm | Node 包管理 | 替代 npm，节省磁盘空间 |
| ruff | Python lint + format | 替代 flake8 + isort + black 部分功能 |
| mypy | Python 类型检查 | — |
| ESLint + Prettier | 前端 lint + format | Ant Design 项目标配 |
| Husky + lint-staged | Git hook | 提交前自动检查 |
| pytest + pytest-asyncio | 后端测试 | — |
| Vitest + RTL | 前端测试 | Vite 原生支持 |
| Playwright | E2E 测试 | 后期可加 |
| DBeaver | 数据库管理 | 跨平台 |
| Postman / Bruno | API 调试 | Bruno 开源替代 |

## 5.3 开发与部署环境

| **环境**   | **部署位置**                 | **用途**       |
|------------|------------------------------|----------------|
| dev (本地) | MacBook Pro M5 Pro / 办公 PC | 开发与本地调试 |
| test       | Linux 虚拟机                 | 集成测试、UAT  |
| prod       | Linux 虚拟机                 | 生产运行       |

代码同步流程：本地开发（Mac/PC）→ Git push → Linux 服务器 Git pull → docker compose up。

## 5.4 关键依赖与版本策略

- Python 主版本固定为 3.12，每年评估升级

- Node.js 主版本固定为 20 LTS

- PostgreSQL 大版本与现有 cmc_data_platform 一致（16）

- 前端依赖：使用 pnpm + lockfile 锁定版本，每季度评估升级

- 后端依赖：使用 uv + pyproject.toml + lockfile 锁定版本

- 安全补丁：每月评估并应用关键安全更新

- 重大版本升级：纳入版本规划，评估兼容性影响

# 6. 数据架构

## 6.1 PostgreSQL Schema 划分

基于域分治原则，单一 PostgreSQL 数据库内通过 schema 实现逻辑隔离：

| **Schema** | **用途** | **主要表** |
|----|----|----|
| srs | Substance Registration | substance, substance_protein, substance_adc, substance_xref, substance_status_history |
| prs | Project Registration | project, project_milestone, project_status_history, project_team |
| ars | Asset Registration | asset, asset_market_id, asset_status_history |
| mm | Material Master (Lite) | material, material_batch, material_attribute |
| ref | Cross-Reference Layer | ref_project_substance, ref_asset_substance, ref_material_substance |
| audit | Audit & Compliance | audit_log, e_signature, change_history |
| auth | Auth & RBAC | user, role, permission, user_role, role_permission |
| meta | Meta Data | code_sequence, lookup_value, system_config |

> ⚠ Schema 隔离的好处
> 1. 域职责清晰：每个 schema 对应一个业务域，权限可精细化控制
> 2. 命名空间避免冲突：不同域可有同名表（如 audit.log vs srs.log）
> 3. 备份与迁移灵活：可单独备份或迁移某个 schema
> 4. 未来拆分微服务平滑：每个 schema 可独立成库

## 6.2 编码规则（基于 SMP-RD-NUM-001 V2.1）

各域的主键编码规则：

| **域**    | **前缀** | **格式示例**    | **规则说明**                 |
|-----------|----------|-----------------|------------------------------|
| Substance | SUB-     | SUB-0000123     | 纯流水号，语义中性，永不复用 |
| Project   | PRJ-     | PRJ-2026-0123   | 年份 + 流水号，便于按年归档  |
| Asset     | AST-     | AST-0045        | 纯流水号，资产数量较少       |
| Material  | （无）   | `51001`         | **用户输入公司既有编码**（max 20 chars，非系统生成；trigger 兜底为 MAT-yyyyNNNNNN） |
| Study     | STD-     | STD-2026-0234   | 年份 + 流水号                |

> ⚠ 编码核心原则
> • 语义中性：编码不携带业务语义（如不嵌入项目类型、模态、阶段等会变化的属性）
> • 唯一不变：编码一旦分配，永不修改、永不复用、永不删除（仅可 deprecate）
> • 集中生成：通过 meta.code_sequence 表统一生成，避免并发冲突
> • 可追溯：编码生成事件全程审计
> • 完整规则参见：SMP-RD-NUM-001 V2.1

## 6.3 多模态 Substance 数据模型

生物制药 substance 结构异构（mAb / 双抗 / ADC / 融合蛋白 / 小分子），采用主表 + 类型扩展表的多态设计：

```text
srs.substance（主表，所有 substance 通用字段）
  ├─ substance_id (PK, 自增)
  ├─ substance_code (UNIQUE, 如 SUB-0000123)
  ├─ substance_type (mab / bispecific / adc / fusion / small_molecule)
  ├─ internal_code (内部代号)
  ├─ status (Draft/Registered/Active/Restricted/Deprecated)
  ├─ created_at, created_by, updated_at, updated_by
  └─ ...

srs.substance_protein（蛋白类扩展，mAb / 双抗 / 融合蛋白共用）
  ├─ substance_id (FK)
  ├─ heavy_chain_sequence (TEXT)
  ├─ light_chain_sequence (TEXT)
  ├─ ptm_info (JSONB)  ← 灵活存储修饰信息
  ├─ glycosylation_sites (JSONB)
  ├─ expression_system
  └─ ...

srs.substance_adc（ADC 扩展）
  ├─ substance_id (FK, 复合 substance 本身)
  ├─ antibody_substance_id (FK → 抗体 substance)
  ├─ linker_substance_id (FK → linker substance)
  ├─ payload_substance_id (FK → payload substance)
  ├─ dar_average (DAR 平均值)
  ├─ conjugation_chemistry
  └─ ...

srs.substance_small_molecule（小分子扩展）
  ├─ substance_id (FK)
  ├─ smiles (TEXT)
  ├─ inchi (TEXT)
  ├─ inchi_key (UNIQUE INDEX)
  ├─ molecular_formula
  └─ ...

srs.substance_xref（外部标识符映射）
  ├─ substance_id (FK)
  ├─ xref_type (INN / USAN / CAS / UNII / GSRS_UUID / ChEMBL / 商品名)
  ├─ xref_value
  ├─ xref_source (来源)
  ├─ effective_date
  └─ ...
```

## 6.4 跨域引用关系表设计

跨域引用通过独立的 ref schema 管理，避免域之间的硬耦合：

```text
ref.project_substance
  ├─ project_id (FK → prs.project)
  ├─ substance_id (FK → srs.substance)
  ├─ relation_type (主要研究 / 对照 / 衍生)
  ├─ created_at, created_by
  └─ PK: (project_id, substance_id, relation_type)

ref.asset_substance
  ├─ asset_id (FK → ars.asset)
  ├─ substance_id (FK → srs.substance)
  ├─ component_role (主成分 / linker / payload)
  └─ ...

ref.material_substance
  ├─ material_id (FK → mm.material)
  ├─ substance_id (FK → srs.substance)
  └─ ...
```

## 6.5 审计与合规数据模型

满足 21 CFR Part 11 / Annex 11 要求的审计追踪机制：

```text
audit.audit_log（操作审计）
  ├─ log_id (PK)
  ├─ user_id  (操作人)
  ├─ session_id  (会话标识)
  ├─ action (CREATE / READ / UPDATE / DELETE / APPROVE / SIGN)
  ├─ entity_schema (srs / prs / ars / ...)
  ├─ entity_table
  ├─ entity_id
  ├─ change_summary (变更摘要)
  ├─ ip_address, user_agent
  ├─ request_id (链路追踪)
  ├─ timestamp (UTC)
  └─ reason (变更原因，关键操作必填)

audit.change_history（数据变更前后值）
  ├─ history_id (PK)
  ├─ audit_log_id (FK)
  ├─ field_name
  ├─ old_value (JSONB)
  ├─ new_value (JSONB)
  └─ ...

audit.e_signature（电子签名）
  ├─ signature_id (PK)
  ├─ user_id
  ├─ entity_schema, entity_table, entity_id
  ├─ signature_meaning (审批 / 复核 / 批准)
  ├─ signed_at (UTC)
  ├─ signature_hash (签名内容哈希)
  ├─ ip_address
  └─ ...
```

**子表 entity_code 回填机制（V1.1 新增）：通用审计触发器 audit.fn_audit_trigger(...) 采用 3 参数签名 (pk_col, code_col, parent_ref)，其中 parent_ref 格式为 'schema.table:pk_col:code_col:fk_on_this_table'。子表（如 substance_xref / project_milestone / asset_market_id / ref.asset_substance）自身无业务编码，触发器通过 parent_ref 自动将 audit_log.entity_code 回填为父表 code（SUB-XXX / PRJ-XXX / AST-XXX），保证「按业务编码查全量审计历史」能跨主子表覆盖。**

**失败副作用的旁路 session 持久化（V1.1 新增）**

① 严格适用范围：仅用于"失败但必须留痕的副作用"——典型场景：failed_login_count++ / failed_signature_count++ / 登录失败审计日志 / 签名失败审计日志 / 账号锁定记录。

② 不得用于：普通业务写操作（CRUD / link / unlink / 状态机变更等）。普通写操作必须在主事务内完成，依赖统一 transaction 边界保证 ACID；旁路 session 绕过主事务原子性，误用会造成数据一致性破坏。

③ 实现：独立 AsyncSessionLocal() 创建 session，写入后单独 await session.commit()，再 raise 业务异常。主事务被 get_db 的 except: rollback() 整体回滚时，旁路 session 已提交的失败痕迹不受影响。

④ 原因：21 CFR Part 11 §11.300 要求防暴力破解与失败审计必须可追溯；若挂在主事务上，raise → rollback 将一并丢失计数与日志，破解保护失效。

⑤ 评审准则：每个使用旁路 session 的位置都应有 code review 备注说明"为何必须脱离主事务"，避免后续维护者将其扩展到普通写场景。

> ⚠ 数据完整性关键设计
> • 所有时间戳使用 UTC 存储，前端按用户时区展示
> • 关键表使用 UPDATE 触发器自动写入 change_history
> • 软删除：通过 deleted_at 字段实现，禁止物理 DELETE
> • 数据库账号权限分离：应用账号 vs 审计审查账号
> • 审计日志独立 schema，应用账号仅可写不可改

# 7. 安全与合规架构

## 7.1 21 CFR Part 11 / Annex 11 合规映射

| **要求** | **实现机制** |
|----|----|
| 唯一用户身份 | auth.user 表，唯一用户名，无共享账号 |
| 密码安全 | bcrypt 哈希存储，复杂度策略，定期更换 |
| 电子签名 | audit.e_signature 表，密码二次确认 + 签名摘要 |
| 审计追踪 | audit.audit_log 全量记录所有 CRUD + 业务事件 |
| 数据完整性 | 数据库触发器记录变更前后值，UTC 时间戳 |
| 不可篡改 | 审计 schema 仅可写不可改，软删除策略 |
| 权限控制 | RBAC 模型，最小权限原则 |
| 会话超时 | Phase 1–3 当前采用 JWT 短有效期（access_token 30 min）+ 过期后重新登录；Refresh Token / 空闲超时策略为目标认证架构，列入 Phase 4 安全收尾实现。 |
| **身份再验证错误分流** | 401 响应携带 \`meta.error.type\` 字段区分会话失效（token_expired / token_invalid / token_missing）与业务身份再验证失败（signature_invalid / old_password_wrong）；前端拦截器按 \`meta.error.type\` 分流处置，会话失效跳登录、业务身份错误就地提示，不一刀切清 token |
| 数据备份 | PostgreSQL 每日全量 + WAL 增量 |
| 系统验证 | 后续完整 CSV 流程，文档化测试 |

**⚠ 实施侧关键比较精度规则（V1.1 新增）**

JWT iat 与 auth.user.password_changed_at 比较时必须按整数秒截断。JWT iat 由 PyJWT 写入为整数秒（Unix epoch），而 PostgreSQL TIMESTAMPTZ 的 password_changed_at 精度为微秒。直接比较会因为 password_changed_at 微秒部分非零，导致刚改完密码立刻签发的 token（同一秒）被判定为「在密码变更之前签发」从而误判失效。正确比较：int(jwt\['iat'\]) \< int(password_changed_at.timestamp())。改密码后旧 token 即时失效的语义仍然保证（密码变更跨秒后所有旧 token 失效）。

## 7.2 认证与授权

### 7.2.1 认证流程

### 说明：本节描述目标认证流程。Phase 1–3 当前仅实现 Access Token 登录与鉴权，access_token 有效期 30 min，过期后由前端引导用户重新登录；Refresh Token 流转与 /auth/refresh 端点列入 Phase 4 安全收尾实现。Redis Token 黑名单属于目标能力，应用层接入列入 Phase 5；当前旧 token 即时失效通过 JWT iat 与 auth.user.password_changed_at 比较实现。

15. 用户在登录页输入用户名 + 密码

16. 后端验证密码（bcrypt 哈希比对），失败 5 次锁定账号。注意：失败计数 failed_login_count++ 与登录失败审计日志必须通过独立 AsyncSessionLocal() 旁路 session 提交，不能挂在主请求事务上（详见 §6.5 失败副作用旁路 session）；否则 raise 401 后主事务 rollback 会丢失计数，账号锁定保护失效。

17. 生成 Access Token（短有效期，如 30 分钟）+ Refresh Token（较长，如 7 天）

18. 前端存储 Access Token（内存 / sessionStorage），Refresh Token（HttpOnly Cookie）

19. 后续请求携带 Access Token，过期时通过 Refresh Token 自动刷新

20. 用户主动登出或会话失效，Token 加入 Redis 黑名单（注：Redis 应用层接入推迟至 Phase 5，当前由 JWT iat 与 auth.user.password_changed_at 比较实现即时失效，见 §7.1 比较精度规则）

21. 用户改密后，auth.user.password_changed_at 更新至当前 UTC 时间；后续所有旧 token 因 iat \< password_changed_at（按整数秒截断）被网关拒绝，无需 Redis 黑名单参与。

### 7.2.2 RBAC 权限模型

```text
User ──→ Role ──→ Permission

预设角色：
  - SystemAdmin       : 系统管理员，全权限
  - SubstanceSteward  : 物质数据管家，物质域审核与合并
  - ProjectManager    : 项目经理，项目域全权限
  - CMCResearcher     : 研发人员，物质/项目读写（受范围限制）
  - QAReviewer        : 质量审核，电子签名权限
  - ReadOnlyUser      : 只读用户

权限粒度：
  - 模块级：能否访问某个域的功能
  - 操作级：能否在某域执行 CREATE / UPDATE / APPROVE / SIGN 等
  - 数据级：能否访问某些受限数据（如保密项目）
```

**权限组合校验（GxP 关键端点）（V1.1 新增）**

对 21 CFR Part 11 §11.50 / §11.70 要求电子签名的关键不可逆操作，端点装饰器使用 require_all_permissions(...) 工厂同时校验操作权限 + 签名权限双权限。例如：物质审批端点要求 substance:approve + substance:sign、资产终止端点要求 asset:update + asset:sign、项目状态变更要求 project:update + project:sign。单一权限不足以触发关键操作。权限矩阵种子数据中 \*:sign 权限仅分配给 QA_REVIEWER 与 PROJECT_MANAGER / SUBSTANCE_STEWARD 等具备签名职责的角色。

**⚠ 反模式：asyncpg 连接池 SET LOCAL GUC 跨事务泄漏（V1.1 新增）**

禁止通过 SET LOCAL \<session_var\> = … 在事务内注入业务上下文（如 e_signature_id）让 DB 触发器读取，即便使用 SET LOCAL 关键字。asyncpg 连接池在事务结束后归还连接到池中，下一个事务复用同一物理连接时，前事务的 SET LOCAL 值会残留（M2.5.1 实测：第 2 条 status_history 写入了第 1 条事务的 e_signature_id）。

正确做法：service 在创建 status_history 行后显式执行 UPDATE status_history SET e_signature_id = :sid WHERE history_id = :hid，由 ORM 显式传参，不依赖 session 变量注入。

## 7.3 数据安全

- 传输加密：所有 HTTP 请求强制 HTTPS，TLS 1.3

- 存储加密：数据库文件系统级加密（LUKS）

- 敏感字段加密：序列等关键 IP 数据，应用层加密存储

- 数据库账号分离：应用账号最小权限，审计账号只读

- API 限流：基于 IP / 用户的请求速率限制

- CORS 严格白名单：仅允许指定域名访问 API

- SQL 注入防护：ORM 参数化查询，禁止字符串拼接

- XSS 防护：前端 React 默认转义 + CSP 头

- CSRF 防护：SameSite Cookie + CSRF Token

## 7.4 备份与灾备

**当前实施状态（Phase 1-3 完成时）（V1.1 新增）**

本节备份策略为目标设计，dev / 测试环境尚未部署完整备份流程；生产部署（Phase 4）前必须完成下列三项，缺一不可：

① 按本节定义部署备份执行流程（全量 + WAL 增量）；

② 完成至少一次完整恢复演练（从备份还原到独立环境并验证业务可用性，验证 RTO ≤ 4h / RPO ≤ 1h 指标）；

③ 演练记录归档（含演练日期、执行人、起止时间、恢复结果、RTO/RPO 实测值、异常处理），并由 QA 归档至 GxP 验证证据库。

⚠ 未完成恢复演练的备份策略不能视为已实施——21 CFR Part 11 / Annex 11 与 GxP 数据完整性（ALCOA+）均要求"备份必须可恢复"，仅定义策略不算合规。详见 §10.6 路线图。

| **类型**    | **频率**   | **保留期** | **位置**                |
|-------------|------------|------------|-------------------------|
| 全量备份    | 每日 02:00 | 30 天      | 本地 + Duck-mounted NAS |
| WAL 增量    | 实时       | 7 天       | 本地                    |
| Schema dump | 每周日     | 180 天     | NAS + 异地              |
| 配置备份    | 变更时     | 永久       | Git 仓库                |
| 代码仓库    | 实时       | 永久       | Git 仓库 + 镜像         |

- RTO（恢复时间目标）：≤ 4 小时

- RPO（恢复点目标）：≤ 1 小时

- 每季度执行一次完整恢复演练

## 7.5 CSV 验证策略

本期定位：第一版作为 R&D 工具，避开 GMP 范围；商业化使用前补充完整 CSV 验证。

分阶段验证策略：

| **阶段**          | **时间**       | **验证范围**                           |
|-------------------|----------------|----------------------------------------|
| Phase 1: R&D 工具 | 本期上线       | URS、IQ/OQ 简化版、用户培训            |
| Phase 2: GxP 系统 | 上线后 6–12 月 | 完整 CSV：URS / FS / DS / IQ / OQ / PQ |
| Phase 3: 持续验证 | 持续           | 变更控制、回归测试、定期再验证         |

# 8. 实施路线图

## 8.1 总体节奏

分四个阶段，总周期 9–12 个月达到 SRS + PRS + ARS 三模块上线：

| **Phase** | **时间** | **主要交付物** |
|----|----|----|
| Phase 0: 设计与脚手架 | Month 1 | 架构文档、数据模型、API 规范、UI 线框、项目脚手架 |
| Phase 1: SRS MVP | Month 2–4 | SRS 后端 + 前端，仅 mAb，CRUD + 审计 |
| Phase 2: PRS + 跨域 | Month 5–6 | PRS 完整模块，跨域引用，全局搜索 |
| Phase 3: ARS + 合规 | Month 7–8 | ARS 模块，电子签名，权限细化 |
| Phase 4: MM 基础域 + 生产部署准备 | Month 9–10 | MM 基础域 / material 搜索接入、/auth/refresh、独立审计日志页、UAT、数据迁移、备份恢复演练、生产部署配置、CSV 验证准备 |
| Phase 5: 数据治理与持续优化 | Month 11–12+ | merge / reject / batch / advance-phase 视需、Redis 缓存、系统管理 Admin UI、复杂 fuzzy matching、其他模态与体验增强 |

## 8.2 Phase 0：设计与脚手架（Month 1）

### 交付物

- 《CMAB MDM 平台总体架构设计文档》（本文档）

- 《数据模型设计文档》（含完整 ERD、DDL 脚本）

- 《API 接口规范》（OpenAPI 3.0 YAML）

- 《UI 信息架构与关键页面线框图》

- Git 仓库 cmab-mdm-platform 初始化

- Monorepo 目录结构搭建

- 后端 FastAPI 基础脚手架（含认证、数据库、Hello World API）

- 前端 React + Vite + Ant Design 基础脚手架（含登录页、布局）

- Docker Compose 开发环境配置

- README + 启动文档

### 里程碑

- M0.1：架构文档评审通过

- M0.2：脚手架可在本地启动，登录页可访问

## 8.3 Phase 1：SRS MVP（Month 2–4）

### 交付物

- SRS 数据库 schema 与 DDL 部署脚本

- SRS 后端 API（CRUD、编码生成、状态机、基础审计）

- Substance 列表 / 详情 / 表单页面（前端）

- mAb 模态扩展信息管理（重链/轻链序列、PTM）

- 内外部 ID 映射模块

- Substance Steward 审核工作流（简化版）

- 基础审计日志记录

- 单元测试覆盖率 ≥ 70%

### 里程碑

- M1.1：能注册新 mAb substance，分配编码

- M1.2：能编辑、查询、状态变更

- M1.3：审计日志可查询

- M1.4：内部演示验收

## 8.4 Phase 2：PRS + 跨域引用（Month 5–6）

### 交付物

- PRS 完整后端模块

- PRS 前端模块（列表、详情、表单、状态机）

- 跨域引用 ref schema 与 API

- Substance ↔ Project 双向关联视图

- 全局搜索功能（substance + project）

- 项目衍生关系（合并、拆分、衍生）

### 里程碑

- M2.1：能创建项目并关联 substance

- M2.2：在 substance 详情可看到关联项目，反之亦然

- M2.3：全局搜索可跨域返回结果

## 8.5 Phase 3：ARS + 合规强化（Month 7–8）

### 交付物

- ARS 完整模块（后端 + 前端）

- 电子签名功能（密码二次确认）

- 完整的 RBAC 权限管理

- 用户与角色管理界面

- 审计日志查询与导出

- 数据完整性触发器（变更前后值记录）

### 里程碑

- M3.1：ARS 模块上线

- M3.2：电子签名可正常使用

- M3.3：审计日志满足 Part 11 / Annex 11 要求

## 8.6 Phase 4：MM 基础域 + 生产部署准备（Month 9–10）

### 交付物

- MM Lite 基础域（R&D 物料 CRUD）+ 全局搜索 material 类型接入

- /auth/refresh 端点与会话安全收尾

- 独立审计日志页 + 审计导出基础能力

- 用户验收测试（UAT）报告、历史数据迁移脚本与数据迁移报告

- 生产级 Nginx / 部署配置 / 集中日志 / Prometheus metrics endpoint

- 数据库备份策略落地 + 至少一次恢复演练记录

- 用户培训材料 + 培训完成

- CSV 验证准备（URS / FS / DS / IQ / OQ / PQ 文档包启动）

### 里程碑

- M4.1：MM 基础域与 material 搜索接入完成

- M4.2：/auth/refresh、安全收尾与独立审计页完成

- M4.3：生产部署前置项、备份恢复演练与 UAT 完成

- M4.4：正式上线（Go-Live）

## 8.7 Phase 5+：数据治理与持续优化（Month 11+）

- 数据治理工具：substance merge / reject、batch create / update / delete、asset advance-phase 视需补充

- Redis 缓存层应用接入与性能优化

- 系统管理 Admin UI（用户 / 角色 / 权限矩阵 / 编码序列 / 字典 / 配置）

- ADC、双抗等其他模态扩展与复杂 fuzzy matching

- Substance 血缘关系图（React Flow 可视化）

- IDMP / GSRS 数据模型深化与 eCTD M3.2.S.1 自动生成探索

- ELN / LIMS / DMS / RIM 等下游系统集成深化

- 升级为生产级 GxP 系统的完整 CSV 验证（OQ / PQ）

## 8.8 团队配置

| **角色**          | **投入**   | **职责**                                |
|-------------------|------------|-----------------------------------------|
| 产品负责人 / 业务 | 1 人（兼） | 需求决策、业务规则确认（CMC Head 兼任） |
| 业务专家          | 1–2 人     | Substance / Project 业务规则细节        |
| 后端开发          | 1–2 人     | FastAPI、PostgreSQL、业务逻辑           |
| 前端开发          | 1 人       | React、Ant Design                       |
| DevOps            | 0.5 人     | 部署、CI/CD、监控（兼）                 |
| QA                | 0.5 人     | 测试、合规验证（兼）                    |

最小可行团队：1 后端 + 1 前端 + 1 PO + 1 业务专家 = 4 人。

## 8.9 风险识别与应对

| **风险**             | **影响** | **应对**                             |
|----------------------|----------|--------------------------------------|
| 业务规则反复迭代     | 中       | Phase 0 详尽设计 + 配置化设计        |
| 前端开发资源紧张     | 高       | 招聘 / 外包 / AI 辅助开发            |
| 历史数据脏，迁移困难 | 中       | Phase 4 前进行 data profiling 与清洗 |
| 组织变革阻力         | 高       | 提前建立 Data Steward 制度，强化培训 |
| 合规要求变化         | 低       | 保持架构灵活性，配置化合规规则       |
| 性能瓶颈             | 低       | PostgreSQL 16 性能足够本期规模       |
| 跨系统集成复杂       | 中       | API-First 设计，预留集成接口         |
| CSV 验证范围扩大     | 中       | Phase 1 定位 R&D 工具，分阶段验证    |

# 9. 业界对标与参考

## 9.1 头部药企 MDM 实践

以下为头部药企在主数据管理的公开实践，供本项目参考：

| **公司** | **Substance Master** | **Project Master** | **Material Master** | **架构模式** |
|----|----|----|----|----|
| Roche / Genentech | 自研 SRS（IDMP-aligned） | 自研 PMP | SAP S/4HANA | 三系统协同 + Informatica MDM |
| Pfizer | Reltio MDM | 自研 + Planisware | SAP | 商业 + 自研混合 |
| Novartis | 自研 + Veeva Vault | Planview | SAP | Veeva RIM 联动 |
| AstraZeneca | 自研（IDMP-aligned） | 自研 PMO 平台 | SAP MDG | 全自研集成 |
| Daiichi Sankyo | 自研 | — | SAP | ADC 主数据强治理 |
| BMS | Informatica + 自研 | 自研 PMO | SAP | 并购整合驱动 |
| Merck (MSD) | Veeva Vault + 自研 | Planisware | SAP | RIM 联动 |
| J&J | Veeva Vault + 自研 | 自研 | SAP | 多事业部统一 |

> ⚠ 信息核对建议
> 上述信息来源于各公司投资者日材料、技术大会演讲、Veeva/Informatica/Reltio 客户案例、行业分析报告。
> 细节可能随时间变化，引用前请核对：
> • 各公司年报与 Investor Day 材料
> • Veeva / Informatica / Reltio 官方客户案例库
> • Pistoia Alliance、PhUSE 等行业组织公开演讲材料
> • 学术期刊（如 Drug Discovery Today）相关文章

## 9.2 商业 MDM 平台对比

| **平台**           | **定位**      | **适用场景**                     |
|--------------------|---------------|----------------------------------|
| Informatica MDM    | 通用 MDM 龙头 | 大型药企、复杂多域、深度数据治理 |
| Reltio             | 云原生 MDM    | 中大型药企、追求云端弹性         |
| SAP MDG            | ERP 集成 MDM  | SAP 环境深度集成需求             |
| Stibo Systems STEP | 多域 MDM      | 复杂产品主数据                   |
| Veeva Vault        | 生命科学专用  | RIM/QMS/Clinical 联动场景        |
| Semarchy xDM       | 中型企业 MDM  | 性价比方案                       |

## 9.3 开源参考项目

| **项目** | **归属** | **可参考价值** |
|----|----|----|
| FDA GSRS | FDA + EMA | Substance 数据模型对齐、序列匹配算法（Java 开源） |
| Pistoia Alliance UDM | 行业联盟 | Unified Data Model 概念参考 |
| OpenSILEX | 学术 | 实验数据管理参考 |
| BridgeDB | 学术 | 外部 ID 映射参考 |

## 9.4 本项目的独特价值

- 结合 SMP-RD-NUM-001 V2.1 的语义中性原则，避免国内大量药企早期 IT 系统的设计误区

- 从第一天就考虑 IDMP 对齐，为 FDA/EMA 转型铺路

- 利用 cmc_data_platform 已有 PostgreSQL 基础设施，降低部署复杂度

- FastAPI + Python 技术栈与 RAGFlow 知识库、CMC 数据平台保持一致

- 自研 + 未来商业平台并行的演进路径，规避一次性巨额投资风险

# 10. 附录

## 10.1 关键缩略语

| **缩略语** | **全称**                                           |
|------------|----------------------------------------------------|
| MDM        | Master Data Management                             |
| SRS        | Substance Registration System                      |
| PRS        | Project Registration System                        |
| ARS        | Asset Registration System                          |
| MM         | Material Master                                    |
| REF        | Cross-Reference Layer                              |
| RBAC       | Role-Based Access Control                          |
| JWT        | JSON Web Token                                     |
| ORM        | Object-Relational Mapping                          |
| API        | Application Programming Interface                  |
| URS        | User Requirement Specification                     |
| FS         | Functional Specification                           |
| DS         | Design Specification                               |
| IQ/OQ/PQ   | Installation/Operational/Performance Qualification |
| CSV        | Computer System Validation                         |
| GxP        | Good x Practice (GMP/GLP/GCP 等)                   |
| INN        | International Nonproprietary Name                  |
| UNII       | Unique Ingredient Identifier (FDA)                 |
| IDMP       | Identification of Medicinal Products (ISO)         |
| GSRS       | Global Substance Registration System               |
| eCTD       | electronic Common Technical Document               |
| DAR        | Drug-to-Antibody Ratio                             |
| PTM        | Post-Translational Modification                    |
| DMS        | Document Management System                         |
| ELN        | Electronic Laboratory Notebook                     |
| LIMS       | Laboratory Information Management System           |
| QMS        | Quality Management System                          |
| RIM        | Regulatory Information Management                  |

## 10.2 参考文献

- CMAB 内部文档：SMP-RD-NUM-001 V2.1《研发资产与项目编号管理 SOP》

- CMAB 内部文档：DQS-MAN-001 V1.0《开发质量体系手册》

- CMAB 内部文档：PLAN-IT-MDM-001 V1.0《主数据管理 3-5 年战略规划》

- FDA 21 CFR Part 11：Electronic Records; Electronic Signatures（最新版核对 FDA 官网）

- EU GMP Annex 11：Computerised Systems（最新版核对欧盟委员会官网）

- ICH Q9(R1)：Quality Risk Management

- ICH Q14：Analytical Procedure Development

- ICH Q2(R2)：Validation of Analytical Procedures

- ICH Q12：Lifecycle Management

- ICH Q5E：Comparability of Biotechnological/Biological Products

- ISO 11238：Health informatics — Identification of medicinal products — Substances

- ISO 11239 / 11240 / 11615 / 11616：IDMP 系列其他标准

- FDA GSRS GitHub：https://github.com/ncats/inxight-substances

- C4 Model：https://c4model.com/

- Simon Brown：《Software Architecture for Developers》

## 10.3 后续文档清单

本架构文档之后的详细设计文档：

| **文档编号** | **文档名称** | **状态** |
|----|----|----|
| DM-MDM-001 | 数据模型设计文档（ERD + DDL） | V1.1 Draft（已按 DEV-MDM-001 V1.2 吸收关键修订） |
| API-MDM-001 | API 接口规范（OpenAPI 3.0） | V1.1 Draft（已统一 meta.error.type / 路线图口径） |
| UI-MDM-001 | UI 信息架构与线框图 | V1.1 Draft（已补 ARS 资产域 UI 与状态/阶段语义） |
| DEV-MDM-001 | 开发规范与编码标准 | V1.2 Draft（设计基准偏离说明） |
| TEST-MDM-001 | 测试策略与计划 | 待编制 |
| DEPLOY-MDM-001 | 部署与运维手册 | 待编制 |
| URS-MDM-001 | 用户需求规格说明 | 待编制 |
| TRAIN-MDM-001 | 用户培训材料 | 待编制 |

## 10.4 文档评审建议

建议本架构文档在 Phase 0 内完成以下评审：

22. CMC IT 内部技术评审

23. CMC R&D 业务评审（业务规则与流程）

24. QA / 注册评审（合规要求）

25. 公司 IT / 信息安全评审（基础设施与安全）

26. 管理层批准（投资与资源决策）

## 10.5 联系与反馈

文档维护者：CMC IT 架构组

反馈渠道：项目协作平台 / 邮件

文档更新策略：重大变更触发版本升级，小修订记录在修订记录表

## 10.6 未实施项路线图（V1.1 新增）

本架构文档 V1.1 结合 DEV-MDM-001 V1.2 的实施偏离说明，统一后续阶段路线图如下。Phase 1-3 已完成 SRS / PRS / ARS / REF 核心域闭环；Phase 4 聚焦 MM 基础域、生产部署前置项与合规运行准备；Phase 5 聚焦数据治理工具、性能优化与 Admin 工具。

| **未实施项** | **文档引用** | **当前状态** | **目标 Phase** | **备注** |
|----|----|----|----|----|
| Redis 缓存层应用层接入 | §4.2 容器图 / §7.2.1 第 6 步 | 容器已部署，应用层未集成；JWT 即时失效改用 password_changed_at 实现 | Phase 5 性能优化 | 当前 dev 数据量无瓶颈 |
| Prometheus metrics endpoint | §4.3 组件图（未画 metrics 端点） | 未实现 | Phase 4 生产部署前 | 与可观测性建设打包 |
| 集中日志收集（ELK / Splunk） | §4.5 部署视图 | 仅 stdout loguru，日志目录 /var/log/cmab-mdm/ 本地保留 | Phase 4 生产部署前 | 与生产日志留存策略打包 |
| 生产级 Nginx 反代 + k8s manifest | §4.5 部署视图 | 仅 docker-compose dev 配置 | Phase 4 生产部署前 | 当前部署形态见 §5.3 |
| 数据库备份策略落地 | §7.4 备份与灾备 | 策略已定义，未部署执行 | Phase 4 生产部署前 | 必须完成至少一次恢复演练并形成可审计记录 |
| CI 门禁 schema 一致性检查脚本 | §5.2 开发工具链 | 未实现 | Phase 4 | 比对 information_schema 与 DM-MDM-001 V1.1 DDL diff |
| 完整 CSV 验证（URS / FS / DS / IQ / OQ / PQ） | §7.5 CSV 验证策略 | Phase 1 R&D 工具简化版完成 | Phase 2 GxP 升级时（上线后 6-12 月） | 与现行分阶段验证策略一致 |
| /auth/refresh 端点 | §7.2.1 认证流程第 5 步 | 未实现，当前 access_token 30min 过期需重登 | Phase 4 安全收尾 | 见 DEV-MDM-001 V1.2 §8.1.1 |
| MM 基础域与 material 搜索接入 | §3.2.4 / §6.1 / §8 路线图 | 物料域当前为设计预留 / UI 占位 | Phase 4 | 覆盖 R&D 物料基础 CRUD 与全局搜索 material 类型接入 |
| 数据治理工具（merge / reject / batch / advance-phase 视需） | SRS / ARS / 全局功能 | 当前未实施 | Phase 5 | 与数据治理工作流和批量维护工具打包 |

Phase 1-3 范围（substance / project / asset / ref）的核心设计路径已形成闭环，包括审计追踪、电子签名、权限控制、失败留痕与状态历史；但生产部署级控制、备份恢复演练、集中日志、完整 CSV 文档包以及 Phase 4-5 范围（material / admin / batch / 缓存 / 监控）仍按计划推迟。本文档不作"100% 合规"宣称。生产上线（Phase 4）前必须完成上表中标注「Phase 4 生产部署前」的全部项 + CSV 验证。
