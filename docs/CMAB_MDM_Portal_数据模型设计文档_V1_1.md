<!--
  本文件由 scripts/docs/extract_md.py 从 docx 自动派生，请勿手工修改。
  源文件:CMAB_MDM_Portal_数据模型设计文档_V1_1.docx
  重新生成:make docs-extract
  一致性校验:make docs-check
-->

**CMAB MDM Portal**

**数据模型设计文档**

*Data Model Design Document*

*ERD · DDL · Constraints · Indexes · Triggers*

| **文档编号** | DM-MDM-001        |
|--------------|-------------------|
| **版本**     | V1.1              |
| **状态**     | Draft             |
| **发布日期** | 2026-05-11        |
| **编制**     | CMC IT 架构组     |
| **上位文档** | ARCH-MDM-001 V1.1 |
| **数据库**   | PostgreSQL 16     |
| **分类**     | 内部技术文档      |

# 修订记录

| **版本** | **日期** | **修订人** | **修订内容** |
|----|----|----|----|
| V1.0 | 2026-05-11 | CMC IT 架构组 | 初始版本，定义所有 schema、表结构、约束、索引、触发器 |
| V1.1 | 2026-05-12 | CMC IT 架构组 | 吸收 DEV-MDM-001 V1.2 偏离说明：补 asset_status_history、project_status_history.e_signature_id、ref 关系表 soft-delete 一致性、parent_ref 审计触发器、asset_market_id.deleted_by、asset_phase discontinued 中文，以及 V1.1 实施侧 GUC 审计上下文说明。 |
| V1.2 | 2026-06-04 | CMC IT | 新增 eqp 设备主数据域（§10A）：eqp.equipment 主表 + EQP-yyyyXXXXXX 年度编码触发器 + 审计 v3；auth 新增 equipment:create/read/update 权限及 CMC_EQUIPMENT_ADMIN / CMC_WAREHOUSE_ADMIN 预置角色。定位为下游 CMC LabOps Portal 设备模块的数据上游。 |

## 适用范围

- 本文档为 CMAB MDM Portal 的数据库层设计依据

- 覆盖所有 schema、表、视图、索引、约束、触发器、函数、初始化数据

- 以 PostgreSQL 16 为目标数据库

- 作为 Alembic migration 脚本编写依据

- 作为 SQLAlchemy ORM 模型实现依据

- 作为 CSV 验证中数据完整性测试用例的输入

# 1. 概述

## 1.1 设计原则

1.  域分治：每个业务域独立 schema，避免跨域硬耦合

2.  语义中性编码：主键编码不携带业务含义，符合 SMP-RD-NUM-001 V2.1

3.  软删除：所有业务表禁止物理删除，使用 deleted_at 标记

4.  审计完整：所有 CRUD 操作记录到 audit schema

5.  时间统一 UTC：所有时间戳字段使用 TIMESTAMPTZ，UTC 存储

6.  数据完整性：通过外键 + CHECK 约束 + 触发器保证

7.  性能优先：合理使用索引、JSONB GIN 索引、分区（必要时）

8.  可扩展：通过 JSONB 字段承载异构属性，避免频繁 schema 变更

9.  可演进：为未来 schema 拆库（微服务化）预留路径

## 1.2 命名规范

### 1.2.1 数据库对象命名

| **对象类型** | **规范** | **示例** |
|----|----|----|
| Schema | 小写，简短，对应业务域 | srs, prs, audit |
| 表名 | 小写 + 下划线，单数形式 | substance, project, audit_log |
| 主键 | \<table\>\_id（如表名长则简化） | substance_id, project_id |
| 外键 | 引用表名 + \_id | substance_id 在 prs.project 中 |
| 索引 | ix\_\<table\>\_\<columns\> | ix_substance_internal_code |
| 唯一索引 | uq\_\<table\>\_\<columns\> | uq_substance_substance_code |
| 主键约束 | pk\_\<table\> | pk_substance |
| 外键约束 | fk\_\<table\>\_\<ref_table\> | fk_project_substance |
| CHECK 约束 | ck\_\<table\>\_\<column\> | ck_substance_status |
| 触发器 | trg\_\<table\>\_\<event\> | trg_substance_audit |
| 函数 | fn\_\<purpose\> | fn_generate_substance_code |
| 视图 | v\_\<purpose\> | v_substance_with_projects |
| 序列 | seq\_\<purpose\> | seq_substance_code |

### 1.2.2 字段命名

- 主键：\<entity\>\_id（BIGINT，自增）

- 业务编码：\<entity\>\_code（VARCHAR，符合 SMP）

- 外键：直接使用被引用表的 \<entity\>\_id

- 时间戳：created_at、updated_at、deleted_at（TIMESTAMPTZ）

- 操作人：created_by、updated_by、deleted_by（BIGINT 引用 auth.user）

- 状态：status（VARCHAR，配合 CHECK 约束限定枚举值）

- 软删除：deleted_at IS NULL 表示有效

- 布尔字段：is_xxx 或 has_xxx

- JSONB 字段：以 \_info 或 \_data 结尾

## 1.3 数据类型选型规范

| **用途** | **类型** | **理由** |
|----|----|----|
| 主键 | BIGINT GENERATED ALWAYS AS IDENTITY | PostgreSQL 推荐方式，性能优于 SERIAL |
| 业务编码 | VARCHAR(32) | 足够容纳 SMP 编码，可索引 |
| 短文本 | VARCHAR(255) | 覆盖名称、标识等 |
| 长文本 | TEXT | 无长度限制，PostgreSQL 性能等同 VARCHAR |
| 时间戳 | TIMESTAMPTZ | 带时区，UTC 存储 |
| 日期 | DATE | 无时间部分（如里程碑日期） |
| 金额 | NUMERIC(18, 4) | 精确小数（预算等） |
| 布尔 | BOOLEAN | — |
| 枚举 | VARCHAR(32) + CHECK | 比 ENUM 类型更灵活，可加值无需迁移 |
| 异构属性 | JSONB | GIN 索引支持，适合 PTM、糖基化、附加属性 |
| 序列（生物） | TEXT | 氨基酸序列长度不固定 |
| 哈希值 | VARCHAR(64) | SHA-256 hex |
| IP 地址 | INET | PostgreSQL 原生类型 |
| UUID | UUID | 外部系统 ID 映射 |

> ⚠ 时区处理铁律
> 1. 数据库一律使用 TIMESTAMPTZ，存储 UTC 时间
> 2. 应用层接入时显式转换：from datetime import datetime; datetime.now(timezone.utc)
> 3. 前端展示按用户时区（默认 Asia/Shanghai）
> 4. 跨系统接口交换使用 ISO 8601 带时区格式
> 5. 切勿混用 TIMESTAMP（无时区），会导致审计追踪歧义

# 2. Schema 总览

## 2.1 Schema 列表

| **Schema** | **用途** | **主要表** | **数据规模预估** |
|----|----|----|----|
| auth | 认证与授权 | user, role, permission, user_role, role_permission | 用户 ~100 |
| meta | 元数据与配置 | code_sequence, lookup_value, system_config | ~1000 |
| srs | Substance Registration | substance, substance_protein, substance_xref, substance_status_history | Substance ~500（10年） |
| prs | Project Registration | project, project_milestone, project_team, project_status_history | Project ~200 |
| ars | Asset Registration | asset, asset_market_id, asset_status_history | Asset ~30 |
| mm | Material Master | material, material_batch, material_attribute | Material ~10000 |
| eqp | Equipment Master（V1.2 新增） | equipment | Equipment ~200 |
| ref | 跨域引用 | ref_project_substance, ref_asset_substance, ref_material_substance | 随业务 |
| audit | 审计追踪 | audit_log, change_history, e_signature | 高速增长 |

## 2.2 Schema 之间的依赖关系

```text
依赖方向（A → B 表示 A 引用 B）：

    prs ──→ srs        (项目引用物质)
    prs ──→ ars        (项目引用资产)
    ars ──→ srs        (资产引用物质)
    mm  ──→ srs        (物料引用物质)
    ref ──→ srs/prs/ars/mm  (引用层依赖所有业务域)

    audit ──→ auth     (审计引用用户)
    所有业务表 ──→ auth (创建人/修改人/删除人)
    所有业务表 ──→ audit (通过触发器写入)

    meta 被所有 schema 使用（编码生成、查找值、配置）

部署顺序：
    1. auth   (基础)
    2. meta   (基础)
    3. audit  (基础)
    4. srs    (业务核心)
    5. ars
    6. prs
    7. mm
    8. ref    (引用层)
    9. v_*    (视图，最后建)
```

## 2.3 数据库初始化与扩展

```sql
-- 创建数据库
CREATE DATABASE cmab_mdm
    WITH ENCODING 'UTF8'
         LC_COLLATE = 'en_US.UTF-8'
         LC_CTYPE = 'en_US.UTF-8'
         TEMPLATE = template0;

-- 切换到新数据库后执行
\c cmab_mdm

-- 启用必要扩展
CREATE EXTENSION IF NOT EXISTS "pgcrypto";       -- 加密、UUID 生成
CREATE EXTENSION IF NOT EXISTS "pg_trgm";        -- 模糊搜索（trigram）
CREATE EXTENSION IF NOT EXISTS "btree_gin";      -- 复合 GIN 索引
CREATE EXTENSION IF NOT EXISTS "unaccent";       -- 去重音搜索

-- 时区设为 UTC
ALTER DATABASE cmab_mdm SET timezone TO 'UTC';

-- 创建所有 schema
CREATE SCHEMA auth;
CREATE SCHEMA meta;
CREATE SCHEMA audit;
CREATE SCHEMA srs;
CREATE SCHEMA ars;
CREATE SCHEMA prs;
CREATE SCHEMA mm;
CREATE SCHEMA ref;

-- 默认搜索路径
ALTER DATABASE cmab_mdm SET search_path TO public, srs, prs, ars, mm, ref, auth, meta, audit;

-- 创建应用账号（最小权限）
CREATE ROLE cmab_app_user WITH LOGIN PASSWORD '<change_me>';
GRANT CONNECT ON DATABASE cmab_mdm TO cmab_app_user;
GRANT USAGE ON SCHEMA srs, prs, ars, mm, ref, auth, meta, audit TO cmab_app_user;

-- 创建审计审查账号（只读）
CREATE ROLE cmab_audit_reader WITH LOGIN PASSWORD '<change_me>';
GRANT CONNECT ON DATABASE cmab_mdm TO cmab_audit_reader;
GRANT USAGE ON SCHEMA audit TO cmab_audit_reader;
```

> ⚠ 权限分离设计
> 应用账号（cmab_app_user）：业务表 CRUD 权限，audit schema 仅 INSERT 不可 UPDATE/DELETE
> 审计审查账号（cmab_audit_reader）：仅读 audit schema，用于内部审计与外部检查
> DBA 账号（postgres）：完整权限，仅供 DBA 与 migration 使用
> 这种分离满足 21 CFR Part 11 关于审计日志不可篡改的要求

# 3. 实体关系图（ERD）

## 3.1 核心 ERD（业务域）

```text
┌─────────────────────────────────────────────────────────────────────┐
│                  CMAB MDM Portal 核心 ERD                           │
└─────────────────────────────────────────────────────────────────────┘

                       ┌──────────────────────┐
                       │   srs.substance      │
                       │  ─────────────────   │
                       │  PK substance_id     │◄──────┐
                       │  UQ substance_code   │       │
                       │     substance_type   │       │
                       │     status           │       │
                       └──────┬───────────────┘       │
                              │ 1:1 (按类型)          │
                              │                       │
                  ┌───────────┼───────────┐           │
                  ▼           ▼           ▼           │
          ┌─────────────┐ ┌──────────┐ ┌─────────┐    │
          │ substance_  │ │substance │ │substance│    │
          │ protein     │ │  _adc    │ │_small_  │    │
          │ (mAb/双抗等)│ │  (ADC)   │ │molecule │    │
          └─────────────┘ └──────────┘ └─────────┘    │
                                                      │
                  ┌───────────────────────────────────┤
                  │                                   │
                  │ 1:N                            1:N│
                  ▼                                   │
          ┌──────────────────┐                        │
          │ substance_xref   │                        │
          │ (内外部 ID 映射) │                        │
          └──────────────────┘                        │
                                                      │
   ┌──────────────────────────────────────────────────┤
   │                                                  │
   │ M:N（通过 ref）                                  │
   │                                                  │
   ▼                                                  │
┌──────────────────────┐    M:N    ┌──────────────────┐│
│ ref.project_         │◄─────────►│   prs.project    ││
│ substance            │           │  ──────────────  ││
└──────────────────────┘           │ PK project_id    ││
                                   │ UQ project_code  ││
                                   │    status        ││
                                   └────┬─────────────┘│
                                        │ M:N          │
                                        ▼              │
                            ┌──────────────────────┐   │
                            │ ref.asset_substance  │◄──┘
                            └────────┬─────────────┘
                                     │
                                     ▼
                            ┌──────────────────┐
                            │   ars.asset      │
                            │  ──────────────  │
                            │ PK asset_id      │
                            │ UQ asset_code    │
                            │    status        │
                            └────┬─────────────┘
                                 │ 1:N
                                 ▼
                       ┌─────────────────────┐
                       │ ars.asset_market_id │
                       │ (NDC/EMA/NMPA 等)   │
                       └─────────────────────┘

                            ┌──────────────────┐
                            │   mm.material    │──→ srs.substance
                            │  ──────────────  │
                            │ PK material_id   │
                            │ UQ material_code │
                            └────┬─────────────┘
                                 │ 1:N
                                 ▼
                       ┌─────────────────────┐
                       │  mm.material_batch  │
                       └─────────────────────┘
```

## 3.2 支撑层 ERD（auth / audit / meta）

```text
┌──────────────────────────────────────────────────────────────────┐
│                      认证与权限                                  │
└──────────────────────────────────────────────────────────────────┘

   ┌────────────┐     ┌──────────────┐     ┌────────────┐
   │ auth.user  │ M:N │auth.user_role│ M:N │ auth.role  │
   │ ────────── │◄────┤              ├────►│ ────────── │
   │PK user_id  │     │ user_id (FK) │     │PK role_id  │
   │UQ username │     │ role_id (FK) │     │   role_name│
   └────────────┘     └──────────────┘     └─────┬──────┘
                                                 │ M:N
                                                 ▼
                                         ┌──────────────────┐
                                         │auth.role_         │
                                         │ permission       │
                                         └────────┬─────────┘
                                                  │ M:N
                                                  ▼
                                         ┌──────────────────┐
                                         │ auth.permission  │
                                         │ ──────────────── │
                                         │ PK permission_id │
                                         │   resource       │
                                         │   action         │
                                         └──────────────────┘

┌──────────────────────────────────────────────────────────────────┐
│                       审计与合规                                 │
└──────────────────────────────────────────────────────────────────┘

   ┌─────────────────┐    1:N    ┌─────────────────────┐
   │ audit.audit_log │──────────►│ audit.change_history│
   │ ─────────────── │           │ ─────────────────── │
   │PK log_id        │           │PK history_id        │
   │   user_id  (FK) │           │   audit_log_id (FK) │
   │   action        │           │   field_name        │
   │   entity_*      │           │   old_value (JSONB) │
   │   timestamp     │           │   new_value (JSONB) │
   └─────────────────┘           └─────────────────────┘

   ┌──────────────────┐
   │audit.e_signature │
   │ ──────────────── │
   │PK signature_id   │
   │   user_id (FK)   │
   │   entity_*       │
   │   meaning        │
   │   signed_at      │
   │   signature_hash │
   └──────────────────┘

┌──────────────────────────────────────────────────────────────────┐
│                        元数据                                    │
└──────────────────────────────────────────────────────────────────┘

   ┌────────────────────┐  ┌──────────────────┐  ┌────────────────┐
   │ meta.code_sequence │  │meta.lookup_value │  │meta.system_    │
   │  (编码序列管理)    │  │  (枚举字典)      │  │ config         │
   └────────────────────┘  └──────────────────┘  └────────────────┘
```

