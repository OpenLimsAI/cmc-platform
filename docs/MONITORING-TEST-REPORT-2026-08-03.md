# 告警与心跳机制测试报告

| | |
|---|---|
| 测试日期 | 2026-08-03 |
| 被测对象 | `vicell/alerting.py` v1.0.0、`vicell/heartbeat.py` v1.0.0、`tools/heartbeat_check.py` v1.0.0、`vicell/vicell_ingest.py` v1.4.0 |
| 对应整改项 | **MD-004**（告警送达）、**MD-005**（任务未执行检测） |
| 设计依据 | `docs/BACKUP_MONITORING_DESIGN.md` |
| 测试隔离 | 全部使用独立机器名（`ZZTEST_ViCell` / `ZZT2_ViCell`）与 tmpfs 假源，不触碰生产数据 |

**结论：全部 11 项测试通过。**

T4 与新增的 T10a/T10b 于 2026-08-03 在**本地 Docker Linux 容器**中补测完成
（Vi-CELL 工作站所在网络当时不可达）。容器环境用 tmpfs 挂载点使
`os.path.ismount()` 判定为真、用文件权限制造真实的写入被拒，
忠实复现了"NAS 可挂载但不可写"的场景。

---

## 1. 测试结果总览

| # | 测试 | 结果 | 关键证据 |
|---|---|---|---|
| T1 | 正常运行 → 心跳生成 | ✅ 通过 | 心跳字段完整，`backup_status=SUCCESS`，处理 6 失败 0 |
| T2 | SHA-256 不一致 | ✅ 通过 | `CRITICAL`，坏副本已删除（归档区 0 文件），心跳 `FAILED` |
| T3 | 源不可访问 | ✅ 通过 | `CRITICAL` / `MOUNT_ERROR`，心跳 `FAILED` 且 `last_success_time` 保留 |
| T4 | NAS 不可写 | ✅ 通过 | 退出码 1，`CRITICAL`/`NAS_UNWRITABLE`×4，**本地兜底告警生成**，NAS 零残留 |
| T5 | metadata 采集失败 | ✅ 通过 | 随 T1 一并覆盖：tmpfs 源 → `stat-only` 6 条，备份照常完成 |
| T6 | `ALERT_CMD` 执行失败 | ✅ 通过 | 返回非零被记录为 WARNING（**原实现完全静默**） |
| T7 | 告警风暴限流 | ✅ 通过 | 100 条告警耗时 **0.01 秒**，外呼 5 次，落盘 101 条一条不少 |
| T8 | 心跳巡检发现异常 | ✅ 通过 | 三类异常全部检出，退出码 1，告警落盘 |
| T9 | 心跳巡检正常 | ✅ 通过 | 退出码 0，`--quiet` 下无输出 |
| T10a | 心跳 NAS 写入失败 | ✅ 通过 | 本地兜底生效，**退出码 0**，归档 4 文件正常 |
| T10b | 心跳 NAS+本地全失败 | ✅ 通过 | 仅 WARNING，**退出码仍为 0**，归档 4 文件正常 |

---

## 2. 逐项证据

### T1 — 正常运行

```
Data   : 新增 3  跳过 0  变化 0  失败 0
Export : 新增 1  跳过 0  变化 0  失败 0
Images : 新增目录 1  跳过目录 0  文件 2  失败 0
Metadata: 采集 6  完整 0  仅stat 6  失败 0
Alerts: CRITICAL 0  ERROR 0  WARNING 1
心跳已写出: SUCCESS  处理 6  失败 0
```

心跳文件（`State/ZZTEST_ViCell_heartbeat.json`）字段齐全：

```json
{
  "machine_name": "ZZTEST_ViCell",  "script_name": "vicell_ingest",
  "software_version": "v1.4.0",     "run_tag": "20260803_213611",
  "last_run_time": "2026-08-03T21:36:11.987177+08:00",
  "last_run_finished": "2026-08-03T21:36:17.411927+08:00",
  "last_success_time": "2026-08-03T21:36:17.411927+08:00",
  "backup_status": "SUCCESS", "files_processed": 6, "files_failed": 0,
  "alerts": {"CRITICAL": 0, "ERROR": 0, "WARNING": 1},
  "duration_sec": 5.4, "expected_interval_hours": 24.0, "max_silence_hours": 72.0
}
```

