# CMC LabOps Portal — 入库人姓名（库存分布显示）设计 V1.0

| 项 | 内容 |
|---|---|
| 版本 | V1.0（草案，待审阅） |
| 日期 | 2026-06-16 |
| 状态 | **已实施**（已上线，现状以数据模型 §3.5 / 需求 FR-MAT-053 / UI §5.4 为准；本稿留作设计档案） |
| 范围 | MDM 改一行（令牌带姓名）；LabOps 加字段+取值+展示+历史回填 |

---

## 1. 背景与需求

在「库存查询 → 物料详情 → 库存分布（各批次/位置）」表格中，新增一列「**入库人**」，显示**当初做入库登记那个人的姓名**。

采用**快照模式**（与物料查询一致）：入库时把姓名固化到 LabOps 本地，今后查询直接读本地、不回 MDM，既快又稳；且快照记录的是"入库**当时**该工号对应的姓名"，符合受监管场景的审计留痕要求。

---

## 2. 现状分析

| 事实 | 说明 |
|---|---|
| 工号登录 | MDM 已支持（`cde3836`），登录 `username` 即工号 |
| 入库人记录 | LabOps `inventory_txn.operator` / 批次入库 operator = `current.username`（现为工号；早期批次为旧账号名如 `shijie.tan`） |
| 姓名数据 | 在 MDM `auth.user.full_name`（必填） |
| 令牌内容 | MDM access token 的 `extra_claims` 仅 `{username, roles}`，**不含姓名** |
| MDM 用户查询接口 | `GET /api/v1/admin/users/{username}` 等为 **admin 权限**，LabOps 普通身份不便调用 |

**结论**：姓名数据齐备，但没有从 MDM 通到 LabOps 的通道。

---

## 3. 方案与原则

**核心**：让 MDM 登录令牌带上姓名；LabOps 入库时**从令牌直接取当前登录人姓名**，快照写入本地批次表；库存分布读本地字段显示。

**为何"从令牌取"而非"入库时查 MDM"**：入库人就是当前登录操作的人本人，其姓名登录那一刻已在令牌里——直接取即可，**省掉每次入库一次 MDM 查询，也绕开 MDM 用户接口的 admin 权限限制**。结果一致（姓名照样快照入库）。

**原则**：
- 快照固化（审计留痕，姓名不随日后改名变动）。
- 本地读取，查询无延迟。
- MDM 改动最小化（仅令牌加一字段）。
- 数据库结构变更走 `cmc-schema-migrations`。

---

## 4. 详细设计

### 4.1 MDM 改动（由你执行，仅一处概念改动 / 两行）

文件 `app/domains/auth/services.py`，**两处** `extra_claims`（登录第 238 行、刷新第 382 行）都加上 `full_name`：

```python
# 改前
extra_claims={"username": user.username, "roles": roles},
# 改后
extra_claims={"username": user.username, "full_name": user.full_name, "roles": roles},
```

> 两处都要改：登录签发与续期（refresh）签发的 access token 都应带姓名，否则续期后姓名丢失。
> `user.full_name` 为必填字段，安全。改完按 MDM 自身流程部署。

### 4.2 LabOps 后端

**(a) 令牌解析** `backend/auth.py`
- `CurrentUser` 增加字段 `full_name: str = ""`。
- `get_current_user` 中 `full_name=payload.get("full_name", "")`。
- `verify_reviewer`（复核签名）解析处同样补 `full_name`（保持一致，备用）。

**(b) 批次表加字段** `backend/models.py`
- `Batch` 增加：`intake_operator_name: Mapped[Optional[str]] = mapped_column(String(128))`
  - 语义：入库登记操作人的姓名快照（对应 operator 工号）。命名用 `intake_operator_name` 比裸 `full_name` 更清晰。
  - 与既有 `operator`（工号，在 inventory_txn）互补：一存工号、一存姓名快照。

