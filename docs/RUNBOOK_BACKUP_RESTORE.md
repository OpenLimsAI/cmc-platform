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
| 频率 | 每天 02:00 UTC（host crond） |
| 格式 | pg_dump custom (`-F c`)，压缩等级 6 |
| 在线保留 | 30 天（host 本地） |
| 离线归档 | ≥ 7 年（药品上市后追溯期；走对象存储 / 磁带） |
| 文件命名 | `cmab_mdm_<hostname>_YYYYMMDD_HHMM.dump` |
| 存储位置 | `${BACKUP_DIR:-/var/lib/cmab-mdm/backups}` |

> 注：本期（Phase 4.B-6）只交付**本地**备份脚本 + 30 天保留窗口。**离线归档**（S3/MinIO / 磁带）走运维侧 SOP，未在脚本范围内；建议在脚本运行后另起 rsync/aws-cli 推送步骤。

## 3. 备份执行

### 3.1 手工跑一次（验证脚本可用）

```bash
# dev 环境（写到 项目根/backups/）
make backup

# 生产环境（host 上跑，写到 BACKUP_DIR）
sudo BACKUP_DIR=/var/lib/cmab-mdm/backups bash scripts/backup_db.sh
```

### 3.2 配置 cron（生产）

```bash
# /etc/cron.d/cmab-mdm-backup（root）
# 每天 UTC 02:00 跑全备
0 2 * * * root /opt/cmab-mdm-platform/scripts/backup_db.sh >> /var/log/cmab-mdm-backup.log 2>&1
```

或 systemd timer（更易管理失败重试）：

```ini
# /etc/systemd/system/cmab-mdm-backup.service
[Unit]
Description=CMAB MDM Portal PostgreSQL backup
After=docker.service

[Service]
Type=oneshot
EnvironmentFile=/etc/cmab-mdm/.env.prod
ExecStart=/opt/cmab-mdm-platform/scripts/backup_db.sh

# /etc/systemd/system/cmab-mdm-backup.timer
[Unit]
Description=Daily CMAB MDM backup at 02:00 UTC

[Timer]
OnCalendar=*-*-* 02:00:00 UTC
Persistent=true

[Install]
WantedBy=timers.target
```

```bash
sudo systemctl enable --now cmab-mdm-backup.timer
sudo systemctl list-timers cmab-mdm-backup.timer
```

### 3.3 监控

- `${BACKUP_DIR}/backup.log` 每行带 ISO8601 时间戳
- 推荐挂 Prometheus blackbox / loki 告警：`backup.log` 24h 内无 `备份完成` 字符则告警
- 文件大小突变（< 80% 上次大小）应人工核查

## 4. 恢复执行

### 4.1 灾难恢复 / 完整回滚

```bash
# 1. 停业务流量（nginx 切到维护页 或 容器停 backend）
docker compose -f deploy/docker-compose.prod.yml stop backend

# 2. 恢复（容器内 pg_restore）
sudo BACKUP_DIR=/var/lib/cmab-mdm/backups \
  bash scripts/restore_db.sh cmab_mdm_<hostname>_YYYYMMDD_HHMM.dump

# 3. 校验
#    alembic 校验用一次性 backend 容器（此时 backend 已 stop，不能 docker exec）
docker compose -f deploy/docker-compose.prod.yml run --rm backend alembic current   # = 备份时 head
#    ⚠️ 禁止对恢复后的生产库执行 pytest（生产镜像无 tests/ 与 pytest，且会写入测试数据污染恢复结果）。
#    如需代码回归测试：仅在 UAT / 隔离 test DB 中另行执行 make test-be，不作为生产恢复数据完整性校验。
docker exec cmab-mdm-postgres psql -U postgres -d cmab_mdm -c "
  SELECT
    (SELECT count(*) FROM srs.substance) AS substances,
    (SELECT count(*) FROM prs.project) AS projects,
    (SELECT count(*) FROM ars.asset) AS assets,
    (SELECT count(*) FROM mm.material) AS materials,
    (SELECT count(*) FROM audit.audit_log) AS audit_logs
  ;
"

# 4. 业务侧抽检：随机 5 条 substance / project / asset / material 详情 vs 备份时间点
#    必要时联系 CMC R&D 负责人核对关键资产

# 5. 恢复业务流量
docker compose -f deploy/docker-compose.prod.yml start backend
```

### 4.2 单业务事故回滚（不推荐用本 SOP）

错删某条 substance / 改坏 audit_log 等单点事故，**不应用本 SOP 全库回滚**，应：
- 走 audit.change_history 反向重建（Phase 5 自助回滚 UI）
- 或单表 `pg_restore -t schema.table` 精准恢复

## 5. 恢复演练（建议 Q1/Q3 各跑一次）

| 步骤 | 验证项 |
|---|---|
| 1 | 从生产备份选最近 1 周内任意一份 dump |
| 2 | 在 UAT/Staging 上跑 restore_db.sh |
| 3 | `docker compose run --rm backend alembic current` 显示备份时 head（不是当前 head） |
| 4 | 代码回归：仅在 UAT / 隔离 test DB 另行 `make test-be` 全量通过（不对恢复库直接跑 pytest） |
| 5 | 关键业务计数与备份时间点 ±0%（无失踪行） |
| 6 | 关键资产抽检（5 条物质/项目/资产/物料）字段逐字段比对 |
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
