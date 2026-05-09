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
| 数据库 | PostgreSQL 16,复用现有实例,新建 schema `material_mgmt`(Mac 调试时 PG 在 Docker;Linux 生产时 PG 原生装在宿主机) |
| 后端 | Python 3.11+ / FastAPI / SQLAlchemy 2.0 / Pydantic v2 |
| 前端 | Streamlit(MVP 阶段;后续可替换为 Vue3) |
| 文件导入 | pandas + openpyxl(Excel 读取) |
| 部署 | **不用 Docker 跑应用**。Mac:venv 直接起进程;Linux:venv + systemd unit |
| 认证 | **MVP 阶段不做认证**,操作人姓名作为字段直接录入 |

---

## 三、目录结构

```
cmc-inventory/
├── README.md                        本文档(开发与 Mac 调试指南)
├── DEPLOY.md                        Linux 服务器部署指南(生产)
├── install.sh                       Linux 一键装/起/重启/卸载脚本
├── .env.example                    环境变量样例
├── .gitignore
├── sql/
│   └── init.sql                    建表 + 字典初始化
├── systemd/
│   ├── cmc-backend.service         FastAPI 后端 systemd unit(Linux)
│   └── cmc-frontend.service        Streamlit 前端 systemd unit(Linux)
├── backend/
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
│       ├── location.py             储存位置 API
│       └── import_data.py          Excel 导入 API
├── frontend/
│   ├── requirements.txt
│   ├── app.py                      Streamlit 主入口(导航)
│   ├── utils.py                    API 调用封装
│   └── pages/
│       ├── 1_物料导入.py
│       ├── 2_物料管理.py            查看/停用/启用、安全库存维护
│       ├── 3_入库登记.py
│       ├── 4_出库登记.py
│       ├── 5_库存查询.py
│       ├── 6_库存预警.py
│       └── 7_盘点调整.py
└── template/
    ├── generate_template.py        生成 Excel 模板的脚本
    └── 物料导入模板.xlsx            生成产物(.gitignore 排除,本地跑脚本生成)
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

### 6.7 盘点调整页
- 选物料 → 选批次(可含过期)→ 显示账面库存
- 两种调整方式:
  - 按**实际盘点数**:输入物理盘点数,前端自动算 delta
  - 按**调整量**:直接输入正负调整量
- 经办人 + 备注(建议填盘点单号 / 原因)
- 后端校验:调整后批次库存不得 < 0,否则拒绝
- 与出入库共用 `inventory_txn` 表,`txn_type='ADJUST'` 区分

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

## 八、部署形态(Mac 调试 / Linux 生产)

应用本身**不用 Docker 跑**(直接 venv + 进程),只是 mac 本机的 PG 在 Docker 里。

|  | Mac(开发调试) | Linux(生产) |
|---|---|---|
| PostgreSQL | Docker 容器,host 端口暴露(默认 5432) | 宿主机原生(`apt install postgresql`) |
| 后端 / 前端 | venv + 直接 `uvicorn` / `streamlit` 起进程 | venv + `systemd` unit(由 `install.sh` 装) |
| 数据库主机 | `127.0.0.1`(到 docker 暴露端口) | `127.0.0.1`(到宿主机 PG) |
| 是否跑 `install.sh` | **不要跑**(`systemctl`/`sudo` 在 mac 没意义) | **要跑**,见 `DEPLOY.md` |

后端只通过 `DATABASE_URL` 连库,所以两套环境的代码完全一致,差别只在 `.env` 里的连接串和起进程的方式。

---

## 九、环境变量(`.env.example`)

```
BACKEND_PORT=8000
FRONTEND_PORT=8501
DATABASE_URL=postgresql://cmc_user:<your-password>@127.0.0.1:5432/cmc_data_platform
API_BASE_URL=http://localhost:8000
```

> systemd 用 `EnvironmentFile=` 直接加载本文件,**KEY=VALUE 之间不能有空格,不要加引号**。
> Mac 调试时同样可以读这份 `.env`,但没有强制格式约束。
> 部署前务必把 `<your-password>` 换成你在 §10 第 1 步建库时设的真实密码;`.env` 已被 `.gitignore` 排除,不会进库。

---

## 十、启动步骤

### 10.A Mac 本机调试(PG 在 Docker,后端/前端在 venv)

> 当前 mac 环境的 PG 容器:**`postgres16`**(host 端口 5432,`postgres` 超管无需密码)。
> 数据库 `cmc_data_platform` 已存在。如果你的环境不一样,把下面的容器名 / 端口 / 库名同步替换。

```bash
# 0)(诊断用)确认 docker pg 在跑
docker ps --filter "name=postgres16" --format "table {{.Names}}\t{{.Ports}}"