# 4. Schema: auth（认证与权限）

## 4.1 表清单

| **表名**              | **用途**               |
|-----------------------|------------------------|
| auth.user             | 用户主表               |
| auth.role             | 角色表                 |
| auth.permission       | 权限表                 |
| auth.user_role        | 用户-角色关联          |
| auth.role_permission  | 角色-权限关联          |
| auth.login_history    | 登录历史               |
| auth.password_history | 密码历史（防重复使用） |

## 4.2 auth.user

### 4.2.1 字段定义

| **字段** | **类型** | **约束** | **说明** |
|----|----|----|----|
| user_id | BIGINT | PK, IDENTITY | 主键 |
| username | VARCHAR(64) | UNIQUE, NOT NULL | 登录名（不可改） |
| email | VARCHAR(255) | UNIQUE, NOT NULL | 邮箱 |
| password_hash | VARCHAR(255) | NOT NULL | bcrypt 哈希 |
| full_name | VARCHAR(128) | NOT NULL | 姓名 |
| full_name_en | VARCHAR(128) | NULL | 英文姓名（外部接口） |
| department | VARCHAR(64) | NULL | 部门 |
| title | VARCHAR(64) | NULL | 职位 |
| phone | VARCHAR(32) | NULL | 电话 |
| status | VARCHAR(16) | NOT NULL DEFAULT 'active' | active/locked/disabled |
| failed_login_count | INT | NOT NULL DEFAULT 0 | 连续失败次数 |
| last_login_at | TIMESTAMPTZ | NULL | 最后登录时间 |
| password_changed_at | TIMESTAMPTZ | NULL | 密码上次修改时间 |
| password_expires_at | TIMESTAMPTZ | NULL | 密码过期时间 |
| mfa_enabled | BOOLEAN | NOT NULL DEFAULT FALSE | 是否启用 MFA（预留） |
| created_at | TIMESTAMPTZ | NOT NULL DEFAULT NOW() | 创建时间 |
| created_by | BIGINT | NULL | 创建人 |
| updated_at | TIMESTAMPTZ | NOT NULL DEFAULT NOW() | 更新时间 |
| updated_by | BIGINT | NULL | 更新人 |
| deleted_at | TIMESTAMPTZ | NULL | 软删除时间 |
| deleted_by | BIGINT | NULL | 删除人 |

### 4.2.2 DDL

```sql
CREATE TABLE auth.user (
    user_id              BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    username             VARCHAR(64)  NOT NULL,
    email                VARCHAR(255) NOT NULL,
    password_hash        VARCHAR(255) NOT NULL,
    full_name            VARCHAR(128) NOT NULL,
    full_name_en         VARCHAR(128),
    department           VARCHAR(64),
    title                VARCHAR(64),
    phone                VARCHAR(32),
    status               VARCHAR(16)  NOT NULL DEFAULT 'active',
    failed_login_count   INT          NOT NULL DEFAULT 0,
    last_login_at        TIMESTAMPTZ,
    password_changed_at  TIMESTAMPTZ,
    password_expires_at  TIMESTAMPTZ,
    mfa_enabled          BOOLEAN      NOT NULL DEFAULT FALSE,
    created_at           TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    created_by           BIGINT,
    updated_at           TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    updated_by           BIGINT,
    deleted_at           TIMESTAMPTZ,
    deleted_by           BIGINT,

    CONSTRAINT uq_user_username UNIQUE (username),
    CONSTRAINT uq_user_email    UNIQUE (email),
    CONSTRAINT ck_user_status   CHECK (status IN ('active','locked','disabled'))
);

CREATE INDEX ix_user_status     ON auth.user(status) WHERE deleted_at IS NULL;
CREATE INDEX ix_user_department ON auth.user(department) WHERE deleted_at IS NULL;

COMMENT ON TABLE  auth.user IS '系统用户主表';
COMMENT ON COLUMN auth.user.username IS '登录名，唯一，不可修改';
COMMENT ON COLUMN auth.user.password_hash IS 'bcrypt 哈希，cost ≥ 12';
COMMENT ON COLUMN auth.user.status IS '账号状态：active=正常，locked=锁定（如登录失败超限），disabled=禁用';
```

## 4.3 auth.role

```sql
CREATE TABLE auth.role (
    role_id          BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    role_code        VARCHAR(32)  NOT NULL,
    role_name        VARCHAR(64)  NOT NULL,
    description      TEXT,
    is_system        BOOLEAN      NOT NULL DEFAULT FALSE,  -- 系统预置角色不可删
    created_at       TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    created_by       BIGINT,
    updated_at       TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    updated_by       BIGINT,
    deleted_at       TIMESTAMPTZ,
    deleted_by       BIGINT,

    CONSTRAINT uq_role_code UNIQUE (role_code)
);

COMMENT ON TABLE auth.role IS '角色表';

-- 系统预置角色
INSERT INTO auth.role (role_code, role_name, description, is_system) VALUES
    ('SYS_ADMIN',          '系统管理员',     '全权限，仅限 IT',                     TRUE),
    ('SUBSTANCE_STEWARD',  '物质数据管家',   'Substance 域审核、合并、状态变更',    TRUE),
    ('PROJECT_MANAGER',    '项目经理',       'Project 域全权限',                    TRUE),
    ('CMC_RESEARCHER',     '研发人员',       '物质/项目读写（受范围限制）',         TRUE),
    ('QA_REVIEWER',        '质量审核',       '电子签名权限',                        TRUE),
    ('REGULATORY_USER',    '注册人员',       '查询所有数据，导出申报材料',          TRUE),
    ('READ_ONLY_USER',     '只读用户',       '仅可查询，不可修改',                  TRUE);
```

## 4.4 auth.permission

```sql
CREATE TABLE auth.permission (
    permission_id    BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    permission_code  VARCHAR(64)  NOT NULL,
    resource         VARCHAR(64)  NOT NULL,   -- 资源：substance, project, asset, material...
    action           VARCHAR(32)  NOT NULL,   -- 动作：create, read, update, delete, approve, sign
    description      TEXT,
    is_system        BOOLEAN      NOT NULL DEFAULT FALSE,
    created_at       TIMESTAMPTZ  NOT NULL DEFAULT NOW(),

    CONSTRAINT uq_permission_code     UNIQUE (permission_code),
    CONSTRAINT uq_permission_res_act  UNIQUE (resource, action)
);

COMMENT ON TABLE auth.permission IS '权限表，按 resource+action 定义';

-- 系统预置权限
INSERT INTO auth.permission (permission_code, resource, action, is_system, description) VALUES
    ('substance:create',  'substance', 'create',  TRUE, '创建物质'),
    ('substance:read',    'substance', 'read',    TRUE, '查询物质'),
    ('substance:update',  'substance', 'update',  TRUE, '更新物质'),
    ('substance:approve', 'substance', 'approve', TRUE, '审核物质'),
    ('substance:sign',    'substance', 'sign',    TRUE, '物质电子签名'),
    ('project:create',    'project',   'create',  TRUE, '创建项目'),
    ('project:read',      'project',   'read',    TRUE, '查询项目'),
    ('project:update',    'project',   'update',  TRUE, '更新项目'),
    ('project:approve',   'project',   'approve', TRUE, '审核项目'),
    ('project:sign',      'project',   'sign',    TRUE, '项目电子签名'),
    ('asset:create',      'asset',     'create',  TRUE, '创建资产'),
    ('asset:read',        'asset',     'read',    TRUE, '查询资产'),
    ('asset:update',      'asset',     'update',  TRUE, '更新资产'),
    ('asset:sign',        'asset',     'sign',    TRUE, '资产电子签名'),
    ('material:create',   'material',  'create',  TRUE, '创建物料'),
    ('material:read',     'material',  'read',    TRUE, '查询物料'),
    ('material:update',   'material',  'update',  TRUE, '更新物料'),
    ('audit:read',        'audit',     'read',    TRUE, '查询审计日志'),
    ('user:manage',       'user',      'manage',  TRUE, '用户管理'),
    ('role:manage',       'role',      'manage',  TRUE, '角色管理');
```

## 4.5 auth.user_role 与 auth.role_permission

```sql
-- 用户-角色关联
CREATE TABLE auth.user_role (
    user_id        BIGINT       NOT NULL,
    role_id        BIGINT       NOT NULL,
    granted_at     TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    granted_by     BIGINT,
    expires_at     TIMESTAMPTZ,

    CONSTRAINT pk_user_role        PRIMARY KEY (user_id, role_id),
    CONSTRAINT fk_user_role_user   FOREIGN KEY (user_id) REFERENCES auth.user(user_id),
    CONSTRAINT fk_user_role_role   FOREIGN KEY (role_id) REFERENCES auth.role(role_id)
);

CREATE INDEX ix_user_role_user ON auth.user_role(user_id);
CREATE INDEX ix_user_role_role ON auth.user_role(role_id);

-- 角色-权限关联
CREATE TABLE auth.role_permission (
    role_id        BIGINT       NOT NULL,
    permission_id  BIGINT       NOT NULL,
    granted_at     TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    granted_by     BIGINT,

    CONSTRAINT pk_role_permission       PRIMARY KEY (role_id, permission_id),
    CONSTRAINT fk_role_permission_role  FOREIGN KEY (role_id) REFERENCES auth.role(role_id),
    CONSTRAINT fk_role_permission_perm  FOREIGN KEY (permission_id) REFERENCES auth.permission(permission_id)
);
```

## 4.6 auth.login_history 与 auth.password_history

```sql
-- 登录历史
CREATE TABLE auth.login_history (
    login_id        BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    user_id         BIGINT,
    username_input  VARCHAR(64)  NOT NULL,   -- 即使用户不存在也记录
    success         BOOLEAN      NOT NULL,
    failure_reason  VARCHAR(64),
    ip_address      INET         NOT NULL,
    user_agent      TEXT,
    login_at        TIMESTAMPTZ  NOT NULL DEFAULT NOW(),

    CONSTRAINT fk_login_history_user FOREIGN KEY (user_id) REFERENCES auth.user(user_id)
);

CREATE INDEX ix_login_history_user_at ON auth.login_history(user_id, login_at DESC);
CREATE INDEX ix_login_history_at      ON auth.login_history(login_at DESC);

-- 密码历史（防止重复使用最近 N 个密码）
CREATE TABLE auth.password_history (
    history_id     BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    user_id        BIGINT       NOT NULL,
    password_hash  VARCHAR(255) NOT NULL,
    changed_at     TIMESTAMPTZ  NOT NULL DEFAULT NOW(),

    CONSTRAINT fk_password_history_user FOREIGN KEY (user_id) REFERENCES auth.user(user_id)
);

CREATE INDEX ix_password_history_user ON auth.password_history(user_id, changed_at DESC);
```

# 5. Schema: meta（元数据）

## 5.1 meta.code_sequence（编码序列管理）

用于生成各域的业务编码（SUB-、PRJ-、AST-、MAT- 等），保证全局唯一与并发安全。

```sql
CREATE TABLE meta.code_sequence (
    sequence_id      BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    sequence_name    VARCHAR(64)  NOT NULL,    -- 如 'substance', 'project_2026'
    prefix           VARCHAR(16)  NOT NULL,    -- 如 'SUB-', 'PRJ-2026-'
    current_value    BIGINT       NOT NULL DEFAULT 0,
    padding_length   INT          NOT NULL DEFAULT 7,   -- SUB- 后 7 位
    increment_step   INT          NOT NULL DEFAULT 1,
    description      TEXT,
    created_at       TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    updated_at       TIMESTAMPTZ  NOT NULL DEFAULT NOW(),

    CONSTRAINT uq_code_sequence_name UNIQUE (sequence_name)
);

-- 初始化序列
INSERT INTO meta.code_sequence (sequence_name, prefix, padding_length, description) VALUES
    ('substance', 'SUB-', 7, 'Substance 编码序列：SUB-0000001 ...'),
    ('asset',     'AST-', 4, 'Asset 编码序列：AST-0001 ...');

-- 项目和物料按年生成，使用专用函数动态创建年份序列
-- 例如：'project_2026' prefix='PRJ-2026-' padding=4

-- 编码生成函数（事务内串行化，并发安全）
CREATE OR REPLACE FUNCTION meta.fn_next_code(p_sequence_name VARCHAR)
RETURNS VARCHAR AS $$
DECLARE
    v_prefix         VARCHAR;
    v_value          BIGINT;
    v_padding        INT;
    v_step           INT;
BEGIN
    -- 行级锁，防并发冲突
    UPDATE meta.code_sequence
       SET current_value = current_value + increment_step,
           updated_at    = NOW()
     WHERE sequence_name = p_sequence_name
    RETURNING prefix, current_value, padding_length, increment_step
        INTO v_prefix, v_value, v_padding, v_step;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'Code sequence % not found', p_sequence_name;
    END IF;

    RETURN v_prefix || LPAD(v_value::text, v_padding, '0');
END;
$$ LANGUAGE plpgsql;

-- 自动创建年份序列函数（项目、物料用）
CREATE OR REPLACE FUNCTION meta.fn_ensure_year_sequence(
    p_base_name VARCHAR,    -- 'project' or 'material'
    p_prefix    VARCHAR,    -- 'PRJ-' or 'MAT-'
    p_year      INT,
    p_padding   INT
) RETURNS VARCHAR AS $$
DECLARE
    v_seq_name VARCHAR;
BEGIN
    v_seq_name := p_base_name || '_' || p_year::text;

    INSERT INTO meta.code_sequence (sequence_name, prefix, padding_length, description)
    VALUES (v_seq_name, p_prefix || p_year::text || '-', p_padding,
            p_base_name || ' 编码 ' || p_year || ' 年序列')
    ON CONFLICT (sequence_name) DO NOTHING;

    RETURN v_seq_name;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION meta.fn_next_code IS '生成下一个业务编码，并发安全';
```

> 💡 使用示例
> -- 生成 substance 编码
> SELECT meta.fn_next_code('substance');     -- 'SUB-0000123'
>
> -- 生成 2026 年项目编码
> SELECT meta.fn_ensure_year_sequence('project', 'PRJ-', 2026, 4);
> SELECT meta.fn_next_code('project_2026');  -- 'PRJ-2026-0123'

## 5.2 meta.lookup_value（枚举字典）

