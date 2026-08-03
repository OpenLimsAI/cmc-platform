# 数据完整性技术审计报告 — `cmc-instrument-ingest`

| | |
|---|---|
| 审计日期 | 2026-08-03 |
| 审计范围 | Stage 1 采集归档程序（`flex2_ingest.py` v1.2.0、`vicell_ingest.py` v1.2.1）及其 NAS 产出物 |
| 审计依据 | FDA Data Integrity and Compliance with Drug CGMP (2018)、EMA GMP Annex 11、ALCOA+ |
| 方法 | 逐行代码审阅 + Linux/NAS 实际产出物取证 + 源端 SMB 协议实测 |
| 声明 | 所有结论均有代码行号或实测输出支撑；无证据处明确标注"需进一步确认" |

> **本报告为技术审计，不构成合规放行意见。** 正式 GxP 认定需 QA 与法规事务参与。

---

## Executive Summary

**当前成熟度：Medium（偏下）**

作为**技术性文件备份系统**，本系统实现质量高于同类内部脚本的平均水平：只读源保护、
SHA-256 双向校验、原子写入、append-only、增量记账、失败不记账重试等机制均**已在代码中真实实现**，
并在 2026-08-03 的实跑中被验证有效（55713 行校验全 `MATCH`；且成功保留了 3 个源端已删除样品）。

但作为**面向 FDA/EMA 检查的电子记录归档系统**，存在结构性缺口，主要为三类：

1. **元数据采集不完整**：Windows `CreationTime`、NTFS 属性、访问时间、属主/ACL 全部未采集。
   **关键发现：这些并非不可获取**——SMB 协议本身传输这些字段，实测 `smbclient allinfo`
   可完整读出（见 MD-001）。当前是"可采集而未采集"，属可避免的丢失。
2. **元数据无权威存储**：不存在数据库。元数据分散在 per-run CSV、state JSON 与日志文本中，
   三者结构不一、无外键、无法联表查询，且**归档侧 hash 仅存在于 per-run CSV**，
   该文件丢失即无法证明归档完整性。
3. **闭环缺失**：无恢复验证、无"任务未执行"检测、告警通道未配置（`ALERT_CMD` 为空
   ⇒ 所有 CRITICAL 告警实际无人可见）。

**结论**：数据大概率是完好的，但**证明其完好的证据链不足以支撑一次 FDA 检查**。

---

## Findings

### MD-001 — Windows CreationTime 可获取但未采集 · **Risk: High**

**证据**

- 挂载后 `os.stat()` 拿不到：`statx` 的 `st_birthtime` 返回 `None`；`stat` 命令显示的
  `Birth:` 字段是 CIFS 用 mtime 伪造的（实测 `Birth == Modify`，两者逐秒相同）。
- **但 SMB 协议层有**。实测 `smbclient allinfo`：
  ```
  D:\Vi-Cell 计数图像\0005m10\0005m10_10.tif（原始位置）
      create_time: Tue Jun 23 15:38:03 2026     ← 原始创建时间完好
      write_time : Tue Jun 23 15:38:03 2026
      attributes : A (20)                       ← NTFS 属性也可读

  E:\Vi-Cell\Images\0005m10\0005m10_10.tif（人工拷贝）
      create_time: Tue Jul  7 19:23:41 2026     ← 被重置为拷贝日
      write_time : Tue Jun 23 15:38:03 2026
  ```
- 代码中无任何一处读取或记录 create time（`grep -rniE "creat|birthtime" flex2 vicell` 无业务命中）。

**三层原因分离（对应审计问题 1.2）**

| 可能原因 | 是否成立 | 说明 |
|---|---|---|
| Linux 文件系统限制 | **部分成立** | Linux 无"设置"创建时间的系统调用 ⇒ **目标副本无法带上该字段**，这一点无解 |
| Python 复制方法导致 | **不成立** | 换 `shutil.copy2` 也一样——`copy2` 只复制 mtime/atime/mode，从不处理 birth time |
| SMB/挂载方式导致 | **成立且可解** | Linux cifs 客户端不把 SMB2 `CreationTime` 映射到 `statx`；**但绕过挂载、直接用 SMB 查询即可取得** |

**Impact**：无法回答"该文件在源盘上何时被创建"。在本项目场景下影响被两点削弱：
① 文件内部自带 `LogDate`/`RunDate`/`FileDate`（业务权威时间）；② `write_time` 已保留。
但检查员若问"你如何证明这份副本对应的原始文件从未被替换过"，缺少 create_time 会削弱论证。

