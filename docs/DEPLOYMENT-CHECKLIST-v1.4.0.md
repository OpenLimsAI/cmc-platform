# v1.4.0 部署清单（告警 + 心跳）

| | |
|---|---|
| 目标版本 | `vicell_ingest v1.4.0` + `alerting v1.0.0` + `heartbeat v1.0.0` + `heartbeat_check v1.0.0` |
| 当前生产版本 | **v1.3.0**（含 metadata 采集，不含告警与心跳） |
| 对应整改项 | MD-004（Phase 1）、MD-005 |
| 前置状态 | 代码已提交并推送 GitHub；**尚未 pull 到 `/opt`** |
| 部署窗口要求 | **等 Vi-CELL 图片回补作业跑完再部署** |
| 部署前检查 | 见 `docs/PRE-DEPLOYMENT-CHECK-v1.4.0.md`（2026-08-03 已执行，4/5 项通过，回补状态待核实） |

> 为什么要等回补跑完：`alert()` 是 32 处调用的热路径，回补作业每批重新加载脚本，
> 中途换版本虽已充分测试但没有必要冒险。回补是一次性任务，等它结束几小时不影响任何事。

---

## A. 修改文件列表

### 新增

| 文件 | 说明 |
|---|---|
| `vicell/alerting.py` | 统一异常事件模型 + AlertSink（落盘 / 分类 / 限流 / 外呼） |
| `vicell/heartbeat.py` | 心跳写入 |
| `tools/heartbeat_check.py` | **独立**巡检脚本（MD-005 本体） |
| `tools/deploy/heartbeat-check.service` | systemd 服务单元 |
| `tools/deploy/heartbeat-check.timer` | systemd 定时器（每日 09:00） |
| `docs/BACKUP_MONITORING_DESIGN.md` | 设计文档 |
| `docs/MONITORING-TEST-REPORT-2026-08-03.md` | 测试报告 |
| `docs/DEPLOYMENT-CHECKLIST-v1.4.0.md` | 本文件 |

### 修改

| 文件 | 改动 |
|---|---|
| `vicell/vicell_ingest.py` | 版本 v1.3.0 → v1.4.0；`alert()` 内部改走 AlertSink；`main()` 初始化告警槽（**在 preflight 之前**）、末尾写心跳；预检失败时也写 `FAILED` 心跳 |
| `vicell/vicell-ingest.env.example` | 新增 5 个配置项 |
| `CHANGELOG.md` | v1.4.0 条目 |

### 明确未改动（可用 diff 复核）

`read_source_stable` / `sha256_file` / `write_atomic` / `os.fsync` / `os.replace` / `os.utime`
/ metadata 采集调用点 / `Checksums/` 9 列表头 / `Daily/` 目录结构 / state JSON 结构
/ **32 处 `alert()` 调用点的签名与参数**。

---

## B. 部署前检查

- [ ] **确认回补作业已结束**
  ```bash
  systemctl is-active vicell-backfill-v2.service     # 应为 inactive
  tail -5 /var/lib/vicell-ingest/backfill_20260803_174226.log
  ```
- [ ] **确认回补结果无异常**
  ```bash
  grep -h MISMATCH /mnt/ttlab-backups/Checksums/C4V61257XH_ViCell/*.csv   # 应无输出
  ls /mnt/ttlab-backups/Daily/C4V61257XH_ViCell/images | wc -l            # 应为 2000
  ```
- [ ] **清理测试残留**（测试报告 §4.2 有完整命令）
  ```bash
  ls -d /mnt/ttlab-backups/*/ZZ* 2>/dev/null | wc -l    # 清理后应为 0
  ```
- [ ] 备份当前生产脚本以便回滚
  ```bash
  cd /opt/cmc-instrument-ingest && git rev-parse --short HEAD    # 记下当前 commit
  ```

---

## C. 部署步骤

- [ ] **1. 拉取代码**
  ```bash
  cd /opt/cmc-instrument-ingest && git pull --ff-only
  python3 vicell/vicell_ingest.py --version        # 应显示 v1.4.0
  ```

- [ ] **2. 补充配置项**（`/etc/instrument-ingest/vicell-ingest.env`）
  ```bash
  sudo tee -a /etc/instrument-ingest/vicell-ingest.env >/dev/null <<'EOF'
  VICELL_ALERTS_ENABLED=1
  VICELL_HEARTBEAT_ENABLED=1
  VICELL_EXPECTED_INTERVAL_HOURS=24
  VICELL_MAX_SILENCE_HOURS=72
  VICELL_ALERT_MAX_EXTERNAL=20
  EOF
  ```
  > `VICELL_ALERT_CMD` 保持为空——外呼端点尚未提供（见 §E）。

- [ ] **3. 准备本地告警目录**
  ```bash
  sudo mkdir -p /var/lib/vicell-ingest/alerts
  sudo chown -R flex2ingest:flex2ingest /var/lib/vicell-ingest
  ```

