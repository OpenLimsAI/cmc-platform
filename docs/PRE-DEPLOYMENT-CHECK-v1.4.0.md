# v1.4.0 部署前状态检查报告

| | |
|---|---|
| 检查日期 | 2026-08-03 |
| 目标版本 | `vicell_ingest v1.4.0` + `alerting/heartbeat v1.0.0` + `heartbeat_check v1.0.0` |
| 当前生产版本 | `v1.3.0`（commit `e0882d4`） |
| 待部署 commit | `316d945` |
| **本次范围** | **只做检查，不执行部署，不新增功能** |
| 检查环境限制 | ⚠️ **服务器 `172.19.0.105` 不可达**（负责人在公司网络外），第 1 项无法实测 |

**结论：代码侧全部就绪，四项检查通过；第 1 项（回补状态）待恢复网络后核实。**

---

## 1. 回补任务状态 —— ⚠️ 无法核实

**当前无法验证。** 本次检查时 Mac 位于 `192.168.1.167`（公司外网络），
到 `172.19.0.105:13568` 不可达。

**最后一次已知状态**（2026-08-03 约 21:40 断线前）：

| 项 | 值 |
|---|---|
| 服务 | `vicell-backfill-v2.service` — `active` |
| 图片目录进度 | 约 900+ / 2000 |
| 历史图片目录 | `XR-2025.04.27`(121) / `2025.5.14HEK-293计数图片`(73) / `1111`(395) **全部完成** |
| 最近批次 | 第 10 批 rc=0 |
| 失败/MISMATCH | **0** |

作业由 systemd 托管，**不依赖 SSH 连接**，断线不影响其继续运行。
按断线时约 9.4 秒/目录估算，剩余约 1100 个目录需约 3 小时，
即应在 2026-08-04 凌晨 00:30–01:00 前后自行结束。

### 恢复访问后必须先执行（部署的前置条件）

```bash
# ① 作业是否已结束
systemctl is-active vicell-backfill-v2.service          # 期望 inactive
tail -20 /var/lib/vicell-ingest/backfill_20260803_174226.log

# ② 结果是否完整
ls /mnt/ttlab-backups/Daily/C4V61257XH_ViCell/images | wc -l    # 期望 2000
grep -h MISMATCH /mnt/ttlab-backups/Checksums/C4V61257XH_ViCell/*.csv   # 期望无输出

# ③ 用核对工具做一次完整核验（只读）
sudo -u flex2ingest env $(grep -v '^#' /etc/instrument-ingest/vicell-ingest.env | grep -v '^$' | xargs) \
  python3 /opt/cmc-instrument-ingest/vicell/vicell_verify.py --sample 50

# ④ 清理测试残留（见 MONITORING-TEST-REPORT §4.2）
ls -d /mnt/ttlab-backups/*/ZZ* 2>/dev/null | wc -l       # 清理后期望 0
```

> **上述四步全部通过前，不得开始部署。**

---

## 2. v1.4.0 与 v1.3.0 diff —— ✅ 通过

### 2.1 改动规模

```
tools/deploy/heartbeat-check.service |  28 ++（新增）
tools/deploy/heartbeat-check.timer   |  12 ++（新增）
tools/heartbeat_check.py             | 159 ++（新增）
vicell/alerting.py                   | 278 ++（新增）
vicell/heartbeat.py                  | 132 ++（新增）
vicell/vicell-ingest.env.example     |  13 ++
vicell/vicell_ingest.py              |  86 ++, 3 --
--------------------------------------------------
                            705 insertions(+), 3 deletions(-)
```

**705 行新增中 597 行是全新独立模块**（`alerting.py` / `heartbeat.py` / `heartbeat_check.py`），
对既有采集流程零侵入。真正改到主脚本的只有 86 行，且集中在四处。

### 2.2 主脚本的四处改动

| 位置 | 改动 | 风险 |
|---|---|---|
| 模块导入 | 增加 2 个 `import` | 无 |
| 配置区 | 增加 5 个环境变量 + `ALERTS_DIR` | 无 |
| `alert()` | 内部增加 `_SINK.emit()` 分支；**签名与日志输出格式不变** | 低——`emit()` 内部全捕获，绝不抛出 |
| `main()` | 初始化告警槽（preflight 前）、preflight 失败时写 FAILED 心跳、末尾写心跳 | 低——均为旁路 |

### 2.3 约束核验（grep 证据，非人工声明）

