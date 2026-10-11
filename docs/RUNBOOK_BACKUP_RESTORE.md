# CMAB MDM Portal 备份与恢复 SOP

| 项目 | 内容 |
|---|---|
| 文档编号 | RUNBOOK-BACKUP-001 |
| 版本 | V1.0 |
| 状态 | 生效（需 QA / IT 安全部门会签） |
| 适用 | 生产 + UAT 环境的 PostgreSQL 全库备份与恢复 |
| 合规 | 21 CFR Part 11 §11.10(c) 数据保护与检索；GxP 数据完整性 ALCOA+ |

---

## 1. 目标

1. 保证 cmab_mdm 全库每日有可恢复的离线备份
2. 灾难恢复 / 系统迁移 / 误操作回滚时能在 60 分钟内恢复到最近 24h 内任意一个备份点
3. 提供可审计的备份/恢复执行记录，满足 CSV 验证 IQ/OQ 阶段证据要求

## 2. 备份策略

| 维度 | 设定 |
|---|---|
| 频率 | 每天 02:00 Asia/Shanghai（systemd timer，最多随机延迟 5 分钟） |
| 格式 | pg_dump custom (`-F c`)，压缩等级 6 |
| 在线保留 | 30 天（host 本地） |
| 离线归档 | ≥ 7 年（药品上市后追溯期；走对象存储 / 磁带） |
| 文件命名 | `cmab_mdm_<hostname>_YYYYMMDD_HHMM.dump` |
| 存储位置 | Linux 默认 `${HOME}/cmc_backups/mdm`；可用 `BACKUP_DIR` 覆盖 |

> 注：本期（Phase 4.B-6）只交付**本地**备份脚本 + 30 天保留窗口。**离线归档**（S3/MinIO / 磁带）走运维侧 SOP，未在脚本范围内；建议在脚本运行后另起 rsync/aws-cli 推送步骤。

## 3. 备份执行

### 3.1 手工跑一次（验证脚本可用）

```bash
# dev 环境（写到 项目根/backups/）
make backup

# Linux 原生生产环境（按 systemd 服务身份运行，自动读取 backend/.env）
sudo -u prometheus env BACKUP_MODE=native bash scripts/backup_db.sh
```

### 3.2 配置 systemd timer（生产）

仓库已经提供 systemd service + timer，以它们为唯一生产调度方式：

```ini
# /etc/systemd/system/cmab-mdm-backup.service
[Unit]
Description=CMAB MDM Portal PostgreSQL backup
After=postgresql.service

[Service]
Type=oneshot
User=prometheus
WorkingDirectory=/opt/cmab-mdm-platform
Environment=RETENTION_DAYS=30
ExecStart=/opt/cmab-mdm-platform/scripts/backup_db.sh

# /etc/systemd/system/cmab-mdm-backup.timer
[Unit]
Description=每天 02:00 备份 CMAB MDM 数据库

[Timer]
OnCalendar=*-*-* 02:00:00
Persistent=true
RandomizedDelaySec=300

[Install]
WantedBy=timers.target
```

```bash
bash deploy/linux/install_systemd.sh
sudo systemctl list-timers cmab-mdm-backup.timer
```

上述片段对应仓库中的 `deploy/systemd/cmab-mdm-backup.service` 与 `.timer`；不要手工维护第二份单元内容。
timer 按主机本地时区解释 `02:00`；生产主机应配置为 `Asia/Shanghai`。备份文件名和
`backup.log` 的时间戳仍由脚本统一使用 UTC，便于跨主机核对。

### 3.3 监控

- `${BACKUP_DIR}/backup.log` 每行带 ISO8601 时间戳
- 推荐挂 Prometheus blackbox / loki 告警：`backup.log` 24h 内无 `备份完成` 字符则告警
- 文件大小突变（< 80% 上次大小）应人工核查

## 4. 恢复执行

### 4.1 灾难恢复 / 完整回滚

> **重要：**当前 `scripts/restore_db.sh` 和 `make restore` 只实现了 Mac Docker 模式，
> 禁止在 Linux 原生生产环境执行。生产恢复由 DBA 使用原生 PostgreSQL 工具完成；以下命令中的
> `<dump绝对路径>` 必须先核对文件名、大小和校验值。

```bash
# 1. nginx 切维护页后停止后端
sudo systemctl stop cmab-backend

# 2. 原生 PG :5433 上踢连接、重建空库
sudo -u postgres psql -p 5433 -d postgres -v ON_ERROR_STOP=1 -c \
  "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname='cmab_mdm' AND pid<>pg_backend_pid();"
sudo -u postgres dropdb -p 5433 --if-exists cmab_mdm
sudo -u postgres createdb -p 5433 -O cmab_app -E UTF8 cmab_mdm

# 3. 使用 cmab_app 恢复；密码通过受控 .pgpass/交互提示提供，不写进命令历史
pg_restore -h 127.0.0.1 -p 5433 -U cmab_app -d cmab_mdm \
  --no-owner --no-privileges --exit-on-error <dump绝对路径>

# 4. 校验 migration（应等于备份时 head；当前仓库 head 是 0062_eqp_total_weight）
( cd backend && .venv/bin/alembic current )

# 5. 只读数据抽检
psql -h 127.0.0.1 -p 5433 -U cmab_app -d cmab_mdm -c "
  SELECT
    (SELECT count(*) FROM srs.substance) AS substances,
    (SELECT count(*) FROM prs.project) AS projects,
    (SELECT count(*) FROM ars.asset) AS assets,
    (SELECT count(*) FROM mm.material) AS materials,
    (SELECT count(*) FROM audit.audit_log) AS audit_logs
  ;
"

# 6. 业务侧抽检：随机 5 条 substance / project / asset / material / equipment 详情 vs 备份时间点
#    必要时联系 CMC R&D 负责人核对关键资产

# 7. 恢复服务和流量
sudo systemctl start cmab-backend
curl -fsS --noproxy '*' http://127.0.0.1:5100/mdm/api/v1/health
```

