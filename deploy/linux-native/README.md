# Linux 三实例原生 PostgreSQL 部署方案

> 目标：在 Linux VM（`prometheus@172.19.0.105:13568`）上，用**原生 PostgreSQL 16 多集群**
> 复刻 Mac 的三实例数据平台架构，与白皮书 `CMAB-DA-WP-001 V0.3` 完全对齐。
> 部署后两端结构一致，便于统一开发。
>
> **不使用 Docker**（Linux 直接跑原生集群）。Mac 用 Docker 只是本地开发习惯。

---

## 0. 目标拓扑

| 实例 | Linux 集群 | 端口 | 数据库 | Mac 对应 |
|---|---|---|---|---|
| **rd_pg** | `16/main`（现有，就地复用）| **5432** | `cmc_rd`, `cmc_analytics`, `cmc_data_platform`(待退役) | rd_pg 容器 :5432 |
| **mdm_pg** | `16/mdm`（新建）| **5433** | `cmab_mdm` | cmab-mdm-postgres :15432 |
| **gmp_pg** | `16/gmp`（新建）| **5434** | `cmc_gmp` | gmp_pg :5434 |

各库 schema（复刻自 Mac，快照在 `../schema/`）：

```
rd_pg:5432
├── cmc_rd            meta, raw_rd_lims_samplemanager, raw_rd_usp_lucullus
├── cmc_analytics     mart, staging, mdm, ml_features, reporting, ext_gmp/rd/mdm, snap_gmp/mdm, meta
└── cmc_data_platform material_mgmt, cost_accounting   ← 待退役，结构保留、数据不导

mdm_pg:5433
└── cmab_mdm          srs, prs, ars, mm, ref, audit, auth, meta

gmp_pg:5434
└── cmc_gmp           meta, raw_gmp_lims_labvantage
```

各库角色（复刻自 Mac）：

| 实例 | 角色 |
|---|---|
| rd_pg | `cmc_user`, `lims_admin`, `lims_reader`, `lims_mdm_writer`, `lucullus_etl`, `quality_user` |
| mdm_pg | `cmab_app`(owner), `cmab_audit_reader` |
| gmp_pg | `gmp_etl`, `gmp_reader` |

---

## 1. 前提与现状

- Linux 现在**只有一个集群** `16/main:5432`，里面只有一个业务库 `cmc_data_platform`（旧的 8 schema），被 5 个老应用占用。三实例在 Linux 上**尚不存在**。
- **策略：推平重建（nuke & pave）**。数据全部丢弃（已确认）：所以不做迁移、不做就地重置，直接清空旧库 + 建三实例 + 灌 Mac 同款 schema。cost_accounting/cmab_mdm 只建表不导数据；ETL 库重跑。
- 旧库已全量备份：`~/cmc_data_platform_backup_2026-06-03.sql`（102 MB），唯一后悔药。

> ⚠️ **有停机**：推平前必须先停 5 个老应用 + cron（否则它们对着被删的库狂刷错误，且被 systemd 自动拉起）。按 §3 顺序执行。
> “删除所有实例”在 Linux 上 = 清空 main 里的旧库（§3.1）。main 集群本身保留用作 rd_pg:5432；如坚持连集群一起删，可 `sudo pg_dropcluster --stop 16 main` 后在 01 脚本里补建 5432 集群——但通常没必要，徒增 pg_hba/conf 重配。

---

## 2. 文件清单

```
deploy/linux-native/
├── README.md                  ← 本文（主 runbook）
├── schema/                    ← Mac 各库 schema-only 快照（复刻真理来源）
│   ├── cmc_rd.schema.sql
│   ├── cmc_analytics.schema.sql
│   ├── cmc_gmp.schema.sql
│   └── cmab_mdm.schema.sql
│   （cmc_data_platform 用仓库根的 assets/004/baseline_schema_2026-06-03.sql）
└── scripts/
    ├── 01_create_clusters.sh  ← 建 5433/5434 两个新集群
    ├── 02_init_rd_pg.sql      ← rd_pg 角色 + 三库
    ├── 02_init_mdm_pg.sql     ← mdm_pg 角色 + cmab_mdm
    ├── 02_init_gmp_pg.sql     ← gmp_pg 角色 + cmc_gmp
    ├── 03_load_schemas.sh     ← 把 schema 快照灌进各库
    └── 04_grants.sql          ← 按白皮书 Part IV 的基线授权
```