```sql
CREATE TABLE meta.lookup_value (
    lookup_id        BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    lookup_type      VARCHAR(64)  NOT NULL,
    lookup_code      VARCHAR(64)  NOT NULL,
    lookup_name      VARCHAR(128) NOT NULL,
    lookup_name_en   VARCHAR(128),
    sort_order       INT          NOT NULL DEFAULT 0,
    is_active        BOOLEAN      NOT NULL DEFAULT TRUE,
    description      TEXT,
    extra            JSONB,
    created_at       TIMESTAMPTZ  NOT NULL DEFAULT NOW(),

    CONSTRAINT uq_lookup_type_code UNIQUE (lookup_type, lookup_code)
);

CREATE INDEX ix_lookup_type ON meta.lookup_value(lookup_type, sort_order) WHERE is_active = TRUE;

-- 部分初始化数据
INSERT INTO meta.lookup_value (lookup_type, lookup_code, lookup_name, lookup_name_en, sort_order) VALUES
    -- substance 状态
    ('substance_status', 'draft',       '草稿',     'Draft',       10),
    ('substance_status', 'registered',  '已注册',   'Registered',  20),
    ('substance_status', 'active',      '活跃',     'Active',      30),
    ('substance_status', 'restricted',  '受限',     'Restricted',  40),
    ('substance_status', 'deprecated',  '已弃用',   'Deprecated',  50),
    ('substance_status', 'obsoleted',   '已废止',   'Obsoleted',   60),

    -- substance 类型
    ('substance_type', 'mab',            '单克隆抗体',  'Monoclonal Antibody', 10),
    ('substance_type', 'bispecific',     '双特异性抗体','Bispecific Antibody', 20),
    ('substance_type', 'adc',            'ADC',         'Antibody-Drug Conjugate', 30),
    ('substance_type', 'fusion',         '融合蛋白',    'Fusion Protein', 40),
    ('substance_type', 'small_molecule', '小分子',      'Small Molecule', 50),
    ('substance_type', 'oligonucleotide','寡核苷酸',    'Oligonucleotide', 60),

    -- 项目状态
    ('project_status', 'proposed',   '已提议', 'Proposed',   10),
    ('project_status', 'initiated',  '已启动', 'Initiated',  20),
    ('project_status', 'active',     '进行中', 'Active',     30),
    ('project_status', 'on_hold',    '暂停',   'On Hold',    40),
    ('project_status', 'completed',  '已完成', 'Completed',  50),
    ('project_status', 'terminated', '已终止', 'Terminated', 60),

    -- 项目类型
    ('project_type', 'cmc',         'CMC 项目',     'CMC Project',         10),
    ('project_type', 'preclinical', '临床前',       'Pre-Clinical',        20),
    ('project_type', 'clinical',    '临床',         'Clinical',            30),
    ('project_type', 'regulatory',  '注册',         'Regulatory',          40),
    ('project_type', 'commercial',  '商业化',       'Commercial',          50),

    -- 资产阶段
    ('asset_phase', 'discovery',  '发现',     'Discovery',     10),
    ('asset_phase', 'preclinical','临床前',   'Pre-Clinical',  20),
    ('asset_phase', 'phase_1',    'I 期',     'Phase I',       30),
    ('asset_phase', 'phase_2',    'II 期',    'Phase II',      40),
    ('asset_phase', 'phase_3',    'III 期',   'Phase III',     50),
    ('asset_phase', 'submission', '申报',     'Submission',    60),
    ('asset_phase', 'approved',   '已批准',   'Approved',      70),
    ('asset_phase', 'marketed',   '已上市',   'Marketed',      80),
    ('asset_phase', 'discontinued','已停止上市', 'Discontinued',  90);
```

## 5.3 meta.system_config

```sql
CREATE TABLE meta.system_config (
    config_key       VARCHAR(64)  PRIMARY KEY,
    config_value     TEXT         NOT NULL,
    value_type       VARCHAR(16)  NOT NULL DEFAULT 'string',  -- string/int/bool/json
    description      TEXT,
    is_sensitive     BOOLEAN      NOT NULL DEFAULT FALSE,
    updated_at       TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    updated_by       BIGINT,

    CONSTRAINT ck_config_type CHECK (value_type IN ('string','int','bool','json'))
);

INSERT INTO meta.system_config (config_key, config_value, value_type, description) VALUES
    ('password.min_length',          '12',     'int',  '密码最小长度'),
    ('password.expire_days',         '90',     'int',  '密码有效期（天）'),
    ('password.history_count',       '5',      'int',  '不可重复使用最近 N 个密码'),
    ('login.max_failed_attempts',    '5',      'int',  '最大连续失败次数'),
    ('login.lock_duration_minutes',  '30',     'int',  '锁定时长'),
    ('session.access_token_minutes', '30',     'int',  'Access Token 有效期'),
    ('session.refresh_token_days',   '7',      'int',  'Refresh Token 有效期'),
    ('audit.retention_years',        '10',     'int',  '审计日志保留年限'),
    ('app.timezone_default',         'Asia/Shanghai', 'string', '默认显示时区'),
    ('app.locale_default',           'zh-CN',  'string', '默认语言');
```

# 6. Schema: audit（审计追踪）

## 6.1 设计原则

- audit schema 仅可 INSERT，不允许 UPDATE/DELETE（应用账号无 UPDATE/DELETE 权限）

- 所有业务表通过 AFTER 触发器写入审计

- 关键审批和签名事件通过应用层显式写入

- 审计数据保留至少 10 年（配置项 audit.retention_years）

- 满足 21 CFR Part 11 与 EU GMP Annex 11 数据完整性要求

## 6.2 audit.audit_log（审计主表）

```sql
CREATE TABLE audit.audit_log (
    log_id           BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    -- 操作者信息
    user_id          BIGINT,                  -- 系统操作时可空
    username         VARCHAR(64)  NOT NULL,   -- 冗余存储防用户改名
    session_id       VARCHAR(64),

    -- 操作上下文
    action           VARCHAR(32)  NOT NULL,   -- CREATE/READ/UPDATE/DELETE/APPROVE/SIGN/LOGIN/LOGOUT
    entity_schema    VARCHAR(32),             -- srs/prs/ars/mm
    entity_table     VARCHAR(64),
    entity_id        BIGINT,
    entity_code      VARCHAR(64),             -- 业务编码（substance_code 等），冗余便于查询

    -- 变更摘要
    change_summary   TEXT,                    -- 简短描述
    reason           TEXT,                    -- 变更原因（关键操作必填）

    -- 网络与请求
    ip_address       INET,
    user_agent       TEXT,
    request_id       VARCHAR(64),             -- 链路追踪 ID

    -- 时间
    timestamp        TIMESTAMPTZ  NOT NULL DEFAULT NOW(),

    -- 拓展字段
    extra            JSONB,

    CONSTRAINT ck_audit_action CHECK (action IN (
        'CREATE','READ','UPDATE','DELETE','RESTORE',
        'APPROVE','REJECT','SIGN',
        'LOGIN','LOGOUT','LOGIN_FAILED',
        'EXPORT','IMPORT','PERMISSION_CHANGE'
    ))
);

-- 高频查询索引
CREATE INDEX ix_audit_log_user_time   ON audit.audit_log(user_id, timestamp DESC);
CREATE INDEX ix_audit_log_entity      ON audit.audit_log(entity_schema, entity_table, entity_id);
CREATE INDEX ix_audit_log_entity_code ON audit.audit_log(entity_code);
CREATE INDEX ix_audit_log_timestamp   ON audit.audit_log(timestamp DESC);
CREATE INDEX ix_audit_log_action      ON audit.audit_log(action, timestamp DESC);

COMMENT ON TABLE  audit.audit_log IS '审计日志主表，所有用户操作必须记录';
COMMENT ON COLUMN audit.audit_log.username IS '冗余存储用户名，防用户改名后历史日志失真';
COMMENT ON COLUMN audit.audit_log.reason IS '关键操作必填的变更原因，用于合规审计';
```

## 6.3 audit.change_history（变更前后值）

```sql
CREATE TABLE audit.change_history (
    history_id       BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    audit_log_id     BIGINT       NOT NULL,
    field_name       VARCHAR(64)  NOT NULL,
    old_value        JSONB,                   -- 用 JSONB 兼容各种类型
    new_value        JSONB,

    CONSTRAINT fk_change_history_log FOREIGN KEY (audit_log_id)
        REFERENCES audit.audit_log(log_id)
);

CREATE INDEX ix_change_history_log ON audit.change_history(audit_log_id);

COMMENT ON TABLE audit.change_history IS '字段级变更前后值记录';
```

## 6.4 audit.e_signature（电子签名）

```sql
CREATE TABLE audit.e_signature (
    signature_id     BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    user_id          BIGINT       NOT NULL,
    username         VARCHAR(64)  NOT NULL,
    full_name        VARCHAR(128) NOT NULL,

    -- 签名对象
    entity_schema    VARCHAR(32)  NOT NULL,
    entity_table     VARCHAR(64)  NOT NULL,
    entity_id        BIGINT       NOT NULL,
    entity_code      VARCHAR(64),

    -- 签名意图与内容
    signature_meaning  VARCHAR(64) NOT NULL,  -- approve/review/release/witness
    signature_reason   TEXT        NOT NULL,

    -- 签名材料（被签名内容的哈希）
    signed_content_hash VARCHAR(64) NOT NULL, -- SHA-256
    signature_hash      VARCHAR(64) NOT NULL, -- 签名整体哈希

    -- 上下文
    ip_address       INET,
    user_agent       TEXT,

    signed_at        TIMESTAMPTZ  NOT NULL DEFAULT NOW(),

    -- 关联审计日志
    audit_log_id     BIGINT,

    CONSTRAINT fk_e_signature_user FOREIGN KEY (user_id) REFERENCES auth.user(user_id),
    CONSTRAINT fk_e_signature_log  FOREIGN KEY (audit_log_id) REFERENCES audit.audit_log(log_id),
    CONSTRAINT ck_e_signature_meaning CHECK (signature_meaning IN (
        'approve','review','release','witness','reject'
    ))
);

CREATE INDEX ix_e_signature_user   ON audit.e_signature(user_id, signed_at DESC);
CREATE INDEX ix_e_signature_entity ON audit.e_signature(entity_schema, entity_table, entity_id);

COMMENT ON TABLE audit.e_signature IS '电子签名记录，满足 21 CFR Part 11.50/11.70';
```

