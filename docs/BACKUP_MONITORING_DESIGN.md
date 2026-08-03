# 备份运行监控设计（告警 + 心跳）

| | |
|---|---|
| 文档版本 | v1.1（2026-08-03）**设计已确认，代码已实现并测试，待部署** |
| 对应整改项 | `AUDIT-2026-08-03-data-integrity.md` **MD-004**（告警送达）、**MD-005**（任务未执行检测） |
| 阶段范围 | 只做告警与心跳。**不做**数据库（MD-002）、恢复验证（MD-003）、看板 |
| 不改动 | SHA-256 流程、metadata 采集流程、NAS 目录结构、`Checksums/` 格式、`Daily/` 结构、state 结构 |

---

## 1. 现状检查：`ALERT_CMD` 实现的六个问题

现有实现（`vicell_ingest.py` / `flex2_ingest.py` 中相同）：

```python
def alert(level: str, message: str) -> None:
    logger.error(f"ALERT[{level}] {message}")
    if not ALERT_CMD:
        return
    try:
        subprocess.run([ALERT_CMD, level, f"[{MACHINE_NAME}] {message}"], timeout=30, check=False)
    except Exception as e:
        logger.warning(f"告警命令执行失败: {e}")
```

调用点：`vicell_ingest.py` 14 处、`flex2_ingest.py` 21 处。

| # | 问题 | 证据 | 影响 |
|---|---|---|---|
| A-1 | **`ALERT_CMD` 未配置，告警只进日志** | 生产 env 中 `VICELL_ALERT_CMD=` 为空 | 这就是 MD-004 本体：最高级别事件无人可见 |
| A-2 | **severity 字符串四种拼法** | 实测调用点：`CRITICAL`×13、`ERROR`×9、`WARN`×7、`WARNING`×3 | `WARN`/`WARNING` 是同一级别两种写法，下游无法按级别路由 |
| A-3 | **告警命令执行失败是静默的** | `check=False` 且 `except` 只捕获异常 | 命令跑了但返回非零（如企业微信接口 4xx）**不会有任何记录**，与"alert 失败要记 warning"的要求相悖 |
| A-4 | **无限流，最坏可阻塞备份 50 分钟** | 每条 `timeout=30`，无上限 | 一次运行若产生 100 条告警，串行等待最坏 50 分钟，违反"不因 alert 影响 backup" |
| A-5 | **无结构化字段** | 只有 `level` + 自由文本 | 无 `event_type`、无 `file_path`，无法机器解析、无法统计"历史上有多少次 SHA 不一致" |
| A-6 | **告警无独立留存** | 只写进 per-run 日志 | 要回答"过去 30 天有哪些告警"需 grep 几十个日志文件（FLEX2 已 51 个） |

> A-3 与 A-4 是本次设计要重点解决的：前者让"告警失败"可见，后者保证告警**永远不会拖慢或阻断备份**。

---

## 2. 统一异常事件模型

### 2.1 字段定义

| 字段 | 类型 | 说明 |
|---|---|---|
| `event_time` | ISO-8601 带时区 | 事件发生时刻 |
| `machine_name` | string | 如 `C4V61257XH_ViCell` |
| `severity` | enum | **只允许三个值**：`CRITICAL` / `ERROR` / `WARNING` |
| `event_type` | enum | 见 §2.3 |
| `file_path` | string \| null | 涉及具体文件时填源端完整路径，否则 null |
| `message` | string | 人可读描述（保留现有文案） |
| `run_tag` | string | 本次运行标识（如 `20260803_210629`），可关联到同批次的日志与 Checksums 文件 |
| `script_version` | string | 如 `vicell_ingest v1.3.0` |

`run_tag` 与 `script_version` 是我建议追加的两个字段（原要求中没有）：
没有它们，一条告警无法关联回"哪一次运行、哪个版本产生的"，
排查与检查举证时会缺一环。

### 2.2 严重度定义（统一为三级）

| severity | 含义 | 处置期望 |
|---|---|---|
| `CRITICAL` | 数据可能丢失或已被污染，需当天人工介入 | 立即通知 |
| `ERROR` | 单项操作失败，程序已自愈或将重试，但需要知道 | 通知 |
| `WARNING` | 需知悉，不影响本次归档完整性 | 汇总通知即可 |

**迁移映射**（现有四种拼法 → 三级）：

