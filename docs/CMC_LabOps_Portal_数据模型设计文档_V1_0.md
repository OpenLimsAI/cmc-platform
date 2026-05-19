**CMC LabOps Portal**

**数据模型设计文档**

*Data Model Design Document*

*ERD · DDL · Constraints · Indexes*

| | |
|---|---|
| **文档编号** | DM-LABOPS-001 |
| **版本** | V1.0 |
| **状态** | Draft |
| **发布日期** | 2026-05-19 |
| **编制** | CMC IT |
| **上位文档** | ARCH-LABOPS-001 V1.0 |
| **数据库** | PostgreSQL 16 |
| **分类** | 内部技术文档 |

# 修订记录

| **版本** | **日期** | **修订人** | **修订内容** |
|---|---|---|---|
| V1.0 | 2026-05-19 | CMC IT | 初始版本，定义设备管理表结构、认证权限升级、审计升级 |

## 适用范围

- 本文档为 CMC LabOps Portal 的数据库层设计依据
- 覆盖现有物料库存表（保留）+ 新增设备管理表 + 认证权限升级表
- 以 PostgreSQL 16 为目标数据库
- 每张表的每个字段都提供：字段名、类型、UI 中文名、说明

# 1. 设计原则

1. **保留现有表**：material_mgmt schema 中的 10 张表原样保留，确保 Streamlit 前端在迁移期间继续正常工作
2. **新模块新 schema**：设备管理使用独立 schema equipment_mgmt
3. **认证权限升级**：新建 labops_auth schema，支持 RBAC；迁移期间旧 material_mgmt.app_user 保留
4. **审计升级**：新建 labops_audit schema，增加模块字段和变更原因
5. **软删除**：所有业务表使用 is_active 或 deleted_at 标记，禁止物理删除
6. **时间戳**：所有时间字段使用 TIMESTAMP（上海本地时间），datetime.now() 写入
7. **数量精度**：NUMERIC(12,2) 避免浮点误差
8. **数据完整性**：通过外键 + CHECK 约束 + 触发器保证

# 2. Schema 总览

| **Schema** | **用途** | **来源** | **主要表** | **数据规模预估** |
|---|---|---|---|---|
| material_mgmt | 物料库存 | 现有保留 | material, batch, inventory_txn, location, unit_dict, category_dict, import_log | 物料 ~2000，批次 ~10000 |
| equipment_mgmt | 仪器设备 | 新增 | equipment, equipment_calibration, equipment_maintenance, equipment_repair, equipment_warranty, equipment_attachment, equipment_reminder | 设备 ~200 |
| labops_auth | 认证与权限 | 新增（升级） | user, role, permission, user_role, role_permission, login_session | 用户 ~50 |
| labops_audit | 审计追踪 | 新增（升级） | audit_log | 高速增长 |

## 2.1 Schema 依赖关系

```text
依赖方向（A → B 表示 A 引用 B）：

  equipment_mgmt ──→ labops_auth   (设备的 created_by 等引用 user)
  material_mgmt  ──→ material_mgmt (现有内部引用保留)
  labops_audit   ──→ labops_auth   (审计引用用户)

  labops_auth 是基础 schema，其他 schema 依赖它

部署顺序：
  1. labops_auth  (基础)
  2. labops_audit (基础)
  3. material_mgmt (现有，保留)
  4. equipment_mgmt (新增)
```

# 3. 现有物料库存表（保留不变）

> 以下 10 张表位于 material_mgmt schema，原样保留。详细字段定义参见 cmc-inventory README §四。

| **表名** | **用途** | **记录数预估** |
|---|---|---|
| material | 物料主数据 | ~2000 |
| batch | 批次 | ~10000 |
| inventory_txn | 出入库流水（库存计算唯一来源） | ~50000 |
| location | 储存位置 | ~100 |
| unit_dict | 单位字典 | ~20 |
| category_dict | 分类字典 | ~30 |
| import_log | 导入日志 | ~100 |
| app_user | 应用账号（迁移后由 labops_auth.user 取代） | ~20 |
| auth_session | 登录会话（迁移后由 labops_auth.login_session 取代） | ~50 |
| audit_log | 审计日志（迁移后由 labops_audit.audit_log 取代） | ~10000 |