💡 签名失败与会话失效的审计分流（V1.1 新增）\
1. 业务身份再验证失败（签名密码错）：HTTP 401 + meta.error.type=signature_invalid；走'失败副作用旁路 session'（§15.2.2）写 audit_log.action='SIGN' 且 result=failed；不清前端 token。\
2. 会话失效（JWT 过期 / 无效 / 缺失）：HTTP 401 + meta.error.type=token_expired / token_invalid / token_missing；前端拦截器清 token 跳登录。\
3. \`meta.error.type\` 字典的完整定义参见 API-MDM-001 V1.1。\
4. 本数据模型层仅声明：audit_log + e_signature 表必须能区分上述两类 401 事件，便于合规审计时分流统计。

## 6.5 通用审计触发器函数

所有业务表通过统一触发器自动写入 audit.audit_log 与 audit.change_history。

```sql
CREATE OR REPLACE FUNCTION audit.fn_audit_trigger()RETURNS TRIGGER AS $$DECLARE    v_log_id        BIGINT;    v_user_id       BIGINT;    v_username      VARCHAR;    v_session_id    VARCHAR;    v_request_id    VARCHAR;    v_ip            INET;    v_action        VARCHAR;    v_entity_id     BIGINT;    v_entity_code   VARCHAR;    v_old_jsonb     JSONB;    v_new_jsonb     JSONB;    v_field         RECORD;BEGIN    -- V1.1 兼容兜底：如应用层显式设置安全请求上下文，可从 session GUC 读取；    -- 当前实施侧不依赖 SET LOCAL/GUC 作为审计 actor 唯一来源，actor / e_signature_id 由 service 层显式写入。    v_user_id    := NULLIF(current_setting('app.user_id',    TRUE), '')::BIGINT;    v_username   := COALESCE(NULLIF(current_setting('app.username',   TRUE), ''), 'system');    v_session_id := NULLIF(current_setting('app.session_id', TRUE), '');    v_request_id := NULLIF(current_setting('app.request_id', TRUE), '');    v_ip         := NULLIF(current_setting('app.ip_address', TRUE), '')::INET;        -- 解析 action    IF TG_OP = 'INSERT' THEN        v_action    := 'CREATE';        v_new_jsonb := to_jsonb(NEW);        v_entity_id := (v_new_jsonb ->> (TG_ARGV[0]))::BIGINT;        v_entity_code := v_new_jsonb ->> COALESCE(TG_ARGV[1], 'code');    -- V1.1: 第 3 参数 parent_ref 支持子表 entity_code 回填    -- 格式: '<schema>.<parent_table>:<parent_pk_col>:<parent_code_col>:<fk_col_on_this_table>'    IF TG_ARGV[2] IS NOT NULL AND TG_ARGV[2] != '' THEN        -- 解析 parent_ref, 按当前行 FK 查父表回填 v_entity_code        DECLARE            v_parts TEXT[] := string_to_array(TG_ARGV[2], ':');            v_parent_table TEXT := v_parts[1];            v_parent_pk TEXT := v_parts[2];            v_parent_code TEXT := v_parts[3];            v_fk_col TEXT := v_parts[4];            v_fk_val BIGINT;        BEGIN            v_fk_val := (COALESCE(v_new_jsonb, v_old_jsonb) ->> v_fk_col)::BIGINT;            EXECUTE format('SELECT %I FROM %s WHERE %I = $1', v_parent_code, v_parent_table, v_parent_pk)                INTO v_entity_code USING v_fk_val;        END;    END IF;    ELSIF TG_OP = 'UPDATE' THEN        -- 软删除特殊处理        IF OLD.deleted_at IS NULL AND NEW.deleted_at IS NOT NULL THEN            v_action := 'DELETE';        ELSIF OLD.deleted_at IS NOT NULL AND NEW.deleted_at IS NULL THEN            v_action := 'RESTORE';        ELSE            v_action := 'UPDATE';        END IF;        v_old_jsonb := to_jsonb(OLD);        v_new_jsonb := to_jsonb(NEW);        v_entity_id := (v_new_jsonb ->> (TG_ARGV[0]))::BIGINT;        v_entity_code := v_new_jsonb ->> COALESCE(TG_ARGV[1], 'code');    -- V1.1: 第 3 参数 parent_ref 支持子表 entity_code 回填    -- 格式: '<schema>.<parent_table>:<parent_pk_col>:<parent_code_col>:<fk_col_on_this_table>'    IF TG_ARGV[2] IS NOT NULL AND TG_ARGV[2] != '' THEN        -- 解析 parent_ref, 按当前行 FK 查父表回填 v_entity_code        DECLARE            v_parts TEXT[] := string_to_array(TG_ARGV[2], ':');            v_parent_table TEXT := v_parts[1];            v_parent_pk TEXT := v_parts[2];            v_parent_code TEXT := v_parts[3];            v_fk_col TEXT := v_parts[4];            v_fk_val BIGINT;        BEGIN            v_fk_val := (COALESCE(v_new_jsonb, v_old_jsonb) ->> v_fk_col)::BIGINT;            EXECUTE format('SELECT %I FROM %s WHERE %I = $1', v_parent_code, v_parent_table, v_parent_pk)                INTO v_entity_code USING v_fk_val;        END;    END IF;    ELSIF TG_OP = 'DELETE' THEN        v_action := 'DELETE';        v_old_jsonb := to_jsonb(OLD);        v_entity_id := (v_old_jsonb ->> (TG_ARGV[0]))::BIGINT;        v_entity_code := v_old_jsonb ->> COALESCE(TG_ARGV[1], 'code');    END IF;        -- 写入 audit_log    INSERT INTO audit.audit_log (        user_id, username, session_id, action,        entity_schema, entity_table, entity_id, entity_code,        ip_address, request_id    ) VALUES (        v_user_id, v_username, v_session_id, v_action,        TG_TABLE_SCHEMA, TG_TABLE_NAME, v_entity_id, v_entity_code,        v_ip, v_request_id    ) RETURNING log_id INTO v_log_id;        -- 写入 change_history（仅 UPDATE 写入变更字段）    IF TG_OP = 'UPDATE' THEN        FOR v_field IN             SELECT key, v_old_jsonb -> key AS old_v, v_new_jsonb -> key AS new_v              FROM jsonb_object_keys(v_new_jsonb) AS key             WHERE key NOT IN ('updated_at')   -- 排除自动更新字段        LOOP            IF v_field.old_v IS DISTINCT FROM v_field.new_v THEN                INSERT INTO audit.change_history (audit_log_id, field_name, old_value, new_value)                VALUES (v_log_id, v_field.key, v_field.old_v, v_field.new_v);            END IF;        END LOOP;    END IF;        RETURN COALESCE(NEW, OLD);END;$$ LANGUAGE plpgsql; COMMENT ON FUNCTION audit.fn_audit_trigger IS '通用审计触发器，所有业务表共用；V1.1 实施侧不依赖 SET LOCAL/GUC 作为审计 actor 唯一来源';
```

> 💡 V1.1 实施侧审计上下文说明
> V1.1 不再建议通过 FastAPI middleware 执行 SET LOCAL app.* 注入审计 actor。请求级 user / IP / request_id 可保存在 Python ContextVar 中，业务表 created_by / updated_by / e_signature_id 由 service 层显式赋值。
> -- 如未来重新启用数据库级请求上下文，必须先完成连接池隔离与泄漏测试；生产实现不得依赖未验证的 GUC 注入。
>
>
>
>
>
> 之后所有 SQL 操作都会被触发器自动审计，无需开发者额外编码。

# 7. Schema: srs（Substance Registration）

## 7.1 表清单

| **表名**                     | **用途**                            |
|------------------------------|-------------------------------------|
| srs.substance                | Substance 主表（所有类型通用字段）  |
| srs.substance_protein        | 蛋白类扩展（mAb / 双抗 / 融合蛋白） |
| srs.substance_adc            | ADC 扩展（父子 substance 血缘）     |
| srs.substance_small_molecule | 小分子扩展                          |
| srs.substance_xref           | 内外部 ID 映射                      |
| srs.substance_status_history | 状态变更历史                        |
| srs.substance_alias          | 曾用名 / 项目代号                   |

## 7.2 srs.substance（主表）

### 7.2.1 字段定义

| **字段** | **类型** | **约束** | **说明** |
|----|----|----|----|
| substance_id | BIGINT | PK, IDENTITY | 主键 |
| substance_code | VARCHAR(32) | UNIQUE, NOT NULL | 业务编码 SUB-XXXXXXX |
| substance_type | VARCHAR(32) | NOT NULL, CHECK | mab/bispecific/adc/fusion/small_molecule/oligo |
| internal_code | VARCHAR(64) | UNIQUE | 公司内部代号（如 CMAB-101） |
| preferred_name | VARCHAR(255) | NOT NULL | 首选名称（INN 优先 / 内部代号） |
| preferred_name_en | VARCHAR(255) | NULL | 英文首选名 |
| display_name | VARCHAR(255) | NULL | 展示名（前端用） |
| target | VARCHAR(128) | NULL | 靶点（如 PD-L1, HER2） |
| target_type | VARCHAR(64) | NULL | 受体/抗原/酶等 |
| modality | VARCHAR(64) | NULL | 细分模态描述 |
| status | VARCHAR(32) | NOT NULL DEFAULT 'draft' | 状态 |
| is_proprietary | BOOLEAN | NOT NULL DEFAULT TRUE | 是否专有 |
| confidentiality | VARCHAR(16) | NOT NULL DEFAULT 'internal' | 保密等级 public/internal/restricted |
| external_uuid | UUID | UNIQUE | 对外唯一标识符（IDMP/GSRS 对齐） |
| description | TEXT | NULL | 描述 |
| notes | TEXT | NULL | 备注 |
| extra | JSONB | NULL | 扩展属性 |
| created_at | TIMESTAMPTZ | NOT NULL | 创建时间 |
| created_by | BIGINT | NOT NULL | 创建人 |
| updated_at | TIMESTAMPTZ | NOT NULL | 更新时间 |
| updated_by | BIGINT | NOT NULL | 更新人 |
| registered_at | TIMESTAMPTZ | NULL | 正式注册时间 |
| registered_by | BIGINT | NULL | 注册审核人 |
| deleted_at | TIMESTAMPTZ | NULL | 软删除时间 |
| deleted_by | BIGINT | NULL | — |
| version | INT | NOT NULL DEFAULT 1 | 乐观锁版本号 |

### 7.2.2 DDL

```sql
CREATE TABLE srs.substance (
    substance_id       BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    substance_code     VARCHAR(32)  NOT NULL,
    substance_type     VARCHAR(32)  NOT NULL,
    internal_code      VARCHAR(64),
    preferred_name     VARCHAR(255) NOT NULL,
    preferred_name_en  VARCHAR(255),
    display_name       VARCHAR(255),
    target             VARCHAR(128),
    target_type        VARCHAR(64),
    modality           VARCHAR(64),
    status             VARCHAR(32)  NOT NULL DEFAULT 'draft',
    is_proprietary     BOOLEAN      NOT NULL DEFAULT TRUE,
    confidentiality    VARCHAR(16)  NOT NULL DEFAULT 'internal',
    external_uuid      UUID         DEFAULT gen_random_uuid(),
    description        TEXT,
    notes              TEXT,
    extra              JSONB,
    created_at         TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    created_by         BIGINT       NOT NULL,
    updated_at         TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    updated_by         BIGINT       NOT NULL,
    registered_at      TIMESTAMPTZ,
    registered_by      BIGINT,
    deleted_at         TIMESTAMPTZ,
    deleted_by         BIGINT,
    version            INT          NOT NULL DEFAULT 1,

    CONSTRAINT uq_substance_code         UNIQUE (substance_code),
    CONSTRAINT uq_substance_internal     UNIQUE (internal_code),
    CONSTRAINT uq_substance_external_uuid UNIQUE (external_uuid),
    CONSTRAINT ck_substance_type         CHECK (substance_type IN
        ('mab','bispecific','adc','fusion','small_molecule','oligonucleotide','other')),
    CONSTRAINT ck_substance_status       CHECK (status IN
        ('draft','registered','active','restricted','deprecated','obsoleted')),
    CONSTRAINT ck_substance_confidentiality CHECK (confidentiality IN
        ('public','internal','restricted')),
    CONSTRAINT fk_substance_created_by   FOREIGN KEY (created_by) REFERENCES auth.user(user_id),
    CONSTRAINT fk_substance_updated_by   FOREIGN KEY (updated_by) REFERENCES auth.user(user_id),
    CONSTRAINT fk_substance_registered_by FOREIGN KEY (registered_by) REFERENCES auth.user(user_id),
    CONSTRAINT fk_substance_deleted_by   FOREIGN KEY (deleted_by) REFERENCES auth.user(user_id)
);

-- 索引
CREATE INDEX ix_substance_type           ON srs.substance(substance_type) WHERE deleted_at IS NULL;
CREATE INDEX ix_substance_status         ON srs.substance(status) WHERE deleted_at IS NULL;
CREATE INDEX ix_substance_target         ON srs.substance(target) WHERE deleted_at IS NULL;
CREATE INDEX ix_substance_preferred_name ON srs.substance USING gin(preferred_name gin_trgm_ops);
CREATE INDEX ix_substance_internal_code  ON srs.substance(internal_code) WHERE deleted_at IS NULL;
CREATE INDEX ix_substance_extra          ON srs.substance USING gin(extra);

COMMENT ON TABLE  srs.substance IS 'Substance 主表，物质身份的唯一权威源';
COMMENT ON COLUMN srs.substance.substance_code IS '业务编码 SUB-XXXXXXX，符合 SMP-RD-NUM-001 V2.1';
COMMENT ON COLUMN srs.substance.external_uuid IS '对外 UUID，用于 IDMP/GSRS 等外部系统对齐';
COMMENT ON COLUMN srs.substance.version IS '乐观锁版本号，每次 UPDATE 自动 +1';

-- 自动 updated_at 触发器
CREATE OR REPLACE FUNCTION srs.fn_substance_before_update()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at := NOW();
    NEW.version    := OLD.version + 1;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_substance_before_update
BEFORE UPDATE ON srs.substance
FOR EACH ROW EXECUTE FUNCTION srs.fn_substance_before_update();

-- 审计触发器
CREATE TRIGGER trg_substance_audit
AFTER INSERT OR UPDATE OR DELETE ON srs.substance
FOR EACH ROW EXECUTE FUNCTION audit.fn_audit_trigger('substance_id', 'substance_code');

-- 自动生成 substance_code（如果未提供）
CREATE OR REPLACE FUNCTION srs.fn_substance_assign_code()
RETURNS TRIGGER AS $$
BEGIN
    IF NEW.substance_code IS NULL OR NEW.substance_code = '' THEN
        NEW.substance_code := meta.fn_next_code('substance');
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_substance_assign_code
BEFORE INSERT ON srs.substance
FOR EACH ROW EXECUTE FUNCTION srs.fn_substance_assign_code();
```

## 7.3 srs.substance_protein（蛋白扩展）

```sql
CREATE TABLE srs.substance_protein (    substance_id          BIGINT       NOT NULL,        -- 序列信息    heavy_chain_sequence  TEXT,                       -- 重链氨基酸序列（FASTA 格式或纯序列）    light_chain_sequence  TEXT,    additional_chains     JSONB,                      -- 双抗/融合蛋白的额外链    sequence_length_hc    INT,    sequence_length_lc    INT,    sequence_hash_hc      VARCHAR(64),                -- SHA-256，用于快速 sameness 比对    sequence_hash_lc      VARCHAR(64),        -- 结构信息    isotype               VARCHAR(32),                -- IgG1/IgG2/IgG4/scFv/Fab 等    architecture          VARCHAR(64),                -- KIH/CrossMAb/DuoBody/Common Light Chain 等    disulfide_bonds       JSONB,                      -- 二硫键拓扑    glycosylation_sites   JSONB,                      -- N-/O-糖基化位点    ptm_info              JSONB,                      -- 翻译后修饰        -- 表达系统    expression_system     VARCHAR(64),                -- CHO/HEK293/E.coli 等    cell_line             VARCHAR(128),    expression_vector     VARCHAR(128),        -- 物理化学性质    molecular_weight_da   NUMERIC(10, 2),             -- 计算或测定的分子量    pi_theoretical        NUMERIC(5, 2),    extinction_coefficient INT,        -- 元数据    created_at            TIMESTAMPTZ  NOT NULL DEFAULT NOW(),    updated_at            TIMESTAMPTZ  NOT NULL DEFAULT NOW(),        CONSTRAINT pk_substance_protein PRIMARY KEY (substance_id),    CONSTRAINT fk_substance_protein_substance FOREIGN KEY (substance_id)         REFERENCES srs.substance(substance_id) ON DELETE CASCADE); -- 序列哈希索引（sameness 快速比对）CREATE INDEX ix_substance_protein_hc_hash ON srs.substance_protein(sequence_hash_hc);CREATE INDEX ix_substance_protein_lc_hash ON srs.substance_protein(sequence_hash_lc); -- 自动计算序列哈希CREATE OR REPLACE FUNCTION srs.fn_substance_protein_compute_hash()RETURNS TRIGGER AS $$BEGIN    IF NEW.heavy_chain_sequence IS NOT NULL THEN        NEW.sequence_hash_hc := encode(digest(NEW.heavy_chain_sequence, 'sha256'), 'hex');        NEW.sequence_length_hc := length(regexp_replace(NEW.heavy_chain_sequence, '[^A-Z]', '', 'g'));    END IF;    IF NEW.light_chain_sequence IS NOT NULL THEN        NEW.sequence_hash_lc := encode(digest(NEW.light_chain_sequence, 'sha256'), 'hex');        NEW.sequence_length_lc := length(regexp_replace(NEW.light_chain_sequence, '[^A-Z]', '', 'g'));    END IF;    NEW.updated_at := NOW();    RETURN NEW;END;$$ LANGUAGE plpgsql; CREATE TRIGGER trg_substance_protein_compute_hashBEFORE INSERT OR UPDATE ON srs.substance_proteinFOR EACH ROW EXECUTE FUNCTION srs.fn_substance_protein_compute_hash(); CREATE TRIGGER trg_substance_protein_auditAFTER INSERT OR UPDATE OR DELETE ON srs.substance_proteinFOR EACH ROW EXECUTE FUNCTION audit.fn_audit_trigger('substance_id', NULL, 'srs.substance:substance_id:substance_code:substance_id');
```

## 7.4 srs.substance_adc（ADC 扩展）

```sql
CREATE TABLE srs.substance_adc (    substance_id            BIGINT  PRIMARY KEY,        -- 父子 substance 引用    antibody_substance_id   BIGINT  NOT NULL,    linker_substance_id     BIGINT,    payload_substance_id    BIGINT  NOT NULL,        -- DAR    dar_average             NUMERIC(4, 2),    dar_distribution        JSONB,           -- {"DAR0":0.05, "DAR2":0.20, ...}    dar_method              VARCHAR(64),     -- HIC/MS/UV        -- 偶联化学    conjugation_chemistry   VARCHAR(64),     -- maleimide-thiol/click/site-specific 等    conjugation_site        VARCHAR(128),    -- inter-chain disulfide / engineered cysteine 等        -- 元数据    created_at              TIMESTAMPTZ  NOT NULL DEFAULT NOW(),    updated_at              TIMESTAMPTZ  NOT NULL DEFAULT NOW(),        CONSTRAINT fk_substance_adc_self      FOREIGN KEY (substance_id)         REFERENCES srs.substance(substance_id) ON DELETE CASCADE,    CONSTRAINT fk_substance_adc_antibody  FOREIGN KEY (antibody_substance_id)         REFERENCES srs.substance(substance_id),    CONSTRAINT fk_substance_adc_linker    FOREIGN KEY (linker_substance_id)         REFERENCES srs.substance(substance_id),    CONSTRAINT fk_substance_adc_payload   FOREIGN KEY (payload_substance_id)         REFERENCES srs.substance(substance_id),    CONSTRAINT ck_substance_adc_dar       CHECK (dar_average IS NULL OR (dar_average >= 0 AND dar_average <= 30))); CREATE INDEX ix_substance_adc_antibody ON srs.substance_adc(antibody_substance_id);CREATE INDEX ix_substance_adc_payload  ON srs.substance_adc(payload_substance_id); CREATE TRIGGER trg_substance_adc_auditAFTER INSERT OR UPDATE OR DELETE ON srs.substance_adcFOR EACH ROW EXECUTE FUNCTION audit.fn_audit_trigger('substance_id', NULL, 'srs.substance:substance_id:substance_code:substance_id'); COMMENT ON TABLE  srs.substance_adc IS 'ADC 扩展表，建模父子 substance 血缘关系';COMMENT ON COLUMN srs.substance_adc.dar_distribution IS 'DAR 分布数据，JSONB 格式';
```

## 7.5 srs.substance_small_molecule（小分子扩展）

```sql
CREATE TABLE srs.substance_small_molecule (    substance_id        BIGINT  PRIMARY KEY,        smiles              TEXT,    inchi               TEXT,    inchi_key           VARCHAR(27),         -- 27 字符标准长度    molecular_formula   VARCHAR(64),    molecular_weight    NUMERIC(10, 4),        salt_form           VARCHAR(64),    crystal_form        VARCHAR(64),    stereochemistry     VARCHAR(64),         -- chiral/racemic/achiral        extra               JSONB,    created_at          TIMESTAMPTZ  NOT NULL DEFAULT NOW(),    updated_at          TIMESTAMPTZ  NOT NULL DEFAULT NOW(),        CONSTRAINT fk_substance_sm_self FOREIGN KEY (substance_id)         REFERENCES srs.substance(substance_id) ON DELETE CASCADE); CREATE UNIQUE INDEX uq_substance_sm_inchi_key ON srs.substance_small_molecule(inchi_key)     WHERE inchi_key IS NOT NULL; CREATE TRIGGER trg_substance_sm_auditAFTER INSERT OR UPDATE OR DELETE ON srs.substance_small_moleculeFOR EACH ROW EXECUTE FUNCTION audit.fn_audit_trigger('substance_id', NULL, 'srs.substance:substance_id:substance_code:substance_id');
```

## 7.6 srs.substance_xref（内外部 ID 映射）

```sql
CREATE TABLE srs.substance_xref (    xref_id          BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,    substance_id     BIGINT       NOT NULL,    xref_type        VARCHAR(32)  NOT NULL,  -- INN/USAN/CAS/UNII/GSRS_UUID/ChEMBL/TRADE_NAME/HISTORICAL_CODE    xref_value       VARCHAR(255) NOT NULL,    xref_source      VARCHAR(64),            -- 来源（WHO/FDA/EMA 等）    region           VARCHAR(16),            -- 适用市场（CN/US/EU/Global）    is_primary       BOOLEAN      NOT NULL DEFAULT FALSE,    effective_date   DATE,    expiry_date      DATE,    notes            TEXT,        created_at       TIMESTAMPTZ  NOT NULL DEFAULT NOW(),    created_by       BIGINT       NOT NULL,    updated_at       TIMESTAMPTZ  NOT NULL DEFAULT NOW(),    updated_by       BIGINT       NOT NULL,    deleted_at       TIMESTAMPTZ,    deleted_by       BIGINT,        CONSTRAINT fk_substance_xref_substance FOREIGN KEY (substance_id)         REFERENCES srs.substance(substance_id),    CONSTRAINT ck_substance_xref_type CHECK (xref_type IN (        'INN','USAN','CAS','UNII','GSRS_UUID','ChEMBL','DRUGBANK',        'TRADE_NAME','GENERIC_NAME','HISTORICAL_CODE','PROJECT_CODE','OTHER'    ))); CREATE UNIQUE INDEX uq_substance_xref_type_value ON srs.substance_xref(xref_type, xref_value)     WHERE deleted_at IS NULL;CREATE INDEX ix_substance_xref_substance ON srs.substance_xref(substance_id);CREATE INDEX ix_substance_xref_value     ON srs.substance_xref(xref_value); CREATE TRIGGER trg_substance_xref_auditAFTER INSERT OR UPDATE OR DELETE ON srs.substance_xrefFOR EACH ROW EXECUTE FUNCTION audit.fn_audit_trigger('xref_id', NULL, 'srs.substance:substance_id:substance_code:substance_id'); COMMENT ON TABLE srs.substance_xref IS '物质内外部标识符映射，是 IND/BLA/MAA 申报的金标准来源';
```

## 7.7 srs.substance_status_history（状态变更历史）

```sql
CREATE TABLE srs.substance_status_history (
    history_id        BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    substance_id      BIGINT       NOT NULL,
    old_status        VARCHAR(32),
    new_status        VARCHAR(32)  NOT NULL,
    change_reason     TEXT         NOT NULL,
    changed_at        TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    changed_by        BIGINT       NOT NULL,
    e_signature_id    BIGINT,                          -- 关键状态变更需电子签名

    -- 合并/弃用专用
    merged_to_substance_id  BIGINT,                    -- 合并到哪个 substance

    CONSTRAINT fk_substance_status_history_sub FOREIGN KEY (substance_id)
        REFERENCES srs.substance(substance_id),
    CONSTRAINT fk_substance_status_history_user FOREIGN KEY (changed_by)
        REFERENCES auth.user(user_id),
    CONSTRAINT fk_substance_status_history_sig FOREIGN KEY (e_signature_id)
        REFERENCES audit.e_signature(signature_id),
    CONSTRAINT fk_substance_status_history_merge FOREIGN KEY (merged_to_substance_id)
        REFERENCES srs.substance(substance_id)
);