| 现有 | 新 | 数量 |
|---|---|---|
| `CRITICAL` | `CRITICAL` | 13 |
| `ERROR` | `ERROR` | 9 |
| `WARN` | `WARNING` | 7 |
| `WARNING` | `WARNING` | 3 |

`alert()` 内部做归一化，**调用点一律不改**——32 处调用点全部保持原样，
避免为了改字符串去动 32 个位置、引入无谓风险。

### 2.3 事件类型（覆盖要求的六类，另补三类现有场景）

| `event_type` | 触发场景 | 典型 severity | 覆盖要求 |
|---|---|---|---|
| `COPY_FAILED` | 文件复制/写入归档失败 | ERROR | ✅ copy 失败 |
| `SHA256_MISMATCH` | 回读校验与源不一致（坏副本已删除） | CRITICAL | ✅ SHA256 mismatch |
| `METADATA_FAILED` | metadata 采集不完整或失败 | WARNING | ✅ metadata 采集失败 |
| `SOURCE_UNAVAILABLE` | 源未挂载、源目录不存在、列目录失败、读取失败 | CRITICAL / ERROR | ✅ source 不可访问 |
| `NAS_UNWRITABLE` | NAS 未挂载或归档区写入被拒 | CRITICAL | ✅ NAS 不可写 |
| `MOUNT_ERROR` | 预检失败、**只读源竟然可写**（配置事故） | CRITICAL | ✅ mount 异常 |
| `SOURCE_DELETED` | 源端文件已消失（归档保留） | WARNING | 现有场景 |
| `CONTENT_CHANGED` | 已归档文件内容变化（另存 `.rev`） | WARNING | 现有场景 |
| `STRUCTURE_ANOMALY` | 结构异常但完好（多行宽、图片张数不符等） | WARNING | 现有场景 |
| `UNCLASSIFIED` | 未匹配到上述任何一类 | 沿用调用方 | 兜底，不丢事件 |

**分类实现方式**：`alert()` 内部按消息关键词自动归类，**不改动 32 处调用点**。
未匹配到的归入 `UNCLASSIFIED` 并原样记录——**分类不确定时不丢事件**，这是底线。

> 该做法的取舍：关键词匹配不如显式传参精确，但显式传参要改 32 个调用点，
> 与"不改变现有 backup 逻辑"的约束冲突。建议本阶段先用关键词归类，
> 后续如需精确分类，再逐个调用点显式补 `event_type`（届时属独立小改动，风险可控）。

---

## 3. 告警输出

### 3.1 存放位置

```
/mnt/ttlab-backups/
└── Alerts/<机器名>/
        alert_YYYYMMDD.jsonl        # 按天一个文件，追加写
```

**本地兜底**（重要）：`/var/lib/<代号>-ingest/alerts/alert_YYYYMMDD.jsonl`

> 为什么必须有本地兜底：**NAS 不可写正是要告警的场景之一**。
> 若告警只写 NAS，那么"NAS 挂了"这条最重要的告警恰恰写不进去。
> 两处都写，任一可用即留痕。

### 3.2 为什么用 JSON Lines 而不是单个 JSON 数组

原要求写的是 `alert_YYYYMMDD.json`（"例如"）。建议改为 **JSON Lines**（每行一个 JSON 对象），
理由：

- **追加写、不需要读-改-写**。单个 JSON 数组每次追加都要读出整个文件、解析、追加、重写，
  一旦运行中断就可能留下损坏的半截 JSON——而告警文件恰恰在系统出问题时最需要可靠。
- **多进程安全**。FLEX2 与 Vi-CELL 的 timer 可能重叠；JSONL 以 `O_APPEND` 单行写入，
  单行小于管道原子写上限时天然安全。
- **可 grep、可 `tail -f`**，运维直接可用。
- 解析成本极低：`[json.loads(l) for l in open(f)]`。

**已确认采用 `alert_YYYYMMDD.jsonl`**（见 §8 决策记录 D-1）。

### 3.3 限流与去重（解决 A-4）

| 机制 | 设计 |
|---|---|
| **写文件** | **全部事件都写**，不限流。写文件成本微秒级，且完整留痕是审计要求 |
| **调外部命令** | 单次运行最多调用 `ALERT_CMD` **20 次**（可配置），超出后只在运行结束时发一条汇总 |
| 去重 | 同一 `event_type` + 同一 severity 在同一次运行内，超过 5 条则合并为一条"同类共 N 条" |
| 超时 | 单条 `timeout` 由 30 秒降为 **10 秒**；单次运行外部告警总耗时上限 **60 秒**，超出即停止外呼（仍继续写文件） |

