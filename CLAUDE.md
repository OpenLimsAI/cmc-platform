# CLAUDE.md

> 本文件供 Claude Code 每次会话自动读取。**先读完再动手。**
> 详细实测记录见 `docs/source-survey-flex2.md`（所有结论均为 2026-07-15 实机验证，非推测）。

---

## 这是什么项目

`cmc-instrument-ingest` —— **小仪器原始数据的备份归档中心**（定位于 2026-07-15 确认）。

**本项目只做一件事：Stage 1 —— 从仪器侧只读拉取数据、SHA256 校验、归档到 NAS。不解析业务字段、不入库。**
当前只接入 Nova BioProfile FLEX2 一台仪器；设计为可容纳其他小仪器（Biacore 待收编），
但**现在不要做过度抽象**，只有一个 `flex2/` 目录，第二台来了再加平级目录。

**ETL 不在本项目。** 每台仪器的解析入库各自独立成 repo（Nova → `rd-nova-etl`，**尚未建**），
从 NAS 读归档 → 解析 → 入 `cmc_rd`，和 `rd-vicell-etl` / `rd-lucullus-etl` 的做法完全一致。

**两阶段解耦，这是架构的核心，物理上拆成两个 repo：**

```
FLEX2 共享（只读挂载）
    ↓  Stage 1（本项目 flex2/flex2_ingest.py）：复制 + SHA256 校验，不解析业务字段
NAS 原始归档（底本，永久保留）
    ↓  Stage 2（独立 repo rd-nova-etl，未建）：解析 + 入库，只读 NAS，绝不回连 FLEX2
cmc_rd → cmc_analytics
```

**为什么必须拆开**：归档是记录保存义务，ETL 是分析，两者验证范围不同；
合并后改一次 ETL schema 就要重新验证整条归档链路。且 ETL 挂掉时归档必须照常跑——数据先落袋为安。
拆成两个 repo 让这道边界更硬。

---

## 铁律（不可违反，违反了不是 bug 是事故）

1. **解析 CSV 必须按列名映射，禁止按列位置。**
   实测：逐次导出与月度导出的**列顺序不同**（`PO2@Temp`/`PCO2@Temp` 互换、
   `pH / Gas Flow Time`/`Chemistry Flow Time` 互换）。按位置解析会**静默调包数值**——
   不报错、数值都在合理范围、看不出来。
   列集合发生变化时必须**告警**，不许静默吞掉。

2. **源挂载点永远 `ro`。** 脚本启动时自验：能写入就立即中止。
   这是保护仪器数据的第一道锁，任何情况下不得移除。

3. **`.dbb` 只归档，不解析，不尝试破解。**
   实测是 7z 容器 + **AES 加密**（`LZMA2 + 7zAES`），密码在 Nova 手里。
   它的定位是**灾备保险**，不是数据源。不要写解压代码。

4. **不做"样品数据陈旧"告警。**
   实测这台仪器会连续停机 2–3 周（2026-01-23→02-05 空 13 天；02-10→03-03 空 21 天）。
   用它告警只会天天误报，最后没人看告警——那才是真正的失效。
   健康信号用 **Database 备份的新鲜度**（每晚 23:30 固定跑，与做不做样品无关）。

5. **校验不过就不归档。** 宁可告警缺一天，也不能把坏数据写进"底本"。

6. **凭据绝不进仓库。** `.gitignore` 必须挡住 `*.cred` / `*.env` / `*_state.json`。
   只提交 `*.env.example`。

7. **法规定位（写进 SOP，别自己加戏）**：
   法规意义上的原始记录是 **FLEX2 机内数据库 + 审计追踪**；CSV 是副本，NAS 归档是副本的副本。
   本系统定位为**分析数据源 + 业务备份**，**不是** Part 11 原始记录保存系统。
   这个定位能显著降低验证等级。不要在代码或文档里暗示相反的意思。

8. **真库建表走 `cmc-schema-migrations`，本项目 `sql/` 只是本地测试镜像 —— 这是规矩，不能破。**
   将来 Stage 2 ETL 要往 `cmc_rd` 建表 / 改表，**权威 DDL 一律在独立仓库 `cmc-schema-migrations`**
   （Alembic 迁移，命令 `dbmig`）里加迁移，和 `rd-vicell-etl` / `rd-lucullus-etl` 完全一致。
   本项目里的 `sql/001_cmc_rd_flex2.sql`（若创建）**只是本地一次性测试用的镜像副本，不是权威建表脚本**；
   一旦改结构必须两处同步，且**以 `cmc-schema-migrations` 为准**。**绝不拿本项目的 sql 直接在生产库上跑。**

---

## 数据源（已定，不要再改）

