# CMC 物料管理系统 MVP (`cmc-inventory`)

> CMC 部门内部使用的轻量化物料管理系统,聚焦核心闭环:**物料导入 → 入库 → 出库 → 库存统计 → 预警**。
> MVP 阶段不涉及 GMP 合规、申购审批、CoA 管理等扩展模块,这些将在后续迭代中逐步加入。

---

## 一、项目目标

为 CMC 部门提供一个**部门级**的物料管理工具,解决:

1. 物料主数据从公司物料代码表一次性导入,后续直接下拉检索使用,**减少人工录入**
2. 重要试剂、关键耗材的**批次级**入库 / 出库登记
3. 实时库存统计(按物料、按批次、按位置)
4. **低库存预警**(对比安全库存)+ **效期预警**(30/90 天分级)
5. 物料**软删除**(停用),保证历史数据可追溯

**明确不做(MVP 之外)**:申购审批流、CoA 文件管理、质量状态管理、供应商管理、GMP 合规审计追踪、权限分级、报表看板、ERP/LIMS 对接。

---

## 二、技术栈

| 层 | 技术 |
|----|------|
| 数据库 | PostgreSQL 16 (Docker,复用现有实例,新建 schema `material_mgmt`) |
| 后端 | Python 3.11+ / FastAPI / SQLAlchemy 2.0 / Pydantic v2 |
| 前端 | Streamlit(MVP 阶段;后续可替换为 Vue3) |
| 文件导入 | pandas + openpyxl(Excel 读取) |
| 部署 | Docker Compose 一键启动 |
| 认证 | **MVP 阶段不做认证**,操作人姓名作为字段直接录入 |

---

## 三、目录结构

```
cmc-inventory/
├── docker-compose.yml              一键启动 PG + 后端 + 前端
├── README.md                        本文档
├── .env.example                    环境变量样例
├── sql/
│   └── init.sql                    建表 + 字典初始化
├── backend/
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── main.py                     FastAPI 入口
│   ├── database.py                 PG 连接配置
│   ├── models.py                   SQLAlchemy ORM
│   ├── schemas.py                  Pydantic 模型
│   ├── crud.py                     通用 CRUD
│   └── routers/
│       ├── __init__.py
│       ├── material.py             物料 API(查询、停用/启用、维护安全库存)
│       ├── batch.py                批次 API
│       ├── inventory.py            出入库 API
│       ├── stock.py                库存查询 + 预警 API
│       └── import_data.py          Excel 导入 API
├── frontend/
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── app.py                      Streamlit 主入口(导航)
│   ├── utils.py                    API 调用封装
│   └── pages/
│       ├── 1_物料导入.py
│       ├── 2_物料管理.py            查看/停用/启用、安全库存维护
│       ├── 3_入库登记.py
│       ├── 4_出库登记.py
│       ├── 5_库存查询.py
│       └── 6_库存预警.py
└── template/
    └── 物料导入模板.xlsx            带字段说明和示例
```

---

## 四、数据模型(7 张表)

### 4.1 `material` — 物料主数据

| 字段 | 类型 | 说明 |
|------|------|------|
| `material_code` | VARCHAR(20) PK | 物料代码,**保留前导 0**(纯数字以字符串存储) |
| `category` | VARCHAR(50) | 分类(如"一般耗材"),来自导入文件 |
| `name_cn` | VARCHAR(200) NOT NULL | 物料名称(中文) |
| `grade` | VARCHAR(50) | 级别(N/A 转 NULL) |
| `manufacturer` | VARCHAR(100) | 生产商 |
| `spec_model` | VARCHAR(200) | 规格/型号 |
| `catalog_no` | VARCHAR(100) | 货号 |
| `unit` | VARCHAR(20) NOT NULL | 单位(支/瓶/g/mL/盒/包等) |
| `package_spec` | VARCHAR(100) | 包装规格 |
| `remark` | TEXT | 备注 |
| `safety_stock` | NUMERIC(12,2) DEFAULT 0 | 安全库存(导入后单独维护) |
| `is_active` | BOOLEAN DEFAULT TRUE | 启用标志(软删除) |
| `deactivated_at` | TIMESTAMP | 停用时间 |
| `deactivated_by` | VARCHAR(50) | 停用操作人 |
| `deactivate_reason` | VARCHAR(200) | 停用原因 |
| `import_batch_id` | INT FK | 导入批次,便于回溯 |
| `created_at` / `updated_at` | TIMESTAMP | 自动维护 |

