## migrations/

Dashboard 自有的 DDL 迁移脚本(不是 alembic,只是有序号的 SQL 文件,手动执行)。

本目录脚本目标库为 `cmc_analytics`(Dashboard 单一连接库)。看板对 `cmab_mdm`(公司级 MDM,管 substance/asset/project/auth.user 等)和 `cmc_rd`(LIMS 原始库)纯只读,不在此持有任何 DDL。

### 命名规则

```
mdm_NNN_<动词>_<对象>.sql
```

`NNN` 为顺序号(三位补零),`<动词>` 用 create / alter / drop / grant 等;前缀 `mdm_` 标识改的是 `cmc_analytics.mdm` schema。

### 执行方式

按序号手动跑,执行前做 pg_dump 全库快照(已在 `backups/`)。每次只跑一个文件:

```bash
docker exec -i rd_pg psql -U postgres -d cmc_analytics < migrations/mdm_001_create_schema.sql
```

执行后在文件末尾追加一行 `-- applied: YYYY-MM-DD HH:MM by <operator>`,作为人工 audit 轨迹。

### 当前进度

| 序号 | 文件 | 应用时间 |
|---|---|---|
| 001 | `mdm_001_create_schema.sql` | 2026-05-18 00:30 |
| 002 | `mdm_002_create_test_method.sql` | 2026-05-18 00:30 |
| 003 | `mdm_003_create_personnel.sql` | 2026-05-18 00:30 |
| 004 | `mdm_004_migrate_data.sql` | 2026-05-18 00:35 |
| 005 | `mdm_005_repoint_mart_views.sql` | 2026-05-18 00:40 |

### 历史背景:为什么把主数据放在 cmc_analytics 而不是 cmab_mdm?

短答:method/personnel 是 LIMS 的域内 reference data,只有本看板一个消费方;放在公司级 MDM 是过度工程。决策见 2026-05-18 commit 历史。

`docs/mdm_contracts.md` 里的"cmc_mdm 独立库"方案已作废 —— 旧的 `rd_pg.cmc_mdm` 占位库会在 Phase 5' 改名隔离 + 一月后 DROP。
