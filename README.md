# CMC LabOps Portal (`cmc-labops`)

> CMC 部门运营平台(原"CMC 物料管理系统",集成设备管理后更名,命名决策见 docs/架构设计文档 §1.2)。
> **物料库存模块**聚焦核心闭环:物料导入 → 入库 → 出库 → 移库 → 盘点 → 库存统计 → 预警;
> **仪器设备模块**覆盖:台账 → 计量校验 → 维护 → 维修 → 保修 → 附件 → 到期预警。
> 认证对接 CMAB MDM Portal(JWT);物料/设备主数据以 MDM 为权威源,本系统持运营数据。
> 不涉及 GMP 合规、申购审批、CoA 管理等扩展模块,这些将在后续迭代中逐步加入。

---

## 一、项目目标

为 CMC 部门提供一个**部门级**的物料管理工具,解决:

1. 物料主数据从公司物料代码表一次性导入,后续直接下拉检索使用,**减少人工录入**
2. 重要试剂、关键耗材的**批次级**入库 / 出库登记;同批号可以分散在多个柜位独立计数
3. **移库**(同批号不丢链地从一个柜位搬到另一个柜位)
4. 实时库存统计(按物料、按批次、按位置)
5. **低库存预警**(对比安全库存)+ **效期预警**(30/90 天分级)
6. 物料**软删除**(停用),保证历史数据可追溯
7. 多用户 + 角色控制(admin / warehouse_admin / user),所有写操作落 **audit_log**
8. **危化品分类标识**(危化品 / 易燃 / 易制毒 / 易制爆 / 剧毒品,多选)在物料卡 + 入库页醒目展示

**明确不做(当前阶段范围外)**:申购审批流、CoA 文件管理、质量状态管理、供应商管理、GMP 合规审计追踪(电子签名)、报表看板、ERP/LIMS 对接。

> ⚠️ 本节为 v1.2 时期的目标描述。v2.x 起新增仪器设备模块,并对接 CMAB MDM Portal,
> 边界见下节"与 MDM 的关系"及 docs/ 设计文档(V1.1~V1.4 修订记录)。
> **下文凡提及 Streamlit 前端、本地账号/改密/用户管理的章节均为 v1.2 历史快照**,
> 现状:React 前端(frontend-react/) + MDM 统一认证,旧 Streamlit 代码已删除。

---

## 一·五、与 CMAB MDM Portal 的关系(v2.x)

| 能力 | 在哪做 | 说明 |
|---|---|---|
| 登录认证 / 用户 / 角色 | **MDM Portal** | 本系统代理 MDM 登录,本地校验其 JWT;不建用户表 |
| 物料主数据(编码/名称/厂家/规格) | **MDM Portal**(mm.material) | 本系统前端无新增入口,"物料查询"页只读 |
| 设备主数据(三标识/名称/型号/序列号/分类/工作站等) | **MDM Portal**(eqp.equipment,系统编码 EQP-yyyyXXXXXX + 业务编号 + 固定资产号) | 设备新增仅"从 MDM 引用",编辑仅运营字段;V1.4 起快照含全部主数据字段 |
| 物料出入库/移库/盘点/库存/预警 | **本系统** | material_mgmt schema |
| 设备运营(状态/位置/负责人/校验/维护/维修/保修/附件) | **本系统** | equipment_mgmt schema |

集成机制(关键约定):
- 两系统为**独立 PG 实例**,不跨库外键;本地表存快照 + `mdm_*_id` / `data_source`(mdm/local)标记
- **用时拉取 + 手动刷新**:MDM 登记后无后台同步任务,物料在首次入库、设备在建档时按编码实时拉取;
  设备详情页"从 MDM 刷新"(POST /api/equipment/{id}/sync-mdm)可整体覆盖快照并同步 MDM 状态(active/retired)
- **设备台账批量初始化**:列表页"从 MDM 批量同步"(POST /api/equipment/batch-from-mdm)一次性把 MDM
  在册设备全部引用建档(已存在跳过),可重复执行做增量;运营字段(房间/负责人)建档后逐台补录
- 查无主数据时,各入口提供"**去 MDM 登记**"跳转(MDM 新建页 `?code=/?name=` 预填;
  地址由 `frontend-react/.env` 的 `VITE_MDM_PORTAL_URL` 配置)
- 本地建档端点(POST /api/materials、/api/equipment)仅作后端 API 兜底,前端无入口
- LabOps 写权限角色随 MDM JWT 下发:`SYS_ADMIN` / `CMC_WAREHOUSE_ADMIN`(物料) /
  `CMC_EQUIPMENT_ADMIN`(设备)
- MDM 侧设计文档:DM-MDM-001 V1.2 §10A、API-MDM-001 V1.2 §5.1.6A(cmab-mdm-platform/docs/)

---

## 二、技术栈

| 层 | 技术 |
|----|------|
| 数据库 | PostgreSQL 16,复用现有实例,新建 schema `material_mgmt`(Mac 调试时 PG 在 Docker;Linux 生产时 PG 原生装在宿主机) |
| 后端 | Python 3.11+ / FastAPI / SQLAlchemy 2.0 / Pydantic v2 |
| 前端 | **React 18 + TypeScript + Ant Design 5 + Vite**(frontend-react/,v2.x 起;旧 Streamlit 前端已删除,历史描述见下文各 v1.2 章节) |
| 文件导入 | pandas + openpyxl(Excel 读取) |
| 部署 | **不用 Docker 跑应用**。Mac:venv 直接起进程;Linux:venv + systemd unit |
| 认证 | **对接 CMAB MDM Portal**(v2.0 起):登录代理 MDM /auth/login,后端本地校验 MDM 签发的 JWT;不建本地用户表,账号/角色/改密都在 MDM 操作 |
| 审计 | 写操作统一落 `audit_log`,记录用户 / 实体 / 前后快照 / 来源 IP |