# 1) 在已有 PG 里新建用户 / schema(只做一次,库已存在所以不用 CREATE DATABASE)
docker exec -i postgres16 psql -U postgres -d cmc_data_platform <<'EOF'
CREATE USER cmc_user WITH PASSWORD '<your-password>';
CREATE SCHEMA material_mgmt AUTHORIZATION cmc_user;
GRANT CONNECT ON DATABASE cmc_data_platform TO cmc_user;
EOF

# 2) 用 cmc_user 跑建表脚本(不需要 mac 本机装 psql:仍走 docker exec)
docker exec -i -e PGPASSWORD='<your-password>' postgres16 \
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

# 5) 起前端(终端 B)
cd frontend
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
set -a; source ../.env; set +a
.venv/bin/streamlit run app.py --server.port "$FRONTEND_PORT"

# 6)(可选)生成 Excel 导入模板
cd template && python3 generate_template.py

# 7) 访问(以下端口若 .env 中改过,以 .env 为准)
#    前端: http://localhost:$FRONTEND_PORT     # 默认 8501
#    后端 API 文档: http://localhost:$BACKEND_PORT/docs   # 默认 8000
```

**Mac 常见问题**:

- *后端报 `password authentication failed`*:`.env` 里的密码与第 1 步 `CREATE USER` 时设的不一致,改一致后重启 uvicorn。
- *后端报 `permission denied for schema material_mgmt`*:第 2 步建表是用 postgres 跑的导致表归 postgres 所有,改用 cmc_user 跑(命令同上,带 `-U cmc_user`)。
- *前端报 `后端不可达`*:确认 uvicorn 在跑(`curl http://127.0.0.1:8000/health`),再确认 `.env` 中 `API_BASE_URL=http://localhost:8000`。
- *端口被占*:`lsof -iTCP -sTCP:LISTEN -P | grep -E '8000|8501'` 查谁占着,改 `.env` 中 `BACKEND_PORT` / `FRONTEND_PORT` 即可,前端读后端的 `API_BASE_URL` 端口要同步改。

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
git clone git@github.com:qingcheng81/cmc-inventory.git /opt/cmc-inventory
cd /opt/cmc-inventory && cp .env.example .env  # 改密码 / 端口

# 3) 一键装 venv + systemd unit + enable --now
./install.sh
```

#### 后续日常流程

按改动类型选合适的命令:

```bash
cd /opt/cmc-inventory

# A. 改了 Python 代码 / 前端页面 → 拉代码并重启进程,不动 systemd
git pull
./install.sh restart

# B. 改了 requirements.txt → 重装依赖再重启
git pull
./install.sh deps && ./install.sh restart

# C. 改了 systemd unit / install.sh / .env.example 默认值 → 重装 + 重启
git pull
./install.sh install            # 会重装 unit、daemon-reload、enable --now

# D. 只改了运行时 .env(不动代码) → 仅重启,让 systemd 重新加载 EnvironmentFile
./install.sh restart
```

> 注意:`./install.sh install` 对**已 active** 的服务不会强制重启进程(只 enable --now),
> 若想确保进程被替换,跟一句 `./install.sh restart` 或 `sudo systemctl restart cmc-backend cmc-frontend`。

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
| 前端 Streamlit | `http://<server-ip>:<FRONTEND_PORT>`(默认 8501) | 任何能到服务器内网的人,直接浏览器打开 |
| 后端 FastAPI | `http://127.0.0.1:<BACKEND_PORT>` | **只允许服务器本机**(MVP 无鉴权,故不直接对外) |
| 后端 Swagger `/docs` | 走 SSH 隧道,见下 | 临时调试用 |