---

## 3. 执行顺序（在 Linux 上）

> 全程 `sudo -u postgres`。先把整个 `deploy/linux-native/` 传到 Linux：
> `scp -P 13568 -r deploy/linux-native prometheus@172.19.0.105:/opt/cmc-deploy`
> 同时把 `assets/004/baseline_schema_2026-06-03.sql` 一并传过去。

### 3.1 停老应用 + 确认备份（推平前提）

```bash
# 停服务（systemd）。KeepAlive 类需 disable 防自动拉起
sudo systemctl stop cmc-backend cmc-frontend
systemctl --user stop tt-lims-backend tt-lims-frontend
crontab -e    # 注释掉 rd_lims_etl 的 3 条 cron（切换期间）
# 确认没有残留连接占着 cmc_data_platform（DROP DATABASE 需要无连接）
sudo -u postgres psql -p 5432 -tAc \
  "SELECT count(*) FROM pg_stat_activity WHERE datname='cmc_data_platform'"   # 应为 0
# 后悔药还在
ls -la ~/cmc_data_platform_backup_2026-06-03.sql
```

> 02_init_rd_pg.sql 会 `DROP DATABASE cmc_data_platform` —— 上面连接数必须为 0 才不会失败。

### 3.3 建两个新集群（5433 / 5434）

```bash
cd /opt/cmc-deploy/scripts
sudo bash 01_create_clusters.sh
pg_lsclusters          # 应看到 16/main:5432, 16/mdm:5433, 16/gmp:5434 都 online
```

### 3.4 建角色 + 库

```bash
# rd_pg = main:5432
sudo -u postgres psql -p 5432 -v ON_ERROR_STOP=1 -f 02_init_rd_pg.sql
# mdm_pg = 5433
sudo -u postgres psql -p 5433 -v ON_ERROR_STOP=1 -f 02_init_mdm_pg.sql
# gmp_pg = 5434
sudo -u postgres psql -p 5434 -v ON_ERROR_STOP=1 -f 02_init_gmp_pg.sql
```

> 角色密码在脚本里是占位符 `CHANGE_ME_*`。执行前改成真实密码，或执行后用
> `ALTER ROLE xxx PASSWORD '...';`，并同步到各 app 的 `.env`。

### 3.5 灌 schema

```bash
sudo bash 03_load_schemas.sh /opt/cmc-deploy/schema ~/cmc_data_platform_baseline.sql
# 末参数 = cmc_data_platform 的 assets/004 快照路径
```

### 3.6 授权（白皮书 Part IV 基线）

```bash
sudo -u postgres psql -p 5432 -f 04_grants.sql   # 只对 rd_pg 的库；mdm/gmp 授权见脚本注释
```

### 3.7 配 pg_hba（应用走 127.0.0.1 + 密码）

三个集群各自的 `pg_hba.conf`（`/etc/postgresql/16/{main,mdm,gmp}/pg_hba.conf`）加一行（若无）：

```
# 本机应用密码连接
host    all    all    127.0.0.1/32    scram-sha-256
host    all    all    ::1/128         scram-sha-256
```

然后 `sudo systemctl reload postgresql@16-main postgresql@16-mdm postgresql@16-gmp`。

### 3.8 验证

```bash
for p in 5432 5433 5434; do
  echo "== :$p =="
  sudo -u postgres psql -p $p -tAc "SELECT datname FROM pg_database WHERE datistemplate=false AND datname<>'postgres'"
done
sudo -u postgres psql -p 5432 -d cmc_rd -tAc "\dn"   # schema 齐不齐
```

---