**Recommendation**
1. 采集端增加 SMB 元数据抓取（`smbclient allinfo` 或 Python `smbprotocol` 库），
   记录 `create_time` / `access_time` / `change_time` / `attributes` 到元数据库。
   **不追求在 NAS 副本上还原该字段**（技术上不可能），改为"作为元数据永久记录"。
2. **时效性提醒**：本次图片回补正从 D 盘原始位置取数，该位置 create_time 完好。
   建议在源端目录被清理前补采一次元数据快照，过期即永久失去。

---

### MD-002 — 无元数据数据库，元数据分散且不可重建 · **Risk: High**

**证据**

- 全仓库无数据库代码：`grep -rniE "psycopg|sqlalchemy|sqlite|postgres" flex2 vicell` → **零命中**。
- 元数据实际分布在三处，结构互不相同：

  | 载体 | 内容 | 问题 |
  |---|---|---|
  | `Checksums/<机器>/*_SHA256_Compare_*.csv` | 唯一记录 **NAS 侧 hash** 的地方 | 每次运行一个文件（FLEX2 已 47 个、Vi-CELL 11 个），无索引，丢一个即该批次归档 hash 永久不可考 |
  | `State/<机器>_backup_state.json` | 增量记账 | **只有源 hash**；Vi-CELL 图片类连源 hash 都没有，仅 `{tif_count, source, archived_at}` |
  | `Logs/<机器>/*.log` | 失败、删除、告警 | 纯文本，无结构，仅靠 grep |

- 两台仪器的 state schema **不同**（实测顶层键）：
  - FLEX2：`monthly / per_event / database / stats_* / last_status …`
  - Vi-CELL：`data_files / export_files / config_files / image_dirs / legacy::<名> …`

**Impact**：无法用一条查询回答"某文件的完整备份履历"。检查场景下需要人工跨 CSV/JSON/日志拼接，
且拼不出图片类文件的源 hash。

**Recommendation**：建立 PostgreSQL 元数据库（见文末架构建议）。

---

### MD-003 — 无恢复验证（Restore Verification） · **Risk: High**

**证据**：`grep -rniE "restore" flex2 vicell` → 零命中。无任何"从 NAS 取回并验证可用"的流程或记录。

**Impact**：检查员的标准问题"How do you know your backup can be restored?"目前**无法回答**。
未验证过恢复的备份，在 GxP 语境下不被承认为有效备份。

**Recommendation**：建立周期性恢复演练（建议每半年）：随机抽 10 个文件取回 → 校验 SHA 与记录一致 →
用实际软件打开确认可读 → 记录演练结果、执行人、日期。演练记录本身是关键证据。

---

### MD-004 — 告警通道未配置，所有 CRITICAL 告警实际无人可见 · **Risk: High**

**证据**：`/etc/instrument-ingest/vicell-ingest.env` 中 `VICELL_ALERT_CMD=`（空）。
代码 `alert()`（`vicell_ingest.py:176-183`）在未配置时仅 `logger.error` 后 `return`。

**Impact**：SHA 不一致、源挂载可写、归档写入失败等最高级别事件，**只写进日志文件**。
系统"有告警机制"但"告警到不了人"，这在审计中比没有告警更糟——因为它给出虚假保证。

**Recommendation**：接企业微信/邮件；并把"告警通道可用性"纳入定期确认（发一条测试告警并留证）。

---

### MD-005 — 无"任务未执行"检测（dead man's switch） · **Risk: High**

**证据**：系统仅在**运行时**产生日志与告警。若 timer 被禁用、服务启动失败、凭据过期或机器重装，
程序一次都不执行，**不产生任何信号**。且按设计（`CLAUDE.md` 铁律 4）明确不使用"业务数据陈旧"告警。

**Impact**：备份静默停止是备份系统最经典的失效模式，当前无任何检测。

**Recommendation**：独立于采集脚本的每日巡检任务，扫描全部 `State/*.json` 的 `last_run`，
超过"正常频次 × 3"即告警。必须独立——脚本没跑时它自己不会上报。

---

### MD-006 — 失败与删除事件无结构化持久记录 · **Risk: Medium**

**证据**