CREATE INDEX ix_substance_status_history_sub ON srs.substance_status_history(substance_id, changed_at DESC);

-- 状态变更自动记录触发器
CREATE OR REPLACE FUNCTION srs.fn_substance_status_change()
RETURNS TRIGGER AS $$
BEGIN
    IF OLD.status IS DISTINCT FROM NEW.status THEN
        INSERT INTO srs.substance_status_history (
            substance_id, old_status, new_status, change_reason, changed_by
        ) VALUES (
            NEW.substance_id, OLD.status, NEW.status,
            'status changed',
            NEW.updated_by
        );
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- V1.1：change_reason 由 service 层在 INSERT status_history 后显式 UPDATE 回填，
-- 触发器仅写入默认值占位，不依赖 PostgreSQL session GUC。

CREATE TRIGGER trg_substance_status_change
AFTER UPDATE ON srs.substance
FOR EACH ROW EXECUTE FUNCTION srs.fn_substance_status_change();
```

## 7.8 srs.substance_alias（曾用名）

```sql
CREATE TABLE srs.substance_alias (
    alias_id         BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    substance_id     BIGINT       NOT NULL,
    alias_value      VARCHAR(255) NOT NULL,
    alias_type       VARCHAR(32),             -- nickname/legacy/project/typo
    notes            TEXT,
    created_at       TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    created_by       BIGINT       NOT NULL,
    deleted_at       TIMESTAMPTZ,

    CONSTRAINT fk_substance_alias_sub FOREIGN KEY (substance_id)
        REFERENCES srs.substance(substance_id)
);

CREATE INDEX ix_substance_alias_value     ON srs.substance_alias USING gin(alias_value gin_trgm_ops);
CREATE INDEX ix_substance_alias_substance ON srs.substance_alias(substance_id);
```

# 8. Schema: ars（Asset Registration）

## 8.1 表清单

| **表名**                 | **用途**         |
|--------------------------|------------------|
| ars.asset                | 资产主表         |
| ars.asset_market_id      | 多市场注册标识符 |
| ars.asset_status_history | 资产状态变更历史 |

## 8.2 ars.asset

```sql
CREATE TABLE ars.asset (
    asset_id            BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    asset_code          VARCHAR(32)  NOT NULL,

    -- 基本信息
    internal_name       VARCHAR(255) NOT NULL,
    trade_name          VARCHAR(255),                     -- 商品名（可多市场）
    inn_name            VARCHAR(255),                     -- 通用名 INN

    -- 资产属性
    asset_type          VARCHAR(32)  NOT NULL,            -- mab/bispecific/adc/fusion/...
    therapeutic_area    VARCHAR(64),                      -- oncology/autoimmune/...
    indication          TEXT,                             -- 适应症
    dosage_form         VARCHAR(64),                      -- 注射剂/冻干粉等
    strength            VARCHAR(64),                      -- 规格
    route_of_administration VARCHAR(32),                  -- IV/SC/IM/...

    -- 阶段
    current_phase       VARCHAR(32)  NOT NULL DEFAULT 'discovery',
    phase_change_at     TIMESTAMPTZ,

    -- 状态
    status              VARCHAR(32)  NOT NULL DEFAULT 'active',

    -- 商业属性
    is_commercial       BOOLEAN      NOT NULL DEFAULT FALSE,
    first_approval_date DATE,
    first_launch_date   DATE,

    -- 描述
    description         TEXT,
    notes               TEXT,
    extra               JSONB,

    -- 审计字段
    created_at          TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    created_by          BIGINT       NOT NULL,
    updated_at          TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    updated_by          BIGINT       NOT NULL,
    deleted_at          TIMESTAMPTZ,
    deleted_by          BIGINT,
    version             INT          NOT NULL DEFAULT 1,

    CONSTRAINT uq_asset_code  UNIQUE (asset_code),
    CONSTRAINT ck_asset_type  CHECK (asset_type IN
        ('mab','bispecific','adc','fusion','small_molecule','combination','other')),
    CONSTRAINT ck_asset_phase CHECK (current_phase IN
        ('discovery','preclinical','phase_1','phase_2','phase_3',
         'submission','approved','marketed','discontinued')),
    CONSTRAINT ck_asset_status CHECK (status IN ('active','on_hold','terminated')),
    CONSTRAINT fk_asset_created_by FOREIGN KEY (created_by) REFERENCES auth.user(user_id),
    CONSTRAINT fk_asset_updated_by FOREIGN KEY (updated_by) REFERENCES auth.user(user_id)
);

CREATE INDEX ix_asset_type   ON ars.asset(asset_type)    WHERE deleted_at IS NULL;
CREATE INDEX ix_asset_phase  ON ars.asset(current_phase) WHERE deleted_at IS NULL;
CREATE INDEX ix_asset_status ON ars.asset(status)        WHERE deleted_at IS NULL;
CREATE INDEX ix_asset_name   ON ars.asset USING gin(internal_name gin_trgm_ops);
CREATE INDEX ix_asset_trade  ON ars.asset USING gin(trade_name gin_trgm_ops);

CREATE TRIGGER trg_asset_audit
AFTER INSERT OR UPDATE OR DELETE ON ars.asset
FOR EACH ROW EXECUTE FUNCTION audit.fn_audit_trigger('asset_id', 'asset_code');

CREATE OR REPLACE FUNCTION ars.fn_asset_assign_code()
RETURNS TRIGGER AS $$
BEGIN
    IF NEW.asset_code IS NULL OR NEW.asset_code = '' THEN
        NEW.asset_code := meta.fn_next_code('asset');
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_asset_assign_code
BEFORE INSERT ON ars.asset
FOR EACH ROW EXECUTE FUNCTION ars.fn_asset_assign_code();
```

## 8.3 ars.asset_market_id（多市场注册标识符）

```sql
CREATE TABLE ars.asset_market_id (    market_id_pk     BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,    asset_id         BIGINT       NOT NULL,        market_code      VARCHAR(8)   NOT NULL,    -- CN/US/EU/JP/...    id_type          VARCHAR(32)  NOT NULL,    -- NDC/EMA_PROCEDURE/NMPA_APPROVAL/PMDA/...    id_value         VARCHAR(128) NOT NULL,    issuing_authority VARCHAR(128),        application_date DATE,    approval_date    DATE,    expiry_date      DATE,    status           VARCHAR(32),             -- pending/approved/withdrawn/expired        notes            TEXT,    created_at       TIMESTAMPTZ  NOT NULL DEFAULT NOW(),    created_by       BIGINT       NOT NULL,    updated_at       TIMESTAMPTZ  NOT NULL DEFAULT NOW(),    updated_by       BIGINT       NOT NULL,    deleted_at       TIMESTAMPTZ,    deleted_by       BIGINT,        CONSTRAINT fk_asset_market_id_deleted_by FOREIGN KEY (deleted_by) REFERENCES auth.user(user_id),    CONSTRAINT uq_asset_market_id      UNIQUE (asset_id, market_code, id_type, id_value),    CONSTRAINT fk_asset_market_id_asset FOREIGN KEY (asset_id) REFERENCES ars.asset(asset_id)); CREATE INDEX ix_asset_market_id_asset ON ars.asset_market_id(asset_id); CREATE TRIGGER trg_asset_market_id_auditAFTER INSERT OR UPDATE OR DELETE ON ars.asset_market_idFOR EACH ROW EXECUTE FUNCTION audit.fn_audit_trigger('market_id_pk', NULL, 'ars.asset:asset_id:asset_code:asset_id');
```

## 8.4 ars.asset_status_history（状态变更历史）

CREATE TABLE ars.asset_status_history (\
history_id BIGINT GENERATED ALWAYS AS IDENTITY,\
asset_id BIGINT NOT NULL,\
old_status VARCHAR(32),\
new_status VARCHAR(32) NOT NULL,\
change_reason TEXT NOT NULL,\
changed_at TIMESTAMPTZ DEFAULT NOW(),\
changed_by BIGINT NOT NULL,\
e_signature_id BIGINT, -- 仅 terminate 动作强制非空（21 CFR Part 11 §11.50）\
CONSTRAINT pk_asset_status_history PRIMARY KEY (history_id),\
CONSTRAINT fk_asset_status_history_asset FOREIGN KEY (asset_id) REFERENCES ars.asset(asset_id),\
CONSTRAINT fk_asset_status_history_user FOREIGN KEY (changed_by) REFERENCES auth.user(user_id),\
CONSTRAINT fk_asset_status_history_sig FOREIGN KEY (e_signature_id) REFERENCES audit.e_signature(signature_id)\
);\
\
COMMENT ON COLUMN ars.asset_status_history.e_signature_id IS '电子签名记录 FK。仅 terminate 动作强制非空（关键不可逆动作，21 CFR Part 11 §11.50）；hold / resume 等可逆状态变更不要求电子签名，本字段可为空。约束由 service 层校验（SIGNATURE_REQUIRED_ACTIONS = {"terminate"}），DB 层不加 CHECK 以保留扩展性。';\
\
CREATE INDEX ix_asset_status_history_asset ON ars.asset_status_history (asset_id, changed_at DESC);

CREATE OR REPLACE FUNCTION ars.fn_asset_status_change()

RETURNS TRIGGER AS \$\$

BEGIN

IF OLD.status IS DISTINCT FROM NEW.status THEN

INSERT INTO ars.asset_status_history (

asset_id, old_status, new_status, change_reason, changed_by

) VALUES (

NEW.asset_id, OLD.status, NEW.status,

'status changed',

NEW.updated_by

);

END IF;

RETURN NEW;

END;

\$\$ LANGUAGE plpgsql;

-- V1.1：change_reason 由 service 层在 INSERT status_history 后显式 UPDATE 回填，

-- 触发器仅写入默认值占位，不依赖 PostgreSQL session GUC。

CREATE TRIGGER trg_asset_status_change

AFTER UPDATE ON ars.asset

FOR EACH ROW EXECUTE FUNCTION ars.fn_asset_status_change();

-- 章节注释：ars.asset 状态机 3 值（active / on_hold / terminated），3 个动作（hold / resume / terminate）。

-- 仅 terminate 是关键不可逆动作，强制电签；hold / resume 是可逆调整，不强制电签。

-- 该约束与 §7.7 substance（4 个签字动作）/ §9.5 project（3 个签字动作）模式一致。

-- 签字范围由各域 service 层 SIGNATURE_REQUIRED_ACTIONS 集合定义，DM 层不在状态机字段加 CHECK。

# 9. Schema: prs（Project Registration）

## 9.1 表清单

| **表名**                   | **用途**          |
|----------------------------|-------------------|
| prs.project                | 项目主表          |
| prs.project_milestone      | 项目里程碑        |
| prs.project_team           | 项目团队成员      |
| prs.project_status_history | 项目状态变更历史  |
| prs.project_relationship   | 项目衍生/合并关系 |

## 9.2 prs.project

```sql
CREATE TABLE prs.project (
    project_id          BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    project_code        VARCHAR(32)  NOT NULL,

    -- 基本信息
    project_name        VARCHAR(255) NOT NULL,
    project_name_en     VARCHAR(255),
    project_type        VARCHAR(32)  NOT NULL,
    project_phase       VARCHAR(32),                     -- 当前所处阶段

    -- 层级
    parent_project_id   BIGINT,                          -- 子项目指向父项目
    program_name        VARCHAR(128),                    -- 所属 Program

    -- 时间
    planned_start_date  DATE,
    planned_end_date    DATE,
    actual_start_date   DATE,
    actual_end_date     DATE,

    -- 资源
    project_manager_id  BIGINT,
    sponsor_id          BIGINT,
    department          VARCHAR(64),

    -- 预算
    budget_total        NUMERIC(18, 2),
    budget_currency     VARCHAR(8) DEFAULT 'CNY',
    budget_actual       NUMERIC(18, 2),

    -- 目标与范围
    objective           TEXT,
    scope               TEXT,
    deliverables        TEXT,
    success_criteria    TEXT,

    -- 状态
    status              VARCHAR(32)  NOT NULL DEFAULT 'proposed',
    priority            VARCHAR(16),                     -- high/medium/low

    -- 保密性
    confidentiality     VARCHAR(16)  NOT NULL DEFAULT 'internal',

    -- 描述
    description         TEXT,
    notes               TEXT,
    extra               JSONB,

    -- 审计字段
    created_at          TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    created_by          BIGINT       NOT NULL,
    updated_at          TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    updated_by          BIGINT       NOT NULL,
    deleted_at          TIMESTAMPTZ,
    deleted_by          BIGINT,
    version             INT          NOT NULL DEFAULT 1,

    CONSTRAINT uq_project_code   UNIQUE (project_code),
    CONSTRAINT ck_project_type   CHECK (project_type IN
        ('cmc','preclinical','clinical','regulatory','commercial','platform','other')),
    CONSTRAINT ck_project_status CHECK (status IN
        ('proposed','initiated','active','on_hold','completed','terminated')),
    CONSTRAINT ck_project_conf   CHECK (confidentiality IN ('public','internal','restricted')),
    CONSTRAINT ck_project_dates  CHECK (planned_end_date IS NULL OR planned_start_date IS NULL
        OR planned_end_date >= planned_start_date),
    CONSTRAINT fk_project_parent  FOREIGN KEY (parent_project_id) REFERENCES prs.project(project_id),
    CONSTRAINT fk_project_pm      FOREIGN KEY (project_manager_id) REFERENCES auth.user(user_id),
    CONSTRAINT fk_project_sponsor FOREIGN KEY (sponsor_id) REFERENCES auth.user(user_id),
    CONSTRAINT fk_project_created_by FOREIGN KEY (created_by) REFERENCES auth.user(user_id),
    CONSTRAINT fk_project_updated_by FOREIGN KEY (updated_by) REFERENCES auth.user(user_id)
);

