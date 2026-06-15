# CMC LabOps Portal — 存放位置管理增强设计 V1.0

> 状态：设计稿（讨论已对齐，待评审后进入编码）
> 范围：物料库存模块 · 入库登记的"存放位置"重构 + 冰箱/试剂柜结构化管理 + 批量入库
> 关联文档：`CMC_LabOps_Portal_数据模型设计文档_V1_0.md`、`CMC_LabOps_Portal_架构设计文档_V1_0.md`

---

## 1. 背景与问题

当前"存放位置"用一张写死三列的表 `material_mgmt.location(room_no, cabinet_no, layer_no)` 表达，
入库表单是一个搜索下拉框，选择后端拼好的 `name`（如 `2251-A01-L1`），批次直接挂 `location_id`。

存在的问题：

1. **房间/柜/层挤在一个下拉框里**，没有级联——选了房间不会过滤柜，选了柜不会带出它的房间与板层。
2. **无法表达冰箱**，尤其 -80℃ 冰箱的"架 → 层 → 盒 → 孔"多级网格，也没有温区概念。
3. **没有空位/占用概念**：找不到"哪管样品在哪个孔"，也无法快速找空位。
4. **新增一台冰箱/一个试剂柜没有 UI**，只能手写 SQL 或直接调 API。
5. **没有批量入库**，500 只参比品要逐条录入。

---

## 2. 设计目标

| # | 目标 |
|---|------|
| G1 | 房间 / 柜 / 板层拆成独立输入，**级联联动**（选房间→过滤柜；选柜→自动带出房间与其板层） |
| G2 | 冰箱按**温区**（2~8℃ / -20~-40℃ / -80℃）分类管理；-80℃ 支持"架→层→盒区→孔"四级网格 |
| G3 | -80℃ 能**定位到唯一一个孔**，系统知道每个孔是空是满，并能"找下一个空位" |
| G4 | 库管员能**按模板新增**一台冰箱 / 一个试剂柜，系统按设定原则自动展开全部子节点（含全部孔位） |
| G5 | 支持**批量入库**（一次 N 只，自动分配连续空孔或落到散放层） |

### 2.1 已确认的关键决策（讨论结论）

- **记账粒度：分级管理。** 试剂柜、2~8℃/-20℃ 冰箱沿用"批次 + 数量"散放（不动现有库存逻辑）；
  **仅 -80℃ 的孔位**做"一孔一管"的单占用追踪。
- **-80℃ 层级链：区即盒。** `冰箱 → 冻存架(A~P) → 层(1~4/5) → 盒区(A~D) → 孔(1~81/100)`，
  其中"盒区 A~D"直接对应 4 个冻存盒。地址示例：`TT3 B3:A,23` = 冰箱 TT3 / 架 B / 层 3 / 盒区 A / 第 23 孔。
- **分期推进**：期1 位置树 + 试剂柜级联 + 维护页；期2 -80℃ 网格 + 单孔占用 + 空位；期3 批量入库。每期独立可用。

---

## 3. 核心数据模型：可配置的"位置树"

把写死的三列改成一棵**层级树**，一张表 `material_mgmt.storage_node` 表达所有形态——
试剂柜（房间→柜→层）与 -80℃ 冰箱（房间→冰箱→架→层→盒→孔）共用同一套结构，深度可变。

### 3.1 `storage_node`（位置节点 / 树）

```
storage_node
├─ node_id        SERIAL PK
├─ parent_id      INT FK→storage_node(node_id)  -- 根节点(房间)为 NULL
├─ node_type      VARCHAR(20)   -- 见 3.2 枚举
├─ code           VARCHAR(40)   -- 该层级编号: '2251' / 'A01' / 'B' / '3' / 'A' / '23'
├─ label          VARCHAR(80)   -- 展示名(可选, 缺省=code), 冰箱可填别名如 'TT3'
├─ path           VARCHAR(255)  -- 维护的全路径, 如 '2251 / TT3 / B / 3 / A / 23'
├─ depth          SMALLINT      -- 根=0, 便于查询与渲染
├─ sort_order     INT           -- 同级排序(字母/数字混排时稳定)
├─ capacity_kind  VARCHAR(10)   -- 叶子容量类型: 'bulk'(散放, 批次+数量) / 'cell'(单孔单占用); 非叶为 NULL
├─ temp_category  VARCHAR(20)   -- 仅 FRIDGE: 'normal' / '2-8' / '-20' / '-80'
├─ temp_text      VARCHAR(50)   -- 温区可读文本, 如 '-20~-40℃'
├─ is_active      BOOLEAN  DEFAULT TRUE
├─ remark         TEXT
└─ created_at     TIMESTAMP DEFAULT CURRENT_TIMESTAMP   -- 裸上海墙钟(ORM:datetime.now / DB默认:CURRENT_TIMESTAMP)

UNIQUE (parent_id, code)        -- 同一父节点下编号唯一
INDEX  (parent_id), (node_type), (path)
```