```bash
$ git diff e0882d4..HEAD -- vicell/vicell_ingest.py | \
    grep -E "^[-+].*(read_source_stable|sha256_file|hashlib\.sha256|os\.fsync|\
                      os\.replace|os\.utime|write_atomic|MetadataCollector|mc\.collect)"
✅ 无输出 —— 复制、校验、metadata 采集路径一行未改

$ ... | grep -E '^[-+].*alert\("'
✅ 无输出 —— 32 处 alert() 调用点全部原样

$ ... | grep -E "^[-+].*(COMPARE_HEADER|Relative_Path|default_state|data_files|image_dirs)"
✅ 无输出 —— Checksums 表头与 state 结构未动
```

`Daily/` 目录结构亦未改动；新增的 `Alerts/` 与 `State/*_heartbeat.json` 均为**新路径**。

---

## 3. systemd unit —— ✅ 通过（有 1 项需注意）

### 3.1 两个单元的关键配置

| 项 | `vicell-ingest.service` | `heartbeat-check.service` |
|---|---|---|
| `Type` | `oneshot` | `oneshot` |
| `User/Group` | `flex2ingest` | `flex2ingest` |
| `EnvironmentFile` | `/etc/instrument-ingest/vicell-ingest.env` | 同左（前缀 `-`，缺失不报错） |
| `RequiresMountsFor` | `/mnt/vicell /mnt/ttlab-backups` | `/mnt/ttlab-backups` |
| `ProtectSystem` | `strict` | `strict` |
| `ReadWritePaths` | `/var/lib/vicell-ingest /mnt/ttlab-backups` | 同左 |
| `SuccessExitStatus` | 默认 | **`0 1`** |
| 触发 | 每日 `02:30`（`RandomizedDelaySec=300`） | 每日 `09:00`（`RandomizedDelaySec=120`） |
| `Persistent` | `true` | `true` |

### 3.2 沙箱与写入路径一致性（自动核验）

`ProtectSystem=strict` 下所有写入必须落在 `ReadWritePaths` 内。逐项核对：

| 新代码写入的路径 | 允许 |
|---|---|
| `/var/lib/vicell-ingest/alerts` | ✅ |
| `/mnt/ttlab-backups/Alerts` | ✅ |
| `/mnt/ttlab-backups/State` | ✅ |
| `/mnt/ttlab-backups/Metadata` | ✅ |
| `/mnt/ttlab-backups/{Daily,Checksums,Logs}` | ✅ |

### 3.3 设计取舍说明

- **`heartbeat-check.service` 用 `SuccessExitStatus=0 1`**：巡检发现异常时退出码为 1，
  但那是"正常发现了问题"，不是"服务启动失败"。若让 systemd 判为 `failed`，
  服务会长期处于 failed 状态，反而掩盖真正的启动问题。
- **`vicell-ingest.service` 的 `RequiresMountsFor` 不含 `/mnt/vicell-old/*`**：
  历史源是一次性回补用的，日常运行带 `--no-legacy` 不读它们。
  故意不列入——历史源哪天断了不该让日常增量整趟不跑。
- **日常参数带 `--no-legacy` 但不带 `--no-metadata`**：metadata 采集每日随增量进行。

### 3.4 ⚠️ 需注意：`--expect` 目前只列了 Vi-CELL

```
ExecStart=… /opt/cmc-instrument-ingest/tools/heartbeat_check.py --expect C4V61257XH_ViCell
```

FLEX2 尚未接入心跳，故未列入。**这意味着"FLEX2 备份停了"目前巡检发现不了。**
属 MD-009 一致性缺口，FLEX2 接入后需在此追加一行 `--expect T281240040C_Nova`。

---

## 4. Rollback 方案 —— ✅ 已实测验证

### 4.1 一级回滚：只改配置，不动代码

```bash
sudo sed -i 's/^VICELL_ALERTS_ENABLED=1/VICELL_ALERTS_ENABLED=0/;\
             s/^VICELL_HEARTBEAT_ENABLED=1/VICELL_HEARTBEAT_ENABLED=0/' \
  /etc/instrument-ingest/vicell-ingest.env
```

**实测结果**（本地 CIFS 环境，2026-08-03）：

| 验证项 | 期望 | 实测 |
|---|---|---|
| 退出码 | 0 | **0** ✅ |
| 归档文件数 | 4 | **4** ✅ |
| SHA 比对非 `MATCH` 行 | 0 | **0** ✅ |
| 产生 `Alerts/` 目录 | 否 | **否** ✅ |
| 产生心跳文件 | 否 | **否** ✅ |
| 产生本地告警目录 | 否 | **否** ✅ |
| metadata 采集 | 仍正常 | **仍正常**（1 个 CSV）✅ |