CREATE INDEX ix_project_status      ON prs.project(status) WHERE deleted_at IS NULL;
CREATE INDEX ix_project_type        ON prs.project(project_type) WHERE deleted_at IS NULL;
CREATE INDEX ix_project_pm          ON prs.project(project_manager_id);
CREATE INDEX ix_project_parent      ON prs.project(parent_project_id);
CREATE INDEX ix_project_dates       ON prs.project(planned_start_date, planned_end_date);
CREATE INDEX ix_project_name        ON prs.project USING gin(project_name gin_trgm_ops);

CREATE TRIGGER trg_project_audit
AFTER INSERT OR UPDATE OR DELETE ON prs.project
FOR EACH ROW EXECUTE FUNCTION audit.fn_audit_trigger('project_id', 'project_code');

-- 自动生成 project_code（按年）
CREATE OR REPLACE FUNCTION prs.fn_project_assign_code()
RETURNS TRIGGER AS $$
DECLARE
    v_year     INT;
    v_seq_name VARCHAR;
BEGIN
    IF NEW.project_code IS NULL OR NEW.project_code = '' THEN
        v_year := EXTRACT(YEAR FROM NOW())::INT;
        v_seq_name := meta.fn_ensure_year_sequence('project', 'PRJ-', v_year, 4);
        NEW.project_code := meta.fn_next_code(v_seq_name);
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_project_assign_code
BEFORE INSERT ON prs.project
FOR EACH ROW EXECUTE FUNCTION prs.fn_project_assign_code();
```

## 9.3 prs.project_milestone

```sql
CREATE TABLE prs.project_milestone (    milestone_id     BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,    project_id       BIGINT       NOT NULL,    milestone_name   VARCHAR(128) NOT NULL,    milestone_type   VARCHAR(32),             -- gate/deliverable/decision    planned_date     DATE         NOT NULL,    actual_date      DATE,    status           VARCHAR(32)  NOT NULL DEFAULT 'planned',    description      TEXT,        created_at       TIMESTAMPTZ  NOT NULL DEFAULT NOW(),    created_by       BIGINT       NOT NULL,    updated_at       TIMESTAMPTZ  NOT NULL DEFAULT NOW(),    updated_by       BIGINT       NOT NULL,        CONSTRAINT fk_project_milestone_project FOREIGN KEY (project_id)         REFERENCES prs.project(project_id) ON DELETE CASCADE,    CONSTRAINT ck_project_milestone_status CHECK (status IN         ('planned','in_progress','completed','delayed','cancelled'))); CREATE INDEX ix_project_milestone_project ON prs.project_milestone(project_id, planned_date); CREATE TRIGGER trg_project_milestone_auditAFTER INSERT OR UPDATE OR DELETE ON prs.project_milestoneFOR EACH ROW EXECUTE FUNCTION audit.fn_audit_trigger('milestone_id', NULL, 'prs.project:project_id:project_code:project_id');
```

## 9.4 prs.project_team

```sql
CREATE TABLE prs.project_team (
    team_id          BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    project_id       BIGINT       NOT NULL,
    user_id          BIGINT       NOT NULL,
    role             VARCHAR(64)  NOT NULL,    -- PM/Lead/Member/Reviewer
    function_area    VARCHAR(64),              -- CMC/QA/Regulatory/Clinical 等
    allocation_pct   INT,                      -- 投入百分比
    joined_at        DATE         NOT NULL DEFAULT CURRENT_DATE,
    left_at          DATE,
    notes            TEXT,

    created_at       TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    created_by       BIGINT       NOT NULL,

    CONSTRAINT uq_project_team       UNIQUE (project_id, user_id, role),
    CONSTRAINT fk_project_team_project FOREIGN KEY (project_id)
        REFERENCES prs.project(project_id) ON DELETE CASCADE,
    CONSTRAINT fk_project_team_user  FOREIGN KEY (user_id) REFERENCES auth.user(user_id),
    CONSTRAINT ck_project_team_alloc CHECK (allocation_pct IS NULL
        OR (allocation_pct BETWEEN 0 AND 100))
);

CREATE INDEX ix_project_team_project ON prs.project_team(project_id) WHERE left_at IS NULL;
CREATE INDEX ix_project_team_user    ON prs.project_team(user_id) WHERE left_at IS NULL;
```

## 9.5 prs.project_status_history 与 project_relationship

```sql
CREATE TABLE prs.project_status_history (    history_id        BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,    project_id        BIGINT       NOT NULL,    old_status        VARCHAR(32),    new_status        VARCHAR(32)  NOT NULL,    change_reason     TEXT         NOT NULL,    changed_at        TIMESTAMPTZ  NOT NULL DEFAULT NOW(),    changed_by        BIGINT       NOT NULL,    e_signature_id    BIGINT,      -- 关键状态变更需电子签名        CONSTRAINT fk_project_status_history_project FOREIGN KEY (project_id)         REFERENCES prs.project(project_id),    CONSTRAINT fk_project_status_history_sig FOREIGN KEY (e_signature_id) REFERENCES audit.e_signature(signature_id),    CONSTRAINT fk_project_status_history_user FOREIGN KEY (changed_by)         REFERENCES auth.user(user_id)); CREATE INDEX ix_project_status_history_project ON prs.project_status_history(project_id, changed_at DESC); CREATE OR REPLACE FUNCTION prs.fn_project_status_change()
RETURNS TRIGGER AS $$
BEGIN
    IF OLD.status IS DISTINCT FROM NEW.status THEN
        INSERT INTO prs.project_status_history (
            project_id, old_status, new_status, change_reason, changed_by
        ) VALUES (
            NEW.project_id, OLD.status, NEW.status,
            'status changed',
            NEW.updated_by
        );
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- V1.1：change_reason 由 service 层在 INSERT status_history 后显式 UPDATE 回填，
-- 触发器仅写入默认值占位，不依赖 PostgreSQL session GUC。

CREATE TRIGGER trg_project_status_change
AFTER UPDATE ON prs.project
FOR EACH ROW EXECUTE FUNCTION prs.fn_project_status_change();-- 项目衍生/合并关系CREATE TABLE prs.project_relationship (    relationship_id   BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,    from_project_id   BIGINT       NOT NULL,    to_project_id     BIGINT       NOT NULL,    relationship_type VARCHAR(32)  NOT NULL,   -- merged_into/split_from/derived_from/depends_on    notes             TEXT,    created_at        TIMESTAMPTZ  NOT NULL DEFAULT NOW(),    created_by        BIGINT       NOT NULL,        CONSTRAINT uq_project_relationship UNIQUE (from_project_id, to_project_id, relationship_type),    CONSTRAINT fk_project_rel_from FOREIGN KEY (from_project_id) REFERENCES prs.project(project_id),    CONSTRAINT fk_project_rel_to   FOREIGN KEY (to_project_id) REFERENCES prs.project(project_id),    CONSTRAINT ck_project_rel_self CHECK (from_project_id != to_project_id),    CONSTRAINT ck_project_rel_type CHECK (relationship_type IN         ('merged_into','split_from','derived_from','depends_on','blocks')));
```

# 10. Schema: mm（Material Master Lite）

## 10.1 mm.material

> v2 重要变更（migration 0038 + 0039，2026-05-19）：
> - `material_code` 业务规则：**由用户手动输入**（公司既有编码体系，最长 20 chars）。
>   trigger `fn_material_assign_code` 保留为兜底（仅当 code 为空时自动生成 `MAT-yyyyNNNNNN`），
>   API 层 schema 强制 required，正常业务路径下不会触发 trigger 分支。
> - `material_type` 固定 4 值：`reagent / consumable / standard / column`。
> - `category` 采用**公司 15 值扁平枚举**（中文存储），与 `material_type` 解耦，
>   不再按 type 分组。

```sql
CREATE TABLE mm.material (
    material_id        BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    material_code      VARCHAR(32)  NOT NULL,   -- 用户输入（业务层 max 20）

    -- 基本信息
    material_name      VARCHAR(255) NOT NULL,
    material_name_en   VARCHAR(255),
    material_type      VARCHAR(32)  NOT NULL,   -- reagent/consumable/standard/column
    category           VARCHAR(50),             -- 公司分类体系（15 值扁平枚举）

    -- 物质引用
    substance_id       BIGINT,                  -- 物理批次对应的 substance（必要时）

    -- 供应商 & 规格
    manufacturer       VARCHAR(100),            -- 生产商
    catalog_no         VARCHAR(100),            -- 货号
    spec_model         VARCHAR(200),            -- 规格型号
    unit               VARCHAR(20)  NOT NULL DEFAULT 'ea', -- 默认计量单位
    package_spec       VARCHAR(100),            -- 包装规格

    -- 危化品分类
    hazard_class       TEXT[],                  -- 多选：危化品/易燃/易制毒/易制爆/剧毒品

    -- 物理属性
    physical_form      VARCHAR(64),             -- liquid/lyophilized/powder
    storage_condition  VARCHAR(64),             -- 2-8°C / -80°C / RT

    -- 来源
    source_type        VARCHAR(32),             -- internal/cdmo/vendor
    source_name        VARCHAR(128),

    -- 级别（自由文本，建议值通过前端 AutoComplete 提示）
    grade              VARCHAR(32),

    -- 状态（无状态机，PUT 直接改）
    status             VARCHAR(32)  NOT NULL DEFAULT 'active',

    description        TEXT,
    notes              TEXT,
    extra              JSONB,

    created_at         TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    created_by         BIGINT       NOT NULL,
    updated_at         TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    updated_by         BIGINT       NOT NULL,
    deleted_at         TIMESTAMPTZ,
    deleted_by         BIGINT,

    CONSTRAINT uq_material_code     UNIQUE (material_code),
    CONSTRAINT ck_material_type     CHECK (material_type IN
        ('reagent','consumable','standard','column')),
    -- 公司分类体系（15 值扁平枚举，0039 加入 外包材）
    CONSTRAINT ck_material_category CHECK (
        category IS NULL OR category IN (
            '一般耗材','关键耗材','关键试剂','内包材','外包材','劳保',
            '原辅料','参比品','对照品','工艺用水/气','标准品',
            '细胞种子','自制包材','试剂','运输包装材料'
        )
    ),
    CONSTRAINT ck_material_status   CHECK (status IN ('active','quarantine','released','rejected','retired')),
    CONSTRAINT fk_material_substance FOREIGN KEY (substance_id) REFERENCES srs.substance(substance_id),
    CONSTRAINT fk_material_created_by FOREIGN KEY (created_by) REFERENCES auth.user(user_id),
    CONSTRAINT fk_material_updated_by FOREIGN KEY (updated_by) REFERENCES auth.user(user_id)
);

CREATE INDEX ix_material_type         ON mm.material(material_type) WHERE deleted_at IS NULL;
CREATE INDEX ix_material_category     ON mm.material(category) WHERE deleted_at IS NULL;
CREATE INDEX ix_material_manufacturer ON mm.material(manufacturer) WHERE deleted_at IS NULL;
CREATE INDEX ix_material_substance    ON mm.material(substance_id);
CREATE INDEX ix_material_status       ON mm.material(status) WHERE deleted_at IS NULL;
CREATE INDEX ix_material_name         ON mm.material USING gin(material_name gin_trgm_ops);