| 数据源 | 定位 | 说明 |
|---|---|---|
| `Results/SampleResults{AID}<YYYY>-<Month>.csv` | **✅ 唯一主数据源** | 月度累积，整月持续追加 |
| `Results/QcResults{AID}<YYYY>-<Month>.csv` | ✅ 一并采集 | 同上 |
| `Database/Backup_<ts>/` | ⚠️ 每日归档（保险） | 每晚覆盖，只留一份，不抓就永久丢失 |
| `Results/SampleResults{AID}<YYYY-MM-DD_HHMMSS>.csv` | ⬜ 冷归档一次后弃用 | 同事手动导的，已告知停止 |
| `Report/*.pdf` | ❌ 忽略 | 人工导的报告 |

`{AID}` = Analyzer ID = `T281240040C`（出现在每个文件名里，是多机区分的唯一标识）

**月度文件是"活的"** —— 整月都在长。策略是**每次内容变化存一份带时间戳的快照**，
不是覆盖同一个文件。额外好处：历史行若被改写或消失（`last_data_rows` 变少），脚本会立刻告警。
这是很硬的数据完整性证据。

---

## 当前状态

| | |
|---|---|
| 连通性 | ✅ 全部验证完毕 |
| Stage 1 `flex2/flex2_ingest.py` | ✅ v1.1.0（归档布局已对齐 NAS 既有多设备约定），**尚未实机跑过** |
| Stage 2 ETL | ⬜ 未开始，**迁往独立 repo `rd-nova-etl`**（不在本项目） |
| `sql/` 本地测试镜像 | ⬜ 未开始（真库 DDL 在 `cmc-schema-migrations`，见铁律 8） |
| 部署（挂载/systemd） | ⬜ 未执行 |

---

## 待办

**代码（本项目 = Stage 1 归档；带 → rd-nova-etl 的属 ETL，迁去独立 repo 做）**
- [ ] Stage 1 首跑：`--dry-run --backfill` → `--backfill` → 日常增量（顺序别跳）
- [ ] → rd-nova-etl：按列名映射解析器 + 去重 upsert
- [ ] `sql/001_cmc_rd_flex2.sql`：raw + meta only（`source_file` / `sha256` / `ingested_at` / `analyzer_id`），
      符合"raw 库严格只放 raw+meta，join/分析在 `cmc_analytics`"的既有约定。
      ⚠️ **权威 DDL 走 `cmc-schema-migrations`（见铁律 8），本文件只是本地测试镜像。**
      Stage 2 若拆成独立 repo `rd-nova-etl`，此项随之迁走。
- [ ] `dim.equipment` 增加 FLEX2 设备条目并关联
- [ ] `--verify-coverage`：核对每条逐次记录是否都在月度文件中
      ⚠️ **"月度是逐次的严格超集"目前只在 1 条样品记录上验证过，不是 280 个文件的证明。**
      验证通过才能正式弃用逐次文件。
- [ ] `tests/fixtures/`：脱敏样例 CSV，给解析器做回归

**需要人去问 / 去确认（不是代码能解决的）**
- [ ] C:\ 根目录 `生化分析仪数据备份 - Shortcut`（2025-08-18）是谁做的、在备份什么 —— 别撞车
- [ ] 2025-05 之前是否做过样品？（月度 SampleResults 最早只到 2025-05，QcResults 到 2024-01）
- [ ] 问 Nova：`.dbb` 恢复时由谁、用什么工具解密？密钥丢失时客户归档是否变成死数据？
- [ ] 问 Nova：`DatabaseBackup.dbb` + `Persist.dbb` 是否足以完整恢复？
- [ ] 问 Nova：是否提供 OPC 接口（Bridge PC 有 `OPC_` 目录）
- [ ] Bridge PC 账户 `nova_export_reader` 勾"密码永不过期"（否则 42 天后任务静默全挂）
- [ ] Bridge PC 仍启用 SMB1 → 报 IT 安全登记
- [ ] SOP：FLEX2 设置变更走变更控制，**Auto Export 不得关闭**
      （停掉手动导出后，没有第二份冗余；而程序层面无法区分"没做样"和"导出被关"）
- [ ] SOP：操作员录入规范。实测 Sample ID 下划线/横杠混用（`FBC_SN_D2` vs `FBC-SN-D0`），
      Vessel/Batch/Cell Type 有时被拼成一串填进 Batch ID。程序修不了，会影响趋势分析

---

## 风格约定

- 中文注释，中英混排技术术语
- 变更控制：改动逻辑请递增脚本内 `SCRIPT_VERSION` 并更新 `CHANGELOG.md`
- Stage 1 只用标准库（无第三方依赖）；Stage 2 可用 pandas / psycopg
- 沿用既有 Biacore 备份脚本的语义：state JSON + Checksums 目录 + 机器名 tag