这样最坏情况下，告警对备份耗时的影响被限制在 60 秒以内，而不是现在的无上限。

### 3.4 告警失败的处理（解决 A-3）

```
外部命令返回非零 → logger.warning（现在完全静默）
外部命令抛异常   → logger.warning（现有行为，保留）
写告警文件失败   → logger.warning，且尝试写另一处（NAS ↔ 本地）
```

**任何告警环节的失败都不向上抛出，不影响备份流程。** 这一条在实现中通过
`alert()` 全函数体包 `try/except Exception` 保证。

---

## 4. 心跳机制

### 4.1 心跳文件

原要求写的是 `State/heartbeat.json`。**已确认改为每台仪器一个文件**（§8 决策记录 D-2）：

```
State/<机器名>_heartbeat.json          # 如 C4V61257XH_ViCell_heartbeat.json
/var/lib/<代号>-ingest/<机器名>_heartbeat.json   # 本地兜底
```

> **为什么不用单一 `heartbeat.json`**：多台仪器共用一个文件需要读-改-写，
> 而 FLEX2（01:00/12:00/16:00）与 Vi-CELL（02:30）的 timer 未来可能重叠，
> 并发写会丢更新——恰好丢掉的是"某台仪器跑过了"这个关键事实。
> 每机一个文件是纯追加语义，无并发风险；巡检脚本 glob 一次即可读全。

### 4.2 字段

| 字段 | 说明 |
|---|---|
| `machine_name` | 机器名 |
| `script_name` / `software_version` | 如 `vicell_ingest` / `v1.3.0` |
| `last_run_time` | 本次运行开始时刻（ISO-8601 带时区） |
| `last_run_finished` | 本次运行结束时刻 |
| `last_success_time` | **最近一次成功**的时刻；失败时保留上一次的值不动 |
| `backup_status` | `SUCCESS` / `FAILED` |
| `files_processed` | 本次新增归档的文件数 |
| `files_failed` | 本次失败项数 |
| `alerts` | 本次各 severity 的计数，如 `{"CRITICAL":0,"ERROR":1,"WARNING":3}` |
| `duration_sec` | 本次耗时 |
| `run_tag` | 关联日志与 Checksums |
| `expected_interval_hours` | **本机正常运行间隔**（Vi-CELL=24，FLEX2=8） |
| `max_silence_hours` | **超过多久算异常**（默认 = 间隔 × 3） |

> `expected_interval_hours` / `max_silence_hours` 写进心跳文件本身，
> 这样**巡检脚本是通用的**——它不需要知道每台仪器的排期，
> 新增仪器零改动。这是刻意的设计。

### 4.2b 心跳写入失败的处理原则（已实测验证）

| 情况 | 行为 |
|---|---|
| NAS 心跳写入失败 | 记 WARNING，**本地兜底文件仍写出** |
| NAS 与本地**都**写入失败 | 记 WARNING（`心跳写入失败（NAS 与本地均不可写，不影响备份结果）`） |
| 任一情况下的备份结果 | **完全不受影响**：归档文件照常写入，**退出码不变** |

**心跳失败绝不改变备份任务的成败判定。** 心跳是观测手段，不是备份的一部分——
让观测失败去污染备份结论，等于本末倒置。

实现上由两点保证：① `write_heartbeat()` 全函数体 `try/except`，异常只返回 `None`；
② `main()` 的返回值只由 `errors`（归档失败项数）决定，与心跳返回值无关。

已由 T10a / T10b 实测验证（见测试报告）：备份成功 + 心跳全写失败 → 退出码仍为 0，
且 4 个归档文件全部正常写入。

### 4.3 何时写

**每次运行结束都写**（无论成功失败），但 `last_success_time` 只在成功时更新。

> 原要求是"每次成功 backup 后生成"。**已确认改为每次都写**（见 §8 决策记录 D-3）：
> 若只在成功时写，"连续失败三天"在心跳文件上表现为"三天没更新"，
> 与"程序根本没跑"**无法区分**——而这两种情况的处置完全不同。
> 每次都写 + `backup_status` 字段即可区分。T3 已实测验证该区分有效。