关键设计不变：
- 库存数量不落表，实时由 inventory_txn 聚合计算
- material_code 部分唯一（'TT内部物料' 例外）
- (material_id, batch_no, location_id) 联合唯一
- location.name 为生成列

# 4. Schema: equipment_mgmt（仪器设备管理）

## 4.1 表清单

| **表名** | **用途** |
|---|---|
| equipment | 设备台账主表 |
| equipment_calibration | 计量校验记录 |
| equipment_maintenance | 常规维护记录 |
| equipment_repair | 维修记录 |
| equipment_warranty | 保修信息 |
| equipment_attachment | 设备附件 |
| equipment_reminder | 到期提醒配置 |

## 4.2 equipment（设备台账主表）

### 4.2.1 字段定义

| **字段** | **类型** | **约束** | **UI 中文名** | **说明** |
|---|---|---|---|---|
| equipment_id | SERIAL | PK | 设备ID | 内部主键 |
| equipment_code | VARCHAR(32) | UNIQUE, NOT NULL | 设备编号 | 内部编号，如 EQP-0001，唯一不可修改 |
| name | VARCHAR(200) | NOT NULL | 设备名称 | 设备名称 |
| category | VARCHAR(50) | NOT NULL | 设备分类 | 分析仪器 / 实验设备 / 辅助设备 等 |
| model | VARCHAR(200) | | 型号规格 | 厂家型号 |
| manufacturer | VARCHAR(100) | | 生产商 | 生产商 |
| serial_no | VARCHAR(100) | | 序列号 | 厂家序列号 |
| location_room | VARCHAR(50) | | 所在房间 | 实验室/房间号 |
| location_detail | VARCHAR(200) | | 安装位置 | 具体安装位置描述 |
| responsible_person | VARCHAR(50) | | 负责人 | 设备负责人姓名 |
| status | VARCHAR(20) | NOT NULL DEFAULT 'in_use' | 状态 | in_use / out_of_service / scrapped / in_repair / in_calibration |
| purchase_date | DATE | | 购入日期 | 购入日期 |
| commission_date | DATE | | 启用日期 | 首次启用日期 |
| asset_value | NUMERIC(12,2) | | 资产价值 | 购入金额 |
| remark | TEXT | | 备注 | 备注 |
| is_active | BOOLEAN | NOT NULL DEFAULT TRUE | 是否有效 | 软删除标记 |
| deactivated_at | TIMESTAMP | | 报废时间 | 报废/停用时间 |
| deactivated_by | VARCHAR(50) | | 报废操作人 | 报废操作人 |
| deactivate_reason | VARCHAR(200) | | 报废原因 | 报废原因 |
| created_at | TIMESTAMP | NOT NULL DEFAULT NOW() | 创建时间 | |
| created_by | VARCHAR(50) | | 创建人 | |
| updated_at | TIMESTAMP | NOT NULL DEFAULT NOW() | 更新时间 | |
| updated_by | VARCHAR(50) | | 更新人 | |

### 4.2.2 DDL