---

## 三、目录结构

```
cmc-labops/
├── README.md                        本文档(开发与 Mac 调试指南)
├── DEPLOY.md                        Linux 服务器部署指南(生产)
├── install.sh                       Linux 一键装/起/重启/卸载脚本
├── restart.sh                       Linux 服务器日常一键重启脚本
├── 重启库存系统.command              macOS 双击重启本机前后端并打开网页
├── .env.example                    环境变量样例
├── .gitignore
├── sql/
│   ├── init.sql                    物料模块建表 + 字典初始化(末尾含迁移段)
│   └── equipment_init.sql          设备模块建表(equipment_mgmt schema,末尾含迁移段)
├── systemd/
│   ├── cmc-backend.service         FastAPI 后端 systemd unit(Linux)
│   └── cmc-frontend.service        React 前端 systemd unit(vite preview 伺服 dist,Linux)
├── backend/
│   ├── requirements.txt
│   ├── main.py                     FastAPI 入口
│   ├── database.py                 PG 连接配置
│   ├── models.py                   SQLAlchemy ORM
│   ├── schemas.py                  Pydantic 模型(物料)
│   ├── schemas_equipment.py        Pydantic 模型(设备)
│   ├── models_equipment.py         设备 ORM(equipment_mgmt 7 表)
│   ├── crud.py                     通用 CRUD
│   ├── mdm_client.py               MDM 主数据查询客户端(物料/设备透传)
│   ├── audit.py                    审计落库工具
│   ├── auth.py                     MDM JWT 校验 + 角色守卫
│   └── routers/
│       ├── __init__.py
│       ├── auth_router.py          登录(代理 MDM)/ 登出 / 当前用户
│       ├── admin_router.py         操作日志(用户管理已移交 MDM)
│       ├── material.py             物料 API(查询、from-mdm 引用、运营字段编辑)
│       ├── batch.py                批次 API
│       ├── inventory.py            出入库 / 盘点 / 移库 API
│       ├── stock.py                库存查询 + 预警 API
│       ├── location.py             储存位置 API
│       ├── import_data.py          Excel 导入 API(历史初始化例外,见 URD FR-MAT-001)
│       └── equipment.py            设备 API(台账/校验/维护/维修/保修/附件/MDM 同步)
├── frontend-react/                 React 前端(v2.x,旧 Streamlit 前端已删除)
│   ├── package.json
│   ├── vite.config.ts              5110 端口;dev/preview 均代理 /api → 后端
│   └── src/
│       ├── api/                    axios 封装 + 各模块 API/类型
│       ├── modules/                materials / equipment / alerts / admin 页面
│       ├── shared/                 布局、MDM 跳转等共享件
│       └── stores/                 登录态(zustand)
└── template/
    ├── generate_template.py        生成 Excel 模板的脚本
    └── 物料导入模板.xlsx            生成产物(.gitignore 排除,本地跑脚本生成)
```

---

## 四、数据模型(10 张表)

### 4.1 `material` — 物料主数据

| 字段 | 类型 | UI 中文名 | 说明 |
|------|------|------------|------|
| `material_id` | SERIAL PK | 物料ID | 物料内部主键 |
| `material_code` | VARCHAR(20) NOT NULL | 物料代码 / 代码 | 物料代码,**保留前导 0**;除 `TT内部物料` 外唯一 |
| `category` | VARCHAR(50) | 分类 | 分类(如"一般耗材"),来自导入文件 |
| `material_type` | VARCHAR(20) | TT分类 | 入库大类:reagent / consumable / standard / column |
| `name_cn` | VARCHAR(200) NOT NULL | 物料名称 | 物料名称(中文) |
| `grade` | VARCHAR(50) | 级别 | 级别(N/A 转 NULL) |
| `manufacturer` | VARCHAR(100) | 生产商 / 厂家 | 生产商 |
| `spec_model` | VARCHAR(200) | 规格/型号 | 规格/型号 |
| `catalog_no` | VARCHAR(100) | 货号 | 货号 |
| `unit` | VARCHAR(20) NOT NULL | 单位 | 单位(支/瓶/g/mL/盒/包等) |
| `package_spec` | VARCHAR(100) | 包装规格 | 包装规格 |
| `hazard_class` | TEXT[] | 危化品分类 | 危化品分类多选:危化品 / 易燃 / 易制毒 / 易制爆 / 剧毒品 |
| `remark` | TEXT | 备注 | 备注 |
| `safety_stock` | NUMERIC(12,2) DEFAULT 0 | 安全库存 | 安全库存(导入后单独维护) |
| `is_active` | BOOLEAN DEFAULT TRUE | 状态 | 启用标志(软删除) |
| `deactivated_at` | TIMESTAMP | 停用时间 | 停用时间 |
| `deactivated_by` | VARCHAR(50) | 停用操作人 | 停用操作人 |
| `deactivate_reason` | VARCHAR(200) | 停用原因 | 停用原因 |
| `import_batch_id` | INT FK | 导入批次ID | 导入批次,便于回溯 |
| `created_at` | TIMESTAMP | 创建时间 | 自动维护 |
| `updated_at` | TIMESTAMP | 更新时间 | 自动维护 |