### 4.4 巡检脚本（MD-005 的本体）

新增独立脚本 `tools/heartbeat_check.py`：

```
扫描 State/*_heartbeat.json
  ├─ last_success_time 距今 > max_silence_hours  → CRITICAL：备份可能已停止
  ├─ backup_status == FAILED                     → ERROR：最近一次运行失败
  └─ 心跳文件本身缺失                             → CRITICAL：从未运行或文件丢失
输出：控制台 + Alerts/_heartbeat/alert_YYYYMMDD.jsonl + 调用 ALERT_CMD
退出码：0=全部正常，1=有异常（便于 systemd/外部监控接管）
```

**关键设计：这个脚本必须独立于采集程序，由自己的 systemd timer 触发。**
理由见审计 MD-005：采集脚本没跑的时候，它自己不会上报"我没跑"。

建议排期：每天 09:00（上班时间，人能看到）。

### 4.5 诚实说明：巡检脚本自身的死角

巡检脚本自己若不跑，同样无声。彻底的解法是把心跳推给外部系统（如企业微信定时确认、
或外部 uptime 监控 pull）。本阶段**不做**，但要记录这个残留风险：

> **残留风险 R-1：`heartbeat_check.py` 自身未被独立监控。**
>
> 本脚本负责发现"采集程序没跑"，但**没有任何机制负责发现"本脚本没跑"**。
> 若它的 timer 被禁用、脚本报错、或整台 Linux 宕机，
> 备份与巡检会**同时静默**，而且这种静默与"一切正常"在外部看来完全一样。
>
> 这是监控链条的固有终点问题：检查者本身也需要被检查。本阶段**不解决**，明确登记在案。
>
> **后续解决方向（daily positive heartbeat / report 机制）**：
> 把"无消息即正常"反转为"有消息才正常"——巡检每天固定推送一条结果报告
> （无论正常与否），接收方约定"连续两天没收到即视为异常"。
> 这样监控链条的断裂本身会成为一个可观测事件。
> 该机制需要外部通知端点，因此与 MD-004 Phase 2 存在依赖关系，建议一并实施。

---

## 5. 改动范围与不改动承诺

### 5.1 计划改动的文件

| 文件 | 改动 |
|---|---|
| `vicell/alerting.py` | **新增**：事件模型、`AlertSink`（写 JSONL + 限流外呼） |
| `vicell/heartbeat.py` | **新增**：心跳写入 |
| `tools/heartbeat_check.py` | **新增**：独立巡检脚本 |
| `vicell/vicell_ingest.py` | `alert()` 内部改为经 `AlertSink`；`main()` 末尾写心跳。**调用点 0 改动** |
| `vicell/deploy/heartbeat-check.{service,timer}` | **新增** systemd 单元 |
| `vicell/vicell-ingest.env.example` | 新增配置项 |
| `docs/` | 本文档 + 测试报告 |

FLEX2 同步接入放在本阶段之后（保持一次只动一台的节奏）。

### 5.2 明确不改动

- **SHA-256 流程**：`read_source_stable` / `sha256_file` / 回读比对 / 失败处置，一行不动
- **Metadata 采集流程**：`smb_metadata.py` 与其调用点不动
- **NAS 目录结构**：`Daily/` 布局不动；新增的 `Alerts/` 与 `State/*_heartbeat.json` 是**新增路径**，不影响既有
- **`Checksums/` 格式**：9 列表头不动
- **32 处 `alert()` 调用点**：签名与参数不动
- **state JSON 结构**：不动（心跳是独立文件）

### 5.3 向后兼容

- `VICELL_ALERTS_ENABLED=0` 可关闭新告警落盘，行为退回 v1.3.0
- 未配置 `ALERT_CMD` 时仍只写日志与告警文件，不报错
- 心跳文件写失败只记 warning，不影响退出码

---

## 6. 测试计划（实施后执行）