### 4.2 `batch` — 批次

| 字段 | 类型 | 说明 |
|------|------|------|
| `batch_id` | SERIAL PK | |
| `material_code` | VARCHAR(20) FK | |
| `batch_no` | VARCHAR(100) NOT NULL | 供应商批号 |
| `expiry_date` | DATE | 效期(可空,部分耗材无效期) |
| `location_id` | INT FK | 储存位置 |
| `received_date` | DATE NOT NULL | 到货日期 |
| `initial_qty` | NUMERIC(12,2) NOT NULL | 入库数量 |
| `remark` | TEXT | |
| `created_at` | TIMESTAMP | |

**唯一约束**: `(material_code, batch_no)` 联合唯一(同一物料同一批号不重复)

### 4.3 `inventory_txn` — 出入库流水(库存计算的唯一来源)

| 字段 | 类型 | 说明 |
|------|------|------|
| `txn_id` | SERIAL PK | |
| `batch_id` | INT FK NOT NULL | |
| `txn_type` | VARCHAR(10) NOT NULL | `IN` / `OUT` / `ADJUST` |
| `qty` | NUMERIC(12,2) NOT NULL | **入库为正,出库为负,调整有正有负** |
| `txn_date` | DATE NOT NULL | 发生日期 |
| `operator` | VARCHAR(50) NOT NULL | 经办人姓名 |
| `purpose` | VARCHAR(200) | 用途/项目编号(出库时填) |
| `remark` | TEXT | |
| `created_at` | TIMESTAMP | |

**关键设计原则**: 库存数量**不存表**,实时由 `inventory_txn` 聚合计算,杜绝账实不符。

### 4.4 `location` — 储存位置

| 字段 | 类型 | 说明 |
|------|------|------|
| `location_id` | SERIAL PK | |
| `name` | VARCHAR(100) NOT NULL UNIQUE | 如"4℃冰箱A-2层" |
| `storage_condition` | VARCHAR(50) | 常温 / 4℃ / -20℃ / -80℃ / 避光 |
| `remark` | TEXT | |

### 4.5 `unit_dict` — 单位字典

| 字段 | 类型 | 说明 |
|------|------|------|
| `unit` | VARCHAR(20) PK | 如 支、瓶、g、mL |
| `description` | VARCHAR(100) | |

**预置值**(从导入样本提取): 张、卷、个、盒、包、根、袋、瓶、把、kg、支、g、mg、mL、L

### 4.6 `category_dict` — 分类字典

| 字段 | 类型 | 说明 |
|------|------|------|
| `category` | VARCHAR(50) PK | |

**初始为空**,导入时自动从文件中提取唯一值入库。

### 4.7 `import_log` — 导入日志

| 字段 | 类型 | 说明 |
|------|------|------|
| `import_id` | SERIAL PK | |
| `file_name` | VARCHAR(200) | |
| `imported_at` | TIMESTAMP | |
| `operator` | VARCHAR(50) | |
| `total_rows` | INT | |
| `inserted_rows` | INT | |
| `updated_rows` | INT | |
| `failed_rows` | INT | |
| `error_detail` | JSONB | 失败行详情 |

---

## 五、核心业务逻辑

### 5.1 物料编码处理(关键)