- 源端删除检测（`vicell_ingest.py:568-605` `detect_deleted`）只 `alert("WARN", …)` + `logger.warning`，
  **不写入任何结构化记录**。
- 失败项同样只进日志。实跑已发生一例：
  `2026-08-03 18:00:27 ALERT[WARN] 图片归档失败: 009-R2505-D7/009-R2505-D7_34.tif ([Errno 5] I/O error)`
  ——事后复测该文件可正常读取三次，属源端偶发抖动；但这一"曾经失败并已重试成功"的事实
  **仅存在于日志文本中**，无结构化留痕。

**Impact**：无法系统性回答"历史上有多少次备份失败、分别是什么原因、是否都已补救"。

**Recommendation**：`backup_event` 表记录 FAILED / RETRIED / SOURCE_DELETED / CHANGED 事件。

---

### MD-007 — NAS 侧 hash 仅存于 per-run CSV；图片类无持久源 hash · **Risk: Medium**

**证据**：`state["image_dirs"]` 实测样例为
`{"0005m10": {"archived_at": "...", "source": "/mnt/vicell-old/dimg", "tif_count": 50}}` —— **无 hash**。
图片的逐文件 hash 只写进当次的 Compare CSV。

**Impact**：Vi-CELL 图片共约 13 万个文件，其 hash 分散在数十个 CSV 中，无索引。
做 bit-rot 复核时无法高效取得基线值。

**Recommendation**：hash registry 入库（见架构建议）。

---

### MD-008 — 缺 backup_job_id / 执行账户 / 源主机 / 源 OS 的结构化记录 · **Risk: Medium**

**证据**：Compare CSV 表头实测为
`Relative_Path, Local_Path, NAS_Path, Change_Type, Local_Size, Local_MTime, Local_SHA256, NAS_SHA256, match_status`
—— 无 job id、无执行账户、无源主机、无 OS、无 hash 计算时刻。
运行标识仅体现在**文件名**里的时间戳（`..._v1_2_1_20260803_191246.csv`），非字段。

部分可推断：源主机可由 `MACHINE_NAME` 与路径推断；执行账户可由系统配置推断为 `flex2ingest`。
但**均未写入记录本身**，属"可推断"而非"可举证"。

**Recommendation**：所有事实字段显式入库，不依赖路径约定或文件名。

---

### MD-009 — 跨仪器元数据模型不一致 · **Risk: Medium**

**证据**（NAS `Checksums/` 实测表头）

| 机器 | 表头 | 摘要算法 |
|---|---|---|
| `T281240040C_Nova`（本程序） | 9 列标准 | SHA-256 |
| `C4V61257XH_ViCell`（本程序） | 9 列标准 | SHA-256 |
| `CZC1079M4B_Biacore`（历史脚本） | 9 列标准 | SHA-256 |
| `PBXYXD3_XEVOG2S`（历史脚本） | **6 列，`Local_MD5/NAS_MD5`** | **MD5** |
| `P509W57K_AVANT` | **无比对表** | **无** |

**Impact**：审计范围内的仪器群不满足 ALCOA+ 的 Consistent。MD5 已不适合完整性举证；
AVANT 无任何校验记录。

**Recommendation**：统一到本程序的模型；历史脚本纳入迁移计划。
注：`Empower / UNICORN / Lucullus` 未在本次审计范围内出现，**其现状不确定，需进一步确认**。

---

### MD-010 — atime / NTFS 属性 / ACL / 属主 未采集 · **Risk: Medium**

**证据**：代码中无 `st_atime` / `st_uid` / `st_mode` / xattr 相关处理（grep 零命中）。
NAS 挂载以 `uid=flex2ingest,gid=flex2ingest,file_mode=0755` 固定，**归档副本的属主与权限
一律是挂载参数决定的，与源端无关**。

同 MD-001，`attributes: A (20)` 等 NTFS 属性经 SMB 可读但未采集。

**Recommendation**：作为元数据采集（不追求在副本上还原）。ACL 是否需要留待 QA 判断——
本系统定位为"分析数据源 + 业务备份"而非 Part 11 记录系统，ACL 可能非必需，**需确认**。

---

### MD-011 — 归档区可被写账户删除/加密，无 WORM 或快照确认 · **Risk: Medium**

**证据**：NAS 以 `backupuser` 读写挂载（`rw`）。可写即可删。
NAS 侧是否启用快照/版本保留/WORM —— **不确定，需向 IT 确认**。