**(c) 数据库迁移**（`~/code/cmc-schema-migrations`，走 Alembic）
- 新 revision：`ALTER TABLE material_mgmt.batch ADD COLUMN intake_operator_name VARCHAR(128)`（可空）。
- downgrade：`DROP COLUMN intake_operator_name`。
- 同步更新 `backend/sql/init.sql`（batch 建表块 + 末尾迁移段 `ADD COLUMN IF NOT EXISTS`），保持测试/dev 一致。

**(d) 入库写入姓名快照**
- 批次创建/入库各入口，把 `current.full_name` 写入 `intake_operator_name`：
  - `backend/routers/batch.py`（`create_batch` → `create_batch_with_initial_in`）
  - `backend/routers/intake.py`
  - `backend/routers/storage.py`（-80 孔位入库 `bulk_intake_cells` 等）
- `crud.py` 相应 create 函数签名增加 `intake_operator_name` 参数并落库。

**(e) 库存分布查询带出** `backend/crud.py` `stock_by_batch`
- select 增加 `Batch.intake_operator_name`，输出 dict 增加该键。
- `backend/schemas.py` `StockByBatch` 增加 `intake_operator_name: Optional[str] = None`。

### 4.3 LabOps 前端
- `frontend-react/src/api/inventory.ts`：`StockByBatch`（及 `Batch`）类型增加 `intake_operator_name: string | null`。
- `frontend-react/src/modules/stock/components/MaterialDetailModal.tsx`：库存分布表格增加一列「**入库人**」，`dataIndex: "intake_operator_name"`，空值显示 `—`。

### 4.4 历史批次回填（一次性）

- 现有批次 `intake_operator_name` 为空；其 `operator` 为工号或**早期旧账号名**（如 `shijie.tan`）。
- 因数据量小（详情页可见就几个工号/账号），建议**一次性人工核对映射后回填**：
  - 已知映射：`admin`→admin、`230710`→任雨乐、`210622`→谭世杰、旧账号 `shijie.tan`→谭世杰…（需你确认完整对照表）。
  - 用一条 SQL 或小脚本按 `operator` 更新 `intake_operator_name`。
- 未回填的历史行：列中先显示工号（或 `—`），不影响今后入库正常显示姓名。

---

## 5. 影响范围 / 迁移 / 回滚

- **影响**：MDM 令牌（+1 字段）；LabOps 后端 auth/models/crud/routers/schemas、前端 1 列；DB +1 列。
- **上线顺序**（加字段：先 schema 后代码 → 但本字段 LabOps 代码依赖它写入，需协调）：
  1. MDM 部署（令牌带姓名）——不影响老逻辑。
  2. schema 迁移加 `intake_operator_name` 列。
  3. LabOps 后端+前端部署。
  4. 历史回填。
- **回滚**：前端列、后端取值可独立回退；DB 列保留无害（可空）。

---

## 6. 验收 / 测试

| 项 | 预期 |
|---|---|
| MDM 令牌带姓名 | 登录后解析令牌含 `full_name` |
| 新入库 | 入库后该批次 `intake_operator_name` = 登录人姓名 |
| 库存分布显示 | 「入库人」列显示姓名；历史未回填行显示工号/— |
| 续期后 | refresh 换的新令牌仍带姓名（第 382 行也改） |
| 无姓名兜底 | 令牌偶无 full_name 时不报错，列显示 — |

**本地测试**：admin 登录 → 新建一个批次 → 库存分布查看「入库人」是否显示 admin 的姓名。

---

## 7. 待审阅确认点

1. 认同"令牌带姓名、入库时从令牌取快照"（而非每次查 MDM）。
2. 字段命名 `intake_operator_name`（入库人姓名）是否可。
3. 历史批次：是否做一次性回填？若做，请提供 `operator`(工号/旧账号) → 姓名 的完整对照表。
4. 其余技术细节认可后据此施工。
