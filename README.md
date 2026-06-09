# cmc-schema-migrations

CMC 数据平台**多个共享数据库结构的单一真理来源**，用多环境 Alembic 管理。

本仓库管 **4 个无 ORM 的共享库**（被多个 app 共用，所以由这个中立仓库统一管，而不是某个 app）：

| 库 | 实例（端口）| 主要使用方 |
|---|---|---|
| `cmc_rd` | rd_pg : 5432 | rd-lims-etl（raw + meta）|
| `cmc_analytics` | rd_pg : 5432 | dashboard / quality-analytics / 各 ETL（dim/staging/mart…）|
| `cmc_data_platform` | rd_pg : 5432 | cmc-inventory / cmc-cost-modeler（material_mgmt / cost_accounting / equipment_mgmt）|
| `cmc_gmp` | gmp_pg : 5434 | qc-lims-etl（GMP LabVantage raw + meta）|

> `cmab_mdm`（MDM Portal）**不在此**——它是单一 app 独占库，由 `cmab-mdm-platform` 自带 alembic（autogenerate）管理。
> 但通过 `dbmig` 可用同一套命令访问它（见下）。架构定义见 `CMAB-DA-WP-001` 白皮书。

---

## 统一入口：`dbmig`

无论改哪个库，命令都一样：

```bash
./dbmig list                          # 看所有库的当前版本
./dbmig <库> revision -m "改了啥"      # 写迁移
./dbmig <库> upgrade head             # 落地
./dbmig <库> history                  # 历史
./dbmig <库> current                  # 当前版本
```

`<库>` ∈ `cmc_rd` / `cmc_analytics` / `cmc_data_platform` / `cmc_gmp` / `cmab_mdm`。
（`cmab_mdm` 会自动转发到 `cmab-mdm-platform/backend` 的 alembic。）

底层其实是 `alembic -n <库> ...`（一个 `alembic/env.py` 按 `-n` 选库），`dbmig` 只是薄封装。

---

## 日常工作流（任何库、任何实例，完全一致）

```
Mac 开发：
  1. 改 schema（写迁移）
     ./dbmig <库> revision -m "add foo column"
  2. 编辑生成的迁移 .py（写 upgrade/downgrade）
  3. ./dbmig <库> upgrade head          ← 落到 Mac 测试
  4. 跑应用验证
  5. git commit + git push

Linux 部署：
  6. ssh -p 13568 prometheus@172.19.0.105
  7. cd ~/cmc-schema-migrations && git pull
  8. ./dbmig <库> upgrade head
  9. ./dbmig <库> current 验证
```

**铁律**：所有结构变更（schema/表/列/索引/约束/视图/函数）必须经 Alembic。
**永远不要**手动 `psql -c "ALTER TABLE..."` 改库。详见 [`SOP.md`](./SOP.md)。

---

## 首次在一台新机器上用（bootstrap）

```bash
git clone git@github.com:qingcheng81/cmc-schema-migrations.git
cd cmc-schema-migrations

# 1) 建 venv（用 uv）
uv venv .venv
uv pip install -r requirements.txt --python .venv/bin/python

# 2) 配 .env（含 DB 密码，不入库）
cp .env.example .env
#   填 PG_USER / PG_PASSWORD / 端口
chmod 600 .env                 # 含库密码，收紧为仅本人可读写

# 3) 看状态
./dbmig list
```

`.env` 用**共享凭据**（一套 `PG_USER`/`PG_PASSWORD` + 端口按库），且 **Mac(docker) 与 Linux(原生) 端口相同**，所以同一份 `.env` 两端通用。

> ⚠️ `.env` 是明文数据库密码，务必 `chmod 600`（仅本人可读写），别留成全用户可读的 `644`。Mac、Linux 两端都要。

> **从空库重建**：每个库都有一个能从空库一把建出全部结构的 baseline。
> 新库：`createdb <库>` 后 `./dbmig <库> upgrade head` 即可。

---

## 连接模型（`.env`）

```bash
PG_HOST=127.0.0.1
PG_USER=postgres
PG_PASSWORD=...          # Mac docker 与 Linux 原生 已统一为同一值
PG_PORT_RD=5432          # cmc_rd / cmc_analytics / cmc_data_platform
PG_PORT_GMP=5434         # cmc_gmp
```

`alembic/env.py` 据 `-n <库名>` 自动拼连接串：`cmc_gmp` 走 `PG_PORT_GMP`，其余走 `PG_PORT_RD`。

---

## 仓库结构

```
cmc-schema-migrations/
├─ dbmig                          # ★ 统一入口脚本
├─ alembic.ini                    # 多 section（每库一段）
├─ alembic/
│  ├─ env.py                      # 共享：按 -n <库> 拼连接
│  ├─ script.py.mako
│  ├─ baselines/                  # 各库全量结构快照（baseline 迁移引用）
│  │  ├─ cmc_rd.sql / cmc_analytics.sql / cmc_data_platform.sql / cmc_gmp.sql
│  └─ versions/
│     ├─ cmc_rd/                  # 每库独立 versions 目录与版本表
│     ├─ cmc_analytics/
│     ├─ cmc_data_platform/
│     ├─ cmc_gmp/
│     └─ _legacy/                 # 旧 001-004（已归档，不再使用）
├─ assets/                        # 历史 DDL 片段（_legacy 迁移引用）
├─ deploy/linux-native/           # ★ Linux 三实例部署 runbook + 纪要 + schema 快照
├─ tools/                         # 盘点/对比脚本（半年体检用）
├─ .env.example  .gitignore  requirements.txt
└─ README.md  SOP.md
```

---

## 部署与架构

- **Linux 三原生 PG 实例**（rd_pg:5432 / mdm_pg:5433 / gmp_pg:5434）的完整部署见
  [`deploy/linux-native/README.md`](./deploy/linux-native/README.md)，过程纪要见同目录
  `部署纪要_2026-06-03.md`。
- Mac 用 Docker（rd_pg / gmp_pg / cmab-mdm-postgres），Linux 用原生集群，端口对齐。

---

## 漂移体检（兜底）

万一有人绕过 Alembic 直接改库，靠 `tools/` 下的盘点+对比脚本发现。建议每月一次。
正常情况下，`git pull` + `./dbmig <库> upgrade head` 就能保证两端一致。

快速列级对比（任一库）：导出两端 `information_schema.columns` 指纹并 diff。

---

## 历史背景（简记）

- **2026-05-13**：`cmc_data_platform` 曾双环境漂移 116 处，手动对齐后记录在旧 `003`。
- **2026-06-03**：Mac 大重构——`postgres16` 容器删除、库迁入 `rd_pg`、单库拆为多库
  （cmc_rd / cmc_analytics / cmc_gmp / cmab_mdm），`meta`/`raw_qc_lims` 等拆走。
- **2026-06-04**：Linux 重建为三原生实例并与 Mac 对齐；本仓库改为**多环境 alembic** 管 4 库，
  每库重做干净 baseline（旧 001-004 归档 `_legacy`），加 `dbmig` 统一入口，git 化接通两端。

完整经过见 `deploy/linux-native/部署纪要_2026-06-03.md`。