**Impact**：勒索软件或脚本缺陷可在一次操作中破坏全部归档；`append-only` 是**程序层自律**，
非存储层强制。

**Recommendation**：NAS 侧启用快照或对归档目录启用一次写入不可改；确认是否存在异地/离线副本。

---

### MD-012 — FLEX2 归档未保留源文件修改时间 · **Risk: Low**

**证据**：`flex2_ingest.py:315-341` `archive_bytes()` 无 `os.utime` 调用。
Vi-CELL 已在 v1.2.1 修复（`vicell_ingest.py:281-290`）。

**缓解**：FLEX2 归档文件名内嵌运行时间戳（`..._snap_<RUN_TAG>.csv`），且源 mtime 记录在
Compare CSV 的 `Local_MTime` 列。故信息未丢失，仅副本 mtime 不等于源 mtime。

**Recommendation**：将 v1.2.1 的修复回移到 FLEX2，保持两台一致。
**注意实现细节**：本次实测发现，该 NAS 的 CIFS 上 `rename` 会重置 mtime，
`utime` 必须在 `os.replace` **之后**执行——先设后改名等于白设。

---

### MD-013 — 时间戳无时区标注 · **Risk: Low**

**证据**：`NOW_STR = RUN_DT.strftime("%Y-%m-%d %H:%M:%S")`（本地时间，无时区）；
`fmt_mtime()` 同。跨时区检查或夏令时变更时存在歧义。

**Recommendation**：记录 ISO-8601 带时区（`2026-08-03T19:12:46+08:00`）或统一存 UTC。

---

### MD-014 — 无归档侧定期完整性复核自动化 · **Risk: Low**

**证据**：已于本次审计期间新增 `vicell/vicell_verify.py`（只读核对工具，支持抽样重算 SHA
与时间戳比对），但**尚未纳入定期任务**，且 FLEX2 无对应工具。

**Recommendation**：纳入季度巡检并留存报告。

---

### MD-015 — 代码卫生 · **Risk: Low**

`vicell_ingest.py:35` `import shutil` 未被使用（grep 仅命中该 import 行）。建议移除。

---

### 流程类观察（非代码缺陷，但影响检查结论）

- **无正式验证文档**（IQ/OQ/PQ 或等效的确认记录）。当前 `CHANGELOG.md` + git 历史构成事实上的
  变更记录，质量较好，但未经 QA 签署。
- **`instrument_reader` 密码于 2026-08-03 因截图外泄，尚未轮换**（已记入待办）。
- 源仪器为 **Windows 7**（微软 2020 年终止支持）+ SMB 2.1，属受支持性风险。

---

## Gap Assessment Table

| Area | Current Status | Risk | Recommendation |
|---|---|---|---|
| Windows CreationTime | 未采集；但经 SMB **可获取**（实测） | High | 采集为元数据入库；副本上无法还原属技术限制，如实说明 |
| 元数据存储 | 无数据库；CSV+JSON+日志三处分散、schema 不一 | High | 建 `backup_file_inventory` 等表，见架构建议 |
| 恢复验证 | 完全没有 | High | 每半年恢复演练 + 留证 |
| 告警送达 | `ALERT_CMD` 为空，告警只进日志 | High | 接通知渠道并定期验证可达 |
| 任务未执行检测 | 无 | High | 独立心跳巡检 `State/*.json` 的 `last_run` |
| 失败/删除事件留痕 | 仅日志文本 | Medium | `backup_event` 表结构化记录 |
| Hash registry | NAS hash 仅在 per-run CSV；图片无持久源 hash | Medium | hash 入库，CSV 降级为导出物 |
| Job / 账户 / 主机 / OS | 未入记录，仅可推断 | Medium | 显式字段入库 |
| 跨仪器一致性 | XEVOG2S 用 MD5、AVANT 无校验 | Medium | 统一模型，历史脚本纳入迁移 |
| atime / NTFS 属性 / ACL / 属主 | 未采集；副本权限由挂载参数决定 | Medium | 采集为元数据；ACL 必要性待 QA 确认 |
| 归档区防篡改 | 程序层 append-only；存储层可写可删 | Medium | NAS 快照 / WORM；确认异地副本 |
| 源 mtime 保留 | Vi-CELL 已保留；**FLEX2 未保留** | Low | 回移修复（注意 utime 必须在 rename 之后） |
| 时区 | 本地时间无时区标注 | Low | 改 ISO-8601 带时区或 UTC |
| bit-rot 定期复核 | 有工具，未定期化 | Low | 季度巡检 + 报告留存 |
| 只读源保护 | **已实现且实测有效** | — | 保持 |
| SHA-256 双向校验 | **已实现且实测有效**（55713 行全 MATCH） | — | 保持 |
| 原子写入 | **已实现**（tmp + `os.replace` + `fsync`） | — | 保持 |
| append-only / 不覆盖底本 | **已实现**（变化另存 `.rev<ts>`） | — | 保持 |
| 幂等与断点续跑 | **已实现且实测有效** | — | 保持 |

