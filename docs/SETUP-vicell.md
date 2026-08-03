# Vi-CELL XR Stage 1 部署说明

数据源事实见 [`source-survey-vicell.md`](./source-survey-vicell.md)（2026-08-03 实测）。
本文只讲怎么在 Linux（172.19.0.105）上把它跑起来。

| 项 | 值 |
|---|---|
| 源 | `//10.0.13.36/Vi-Cell$`（**SMB 2.1**，Win7，账户 `instrument_reader`，非管理员） |
| 机器名 | `C4V61257XH_ViCell`（= 工作站主机名 + 厂商，对齐 NAS `Daily/` 既有目录） |
| 归档目标 | `/mnt/ttlab-backups/Daily/C4V61257XH_ViCell/{data,export,images}` |
| 运行用户 | `flex2ingest`（见下方说明） |

---

## 1. 凭据

```bash
sudo mkdir -p /etc/instrument-ingest
read -s -p "instrument_reader 密码: " P; echo
printf 'username=instrument_reader\npassword=%s\n' "$P" | sudo tee /etc/instrument-ingest/vicell.cred >/dev/null
unset P
sudo chmod 600 /etc/instrument-ingest/vicell.cred
sudo chown root:root /etc/instrument-ingest/vicell.cred
```

> 用 `read -s` 输入，密码不回显、不进 shell 历史。**绝不把密码写进命令行或提交进仓库**（铁律 6）。
> `instrument_reader` 是所有小仪器共用的统一只读账户，权限收口靠"每台机器只授权那一个共享"。

---

## 2. 挂载

```bash
sudo mkdir -p /mnt/vicell
```

`/etc/fstab` 追加 —— **`vers=2.1` 不可改成 3.0**，这台 Win7 不支持，会 `mount error(95)`：

```
# Vi-CELL XR 源 —— ro 不可省略，它是保护仪器数据的第一道锁
//10.0.13.36/Vi-Cell$  /mnt/vicell  cifs  ro,credentials=/etc/instrument-ingest/vicell.cred,vers=2.1,uid=flex2ingest,gid=flex2ingest,file_mode=0440,dir_mode=0550,iocharset=utf8,nofail,_netdev,soft,noserverino  0  0
```

`fstab` 里 `$` 不需要转义。挂载并自检：

```bash
sudo mount -a
mount | grep vicell          # 应显示 vers=2.1、ro
sudo -u flex2ingest touch /mnt/vicell/.probe   # 必须报 Read-only file system
```

NAS（`/mnt/ttlab-backups`）已由 FLEX2 部署时挂好，无需重复。

---

## 3. 运行用户

**沿用 `flex2ingest`**（uid 999）。理由：NAS 共享是以 `uid=flex2ingest` 挂载的，
`Daily/` 下所有归档文件的属主都是它；换用户就得重挂 NAS 并改所有属主，收益为零。

> 名字带 `flex2` 有点误导（它现在其实是"仪器归档"这个身份）。
> 要正名的话得连同 NAS 挂载的 `uid=` 一起改，属独立的运维任务，别顺手做。

⚠️ **用别的用户跑会失败**：以 `prometheus` 直接跑会在写入时全部 `Permission denied`
（2026-08-03 首跑踩过；好在是写入前失败，不产生半截文件）。

本地状态副本目录：

```bash
sudo mkdir -p /var/lib/vicell-ingest
sudo chown flex2ingest:flex2ingest /var/lib/vicell-ingest
```

---

## 3b. 挂载清单（七个共享，2026-08-03 已写入 fstab）

| 挂载点 | 共享 | 用途 |
|---|---|---|
| `/mnt/vicell` | `Vi-Cell$` | 主源（`Data` / `Export` / `Images`），日常增量只读这个 |
| `/mnt/vicell-old/dimg` | `VC-DImg$` | `D:\Vi-Cell 计数图像`，2026-07 之前图片的**原始位置** |
| `/mnt/vicell-old/img2025` | `VC-Img2025$` | `E:\XR-2025.04.27` |
| `/mnt/vicell-old/img2024` | `VC-Img2024$` | `E:\2025.5.14HEK-293计数图片` |
| `/mnt/vicell-old/img2023` | `VC-Img2023$` | `E:\1111` |
| `/mnt/vicell-old/history` | `VC-History$` | `E:\计数仪历史数据` |
| `/mnt/vicell-old/app` | `VC-App$` | `E:\ViCELLXR`，只取根目录的配置与审计文件 |