```sql
CREATE TABLE equipment_mgmt.equipment (
    equipment_id      SERIAL PRIMARY KEY,
    equipment_code    VARCHAR(32)  NOT NULL,
    name              VARCHAR(200) NOT NULL,
    category          VARCHAR(50)  NOT NULL,
    model             VARCHAR(200),
    manufacturer      VARCHAR(100),
    serial_no         VARCHAR(100),
    location_room     VARCHAR(50),
    location_detail   VARCHAR(200),
    responsible_person VARCHAR(50),
    status            VARCHAR(20)  NOT NULL DEFAULT 'in_use',
    purchase_date     DATE,
    commission_date   DATE,
    asset_value       NUMERIC(12,2),
    remark            TEXT,
    is_active         BOOLEAN      NOT NULL DEFAULT TRUE,
    deactivated_at    TIMESTAMP,
    deactivated_by    VARCHAR(50),
    deactivate_reason VARCHAR(200),
    created_at        TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    created_by        VARCHAR(50),
    updated_at        TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_by        VARCHAR(50),

    CONSTRAINT uq_equipment_code UNIQUE (equipment_code),
    CONSTRAINT ck_equipment_status CHECK (status IN ('in_use','out_of_service','scrapped','in_repair','in_calibration'))
);

CREATE INDEX ix_equipment_category ON equipment_mgmt.equipment(category) WHERE is_active = TRUE;
CREATE INDEX ix_equipment_status   ON equipment_mgmt.equipment(status) WHERE is_active = TRUE;
CREATE INDEX ix_equipment_room     ON equipment_mgmt.equipment(location_room);
CREATE INDEX ix_equipment_responsible ON equipment_mgmt.equipment(responsible_person);

-- updated_at 自动维护
CREATE TRIGGER equipment_updated_at
    BEFORE UPDATE ON equipment_mgmt.equipment
    FOR EACH ROW EXECUTE FUNCTION material_mgmt.trg_set_updated_at();
```

## 4.3 equipment_calibration（计量校验记录）

### 4.3.1 字段定义

| **字段** | **类型** | **约束** | **UI 中文名** | **说明** |
|---|---|---|---|---|
| calibration_id | SERIAL | PK | 校验ID | 内部主键 |
| equipment_id | INT | FK NOT NULL | 设备ID | 关联设备 |
| calibration_date | DATE | NOT NULL | 校验日期 | 本次校验日期 |
| calibration_agency | VARCHAR(200) | | 校验机构 | 校验机构名称 |
| result | VARCHAR(20) | NOT NULL | 校验结论 | qualified / unqualified / limited_use |
| certificate_no | VARCHAR(100) | | 证书编号 | 校验证书编号 |
| next_calibration_date | DATE | | 下次校验日期 | 下次校验到期日 |
| remark | TEXT | | 备注 | |
| created_at | TIMESTAMP | NOT NULL DEFAULT NOW() | 创建时间 | |
| created_by | VARCHAR(50) | | 创建人 | |

### 4.3.2 DDL

```sql
CREATE TABLE equipment_mgmt.equipment_calibration (
    calibration_id      SERIAL PRIMARY KEY,
    equipment_id        INT         NOT NULL REFERENCES equipment_mgmt.equipment(equipment_id),
    calibration_date    DATE        NOT NULL,
    calibration_agency  VARCHAR(200),
    result              VARCHAR(20) NOT NULL,
    certificate_no      VARCHAR(100),
    next_calibration_date DATE,
    remark              TEXT,
    created_at          TIMESTAMP   NOT NULL DEFAULT CURRENT_TIMESTAMP,
    created_by          VARCHAR(50),

    CONSTRAINT ck_calibration_result CHECK (result IN ('qualified','unqualified','limited_use'))
);

CREATE INDEX ix_calibration_equipment ON equipment_mgmt.equipment_calibration(equipment_id, calibration_date DESC);
CREATE INDEX ix_calibration_next_date ON equipment_mgmt.equipment_calibration(next_calibration_date);
```

## 4.4 equipment_maintenance（常规维护记录）

### 4.4.1 字段定义