- 数据库存储为 `VARCHAR(20)`,**严格保留前导 0**
- Excel 读取时强制 dtype:
  ```python
  pd.read_excel(file, dtype={'代码': str})
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
   - material_code 唯一且非空
   - name_cn、unit 非空
   - unit 在 unit_dict 中(否则提示先维护字典或自动加入)
   - 检测前导 0
   ↓
④干跑结果:"将插入 X 条 / 更新 Y 条 / 错误 Z 条"
   错误行可下载 Excel 查看原因
   ↓
⑤UPSERT 写入(material_code 冲突则更新)
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
SELECT m.material_code, m.name_cn, SUM(t.qty) AS total_qty
FROM material m
JOIN batch b ON b.material_code = m.material_code
JOIN inventory_txn t ON t.batch_id = b.batch_id
GROUP BY m.material_code, m.name_cn;
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

## 六、前端页面设计(Streamlit)

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
- 行内操作: 编辑安全库存、停用/启用
- 停用时弹窗输入原因

### 6.3 入库登记页
- 物料选择(三层级联: 分类 → 模糊搜索 → 选中)
- 批号、效期、储存位置、到货日期、入库数量、经办人、备注
- 同一物料同一批号已存在 → 提示是否追加入库(创建新 txn 而非新 batch)
- 提交后显示当前批次库存

### 6.4 出库登记页
- 物料选择(同上,但只显示**有库存**的物料)
- 批次选择(显示该物料的可用批次,默认按效期升序 - FIFO 建议)
- 出库数量(校验不超过批次现有库存)
- 经办人、用途/项目编号、备注
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

---

## 七、API 设计(FastAPI)

### 7.1 物料相关 `/api/materials`

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/materials` | 查询(支持 `category`、`keyword`、`include_inactive`、`is_active` 过滤) |
| GET | `/api/materials/{code}` | 详情 |
| PATCH | `/api/materials/{code}` | 更新(主要用于 safety_stock) |
| POST | `/api/materials/{code}/deactivate` | 停用(body: operator, reason) |
| POST | `/api/materials/{code}/activate` | 启用 |
| GET | `/api/categories` | 分类字典 |
| GET | `/api/units` | 单位字典 |

### 7.2 批次 `/api/batches`

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/batches` | 查询(支持 `material_code` 过滤) |
| POST | `/api/batches` | 创建批次(同时创建首次入库 txn) |
| GET | `/api/batches/{batch_id}` | 详情 |

### 7.3 出入库 `/api/inventory`

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/inventory/in` | 入库(对已有批次追加) |
| POST | `/api/inventory/out` | 出库 |
| POST | `/api/inventory/adjust` | 调整(盘点用,可正可负) |
| GET | `/api/inventory/txns` | 流水查询 |

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

---

## 八、Docker Compose 服务

```yaml
services:
  postgres:
    image: postgres:16
    environment:
      POSTGRES_USER: ${PG_USER}
      POSTGRES_PASSWORD: ${PG_PASSWORD}
      POSTGRES_DB: ${PG_DB}
    ports: ["5432:5432"]
    volumes:
      - pgdata:/var/lib/postgresql/data
      - ./sql/init.sql:/docker-entrypoint-initdb.d/init.sql

  backend:
    build: ./backend
    environment:
      DATABASE_URL: postgresql://${PG_USER}:${PG_PASSWORD}@postgres:5432/${PG_DB}
    ports: ["8000:8000"]
    depends_on: [postgres]

  frontend:
    build: ./frontend
    environment:
      API_BASE_URL: http://backend:8000
    ports: ["8501:8501"]
    depends_on: [backend]

volumes:
  pgdata:
```

**说明**: 若用户希望复用其本机已有的 PG16 实例(而非本 compose 启动新实例),README 应提供注释方案。

---

## 九、环境变量(`.env.example`)

```
PG_USER=cmc_user
PG_PASSWORD=change_me
PG_DB=cmc_inventory
DATABASE_URL=postgresql://cmc_user:change_me@postgres:5432/cmc_inventory
API_BASE_URL=http://backend:8000
```

---

## 十、启动步骤

```bash
# 1. 克隆/进入项目目录
cd cmc-inventory

# 2. 复制环境变量
cp .env.example .env
# 编辑 .env 修改密码

# 3. 启动所有服务
docker compose up -d --build

# 4. 检查服务
docker compose ps
docker compose logs -f backend

# 5. 访问
# 前端: http://localhost:8501
# 后端 API 文档: http://localhost:8000/docs
# PostgreSQL: localhost:5432

# 6. 首次使用
# - 打开"物料导入"页,上传贵司物料代码 Excel 完成主数据导入
# - 打开"物料管理"页,维护各物料的安全库存
# - 在"入库登记"页录入实际批次
# - 日常使用"出库登记"扣减,定期查看"库存预警"
```

