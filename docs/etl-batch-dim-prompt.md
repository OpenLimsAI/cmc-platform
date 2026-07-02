# 给 rd-lucullus-etl 的实现 Prompt：构建批次维度（staging.stg_batch → mart.dim_batch）

> 把下面「PROMPT 开始 … PROMPT 结束」之间的全部内容，粘贴到在 `rd-lucullus-etl` 目录下新开的 Claude Code 会话里。

---

## PROMPT 开始

你在 `rd-lucullus-etl` 项目里工作。请先读这些文件，严格沿用项目已有约定：`CLAUDE.md`、`architecture.md`、`schema.sql`、`lucullus_sync_reference_tables.py`（重点看它的配置加载、连接、`build_upsert_sql`、`start_etl_run`/`finish_etl_run`/`log_load_error` 记账模式）。沟通与注释用中文、简短、少术语。

### 一、目标

新增一个 **PG → PG 的转换步骤**：读取已经同步进 `cmc_rd.raw_rd_usp_lucullus` 的批次原始数据，把 Lucullus 的批次名解析成规整字段，写入 **`cmc_analytics`** 的一张「批次维度表」，供看板做多字段筛选、并作为将来与 Nova / Vi-Cell / LIMS 数据整合的连接地基。

这一步**不碰 Oracle**（纯 PG→PG），因此可以直接在 Mac 测试环境跑通验证。

### 二、关键数据事实（已核实）

- 批次原始信息在 `cmc_rd.raw_rd_usp_lucullus.process_src`（每行一个批次；关键列 `source_instance, procid, procname, starttime, endtime, duration, timeunit`）。`procname` 就是那串批次名。
- `signal_timeseries.reactor_name` 是**权威罐号**（每个 `(source_instance, procid)` 对应一个罐号，用 `(source_instance, procid)` 索引取 `DISTINCT reactor_name` 很快）。`process_src` 里**没有**罐号。
- `signal_timeseries.batch_id` 目前 = `procname`（未清洗）。本步骤产出的 `batch_key` 才是清洗后的标准批次键。
- **`cmc_analytics` 是和 `cmc_rd` 同一台 PostgreSQL 实例（rd_pg:5432）上的另一个数据库**。PG 不能跨数据库 join，所以要开**两条连接**：从 `cmc_rd` 读、往 `cmc_analytics` 写。
- 生产线编号来自设备字典 `cmc_rd.meta.equipment_lookup`（是 `cmc_analytics.dim.equipment_master` 的本地只读缓存）。**目前它是空的**（0 行）——见「前提」一节。**严禁字符串解析 `source_instance`**。

### 三、批次名解析规范（负责人已确认）

分隔符可能是下划线 `_` 或空格，按 `[_\s]+` 一起切分。字段从左到右：

1. **项目编号 `project_code`**：数字，**必须当字符串保留前导零**（"0092" ≠ "92"）。例：016 / 015 / 0092。
2. **批号 `batch_number`**：形如 `R` + 4 位数字（正则 `^R\d{4}$`）。前 2 位是年份、后 2 位是流水号 →
   `batch_year = 2000 + 前两位`，`batch_seq = 后两位`。例：R2501 → 2025 年第 01。
3. **实验目的 `experiment_purpose`**：字母串，**可有可无**（有的批次没有这段）。例：EOPC / HCP。
4. **罐号（末段）**：仅用于**校验**，不作为权威。罐号有效集合：`A1–A10、B1–B8、R1–R4、C1`。
   注意用正则区分「批号 R+4位」和「罐号 R+1位（R1–R4）」，别混。

真实样例（都要能正确解析）：
```
0092 R2501 EOPC A1 A1   → project=0092 batch=R2501 purpose=EOPC 末段罐=A1（A1 重复，去重）
015 R2502 HCP A4        → 015 / R2502 / HCP / A4
0072_R2601_EOPC_A9_A9   → 0072 / R2601 / EOPC / A9（下划线分隔）
016_R2604_A8            → 016 / R2604 / (无 purpose) / A8
```

### 四、batch_key 与层级