### 4.2 `batch` — 批次

| 字段 | 类型 | UI 中文名 | 说明 |
|------|------|------------|------|
| `batch_id` | SERIAL PK | 批次ID | 批次内部主键 |
| `material_id` | INT FK | 物料ID | 关联 `material.material_id` |
| `batch_no` | VARCHAR(100) NOT NULL | 批号 | 供应商批号 |
| `expiry_date` | DATE | 效期 / 有效期 | 效期(可空,部分耗材无效期) |
| `location_id` | INT FK NOT NULL | 储存位置ID | 储存位置 |
| `received_date` | DATE NOT NULL | 到货日期 / 入库日期 | 到货日期 |
| `initial_qty` | NUMERIC(12,2) NOT NULL | 入库数量 | 首次入库数量 |
| `remark` | TEXT | 备注 | 备注 |
| `intake_type` | VARCHAR(20) | 入库类型 | 本批次入库时所在大类 |
| `concentration` | VARCHAR(50) | 浓度 | 标准物质浓度 |
| `extinction_coefficient` | NUMERIC(12,2) | 消光系数 | 标准物质消光系数 |
| `serial_no` | VARCHAR(100) | 序列号 | 色谱柱序列号 |
| `asset_no` | VARCHAR(100) | 内部编号 / 资产编号 | 色谱柱内部编号/资产编号 |
| `responsible_person` | VARCHAR(50) | 负责人 | 色谱柱负责人 |
| `created_at` | TIMESTAMP | 创建时间 | 自动维护 |

**唯一约束**: `(material_id, batch_no, location_id)` 联合唯一。同一物料同一批号允许分散在多个位置上独立计数。

### 4.3 `inventory_txn` — 出入库流水(库存计算的唯一来源)

| 字段 | 类型 | UI 中文名 | 说明 |
|------|------|------------|------|
| `txn_id` | SERIAL PK | 流水ID / 记录ID | 出入库流水内部主键 |
| `batch_id` | INT FK NOT NULL | 批次ID | 关联批次 |
| `txn_type` | VARCHAR(10) NOT NULL | 操作类型 | `IN` / `OUT` / `ADJUST` |
| `qty` | NUMERIC(12,2) NOT NULL | 数量 / 调整量 | **入库为正,出库为负,调整有正有负** |
| `txn_date` | DATE NOT NULL | 日期 / 发生日期 | 发生日期 |
| `operator` | VARCHAR(50) NOT NULL | 经办人 | 经办人姓名,自动取当前登录用户 |
| `purpose` | VARCHAR(200) | 用途 / 项目编号 | 用途/项目编号(出库时填) |
| `remark` | TEXT | 备注 | 备注 |
| `created_at` | TIMESTAMP | 创建时间 | 自动维护 |

**关键设计原则**: 库存数量**不存表**,实时由 `inventory_txn` 聚合计算,杜绝账实不符。

### 4.4 `location` — 储存位置

| 字段 | 类型 | UI 中文名 | 说明 |
|------|------|------------|------|
| `location_id` | SERIAL PK | 位置ID | 储存位置内部主键 |
| `room_no` | VARCHAR(20) NOT NULL | 房间号 | 房间号 |
| `cabinet_no` | VARCHAR(20) NOT NULL | 柜号 | 柜号 |
| `layer_no` | SMALLINT NOT NULL | 层号 | 层号,必须 >= 1 |
| `name` | VARCHAR(80) GENERATED | 储存位置 / 位置 | 生成展示名,如 `2251-A01-L1` |
| `storage_condition` | VARCHAR(50) | 储存条件 | 常温 / 4℃ / -20℃ / -80℃ / 避光 |
| `remark` | TEXT | 备注 | 备注 |

**唯一约束**: `(room_no, cabinet_no, layer_no)`。

### 4.5 `unit_dict` — 单位字典

| 字段 | 类型 | UI 中文名 | 说明 |
|------|------|------------|------|
| `unit` | VARCHAR(20) PK | 单位 | 如 支、瓶、g、mL |
| `description` | VARCHAR(100) | 单位说明 | 单位说明 |

**预置值**(从导入样本提取): 张、卷、个、盒、包、根、袋、瓶、把、kg、支、g、mg、mL、L

### 4.6 `category_dict` — 分类字典

| 字段 | 类型 | UI 中文名 | 说明 |
|------|------|------------|------|
| `category` | VARCHAR(50) PK | 分类 | 物料分类名称 |

**初始为空**,导入时自动从文件中提取唯一值入库。

### 4.7 `import_log` — 导入日志

| 字段 | 类型 | UI 中文名 | 说明 |
|------|------|------------|------|
| `import_id` | SERIAL PK | 导入ID | 导入记录内部主键 |
| `file_name` | VARCHAR(200) | 文件名 | 导入文件名 |
| `imported_at` | TIMESTAMP | 导入时间 | 导入发生时间 |
| `operator` | VARCHAR(50) | 操作人 | 导入操作人 |
| `total_rows` | INT | 总行数 | 导入总行数 |
| `inserted_rows` | INT | 新增行数 | 成功新增行数 |
| `updated_rows` | INT | 更新行数 | 成功更新行数 |
| `failed_rows` | INT | 失败行数 | 导入失败行数 |
| `error_detail` | JSONB | 错误详情 | 失败行详情 |