---

## 十一、Excel 导入模板

模板放在 `template/物料导入模板.xlsx`,字段与贵司实际表对齐:

| 序号 | 分类 | 代码 | 物料名称 | 级别 | 生产商 | 规格/型号 | 货号 | 单位 | 包装规格 | 备注 |
|------|------|------|---------|------|--------|----------|------|------|---------|------|
| 1 | 一般耗材 | 42001 | PVC封膜(透明) | N/A | N/A | 50*33mm | N/A | 张 | | N/A |

**说明**:
- `序号` 列读取时**忽略**(非业务字段)
- `N/A` 与空白统一转 NULL
- `代码` 列必须以**文本格式**存储,避免前导 0 丢失
- `单位` 必须在 `unit_dict` 中,否则导入失败或自动追加(行为可配置)

---

## 十二、给 Claude Code 的实施指令

请按以下顺序生成代码:

1. **`sql/init.sql`** — 完整建表 + 字典预置数据 + 索引
2. **`backend/`** 全部文件 — FastAPI 应用,含所有路由
3. **`frontend/`** 全部文件 — Streamlit 多页应用
4. **`docker-compose.yml`** + **`.env.example`** + 两个 `Dockerfile`
5. **`template/物料导入模板.xlsx`** 生成脚本(用 openpyxl)
6. 每个文件顶部加用途说明注释,关键逻辑加中文注释

### 实施要求

- ✅ 所有代码可在 macOS / Docker 环境直接运行
- ✅ Pydantic v2 语法,SQLAlchemy 2.0 风格
- ✅ FastAPI 启用 CORS,允许前端访问
- ✅ 所有金额/数量字段用 `Decimal`,避免浮点误差
- ✅ Excel 导入用 `pd.read_excel(dtype={'代码': str})` 严格保留前导 0
- ✅ 时间字段统一 UTC,前端展示按本地时区
- ✅ 错误处理: 友好的中文错误信息返回前端
- ✅ Streamlit 页面用 `st.session_state` 缓存物料字典,提升下拉响应速度
- ✅ 库存数量永远从 `inventory_txn` 实时聚合,绝不缓存到 `batch` 表
- ✅ README 中的启动步骤要在生成代码后**实测可用**

### 不要做的

- ❌ 不要加用户登录/JWT(MVP 阶段无认证)
- ❌ 不要加申购/审批/CoA/质量状态(范围外)
- ❌ 不要使用复杂前端框架(Vue/React),坚持 Streamlit
- ❌ 不要过度抽象(无需 DDD、CQRS 等)
- ❌ 不要省略中文注释

---

## 十三、迭代路线图(MVP 之后,仅作参考)

| 阶段 | 计划功能 |
|------|---------|
| v1.1 | 申购单(PR) + 简单审批流 |
| v1.2 | CoA 文件上传 + 关联批次 |
| v1.3 | 供应商主数据 + 质量状态(待检/合格/不合格) |
| v1.4 | 用户登录(对接公司 AD)+ RBAC |
| v2.0 | 与 `rd_budget` 库联动 + 预算占用校验 |
| v2.1 | GMP 合规模式: 审计追踪、电子签名(21 CFR Part 11) |
| v3.0 | 替换前端为 Vue3,支持移动端扫码出入库 |

---

## 十四、合规与法规提示

MVP 阶段**不主张**满足 GMP / 21 CFR Part 11,仅为部门级管理工具。
若未来扩展到 GMP 范围,需对照核对(**版本以发布时为准**):

- ICH Q9(R1) — Quality Risk Management
- ICH Q10 — Pharmaceutical Quality System
- 《药品生产质量管理规范》及附录(NMPA)
- FDA *Data Integrity and Compliance with Drug CGMP* (2018)
- EU GMP Annex 11 — Computerised Systems
- 21 CFR Part 11 — Electronic Records; Electronic Signatures

---

**项目所有者**: 清城 (CMC Head)
**MVP 目标周期**: 2-4 周内可上线试运行
**联系方式**: 部门内部使用