| **字段** | **类型** | **约束** | **UI 中文名** | **说明** |
|---|---|---|---|---|
| maintenance_id | SERIAL | PK | 维护ID | 内部主键 |
| equipment_id | INT | FK NOT NULL | 设备ID | 关联设备 |
| maintenance_date | DATE | NOT NULL | 维护日期 | 维护日期 |
| maintenance_type | VARCHAR(30) | NOT NULL | 维护类型 | daily / periodic / special |
| content | TEXT | | 维护内容 | 维护具体内容描述 |
| performed_by | VARCHAR(50) | NOT NULL | 执行人 | 维护执行人 |
| next_maintenance_date | DATE | | 下次维护日期 | 下次维护到期日 |
| remark | TEXT | | 备注 | |
| created_at | TIMESTAMP | NOT NULL DEFAULT NOW() | 创建时间 | |
| created_by | VARCHAR(50) | | 创建人 | |

### 4.4.2 DDL

```sql
CREATE TABLE equipment_mgmt.equipment_maintenance (
    maintenance_id      SERIAL PRIMARY KEY,
    equipment_id        INT         NOT NULL REFERENCES equipment_mgmt.equipment(equipment_id),
    maintenance_date    DATE        NOT NULL,
    maintenance_type    VARCHAR(30) NOT NULL,
    content             TEXT,
    performed_by        VARCHAR(50) NOT NULL,
    next_maintenance_date DATE,
    remark              TEXT,
    created_at          TIMESTAMP   NOT NULL DEFAULT CURRENT_TIMESTAMP,
    created_by          VARCHAR(50),

    CONSTRAINT ck_maintenance_type CHECK (maintenance_type IN ('daily','periodic','special'))
);

CREATE INDEX ix_maintenance_equipment ON equipment_mgmt.equipment_maintenance(equipment_id, maintenance_date DESC);
CREATE INDEX ix_maintenance_next_date ON equipment_mgmt.equipment_maintenance(next_maintenance_date);
```

## 4.5 equipment_repair（维修记录）

### 4.5.1 字段定义

| **字段** | **类型** | **约束** | **UI 中文名** | **说明** |
|---|---|---|---|---|
| repair_id | SERIAL | PK | 维修ID | 内部主键 |
| equipment_id | INT | FK NOT NULL | 设备ID | 关联设备 |
| report_date | DATE | NOT NULL | 报修日期 | 发现故障/报修日期 |
| fault_description | TEXT | NOT NULL | 故障描述 | 故障现象描述 |
| repair_provider | VARCHAR(200) | | 维修单位 | 内部维修 / 外部服务商名称 |
| repair_type | VARCHAR(20) | NOT NULL DEFAULT 'external' | 维修类型 | internal / external |
| completion_date | DATE | | 完成日期 | 维修完成日期 |
| repair_cost | NUMERIC(12,2) | | 维修费用 | 维修费用（元） |
| conclusion | TEXT | | 维修结论 | 维修结果描述 |
| remark | TEXT | | 备注 | |
| created_at | TIMESTAMP | NOT NULL DEFAULT NOW() | 创建时间 | |
| created_by | VARCHAR(50) | | 创建人 | |

### 4.5.2 DDL

```sql
CREATE TABLE equipment_mgmt.equipment_repair (
    repair_id           SERIAL PRIMARY KEY,
    equipment_id        INT         NOT NULL REFERENCES equipment_mgmt.equipment(equipment_id),
    report_date         DATE        NOT NULL,
    fault_description   TEXT        NOT NULL,
    repair_provider     VARCHAR(200),
    repair_type         VARCHAR(20) NOT NULL DEFAULT 'external',
    completion_date     DATE,
    repair_cost         NUMERIC(12,2),
    conclusion          TEXT,
    remark              TEXT,
    created_at          TIMESTAMP   NOT NULL DEFAULT CURRENT_TIMESTAMP,
    created_by          VARCHAR(50),

    CONSTRAINT ck_repair_type CHECK (repair_type IN ('internal','external'))
);

CREATE INDEX ix_repair_equipment ON equipment_mgmt.equipment_repair(equipment_id, report_date DESC);
```

## 4.6 equipment_warranty（保修信息）

### 4.6.1 字段定义