## 4. 代码部署（Mac→Git→Linux）

| 项目 | github | Linux 操作 |
|---|---|---|
| cmc-inventory | `qingcheng81/cmc-inventory` | `git clone` 新建 |
| rd-lims-etl | `qingcheng81/rd-lims-etl` | `git clone` |
| cmc-cost-modeler | `qingcheng81/cmc-cost-modeler` | `git clone` |
| cmc-rd-lims-dashboard | `qingcheng81/cmc-rd-lims-dashboard` | `git clone` |
| cmab-mdm-platform | `qingcheng81/cmab-mdm-platform` | `git clone`（注意它原是 Docker，Linux 改连原生 5433）|
| cmc-quality-analytics-platform | **非 git** | 先在 Mac `git init`+push，或 `scp` |
| qc-lims-etl | **非 git** | 同上 |
| lucullus_etl | **非 git** | 同上 |

> 老目录名（`tt-lims-platform`/`qc_lims_etl`/`rd_lims_etl`）是重构前的，**不要 pull 进旧目录**，按新名重新 clone。

### 4.1 各 app 的 Linux `.env`（关键：端口/库名/角色对齐）

| 项目 | 连接目标（Linux）|
|---|---|
| cmc-inventory | `127.0.0.1:5432/cmc_data_platform`，用户 `cmc_user` |
| cmc-cost-modeler | `127.0.0.1:5432/cmc_data_platform` |
| rd-lims-etl | `127.0.0.1:5432/cmc_rd` + `cmc_analytics`，用户 `lucullus_etl` |
| qc-lims-etl | `127.0.0.1:5434/cmc_gmp` + `5432/cmc_analytics`，用户 `gmp_etl` |
| cmc-rd-lims-dashboard | `5432/cmc_analytics`+`cmc_rd`+`cmc_data_platform`，`5433/cmab_mdm`（只读）|
| cmc-quality-analytics-platform | `5432/cmc_analytics`，用户 `quality_user`/`lims_reader` |
| cmab-mdm-platform | `127.0.0.1:5433/cmab_mdm`，用户 `cmab_app`（**Mac 是 15432→Linux 5433**）|

> Mac 上各 app 把 DB 端口写在 `.env` / compose；Linux 部署时逐个改成上表（mdm 尤其要从 15432 改 5433）。

---

## 5. ETL 重灌 + 启动

```bash
# 确认 ETL 源（SampleManager / Lucullus / LabVantage）从 Linux 可达
# 手动跑一轮，确认能写进新库
bash /opt/rd-lims-etl/scripts/run_etl.sh
# 验证行数后，恢复 cron / 启动各服务
sudo systemctl start cmc-backend cmc-frontend
```

---

## 6. 收尾

- 推平已使旧遗留 schema（raw_qc_lims/raw_rd_lims/staging_rd/app_rd/旧 meta）随整库消失，无需再单独瘦身。
- 新栈全绿、ETL 重灌确认无误后，可删除备份文件 `~/cmc_data_platform_backup_2026-06-03.sql`（确认不再需要回滚时）。
- 把本部署结果（端口/角色/库）补回白皮书 Part I 与 PORTS.md。
- 本仓库 `cmc-schema-migrations` 仅是 `cmc_data_platform` 的 Alembic 真理来源；
  `cmc_rd`/`cmc_analytics`/`cmc_gmp`/`cmab_mdm` 的结构真理来源是 `deploy/linux-native/schema/` 的快照
  （后续若要纳入迁移管理，各自另立 Alembic 链）。

---

## 7. 回滚

新栈未通过验证前，旧 main 集群数据仍可从 `~/cmc_data_platform_backup_2026-06-03.sql` 恢复：

```bash
sudo -u postgres createdb cmc_data_platform_restore
sudo -u postgres psql -d cmc_data_platform_restore -f ~/cmc_data_platform_backup_2026-06-03.sql
```

两个新集群可整体删除重来：`sudo pg_dropcluster --stop 16 mdm && sudo pg_dropcluster --stop 16 gmp`。