**后端为什么只绑 127.0.0.1?** 因为 MVP 阶段没做认证,直接对外等于把数据库读写权限暴露到内网。
Streamlit 前端跑在**同一台机器**上,走 `localhost:<BACKEND_PORT>` 不受限制;
内网用户访问前端 8501 即可,所有 API 调用都在服务器内完成。

#### 在自己笔记本上看 Swagger `/docs`(SSH 隧道)

前端首页那行"后端 API 仅限服务器本机访问"提示就是这个意思 — 链接不要点,而是按下面的方式开隧道:

```bash
# 在自己笔记本上跑;开着不要关,期间浏览器才能访问 http://localhost:8200/docs
# 把端口和 ssh 配置改成你的实际值
ssh -L 8200:127.0.0.1:8200 -p <ssh-port> prometheus@<server-ip>

# 然后浏览器打开
#   http://localhost:8200/docs
```

> 笔记本本地端口可以选别的(避免与本机已用端口冲突),例如 `-L 19000:127.0.0.1:8200`,然后浏览器开 `http://localhost:19000/docs`。

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

## 十二、给 Claude Code 的实施指令(回顾,主体已完成)

按以下顺序生成代码:

1. **`sql/init.sql`** — 完整建表 + 字典预置数据 + 索引 ✅
2. **`backend/`** 全部文件 — FastAPI 应用,含所有路由 ✅
3. **`frontend/`** 全部文件 — Streamlit 多页应用 ✅
4. **`.env.example`** + **`install.sh`** + **`systemd/*.service`** + **`DEPLOY.md`** — Linux 部署套件 ✅
5. **`template/generate_template.py`** — 用 openpyxl 生成 Excel 模板 ✅
6. 每个文件顶部加用途说明注释,关键逻辑加中文注释 ✅

### 实施要求

- ✅ 所有代码可在 macOS(PG in docker)+ Linux(PG 原生)双环境运行
- ✅ Pydantic v2 语法,SQLAlchemy 2.0 风格
- ✅ FastAPI 启用 CORS,允许前端访问
- ✅ 所有金额/数量字段用 `Decimal`,避免浮点误差
- ✅ Excel 导入用 `pd.read_excel(dtype=str)` 严格保留前导 0
- ✅ 时间字段统一走 PG 服务器时间(`now()` / `CURRENT_TIMESTAMP`),前端按字符串原样展示
- ✅ 错误处理: 友好的中文错误信息返回前端
- ✅ Streamlit 页面用 `st.session_state` 缓存物料字典,提升下拉响应速度
- ✅ 库存数量永远从 `inventory_txn` 实时聚合,绝不缓存到 `batch` 表
- ✅ 不引入 Docker 跑应用(应用直接 venv;只有 mac 调试时 PG 在 docker)

### 不要做的

- ❌ 不要加用户登录/JWT(MVP 阶段无认证)
- ❌ 不要加申购/审批/CoA/质量状态(范围外)
- ❌ 不要使用复杂前端框架(Vue/React),坚持 Streamlit
- ❌ 不要过度抽象(无需 DDD、CQRS 等)
- ❌ 不要省略中文注释

---

## 十三、迭代路线图

### 13.A v1.1 实施计划(已确认,即将开发)

MVP 上线后实际使用中暴露的问题与高频功能诉求,合并为 v1.1。按依赖与价值分**三阶段**滚动交付,每阶段独立 push、独立可发版,服务器按 §10.B 流程拉新代码即可。

#### 阶段 A — Hot Fix(1-2 天)

| # | 问题 | 改动范围 |
|---|---|---|
| A.1 | 入库登记搜索:含中文/全角字符时部分关键字搜不到 | `frontend/utils.py` 加 NFKC 归一化函数 + `material_label` / 搜索过滤函数都用归一化后的值比对 |
| A.2 | 库存查询默认显示零库存物料,信噪比低 | `backend/crud.py.stock_by_material` 加 `only_positive` 参数(默认 True);`backend/routers/stock.py` 暴露同名 query;`frontend/pages/5_库存查询.py` 加"包含零库存"复选框,默认关 |