---

## Metadata 保留逐项核对（审计问题 1）

| 字段 | 是否采集 | 是否保存 | 是否验证 | 证据 |
|---|---|---|---|---|
| File name | ✅ | ✅ | ✅ | Compare CSV `Relative_Path`；归档同名 |
| Full original path | ✅ | ✅ | — | Compare CSV `Local_Path`（实测含完整源路径） |
| File extension | ✅ | ✅ | — | 含于文件名 |
| File size | ✅ | ✅ | ✅ | `Local_Size`；state `size` |
| **Creation time** | ❌ | ❌ | ❌ | **可获取未采集，见 MD-001** |
| Last modified time | ✅ | ✅ | ⚠️ | `Local_MTime`；Vi-CELL 副本已还原，FLEX2 未还原（MD-012） |
| Last access time | ❌ | ❌ | ❌ | 可经 SMB 获取，未采集 |
| File attributes (NTFS) | ❌ | ❌ | ❌ | `smbclient allinfo` 可得 `attributes: A (20)`，未采集 |
| File permissions / ACL | ❌ | ❌ | ❌ | 副本权限由挂载 `file_mode=0755` 决定 |
| Owner / user | ❌ | ❌ | ❌ | 未采集 |
| Source workstation | ⚠️ | ⚠️ | — | 仅体现在 `MACHINE_NAME` 与路径，非字段 |
| Source OS | ❌ | ❌ | ❌ | 未记录（实测为 Windows 7 / SMB 2.1） |
| Original filesystem (NTFS) | ❌ | ❌ | ❌ | 未记录 |

---

## ALCOA+ 逐项评估

| 原则 | 评级 | 依据 |
|---|---|---|
| **Attributable** | ⚠️ 部分 | 可答：来自哪台工作站、哪个路径、何时采集（Compare CSV + 日志）。**不可结构化举证**：backup_job_id、执行账户、源 OS。见 MD-008 |
| **Legible** | ✅ 良好 | UTF-8 CSV（带 BOM）+ JSON + 纯文本日志，全部开放格式、无二进制专有格式，十年后仍可读 |
| **Contemporaneous** | ⚠️ 部分 | 有采集执行时刻（日志/文件名时间戳）与源文件 mtime。**缺**"文件被发现的时刻"与"hash 计算时刻"独立字段；且时间无时区（MD-013） |
| **Original** | ✅ 良好 | 全程按字节复制，不解析、不改写；`validate_csv` 只判断可读性不修改内容；结构异常只告警照常归档（铁律 5）。**唯一原始性损失是 create_time 未随行**（MD-001） |
| **Accurate** | ✅ 良好 | 源 hash 对内存字节计算 → 原子写入 → **回读 NAS 重算** → 比对；不一致即删除坏副本、不记账、告警。实测 55713 行全 `MATCH`。**弱点**：hash 计算时刻未记录，NAS hash 仅存 CSV（MD-007） |
| **Complete** | ⚠️ 部分 | 变化留痕（`.rev<ts>` + `last_data_rows` 减少告警）设计良好；**但**删除、失败事件仅在日志文本（MD-006） |
| **Consistent** | ❌ 不足 | 两台在用仪器 state schema 不同；机群内 XEVOG2S 用 MD5、AVANT 无校验（MD-009） |
| **Enduring** | ✅ 良好 | 纯文本 + 开放格式，NAS 剩余 60 T，容量非近期约束。**风险在存储层**：无 WORM/快照确认（MD-011） |
| **Available** | ⚠️ 部分 | 文件本身可立即取出；**但"备份履历"需人工跨 CSV/JSON/日志拼接**，图片类源 hash 拼不出（MD-002/007） |

---