### 4.8 `app_user` — 应用账号

| 字段 | 类型 | UI 中文名 | 说明 |
|------|------|------------|------|
| `id` | SERIAL PK | 用户ID | 用户内部主键 |
| `username` | VARCHAR(50) UNIQUE | 用户名 | 登录名 |
| `password_hash` | VARCHAR(255) | 密码 | bcrypt hash,页面不显示明文 |
| `role` | VARCHAR(20) | 角色 | `admin` / `warehouse_admin` / `user` |
| `is_active` | BOOLEAN | 状态 | 是否启用 |
| `must_change_password` | BOOLEAN | 需改密 | 是否要求下次登录改密 |
| `created_at` | TIMESTAMP | 创建时间 | 创建时间 |
| `last_login_at` | TIMESTAMP | 上次登录 | 最近登录时间 |

### 4.9 `auth_session` — 登录会话

| 字段 | 类型 | UI 中文名 | 说明 |
|------|------|------------|------|
| `token` | VARCHAR(64) PK | 登录凭证 | 随机 hex token,页面不直接显示 |
| `user_id` | INT FK | 用户ID | 登录用户 |
| `created_at` | TIMESTAMP | 登录时间 | 会话创建时间 |
| `expires_at` | TIMESTAMP | 过期时间 | 会话过期时间 |
| `last_seen_at` | TIMESTAMP | 最近活跃时间 | 最近一次访问时间 |
| `source_ip` | VARCHAR(45) | 来源IP | 来源 IP |

### 4.10 `audit_log` — 操作日志

| 字段 | 类型 | UI 中文名 | 说明 |
|------|------|------------|------|
| `id` | BIGSERIAL PK | 日志ID | 操作日志内部主键 |
| `user_id` | INT | 用户ID | 操作用户ID |
| `username` | VARCHAR(50) | 操作用户 | 操作用户名,冗余保留 |
| `action` | VARCHAR(50) | 操作类型 | 如 `material.update`、`inventory.transfer` |
| `entity_type` | VARCHAR(50) | 对象类型 | 被操作对象类型 |
| `entity_id` | VARCHAR(50) | 对象ID | 被操作对象ID |
| `before_json` | JSONB | 操作前 | 操作前快照 |
| `after_json` | JSONB | 操作后 | 操作后快照 |
| `source_ip` | VARCHAR(45) | 来源IP | 来源 IP |
| `created_at` | TIMESTAMP | 操作时间 | 操作发生时间 |

---

## 五、核心业务逻辑

### 5.1 物料编码处理(关键)

- `material_code` 存储为 `VARCHAR(20)`,**严格保留前导 0**
- `material_id` 是内部主键;`material_code='TT内部物料'` 允许重复,其余编码唯一
- Excel 读取时强制全列字符串 + 关掉 NaN 自动识别(实现见 `backend/routers/import_data.py`):
  ```python
  pd.read_excel(file, dtype=str, keep_default_na=False)
  ```
- 导入预览时,若检测到以 `0` 开头的编码,**前端弹窗提示用户核对**,避免 Excel 自动去 0

### 5.2 N/A 与空白处理

- 原表中 `N/A`、空字符串、`NaN` **统一转为 NULL**
- 前端展示时 NULL 显示为 `-`

### 5.3 Excel 导入流程

```
①上传 Excel
   ↓
②自动按中文表头映射字段(代码→material_code, 物料名称→name_cn 等)
   ↓
③校验:
   - material_code 非空;除 `TT内部物料` 外唯一
   - name_cn、unit 非空
   - unit 在 unit_dict 中(否则提示先维护字典或自动加入)
   - 检测前导 0
   ↓
④干跑结果:"将插入 X 条 / 更新 Y 条 / 错误 Z 条"
   错误行可下载 Excel 查看原因
   ↓
⑤UPSERT 写入(按 material_code 更新;`TT内部物料` 按新增处理)
   - 同时插入 import_log
   - 自动从文件提取新分类写入 category_dict
   ↓
⑥成功提示
```

### 5.4 库存计算

```sql
-- 单批次实时库存
SELECT batch_id, SUM(qty) AS current_qty
FROM inventory_txn
GROUP BY batch_id;

-- 物料总库存(只计有效批次)
SELECT m.material_id, m.material_code, m.name_cn, SUM(t.qty) AS total_qty
FROM material m
JOIN batch b ON b.material_id = m.material_id
JOIN inventory_txn t ON t.batch_id = b.batch_id
GROUP BY m.material_id, m.material_code, m.name_cn;
```

### 5.5 预警规则

| 类型 | 规则 | 颜色 |
|------|------|------|
| 已过期 | `expiry_date < today` | 🔴 红色,**不计入可用库存** |
| 临近过期(紧急) | `0 ≤ expiry_date - today ≤ 30` | 🔴 红色 |
| 临近过期(预警) | `30 < expiry_date - today ≤ 90` | 🟡 黄色 |
| 低库存 | `物料总库存 < safety_stock` 且 `safety_stock > 0` | 🟡 黄色 |

### 5.6 物料停用(软删除)

- 设 `is_active = FALSE`,记录停用时间、操作人、原因
- 入库 / 出库下拉**不显示**已停用物料
- 库存查询**仍显示**(标灰 + "已停用"标签)
- 历史出入库记录完整保留
- 提供"查看已停用"切换开关 + 一键启用功能
- 停用时若仍有库存 > 0,**弹窗提示但允许停用**

---

