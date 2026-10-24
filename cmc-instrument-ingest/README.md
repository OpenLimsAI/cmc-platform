# cmc-instrument-ingest

> **小仪器原始数据备份归档中心。** 从实验室仪器侧**只读拉取**数据，SHA-256 校验后归档到 NAS，作为 CMC 数据中台的底本与业务备份。

本仓库**只做备份归档（Stage 1）**，不解析业务字段、不入库。每台仪器的解析入库（ETL）各自独立成 repo。
已接入的源：

| 仪器 | 目录 | 源 | 状态 |
|---|---|---|---|
| Nova Biomedical BioProfile **FLEX2**（生化分析仪，Analyzer ID `T281240040C`） | `flex2/` | `//10.0.13.66/Export`（SMB 3.0） | ✅ 已上线 |
| Beckman **Vi-CELL XR**（细胞计数仪，工作站 `C4V61257XH`） | `vicell/` | `//10.0.13.36/Vi-Cell$`（**SMB 2.1**，Win7） | 🟡 待首跑 |
| Bioengineering **RALF** 发酵工作站（**数据库型源**，多台） | `ralf/` | MySQL 4.1 `10.0.13.58:3306` 等，`mysqldump` 导出 | 🌱 勘察/设计中（脚本待联网实测） |

> ⚠️ **ralf 是本库第一个「数据库型」源**：用 `mysqldump` 导出整库，而非复制文件；
> 与文件型仪器的规范差异（不挂 CIFS、走只读 DB 账号、自己的周/月定时器）见 `docs/source-survey-ralf.md` §3。
>
> ⚠️ 动手前先读 [`CLAUDE.md`](./CLAUDE.md)（铁律）和对应的数据源实测记录：
> [`docs/source-survey-flex2.md`](./docs/source-survey-flex2.md) / [`docs/source-survey-vicell.md`](./docs/source-survey-vicell.md) / [`docs/source-survey-ralf.md`](./docs/source-survey-ralf.md)。

---

## 架构：两阶段解耦

归档是**记录保存义务**，ETL 是**分析**，两者验证范围不同、物理上拆成两个 repo。
ETL 挂掉时归档必须照常跑——数据先落袋为安。

```
FLEX2 共享（SMB，只读挂载）
    │   Stage 1 ← 本仓库：复制 + SHA-256 校验，不解析业务字段
    ▼
NAS 原始归档（底本，永久保留）
    │   Stage 2 ← 独立 repo rd-nova-etl（未建）：解析 + 入库，只读 NAS，绝不回连 FLEX2
    ▼
cmc_rd  →  cmc_analytics
```

**法规定位**：法规意义上的原始记录是 FLEX2 机内数据库 + 审计追踪；CSV 是副本，NAS 归档是副本的副本。
本系统是**分析数据源 + 业务备份**，不是 Part 11 原始记录保存系统。

---

## 目录结构

```
cmc-instrument-ingest/
├── CLAUDE.md                     # 项目铁律 + 状态 + 待办（每次会话先读）
├── README.md                     # 本文件
├── CHANGELOG.md                  # 变更记录（跟随脚本 SCRIPT_VERSION）
├── flex2/
│   ├── flex2_ingest.py           # Stage 1 采集脚本（仅标准库）
│   └── flex2-ingest.env.example  # 配置样例（真配置不入库）
└── docs/
    ├── SETUP.md                  # Linux 部署：凭据 / 挂载 / systemd / 首跑
    └── source-survey-flex2.md    # 数据源实测记录（连通性 / CSV 格式 / 坑）
```

第二台小仪器接入时，加一个平级目录（如 `biacore/`）——现在不做过度抽象。

---

## 快速开始

部署与首跑完整步骤见 [`docs/SETUP.md`](./docs/SETUP.md)。要点：

```bash
# 1. 配置：复制样例，改成实际值（不要提交真配置）
cp flex2/flex2-ingest.env.example /etc/flex2-ingest.env

# 2. 首跑，按顺序，别跳步（详见 SETUP.md §4）
flex2/flex2_ingest.py --dry-run --backfill   # a. 空跑，只探测和校验，不写 NAS
flex2/flex2_ingest.py --backfill             # b. 回填历史
flex2/flex2_ingest.py                        # c. 日常增量（systemd timer 这么跑）
```

**源挂载点必须 `ro`**：脚本启动会自验，能写入就立即中止（保护仪器数据的第一道锁）。

---

## NAS 归档布局

归档写到 NAS 共享根 `TTLab_Backups` 下、按设备划分的目录：

沿用 NAS 上既有的多设备备份约定（数据在 `Daily/`，记账在根级 `Checksums/`、`Logs/`、`State/`，均按机器名分）：

```
/mnt/ttlab-backups/                     NAS 共享根（多设备共用）
├── Daily/T281240040C_Nova/             数据（内部镜像仪器 Export）
│   ├── Results/                        月度快照（Monthly/）+ 逐次冷备（PerEvent/）
│   ├── Database/                       每晚数据库备份（Nova 只留一份，不抓就永久丢失）
│   └── Report/                         NAS 侧预建，程序不写（人工 PDF，忽略）
├── Checksums/T281240040C_Nova/         每次运行一个 SHA256_Compare CSV（审计记录，格式同其它设备）
├── Logs/T281240040C_Nova/              运行日志
└── State/T281240040C_Nova_backup_state.json   运行状态（断点续传）
```

---

## 铁律（摘要，完整见 [`CLAUDE.md`](./CLAUDE.md)）

1. 解析 CSV 必须按**列名**映射，禁止按列位置（逐次/月度列顺序不同，按位置会静默调包数值）。
2. 源挂载点永远 `ro`，脚本自验，可写即中止。
3. `.dbb` 只归档，不解析，不破解（7z + AES 加密，密码在 Nova 手里）。
4. 不做"样品数据陈旧"告警（仪器会连续停机数周，只会误报）；健康信号用 Database 备份新鲜度。
5. 校验不过就不归档（宁可告警缺一天，不把坏数据写进底本）。
6. 凭据绝不进仓库（`.gitignore` 挡 `*.cred` / `*.env` / `*_state.json`，只提交 `*.env.example`）。
7. 法规定位见上，不在代码/文档里暗示自己是 Part 11 原始记录系统。
8. **真库建表走 `cmc-schema-migrations`**，本项目 `sql/` 仅本地测试镜像，绝不在生产库直接跑。

---

## 当前状态

| | |
|---|---|
| 连通性 | ✅ 全部验证完毕 |
| Stage 1 `flex2/flex2_ingest.py` | ✅ v1.2.0（校验放宽：多行宽只告警不拒收） |
| 部署（挂载 / systemd） | ✅ 已上线（Linux `/opt`；所有仪器共用两个 timer：`02:00` 全量 / `11:45`+`16:00` 不含图片；历史 backfill 已归档） |
| Stage 2 ETL | ⬜ 未开始，迁往独立 repo `rd-nova-etl`（不在本项目） |

---

## 相关仓库

| 仓库 | 作用 |
|---|---|
| `cmc-schema-migrations` | 数据库建表/改表的**权威** DDL（Alembic 迁移，`dbmig`） |
| `rd-nova-etl`（未建） | Nova FLEX2 的 ETL：从 NAS 读归档 → 解析 → 入 `cmc_rd` |
| `rd-vicell-etl` / `rd-lucullus-etl` | 同类设备 ETL，本项目的架构参照 |