- **单罐发酵**（一个 `procid` = 一条曲线 = 一个罐的一次运行）：这是本表的粒度，**每 `(source_instance, procid)` 一行**。
- **标准批次键** `batch_key = project_code_batch_number_bioreactor_code`，例 `0092_R2501_A1`。
  - `bioreactor_code` 取**权威 `reactor_name`**（不是名字末段）。
  - 若关键字段缺失导致拼不出，`batch_key` 置空并在 `parse_status` 标记。
- 说明：同一个「项目+批号」常横跨多个罐并行（如 `515 R2501` 在 A1/A3/A4 各一次），所以罐号必须进 key。将来 Nova/Vi-Cell 的取样也记录到罐，用同一个 `batch_key` 对齐。

### 五、目标表（在 `cmc_analytics`）

分两层（对齐白皮书 staging→mart）：

**1) `cmc_analytics.staging.stg_batch`（本步骤写入的实体表，每单罐运行一行）**，建议列：

| 列 | 说明 |
|---|---|
| source_system TEXT | 'lucullus' |
| source_instance TEXT | 如 rd_ws01_usp_lucullus_01 |
| procid BIGINT | Lucullus 内部批次号 |
| batch_key TEXT | 项目_批号_罐（拼不出则 NULL） |
| project_code TEXT | 保留前导零 |
| batch_number TEXT | R2501 |
| batch_year INT / batch_seq INT | 从批号拆 |
| experiment_purpose TEXT | 可空 |
| bioreactor_code TEXT | 权威 reactor_name |
| line_code TEXT | join equipment_lookup 得（缺登记则 NULL + 标记） |
| name_reactor TEXT | 名字末段解析出的罐（去重） |
| reactor_match BOOLEAN | name_reactor 是否与 bioreactor_code 一致 |
| parse_status TEXT | 见下方枚举 |
| procname_raw TEXT | 原始批次名，审计用 |
| starttime / endtime TIMESTAMPTZ | 取自 process_src |
| duration_days DOUBLE PRECISION | 建议 endtime-starttime 换算成天；取不到再用 process_src.duration+timeunit |
| built_by_run_id BIGINT / built_at TIMESTAMPTZ | 记账 |
| 主键 | (source_instance, procid) |

`parse_status` 枚举建议：`ok` / `ok_no_purpose` / `reactor_mismatch`（名字末段罐 ≠ 权威罐号，需人工核查）/ `suspect_test`（疑似测试批，如 procname 里全是 test/tset/纯数字等）/ `unparseable`（拼不出项目或批号）。**解析失败绝不能让整批中断**，坏行记 `parse_status` + 写 `meta.load_error_log`。

**2) `cmc_analytics.mart.dim_batch`（看板消费的维度）**：v1 先做成 `stg_batch` 上的**视图**，暴露干净字段（batch_key, project_code, batch_number, batch_year, experiment_purpose, bioreactor_code, line_code, source_instance, procid, procname_raw, starttime, endtime, duration_days, parse_status）。将来多数据源汇入时再改成物化表。

### 六、治理边界（重要，别踩线）

1. **不改 `cmc_rd` 原始层**：本步骤对 `cmc_rd` 只读。
2. **建表 DDL 走 `cmc-schema-migrations`（命令 `dbmig`）——它才是权威**，不要在 ETL 脚本里 `CREATE TABLE` 建 `cmc_analytics` 的正式表。请把上面 `staging.stg_batch` 表和 `mart.dim_batch` 视图写成 Alembic 迁移放进 `cmc-schema-migrations`（若本会话不便跨库操作，就把完整 DDL 产出给负责人，由他在那个仓库建迁移）。本仓库 `schema.sql` 只是 `cmc_rd` 的参考副本，不管 `cmc_analytics`。
3. 本仓库 `CLAUDE.md` 现写「本 ETL 只写 cmc_rd」——本步骤**扩展了写入范围到 `cmc_analytics`(staging/mart)**，请**同步更新该说明**，并确认 ETL 账号在 `cmc_analytics` 有写权限（见开放问题）。
4. `meta.etl_run` / `meta.load_error_log` 仍写在 `cmc_rd.meta`，沿用现有记账函数；新 job 名建议 `lucullus_build_batch_dim`，并在 `schema.sql` 的 seed 里登记（`meta.etl_job`）。