要求的 7 个字段（machine_name / last_run_time / last_success_time / backup_status /
files_processed / files_failed / software_version）全部存在。

### T2 — SHA-256 不一致

用测试桩令回读校验必然不一致（**不改动生产代码**，仅在测试脚本里替换 `sha256_file`）：

```
ALERT[CRITICAL] SHA256 校验不一致，已删除坏副本: /mnt/ttlab-backups/Daily/ZZT2_ViCell/data/x.txt
Data   : 新增 1  跳过 0  变化 0  失败 1
心跳已写出: FAILED  处理 1  失败 1
坏副本是否已删除（应为 0 个文件）: 0
```

行为符合铁律 5：校验不过 → 删除坏副本 → 不写 state → 告警 → 下次重来。

### T3 — 源不可访问（含一处设计改进）

卸载源挂载后运行：

```
ALERT[CRITICAL] 预检失败 -> 源未挂载: /mnt/zztest
心跳已写出: FAILED  处理 0  失败 1
```

心跳内容（**这是本次设计的核心价值所在**）：

| 字段 | 值 | 意义 |
|---|---|---|
| `backup_status` | `FAILED` | 本次运行失败 |
| `last_run_time` | `2026-08-03T21:38:05` | **跑过了** |
| `last_success_time` | `2026-08-03T21:36:17` | 保留上一次成功的时刻，未被覆盖 |

即"挂载坏了"与"程序根本没跑"在巡检看来完全不同——前者 `last_run_time` 是新的，
后者整个文件都不会更新。

> **测试中发现并修复的设计缺口**：初版实现里预检失败会 `SystemExit` 直接退出，
> **不写心跳**，导致这两种情况在心跳文件上表现一致。已修复为预检失败时先写
> `FAILED` 心跳再退出。这个缺口是测试发现的，不是设计时想到的。

结构化告警事件（`Alerts/ZZTEST_ViCell/alert_20260803.jsonl`）：

```json
{"event_time":"2026-08-03T21:38:05.369229+08:00","machine_name":"ZZTEST_ViCell",
 "severity":"CRITICAL","event_type":"MOUNT_ERROR","file_path":"/mnt/zztest",
 "message":"预检失败 -> 源未挂载: /mnt/zztest","run_tag":"20260803_213805",
 "script_version":"vicell_ingest v1.4.0"}
```

要求的 6 个字段（event_time / machine_name / severity / event_type / file_path / message）
全部存在，另含建议追加的 run_tag 与 script_version。`file_path` 从消息中自动提取成功。

### T6 — 告警命令执行失败

告警命令改为必然返回 3 并向 stderr 写错误：

```
WARNING | 告警命令返回非零(3)，告警可能未送达: 模拟接口 4xx
```

**原实现（`check=False` + 只捕获异常）对这种情况完全静默**，这正是审计 A-3 指出的问题。

### T7 — 告警风暴限流

连发 100 条告警：

| 指标 | 结果 |
|---|---|
| 耗时 | **0.01 秒** |
| 落盘条数 | **101 条**（T6 一条 + T7 一百条），一条不少 |
| 外呼次数 | **5 次**（同类去重先于总量上限生效） |
| 被限流 | 95 条，运行结束发一条汇总 |
| 分类正确性 | `('ERROR','COPY_FAILED')` × 100，`('CRITICAL','SHA256_MISMATCH')` × 1 |

原实现在同样场景下最坏需 100 × 30 秒 = 50 分钟。**告警对备份耗时的影响实测为零。**

### T8 / T9 — 心跳巡检

构造三个心跳文件（正常 / 静默 200 小时 / 最近一次失败）+ 一个 `--expect` 但不存在的机器：

```
[CRITICAL] BBB_Stale: 备份已 200.0 小时未成功（阈值 72h）……——备份可能已停止
[CRITICAL] DDD_Missing: 找不到心跳文件——该仪器可能从未运行或文件已丢失
结论：发现 2 个问题 ❌     退出码: 1
```

