## 2026-11-05 — 下游凌晨ETL计划补齐

用户确认Nova/Vi-CELL每次归档计划启动后20分钟执行ETL，增加02:20（首次2026-11-06），保留12:05/16:20。同步运行时刻表和项目说明；本归档项目程序、timer及Linux部署不变。ETL timer、监控生效日期与验收记录分别由对应仓库和cmc-platform-monitor维护。

# Changelog

本文件记录 `cmc-instrument-ingest` 的变更。遵循 [Keep a Changelog](https://keepachangelog.com/zh-CN/) 风格。
版本号跟随各采集脚本内的 `SCRIPT_VERSION`（改动逻辑必须同步递增并在此登记，见 `CLAUDE.md` 风格约定）。

---

## flex2_ingest.py v1.5.0 + vicell_ingest.py v1.7.0 (2026-08-11) 🧹 审查修复 11 项：校验失败删坏副本 / dir_ok 拆分 / mtime 保留 / 互斥锁

外部审查发现的 11 个问题一次修完。判定基准 `docs/INGEST-STANDARD.md`。

### FLEX2（v1.4.0 → v1.5.0）

- **【高】校验失败不再留坏副本**：monthly / database / per-event 三处 SHA 不一致时
  按 §6 要求"删除坏副本 + 不记账 + CRITICAL"（与 Vi-CELL 既有做法对齐）。
  坏副本留着的话，下次重跑 append-only 守卫会把好数据挤成 `.rev`。
  配套：`archive_bytes` 改为返回**实际写入路径**——守卫可能已把目标改到 `.rev`，
  按调用方手里的旧路径删会误删原有好文件。
- **【中】归档副本保留源 mtime**（§7）：`archive_bytes` 加 `mtime=` 参数，
  rename 之后 `os.utime` + 回读确认，所有调用点传入源文件修改时间。
- **【中】Database 目录单文件失败改 `continue`**：该备份每晚被覆盖，错过永久丢；
  逐文件尽力归档，目录有失败仍不记账（下轮重试语义不变）。
- **【中】Database 目录不存在改 `alert WARNING`**：原来只 `logger.info` 静默跳过，
  且 `DB_STALE_HOURS` 新鲜度告警随之失效——共享结构变更必须留痕。
- **【低】per-event 疑似损坏改走 `alert WARNING`** 留痕；照常归档是刻意的
  （冷备忠实保存，SHA 双向校验已过），注释写明。

### Vi-CELL（v1.6.0 → v1.7.0）

- **【中】`dir_ok` 拆成 `list_ok` × `copy_ok`**：v1.6.0 的"本趟失败全是源端损坏"
  豁免分支无条件 `dir_ok = True`，把 list_entries 出 stat 失败时置的 False 也覆盖了
  ——目录被记账、stat 失败的图片永久跳过。现在豁免只作用于复制失败，
  list 失败的目录一律不记账、下次重来。
- **【中】`SRC_IMAGES` 消失单独告警**：preflight 只查 Data/Export，而
  `archive_sample_dirs` 只要历史源还在就不出声，活动图片源没了完全静默。
  现在 preflight 单独查它：不存在时 `WARNING` 并继续（不中止其他源）。
- **【低】`VICELL_ALERTS_ENABLED=0` 真正退回 v1.3.0 行为**：原来 sink 存在但
  disabled 时 `alert()` 直接 return，`ALERT_CMD` 直呼分支永远走不到，与注释不符。
  现在 disabled 时落到直呼分支；dry-run 保持不外呼。

### 两者共同

- **【低】启动时清扫 SIGKILL 残留的临时文件**：在归档树内查找匹配**自家专属模式**
  （vicell `.<名>.<pid>.tmp` / flex2 `<名>.part.<pid>.<时间戳>`）且 mtime 超过
  1 天的文件删除并留日志。模式锚定 pid/时间戳数字段，正式归档文件不可能命中。

### 部署侧

- **`run-ingest.sh` 加 flock 互斥锁**（`/var/lock/instrument-ingest.lock`，
  阻塞等待最多 30 分钟）：day/night 两个 timer 都 `Persistent=true`，
  停机跨过两个触发点后开机会并发补跑、并发写同一批 state 文件。
  两个 service 的 `ReadWritePaths` 补 `/run/lock`（`ProtectSystem=strict` 下
  锁文件才写得进去）。
- `heartbeat-check.timer` 注释里的旧排班（01:00 FLEX2 / 02:30 Vi-CELL）改为
  实际值（02:00 夜班全量 + 11:45/16:00 白天班）。带日期的历史文档
  （DEPLOYMENT-CHECKLIST / PRE-DEPLOYMENT-CHECK / 旧 CHANGELOG 条目）按
  历史记录保留原文不改。

### 验证

`tests/local_cifs_suite.sh`（Docker + 真 CIFS，12 项断言）全部通过。
该套件只覆盖 Vi-CELL；FLEX2 的改动（删坏副本 / mtime / continue / Database 告警）
以代码审查保证，上线后按 §11 首跑三步复核。

---

## vicell_ingest.py v1.6.0 (2026-08-06) 🔴 解开夜班死结：分段存盘 / 坏文件跳过 / SIGTERM 心跳

**2026-08-06 夜班跑满 2 小时被 systemd 超时杀掉，而今早 09:00 巡检报告"全部正常 ✅"。**
这一次不是单个缺陷，是三个问题叠成了一个不会自愈的死结。

### 出了什么事

两张 tif 稳定报 `[Errno 5] Input/output error`（`016-R2607-B5-B6-R3-D13_49.tif`、
`807-R2604-SF7-D1_14.tif`），每张要走满 `STABLE_RETRIES` 次重试、各烧掉约 30 分钟。
两张就吃掉一小时，整趟撞上 2 小时超时被 SIGTERM。然后：

1. **记账只在跑完时存一次** → 那晚 28 个已经完整拷完 50/50 的目录**一个都没记上**，
   第二晚要从头再拷 → 再超时 → 再白干。**永远不收敛。**
2. **SIGTERM 时不写心跳** → 心跳停留在前一次成功（17 小时前，未超 36 小时阈值）
   → 巡检判定"全部正常"。**备份连挂两晚，监控一声不响。**
3. 已生成 `.rev` 快照的变更也没记账 → 下一趟会再判一次"内容变了"、
   再生成一个重复的 `.rev`，NAS 上垃圾持续累积。

### 三条修复

- **分段存盘**（`VICELL_STATE_SAVE_EVERY`，默认 20 个目录）。这是解死结的关键一条：
  无论怎么死，已完成的部分都留得住，每一晚都能往前推进。
- **坏文件判定与跳过**（`VICELL_BAD_FILE_THRESHOLD`，默认 3 趟）。连续 3 趟读不出来
  即判定源端损坏，记入 state 的 `unreadable_files`，**发一次 CRITICAL**（只在判定那一刻，
  不重复刷屏），此后直接跳过不再重试。文件后来被修好/重导出会自动清除记录并恢复归档。
  含坏文件的目录记账时**如实写明缺哪几个**（`unreadable` / `expected_count` /
  `complete: false`）——记账不等于"当它是完整的"，那份缺失清单就是证据。
  > 这**不是**放宽铁律 5。铁律 5 说的是"别把损坏数据写进底本"；
  > 这里是"如实记录源端坏了"，两回事。真正违背铁律的做法是继续假装能拿到，
  > 让整趟超时、连带其余目录也归不了档。
  > `SHA256` 不一致**不计入**坏文件累计——那是传输/存储问题，重试通常能好。
- **捕获 SIGTERM**：先存盘、再写 `FAILED` 心跳、退出码 143。
  局限也写进代码注释了：信号只能在字节码之间投递，若正卡在迟迟不返回的 SMB 读上，
  处理函数要等它返回；systemd 默认只等 90 秒。**所以分段存盘才是第一道防线**，
  SIGTERM 处理是第二道。单元里同时把 `TimeoutStopSec` 放到 300 秒给收尾留时间。
- `instrument-ingest-night.service` 的 `TimeoutStartSec` 由 2 小时放到 4 小时——
  只是留余量，治本靠上面两条。

### 验证

新增对照脚本覆盖三条，全部通过：前两趟不轻易判定损坏、第三趟达阈值即判定并**当场记账**
（这里抓到过一个真 bug：判定成立的那趟目录仍不记账，要拖到第四晚才收敛，已修）、
第四趟不再去读坏文件、归档中途确实存了盘、SIGTERM 后心跳为 `FAILED`。
此前四轮的验证脚本全部回归通过。

---

## flex2_ingest.py v1.4.0 + vicell_ingest.py v1.5.0 (2026-08-05) 🛡️ 三道防线：空目录 / append-only / mtime

外部审查（Codex）剩余的三条数据丢失风险，一次修完。三条各自都做了
"修复前失败 / 修复后通过"的对照验证。

### ① FLEX2：空的 `Backup_*` 目录不再被记成"已归档"

目录为空时 `for src in files` 直接不执行、`failed` 保持 `False`，于是走到最后写下
`status: ARCHIVED, files: {}`——**这个目录从此被永久跳过**，哪怕备份程序后来把文件
补进去也再不会抓。目录建了却是空的，本身就说明备份没跑成，该报警而不是记完成。

顺带修掉同一段里更宽的一个洞：**已 ARCHIVED 的目录原来不再核对文件名单**。
现在每轮都比一次源端文件名，发现归档之后才出现的文件就补抓（只补新增的，
已归档的不重读不覆盖，原有记账也不会被冲掉）。备份分两次写完就属于这种情况。

### ② append-only 守卫：`state` 丢了也不许覆盖底本

"归档区 append-only"这条铁律原来**完全靠 state 记账来保证**：state 说"没归档过"
就直接写。可是 state 丢了、回退了、或读到旧副本时，NAS 上明明已有同名文件，
底本就会被静默覆盖——没有 `.rev` 快照、没有告警，谁也发现不了。

现在写入前**直接问 NAS**，不依赖任何记账：
- 目标不存在 → 照常写（正常路径零额外开销）
- 已存在且内容一致 → **不重写**，只把记账补回去（省一次 NAS 往返）
- 已存在且内容不同 → 另存 `.rev<RUN_TAG>`，原件保留，发 **CRITICAL** 并点明
  "state 可能丢失或回退"

三条写入路径都加了：FLEX2 的 `archive_bytes()`、Vi-CELL 的平铺文件与图片。
图片那条跑在线程池里，所以告警信息先收集、等线程池结束由主线程统一发出——
`alert()` 会外呼还会写文件，不适合并发调用。

### ③ Vi-CELL：同大小的内容改动不再被静默跳过

原来判"没变"只比文件大小，**大小相同的内容改动会被完全跳过**
（实测源文件 `AAAA` 改成 `BBBB`，归档仍是旧内容，无告警）。
现在把 `mtime` 一起纳入判定——它在同一次 `stat()` 里已经拿到了，比它不额外花钱。

**没有**改成每次重算哈希：这是 A 类源（一次写死，见 `INGEST-STANDARD` §5），
5.5 万个文件每天经 SMB 重读一遍要几十分钟，日常一趟就废了。

容差取 1 秒且宁紧勿松——判错成"没变"会静默漏掉内容改动（正是要修的病），
判错成"变了"只是多读一次文件重算哈希，慢一点但不丢数据。
老记录没有 `mtime` 字段时退回"只比大小"的旧行为并顺手补上，**不必为此重扫全库**。

### 同批文档清理

`CLAUDE.md` / `README.md` 里 `rd-nova-etl`"未建"（实际已建成）、
`README.md` 里 Vi-CELL"待首跑"（实际已上线）、`BACKUP_MONITORING_DESIGN.md`"待部署"、
`DEPLOYMENT-CHECKLIST-v1.4.0.md` 里引用已删除的 `vicell/deploy/*` 与 `vicell-ingest.timer`
（该清单是历史执行记录，加了醒目的"已过时、勿照做"提示而不是删掉，以便追溯）。

---

## flex2_ingest.py v1.3.0 + heartbeat v1.1.0 (2026-08-05) 💓 FLEX2 接入心跳，堵上监控盲区

**在此之前 `flex2_ingest.py` 里 `heartbeat` 出现 0 次——FLEX2 停了根本没人会发现。**
巡检的 `--expect` 只列了 Vi-CELL，就算加上 FLEX2 也只会天天报"找不到心跳文件"，
因为它压根不写。这是外部审查确认的监控盲区，也是 CLAUDE.md 里挂了很久的待办。

- `heartbeat.py` 从 `vicell/` **挪到 `tools/`**：心跳与仪器无关，两台都要用，
  放在某一台的目录下会让另一台"要依赖别人的目录才能写心跳"。
  新增 `log=` 参数，各脚本传自己的 logger，日志才会落进各自的日志文件。
- FLEX2 在**三个出口**都写心跳，一个都不能少：
  - 正常跑完（SUCCESS / FAILED，排在告警之后，保证告警计数完整）
  - **预检失败**（源未挂载、NAS 未挂载、ro 自验不过）——不写的话"挂载坏了"与
    "程序根本没跑"在巡检看来完全一样，而这正是心跳要区分的（Vi-CELL v1.4.0 踩过）
  - **顶层崩溃**——同理，"崩了"与"没跑"处置完全不同
- `--dry-run` **不写**心跳：空跑没有真备份，写了会让巡检误以为一切正常。
- `alert()` 顺带做各级别计数（`WARN`/`WARNING` 归一），写进心跳的 `alerts` 字段，
  与 Vi-CELL 对齐——巡检不用翻日志就知道这趟出过几条什么级别的告警。
- 新增 `FLEX2_HEARTBEAT_ENABLED` / `FLEX2_EXPECTED_INTERVAL_HOURS`（12）/
  `FLEX2_MAX_SILENCE_HOURS`（36）。12 小时的依据：排 02:00 / 11:45 / 16:00 三趟，
  最长间隔是 16:00→次日 02:00 的 10 小时。
- `heartbeat-check.service` 加 `--expect T281240040C_Nova` 与
  `ReadWritePaths=/var/lib/flex2-ingest`。

验证（5 个场景全通过）：预检失败写出 FAILED 心跳且 `last_success_time` 保持为空、
正常跑写出 SUCCESS、`--dry-run` 不写、开关关掉退回旧行为、巡检能读懂并在心跳
被删掉时报出缺失。Vi-CELL 侧回归通过（模块挪位置未影响）。

### 同批修正：一处**写反了**的数据源结论

`docs/SETUP.md` 与 `flex2_ingest.py` 的文档字符串都写着"月度 CSV 是逐次文件的
**严格超集**"。**这是错的**，2026-07-23 全量核对（7704 行 / 15 个月）结论相反：
逐次独有 810 条错位行的中段检测值（月度里因通道省略而丢失、无法还原），
月度独有试剂批号列，**两者互补**。照旧结论做 ETL 会以为逐次文件可弃用，
那会永久丢掉 810 条记录的检测值。SETUP.md 的"已忽略：逐次 CSV"也同步改正
（`--per-event` 自 2026-07-23 起就一直是开的）。

---

## vicell_ingest.py v1.4.2 + heartbeat_check v1.0.1 (2026-08-05) 🔴 两个静默失效缺陷

外部代码审查（Codex）提出 15 项，逐条对代码复核后确认属实的先修最紧的两条。
两条都**已用"修复前失败 / 修复后通过"的对照脚本验证**。

### ① 图片目录"部分归档却记成完成"——会永久丢图片

`archive_sample_dirs()` 里，被仪器占用、`list_entries` 读不到属性的文件会被剔出
`files` 列表。于是后面的完整性判据 `copied == len(files)` **照样成立**、`dir_ok`
仍为 `True`，目录被写进 state，**下次直接跳过，缺的图片永远补不回来**。

最坑的是当时那条告警的文字就写着"本目录本次不记账，下次重试"——**代码做的和告警
说的正好相反**，看到告警的人会以为已经安排重试了。

实测复现（3 个文件占用 1 个）：修复前 state 记账 `SAMPLE-001`、`new_dirs: 1`、
`error: 0`（**看起来像一次干净的成功**），第二轮占用解除也救不回来；
修复后目录不记账、第二轮 3 个文件全部归档。

- 把 `dir_ok` 提到列目录之前，`list_entries` 有跳过项即置 `False`，并计入 `stats["error"]`。
- 跳过项的文件名带进告警（原来只报个数，不知道是哪张）。
- `dir_ok` 为假时不再重复报"图片数异常"——那条会让人误以为是仪器少拍了，
  掩盖真正的原因。

> 这正是 2026-08-04 生产上真实发生过的场景（图片 `Device or resource busy`），
> 不是理论风险。v1.4.1 修好了"整个进程崩掉"，但没修"崩不掉之后记错账"。

### ② 一台仪器的心跳坏掉，会让整个巡检停摆

`float(hb.get("max_silence_hours") or 72)` 写在 `try` 之外，而它位于遍历各仪器的
**循环内部**。字段被写成 `"oops"` 之类就抛 `ValueError`，**整个 `check()` 中断，
排在它后面的仪器一台都检查不到**——真正停掉的备份会被一个坏字段完全掩盖。
监控自身失效是最坏的一类失效。

实测（5 台，第 1 台字段坏）：修复前直接 `ValueError` 崩掉、0 台被检查；
修复后 5 台全部检出，坏的那台报 WARNING 并退回默认阈值，排在它后面的超时仪器
照常报 CRITICAL。

- 拆出 `check_one()`，每台单独 try 兜底，一台坏不影响其余。
- 新增 `parse_hours()`：非数值、NaN、非正数一律退回默认 72h 并报 WARNING。
  （NaN 尤其阴险——参与比较恒为 `False`，会让超时判断**永远不触发**。）
- 心跳文件内容不是对象（如被写成数组）时单独报 CRITICAL，不再往下猜。

**未改动**：SHA-256 流程、NAS 目录结构、`Checksums/` 格式、state 结构、告警分级语义。

---

## 接入 — 2026-08-04 🌱 新增数据库型源 `ralf`（Bioengineering 发酵）脚手架

**背景**：新增一类源——Bioengineering **RALF** 发酵工作站，数据在 **MySQL 4.1** 里
（不是文件共享），要用 `mysqldump` 备份到 NAS。有多台工作站（至少两台，后续可能增加）。
这是本库**第一个数据库型源**。

**本次只建离线能做的脚手架，采集脚本待联网勘察 + 实测后落地**（遵循 §11「survey → 写脚本 → 首跑三步」不跳步）：

- 新增 `ralf/ralf-ingest.env.example`：每台工作站一份配置的配置面（源 DB / 冷热库前缀 / 保留 / 告警心跳）。
- 新增 `docs/source-survey-ralf.md`：一台的实测事实（MySQL 4.1、InnoDB、`t_analyze` 近亿行、ibdata1 在 D 盘、只读账号 `etl_reader`、群晖整盘备份现状）+ **多台区分规则** + **与文件型规范的差异**。
- **`docs/INGEST-STANDARD.md` 扩展为覆盖两种源形态**：§0 声明"文件型 / 数据库型"；
  **新增 §5B 数据库型源通用规范**（引擎无关的策略 + 引擎专属的导出命令表，
  这样今后任何数据库源照 §5B 办，不用翻 ralf 文档现想）；§3 账号表加"读数据库型源"一行。
  未改动现有 §号（多处交叉引用，用带字母的 §5B 避免重排）。
- README 设备表加一行。

**多台如何区分（已定，负责人 2026-08-04）**：一个 `ralf/` 目录 + 一份脚本；每台靠
**机器名 `<主机名>_Bioengineering`**（贯穿 NAS 目录）+ 各自 `ralf-<机器名>.env` 区分；
冷热库按名字前缀（`db_archive*`/`pbh*`）自动识别，不同罐号无需改代码。

**与文件型仪器规范的差异（见 survey §3）**：不挂 CIFS、走只读 MySQL 账号保证只读边界；
SHA-256 校验对象是 `.sql.gz`；不共用日定时器，走自己的**周（热库）/ 月（冷库）**定时器；
健康信号用「dump 任务是否按时跑」。核心铁律（只读 / 校验 / append-only / 凭据不入库 / 告警心跳）不变。

**待办**：见 `docs/source-survey-ralf.md` §4（逐台勘察主机名+凭据、写 `ralf_ingest.py`、
`run-ingest.sh` 加 ralf 段 + 周/月 timer、群晖 ABB 确认、账号 `etl_reader`→`instrument_reader` 消歧）。

---

## 部署 — 2026-08-05 🗓️ 定时器从 4 个合并成 2 个

**起因**：原先按设备拆定时器（FLEX2 一天三趟、Vi-CELL 完整版一趟、Vi-CELL 白天快跑两趟），
彼此还要错开 10 分钟，共 4 个 timer、6 个触发时刻。两台仪器每趟只有几十个小文件，
错峰的实际收益极小，代价却是"今天几点该跑什么"没人记得住、改一个时刻要动四个文件。

**改成**：按"时段"而非按设备组织，所有仪器共用两个单元。

| 时刻 | 单元 | 跑什么 |
|---|---|---|
| `02:00` | `instrument-ingest-night` | 全量，含 Vi-CELL 图片、FLEX2 Database 备份 |
| `11:45` / `16:00` | `instrument-ingest-day` | 所有设备，不含图片 |

- 新增 `tools/run-ingest.sh <day|night> [设备...]`：逐台调用各设备采集脚本。
  **两个采集脚本没有合并**——一台仪器故障不许拖垮另一台，所以 wrapper 里
  前一台失败后一台照跑，各记退出码，最后汇总一条批次告警。
  FLEX2 排前面（几秒完成），Vi-CELL 排后面（夜班图片可能几十分钟）。
- 删除 `flex2/deploy/`、`vicell/deploy/` 下全部单元及 `per-event.conf` drop-in；
  `--per-event` / `--no-legacy` / `--no-images` 现由 wrapper 按时段决定。
  **所有 systemd 单元统一收进 `tools/deploy/`。**
- 采集单元的 `RequiresMountsFor` 只留 `/mnt/ttlab-backups`：
  一台仪器的源共享断了不该连累另一台不跑，源挂载由脚本自己检查并告警
  （原先每个单元都列自己的源，合并后若照抄会变成"任一源断=全都不跑"）。
- **同步改了下游两个 ETL 仓库**：`rd-nova-etl` / `rd-vicell-etl` 的 timer
  由 `12:05` + `18:20` 改为 `12:05` + `16:20`，保持"归档后 20 分钟入库"。
  这是跨仓库硬耦合，只改一边会让当天数据静默入不了库。
- 权威时刻表落在 `docs/INGEST-STANDARD.md` §9.1，改时刻先改那里。

---

## vicell_ingest.py — v1.4.1 (2026-08-04) 🔴 缺陷修复

**首次生产运行暴露的既有缺陷：单个被占用的文件会让整趟备份崩溃。**

2026-08-04 09:16 首次 v1.4.0 生产运行时操作员正在使用仪器，
`/mnt/vicell/Export/007-0715-2.xls` 被占用，`archive_flat_dir` 列目录时
`p.is_file()` 抛 `OSError[16] Device or resource busy`，**整个进程异常退出，
一个文件都没归档**。该缺陷自 v1.0.0 存在，此前从未在仪器使用中运行故未暴露。

- 新增 `list_entries(d, want)`：列目录**逐条容错**，单条 `stat()` 失败只跳过并计数，
  不影响其余条目；整个目录列不出来仍抛给调用方（那是真问题）。
  被跳过的条目**必定告警**——跳过意味着该文件本次没归档，绝不能静默。
  已应用于 4 处：`archive_flat_dir`、`archive_sample_dirs` 的来源映射与样品目录内列文件、
  metadata 补采。
- **顶层异常处理现在也写 `FAILED` 心跳。** 原来异常从 `main()` 抛出后心跳代码
  根本执行不到，导致"崩溃"与"从没跑过"在巡检看来完全一样——恰恰是心跳要消除的歧义。
- 告警新增 `SCRIPT_CRASH` 分类（原落入 `UNCLASSIFIED`）。

验证：本地回归 12/12 通过；另用 `stat()` 必抛错的条目直接验证 `list_entries`——
修复前整体崩溃，修复后坏条目被隔离、其余 2 个文件照常返回。

> **运行时特性**：仪器使用中，其当前样品的文件会被持有句柄，
> 表现为 `Device or resource busy`。这类文件本次跳过、下次重试即可，属正常现象。
> 日常 timer 排在 02:30 仪器空闲时段，正常不会遇到。

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