| # | 测试 | 验证点 |
|---|---|---|
| T1 | 正常运行 | 心跳文件生成、字段完整、`backup_status=SUCCESS`、无告警文件或仅 WARNING |
| T2 | 制造 SHA 不一致 | 产生 `SHA256_MISMATCH`/`CRITICAL` 事件，JSONL 字段完整，坏副本被删 |
| T3 | 源不可访问 | 卸载源挂载后运行 → `MOUNT_ERROR`/`CRITICAL`，程序按预检中止 |
| T4 | NAS 不可写 | 归档区只读 → `NAS_UNWRITABLE`，本地兜底告警文件仍写出 |
| T5 | metadata 采集失败 | tmpfs 源 → `METADATA_FAILED`/`WARNING`，备份照常完成 |
| T6 | **ALERT_CMD 执行失败** | 指向必然返回非零的命令 → 记录 warning（当前是静默的），备份不受影响 |
| T7 | **告警风暴限流** | 制造 >20 条告警 → 外呼次数被限、文件仍全量记录、备份耗时未被拖慢 |
| T8 | 心跳巡检告警 | 手工把 `last_success_time` 改早 → 巡检脚本报 CRITICAL、退出码 1 |
| T9 | 心跳巡检正常 | 正常状态 → 退出码 0，无告警 |

测试一律使用隔离机器名（如 `ZZTEST_*`），完成后清理，不污染生产数据。

---

## 7. 风险评估

| 风险 | 等级 | 说明与缓解 |
|---|---|---|
| **改 `alert()` 影响现有备份流程** | 中 | `alert()` 有 32 处调用，是热路径。缓解：全函数体包 `try/except`，任何内部异常都吞掉并降级为 `logger.warning`；先在隔离机器名下跑完整 T1–T9 再上生产 |
| **告警外呼拖慢备份** | 中 | 现状已有此风险（无上限）。本设计引入单条 10 秒 + 单次运行总计 60 秒上限，**风险较现状降低** |
| **关键词分类误判 `event_type`** | 低 | 误判只影响分类字段，`message` 原文始终保留；未匹配归 `UNCLASSIFIED` 不丢事件。后续可逐点显式化 |
| **告警文件写入失败** | 低 | NAS 与本地双写，任一成功即留痕；两处都失败只记 warning，不影响备份 |
| **心跳文件与 state 不一致** | 低 | 心跳是独立文件，不参与增量判断；即使损坏也不影响归档正确性 |
| **巡检脚本自身不跑** | 中 | 见 §4.5 残留风险 R-1，本阶段不解决，需记录在案 |
| **正在进行的图片回补受影响** | 中 | 回补作业每批重新加载脚本，部署即生效。缓解：**在回补完成后再部署**，或部署前完成隔离测试 |
| 时区/夏令时 | 低 | 全部使用 ISO-8601 带时区，不用裸本地时间 |

---

## 8. 设计决策记录（2026-08-03 已确认）

| # | 决策点 | 结论 | 依据 |
|---|---|---|---|
| D-1 | 告警文件格式 | **JSON Lines，文件名 `alert_YYYYMMDD.jsonl`** | 追加写、无读-改-写、中断不产生损坏文件、多进程安全（§3.2） |
| D-2 | 心跳文件 | **每台仪器一个 `State/<机器名>_heartbeat.json`** | 单一文件需读-改-写，两台 timer 重叠会丢更新（§4.1） |
| D-3 | 心跳写入时机 | **每次运行都写，`backup_status` 区分成败**；`last_success_time` 仅成功时更新 | 否则"连续失败"与"根本没跑"无法区分，而两者处置不同（§4.3） |

以上三项均偏离最初口头规格，已逐条说明理由并获确认。

### MD-004 的阶段定义（不得跳过）

**MD-004 当前状态：Phase 1 — Alert generation + persistent logging completed.**

本阶段完成的是"告警的产生与留存"，**不是**"告警的送达"。

> **Residual gap: `ALERT_CMD` notification endpoint not configured.**
>
> 在拿到通知渠道（企业微信机器人 / 邮件 / 其它）并完成连通性验证之前，
> 告警会**完整落盘但不外呼**——**仍然没有人会被主动通知**。
>
> **因此不得宣称 MD-004 已关闭。** 任何整改结论、汇报材料、检查应答中，
> MD-004 的状态一律写作 "Phase 1 completed / Phase 2 pending notification endpoint"。

**Phase 2 的完成判据**（三条全满足才可关闭 MD-004）：

1. `ALERT_CMD` 指向真实通知端点并写入生产配置；
2. 发一条测试告警并**确认收到**（留存截图或收件记录）；
3. 通知通道的可用性纳入定期确认（建议随季度巡检一并做，避免通道悄悄失效）。