告警落盘为 `severity=CRITICAL  event_type=HEARTBEAT_STALE  machine=_heartbeat`。

移除异常项后：`结论：全部正常 ✅  退出码: 0`，`--quiet` 模式下无任何输出。

> 阈值取自心跳文件自身的 `max_silence_hours`，**巡检脚本无需知道任何一台仪器的排期**，
> 新增仪器零改动。

---

## 3. 已知限制与观察

| # | 事项 | 影响 | 处理建议 |
|---|---|---|---|
| L-1 | **`files_processed` 在失败时会多计** | T2 中文件校验失败但 `新增 1`、`files_processed=1`。原因是 `archive_flat_dir` 里 `stats["new"] += 1` 发生在写入尝试之前——**这是既有逻辑，非本次引入** | 心跳的 `files_failed` 字段仍准确，可据此判断。修正需动归档函数计数，建议单独作为小改动处理 |
| L-2 | 事件分类依赖关键词 | 误判只影响 `event_type` 字段，`message` 原文始终保留，未命中归 `UNCLASSIFIED` 不丢事件 | 后续可逐个调用点显式传 `event_type` |
| L-3 | 测试中新增 `RUN_FAILED` 分类 | "本次运行有 N 个失败项"原落入 `UNCLASSIFIED`，已补规则 | ✅ 已修复并验证——T4 的事件分布中出现 `('WARNING','RUN_FAILED')`，分类正确 |
| L-4 | 巡检脚本自身不跑则无声 | 监控链条最后一环仍在本机 | 设计文档 §4.5 已登记为残留风险 R-1 |

---

## 3b. T4 / T10 补测证据（Docker Linux 容器）

### T4 — NAS 不可写

环境：`--tmpfs /nas`（`ismount=True`）+ `chmod 555 /nas`，以非 root 用户运行。

```
NAS 权限: dr-xr-xr-x   ismount: True
退出码: 1
ALERT[CRITICAL] 归档写入失败: Data/f1.txt ([Errno 13] Permission denied: '/nas/Daily')
ALERT[CRITICAL] 归档写入失败: Data/f2.txt (…)
ALERT[CRITICAL] 归档写入失败: Data/f3.txt (…)
ALERT[CRITICAL] 归档写入失败: Export/f1.xls (…)
WARNING | 比对文件写入失败: [Errno 13] Permission denied: '/nas/Checksums'
--- 本地兜底告警是否生成 ---
alert_20260803.jsonl
  事件分布: Counter({('CRITICAL','NAS_UNWRITABLE'): 4, ('WARNING','RUN_FAILED'): 1})
--- NAS 上是否留下任何文件（应为 0）---
0
```

| 验证点 | 结果 |
|---|---|
| backup 行为 | 全部归档尝试失败并告警，**NAS 上零残留文件**（无半截产物） |
| **local alert 是否生成** | ✅ **生成**——NAS 完全不可写时，告警仍完整落在本地 |
| exit code | ✅ **1**（正确反映失败） |
| 事件分类 | `NAS_UNWRITABLE` × 4 + `RUN_FAILED` × 1，分类准确 |

> 本地兜底是设计中最关键的一环：**"NAS 不可写"恰恰是最需要告警、却又写不进 NAS 的场景。**
> 本测试证明该兜底真实有效，而非仅存在于设计文档中。

### T10a / T10b — 心跳写入失败不改变退出码

对应整改要求"heartbeat failure: warning / local log / 不改变 backup exit code"。

**T10a**（只有 NAS 心跳目录不可写）：

```
退出码: 0  （备份成功，应为 0）
Data   : 新增 3  跳过 0  变化 0  失败 0
心跳已写出: SUCCESS  处理 4  失败 0
归档文件数: 4   本地心跳: 1
```

**T10b**（NAS 与本地心跳**都**不可写，最坏情况）：

```
退出码: 0  （备份成功，心跳全写失败，应仍为 0）
Data   : 新增 3  跳过 0  变化 0  失败 0
WARNING | 心跳写入失败（NAS 与本地均不可写，不影响备份结果）
归档文件数: 4
✅ 心跳写入失败未改变退出码
```

