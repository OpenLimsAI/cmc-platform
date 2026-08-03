# Changelog

本文件记录 `cmc-instrument-ingest` 的变更。遵循 [Keep a Changelog](https://keepachangelog.com/zh-CN/) 风格。
版本号跟随各采集脚本内的 `SCRIPT_VERSION`（改动逻辑必须同步递增并在此登记，见 `CLAUDE.md` 风格约定）。

---

## vicell_ingest.py — v1.4.0 + alerting/heartbeat v1.0.0 (2026-08-03)

**整改 MD-004（告警送达）与 MD-005（任务未执行检测）。**
设计依据 `docs/BACKUP_MONITORING_DESIGN.md`；测试 `docs/MONITORING-TEST-REPORT-2026-08-03.md`。

- 新增 `vicell/alerting.py`：统一异常事件模型。severity 归一化为三级
  （原有 `CRITICAL`/`ERROR`/`WARN`/`WARNING` 四种拼法），事件按关键词归入九类
  （`SHA256_MISMATCH` / `MOUNT_ERROR` / `NAS_UNWRITABLE` / `SOURCE_UNAVAILABLE` /
  `METADATA_FAILED` / `COPY_FAILED` / `SOURCE_DELETED` / `CONTENT_CHANGED` /
  `STRUCTURE_ANOMALY` / `RUN_FAILED`），未命中归 `UNCLASSIFIED` **绝不丢事件**。
  落盘 `Alerts/<机器名>/alert_YYYYMMDD.jsonl`，**NAS 与本地双写**
  ——"NAS 不可写"恰恰是要告警的场景，只写 NAS 等于最重要的那条写不进去。
- 新增 `vicell/heartbeat.py`：每台仪器一个 `State/<机器名>_heartbeat.json`，
  **每次运行都写**，`last_success_time` 仅成功时更新。
  `expected_interval_hours` / `max_silence_hours` 写进文件本身，使巡检脚本通用。
- 新增 `tools/heartbeat_check.py` + systemd 单元（每日 09:00）：
  **独立于采集程序**扫描心跳，超时/失败/缺失即告警，退出码 0/1。
- `alert()` 内部改走 AlertSink，**32 处调用点签名与参数一律不改**。

**修复原实现的两个缺陷（审计 A-3 / A-4）**

| 缺陷 | 原行为 | 现行为 |
|---|---|---|
| 告警命令返回非零 | `check=False` 且只捕获异常 → **完全静默** | 检查返回码并记 WARNING（T6 实测） |
| 无限流 | 每条 `timeout=30` 无上限，100 条最坏阻塞 **50 分钟** | 外呼次数 20 / 同类 5 / 单条 10s / 总计 60s 四重上限。**实测 100 条告警耗时 0.01 秒** |

**测试中发现并修复的设计缺口**：预检失败原本直接 `SystemExit`、**不写心跳**，
导致"挂载坏了"与"程序根本没跑"在巡检看来完全一样——而这正是心跳要区分的。
已改为预检失败时先写 `FAILED` 心跳再退出（T3 实测验证）。

**已知限制**：`files_processed` 在文件校验失败时会多计（`archive_flat_dir` 中
`stats["new"]` 自增早于写入尝试，属既有逻辑非本次引入）；`files_failed` 仍准确。

**测试**：11 项全部通过。T4（NAS 不可写）与 T10a/T10b（心跳写入失败）在本地 Docker
Linux 容器中完成（Vi-CELL 网络当时不可达），用 tmpfs 挂载点 + 文件权限忠实复现场景：
- T4：退出码 1，`CRITICAL`/`NAS_UNWRITABLE`×4，**NAS 完全不可写时本地兜底告警仍生成**，NAS 零残留
- T10a/T10b：心跳写入失败（含 NAS 与本地都失败的最坏情况）**退出码仍为 0**，归档文件正常

**MD-004 状态：Phase 1 completed — Alert generation + persistent logging.**
**Residual gap: `ALERT_CMD` notification endpoint not configured.**
外呼端点接入并确认收件前**不得宣称 MD-004 已关闭**。

**MD-005 残留风险 R-1**：`heartbeat_check.py` 自身未被独立监控——检查者本身也需要被检查。
后续用 daily positive heartbeat/report 机制解决（依赖 MD-004 Phase 2 的通知端点）。

**未完成**：测试残留待清理；v1.4.0 尚未部署到 `/opt`（等图片回补跑完）。
部署步骤见 `docs/DEPLOYMENT-CHECKLIST-v1.4.0.md`。

## vicell_ingest.py — v1.3.0 + smb_metadata.py v1.0.0 (2026-08-03)

**整改 MD-001：补充 Windows 原始文件 metadata 采集能力。**
设计依据 `docs/DATA_INTEGRITY_METADATA_DESIGN.md`；审计来源 `docs/AUDIT-2026-08-03-data-integrity.md`。

- 新增 `vicell/smb_metadata.py`：从 CIFS 扩展属性 `user.cifs.creationtime` 读取
  **Windows 原始创建时间**（8 字节小端 FILETIME），配合 `os.stat()` 取修改/访问/变更时间。
  仅标准库，不引入外部依赖。
- 新增输出 `Metadata/<机器名>/<时间戳>_SMB_Metadata.csv`（12 列，UTF-8 with BOM，
  时间一律 ISO-8601 带时区）。与 `Checksums/` 的关联键为
  `relative_path` + `source_path` + `file_size`。
- 新增 `--metadata-backfill`（只给已归档文件补采，不复制、不改 state）、`--no-metadata`；
  环境变量 `VICELL_COLLECT_METADATA=0` 可完全关闭，关闭后行为与 v1.2.1 一致。
- **未改动**：复制逻辑、SHA-256 双向校验流程、NAS 目录结构、`Checksums/` 格式、state 结构。
  采集调用点一律在"归档成功并记账之后"，且 `collect()` 内部全捕获、绝不抛出。
- 采集失败不阻断备份，以 WARNING 记录并**按原因聚合**（13 万文件逐条告警会淹没日志）；
  失败仍写出该行，`metadata_source` 标 `stat-only` / `failed`，缺失字段留空。
- metadata 在主线程采集，不放进复制线程池——`stats` 累加非原子操作，放进池里会丢计数。
  每目录 50 个文件约 0.13 秒，相对 8 秒的复制耗时可忽略。

**实测依据**（详见 `docs/METADATA-TEST-REPORT-2026-08-03.md`）

| 项 | 结果 |
|---|---|
| xattr 解码与 `smbclient allinfo` 一致性 | 四个时间字段逐秒吻合 |
| 采集速度（冷读） | **2.6 ms/文件** → 13 万文件约 6 分钟 |
| 对照 `smbclient allinfo` | 边际 **72 ms/文件** → 约 2.6 小时，且需外部命令依赖 |
| 属主/ACL（`system.cifs_ntsd`） | 可取但 **201 ms/文件**，本阶段不采集 |

**已知限制（不可消除，见设计文档 §3）**：NAS 归档副本自身**无法携带** Windows 创建时间
——Linux 无设置该字段的系统调用，换复制方法或换数据源均无效。
本系统保存的是 **Original Source Creation Time**，作为独立证据记录，
**不尝试**修改 NAS 副本的创建时间。

## vicell_ingest.py — v1.2.1 (2026-08-03)

**修正：时间戳必须在 rename 之后设，否则被 CIFS 冲掉。**（补记：该版发布时漏登记）

- 实测本 NAS 的 CIFS 上 `os.replace` 会把文件修改时间重置为当前时间，
  原来"先 utime 再 rename"（为保原子性）等于白设。回补抽查时发现：
  内容 SHA-256 一致、文件数正确，唯独修改时间是归档时间而非原始拍摄时间。
- `write_atomic` 改为 rename 之后再 utime；原子性保的是"内容不被读到半截"，
  时间戳晚几毫秒对齐无妨。
- 设完立刻回读确认，不一致则告警——这个坑静默发生、内容校验全绿，不主动查发现不了。
- 影响范围：v1.0.0/v1.1.0/v1.2.0 归档的文件时间戳均为归档时间；
  Data/Export 已由一次性脚本修正 55712 个，图片已清记账重做。

## vicell_ingest.py — v1.2.0 (2026-08-03)

**图片复制改为并发，回补耗时从约 21 小时降到约 5 小时。**

- 样品目录内的文件复制改用线程池（`VICELL_COPY_WORKERS`，默认 6）。
  每个文件的"读源→写临时→fsync→改时间→rename→回读校验"彼此独立，可并发。
- 实测数据（2026-08-03，Vi-CELL 工作站）：
  | 项 | 值 |
  |---|---|
  | 仪器侧读取上限 | **约 15 MB/s，且并行读与顺序读同速**（366 MB 都是 23 s）→ 服务端上限，加并发无用 |
  | NAS 写入 | 103 MB/s（含 `conv=fsync`），不是瓶颈 |
  | 串行时实际吞吐 | 约 2 MB/s（30 s/样品目录） |
  | 并发 6 后 | 约 8.4 MB/s（7.3 s/样品目录） |
  | 并发 12 / 20 | 与 6 无差异 → 6 即够 |
- 未进一步优化的原因：剩余差距来自每文件的 fsync 与回读校验。
  省掉 fsync 虽能提速，但回读可能命中 CIFS 客户端缓存，**等于没校验**——
  不拿完整性换速度（铁律 2/§6）。

## vicell_ingest.py — v1.1.0 (2026-08-03)

**支持多来源：历史图片改从 D 盘原始位置取；接入四个历史遗留目录与仪器配置/审计追踪。**

- **主图片集按优先级取源**：`archive_sample_dirs()` 接受有序的源列表，样品名在多个源都有时
  取排在前面的。配置为 `[D:\Vi-Cell 计数图像, E:\Vi-Cell\Images]`，实跑来源分布
  **dimg:1602 / Images:397**——2026-07 之前的历史样品取自软件当年真正写入的 D 盘原始位置，
  之后的新样品取自现用目录。状态文件里逐目录记录 `source`，比对表 `Local_Path` 记录实际来源。
  > 依据：D 盘与 E 盘重合部分已**全量核对一致**——1602 个目录的文件名/大小/修改时间全等、
  > 零差异；随机 40 个目录 2000 个文件逐个 SHA-256 全部一致。内容既然相同，
  > 取原始位置只是让归档记录的来源更经得起问。
- **新增历史遗留目录归档**（`legacy/<原目录名>/`，保留来源目录名以便追溯与防同名覆盖）：
  `XR-2025.04.27`(121 样品/6050 图)、`2025.5.14HEK-293计数图片`(73/3650)、
  `1111`(395/19750)、`计数仪历史数据`(56 个 txt)。
- **新增仪器配置与审计追踪归档**（`config/`）：取 `E:\ViCELLXR` 根目录下 15 个文件
  （`AuditTrail.txt`、`Users.txt`、`CellTypes.txt`、`ViabilityDef.cfg`、`*.ppr` 等，几十 KB）。
  **不进它的 `Data\`/`Excel\` 子目录**——那是搬家前的旧导出，已被现用目录完整包含。
- 样品目录型的历史源**补一趟根部平铺扫描**：这些人工归拢的目录根上偶尔散着零星文件
  （实测 `E:\1111` 有 1 个 `.xls`），只扫目录会把它们静默丢掉。
- 新增 `--no-legacy`；`detect_deleted()` 覆盖全部新来源，图片按"任一来源还在即不算消失"判定。
- ⚠️ **Windows 的「创建时间」保不住**：CIFS 不提供该字段（`stat` 显示的 `Birth` 是把 mtime
  填进去的假值，`statx` 返回 `None`），且 Linux 没有设置它的接口。换哪个源都一样。
  修改时间可以完整保留（v1.0.0 已实现），真实生成时间另有文件内部的 `FileDate` 可依。

## vicell_ingest.py — v1.0.0 (2026-08-03)

**新增第二台仪器：Beckman Vi-CELL XR（工作站 `C4V61257XH` = `10.0.13.36`）。**

- 新增 `vicell/vicell_ingest.py` + `vicell/vicell-ingest.env.example`。沿用 FLEX2 的全部语义：
  只读源自验、state JSON、`Checksums/<机器名>/*_SHA256_Compare_*.csv`、原子写入、SHA256 双向校验。
- 归档三类：`Data/*.txt`+`*.ctl`、`Export/*.xls`、`Images/<SampleID>/*.tif`。
  落到 NAS 既有目录 `Daily/C4V61257XH_ViCell/{data,export,images}`（沿用已存在的小写子目录名）。
- **`Data` 与 `Export` 时间段互补，必须都抓**：实测 `Export` 覆盖 2021-08→2025-09 与 2026-03→今，
  `Data` 覆盖 2024-12→今；2025-10…2026-02 五个月源头就只有 `.txt` 没有 `.xls`
  （已比对旧导出目录 `E:\ViCELLXR\Excel`，同样缺，属操作/设置问题而非文件丢失）。
- **图片增量只比对目录名单**：样品图片目录一旦生成即不再变，已归档的目录不再打开，
  不重扫、不重算哈希。⚠️ 判断"新目录"只能靠目录名——实测目录 mtime 被 2026-07 那次
  搬文件夹整体刷掉了，完全不可信。
- `--dry-run` 不读文件内容，只按文件名/大小出清单（否则首跑要经 SMB 拉 1.1 GB 才肯出结果）。
- 单文件校验不过即删除坏副本且不记账，下次重跑（铁律 5）；图片目录未完整复制则整目录不记账。
- 源文件视为 immutable：同名文件内容变化 → 告警并另存 `.rev<时间戳>` 版本快照，绝不覆盖底本。
- **归档副本保留源文件的修改时间**（`write_atomic(..., mtime=)`，在 rename 前 `os.utime` 保证原子）。
  实测 Vi-CELL 样品文件的修改时间 == 文件内部 `FileDate`（抽查四个文件，含 2025 年的，秒级一致），
  是有溯源价值的元数据；不带过去会让归档副本统统显示成"归档那天"。
  首跑（2026-08-03）用的是不带此修复的版本，已用一次性脚本 `fix_mtime.py` 补正。
- 连接注意：该工作站是 Win7，**只支持 SMB 2.1**，挂载必须 `vers=2.1`（`vers=3.0` 会
  `mount error(95) Operation not supported`）。

## 部署变更 — 采集频次 1 次/天 → 3 次/天 (2026-07-23)

**无代码改动**（`flex2_ingest.py` 仍为 v1.2.0），仅调整 systemd timer 触发时刻。

- `flex2-ingest.timer` 由单一 `OnCalendar=*-*-* 01:00:00` 增加为 01:00 / 12:00 / 16:00 三个时刻。
  01:00 那趟仍是抓 Nova 23:30 数据库备份的主趟；白天两趟主要缩短当天月度 CSV 落到 NAS 的延迟。
- 脚本本身是增量+SHA256 比对，内容没变化只记 `unchanged` 不重复写快照，加跑无副作用。
- Linux 侧改的是 `/etc/systemd/system/flex2-ingest.timer`（原文件备份为 `.bak-20260723`），
  文档同步见 `docs/SETUP.md` §5。

## flex2_ingest.py — v1.2.0 (2026-07-16)

**放宽归档层校验：忠实保存底本优先（实机 dry-run 发现月度文件普遍"同一文件多种行宽"）。**

- 背景：首次实机 dry-run 发现 19 个月度文件里 12 个含"多种行宽"——某些样品未测的通道
  未留空占位、直接省略，使该行变短（套餐化、非随机，非损坏）。v1.1.0 的"每行列数必须等于
  表头"会把这些**完好数据**判为失败拒收，导致主数据源大量归档不了。
- `validate_csv` 改为只判"文件完整可读"（UTF-8 可解码、CSV 可解析、非空、有数据行）；
  遇到 多行宽 / 行宽≠表头 / 带 BOM → **告警但照常归档**（守铁律 1，不静默吞），
  交 Stage 2 按行宽分套餐解析。只有真损坏（非 UTF-8 / 无法解析 / 空 / 只有表头）才拒收（铁律 5）。
  返回值由 3 元组扩为 4 元组（增加告警字段）；月度调用点新增 WARNING 分支、逐次调用点新增 info 提示。
- 同步更新 CLAUDE.md 铁律 1/5 措辞，待办新增"问 Nova：导出能否让未测通道留空占位（治本）"。

## flex2_ingest.py — v1.1.0 (2026-07-15)

**全面对齐 NAS 既有多设备备份约定（实地核对 ViCell / Biacore 现状后确定）。无采集/校验算法改动。**

- 数据归档根由 `Raw/FLEX2_<AID>/` 改为 `Daily/<机器名>/`，机器名默认 `T281240040C_Nova`
  （与 NAS 侧预建目录及其它设备 `Daily/<机器名>/` 命名一致）。
- 数据文件夹镜像仪器 `Export/`：月度快照+逐次冷备 → `Results/`（`Monthly/`、`PerEvent/`），
  数据库备份 → `Database/`；`Report/` 预建但不写（人工 PDF，按铁律忽略）。
- 记账目录放 NAS 根级、按机器名分（与其它设备完全一致，不再塞进数据目录）：
  `Checksums/<机器名>/`、`Logs/<机器名>/`、`State/<机器名>_backup_state.json`。
- 校验记录由"单个只追加 manifest.csv"改为**每次运行一个** `_SHA256_Compare_<版本>_<时间戳>.csv`，
  列与其它设备一致（`Relative_Path, Local_Path, NAS_Path, Change_Type, Local_Size, Local_MTime,
  Local_SHA256, NAS_SHA256, match_status`）；空跑也留只含表头的文件（证明当天跑过）。
- NAS 挂载点默认值 `/mnt/nas/TTLab_Backups` → `/mnt/ttlab-backups`；
  写账户明确为 `backupuser`（不复用只读的 `etl_reader`）。

## flex2_ingest.py — v1.0.0 (2026-07-15)

**首个交付版本（Stage 1 采集与校验）。尚未实机跑过。**

- 三类数据源采集：月度 CSV 快照（主）、Database 每日备份（保险）、逐次 CSV 冷备（`--per-event`，默认关）。
- 只读源自验（能写入即中止）、SHA-256 双向校验（源哈希 vs 回读哈希）、临时文件 + rename 原子写入。
- CSV 结构校验（UTF-8、无 BOM、列数一致；按列名映射的理念，绝不按列位置）。
- 月度文件行数回退告警（`last_data_rows` 变少 = 历史可能被改写）。
- 健康信号取自 Database 备份新鲜度（不用"样品数据陈旧"，避免停机误报）。
- 归档清单 `manifest.csv`（只追加，审计记录）、`state.json` 断点续传、本地状态副本兜底。
- 仅依赖 Python 标准库。
