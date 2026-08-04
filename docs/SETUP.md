# FLEX2 Stage 1 部署说明

数据源事实（2026-07-15 实测，非推测）：

| 项 | 值 |
|---|---|
| 源 | `//10.0.13.66/Export`（SMB 3.1.1，账户 `nova_export_reader`，非管理员） |
| Analyzer ID | `T281240040C` |
| 主数据源 | `Results/SampleResultsT281240040C<YYYY>-<Month>.csv`（月度累积，逐次文件的严格超集） |
| 次数据源 | `Results/QcResultsT281240040C<YYYY>-<Month>.csv` |
| 灾备归档 | `Database/Backup_<ts>/`（每晚 23:30 覆盖，**只留一份**） |
| 编码 | UTF-8，无 BOM |
| 时间 | 24 小时制，`M/D/YYYY  H:MM:SS`（日期与时间之间**两个空格**） |
| 已忽略 | 逐次 CSV（~280 个，列序与月度不同）、`Report/`（人工导的 PDF） |

---

## 1. 凭据文件

```bash
sudo mkdir -p /etc/flex2
sudo tee /etc/flex2/flex2.cred >/dev/null <<'EOF'
username=nova_export_reader
password=在这里填密码
EOF
sudo chmod 600 /etc/flex2/flex2.cred
sudo chown root:root /etc/flex2/flex2.cred
```

NAS 凭据同理放 `/etc/flex2/nas.cred` —— 用**写账户 `backupuser`**（对 `TTLab_Backups` 有写权限；
别用 Vi-CELL 那个只读的 `etl_reader`）：

```bash
sudo tee /etc/flex2/nas.cred >/dev/null <<'EOF'
username=backupuser
password=在这里填密码
EOF
sudo chmod 600 /etc/flex2/nas.cred
sudo chown root:root /etc/flex2/nas.cred
```

---

## 2. 挂载

创建运行用户与目录：

```bash
sudo useradd -r -s /usr/sbin/nologin flex2ingest
sudo mkdir -p /mnt/flex2 /mnt/ttlab-backups /var/lib/flex2-ingest
sudo chown flex2ingest:flex2ingest /var/lib/flex2-ingest
```

`/etc/fstab` 追加：

```
# FLEX2 源 —— ro 不可省略，它是保护仪器数据的第一道锁
//10.0.13.66/Export  /mnt/flex2  cifs  ro,credentials=/etc/flex2/flex2.cred,vers=3.0,uid=flex2ingest,gid=flex2ingest,file_mode=0440,dir_mode=0550,iocharset=utf8,nofail,_netdev,soft,noserverino  0  0

# NAS 归档区（可写；写账户 backupuser）。归档落到其下 Daily/<机器名>/
//10.0.6.100/ttlab_backups  /mnt/ttlab-backups  cifs  rw,credentials=/etc/flex2/nas.cred,vers=3.0,uid=flex2ingest,gid=flex2ingest,iocharset=utf8,nofail,_netdev,soft  0  0
```

```bash
sudo mount -a
mountpoint /mnt/flex2 && mountpoint /mnt/ttlab-backups
```

**验证只读锁真的生效**（别跳过）：

```bash
sudo -u flex2ingest touch /mnt/flex2/x   # 必须报 Read-only file system
```

脚本启动时也会自己再验一次，可写就直接中止。

---

## 3. 安装

放 `/opt`，属主 `prometheus`（与其它项目一致；`prometheus` 有免密 sudo）：