## Backup Architecture Review（审计问题 3）

**当前架构**：`Windows Instrument PC —(SMB, ro pull)→ Linux cmc-instrument-ingest —(SMB, rw)→ NAS`

### Pull 模式风险评估

| 风险项 | 实测结论 |
|---|---|
| Linux 访问 Windows 共享是否可靠 | **基本可靠但有抖动**。实跑 13 万文件中出现 1 次 `[Errno 5] I/O error`，复测该文件三次均成功 ⇒ 源端负载抖动，非文件损坏。程序处理正确（整目录不记账、下批重试） |
| 权限问题 | **已正确收口**。`instrument_reader` 实测对 `C$`/`ADMIN$`/`D$`/`E$` 全部 `NT_STATUS_ACCESS_DENIED`，仅授权共享可读 |
| 是否可能漏文件 | **低**。按文件名全量比对而非依赖 mtime/事件；已知边界：`archive_sample_dirs` 只扫一层子目录，故对"样品目录根部散落文件"曾有盲区，v1.1.0 已补平铺扫描（实测捞回 `E:\1111` 根部 1 个 xls） |
| 是否可能重复备份 | **不会**。state 按名+大小跳过；实测二次运行 4 秒完成、新增 0 |
| 增量备份 | ✅ state JSON 驱动 |
| 全量备份 | ✅ `--backfill`（FLEX2）/ 清空 state 即全量重跑（Vi-CELL） |
| 重试机制 | ⚠️ **部分**。`read_source_stable` 有 4 次读取重试；批次级失败靠"不记账 ⇒ 下次自然重试"。**无失败项显式重试队列** |
| 失败通知 | ❌ `ALERT_CMD` 未配置（MD-004） |
| 日志 | ✅ 每次运行独立日志（FLEX2 已 51 个），落 NAS |

### 架构性观察

- **Pull 模式本身适合 GxP**：仪器侧零安装、只读、不改变仪器状态，验证负担低。建议保持。
- **Linux 中转节点是单点**：其 `/var/lib/*-ingest` 本地 state 副本与 NAS 副本互为备份，设计正确。
- **源端为 Win7 + SMB 2.1**：受支持性风险，应纳入风险登记册。

---

## File Copy Method Review（审计问题 5）

**实际实现：手写字节复制，非 `shutil`。**

```
读取：read_source_stable() → open(rb).read()      # 全量读入内存 + 前后 stat 稳定性校验
写入：open(wb).write() → flush() → os.fsync()      # 落盘
      → os.replace(tmp, dest)                      # 原子改名
      → os.utime(dest, (mtime, mtime))             # 仅 Vi-CELL v1.2.1+
```

代码位置：`flex2_ingest.py:315-341`、`vicell_ingest.py:266-296`。
`shutil` 在 Vi-CELL 中虽 import 但未使用（MD-015）。

| 方法 | mtime | create time | 权限 | 扩展属性 | 评价 |
|---|---|---|---|---|---|
| **当前实现** | ✅（Vi-CELL）/ ❌（FLEX2） | ❌ | ❌ | ❌ | 可控性最好：能插入 hash 校验与原子写入 |
| `shutil.copy` | ❌ | ❌ | ✅(mode) | ❌ | 不如当前 |
| `shutil.copy2` | ✅ | ❌ | ✅(mode) | 尽力而为 | **仍不解决 create time** |
| `rsync` | ✅ | ❌ | ✅ | ✅(`-X`) | 快，但不便嵌入双向 hash 校验 |
| `robocopy`（Windows 侧） | ✅ | ✅ | ✅ | ✅ | **唯一能保住 create time 的路径**，但需在仪器 PC 上运行 ⇒ 推翻 pull 架构，不建议 |

**结论**：当前方法的选择是合理的；`create_time` 不能保留**不是**方法选择造成的（见 MD-001 三层原因分离）。

---

## Hash Verification Review（审计问题 6）

