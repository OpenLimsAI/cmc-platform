# cmc-schema-migrations

`cmc_data_platform` 数据库结构的**单一真理来源（single source of truth）**。

四个应用（tt-lims-platform、cmc-inventory、qc_lims_etl、rd_lims_etl）共享这一个 PostgreSQL 库，但**只有这个仓库**有权改它的 schema。

## 使用场景

- **改 schema** = 在这里写一个 Alembic 迁移，`alembic upgrade head`，push
- **新环境部署** = clone 这个仓库，配 `.env`，`alembic upgrade head`，DB schema 完全就位
- **结构走样了** = 用 `compare_pg_inventory.py` 对比，发现差异；要么补迁移、要么 reset 到 head

## 快速上手

### 0. 装环境（首次）

```bash
cd cmc-schema-migrations
python3 -m venv .venv
source .venv/bin/activate          # Windows: .\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

### 1. 配 `.env`

把 `.env.example` 复制成 `.env`，填上 DB URL：

```bash
cp .env.example .env
# 然后编辑 .env
```

举例：

```bash
# Mac (Docker, 密码连接) —— 2026-06-03 起库在 rd_pg 容器，端口仍是 5432
DATABASE_URL=postgresql+psycopg2://postgres:YourStrongPassword_2026@127.0.0.1:5432/cmc_data_platform

# Linux (本机 Unix socket peer，无需密码)
DATABASE_URL=postgresql+psycopg2:///cmc_data_platform?host=/var/run/postgresql

# Linux (TCP 密码连接，备选)
DATABASE_URL=postgresql+psycopg2://postgres:xxx@127.0.0.1:5432/cmc_data_platform
```

`.env` 已经在 `.gitignore` 里，不会被 commit。

### 2. 看当前状态

```bash
alembic current      # 当前版本
alembic history      # 全部历史
alembic heads        # 头部版本号
```

### 3. 把库追到最新

```bash
alembic upgrade head
```

### 4. 写一个新迁移

```bash
alembic revision -m "describe what you change"
# 编辑 alembic/versions/xxx_describe_what_you_change.py
# 测试: alembic upgrade head
# 满意了就 git commit + push
```

## 日常工作流（简版，详版见 `SOP.md`）

```
Mac 上改 schema:
  1. cd cmc-schema-migrations && source .venv/bin/activate
  2. alembic revision -m "add foo column to bar"
  3. 编辑生成的 .py，写 upgrade / downgrade
  4. alembic upgrade head            ← 落到 Mac 的 Docker PG
  5. 用 docker exec -it postgres16 psql 进库看效果
  6. 跑应用代码验证
  7. git commit -am "..." && git push

Linux 部署:
  1. ssh -p 13568 prometheus@172.19.0.105
  2. cd ~/cmc-schema-migrations && git pull
  3. sudo -u postgres bash -c 'cd ~/cmc-schema-migrations && ./.venv/bin/alembic upgrade head'
  4. 用 sudo -u postgres psql -d cmc_data_platform 验证
```

**铁律**：永远不要手动 `psql -c "ALTER TABLE ..."` 改结构。所有结构变更必须经 Alembic。
完整 SOP 看 [`SOP.md`](./SOP.md)。

## 仓库结构

```
cmc-schema-migrations/
├─ alembic.ini                          # Alembic 配置
├─ alembic/
│  ├─ env.py                            # 从 DATABASE_URL 读连接，简单同步引擎
│  ├─ script.py.mako                    # 新迁移模板
│  └─ versions/                         # 迁移脚本
│     ├─ 001_add_target_days_to_dim_method.py
│     ├─ 002_dim_method_std_minutes_to_numeric.py
│     ├─ 003_align_dual_env_baseline.py
│     └─ 004_rehome_to_rd_pg_and_drop_meta_raw_qc_lims.py
├─ assets/                              # 大段 DDL / baseline 快照（被 migration 引用）
│  ├─ 003/
│  │  ├─ 01_material_mgmt_auth_tables.sql
│  │  ├─ 02_raw_qc_lims_schema.sql
│  │  └─ 03_cost_accounting_schema.sql
│  └─ 004/
│     └─ baseline_schema_2026-06-03.sql  # 重组后真实结构全量快照（灾备真理来源）
├─ requirements.txt                     # alembic, psycopg2-binary, python-dotenv
├─ .env.example                         # 文档化 DATABASE_URL（不含真密码）
├─ .gitignore                           # 排除 .env, .venv 等
└─ README.md
```

## 与盘点工具的关系

`F:\Python\sql\` 下的 `export_postgres_inventory.py` 和 `compare_pg_inventory.py` **不再是同步主力**，
退居为：

- **半年一次的体检**：跑盘点 + 对比，确认没人偷偷改库
- **怀疑 Alembic 漂移**时的真相校验

正常情况下，git pull + `alembic upgrade head` 就能保证两库一致。

## 历史背景（2026-05-13 baseline）

在这个仓库建立之前，`cmc_data_platform` 经过一段时间的双环境（Mac/Linux）并行演进，
两边结构曾出现 116 处差异。差异已通过手动对齐消除，结果记录在 migration `003` 中。

`alembic_version` 表此前从未存在过——之前的迁移文件（001、002）虽已写在 tt-lims-platform 里，
但实际 schema 变更都是手动 `psql` 执行的。本仓库建立后，两个数据库均通过 `alembic stamp head`
直接打标到 `003`，从此**强制**走 Alembic。

## 历史背景（2026-06-03 重组 + 重建 baseline）

Mac 端做了一次大调整：

- 项目目录从 `~/Python/cmc-schema-migrations` 挪到 `~/code/cmc-schema-migrations`（旧 `.venv` 因此失效，已重建）。
- 专用容器 `postgres16` 被删除；其数据 volume `postgres16_postgres16_data` 仍残留但已弃用。
- `cmc_data_platform` 迁入 `rd_pg` 容器（host 端口仍 5432）。
- 范围**有意缩减**：`meta` 与 `raw_qc_lims` 两个 schema 被拆走/退役，本库今后只管 `material_mgmt` + `cost_accounting`。
- 迁入后该库没有 `alembic_version` 表。通过 migration `004` + `alembic stamp head` 重新接管，
  并以 `assets/004/baseline_schema_2026-06-03.sql` 作为新的全量灾备真理来源
  （历史链 001→003 只是在既有库上打补丁，从来不能从空库构建）。

> ⚠️ **Linux VM 尚未处理**：Linux 上的 `cmc_data_platform` 很可能仍停在旧的「4 schema / v003」状态，
> 与 Mac 现状已分叉。是否让 Linux 也跟着缩范围（drop meta/raw_qc_lims、升到 004），需另行决定。
