# 告警与心跳机制测试报告

| | |
|---|---|
| 测试日期 | 2026-08-03 |
| 被测对象 | `vicell/alerting.py` v1.0.0、`vicell/heartbeat.py` v1.0.0、`tools/heartbeat_check.py` v1.0.0、`vicell/vicell_ingest.py` v1.4.0 |
| 对应整改项 | **MD-004**（告警送达）、**MD-005**（任务未执行检测） |
| 设计依据 | `docs/BACKUP_MONITORING_DESIGN.md` |
| 测试隔离 | 全部使用独立机器名（`ZZTEST_ViCell` / `ZZT2_ViCell`）与 tmpfs 假源，不触碰生产数据 |

**结论：9 项计划测试中 8 项通过，1 项（T4）因网络中断未能执行。**

> ⚠️ **两项未完成事项见文末 §4，必须在恢复服务器访问后处理**：T4 补测、测试残留清理。

---

## 1. 测试结果总览

| # | 测试 | 结果 | 关键证据 |
|---|---|---|---|
| T1 | 正常运行 → 心跳生成 | ✅ 通过 | 心跳字段完整，`backup_status=SUCCESS`，处理 6 失败 0 |
| T2 | SHA-256 不一致 | ✅ 通过 | `CRITICAL`，坏副本已删除（归档区 0 文件），心跳 `FAILED` |
| T3 | 源不可访问 | ✅ 通过 | `CRITICAL` / `MOUNT_ERROR`，心跳 `FAILED` 且 `last_success_time` 保留 |
| T4 | NAS 不可写 | ⬜ **未执行** | 网络中断，见 §4 |
| T5 | metadata 采集失败 | ✅ 通过 | 随 T1 一并覆盖：tmpfs 源 → `stat-only` 6 条，备份照常完成 |
| T6 | `ALERT_CMD` 执行失败 | ✅ 通过 | 返回非零被记录为 WARNING（**原实现完全静默**） |
| T7 | 告警风暴限流 | ✅ 通过 | 100 条告警耗时 **0.01 秒**，外呼 5 次，落盘 101 条一条不少 |
| T8 | 心跳巡检发现异常 | ✅ 通过 | 三类异常全部检出，退出码 1，告警落盘 |
| T9 | 心跳巡检正常 | ✅ 通过 | 退出码 0，`--quiet` 下无输出 |

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
| L-3 | 测试中新增 `RUN_FAILED` 分类 | "本次运行有 N 个失败项"原落入 `UNCLASSIFIED`，已补规则 | 已修复，但**该修复未经服务器验证**（网络中断），见 §4 |
| L-4 | 巡检脚本自身不跑则无声 | 监控链条最后一环仍在本机 | 设计文档 §4.5 已登记为残留风险 R-1 |

---

## 4. ⚠️ 未完成事项（需恢复服务器访问后处理）

2026-08-03 约 21:40，因负责人离开公司网络，SSH 到 `172.19.0.105` 中断。以下两项未完成：

### 4.1 T4（NAS 不可写）未执行

计划方法：以只读 tmpfs 作为 NAS 挂载点运行，验证产生 `NAS_UNWRITABLE` 事件、
**本地兜底告警文件仍能写出**、备份以失败退出且心跳记为 `FAILED`。

本地兜底路径是设计中的关键一环（"NAS 不可写"恰恰是最需要告警却写不进 NAS 的场景），
**未经验证不应视为已实现**。

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
| **MD-004 告警送达** | 🟡 **部分解决** | 告警已升级为结构化、按天留存、可查询、可统计，并解决了原实现的静默失败与无限流两个缺陷。**但 `ALERT_CMD` 仍未配置外呼目标，仍然没有人会被主动通知。** 在拿到通知渠道之前不应宣称 MD-004 已闭环 |
| **MD-005 任务未执行检测** | 🟢 **已解决**（待部署） | 心跳 + 独立巡检脚本已实现并验证；残留风险 R-1（巡检自身不跑）已登记 |