| 要求 | 结果 |
|---|---|
| heartbeat failure → warning | ✅ 记 WARNING |
| heartbeat failure → local log | ✅ T10a 本地兜底生效；T10b 两处均不可写时仅告警 |
| **不改变 backup exit code** | ✅ **两种情况退出码均为 0，归档文件 4 个全部正常写入** |

---

## 4. ⚠️ 未完成事项（需恢复服务器访问后处理）

2026-08-03 约 21:40，因负责人离开公司网络，SSH 到 `172.19.0.105` 中断。
T4 已在 Docker 中补测完成（§3b）。以下两项仍待处理：

### 4.2 测试残留未清理

服务器上仍有以下测试产物，**需清理后才能认为环境干净**：

```bash
# NAS 上的测试机器目录
sudo -u flex2ingest rm -rf \
  /mnt/ttlab-backups/{Daily,Checksums,Metadata,Logs,Alerts}/ZZTEST_ViCell \
  /mnt/ttlab-backups/{Daily,Checksums,Metadata,Logs,Alerts}/ZZT2_ViCell \
  /mnt/ttlab-backups/State/ZZTEST_ViCell_heartbeat.json \
  /mnt/ttlab-backups/State/ZZT2_ViCell_heartbeat.json \
  /mnt/ttlab-backups/State/ZZTEST_ViCell_backup_state.json \
  /mnt/ttlab-backups/State/ZZT2_ViCell_backup_state.json

# 临时挂载与本地临时文件
sudo umount /mnt/zztest && sudo rmdir /mnt/zztest
sudo rm -rf /tmp/zzstate /tmp/zzhb /tmp/zzalerts /tmp/t2.py /tmp/t67.py \
            /tmp/failing_alert.sh /tmp/t8.out

# 核验残留为 0
ls -d /mnt/ttlab-backups/*/ZZ* 2>/dev/null | wc -l
```

### 4.3 v1.4.0 尚未部署

代码已提交并推送到 GitHub，但**未 pull 到 `/opt/cmc-instrument-ingest`**。
生产环境当前运行的仍是 v1.3.0（含 metadata 采集，不含告警与心跳）。

部署顺序建议：**等图片回补作业跑完再部署**。理由：`alert()` 是热路径（32 处调用），
回补作业每批重新加载脚本，中途换版本虽已测试但无必要冒险。

### 4.4 图片回补作业状态

网络中断时（21:40 左右）回补正常运行：图片目录已归档约 900+/2000，
最近批次 rc=0、零失败，三个历史图片目录已全部完成。
作业由 systemd 托管，**不依赖 SSH 连接，会自行跑完**。

恢复访问后请先检查：

```bash
systemctl is-active vicell-backfill-v2.service
tail -20 /var/lib/vicell-ingest/backfill_20260803_174226.log
grep -h MISMATCH /mnt/ttlab-backups/Checksums/C4V61257XH_ViCell/*.csv   # 应无输出
```

---

## 5. 整改结论

| 整改项 | 状态 | 说明 |
|---|---|---|
| **MD-004 告警送达** | 🟡 **Phase 1 completed — Alert generation + persistent logging.** | 告警已升级为结构化、按天留存、可查询、可统计，并修复了原实现的静默失败（A-3）与无限流（A-4）两个缺陷。<br>**Residual gap: `ALERT_CMD` notification endpoint not configured.**<br>Phase 2 待通知端点接入并完成收件验证后方可关闭。**不得宣称 MD-004 已完全关闭。** |
| **MD-005 任务未执行检测** | 🟢 **已解决**（待部署） | 心跳 + 独立巡检脚本已实现并验证（T1/T3/T8/T9/T10）。<br>**残留风险 R-1**：`heartbeat_check.py` 自身未被独立监控——检查者本身也需要被检查。<br>后续可通过 daily positive heartbeat/report 机制解决（每天固定推送结果，"连续两天没收到即视为异常"），该机制依赖 MD-004 Phase 2 的通知端点，建议一并实施 |