CREATE TRIGGER trg_material_audit
AFTER INSERT OR UPDATE OR DELETE ON mm.material
FOR EACH ROW EXECUTE FUNCTION audit.fn_audit_trigger('material_id', 'material_code');

-- 兜底：用户未提供 material_code 时自动生成 MAT-yyyyNNNNNN（业务层 schema required，
-- 正常 API 路径不会进入这个分支；保留用于历史数据迁移或 admin 脚本场景）
CREATE OR REPLACE FUNCTION mm.fn_material_assign_code()
RETURNS TRIGGER AS $$
DECLARE
    v_year     INT;
    v_seq_name VARCHAR;
BEGIN
    IF NEW.material_code IS NULL OR NEW.material_code = '' THEN
        v_year := EXTRACT(YEAR FROM NOW())::INT;
        v_seq_name := meta.fn_ensure_year_sequence('material', 'MAT-', v_year, 6);
        NEW.material_code := meta.fn_next_code(v_seq_name);
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_material_assign_code
BEFORE INSERT ON mm.material
FOR EACH ROW EXECUTE FUNCTION mm.fn_material_assign_code();
```

**初始数据（2026-05-19）：** 公司既有「物流-物料代码表」3702 条物料经
`app/scripts/import_materials_excel.py` 一次性导入，分布：
reagent 1277 / consumable 2259 / standard 116 / column 50。

## 10.2 mm.material_batch

```sql
CREATE TABLE mm.material_batch (
    batch_id          BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    material_id       BIGINT       NOT NULL,
    batch_number      VARCHAR(64)  NOT NULL,        -- 物理批号

    -- 数量
    quantity_value    NUMERIC(18, 4),
    quantity_unit     VARCHAR(16),

    -- 时间
    manufacture_date  DATE,
    expiry_date       DATE,
    receive_date      DATE,

    -- 状态
    status            VARCHAR(32)  NOT NULL DEFAULT 'in_stock',  -- in_stock/in_use/depleted/expired

    -- 来源批号
    source_batch_ref  VARCHAR(128),
    coa_url           TEXT,                             -- 检验证书 URL

    storage_location  VARCHAR(128),
    notes             TEXT,
    extra             JSONB,

    created_at        TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    created_by        BIGINT       NOT NULL,
    updated_at        TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    updated_by        BIGINT       NOT NULL,
    deleted_at        TIMESTAMPTZ,

    CONSTRAINT uq_material_batch UNIQUE (material_id, batch_number),
    CONSTRAINT fk_material_batch_material FOREIGN KEY (material_id)
        REFERENCES mm.material(material_id),
    CONSTRAINT ck_material_batch_status CHECK (status IN
        ('in_stock','in_use','depleted','expired','recalled'))
);

CREATE INDEX ix_material_batch_material ON mm.material_batch(material_id);
CREATE INDEX ix_material_batch_expiry   ON mm.material_batch(expiry_date) WHERE deleted_at IS NULL;
```

# 10A. Schema: eqp（Equipment Master，V1.2 新增）

> **定位**：全公司仪器设备身份注册表，是下游 **CMC LabOps Portal**（cmc-inventory 仓库，
> 文档 ARCH-LABOPS-001 / DM-LABOPS-001 V1.2 起）设备模块的数据上游。
> 本域仅管**主数据**（身份与采购属性）；设备的日常运营（在用状态、所在房间、负责人、
> 计量校验、维护、维修、保修、附件、到期提醒）全部在 LabOps 的 equipment_mgmt schema
> 中维护，两库为独立 PG 实例，**不跨库外键**，LabOps 通过 API 按需拉取
> （GET /api/v1/equipments、GET /api/v1/equipments/{code}）。

## 10A.1 eqp.equipment

设计完全对标 mm.material：无状态机（status 两值，PUT 直接改）、无 version 乐观锁、
无电子签名；接入审计 v3 触发器（id_col='equipment_id', code_col='equipment_code'）。

| **字段** | **类型** | **约束** | **说明** |
|----|----|----|----|
| equipment_id | BIGINT | PK, Identity | 内部主键 |
| equipment_code | VARCHAR(32) | UNIQUE NOT NULL | 设备编码。留空由 BEFORE INSERT 触发器自动分配 **EQP-yyyyXXXXXX**（年度序列，走 meta.fn_ensure_year_sequence/fn_next_code）；也可手动传入沿用部门历史编号 |
| equipment_name | VARCHAR(255) | NOT NULL | 设备名称 |
| equipment_name_en | VARCHAR(255) | | 英文名称 |
| category | VARCHAR(64) | NOT NULL, CHECK | 分析仪器 / 实验设备 / 辅助设备 / 其他 |
| model | VARCHAR(200) | | 型号规格 |
| manufacturer | VARCHAR(100) | | 生产商 |
| serial_no | VARCHAR(100) | | 厂家序列号 |
| purchase_date | DATE | | 购入日期 |
| asset_value | NUMERIC(12,2) | | 资产价值（元） |
| supplier | VARCHAR(200) | | 供应商 |
| status | VARCHAR(32) | NOT NULL DEFAULT 'active', CHECK | active（在册）/ retired（已退役） |
| description / notes / extra | TEXT / TEXT / JSONB | | 描述 / 备注 / 扩展 |
| created_at/by, updated_at/by, deleted_at/by | 标准审计列 | created_by 等 FK → auth.user | 软删除（deleted_at），与全库一致 |

索引：category / status 部分索引（deleted_at IS NULL）、manufacturer、
equipment_name gin_trgm（模糊搜索）。

Migration：`2026_06_04_0100_0040_eqp_equipment.py`（含 schema 创建、
updated_at 触发器、编码触发器、审计 v3 触发器；downgrade 同步清理年度序列）。

## 10A.2 权限与角色（auth 域同步变更）

| **权限码** | **说明** |
|----|----|
| equipment:create | 创建设备 |
| equipment:read | 查询设备 |
| equipment:update | 更新 / 软删除设备 |

预置角色变更（seed_data.py 与 live 库同步）：

- **CMC_EQUIPMENT_ADMIN**（新增）：equipment:create/read/update + material:read。
  同时是 LabOps 设备模块写权限角色——LabOps 信任本系统 JWT 的 roles claim。
- **CMC_WAREHOUSE_ADMIN**（补入 seed，此前仅存在于 live 库）：material:create/read/update
  + equipment:read。同时是 LabOps 物料模块写权限角色。
- CMC_RESEARCHER / READ_ONLY_USER 增加 equipment:read。

## 10A.3 与下游 LabOps 的引用约定

- LabOps 的 equipment_mgmt.equipment 行携带 `mdm_equipment_id`（本表主键快照）与
  `data_source`（mdm / local）；身份字段以本表为权威，运营字段归 LabOps。
- LabOps 前端不提供本地新增主数据入口（标准化决议，2026-06-04）：新设备一律先在
  本系统登记，LabOps "新增设备(从 MDM 引用)" 搜索选中后仅补运营字段。
- 本系统前端 /equipments/new、/materials/new 支持 `?code=` / `?name=` 查询参数预填，
  承接 LabOps "去 MDM 登记" 跳转。

# 11. Schema: ref（跨域引用）

## 11.1 设计原则

- 跨域引用集中管理，避免业务表之间的硬耦合

- 引用关系类型灵活（主要研究 / 对照 / 衍生 等）

- 支持多对多关系

- 被引用实体不可物理删除（外键约束保证）

业务规则：被引用实体处于终止态（substance.status='obsoleted' / asset.status='terminated' / project.status='terminated'）时，service 层禁止新建关联记录（已存在记录不强制清理）。本规则由应用层校验，DB 层不加 CHECK。

## 11.2 ref.project_substance

```sql
CREATE TABLE ref.project_substance (    project_id       BIGINT       NOT NULL,    substance_id     BIGINT       NOT NULL,    relation_type    VARCHAR(32)  NOT NULL DEFAULT 'primary',        -- 关系属性    is_primary       BOOLEAN      NOT NULL DEFAULT FALSE,    notes            TEXT,        -- 审计    created_at       TIMESTAMPTZ  NOT NULL DEFAULT NOW(),    created_by       BIGINT       NOT NULL,    updated_at       TIMESTAMPTZ  NOT NULL DEFAULT NOW(),    updated_by       BIGINT       NOT NULL,    deleted_at       TIMESTAMPTZ,    deleted_by       BIGINT,        CONSTRAINT pk_ref_project_substance PRIMARY KEY (project_id, substance_id, relation_type),
    CONSTRAINT fk_ref_ps_project   FOREIGN KEY (project_id) REFERENCES prs.project(project_id),
    CONSTRAINT fk_ref_ps_substance FOREIGN KEY (substance_id) REFERENCES srs.substance(substance_id),
    CONSTRAINT fk_ref_ps_deleted_by FOREIGN KEY (deleted_by) REFERENCES auth.user(user_id),
    CONSTRAINT ck_ref_ps_type CHECK (relation_type IN
        ('primary','secondary','reference','control','derivative'))
); CREATE INDEX ix_ref_ps_project   ON ref.project_substance(project_id) WHERE deleted_at IS NULL;CREATE INDEX ix_ref_ps_substance ON ref.project_substance(substance_id) WHERE deleted_at IS NULL; CREATE TRIGGER trg_ref_ps_auditAFTER INSERT OR UPDATE OR DELETE ON ref.project_substanceFOR EACH ROW EXECUTE FUNCTION audit.fn_audit_trigger('project_id', NULL, 'prs.project:project_id:project_code:project_id');
```

## 11.3 ref.asset_substance

```sql
CREATE TABLE ref.asset_substance (
    asset_id         BIGINT       NOT NULL,
    substance_id     BIGINT       NOT NULL,
    component_role   VARCHAR(32)  NOT NULL,    -- main_component/antibody/linker/payload/excipient

    is_active_ingredient  BOOLEAN  NOT NULL DEFAULT TRUE,
    notes            TEXT,

    created_at       TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    created_by       BIGINT       NOT NULL,
    updated_at       TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    updated_by       BIGINT       NOT NULL,
    deleted_at       TIMESTAMPTZ,
    deleted_by       BIGINT,

    CONSTRAINT pk_ref_asset_substance PRIMARY KEY (asset_id, substance_id, component_role),
    CONSTRAINT fk_ref_as_asset     FOREIGN KEY (asset_id) REFERENCES ars.asset(asset_id),
    CONSTRAINT fk_ref_as_substance FOREIGN KEY (substance_id) REFERENCES srs.substance(substance_id),
    CONSTRAINT fk_ref_as_deleted_by FOREIGN KEY (deleted_by) REFERENCES auth.user(user_id),
    CONSTRAINT ck_ref_as_role CHECK (component_role IN
        ('main_component','antibody','linker','payload','excipient','impurity'))
);

CREATE INDEX ix_ref_as_asset     ON ref.asset_substance(asset_id) WHERE deleted_at IS NULL;
CREATE INDEX ix_ref_as_substance ON ref.asset_substance(substance_id) WHERE deleted_at IS NULL;
```

CREATE TRIGGER trg_ref_as_audit

AFTER INSERT OR UPDATE OR DELETE ON ref.asset_substance

FOR EACH ROW EXECUTE FUNCTION audit.fn_audit_trigger(

'asset_id',

NULL,

'ars.asset:asset_id:asset_code:asset_id'

);

## 11.4 ref.project_asset

```sql
CREATE TABLE ref.project_asset (
    project_id       BIGINT       NOT NULL,
    asset_id         BIGINT       NOT NULL,
    relation_type    VARCHAR(32)  NOT NULL DEFAULT 'primary',
    notes            TEXT,

    created_at       TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    created_by       BIGINT       NOT NULL,
    updated_at       TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    updated_by       BIGINT       NOT NULL,
    deleted_at       TIMESTAMPTZ,
    deleted_by       BIGINT,

    CONSTRAINT pk_ref_project_asset PRIMARY KEY (project_id, asset_id),
    CONSTRAINT fk_ref_pa_project FOREIGN KEY (project_id) REFERENCES prs.project(project_id),
    CONSTRAINT fk_ref_pa_asset   FOREIGN KEY (asset_id) REFERENCES ars.asset(asset_id),
    CONSTRAINT fk_ref_pa_deleted_by FOREIGN KEY (deleted_by) REFERENCES auth.user(user_id)
);
CREATE TRIGGER trg_ref_pa_audit
AFTER INSERT OR UPDATE OR DELETE ON ref.project_asset
FOR EACH ROW EXECUTE FUNCTION audit.fn_audit_trigger(
    'project_id',
    NULL,
    'prs.project:project_id:project_code:project_id'
);
```

# 12. 视图（Views）

## 12.1 v_substance_summary（物质摘要视图）

聚合 substance + 各类型扩展 + xref 主要标识符，便于前端列表展示。

```sql
CREATE OR REPLACE VIEW srs.v_substance_summary AS
SELECT
    s.substance_id,
    s.substance_code,
    s.substance_type,
    s.internal_code,
    s.preferred_name,
    s.preferred_name_en,
    s.target,
    s.status,
    s.confidentiality,

    -- INN（如有）
    (SELECT xref_value FROM srs.substance_xref x
       WHERE x.substance_id = s.substance_id
         AND x.xref_type = 'INN'
         AND x.deleted_at IS NULL
       LIMIT 1) AS inn,

    -- CAS（如有）
    (SELECT xref_value FROM srs.substance_xref x
       WHERE x.substance_id = s.substance_id
         AND x.xref_type = 'CAS'
         AND x.deleted_at IS NULL
       LIMIT 1) AS cas_number,

    -- 蛋白属性
    p.isotype,
    p.architecture,
    p.expression_system,

    -- ADC 父子（如适用）
    adc.antibody_substance_id,
    adc.payload_substance_id,
    adc.dar_average,

    -- 关联计数
    (SELECT COUNT(*) FROM ref.project_substance r
       WHERE r.substance_id = s.substance_id AND r.deleted_at IS NULL) AS project_count,
    (SELECT COUNT(*) FROM ref.asset_substance r
       WHERE r.substance_id = s.substance_id AND r.deleted_at IS NULL) AS asset_count,
    (SELECT COUNT(*) FROM mm.material m
       WHERE m.substance_id = s.substance_id AND m.deleted_at IS NULL) AS material_count,

    s.created_at,
    s.updated_at
FROM srs.substance s
LEFT JOIN srs.substance_protein       p   ON p.substance_id = s.substance_id
LEFT JOIN srs.substance_adc           adc ON adc.substance_id = s.substance_id
WHERE s.deleted_at IS NULL;
```

## 12.2 v_project_summary（项目摘要视图）

```sql
CREATE OR REPLACE VIEW prs.v_project_summary AS
SELECT
    p.project_id,
    p.project_code,
    p.project_name,
    p.project_type,
    p.status,
    p.priority,
    p.planned_start_date,
    p.planned_end_date,
    pm.full_name   AS pm_name,
    pm.username    AS pm_username,

    -- 关联物质（多个用 || 拼接）
    (SELECT string_agg(s.substance_code, ', ' ORDER BY s.substance_code)
       FROM ref.project_substance r
       JOIN srs.substance s ON s.substance_id = r.substance_id
      WHERE r.project_id = p.project_id AND r.deleted_at IS NULL) AS related_substances,

    -- 关联资产
    (SELECT string_agg(a.asset_code, ', ' ORDER BY a.asset_code)
       FROM ref.project_asset r
       JOIN ars.asset a ON a.asset_id = r.asset_id
      WHERE r.project_id = p.project_id AND r.deleted_at IS NULL) AS related_assets,

    -- 团队规模
    (SELECT COUNT(*) FROM prs.project_team t
      WHERE t.project_id = p.project_id AND t.left_at IS NULL) AS team_size,

    p.created_at,
    p.updated_at