## 六、前端页面设计(⚠️ v1.2 Streamlit 历史快照;现行 React UI 见 docs/UI信息架构与线框图 V1.4)

### 6.1 物料导入页
- 文件上传组件
- 上传后预览前 10 行
- 字段映射确认(自动匹配,允许人工调整)
- "干跑校验"按钮 → 显示统计 + 错误行下载
- "确认导入"按钮 → 执行 + 显示结果
- 历史导入记录列表(最近 20 次)

### 6.2 物料管理页
- 检索栏: 分类筛选 + 名称/编码模糊搜索 + "查看已停用"开关
- 物料列表(表格)
- 管理员和库管理员可新增/编辑物料,维护安全库存和危化品分类
- 行内操作: 编辑、停用/启用
- 停用时弹窗输入原因

### 6.3 入库登记页
- 物料选择(三层级联: 分类 → 模糊搜索 → 选中)
- 批号、效期、储存位置(房间/柜号/层)、到货日期、入库数量、备注
- 经办人自动取当前登录用户
- 同一物料同一批号同一位置已存在 → 追加入库(创建新 txn 而非新 batch)
- 提交后显示当前批次库存

### 6.4 出库登记页
- 物料选择(同上,但只显示**有库存**的物料)
- 批次选择(显示该物料的可用批次,默认按效期升序 - FIFO 建议)
- 出库数量(校验不超过批次现有库存)
- 经办人自动取当前登录用户,可填用途/项目编号、备注
- 已过期批次默认不显示,可勾选"显示已过期"

### 6.5 库存查询页
- 筛选: 分类、物料、储存位置、是否含已停用、是否含已过期
- 两种视图切换:
  - 按物料汇总(总库存)
  - 按批次明细(批次级库存)
- 支持导出 Excel

### 6.6 库存预警页
- 三个 Tab:
  - 🔴 已过期 + 临近过期(30 天内)
  - 🟡 临近过期(30-90 天)
  - 🟡 低库存(低于安全库存)
- 每个列表显示: 物料、批号、效期、剩余天数、库存量、储存位置
- 支持导出 Excel

### 6.7 盘点调整页
- 选物料 → 选批次(可含过期)→ 显示账面库存
- 两种调整方式:
  - 按**实际盘点数**:输入物理盘点数,前端自动算 delta
  - 按**调整量**:直接输入正负调整量
- 经办人自动取当前登录用户,可填备注(建议填盘点单号 / 原因)
- 后端校验:调整后批次库存不得 < 0,否则拒绝
- 与出入库共用 `inventory_txn` 表,`txn_type='ADJUST'` 区分

### 6.8 用户管理页
- 管理员维护用户、角色、启停状态
- 管理员可重置密码并要求用户下次登录改密
- 操作日志 tab 查询所有写操作的审计记录

### 6.9 移库页
- 选择源批次、目标位置、数量和日期
- 后端将一次移库落为源批次 OUT + 目标批次 IN 两条流水
- 目标位置若已有同物料同批号批次则追加,否则自动创建目标批次

---

## 七、API 设计(FastAPI)

> ⚠️ 本节为 v1.2 时期的物料 API 清单,未含 v2.x 新增内容,完整现状以代码 `backend/routers/` 为准:
> - 设备模块全套 API(台账/校验/维护/维修/保修/附件/预警)见 `routers/equipment.py` 头注释
> - MDM 集成端点:`/api/mdm/materials*`、`/api/mdm/equipments*`(透传)、`POST /api/materials/from-mdm/{code}`、
>   `POST /api/equipment/from-mdm/{code}`、`POST /api/equipment/{id}/sync-mdm`、`POST /api/equipment/batch-from-mdm`
> - 用户管理/改密端点已于 v2.0 移交 MDM Portal(本地仅保留 /api/auth/login 代理与 /api/users/me)

默认情况下,查询接口要求已登录;物料、批次、出入库、移库、导入、位置新增等业务写操作要求 `admin` 或 `warehouse_admin`;用户管理和审计日志只允许 `admin`。

### 7.1 物料相关 `/api/materials`

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/materials` | 查询(支持 `category`、`keyword`、`include_inactive`、`is_active` 过滤) |
| POST | `/api/materials` | 新增物料(admin / warehouse_admin) |
| GET | `/api/materials/{material_id}` | 详情 |
| PATCH | `/api/materials/{material_id}` | 更新(admin / warehouse_admin) |
| POST | `/api/materials/{material_id}/deactivate` | 停用(admin / warehouse_admin,body: reason) |
| POST | `/api/materials/{material_id}/activate` | 启用(admin / warehouse_admin) |
| GET | `/api/categories` | 分类字典 |
| GET | `/api/units` | 单位字典 |

### 7.2 批次 `/api/batches`

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/batches` | 查询(支持 `material_id` 过滤) |
| POST | `/api/batches` | 创建批次(同时创建首次入库 txn) |
| GET | `/api/batches/{batch_id}` | 详情 |

### 7.3 出入库 `/api/inventory`

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/inventory/in` | 入库(对已有批次追加) |
| POST | `/api/inventory/out` | 出库 |
| POST | `/api/inventory/adjust` | 调整(盘点用,可正可负) |
| POST | `/api/inventory/transfer` | 移库(源 OUT + 目标 IN) |
| GET | `/api/inventory/txns` | 流水查询(支持 `batch_id`、`material_id`) |

### 7.4 库存与预警 `/api/stock`

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/stock/by-material` | 按物料汇总库存 |
| GET | `/api/stock/by-batch` | 按批次明细库存 |
| GET | `/api/stock/alerts/expiry` | 效期预警(参数: days=30/90) |
| GET | `/api/stock/alerts/low-stock` | 低库存预警 |