### 七、新脚本规范

新增独立脚本（如 `lucullus_build_batch_dim.py`），沿用 `lucullus_sync_reference_tables.py` 的骨架：
- 配置从 `.env` 读；**新增** `cmc_analytics` 连接参数（如 `PG_ANALYTICS_DBNAME=cmc_analytics`，host/port 复用）。
- 两条 psycopg 连接：`cmc_rd`（读 process_src / signal_timeseries / meta.equipment_lookup、写 meta 记账）＋ `cmc_analytics`（写 stg_batch）。
- 流程：`start_etl_run` → 读 process_src 全量（或按 source_instance）→ 逐批解析（Python 正则）→ 取权威罐号 → join equipment_lookup 取 line_code → 组装行 → `build_upsert_sql` 风格 UPSERT 进 `stg_batch`（`ON CONFLICT (source_instance, procid) DO UPDATE`，幂等）→ `finish_etl_run`。
- 坏行走 `log_load_error`，单批失败不中断整体（`PARTIAL_FAILED`）。
- CLI 建议：`--source-instance`（可选，限定某工作站）、`--procid`（可选，单批调试）。

### 八、前提：登记设备字典（拿 line_code）

`equipment_lookup` 现在是空的。请在 `cmc_analytics.dim.equipment_master` 里登记这两台（并确保同步/缓存到 `cmc_rd.meta.equipment_lookup`），字段参考 `schema.sql` 的 `meta.equipment_lookup`：
- `rd_ws01_usp_lucullus_01` → line_code=`WS01`, stage=`usp`, vendor_key=`lucullus`
- `rd_ws02_usp_lucullus_01` → line_code=`WS02`, stage=`usp`, vendor_key=`lucullus`

（equipment_master 也走 `cmc-schema-migrations`/数据平台维护。若本会话拿不到，可先把 line_code 逻辑留空并在 parse_status/日志标记「line 未登记」，登记后重跑即可。）

### 九、测试（Mac 测试环境，纯 PG→PG，无需 Oracle）

Mac 本地 `cmc_rd`（Docker 容器 `rd_pg`，localhost:5432）已灌入 4 个真实样本批次：
- ws01 procid 457（`0092 R2501 EOPC A1 A1`）、460（`015 R2502 HCP A4`）
- ws02 procid 222（`0072_R2601_EOPC_A9_A9`）、226（`016_R2604_A8`）

这 4 批覆盖了空格/下划线两种分隔符、罐号重复、有/无实验目的等情况。用它们验证解析结果正确（project/batch/year/seq/purpose/reactor/batch_key/reactor_match），并确认幂等重跑不产生重复。注意：Mac 上参考表和 equipment_lookup 是空的，所以罐号从 `signal_timeseries.reactor_name` 取；line_code 在未登记设备字典前会是空，属正常。

### 十、交付物

1. 新脚本 `lucullus_build_batch_dim.py`（含解析、校验、记账、幂等 UPSERT、CLI）。
2. `cmc-schema-migrations` 的迁移（或完整 DDL 交付）：`staging.stg_batch` 表 + `mart.dim_batch` 视图（+ 如需，equipment_master 两行登记）。
3. `.env.example` 增加 `cmc_analytics` 连接变量；`meta.etl_job` seed 增加新 job；更新 `CLAUDE.md` / `architecture.md` 中「只写 cmc_rd」的表述。
4. 在 Mac 测试环境跑通并给出 4 个样本批次的解析结果核对。

### 十一、动手前请先和负责人确认（开放问题）

1. **写权限**：ETL 账号 `lucullus_etl` 目前对 `cmc_analytics` 只有 SELECT（按白皮书 grants）。写 `staging.stg_batch` 需要 INSERT/UPDATE 授权——是给 `lucullus_etl` 补授，还是换 `lims_admin` 账号？
2. **迁移归属**：`cmc_analytics` 的表由 `cmc-schema-migrations` 建。本会话是直接在那个仓库写迁移，还是只产出 DDL 交付？
3. **dim_batch 形态**：v1 用视图可否（简单），还是一开始就要物化表？

## PROMPT 结束