```bash
sudo git clone git@github.com:qingcheng81/cmc-instrument-ingest.git /opt/cmc-instrument-ingest
sudo chown -R prometheus:prometheus /opt/cmc-instrument-ingest
sudo chmod 0755 /opt/cmc-instrument-ingest/flex2/flex2_ingest.py
# ⚠️ 忽略文件权限位变化，否则 chmod 后 git pull 会因 mode change 冲突而 Aborting
git -C /opt/cmc-instrument-ingest config core.fileMode false

# 配置文件：设为 root:flex2ingest 640，运行用户（flex2ingest）才读得到；systemd EnvironmentFile 也靠它
sudo cp /opt/cmc-instrument-ingest/flex2/flex2-ingest.env.example /etc/flex2-ingest.env
sudo chown root:flex2ingest /etc/flex2-ingest.env
sudo chmod 0640 /etc/flex2-ingest.env
# 默认值已对齐现网（机器名 T281240040C_Nova、挂载点 /mnt/ttlab-backups 等），按需微调
```

以后更新：`cd /opt/cmc-instrument-ingest && sudo -u prometheus git pull`。

告警脚本（示例，改成你们的企业微信/邮件通道）：

```bash
sudo tee /usr/local/bin/flex2-alert.sh >/dev/null <<'EOF'
#!/bin/bash
# $1=级别 $2=消息
logger -t flex2-ingest "[$1] $2"
# curl -s -X POST "https://你的webhook" -H 'Content-Type: application/json' \
#   -d "$(jq -nc --arg t "[$1] $2" '{msgtype:"text",text:{content:$t}}')"
EOF
sudo chmod 755 /usr/local/bin/flex2-alert.sh
```

---

## 4. 首跑（按顺序，别跳步）

用运行用户 flex2ingest 跑、source 配置、python3 显式调用（不依赖脚本 x 位/shebang）：

```bash
run() { sudo -u flex2ingest bash -c "set -a; source /etc/flex2-ingest.env; set +a; python3 /opt/cmc-instrument-ingest/flex2/flex2_ingest.py $*"; }

run --dry-run --backfill   # a. 空跑，只探测和校验，不写 NAS
run --backfill             # b. 确认输出无误后回填历史（一次搞定）
run                        # c. 之后每日增量（timer 会这么跑）
```

首跑 `--dry-run --backfill` 应看到 `status: SUCCESS`；月度文件若有"多行宽"会打 `WARNING` 但照常归档
（v1.2.0 起，见 CLAUDE.md 铁律 1/5），只有真损坏才 `ERROR` 不归档。

冷备逐次文件（可选，一次性，~280 个）：加 `--per-event`。

---

## 5. 定时任务