### 7.5 位置 `/api/locations`

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/locations` | 查询 |
| POST | `/api/locations` | 新增 |

### 7.6 导入 `/api/import`

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/import/materials/dry-run` | 干跑校验 |
| POST | `/api/import/materials/commit` | 正式导入 |
| GET | `/api/import/logs` | 导入历史 |

### 7.7 鉴权 / 审计(v2.0 修订:用户管理移交 MDM Portal)

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/auth/login` | 登录(代理 MDM /auth/login,返回 MDM 签发的 JWT) |
| POST | `/api/auth/logout` | 登出 |
| GET | `/api/users/me` | 当前用户(解码 JWT) |
| GET | `/api/audit/logs` | 操作日志(SYS_ADMIN) |

> 改密 / 用户增删改 / 重置密码 / 角色分配均在 **MDM Portal** 操作,本系统已无这些端点。

---

## 八、部署形态(Mac 调试 / Linux 生产)

应用本身**不用 Docker 跑**(直接 venv + 进程),只是 mac 本机的 PG 在 Docker 里。

|  | Mac(开发调试) | Linux(生产) |
|---|---|---|
| PostgreSQL | Docker 容器,host 端口暴露(默认 5432) | 宿主机原生(`apt install postgresql`) |
| 后端 / 前端 | 后端 venv+`uvicorn`,前端 `npm run dev`(Vite) | 后端 venv+systemd,前端 `npm run build`+vite preview(systemd,由 `install.sh` 装) |
| 数据库主机 | `127.0.0.1`(到 docker 暴露端口) | `127.0.0.1`(到宿主机 PG) |
| 是否跑 `install.sh` | **不要跑**(`systemctl`/`sudo` 在 mac 没意义) | **要跑**,见 `DEPLOY.md` |

后端只通过 `DATABASE_URL` 连库,所以两套环境的代码完全一致,差别只在 `.env` 里的连接串和起进程的方式。

---

## 九、环境变量(`.env.example`)

```
BACKEND_PORT=8010
FRONTEND_PORT=5110
DATABASE_URL=postgresql://cmc_user:<your-password>@127.0.0.1:5432/cmc_data_platform
API_BASE_URL=http://localhost:8010
MDM_BASE_URL=http://127.0.0.1:18000/api/v1
MDM_TIMEOUT=5
MDM_SECRET_KEY=<must-match-mdm-backend-secret-key>
MDM_JWT_ALGORITHM=HS256
```

> systemd 用 `EnvironmentFile=` 直接加载本文件,**KEY=VALUE 之间不能有空格,不要加引号**。
> Mac 调试时同样可以读这份 `.env`,但没有强制格式约束。
> 部署前务必把 `<your-password>` 换成你在 §10 第 1 步建库时设的真实密码;`.env` 已被 `.gitignore` 排除,不会进库。

---

## 十、启动步骤

### 10.A Mac 本机调试(PG 在 Docker,后端/前端在 venv)

#### 日常一键重启(推荐)

如果本机环境已经装好、`.env` 已配置好,平时不要手动找 PID,直接双击项目根目录里的:

```text
重启库存系统.command
```

它会自动:

1. 停掉本项目旧的前端进程(`FRONTEND_PORT`,固定 5110)
2. 停掉本项目旧的后端进程(`BACKEND_PORT`,固定 8010)
3. 重新启动 FastAPI 后端
4. 重新启动 React 前端(Vite dev server)
5. 打开浏览器到前端页面(登录依赖 MDM Portal,请确保其 Docker 已启动)

日志写在:

```text
logs/backend.log
logs/frontend.log
```

> 如果 macOS 提示无法打开,先在终端执行一次:
>
> ```bash
> chmod +x 重启库存系统.command
> ```

#### 首次本机初始化

> 当前 mac 环境的 PG 容器:**`rd_pg`**(host 端口 5432,`postgres` 超管无需密码)。
> 数据库 `cmc_data_platform` 已存在。如果你的环境不一样,把下面的容器名 / 端口 / 库名同步替换。

```bash
# 0)(诊断用)确认 docker pg 在跑
docker ps --filter "name=rd_pg" --format "table {{.Names}}\t{{.Ports}}"

# 1) 在已有 PG 里新建用户 / schema(只做一次,库已存在所以不用 CREATE DATABASE)
docker exec -i rd_pg psql -U postgres -d cmc_data_platform <<'EOF'
CREATE USER cmc_user WITH PASSWORD '<your-password>';
CREATE SCHEMA material_mgmt AUTHORIZATION cmc_user;
GRANT CONNECT ON DATABASE cmc_data_platform TO cmc_user;
EOF

# 2) 用 cmc_user 跑建表脚本(不需要 mac 本机装 psql:仍走 docker exec)
docker exec -i -e PGPASSWORD='<your-password>' rd_pg \
    psql -h 127.0.0.1 -U cmc_user -d cmc_data_platform < sql/init.sql

# 3) 配 .env(默认值已对齐 docker pg 暴露在 127.0.0.1:5432 的情况)
cp .env.example .env
# 如果你的 docker pg host 端口不是 5432,改 DATABASE_URL 里的端口