禁止对恢复后的生产库执行 pytest。代码回归只能在隔离环境通过 `make test-be` 运行。

### 4.2 单业务事故回滚（不推荐用本 SOP）

错删某条 substance / 改坏 audit_log 等单点事故，**不应用本 SOP 全库回滚**，应：
- 走 audit.change_history 反向重建（Phase 5 自助回滚 UI）
- 或单表 `pg_restore -t schema.table` 精准恢复

## 5. 恢复演练（建议 Q1/Q3 各跑一次）

| 步骤 | 验证项 |
|---|---|
| 1 | 从生产备份选最近 1 周内任意一份 dump |
| 2 | 在隔离 UAT/Staging 恢复：Docker 环境可用 `restore_db.sh`；Linux 原生环境按 §4.1 执行 |
| 3 | `cd backend && .venv/bin/alembic current` 显示备份时 head（不是盲目要求当前 head） |
| 4 | 代码回归：仅在 UAT / 隔离 test DB 另行 `make test-be` 全量通过（不对恢复库直接跑 pytest） |
| 5 | 关键业务计数与备份时间点 ±0%（无失踪行） |
| 6 | 关键资产抽检（5 条物质/项目/资产/物料/设备）字段逐字段比对 |
| 7 | 演练记录归档到 GxP 文档系统（含执行人、时间、结果） |

## 6. 已知限制 / 未来工作

| 项 | 当前 | 计划 |
|---|---|---|
| 离线归档（对象存储 / 磁带） | 不在脚本范围 | 部署侧 SOP，Phase 4.D CSV 验证前 IT 安全部门提供 |
| 增量备份 / WAL 归档（PITR） | 未实现 | Phase 5；当前仅每日全备 |
| 备份加密 | 不在脚本范围 | 走文件系统层 LUKS / 对象存储 SSE |
| 备份完整性自动验证 | 仅 size > 0 | Phase 5 加 `pg_restore --list` 静默校验 + 月度自动 restore CI |

## 7. 参考

- API §3.7：审计追踪
- DM §6：audit schema（备份必含）
- 21 CFR Part 11 §11.10(c)：可获取性 / 可读性 / 可检索性
- PostgreSQL 文档：[Backup and Restore](https://www.postgresql.org/docs/16/backup.html)


## 8. 逐份自动隔离恢复验证（P16，2026-10-11实现中）

负责人已确认：每次Linux每日备份成功后，自动在独立Docker PostgreSQL16中恢复验证，验证完成清理临时数据库，保留报告；不使用Mac现有真实数据或Linux原生正式实例作恢复目标。本项目当前仍按原型运维工具推进，不新增GMP会签流程。

- `scripts/backup_db.sh`仅在每日服务设置`BACKUP_VERIFY_ENABLED=1`时启用：同只读导出snapshot基线与pg_dump，保存应用表/行数、结构、迁移版本、扩展及大对象范围；普通手工/发布保护性备份默认沿用原流程。基线不可取得时回退正常全库备份，不能宣称完整性通过。
- 新脚本`scripts/mdm_backup_verification.py`只恢复到自身新建、带唯一标签的容器。固定镜像内容摘要、无宿主端口、network=none、1 CPU/512MiB/600秒，不挂正式数据目录、配置或Docker socket。恢复使用严格错误退出；校验备份SHA、同快照基线与恢复后清单/计数/结构；对象所有者/ACL、服务器角色口令、整站功能与外部文件不在本次验证范围。
- `deploy/linux/install_backup_verification.py --image <审核过的sha256内容摘要>`由受控root安装service/path及每日服务环境drop-in；不启动正式备份、不改变02:00 timer。验证请求目录为`/var/lib/cmab-mdm-backup-verify/requests`，完整报告在同根的`reports`；报告90天，dump仍原30天，基线侧文件随dump保留期清理。
- 脱敏摘要导出到`/var/lib/cmc-platform-monitor/mdm-verification`，目录prometheus属主、opsmonitor-evidence组只读；monitor不读dump内容，不拥有Docker控制权。备份结束和验证结束分别提示只读采集，执行与验证状态分开。
- service异常停止仍通过受控ExecStopPost仅清理本项目带唯一ID的容器；残留、空间不足、超时、读取/关联失败不能显示验证通过。失败摘要不暴露原始SQL/业务行或连接串；SHA/检查步骤/耗时与检查结论在报告内追溯。
- 先对合成库测试并发写入/损坏文件/对账失败，再对一份已有Linux备份恢复；历史dump没有同快照基线时，只标实际恢复通过、完整性证据不足。每日自动链路等待发布后下一次自然02:00备份单独验收，不主动重跑正式备份。

本节为已确认实现说明，最终两仓SHA、真实恢复结果、容量实测、部署及自然链路状态以platform-monitor的`docs/RELEASE_20261011_BACKUP_VERIFY.md`为发布记录；尚未取得的结果不得标通过。V1.1 Word派生设计文件不在本次修改范围。