⚠️ **FLEX2 没有自己的定时器了**（2026-08-05 起）。本机所有仪器共用两个采集单元，
由 `tools/run-ingest.sh` 逐台调用采集脚本。完整时刻表与排班理由见
[`INGEST-STANDARD.md` §9.1](./INGEST-STANDARD.md#91-运行时刻表本机唯一权威改时刻先改这里)。

安装（两台仪器一次装完，不必按设备分别安装）：

```bash
sudo cp /opt/cmc-instrument-ingest/tools/deploy/instrument-ingest-{day,night}.{service,timer} \
        /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now instrument-ingest-day.timer instrument-ingest-night.timer
systemctl list-timers 'instrument-ingest-*'
```

FLEX2 侧只需保证 `/etc/flex2-ingest.env` 存在——它被两个单元用 `EnvironmentFile=` 读入。

只跑 FLEX2 一台（排障用，不走定时器）：

```bash
sudo systemd-run --uid=flex2ingest --gid=flex2ingest --wait --pty \
  -p EnvironmentFile=/etc/flex2-ingest.env \
  /opt/cmc-instrument-ingest/tools/run-ingest.sh night flex2
```

**逐次文件一直是开的**：`run-ingest.sh` 给 FLEX2 固定加 `--per-event`
（原先是 `flex2-ingest.service.d/per-event.conf` drop-in，已随旧单元一起删除）。

> 为什么必须开：逐次文件**不是**月度的冗余（见 `source-survey-flex2.md` §8.3），
> 且今后用「从仪器重新导出」修历史错位数据，产出的文件落在 `Results/` 根下，
> 不开这个开关就**不会被归档**，只存在于仪器电脑上。

---

## 6. 产出的目录结构

```
/mnt/ttlab-backups/                          ← NAS 共享根 TTLab_Backups（多设备共用）
├── Daily/T281240040C_Nova/                  ← 数据（每设备一个目录，内部镜像仪器 Export）
│   ├── Results/                             ← 对应仪器 Export/Results
│   │   ├── Monthly/2026-07/SampleResultsT281240040C2026-July__snap_20260716T010000.csv
│   │   │                   QcResultsT281240040C2026-July__snap_20260716T010000.csv
│   │   └── PerEvent/2026-07/...             ← 仅 --per-event 时
│   ├── Database/Backup_2026-07-15_233019/DatabaseBackup.dbb
│   │                                       Persist.dbb
│   └── Report/                             ← NAS 侧预建，程序不写（人工 PDF，忽略）
├── Checksums/T281240040C_Nova/T281240040C_Nova_SHA256_Compare_v1_1_0_<ts>.csv  ← 每次运行一个，审计记录
├── Logs/T281240040C_Nova/T281240040C_Nova_ingest_<ts>.log
└── State/T281240040C_Nova_backup_state.json
```

> 记账目录（Checksums / Logs / State）放 NAS 根级、按机器名分，**与 ViCell / Biacore 等其它设备完全一致**。

**Stage 2（ETL，独立 repo `rd-nova-etl`）只读 `Daily/T281240040C_Nova/Results/Monthly/` 下最新的快照，不回连 FLEX2。**

---

## 7. 容量估算

| | 每天 | 每年 |
|---|---|---|
| 月度快照 | ~300 KB | ~110 MB |
| Database 备份 | ~15 MB | ~5.4 GB |

Database 是大头，但它是 Nova 自己不保留的东西 —— 5 GB/年买一份完整历史，很划算。
将来紧张了再加保留策略（如月末那份长期留、日常留 90 天）。

---

## 8. 几个设计决定，写在这里免得以后忘了为什么

1. **每天存快照，不是覆盖同一个文件** —— 月度文件整月都在长。存快照除了防丢，还有个额外好处：**历史行如果被改写或消失，脚本会立刻告警**（`last_data_rows` 比对）。这是很硬的数据完整性证据。

2. **不拿"样品数据多久没更新"做告警** —— 实测这台仪器会连续停机 2-3 周（2026-01-23→02-05 空 13 天，02-10→03-03 空 21 天）。用它告警只会天天误报。改用 Database 备份的新鲜度，它每晚固定跑。

3. **校验不过就不归档** —— 宁可告警缺一天，也不能把坏数据写进"底本"。

4. **`.dbb` 只归档不解析** —— 实测是 7z 容器，但是 Nova 私有格式、无文档、无厂商承诺、固件升级可能就变。在 GMP 环境里把管道建在这上面没法做验证。它的定位是灾备保险。

5. **法规定位** —— 法规意义上的原始记录是 FLEX2 机内数据库与审计追踪，CSV 是副本，NAS 归档是副本的副本。本系统定位为**分析数据源 + 业务备份**，不是 Part 11 原始记录保存系统。这一条写进 SOP 能显著降低验证等级。别主动揽责任。

---

## 9. 待办

- [ ] 查清 C:\ 根目录那个 `生化分析仪数据备份 - Shortcut`（2025-08-18）是谁做的、在备份什么 —— 别撞车
- [ ] 问 Nova：FLEX2 是否提供 OPC 接口（Bridge PC 上有 `OPC_` 目录）可供第三方取数
- [ ] 问 Nova：`.dbb` 是否有官方读取方式
- [ ] SOP：操作员录入规范。实测 Sample ID 下划线/横杠混用（`FBC_SN_D2` vs `FBC-SN-D0`），
      Vessel/Batch/Cell Type 有时被拼成一个字段填进 Batch ID。这是培训问题，程序修不了，
      但会直接影响将来的趋势分析
- [ ] Bridge PC 仍启用 SMB1（nmap 可见），报 IT 做安全登记