#### 阶段 B — 物料维护补全(2-3 天)

| # | 改动 | 范围 |
|---|---|---|
| B.1 | 后端新增 `POST /api/materials`(单条创建) | `backend/routers/material.py`;`backend/crud.py` 加 `create_material`;`schemas.py` 复用 `MaterialCreate` |
| B.2 | 「物料管理」页加"➕ 新增物料"按钮 + 完整表单 | `frontend/pages/2_物料管理.py`;含字段:代码、分类、名称、级别、生产商、规格/型号、货号、单位、包装规格、备注、安全库存 |
| B.3 | 「物料管理」页加"✏️ 编辑物料"完整表单 | 同上文件;后端 PATCH 已支持,只补前端 UI;允许改除 `material_code`/`is_active` 外所有字段 |

> 「物料导入」页保持不变,继续负责 Excel 批量。两条路径(单条 / 批量)语义清晰。

#### 阶段 C — 用户系统 + 审计追踪(约 1 周)

技术选型:**streamlit-authenticator** 库 + 后端简单 token 验证。

| # | 改动 | 范围 |
|---|---|---|
| C.1 | 数据模型 | 新增 `app_user`(id / username / password_hash / role / is_active / created_at)、`audit_log`(id / user_id / action / entity_type / entity_id / before_json / after_json / source_ip / created_at);`sql/init.sql` 增量补丁 + 一份 `sql/migrate_v1.1.sql` |
| C.2 | 后端鉴权 | `POST /api/auth/login` 返 token;FastAPI 依赖 `current_user` 注入路由;写操作 router 在事务内调 `audit_log_helper(...)` 写日志 |
| C.3 | 角色控制 | `admin` / `user` 两档:user 仅 GET,admin 才能 POST/PATCH;后端中间件级控制(403),前端按 role 隐藏按钮 |
| C.4 | 前端登录 | streamlit-authenticator 接 cookie session;首次启动用预置 admin(`.env` 注入初始密码,首次登录强制改);把所有页里"经办人 *"输入框改为**自动取登录用户名**(只读展示,不再手填) |
| C.5 | 用户管理页 | 新增「用户管理」页(`8_用户管理.py`),仅 admin 可见:列表、新增、改密、停用 |
| C.6 | 审计追踪查看 | 「用户管理」页中加"操作日志" tab,仅 admin 可见,可按用户/实体/时间段筛选 |

#### 与原"远期路线图"的关系

原 v1.4(用户登录 + RBAC)、原 v2.1 的"审计追踪"部分,**提前到 v1.1**,因为 MVP 实际跑起来后这两项是最影响日常使用的。`v1.4` 中"对接公司 AD"延后到 SSO 阶段。

### 13.B 远期路线图(MVP 之后,仅作参考)

| 阶段 | 计划功能 |
|------|---------|
| v1.2 | 申购单(PR) + 简单审批流 |
| v1.3 | CoA 文件上传 + 关联批次 |
| v1.4 | 供应商主数据 + 质量状态(待检/合格/不合格) |
| v1.5 | 对接公司 AD / SSO(替换 v1.1 的本地账号体系) |
| v2.0 | 与 `rd_budget` 库联动 + 预算占用校验 |
| v2.1 | GMP 合规模式增强: 电子签名(21 CFR Part 11)、变更控制 |
| v3.0 | 替换前端为 Vue3,支持移动端扫码出入库 |

---

## 十四、测试

仅核心账实计算路径有 pytest 用例(库存聚合、过期排除、严重度判断、出库超量、盘点为负拒绝),共 17 条。

```bash
cd backend
.venv/bin/pip install -r requirements-dev.txt        # 装 pytest + httpx

# 用一个独立的 PG database 跑测试(切勿指生产库 cmc_data_platform!)
# Mac 默认连 docker postgres16 中的 postgres 库:
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