# 4) 起后端(终端 A)
cd backend
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
# 加载 .env 后用 uvicorn --reload(开发热加载)
set -a; source ../.env; set +a
.venv/bin/uvicorn main:app --reload --host 127.0.0.1 --port "$BACKEND_PORT"

# 5) 起前端(终端 B,React + Vite)
cd frontend-react
npm install
npm run dev          # 固定 5110 端口,自动代理 /api 到后端 8010

# 6)(可选)生成 Excel 导入模板
cd template && python3 generate_template.py

# 7) 访问(以下端口若 .env 中改过,以 .env 为准)
#    前端: http://localhost:5110
#    后端 API 文档: http://localhost:8010/docs
#    注意:登录依赖 MDM Portal 后端(Docker,127.0.0.1:18000),需先启动
```

**Mac 常见问题**:

- *后端报 `password authentication failed`*:`.env` 里的密码与第 1 步 `CREATE USER` 时设的不一致,改一致后重启 uvicorn。
- *后端报 `permission denied for schema material_mgmt`*:第 2 步建表是用 postgres 跑的导致表归 postgres 所有,改用 cmc_user 跑(命令同上,带 `-U cmc_user`)。
- *前端报 `后端不可达`*:确认 uvicorn 在跑(`curl http://127.0.0.1:8010/health`);前端 dev/preview 均经 Vite 代理 /api,无需配 API 地址。
- *登录失败/401*:确认 MDM Portal 后端在跑(`curl http://127.0.0.1:18000/api/v1/health`),`.env` 的 `MDM_SECRET_KEY` 与 MDM 一致。
- *端口被占*:`lsof -iTCP -sTCP:LISTEN -P | grep -E '8010|5110'` 查谁占着,改 `.env` 中 `BACKEND_PORT` / `FRONTEND_PORT`(本项目端口编号 10,见 ~/code/PORTS.md)。

### 10.B Linux 生产部署

完整流程见 [`DEPLOY.md`](DEPLOY.md)。**首次部署**要点:

```bash
# 1) 在宿主机已有 PG 中建 schema/user(详见 DEPLOY.md §1)
sudo -u postgres psql -d cmc_data_platform <<'EOF'
CREATE USER cmc_user WITH PASSWORD '<your-password>';
CREATE SCHEMA material_mgmt AUTHORIZATION cmc_user;
GRANT CONNECT ON DATABASE cmc_data_platform TO cmc_user;
EOF
PGPASSWORD='<your-password>' psql -h 127.0.0.1 -U cmc_user -d cmc_data_platform -f sql/init.sql

# 2) 拉代码 + 配 .env
git clone git@github.com:qingcheng81/cmc-labops.git /opt/cmc-labops
cd /opt/cmc-labops && cp .env.example .env  # 改密码 / 端口

# 3) 一键装 venv + systemd unit + enable --now
./install.sh
```

#### 后续日常流程

最简单的日常重启方式:

```bash
ssh <你的用户>@<服务器IP>
cd /opt/cmc-labops
./restart.sh
```

`restart.sh` 会自动:

1. `sudo systemctl daemon-reload`
2. 重启 `cmc-backend`
3. 重启 `cmc-frontend`
4. 打印两个服务状态
5. 检查后端 `/health`
6. 打印前端访问地址

如果提示输入密码,输入 Linux 登录用户的密码即可。

也可以一行完成:

```bash
ssh <你的用户>@<服务器IP>
cd /opt/cmc-labops && ./restart.sh
```

按改动类型,稍微更完整的流程如下:

```bash
cd /opt/cmc-labops

# A. 改了 Python 代码 / 前端页面 → 拉代码并重启进程,不动 systemd
git pull
./restart.sh

# B. 改了 requirements.txt → 重装依赖再重启
git pull
./install.sh deps && ./restart.sh

# C. 改了 systemd unit / install.sh / .env.example 默认值 → 重装 + 重启
git pull
./install.sh install            # 会重装 unit、daemon-reload、enable --now
./restart.sh                    # 确保进程使用最新配置

# D. 只改了运行时 .env(不动代码) → 仅重启,让 systemd 重新加载 EnvironmentFile
./restart.sh
```

> `./install.sh restart` 仍然可用;`./restart.sh` 是更适合日常使用的简化入口,会额外打印状态、健康检查和访问地址。

#### 日志、状态、卸载

```bash
sudo journalctl -u cmc-backend -f             # 后端实时日志
sudo journalctl -u cmc-frontend -f            # 前端实时日志
sudo systemctl status cmc-backend cmc-frontend  # 状态摘要
./install.sh uninstall                         # 停服务 + 删 unit(数据库 / venv / 代码 都保留)
```

#### 访问入口

| 服务 | 地址 | 谁能访问 |
|---|---|---|
| 前端 React(vite preview) | `http://<server-ip>:<FRONTEND_PORT>`(默认 5110) | 任何能到服务器内网的人,直接浏览器打开 |
| 后端 FastAPI | `http://127.0.0.1:<BACKEND_PORT>` | **只允许服务器本机**;前端同机调用 |
| 后端 Swagger `/docs` | 走 SSH 隧道,见下 | 临时调试用 |

**后端为什么只绑 127.0.0.1?** 后端虽已有 JWT 鉴权,但内部 API 不需要直接暴露给所有内网用户;统一由同机前端(vite preview 的 /api 代理)调用更简单也更稳。
内网用户访问前端 5110 即可,所有 API 调用都在服务器内完成。

#### 在自己笔记本上看 Swagger `/docs`(SSH 隧道)