**即一级回滚可完整退回 v1.3.0 行为，且不影响 metadata 采集能力。**

### 4.2 二级回滚：回退代码

```bash
cd /opt/cmc-instrument-ingest && git checkout e0882d4     # v1.3.0
sudo systemctl disable --now heartbeat-check.timer
```

### 4.3 数据侧无需回滚

`Alerts/` 与 `State/*_heartbeat.json` 均为**新增路径**，
不触碰 `Daily/` / `Checksums/` / `State/*_backup_state.json` 中的既有内容。
回滚后这些新文件留在原地不影响任何既有流程，可保留亦可删除。

---

## 5. 生产部署 checklist

完整清单见 **`docs/DEPLOYMENT-CHECKLIST-v1.4.0.md`**（9 步部署 + 24 小时确认 + 回滚）。
本次检查后需补充的两点已在下方列出。

### 5.1 部署前置门槛（必须全绿）

- [ ] 回补作业 `inactive` 且日志显示正常结束
- [ ] `images` 目录数 = 2000
- [ ] 全部 Checksums 无 `MISMATCH`
- [ ] `vicell_verify.py --sample 50` 通过
- [ ] 测试残留清理完毕（`ZZ*` 计数为 0）
- [ ] 记录当前 commit 以备回滚（应为 `e0882d4`）

### 5.2 ⚠️ 本次检查新发现，需补进部署说明

**告警文件只在"有告警"时才产生。**

`AlertSink` 仅在 `emit()` 被调用时才创建目录与文件。一次完全正常的运行
**不会**产生 `Alerts/<机器名>/alert_YYYYMMDD.jsonl`。

这与 `Checksums/` 的既有约定不同——后者刻意在空跑时也写一个只含表头的文件，
作为"当天确实跑过"的证据。

| 影响 | 说明 |
|---|---|
| 是否缺陷 | **否**。"跑过没有"由心跳文件回答，且心跳内含 `alerts` 各级别计数 |
| 风险 | 运维/检查人员若只看 `Alerts/` 目录，可能把"没有告警"误读为"没有运行" |
| 处置 | **本阶段不改**（不新增功能）。部署清单第 D 步的验证项措辞需调整，见下 |

原第 D 步写的是"`Alerts/…jsonl` 内容合理"，若当天无告警则文件不存在，会误判为异常。
**改为**：

> - [ ] 若存在 `Alerts/C4V61257XH_ViCell/alert_YYYYMMDD.jsonl` 则内容合理；
>       **文件不存在属正常**（当天无告警），此时以心跳文件中的
>       `alerts: {"CRITICAL":0,"ERROR":0,"WARNING":n}` 为准

> 后续若认为需要与 `Checksums/` 保持一致（空跑也留证），可作为独立小改动实施，
> 本阶段不做。

### 5.3 部署后仍未闭环（与本次检查无关，但需持续记录）

| # | 事项 |
|---|---|
| E-1 | **`ALERT_CMD` 外呼端点未配置 → MD-004 停留在 Phase 1**，告警落盘但无人被通知 |
| E-2 | `heartbeat_check.py` 自身未被独立监控（残留风险 R-1） |
| E-3 | FLEX2 未接入告警/心跳，巡检 `--expect` 未含 FLEX2 |
| E-4 | `instrument_reader` 密码未轮换 |
| E-5 | `files_processed` 在失败时会多计（既有逻辑，`files_failed` 准确） |

---

## 附：本次检查执行的验证动作

| 动作 | 方式 | 结果 |
|---|---|---|
| 服务器可达性 | `nc -z 172.19.0.105 13568` | ❌ 不可达 |
| diff 规模与内容 | `git diff --stat` + 逐行审阅 | ✅ |
| 三项约束（复制/校验/调用点/表头/state） | `git diff \| grep` | ✅ 全部无命中 |
| systemd 单元配置 | 逐项比对 | ✅ |
| 写入路径与 `ReadWritePaths` 一致性 | 脚本自动核对 | ✅ 7/7 |
| **一级回滚有效性** | **本地 CIFS 环境实跑** | ✅ 7/7 项符合预期 |
| 告警文件生成条件 | 代码走查 + 实跑对照 | ⚠️ 发现差异，已记录 |
| 本地回归套件 | `bash tests/local_cifs_suite.sh` | ✅ 12/12 通过 |