| 要求 | 实现情况 | 证据 |
|---|---|---|
| 复制前计算源 hash | ✅ 对**内存中的字节**计算，非二次读源 | `vicell_ingest.py` `_copy_one`；`flex2_ingest.py:320` |
| 复制后重新计算 | ✅ **回读 NAS 文件**重算，非复用内存值 | `flex2_ingest.py:340` 注释明确"回读，不是复用内存里的 h1" |
| 比对与处置 | ✅ 不一致 ⇒ 删除坏副本 + 不写 state + CRITICAL 告警 ⇒ 下次重来 | `vicell_ingest.py` `_copy_one` 返回 `"SHA256 不一致"` 分支 |
| 结果永久保存 | ⚠️ 仅在 per-run Compare CSV（`Local_SHA256`/`NAS_SHA256`/`match_status`） | 见 MD-007 |
| hash 计算时刻 | ❌ 未记录 | Compare CSV 无该列 |
| 文件变化后重算 | ✅ 内容变化 ⇒ 另存 `.rev<ts>` + 重新 hash + 告警，不覆盖底本 | `archive_flat_dir` CHANGED 分支 |
| 算法 | ✅ SHA-256（历史脚本 XEVOG2S 仍为 MD5，见 MD-009） | 实测表头 |

**评价**：hash 校验的**逻辑链条是完整且正确的**，是本系统最强的一环。缺口在"结果如何长期、可查询地保存"。

---

## FDA Inspection Scenario Simulation（审计问题 7）

> Inspector: *"Please demonstrate that your electronic records backup maintains data integrity."*

| # | 要求 | 现状 | 说明 |
|---|---|---|---|
| 1 | Original file | ✅ 可 | 仪器工作站上可查（只读共享） |
| 2 | Backup copy | ✅ 可 | NAS `Daily/<机器名>/…`，结构镜像源端，可即时取出 |
| 3 | Original metadata | ⚠️ 部分 | 文件名/路径/大小/mtime 有；**create time、NTFS 属性、属主无**（MD-001/010） |
| 4 | Backup timestamp | ✅ 可 | 日志 + Compare CSV 文件名时间戳 + state `archived_at` |
| 5 | Hash verification | ⚠️ 可但费力 | 值在 per-run CSV 中，需人工定位是哪一次运行归档的；图片类尤其难查（MD-007） |
| 6 | Backup execution log | ✅ 可 | 每次运行独立日志落 NAS（FLEX2 已 51 个） |
| 7 | Restore verification | ❌ **不可** | 从未做过（MD-003） |

**模拟结论**：能出示数据与执行日志，**但在第 3、5、7 项上会被追问**。
第 7 项（恢复验证）是**最可能导致观察项（observation）的单点**——它无法靠现有记录补救，
只能靠今后建立演练制度并积累记录。

**当前若被检查，最有力的三项证据**：
① 55713 行 SHA-256 比对全 `MATCH` 的机器可读记录；
② 3 个源端已删除样品仍完好保存在归档区，证明 append-only 真实有效；
③ 完整的变更记录（`CHANGELOG.md` + git 历史），含缺陷发现与修复过程（如 rename 冲掉时间戳的修复）。

---

## Recommended Future Architecture

```
Windows Instrument PC (SMB, read-only share)
        │
        │  ① 文件字节         ② SMB 元数据（create/access/change time、NTFS attributes）
        ▼
Linux  cmc-instrument-ingest
        │
        ├──③ 元数据 + hash ──►  PostgreSQL（元数据库）
        │                        backup_file_inventory / backup_job / backup_event / restore_drill
        │
        └──④ 文件字节 ──────►  NAS Archive（底本，append-only + WORM/快照）
                                 Checksums/ 降级为"导出物"，权威值在库里
```

### 需要新增的五个组件

**1. Metadata Collector（新）** — 采集 SMB 层元数据

补上 MD-001/010 的缺口。用 `smbclient allinfo` 或 Python `smbprotocol` 读取
`create_time / access_time / change_time / attributes`，与文件字节同批采集。

**2. 元数据库（新）** — 建议置于 `cmc_analytics`

> ⚠️ **归属需负责人确认**：按 `~/code/CLAUDE.md` 总纲，`cmc_rd` 为原始层只放 raw+meta，
> 分析结果入 `cmc_analytics`。本表属"运维元数据"，两边都不完全贴合，
> 按总纲 §9 准入清单应**先问负责人**，不自行决定。