| **字段** | **类型** | **约束** | **UI 中文名** | **说明** |
|---|---|---|---|---|
| warranty_id | SERIAL | PK | 保修ID | 内部主键 |
| equipment_id | INT | FK NOT NULL, UNIQUE | 设备ID | 关联设备（一台设备一条保修记录） |
| warranty_start | DATE | NOT NULL | 保修起始日 | 保修开始日期 |
| warranty_end | DATE | NOT NULL | 保修截止日 | 保修结束日期 |
| warranty_scope | TEXT | | 保修范围 | 保修覆盖范围描述 |
| provider_name | VARCHAR(200) | | 服务商 | 供应商/服务商名称 |
| provider_contact | VARCHAR(200) | | 联系方式 | 服务商联系电话/邮箱 |
| remark | TEXT | | 备注 | |
| created_at | TIMESTAMP | NOT NULL DEFAULT NOW() | 创建时间 | |
| updated_at | TIMESTAMP | NOT NULL DEFAULT NOW() | 更新时间 | |

### 4.6.2 DDL

```sql
CREATE TABLE equipment_mgmt.equipment_warranty (
    warranty_id         SERIAL PRIMARY KEY,
    equipment_id        INT         NOT NULL REFERENCES equipment_mgmt.equipment(equipment_id),
    warranty_start      DATE        NOT NULL,
    warranty_end        DATE        NOT NULL,
    warranty_scope      TEXT,
    provider_name       VARCHAR(200),
    provider_contact    VARCHAR(200),
    remark              TEXT,
    created_at          TIMESTAMP   NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at          TIMESTAMP   NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT uq_warranty_equipment UNIQUE (equipment_id),
    CONSTRAINT ck_warranty_dates CHECK (warranty_end >= warranty_start)
);

CREATE INDEX ix_warranty_end ON equipment_mgmt.equipment_warranty(warranty_end);
```

## 4.7 equipment_attachment（设备附件）

### 4.7.1 字段定义

| **字段** | **类型** | **约束** | **UI 中文名** | **说明** |
|---|---|---|---|---|
| attachment_id | SERIAL | PK | 附件ID | 内部主键 |
| equipment_id | INT | FK NOT NULL | 设备ID | 关联设备 |
| file_name | VARCHAR(255) | NOT NULL | 文件名 | 原始文件名 |
| file_path | VARCHAR(500) | NOT NULL | 存储路径 | 服务器存储路径 |
| file_size | INT | | 文件大小 | 字节数 |
| file_type | VARCHAR(20) | | 文件类型 | pdf / image / doc / other |
| tag | VARCHAR(30) | | 分类标签 | sop / certificate / contract / photo / other |
| description | VARCHAR(200) | | 说明 | 附件说明 |
| uploaded_at | TIMESTAMP | NOT NULL DEFAULT NOW() | 上传时间 | |
| uploaded_by | VARCHAR(50) | | 上传人 | |

### 4.7.2 DDL

```sql
CREATE TABLE equipment_mgmt.equipment_attachment (
    attachment_id   SERIAL PRIMARY KEY,
    equipment_id    INT          NOT NULL REFERENCES equipment_mgmt.equipment(equipment_id),
    file_name       VARCHAR(255) NOT NULL,
    file_path       VARCHAR(500) NOT NULL,
    file_size       INT,
    file_type       VARCHAR(20),
    tag             VARCHAR(30),
    description     VARCHAR(200),
    uploaded_at     TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    uploaded_by     VARCHAR(50),

    CONSTRAINT ck_attachment_tag CHECK (tag IS NULL OR tag IN ('sop','certificate','contract','photo','other'))
);

CREATE INDEX ix_attachment_equipment ON equipment_mgmt.equipment_attachment(equipment_id);
```

## 4.8 equipment_reminder（到期提醒配置）

### 4.8.1 字段定义