- [ ] **4. 空跑验证**（不写任何文件，`--dry-run` 下告警落盘自动禁用）
  ```bash
  cd /opt/cmc-instrument-ingest
  sudo -u flex2ingest env $(grep -v '^#' /etc/instrument-ingest/vicell-ingest.env | grep -v '^$' | xargs) \
    python3 vicell/vicell_ingest.py --dry-run
  ```
  预期：正常输出汇总，无异常，**不产生心跳与告警文件**。

- [ ] **5. 首次真跑**（增量，正常情况下只有当天新样品）
  ```bash
  sudo -u flex2ingest env $(grep -v '^#' /etc/instrument-ingest/vicell-ingest.env | grep -v '^$' | xargs) \
    python3 vicell/vicell_ingest.py --no-legacy
  echo "退出码: $?"
  ```
  预期：退出码 0，日志出现 `Alerts: ...` 与 `心跳已写出: SUCCESS`。

- [ ] **6. 核验心跳文件**
  ```bash
  cat /mnt/ttlab-backups/State/C4V61257XH_ViCell_heartbeat.json
  ```
  必须包含：`machine_name` / `last_run_time` / `last_success_time` / `backup_status`
  / `files_processed` / `files_failed` / `software_version`（应为 `v1.4.0`）
  / `expected_interval_hours` / `max_silence_hours`。

- [ ] **7. 安装巡检 timer**
  ```bash
  sudo cp /opt/cmc-instrument-ingest/tools/deploy/heartbeat-check.{service,timer} /etc/systemd/system/
  sudo systemctl daemon-reload
  sudo systemctl enable --now heartbeat-check.timer
  systemctl list-timers heartbeat-check.timer
  ```

- [ ] **8. 手工跑一次巡检确认**
  ```bash
  sudo -u flex2ingest python3 /opt/cmc-instrument-ingest/tools/heartbeat_check.py \
    --expect C4V61257XH_ViCell
  echo "退出码: $?"     # 刚跑过备份，应为 0
  ```

- [ ] **9. 启用日常采集 timer**（此前一直是手工/回补脚本触发）
  ```bash
  sudo cp /opt/cmc-instrument-ingest/vicell/deploy/vicell-ingest.{service,timer} /etc/systemd/system/
  sudo systemctl daemon-reload
  sudo systemctl enable --now vicell-ingest.timer
  systemctl list-timers vicell-ingest.timer      # 应显示次日 02:30
  ```

---

## D. 部署后 24 小时内确认

- [ ] 次日 02:30 的采集自动跑过：`journalctl -u vicell-ingest.service --since today`
- [ ] 心跳 `last_success_time` 已更新为当日
- [ ] 09:00 巡检已跑过且退出码 0：`journalctl -u heartbeat-check.service --since today`
- [ ] 若存在 `Alerts/C4V61257XH_ViCell/alert_YYYYMMDD.jsonl` 则内容合理；
      **⚠️ 文件不存在属正常**——告警文件只在"有告警"时才产生，一次完全正常的运行不会生成它。
      此时以心跳文件中的 `alerts: {"CRITICAL":0,"ERROR":0,"WARNING":n}` 为准
      （与 `Checksums/` 空跑也写表头的约定不同，详见 `PRE-DEPLOYMENT-CHECK-v1.4.0.md` §5.2）
- [ ] 备份耗时未因告警明显变长（对比部署前的日志时长）

---

## E. 部署后仍未闭环的事项

| # | 事项 | 状态 |
|---|---|---|
| E-1 | **`ALERT_CMD` 外呼端点未配置** | **MD-004 停留在 Phase 1**：告警产生并留存，但**没有人会被主动通知**。需提供企业微信机器人 / 邮件端点，配置后发测试告警并确认收到，才能进入 Phase 2 |
| E-2 | `heartbeat_check.py` 自身未被独立监控 | 残留风险 R-1。后续用 daily positive report 机制解决（依赖 E-1 的端点） |
| E-3 | FLEX2 未接入告警与心跳 | 目前只有 Vi-CELL 有心跳；巡检的 `--expect` 也只列了 Vi-CELL。属 MD-009 一致性问题 |
| E-4 | `instrument_reader` 密码未轮换 | 2026-08-03 截图外泄，与本次部署无关但仍未处理 |
| E-5 | `files_processed` 在失败时会多计 | 既有逻辑缺陷（测试报告 L-1），`files_failed` 仍准确 |

---

## F. 回滚方案

告警与心跳都是**旁路功能**，出问题有两级回滚：

**一级（不改代码，改配置即可）**
```bash
sudo sed -i 's/^VICELL_ALERTS_ENABLED=1/VICELL_ALERTS_ENABLED=0/;s/^VICELL_HEARTBEAT_ENABLED=1/VICELL_HEARTBEAT_ENABLED=0/' \
  /etc/instrument-ingest/vicell-ingest.env
```
关闭后行为与 v1.3.0 完全一致（`alert()` 退回直接调用，不落盘、不写心跳）。

**二级（回退代码）**
```bash
cd /opt/cmc-instrument-ingest && git checkout <部署前记下的 commit>
sudo systemctl disable --now heartbeat-check.timer
```

> 无需回滚数据：`Alerts/` 与 `*_heartbeat.json` 都是新增路径，
> 不影响 `Daily/` / `Checksums/` / `State/*_backup_state.json` 中的既有内容。
