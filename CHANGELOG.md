# Changelog

本文件记录 `cmc-instrument-ingest` 的变更。遵循 [Keep a Changelog](https://keepachangelog.com/zh-CN/) 风格。
版本号跟随各采集脚本内的 `SCRIPT_VERSION`（改动逻辑必须同步递增并在此登记，见 `CLAUDE.md` 风格约定）。

---

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