| **字段** | **类型** | **约束** | **UI 中文名** | **说明** |
|---|---|---|---|---|
| reminder_id | SERIAL | PK | 提醒ID | 内部主键 |
| equipment_id | INT | FK NOT NULL | 设备ID | 关联设备 |
| reminder_type | VARCHAR(30) | NOT NULL | 提醒类型 | calibration / maintenance / warranty |
| due_date | DATE | NOT NULL | 到期日期 | 需要完成的到期日期 |
| advance_days | INT | NOT NULL DEFAULT 30 | 提前天数 | 提前多少天开始提醒 |
| is_resolved | BOOLEAN | NOT NULL DEFAULT FALSE | 是否已处理 | 处理后标记为已完成 |
| resolved_at | TIMESTAMP | | 处理时间 | |
| resolved_by | VARCHAR(50) | | 处理人 | |
| remark | TEXT | | 备注 | |
| created_at | TIMESTAMP | NOT NULL DEFAULT NOW() | 创建时间 | |

### 4.8.2 DDL

```sql
CREATE TABLE equipment_mgmt.equipment_reminder (
    reminder_id     SERIAL PRIMARY KEY,
    equipment_id    INT         NOT NULL REFERENCES equipment_mgmt.equipment(equipment_id),
    reminder_type   VARCHAR(30) NOT NULL,
    due_date        DATE        NOT NULL,
    advance_days    INT         NOT NULL DEFAULT 30,
    is_resolved     BOOLEAN     NOT NULL DEFAULT FALSE,
    resolved_at     TIMESTAMP,
    resolved_by     VARCHAR(50),
    remark          TEXT,
    created_at      TIMESTAMP   NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT ck_reminder_type CHECK (reminder_type IN ('calibration','maintenance','warranty'))
);

CREATE INDEX ix_reminder_due ON equipment_mgmt.equipment_reminder(due_date) WHERE is_resolved = FALSE;
CREATE INDEX ix_reminder_equipment ON equipment_mgmt.equipment_reminder(equipment_id);
```

# 5. Schema: labops_auth（认证与权限升级）

## 5.1 升级说明

现有 material_mgmt.app_user 采用硬编码 3 角色（admin / warehouse_admin / user）。升级为 RBAC 模型，支持灵活的角色权限组合。

迁移策略：
- labops_auth 新 schema 独立建表
- 数据从 material_mgmt.app_user 迁移
- 迁移期间旧表保留，Streamlit 前端继续使用旧表
- React 前端使用新表
- Streamlit 完全退役后删除旧表

## 5.2 labops_auth.user

| **字段** | **类型** | **约束** | **UI 中文名** | **说明** |
|---|---|---|---|---|
| user_id | SERIAL | PK | 用户ID | |
| username | VARCHAR(50) | UNIQUE, NOT NULL | 用户名 | 登录名，不可修改 |
| password_hash | VARCHAR(255) | NOT NULL | 密码 | bcrypt 哈希 |
| full_name | VARCHAR(100) | | 姓名 | |
| email | VARCHAR(200) | | 邮箱 | |
| department | VARCHAR(50) | | 部门 | |
| is_active | BOOLEAN | NOT NULL DEFAULT TRUE | 状态 | |
| must_change_password | BOOLEAN | NOT NULL DEFAULT FALSE | 需改密 | |
| created_at | TIMESTAMP | NOT NULL DEFAULT NOW() | 创建时间 | |
| last_login_at | TIMESTAMP | | 上次登录 | |

## 5.3 labops_auth.role

| **字段** | **类型** | **约束** | **UI 中文名** | **说明** |
|---|---|---|---|---|
| role_id | SERIAL | PK | 角色ID | |
| role_code | VARCHAR(32) | UNIQUE, NOT NULL | 角色代码 | sys_admin / warehouse_admin / equipment_admin / user |
| role_name | VARCHAR(64) | NOT NULL | 角色名称 | 中文显示名 |
| description | TEXT | | 角色描述 | |
| is_system | BOOLEAN | NOT NULL DEFAULT FALSE | 系统预置 | 系统角色不可删除 |
| created_at | TIMESTAMP | NOT NULL DEFAULT NOW() | 创建时间 | |