后六个只在一次性回补时需要。回补完成后，日常运行可加 `--no-legacy`；
挂载留着无妨（`nofail`，断了不影响开机）。

配置文件 `/etc/instrument-ingest/vicell-ingest.env`（不含凭据，样例见 `vicell/vicell-ingest.env.example`）。

---

## 4. 首跑顺序（别跳）

```bash
cd /opt/cmc-instrument-ingest
ENV="$(grep -v '^#' /etc/instrument-ingest/vicell-ingest.env | grep -v '^$' | xargs)"

# ① 空跑，只看清单不写文件（约 1 分钟）
sudo -u flex2ingest env $ENV python3 vicell/vicell_ingest.py --dry-run

# ② 先把 Data/Export/Config 落袋（约 1.1 GB，十几分钟）
sudo -u flex2ingest env $ENV python3 vicell/vicell_ingest.py --no-images --no-legacy

# ③ 图片分批回补（约 150 GB）——用回补脚本，跑完一批状态即落盘，无新增自动停
sudo systemd-run --uid=flex2ingest --unit=vicell-backfill \
  --setenv=VICELL_BATCH=50 --setenv=VICELL_MAX_BATCHES=80 \
  /usr/local/sbin/vicell-backfill.sh
```

`/usr/local/sbin/vicell-backfill.sh` 每批调用一次采集脚本（`--image-dir-limit`），
批次之间比对状态文件条目数，**无新增即自动停止**；日志落在 `/var/lib/vicell-ingest/backfill_*.log`。

跑完检查：

- `Daily/C4V61257XH_ViCell/{data,export,images,legacy,config}` 文件数
- `Checksums/C4V61257XH_ViCell/*_SHA256_Compare_*.csv` 里 `match_status` 是否全 `MATCH`
- 抽查若干文件的修改时间是否为**原始生成时间**（不是归档时间）
- `State/C4V61257XH_ViCell_backup_state.json` 是否已记账

> 实际执行记录：2026-08-03 完成 Data 18899 + Export 36814（55713 行校验全 `MATCH`、零失败）；
> 图片回补排在当晚 20:00 分批执行。

---

## 5. 日常托管（systemd）

单元文件在 `vicell/deploy/`，**回补完成并核对通过后再启用**：

```bash
sudo cp /opt/cmc-instrument-ingest/vicell/deploy/vicell-ingest.{service,timer} /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now vicell-ingest.timer
systemctl list-timers vicell-ingest.timer
```

要点：

- **每日一趟即可**（02:30）：这台仪器没有"每晚覆盖、不抓就丢"的数据源（不像 FLEX2 的
  Database 备份必须赶在覆盖前抓），频次不紧张。排在 FLEX2 的 01:00 之后，两台不抢 NAS 带宽。
- 日常参数带 `--no-legacy`：历史目录是一次性回补的，不必每天重扫。
- `RequiresMountsFor` 只列 `/mnt/vicell` 和 `/mnt/ttlab-backups`——历史源断了不该让日常整趟不跑。
- ⚠️ 用别的用户跑会在写入时全部 `Permission denied`（归档区属主是 `flex2ingest`）。

---

## 6. 已知待办

见 [`source-survey-vicell.md`](./source-survey-vicell.md) §7。其中影响部署的两条：

- 旧图片/旧历史数据（`E:\XR-2025.04.27`、`E:\2025.5.14HEK-293计数图片`、`E:\1111`、
  `E:\计数仪历史数据`）还在共享外，需在工作站上开只读共享或移进 `E:\Vi-Cell\` 才能接入。
- `instrument_reader` 密码需轮换（2026-08-03 截图误带出明文）。