```sql
-- 建议：cmc_analytics.ops.backup_file_inventory
id                    bigserial primary key
backup_job_id         bigint  references ops.backup_job(id)
source_system         text    -- 'vicell' / 'flex2'
instrument_name       text    -- 'C4V61257XH_ViCell'
source_host           text    -- 'C4V61257XH'
source_os             text    -- 'Windows 7 / SMB 2.1'
source_share          text    -- '//10.0.13.36/VC-DImg$'
source_path           text    -- 完整原始路径
file_name             text
file_ext              text
file_size             bigint
creation_time_original    timestamptz   -- ← MD-001 补上
modified_time_original    timestamptz
access_time_original      timestamptz
file_attributes           text          -- NTFS 属性，如 'A'
backup_time           timestamptz
backup_location       text
sha256_original       char(64)
sha256_backup         char(64)
hash_computed_at      timestamptz       -- ← 补上 hash 计算时刻
verification_status   text              -- MATCH / MISMATCH / PENDING
software_version      text              -- 'vicell_ingest v1.2.1'
service_account       text              -- 'flex2ingest'
created_at            timestamptz default now()

unique (instrument_name, source_path, sha256_original)
```

配套三张表：
- `ops.backup_job` — 每次运行一行：job_id、开始/结束、参数、汇总计数、退出码、执行账户
- `ops.backup_event` — FAILED / RETRIED / SOURCE_DELETED / CONTENT_CHANGED，补 MD-006
- `ops.restore_drill` — 恢复演练记录：日期、抽样清单、校验结果、执行人，补 MD-003

**3. Hash Registry** — 即 inventory 表中的 `sha256_*` 字段；
Compare CSV 保留但降级为人可读导出物，权威值在库。

**4. Audit Log** — `backup_job` + `backup_event` 即构成审计轨迹；
库表只增不改（触发器禁 UPDATE/DELETE），与归档区 append-only 对齐。

**5. Restore Verification** — 定期作业：随机抽样取回 → 校验 SHA → 打开确认 → 写 `restore_drill`。

### 与当前设计的差距对照

| 维度 | 当前 | 建议 | 差距 |
|---|---|---|---|
| 存储 | CSV + JSON + 日志，三处分散 | 单一 PostgreSQL，四表关联 | **大** |
| 查询 | 人工 grep / 跨文件拼接 | 一条 SQL 出完整履历 | **大** |
| create/access time、NTFS 属性 | 无 | 有 | **大** |
| job / 账户 / 主机 / OS | 可推断不可举证 | 显式字段 | 中 |
| hash 时刻 | 无 | 有 | 中 |
| 失败/删除事件 | 日志文本 | 结构化表 | 中 |
| 恢复演练 | 无 | 有表有制度 | **大** |
| 文件本体与校验逻辑 | **已达标** | 不变 | 无 |

### 实施优先级建议

| 优先级 | 事项 | 理由 |
|---|---|---|
| **P0（本周）** | 配置 `ALERT_CMD`；建立心跳巡检 | 成本极低；不做则所有告警等于不存在（MD-004/005） |
| **P0（本周）** | 轮换 `instrument_reader` 密码 | 已知外泄 |
| **P1（趁回补窗口）** | 采集 SMB 元数据（含 create time） | **有时效性**：源端目录一旦清理，D 盘的原始 create time 永久失去（MD-001） |
| **P1** | 向 IT 确认 NAS 快照/WORM/异地副本 | 单点风险（MD-011） |
| **P2** | 建元数据库并回填历史 | 工作量大，但可从现有 CSV+JSON 回填大部分 |
| **P2** | 建立恢复演练制度 | 需积累记录，越早开始越好（MD-003） |
| **P3** | FLEX2 回移 mtime 修复；统一跨仪器模型；时区标注 | 一致性与细节 |

---

## 附：本次审计已确认为**有效实现**的机制（建议保持，勿在改造中破坏）

1. **只读源保护**：挂载 `ro` + 启动时写入自验，可写即中止（`preflight()`）。实测有效。
2. **SHA-256 双向校验**：源侧对内存字节算，归档侧**回读重算**，不一致即删副本、不记账、告警。
3. **原子写入**：临时文件 + `fsync` + `os.replace`，ETL 不会读到半截文件。
4. **append-only**：内容变化另存 `.rev<ts>`，绝不覆盖底本；源端删除只报告不跟随。
5. **半截不记账**：目录型资产未完整复制则整目录不记账，避免漏文件被永久跳过。实测有效。
6. **幂等**：重复运行无副作用，可放心加跑与手工补跑。
7. **忠实保存优于结构洁癖**：结构异常只告警照常归档，只有真损坏才拒收（铁律 5）。
   这一条在 GxP 语境下尤其正确——归档层不应做任何"智能"清洗。