预置角色：

```sql
INSERT INTO labops_auth.role (role_code, role_name, description, is_system) VALUES
    ('sys_admin',       '系统管理员', '全权限，包括用户管理和审计',     TRUE),
    ('warehouse_admin', '库管员',     '物料模块全权限（入出库等）',     TRUE),
    ('equipment_admin', '设备管理员', '设备模块全权限（校验/维护等）', TRUE),
    ('user',            '普通用户',   '只读 + 基本查询',               TRUE);
```

## 5.4 labops_auth.permission

| **字段** | **类型** | **约束** | **UI 中文名** | **说明** |
|---|---|---|---|---|
| permission_id | SERIAL | PK | 权限ID | |
| permission_code | VARCHAR(64) | UNIQUE, NOT NULL | 权限代码 | 如 material:create |
| module | VARCHAR(32) | NOT NULL | 模块 | material / equipment / admin / audit |
| action | VARCHAR(32) | NOT NULL | 操作 | access / create / update / delete |
| description | VARCHAR(200) | | 权限说明 | |

预置权限：

```sql
INSERT INTO labops_auth.permission (permission_code, module, action, description) VALUES
    ('material:access',   'material',  'access',  '访问物料模块'),
    ('material:create',   'material',  'create',  '新增物料/入库/导入'),
    ('material:update',   'material',  'update',  '编辑物料/出库/盘点/移库'),
    ('material:delete',   'material',  'delete',  '停用物料'),
    ('equipment:access',  'equipment', 'access',  '访问设备模块'),
    ('equipment:create',  'equipment', 'create',  '新增设备/记录校验维护'),
    ('equipment:update',  'equipment', 'update',  '编辑设备/更新记录'),
    ('equipment:delete',  'equipment', 'delete',  '报废设备'),
    ('admin:user_manage', 'admin',     'manage',  '用户管理'),
    ('admin:audit_read',  'admin',     'read',    '查看审计日志');
```

## 5.5 labops_auth.user_role 与 role_permission

```sql
CREATE TABLE labops_auth.user_role (
    user_id   INT NOT NULL REFERENCES labops_auth.user(user_id),
    role_id   INT NOT NULL REFERENCES labops_auth.role(role_id),
    granted_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (user_id, role_id)
);

CREATE TABLE labops_auth.role_permission (
    role_id       INT NOT NULL REFERENCES labops_auth.role(role_id),
    permission_id INT NOT NULL REFERENCES labops_auth.permission(permission_id),
    PRIMARY KEY (role_id, permission_id)
);
```

## 5.6 labops_auth.login_session

与现有 auth_session 基本一致，迁移到新 schema：

| **字段** | **类型** | **约束** | **UI 中文名** | **说明** |
|---|---|---|---|---|
| token | VARCHAR(64) | PK | 登录凭证 | 随机 hex token |
| user_id | INT | FK NOT NULL | 用户ID | |
| created_at | TIMESTAMP | NOT NULL DEFAULT NOW() | 登录时间 | |
| expires_at | TIMESTAMP | NOT NULL | 过期时间 | |
| last_seen_at | TIMESTAMP | NOT NULL DEFAULT NOW() | 最近活跃 | |
| source_ip | VARCHAR(45) | | 来源IP | |

# 6. Schema: labops_audit（审计升级）

## 6.1 labops_audit.audit_log

升级版审计表，增加 module 和 reason 字段：