> 时区遵循项目约定：所有时间戳为裸上海墙钟，禁止 `utcnow()`。写入有三重保障且都产出上海时间——ORM 用 Python `datetime.now()`（**首选**，宿主机 Asia/Shanghai，不依赖 DB 连接）、列默认 `NOW()/CURRENT_TIMESTAMP`、`backend/database.py` 连接事件 `SET TIME ZONE 'Asia/Shanghai'` 兜底。⚠️ 仅靠 DB 默认值时，部署后未完整重启致连接池残留旧连接可能写成 UTC，故以 ORM `datetime.now()` 为权威写入路径。

### 3.2 `node_type` 枚举与两条典型路径

| node_type | 含义 | 容量 | 出现在 |
|-----------|------|------|--------|
| `ROOM` | 房间 | — | 两者根节点 |
| `CABINET` | 试剂柜 | — | 试剂柜路径 |
| `CABINET_LAYER` | 柜板层（半层/板层） | `bulk` | 试剂柜叶子 |
| `FRIDGE` | 冰箱（带温区） | — | 冰箱路径 |
| `FRIDGE_SHELF` | 普通冰箱隔板 | `bulk` | 2~8/-20 冰箱叶子 |
| `RACK` | 冻存架（A~P） | — | -80 路径 |
| `RACK_LAYER` | 架内层（1~4/5） | — | -80 路径 |
| `BOX` | 盒区 / 冻存盒（A~D） | — | -80 路径 |
| `CELL` | 孔位（1~81/100） | `cell` | -80 叶子（单占用） |

**试剂柜**：`ROOM → CABINET → CABINET_LAYER(bulk)`
**普通冰箱**：`ROOM → FRIDGE(2-8/-20) → FRIDGE_SHELF(bulk)`
**-80℃ 冰箱**：`ROOM → FRIDGE(-80) → RACK → RACK_LAYER → BOX → CELL(cell)`

### 3.3 批次与位置的关系（零侵入：树作为 location 的覆盖层）

为把风险降到最低，期1 **不动** `batch.location_id`、不动任何现有库存/出入库/移库/盘点查询：

- `storage_node` 是覆盖在现有 `location` 之上的**层级树**。**散放叶子**（`CABINET_LAYER` / `FRIDGE_SHELF`）
  通过 `storage_node.location_id` **回链**到一条 `location` 行（1:1）。
- `location` 仍是所有 **bulk 散放位置**的存储记录（试剂柜板层、普通冰箱隔板都落 location；
  冰箱名写 `cabinet_no`、隔板号写 `layer_no`，生成列 `name` 仍可用）。
- 入库表单的三级级联在树上选到叶子 → 解析出叶子的 `location_id` → 提交给**原封不动**的 `POST /api/batches`。
- -80℃ 的 `CELL` 节点 `location_id` 为空，不进 `location`，期2 用 `cell_occupancy` 管理。

> 收益：期1 是纯增量，`batch` / `inventory_txn` / `crud.list_batches` / 移库 / 盘点 / 库存看板全部零改动。

### 3.4 `cell_occupancy`（仅 -80℃ 单孔占用，期2 引入）

"一孔一管"用一张占用表表达：**空孔 = 没有占用行**，占用行最多一行（唯一约束）。

