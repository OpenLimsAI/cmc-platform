# Legacy 文档

本目录保留前身项目 **tt-lims-platform** 的历史文档，仅供溯源参考。

- `migration-log.md` — 旧库 `cmc_data_platform` 从 Win Server 迁移到 Docker 的记录；新项目使用 `cmc_analytics` + `cmc_mdm`，不再适用
- `systemd/` — 旧项目在 Linux 正式环境的 systemd user units 归档；新项目部署方式由 CMC 平台运维统一规划，未确定前不重复落盘

新架构文档：
- 顶层 `README.md` / `CLAUDE.md` — 项目说明
- `mart_contracts.md` — 看板与 `cmc_analytics.mart` 的接口
- `mdm_contracts.md` — admin 与 `cmc_mdm` 的接口