前端首页那行"后端 API 仅限服务器本机访问"提示就是这个意思 — 链接不要点,而是按下面的方式开隧道:

```bash
# 在自己笔记本上跑;开着不要关,期间浏览器才能访问 http://localhost:28010/docs
# (本地端口避开 18000:那是 MDM 后端的本机约定端口)
ssh -L 28010:127.0.0.1:8010 -p <ssh-port> prometheus@<server-ip>

# 然后浏览器打开
#   http://localhost:28010/docs
```

### 10.C 首次使用(两套环境通用)

1. 打开「物料导入」页,上传贵司物料代码 Excel 完成主数据导入
2. 打开「物料管理」页,维护各物料的安全库存
3. 在「入库登记」页录入实际批次
4. 日常使用「出库登记」扣减,定期查看「库存预警」

---

## 十一、Excel 导入模板

模板由 `template/generate_template.py` 生成,产物 `template/物料导入模板.xlsx` 已在 `.gitignore` 中排除——克隆后本地跑一次脚本生成即可:

```bash
cd template && python3 generate_template.py
```

字段与贵司实际表对齐:

| 序号 | 分类 | 代码 | 物料名称 | 级别 | 生产商 | 规格/型号 | 货号 | 单位 | 包装规格 | 备注 |
|------|------|------|---------|------|--------|----------|------|------|---------|------|
| 1 | 一般耗材 | 42001 | PVC封膜(透明) | N/A | N/A | 50*33mm | N/A | 张 | | N/A |

**说明**:
- `序号` 列读取时**忽略**(非业务字段)
- `N/A` 与空白统一转 NULL
- `代码` 列必须以**文本格式**存储,避免前导 0 丢失
- `单位` 必须在 `unit_dict` 中,否则导入失败或自动追加(行为可配置)

---

## 十二、当前实现状态

当前代码已经完成(v2.x):

- 物料:Excel 导入(历史初始化例外)、只读"物料查询"、从 MDM 引用、安全库存维护
- 批次级入库、出库、盘点调整、移库;按物料/批次/位置查询实时库存
- 效期预警、低库存预警
- 设备:台账(从 MDM 引用/批量同步/快照刷新)、校验、维护、维修、保修、附件、到期预警
- MDM 统一认证(JWT 本地校验)、按角色守卫(前端路由 + 后端接口双层)
- 主数据写边界:data_source='mdm' 记录身份字段后端只读
- 操作日志审计(所有写操作含批次首笔流水)
- macOS 双击重启脚本和 Linux `restart.sh` 一键重启;后端测试 39 例全绿

仍明确不做:

- 申购/审批/CoA/质量状态/GMP 电子签名
- 应用容器化;应用仍按 venv/npm + 进程/systemd 运行

---

## 十三、后续路线图(仅作参考)

| 阶段 | 计划功能 |
|------|---------|
| 后续 A | 申购单(PR) + 简单审批流 |
| 后续 B | CoA 文件上传 + 关联批次 |
| 后续 C | 供应商主数据 + 质量状态(待检/合格/不合格) |
| ~~后续 D~~ | ~~对接公司 AD / SSO~~ ✅ 已由 MDM Portal 统一认证实现(v2.0) |
| 后续 E | 与 `rd_budget` 库联动 + 预算占用校验 |
| 后续 F | GMP 合规模式增强:电子签名、变更控制 |
| ~~后续 G~~ | ~~替换前端~~ ✅ 已迁移 React 18 + AntD 5(v2.x);移动端扫码出入库待做 |

---

## 十四、测试

后端测试集中在核心账实计算、物料 CRUD、鉴权审计等路径,用例位于 `backend/tests/`。

```bash
cd backend
.venv/bin/pip install -r requirements-dev.txt        # 装 pytest + httpx

# 用一个独立的 PG database 跑测试(切勿指生产库 cmc_data_platform!)
# Mac 默认连 docker rd_pg 中的 postgres 库:
PGPASSWORD='<postgres超管密码>' \
  DATABASE_URL_TEST='postgresql://postgres@127.0.0.1:5432/postgres' \
  .venv/bin/pytest tests/ -v

# Linux 同理,自己建一个测试库:
# sudo -u postgres createdb cmc_test
# DATABASE_URL_TEST='postgresql://postgres@127.0.0.1:5432/cmc_test' .venv/bin/pytest tests/ -v
```

约定:
- 每个测试函数开始前会 TRUNCATE 业务表,但保留 unit_dict / location 预置值
- session 开始时 DROP+CREATE schema material_mgmt,跑完不清理(方便 psql 调试)
- DB 连不上时,集成测试自动 skip,纯函数测试(test_severity)仍会跑

---

## 十五、合规与法规提示

当前阶段**不主张**满足 GMP / 21 CFR Part 11,仅为部门级管理工具。
若未来扩展到 GMP 范围,需对照核对(**版本以发布时为准**):

- ICH Q9(R1) — Quality Risk Management
- ICH Q10 — Pharmaceutical Quality System
- 《药品生产质量管理规范》及附录(NMPA)
- FDA *Data Integrity and Compliance with Drug CGMP* (2018)
- EU GMP Annex 11 — Computerised Systems
- 21 CFR Part 11 — Electronic Records; Electronic Signatures

---

**项目所有者**: 清城 (CMC Head)
**当前版本**: v2.x(设备模块 + MDM 对接;v1.2 为物料模块历史基线)
**联系方式**: 部门内部使用