```
cell_occupancy
├─ occupancy_id  SERIAL PK
├─ cell_node_id  INT FK→storage_node(node_id)  UNIQUE   -- 单占用: 一个孔最多一行
├─ batch_id      INT FK→batch(batch_id)                 -- 这一管属于哪个批次/物料
├─ sample_label  VARCHAR(100)                            -- 可选: 管标签/样品号
├─ status        VARCHAR(10)  DEFAULT 'stored'           -- stored / removed(留痕可软删)
├─ stored_at     TIMESTAMP DEFAULT CURRENT_TIMESTAMP     -- 裸上海时间
├─ stored_by     VARCHAR(50)
└─ remark        TEXT

UNIQUE (cell_node_id) WHERE status='stored'   -- 部分唯一索引, 占用唯一
```

**与现有库存逻辑的一致性**（关键）：-80℃ 入库时，每填一个孔写一条 `cell_occupancy`（qty=1），
同时按"填了几孔"写**一条** `inventory_txn(IN, qty=N)`。这样：

> 聚合库存 `SUM(inventory_txn.qty)` ＝ 该批次当前占用孔数 ＝ `cell_occupancy` 行数

取出一管时：`OUT, qty=1` + 把对应 `cell_occupancy.status` 置 `removed`。两个视图永远对账。

---

## 4. 模板化新增设备（G4）

库管员"按原则添加"＝选模板、填参数 → 后端一次性展开整棵子树。模板是参数，不写死。

### 4.1 试剂柜模板

| 参数 | 示例 |
|------|------|
| 房间号 | 2251（已存在则复用，不存在则新建 ROOM） |
| 柜号 | C08 |
| 板层数 | 5 → 生成 `CABINET_LAYER` 1~5 |
| 存储条件 | 常温 / 避光 …（写在 CABINET_LAYER.remark 或柜级属性） |

→ 生成 1 个 CABINET + N 个 CABINET_LAYER。

### 4.2 普通冰箱模板（2~8℃ / -20~-40℃）

| 参数 | 示例 |
|------|------|
| 房间号 | 2251 |
| 冰箱名/编号 | RF-01 |
| 温区 | `2-8` / `-20`（写 temp_category + temp_text） |
| 隔板数 | 4 → 生成 `FRIDGE_SHELF` 1~4（bulk） |

### 4.3 -80℃ 冰箱模板（核心）

| 参数 | 示例 | 展开规则 |
|------|------|----------|
| 房间号 | 2251 | ROOM |
| 冰箱名 | TT3 | FRIDGE(temp=-80) |
| 架编号 | A~P（字母序，可指定起止/数量） | RACK |
| 每架层数 | 4 或 5 | RACK_LAYER 1~N |
| 每层盒区 | A~D（默认 4） | BOX |
| 每盒孔数 | 81 或 100 | CELL 1~M（capacity_kind=cell） |

→ 一台满配 16 架×5 层×4 盒×100 孔 = **32000 个 CELL 节点**。展开在一个事务里批量 INSERT，
并提示规模、二次确认（避免误填生成海量节点）。地址串由 `path` 推导，展示为 `TT3 B3:A,23`。

> 实现注意：批量生成走 `executemany` / `COPY` 风格，避免逐行 ORM；
> 字母序 `code` 的 `sort_order` 按 A=1,B=2… 显式写入，保证排序稳定。

---

## 5. 功能与接口（按期）

### 期1 — 位置树 + 试剂柜级联 + 维护页

**后端**
- `GET  /api/storage/rooms` — 房间列表
- `GET  /api/storage/nodes?parent_id=&node_type=` — 取某节点的下级（级联数据源）
- `GET  /api/storage/nodes/{id}/ancestors` — 取某节点的祖先链（选了柜回填房间用）
- `POST /api/storage/cabinets` — 试剂柜模板新增（§4.1）  *权限: warehouse_admin/admin*
- `POST /api/storage/fridges` — 普通冰箱模板新增（§4.2）  *权限同上*
- `PATCH/DELETE /api/storage/nodes/{id}` — 改名/停用/删除（无占用才允许删）
- `POST /api/batches` 改为接收散放叶子 `node_id`（兼容期同时接受旧 `location_id`）

**前端**
- 入库表单：房间 / 柜 / 板层**三个级联下拉**（Ant Design `Cascader` 或三联动 `Select`）；
  选柜自动回填房间、加载该柜板层。
- 新增"**位置管理**"页（菜单项）：左树右详情，支持模板新增柜/冰箱、改名、停用。

### 期2 — -80℃ 网格 + 单孔占用 + 空位