| **字段** | **类型** | **约束** | **UI 中文名** | **说明** |
|---|---|---|---|---|
| id | BIGSERIAL | PK | 日志ID | |
| user_id | INT | | 用户ID | 操作用户（允许 NULL，用户删后保留记录） |
| username | VARCHAR(50) | | 操作用户 | 冗余存储 |
| module | VARCHAR(30) | NOT NULL | 模块 | material / equipment / auth / admin |
| action | VARCHAR(50) | NOT NULL | 操作类型 | 如 material.create / equipment.calibrate |
| entity_type | VARCHAR(50) | | 对象类型 | 如 material / equipment / batch |
| entity_id | VARCHAR(50) | | 对象ID | |
| reason | VARCHAR(500) | | 操作原因 | 关键操作的原因说明 |
| before_json | JSONB | | 操作前 | 前快照（敏感字段已脱敏） |
| after_json | JSONB | | 操作后 | 后快照 |
| source_ip | VARCHAR(45) | | 来源IP | |
| created_at | TIMESTAMP | NOT NULL DEFAULT NOW() | 操作时间 | |

```sql
CREATE TABLE labops_audit.audit_log (
    id           BIGSERIAL PRIMARY KEY,
    user_id      INT,
    username     VARCHAR(50),
    module       VARCHAR(30) NOT NULL,
    action       VARCHAR(50) NOT NULL,
    entity_type  VARCHAR(50),
    entity_id    VARCHAR(50),
    reason       VARCHAR(500),
    before_json  JSONB,
    after_json   JSONB,
    source_ip    VARCHAR(45),
    created_at   TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT ck_audit_module CHECK (module IN ('material','equipment','auth','admin'))
);

CREATE INDEX ix_audit_user_time   ON labops_audit.audit_log(user_id, created_at DESC);
CREATE INDEX ix_audit_module_time ON labops_audit.audit_log(module, created_at DESC);
CREATE INDEX ix_audit_entity      ON labops_audit.audit_log(entity_type, entity_id, created_at DESC);
CREATE INDEX ix_audit_action      ON labops_audit.audit_log(action, created_at DESC);
```

# 7. MDM 数据边界说明

| **数据域** | **权威源** | **LabOps Portal 中的体现** |
|---|---|---|
| 物质身份（Substance） | MDM Portal | 不涉及 |
| 项目（Project） | MDM Portal | 不涉及 |
| 资产（Asset） | MDM Portal | 不涉及 |
| R&D 物料主数据 | MDM Portal（未来） | 不涉及，LabOps 的 material 是部门操作数据 |
| 部门物料库存 | LabOps Portal | 核心能力：批次、出入库、位置、库存 |
| 仪器设备管理 | LabOps Portal | 核心能力：台账、校验、维护、维修 |
| 用户认证 | 各系统独立 | 独立用户表（未来可对接 SSO） |

未来可选集成：
- LabOps material 可增加 mdm_substance_id 字段引用 MDM substance
- 设备数据完全在 LabOps 内部管理，不与 MDM 交互

# 8. 附录：设备 ERD

```text
┌──────────────────────────────────────────────────────────────┐
│              equipment_mgmt 实体关系图                        │
└──────────────────────────────────────────────────────────────┘

              ┌──────────────────────┐
              │  equipment           │
              │  ──────────────────  │
              │  PK equipment_id     │
              │  UQ equipment_code   │
              │     name             │
              │     category         │
              │     status           │
              └──┬──┬──┬──┬──┬──┬───┘
                 │  │  │  │  │  │
     ┌───────────┘  │  │  │  │  └───────────┐
     │              │  │  │  │              │
     ▼              ▼  │  ▼  │              ▼
┌──────────┐  ┌──────┐│┌──────┐│  ┌──────────────┐
│calibration│  │maint-│││repair││  │  attachment   │
│  (1:N)    │  │enance││└──────┘│  │    (1:N)     │
└──────────┘  └──────┘│  (1:N) │  └──────────────┘
                      │        │
                      ▼        ▼
               ┌──────────┐ ┌──────────┐
               │ warranty  │ │ reminder │
               │  (1:1)    │ │  (1:N)   │
               └──────────┘ └──────────┘
```