FROM prs.project p
LEFT JOIN auth.user pm ON pm.user_id = p.project_manager_id
WHERE p.deleted_at IS NULL;
```

## 12.3 v_audit_log_extended（审计日志增强视图）

```sql
CREATE OR REPLACE VIEW audit.v_audit_log_extended AS
SELECT
    al.log_id,
    al.timestamp,
    al.username,
    u.full_name,
    u.department,
    al.action,
    al.entity_schema,
    al.entity_table,
    al.entity_id,
    al.entity_code,
    al.change_summary,
    al.reason,
    al.ip_address,
    al.session_id,

    -- 字段变更摘要
    (SELECT string_agg(field_name || ': ' || COALESCE(old_value::text, 'null')
                     || ' → ' || COALESCE(new_value::text, 'null'), '; ')
       FROM audit.change_history ch
      WHERE ch.audit_log_id = al.log_id) AS field_changes
FROM audit.audit_log al
LEFT JOIN auth.user u ON u.user_id = al.user_id;
```

# 13. 性能与索引策略

## 13.1 索引设计原则

- 所有外键自动建索引（PostgreSQL 不自动建，需显式）

- 软删除字段配合：WHERE deleted_at IS NULL 条件用部分索引

- 名称类字段使用 GIN + pg_trgm 索引支持模糊搜索

- JSONB 字段使用 GIN 索引

- 时间序列查询字段建 DESC 索引（如 audit_log.timestamp）

- 避免过度索引（每个索引都增加 INSERT/UPDATE 开销）

## 13.2 关键查询的优化

| **查询场景** | **优化手段** |
|----|----|
| 全局搜索（substance_code / 名称 / INN） | GIN trigram + 联合查询 |
| 按 substance 反向查项目 | ref.project_substance(substance_id) 索引 |
| 按时间范围查审计日志 | audit_log.timestamp DESC 索引 |
| 按用户查历史操作 | audit_log(user_id, timestamp DESC) 复合索引 |
| 序列 sameness 比对 | sequence_hash 索引（O(1) 精确匹配） |
| 状态筛选 + 排序 | (status, updated_at DESC) 复合索引 |

## 13.3 分区策略（未来）

- audit.audit_log 数据量预计每年 100W+，3 年后考虑按月分区

- audit.change_history 跟随 audit_log 分区

- PostgreSQL 16 原生分区表支持，迁移平滑

## 13.4 查询缓存

- 热点配置（meta.system_config、meta.lookup_value）：应用层 Redis 缓存

- 全局搜索：考虑接入 PostgreSQL FTS 或 Elasticsearch（后期）

- 用户权限：登录时加载到 Redis，会话期间不重复查询

## 13.5 数据库参数建议

```sql
# postgresql.conf 关键参数（基于 16GB 内存服务器）

# 内存
shared_buffers          = 4GB              # 总内存的 25%
effective_cache_size    = 12GB             # 总内存的 75%
work_mem                = 32MB             # 单个排序/哈希操作
maintenance_work_mem    = 512MB            # VACUUM/CREATE INDEX

# WAL
wal_level               = replica
max_wal_size            = 2GB
min_wal_size            = 128MB
wal_compression         = on

# 并发
max_connections         = 200
effective_io_concurrency = 200             # SSD 推荐值

# 日志（合规要求）
log_destination         = 'csvlog'
logging_collector       = on
log_min_duration_statement = 1000          # 慢 SQL ≥ 1s 记录
log_connections         = on
log_disconnections      = on
log_statement           = 'mod'            # 所有 INSERT/UPDATE/DELETE/DDL

# 时区
timezone                = 'UTC'
log_timezone            = 'UTC'

# 备份
archive_mode            = on
archive_command         = 'cp %p /backup/wal_archive/%f'
```

# 14. 数据迁移策略

## 14.1 工具选型

- 使用 Alembic（SQLAlchemy 官方迁移工具）

- 迁移脚本与代码同仓库（backend/alembic/versions/）

- 每次 schema 变更生成新的 revision，禁止修改已发布的 revision

- 生产环境迁移由 DBA 手动执行，不通过应用自动 upgrade

## 14.2 迁移命名规范

```text
# 文件名格式：<timestamp>_<short_description>.py
# 例如：
2026_05_11_1430_init_auth_schema.py
2026_05_15_0900_add_substance_main_tables.py
2026_05_15_0915_add_substance_protein_extension.py
2026_05_20_1100_add_audit_trigger_function.py

# 每个 migration 包含：
def upgrade() -> None:    # 升级
    ...
def downgrade() -> None:  # 回滚
    ...
```

## 14.3 迁移分组与依赖

```text
# 推荐 migration 分组顺序：

001-009: 基础设施（schema 创建、扩展安装）
010-019: auth schema
020-029: meta schema（含编码生成函数）
030-039: audit schema（含通用触发器函数）
040-059: srs schema（substance 全部表）
060-069: ars schema
070-079: prs schema
080-089: mm schema
090-099: ref schema
100-109: 视图
110-119: 初始化数据（lookup_value, role, permission）
120-129: 测试数据（仅 dev / test 环境）
```

## 14.4 历史数据导入

### 14.4.1 导入流程

10. Data profiling：用 Python 脚本扫描现有 Excel/数据库，识别字段、缺失、异常

11. 数据清洗：在 staging schema 中清洗（不污染正式 schema）

12. 映射规则：建立旧编码 ↔ 新 substance_code/project_code 映射表

13. 分批导入：先导入 substance，再导入 project，最后建立引用关系

14. 校验：导入后跑校验脚本，对账记录数与关键字段

15. 审计：所有导入记录在 audit_log 中标记为 IMPORT action

### 14.4.2 推荐 staging schema 设计

```sql
CREATE SCHEMA staging;

-- 临时导入表，结构与原始数据对齐
CREATE TABLE staging.substance_import_2026 (
    raw_row_no       INT,
    legacy_code      VARCHAR(64),
    legacy_name      VARCHAR(255),
    legacy_target    VARCHAR(128),
    -- ... 其他原始字段

    -- 导入控制
    new_substance_id BIGINT,        -- 导入成功后填回
    new_substance_code VARCHAR(32),
    import_status    VARCHAR(16),   -- pending/imported/error/skipped
    import_error     TEXT,
    imported_at      TIMESTAMPTZ
);
```

## 14.5 回滚策略

- 每个 migration 必须实现可执行的 downgrade()

- 生产部署前：在 test 环境演练 upgrade → downgrade → upgrade

- 数据破坏性 migration（如删除字段）：先做完整备份，再分两步：1) 应用层不再使用，2) 一段稳定期后再删字段

- 不可逆 migration（如数据合并）：明确标注 IRREVERSIBLE，需要团队评审

## 14.6 备份策略（与 ARCH-MDM-001 对齐）

| **类型**      | **工具**              | **频率**   | **保留期** |
|---------------|-----------------------|------------|------------|
| 全量备份      | pg_dump --format=c    | 每日 02:00 | 30 天      |
| WAL 增量      | archive_command       | 实时       | 7 天       |
| Schema 元数据 | pg_dump --schema-only | 每周日     | 180 天     |
| 逻辑备份验证  | pg_restore 演练       | 每月       | —          |
| 异地备份      | rsync to NAS          | 每日       | 180 天     |

# 15. 附录

## 15.1 完整 DDL 部署脚本结构

```text
# 推荐目录结构（migration 总入口）
backend/
├── alembic/
│   ├── alembic.ini
│   ├── env.py                # 配置
│   ├── script.py.mako
│   └── versions/             # 所有 migration
│       ├── 001_init_extensions_and_schemas.py
│       ├── 010_auth_user_role_permission.py
│       ├── 020_meta_code_sequence_lookup.py
│       ├── 030_audit_log_change_signature.py
│       ├── 040_srs_substance_main.py
│       ├── 041_srs_substance_protein.py
│       ├── 042_srs_substance_adc.py
│       ├── 043_srs_substance_small_molecule.py
│       ├── 044_srs_substance_xref.py
│       ├── 045_srs_substance_status_history.py
│       ├── 060_ars_asset.py
│       ├── 061_ars_asset_market_id.py
│       ├── 070_prs_project.py
│       ├── 071_prs_project_milestone.py
│       ├── 072_prs_project_team.py
│       ├── 073_prs_project_status_history.py
│       ├── 080_mm_material.py
│       ├── 081_mm_material_batch.py
│       ├── 090_ref_project_substance.py
│       ├── 091_ref_asset_substance.py
│       ├── 092_ref_project_asset.py
│       ├── 100_views_summary.py
│       └── 110_seed_lookup_values.py
```

## 15.2 SQLAlchemy ORM 映射示例

```python
# backend/app/domains/srs/models.py

from sqlalchemy import (
    BigInteger, String, Text, Boolean, DateTime, Integer,
    ForeignKey, CheckConstraint, UniqueConstraint, func
)
from sqlalchemy.dialects.postgresql import JSONB, UUID, INET
from sqlalchemy.orm import Mapped, mapped_column, relationship
from datetime import datetime
from app.core.database import Base


class Substance(Base):
    __tablename__ = "substance"
    __table_args__ = (
        UniqueConstraint("substance_code", name="uq_substance_code"),
        CheckConstraint(
            "substance_type IN ('mab','bispecific','adc','fusion','small_molecule','oligonucleotide','other')",
            name="ck_substance_type"
        ),
        {"schema": "srs"},
    )

    substance_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    substance_code: Mapped[str] = mapped_column(String(32), nullable=False)
    substance_type: Mapped[str] = mapped_column(String(32), nullable=False)
    internal_code: Mapped[str | None] = mapped_column(String(64))
    preferred_name: Mapped[str] = mapped_column(String(255), nullable=False)
    preferred_name_en: Mapped[str | None] = mapped_column(String(255))
    target: Mapped[str | None] = mapped_column(String(128))
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="draft")
    extra: Mapped[dict | None] = mapped_column(JSONB)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    created_by: Mapped[int] = mapped_column(BigInteger, ForeignKey("auth.user.user_id"), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_by: Mapped[int] = mapped_column(BigInteger, ForeignKey("auth.user.user_id"), nullable=False)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)

    # 关系
    protein: Mapped["SubstanceProtein"] = relationship("SubstanceProtein", uselist=False, back_populates="substance")
    xrefs:   Mapped[list["SubstanceXref"]] = relationship("SubstanceXref", back_populates="substance")
```

15.2.1 service 层事务提交时机（V1.1 新增）

1\. 写操作完成后，service 必须显式 await self.db.commit()，不依赖 FastAPI yield 依赖（get_db）的 cleanup commit。\
2. 原因：FastAPI 的 yield 依赖 cleanup 在 response 已发送给客户端之后才执行，客户端连续请求可能在 commit 完成前到达新连接，读到 pre-commit 快照，违反 §11.300 强一致性要求。\
3. 示例伪代码：\
async def update_status(...):\
self.db.add(...)\
await self.db.flush()\
await self.db.commit()\
return result\
4. 影响范围：所有状态变更端点、签名生效端点、跨域关联写入端点。

15.2.2 失败副作用旁路 session 持久化（V1.1 新增）

1\. 适用场景：登录失败计数（user.failed_login_count++）、签名密码错误、状态机非法转换等'失败但需留痕'的副作用。\
2. 反模式：在主 service session 里写 failed_login_count++ 再 raise → get_db 的 except 分支 rollback 会同时撤销计数与失败 audit_log，导致防暴力破解失效。\
3. 推荐模式：副作用走独立 AsyncSessionLocal() 旁路 session，单独 await session.commit()，再 raise 业务异常。主事务的 rollback 不影响旁路 session 已提交的失败记录。\
4. 示例伪代码：\
async with AsyncSessionLocal() as bypass:\
bypass.add(audit_log)\
user.failed_login_count += 1\
await bypass.merge(user)\
await bypass.commit()\
raise HTTPException(401, ...)\
5. 与 §6.5 通用审计触发器的关系：成功路径的审计走触发器；失败路径的审计走 service 显式写入 + 旁路 session。

## 15.3 关键约束清单

| **约束类型** | **说明** | **应用范围** |
|----|----|----|
| PK | 所有业务表使用 BIGINT IDENTITY 主键 | 全部 |
| UQ on code | 业务编码全局唯一 | substance, project, asset, material |
| CHECK on enum | 枚举类字段用 CHECK 约束 | status, type 等字段 |
| FK with audit | 外键引用 auth.user 与 audit | 全部业务表 |
| NOT NULL on key fields | 关键字段非空 | code, name, status, created\_\* |
| Soft delete pattern | deleted_at 字段，配合部分索引 | 全部业务表 |
| Optimistic lock | version 字段 + 应用层比对 | substance, project, asset |
| RBAC 双权限 | 关键不可逆动作（terminate / obsolete / merge / reject）要求"操作权限 + 签名权限"双校验 | substance:approve+sign / project:approve+sign / asset:update+sign |

## 15.4 测试数据建议

- dev 环境：种子脚本插入 5–10 条 mAb substance、3–5 个 project、1–2 个 asset

- test 环境：从生产脱敏导出小规模数据

- 性能测试：用 Faker 生成 1万条 substance、5000 个 project（仅压测环境）

- 敏感字段（如序列、内部代号）测试环境必须脱敏

## 15.5 后续文档清单

| **文档编号**    | **文档名称**                            | **依赖本文档** |
|-----------------|-----------------------------------------|----------------|
| API-MDM-001     | API 接口规范（OpenAPI 3.0）             | ✓              |
| UI-MDM-001      | UI 信息架构与线框图                     | —              |
| DEV-MDM-001     | 开发规范（含 ORM 模式、Service 层规范） | ✓              |
| TEST-MDM-001    | 测试策略与计划                          | ✓              |
| DEPLOY-MDM-001  | 部署与运维手册                          | ✓              |
| MIGRATE-MDM-001 | 历史数据迁移方案                        | ✓              |

## 15.6 参考

- CMAB 内部文档：SMP-RD-NUM-001 V2.1 编码规则

- CMAB 内部文档：ARCH-MDM-001 V1.0 总体架构

- PostgreSQL 16 官方文档：https://www.postgresql.org/docs/16/

- SQLAlchemy 2.0 文档：https://docs.sqlalchemy.org/en/20/

- Alembic 文档：https://alembic.sqlalchemy.org/

- 21 CFR Part 11（FDA 官网最新版）

- EU GMP Annex 11（欧盟委员会官网最新版）

- ICH Q9(R1)、Q14、Q2(R2)、Q12、Q5E（核对当前版本）