**后端**
- `POST /api/storage/freezers` — -80 模板展开（§4.3）
- `GET  /api/storage/cells?box_id=` — 盒内 81/100 孔占用矩阵（满/空/谁占用）
- `GET  /api/storage/free-cells?freezer_id=&count=N` — 找下一组 N 个空孔（连续优先）
- `POST /api/storage/occupy` / `POST /api/storage/release` — 占用/释放（写 cell_occupancy + inventory_txn）

**前端**
- -80 入库：选冰箱→架→层→盒，渲染 9×9 / 10×10 **孔位热力图**，点选空孔或"自动找空位 N 个"。
- 地址展示统一 `TT3 B3:A,23`；样品检索可按地址或样品号反查孔。

### 期3 — 批量入库

**后端**
- `POST /api/intake/batch-in` — 一次提交共性信息 + 数量 N：
  - 目标是 `bulk` 叶子 → 建/追加一条批次，`IN qty=N`。
  - 目标是 `cell` 区域 → 自动分配 N 个空孔，写 N 条 `cell_occupancy` + 一条 `IN qty=N`。
  - 全程单事务，失败回滚；返回分配到的地址清单。
- （可选）Excel/CSV 导入：模板列 = 物料编码/批号/有效期/数量/目标设备。

**前端**
- 批量入库向导：① 选物料&共性字段 ② 选目标（散放层 / -80 盒区）③ 填数量或上传文件 ④ 预览分配的孔位地址 ⑤ 确认落库。

---

## 6. 迁移方案（期1 一次性，纯增量）

遵循项目 SQL 迁移约定：写进 `sql/init.sql` 末尾"11. 迁移段"，幂等可重复执行
（建表 `CREATE TABLE IF NOT EXISTS`；回填用 `DO $$ ... $$`，以"`storage_node` 已有数据则跳过"自守卫）。

1. 建 `storage_node`（含索引、同父唯一约束、`location_id` 回链 FK）。
2. **回填树**：遍历现有 `location` 行，按 `room_no`→ROOM、`(room,cabinet)`→CABINET、
   `(room,cabinet,layer)`→CABINET_LAYER(bulk) 建节点；叶子 `CABINET_LAYER.location_id = location.location_id`。
3. **不改 `batch`**：批次继续挂 `location_id`；树叶子 1:1 回链 location，入库经级联解析出 `location_id` 后走原 API。
4. 旧迁移占位（`迁移占位-未指定-L1`）自然成为一个占位 CABINET_LAYER 叶子，UI 提示库管员逐步改正。

> 风险控制：期1 全程 `batch` / `inventory_txn` / 库存查询零改动，可独立回滚（删 `storage_node` 即回旧态）。

---

## 7. 影响面与非目标

**改动文件（预估）**
- `sql/init.sql`（建表 + 迁移段）
- `backend/models.py`（`StorageNode`、`CellOccupancy`；`Batch.node_id`）
- `backend/schemas.py`、`backend/crud.py`、`backend/routers/`（新增 `storage.py`，改 `batch.py`/`inventory.py`/`intake`）
- `frontend-react/src/modules/intake/*`（级联表单、批量向导）、新增"位置管理"与"-80 网格"页、`src/api/*`

**非目标（本设计不含）**
- 不改库存"只记流水、实时聚合"的核心原则。
- 不引入跨库的位置主数据（位置属 LabOps 运营数据，与 MDM 物料/设备主数据边界不变）。
- 期1/期2 不做扫码枪/条码硬件集成（可作为后续增强）。

---

## 8. 评审决策（已确认）

1. 普通冰箱（2~8/-20）止于 `FRIDGE_SHELF` 散放，不做更细分格。
2. -80 孔位 `sample_label`（样品号/管标签）**可空**——占用只需孔位+批次，管标签选填、后续可补。
3. 批量入库第一版只做**表单数量 N + 自动分配**（连续空孔 / 散放层），Excel 导入留作后续增强。
4. 位置树删除/停用策略：有占用/有在库批次的节点**禁止删除，仅允许停用**。

> 以上为讨论评审结论，已锁定；按 期1 → 期2 → 期3 进入编码。

---

*文档版本 V1.0 · 待评审 · 评审通过后按期1→期2→期3 进入编码*
