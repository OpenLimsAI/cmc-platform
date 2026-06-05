# CMAB MDM Portal 数据迁移演练 SOP

| 项目 | 内容 |
|---|---|
| 文档编号 | RUNBOOK-MIGRATION-001 |
| 版本 | V1.0 |
| 适用 | 首次生产部署 + 后续 alembic 升级 + 跨环境数据迁移（dev → UAT / UAT → 生产）|
| 合规 | GAMP 5 / 21 CFR Part 11 §11.10(a) 数据完整性 / EU Annex 11 §4.5 数据迁移 |
| 当前 head | `0044_eqp_identifiers`（共 44 个 migration，2026-06-05） |

---

## 0. 用途与范围

本 SOP 用于：
1. **首次生产部署**：从空 PG 实例完整执行 0001→0044 全部 migration + baseline seed
2. **alembic 升级部署**：现有 head 升级到新 head（举例 0044 → 0045）
3. **跨环境迁移**：dev / UAT / 生产之间用 pg_dump + pg_restore 整体迁移（结构 + 数据）
4. **基线快照演练**：UAT/Staging 环境上跑一次完整 reset → migrate → seed → 抽检，确保灾难恢复路径可走

**不在范围**：业务级数据导入（substance / project 批量从 Excel 灌入）— 走独立 ETL SOP（Phase 5 staging.substance_import_* 表）。

---

## 1. Migration 全景表

| 序号 | revision | 文件 | 内容（简） |
|---|---|---|---|
| 1 | 0001_init_schemas | 2026_05_11_1200 | meta 序列函数 + auth schema 全部表（user/role/permission/user_role/role_permission/login_history） + srs.substance/protein/xref |
| 2 | 0002_audit_baseline | 2026_05_11_1400 | audit.audit_log + change_history + e_signature + fn_audit_trigger v1 |
| 3 | 0003_srs_triggers | 2026_05_11_1430 | srs 三表 audit trigger + assign_code 触发器 + sequence_hash 触发器 |
| 4 | 0004_backfill_sequence_hash | 2026_05_11_1500 | 历史 substance_protein 行回填 sequence_hash |
| 5 | 0005_audit_trigger_v2 | 2026_05_11_1600 | fn_audit_trigger 升级 v2（三参签名：id_col + code_col + parent_ref） |
| 6 | 0006_prs_init | 2026_05_11_1700 | prs schema：project / project_milestone / project_team / project_status_history |
| 7 | 0007_ref_init | 2026_05_11_1730 | ref schema：project_substance（v1 简版） |
| 8 | 0008_prs_triggers | 2026_05_11_1800 | prs 全表 audit trigger + project assign_code（PRJ-yyyy 年度序列） |
| 9 | 0009_signature_session_var | 2026_05_11_1900 | 临时签名 session var 实验（被 0010 撤销）|
| 10 | 0010_revert_signature_session_var | 2026_05_11_2000 | 撤销 0009 |
| 11 | 0011_signature_pivot | 2026_05_11_2100 | e_signature 改成 service 后置 UPDATE 模式 |
| 12 | 0012_ref_ps_v2 | 2026_05_11_2200 | ref.project_substance 升 v2（复合 PK 三键 + relation_type） |
| 13 | 0013_prs_proj_v2 | 2026_05_11_2300 | prs.project 字段集对齐 V1.1 §9.2 + 年度序列 fn_ensure_year_sequence |
| 14 | 0014~0021 | 2026_05_12_*  | M3.0 系列回归：team unique / xref backfill / protein hash 索引等 |
| 15 | 0022_ars_asset | 2026_05_12_0030 | ars.asset 主表 + assign_code + audit trigger + before_update 版本+1 |
| 16 | 0023_ars_market_id | 2026_05_12_0040 | ars.asset_market_id + UNIQUE(asset_id, market_code, id_type, id_value) |
| 17 | 0024_ars_status_hist | 2026_05_12_0050 | ars.asset_status_history（V1.1 §8 缺整表 DDL，实施补齐） + status_change 触发器 |
| 18 | 0025_ref_as | 2026_05_12_0100 | ref.asset_substance（复合 PK 三键 + component_role 6 值）|
| 19 | 0026_ref_pa | 2026_05_12_0110 | ref.project_asset（复合 PK 仅二键 + relation_type 属性）|
| 20 | 0027_softdel_by | 2026_05_12_0900 | 全表 deleted_by FK 统一补（除了 prs 几张漏的）|
| 21 | 0028_srs_baseline_align | 2026_05_12_1000 | Batch A：SRS 4 项 DB 基线缺口（external_uuid UNIQUE / protein hash 索引 ×2 / xref_value 索引 / internal_code partial）+ S8 触发器 GUC 去除 |
| 22 | 0029_baseline_align_arp | 2026_05_12_1100 | Batch D：ars/prs/ref 同款 GUC 去除 + ref.project_substance.deleted_by FK + prs 索引重命名 + ix_project_dates |
| 23 | 0030_meta_lookup_config | 2026_05_13_0200 | Batch G3.A：meta.lookup_value + meta.system_config（ARCH12 / DM §5.2-§5.3 完整 seed）|
| 24 | 0031_h1_team_unique_ref_fks | 2026_05_13_0300 | Batch H1：prs.project_team partial UNIQUE WHERE left_at IS NULL + ref 三表 6 个 created/updated_by FK |
| 25 | 0032_mm_material | 2026_05_13_0400 | Phase 4.A：mm.material 主表（7 类型 / 4 等级 / 5 状态 / MAT-yyyy 年度序列编码 / audit trigger v2）|
| 26 | 0033_mm_material_batch | 2026_05_13_0500 | Phase 4.A：mm.material_batch（5 状态 / UNIQUE batch_number / audit trigger v2 parent_ref 回填 material_code）|
| 27 | 0034_auth_refresh_token | 2026_05_13_0600 | Phase 4.B-1：auth.refresh_token（jti PK + rotated_to_jti + revoked_reason 字典 + ip/ua）|
| 28 | 0035_protein_ext_coef_float | 2026_05_13_0700 | Phase 4.B-2：srs.substance_protein.ext_coef DECIMAL → REAL（蛋白消光系数科学计算精度）|
| 29 | 0036_audit_trigger_v3 | 2026_05_14_0100 | 修订十二：audit trigger v3 — CREATE / DELETE 字段级展开 + parent_ref 回填策略 |
| 30 | 0037_user_force_password_change | 2026_05_16_0100 | Phase 5.A：auth.user.force_password_change 布尔（首次登录强改密）|
| 31 | 0038_mm_material_v2 | 2026_05_19_0100 | MM v2：material_type 4 值（reagent/consumable/standard/column）+ category 14 值扁平枚举 + grade 自由文本 + 7 新字段（manufacturer/catalog_no/spec_model/unit NOT NULL/package_spec/hazard_class[]/category）|
| 32 | 0039_mm_category_add_waibao | 2026_05_19_0200 | MM v2：category CHECK 加 `外包材`（15 值扁平枚举）|
| 33 | 0040_eqp_equipment | 2026_06_04_0100 | EQP 设备域第 1 步：eqp schema + equipment 主表 + assign_code（EQP-yyyy 年度序列）+ audit trigger；定位为 LabOps 数据上游 |
| 34 | 0041_eqp_add_fields | 2026_06_04_0200 | EQP：新增 rated_power（额定功率）/ origin（产地）+ 列注释语义校准 |
| 35 | 0042_eqp_category_5class | 2026_06_04_0300 | EQP：设备分类 4 类 → 5 类体系（分析仪器/工艺制备/通用实验室/公用工程/IT自动化）+ 旧值重映射 |
| 36 | 0043_eqp_workstation | 2026_06_05_0100 | EQP：has_workstation 布尔 + workstation_info JSONB（附带专用工作站配置）|
| 37 | **0044_eqp_identifiers** | 2026_06_05_0200 | EQP：三标识体系 — equipment_code 定位为系统设备ID（不可改）+ 新增 equipment_no（业务）/ fixed_asset_no（财务）— **当前 head** |

> 注：序号 14（0014-0021）是 M3.0 多次小修迁移，本表为节省篇幅合并。完整 44 个文件用 `alembic history` 查看。

---

## 2. 首次生产部署迁移路径

### 2.1 前置条件

- IQ 清单（`deploy/checklist_iq.md`）全部 PASS
- PG 实例已建（`cmab_mdm` 数据库 + `cmab_app` 应用账号 + 4 个 schema + pgcrypto/pg_trgm/btree_gin/unaccent 扩展）
- backend 容器构建好（production stage，含 alembic）

### 2.2 执行步骤

```bash
# 1. 启动基础服务（不启 backend，先做迁移）
docker compose -f deploy/docker-compose.prod.yml --env-file /etc/cmab-mdm/.env.prod up -d postgres redis

# 2. 等 PG ready
until docker exec cmab-mdm-postgres pg_isready -U postgres -d cmab_mdm; do sleep 2; done

# 3. 跑全部 migration（一次性 0001 → 0044）
docker run --rm \
  --network cmab-mdm-prod_internal \
  --env-file /etc/cmab-mdm/.env.prod \
  --env DATABASE_URL_SYNC=postgresql://${POSTGRES_USER}:${POSTGRES_PASSWORD}@postgres:5432/${POSTGRES_DB} \
  cmab-mdm-backend:latest \
  alembic upgrade head

# 4. 验证 head
docker exec cmab-mdm-postgres psql -U cmab_app -d cmab_mdm -c \
  "SELECT version_num FROM alembic_version"
# 应输出：0044_eqp_identifiers

# 5. baseline seed（权限/角色/默认用户/必备字典）
docker run --rm \
  --network cmab-mdm-prod_internal \
  --env-file /etc/cmab-mdm/.env.prod \
  --env DATABASE_URL=postgresql+asyncpg://${POSTGRES_USER}:${POSTGRES_PASSWORD}@postgres:5432/${POSTGRES_DB} \
  cmab-mdm-backend:latest \
  python -m app.scripts.seed_data
# **生产部署不带 --demo**

# 6. 启 backend + frontend + gateway
docker compose -f deploy/docker-compose.prod.yml --env-file /etc/cmab-mdm/.env.prod up -d

# 7. 健康检查
curl -k https://<域名>/health
```

### 2.3 完成后强制验证

| 验证项 | 命令 | 期望 |
|---|---|---|
| alembic head | `docker exec cmab-mdm-postgres psql -U cmab_app -d cmab_mdm -c "SELECT * FROM alembic_version"` | `0044_eqp_identifiers` |
| schema 对齐 | `make check-schema`（dev 端做，生产用相同脚本） | exit 0 |
| 权限表行数 | `psql -c "SELECT count(*) FROM auth.permission"` | ≥ 20 |
| 角色表 | `psql -c "SELECT role_code FROM auth.role"` | 8 行（SYS_ADMIN/SUBSTANCE_STEWARD/PROJECT_MANAGER/CMC_RESEARCHER/QA_REVIEWER/READ_ONLY_USER/CMC_WAREHOUSE_ADMIN/CMC_EQUIPMENT_ADMIN） |
| code_sequence | 5 域（substance/project/asset/material/equipment）年度序列动态创建 | `psql -c "SELECT sequence_name FROM meta.code_sequence"` |
| audit trigger 在位 | `psql -c "SELECT count(*) FROM pg_trigger WHERE tgname LIKE 'trg_%_audit'"` | ≥ 12 |
| OQ 测试通过 | UAT 上跑 `make test-be` | 277 passed（2026-06-05 基线）|

---

## 3. alembic 升级部署（增量）

### 3.1 升级时机

任何新增 migration（如 0045+）合并到 main 后，先在 UAT 跑通，再走生产升级。

### 3.2 升级步骤

```bash
# 1. 备份当前生产数据（强制；不可跳过）
sudo bash scripts/backup_db.sh
# 记录备份文件名 + 大小 + 时间戳 → 升级单

# 2. 停业务流量（nginx 切维护页 或 backend 停容器）
docker compose -f deploy/docker-compose.prod.yml stop backend

# 3. 拉新镜像
docker compose -f deploy/docker-compose.prod.yml --env-file /etc/cmab-mdm/.env.prod pull backend

# 4. 跑增量 migration
docker run --rm \
  --network cmab-mdm-prod_internal \
  --env-file /etc/cmab-mdm/.env.prod \
  --env DATABASE_URL_SYNC=postgresql://${POSTGRES_USER}:${POSTGRES_PASSWORD}@postgres:5432/${POSTGRES_DB} \
  cmab-mdm-backend:latest \
  alembic upgrade head

# 5. 验证新 head + schema 对齐
docker exec cmab-mdm-postgres psql -U cmab_app -d cmab_mdm -c \
  "SELECT version_num FROM alembic_version"

# 6. 启 backend
docker compose -f deploy/docker-compose.prod.yml --env-file /etc/cmab-mdm/.env.prod start backend

# 7. smoke 测试
curl -k https://<域名>/health
curl -k https://<域名>/api/v1/system/info

# 8. 恢复流量
```

### 3.3 升级失败回滚

- 数据无变更（仅 schema 失败）：`alembic downgrade <prev_head>`
- 数据已变更：必须从 step 1 备份 + `scripts/restore_db.sh` 完整回滚（参考 `RUNBOOK_BACKUP_RESTORE.md` §4.1）
- 任何回滚必须 1 小时内启动；超过则启动 CAPA + 偏差报告

---

## 4. 跨环境数据迁移（dev / UAT / 生产）

### 4.1 整体迁移模板

```bash
# === 源环境（dev）===
bash scripts/backup_db.sh
# 产出 backups/cmab_mdm_<host>_<ts>.dump

# === 目标环境（UAT）===
# 1. 准备目标 PG（空库或先清空）
docker exec cmab-mdm-postgres psql -U postgres -c "
  DROP DATABASE IF EXISTS cmab_mdm;
  CREATE DATABASE cmab_mdm WITH ENCODING='UTF8';
"

# 2. 拷贝 dump 文件到目标 host
scp backups/cmab_mdm_dev_*.dump uat-host:/var/lib/cmab-mdm/backups/

# 3. 在目标 host 上 restore
ssh uat-host
sudo bash scripts/restore_db.sh cmab_mdm_dev_<ts>.dump

# 4. 验证（见 §5 抽检模板）
```

### 4.2 dev → 生产首次同步特别注意

- **绝对不要把 dev 的演示数据（DEMO_SUBSTANCES / DEMO_PROJECTS / DEMO_ASSETS / DEMO_MATERIALS）带到生产**。生产从空库 + baseline seed 起。
- dev 的测试用户（admin / qingcheng / researcher / qa_reviewer / readonly）密码**必须重设**或重新创建。
- `auth.refresh_token` 表所有行清空（dev 残留的 token 不能带到生产）：`DELETE FROM auth.refresh_token;`
- 审计日志（audit.audit_log）按合规决定是否携带：通常**不携带** dev 审计到生产（dev 的 user_id 在生产无意义）。

---

## 5. 抽检模板（迁移前后对比）

### 5.1 关键计数对比

```sql
-- 迁移前 / 迁移后各跑一次，对比
SELECT
  'auth.user' AS tbl,         count(*) FROM auth.user
UNION ALL SELECT 'auth.permission', count(*) FROM auth.permission
UNION ALL SELECT 'auth.role',       count(*) FROM auth.role
UNION ALL SELECT 'auth.user_role',  count(*) FROM auth.user_role
UNION ALL SELECT 'auth.role_permission', count(*) FROM auth.role_permission
UNION ALL SELECT 'meta.code_sequence',   count(*) FROM meta.code_sequence
UNION ALL SELECT 'meta.lookup_value',    count(*) FROM meta.lookup_value
UNION ALL SELECT 'meta.system_config',   count(*) FROM meta.system_config
UNION ALL SELECT 'srs.substance',        count(*) FROM srs.substance
UNION ALL SELECT 'srs.substance_protein',count(*) FROM srs.substance_protein
UNION ALL SELECT 'srs.substance_adc',    count(*) FROM srs.substance_adc
UNION ALL SELECT 'srs.substance_xref',   count(*) FROM srs.substance_xref
UNION ALL SELECT 'srs.substance_status_history', count(*) FROM srs.substance_status_history
UNION ALL SELECT 'prs.project',          count(*) FROM prs.project
UNION ALL SELECT 'prs.project_milestone',count(*) FROM prs.project_milestone
UNION ALL SELECT 'prs.project_team',     count(*) FROM prs.project_team
UNION ALL SELECT 'prs.project_status_history', count(*) FROM prs.project_status_history
UNION ALL SELECT 'ars.asset',            count(*) FROM ars.asset
UNION ALL SELECT 'ars.asset_market_id',  count(*) FROM ars.asset_market_id
UNION ALL SELECT 'ars.asset_status_history', count(*) FROM ars.asset_status_history
UNION ALL SELECT 'mm.material',          count(*) FROM mm.material
UNION ALL SELECT 'mm.material_batch',    count(*) FROM mm.material_batch
UNION ALL SELECT 'ref.project_substance',count(*) FROM ref.project_substance
UNION ALL SELECT 'ref.asset_substance',  count(*) FROM ref.asset_substance
UNION ALL SELECT 'ref.project_asset',    count(*) FROM ref.project_asset
UNION ALL SELECT 'audit.audit_log',      count(*) FROM audit.audit_log
UNION ALL SELECT 'audit.change_history', count(*) FROM audit.change_history
UNION ALL SELECT 'audit.e_signature',    count(*) FROM audit.e_signature
ORDER BY tbl;
```

判定：所有行**逐行 ±0**（完全相等）。任何 ≠0 必须解释。

### 5.2 关键资产抽检（5 条/域）

```sql
-- substance 抽检：迁移前后各取 5 条最早的 + 5 条最新的
SELECT substance_code, internal_code, preferred_name, status, version,
       created_at::date, updated_at::date
  FROM srs.substance
 WHERE deleted_at IS NULL
 ORDER BY substance_id
 LIMIT 5
UNION ALL
SELECT substance_code, internal_code, preferred_name, status, version,
       created_at::date, updated_at::date
  FROM srs.substance
 WHERE deleted_at IS NULL
 ORDER BY substance_id DESC
 LIMIT 5;

-- project / asset / material 同款
```

判定：迁移前后字段逐字段比对（建议存 CSV diff）。任何差异必须有源（如迁移期间的并发写入）。

### 5.3 audit_log 完整性

```sql
-- 任意一条业务记录的所有 audit 行 → 迁移前后行数相等
WITH probe AS (SELECT 'srs' AS schema_name, 'substance' AS table_name, 1 AS entity_id)
SELECT count(*) FROM audit.audit_log a, probe p
 WHERE a.entity_schema = p.schema_name
   AND a.entity_table = p.table_name
   AND a.entity_id = p.entity_id;
```

判定：相等。审计 log 不允许丢失（21 CFR Part 11 §11.10(c)）。

---

## 6. 失败处置 / 回滚

### 6.1 alembic upgrade 失败

| 阶段 | 现象 | 处置 |
|---|---|---|
| migration 文件语法错 | `alembic upgrade` 抛 Python 异常 | 修代码 + 重跑（迁移文件本身**未对 DB 生效**） |
| DDL 执行失败 | `alembic upgrade` 抛 SQL 异常 | PG 事务回滚；`alembic current` 仍是旧 head；修 DDL + 重跑 |
| 部分迁移成功部分失败 | 多文件升级中途失败 | 检查 `alembic_version` 与实际 schema；必要时手工 `alembic stamp <ok_head>` |

### 6.2 跨环境迁移失败

| 现象 | 处置 |
|---|---|
| pg_restore 抛 FK 异常 | 通常因为 schema 版本不一致；先在目标环境 `alembic upgrade head` 到与源相同 head 再 restore |
| restore 后 audit_log 行数不对 | 检查 pg_dump 是否 `-F c` + 完整模式；重做 backup → restore |
| `make check-schema` 失败 | 见 §3.1 升级失败处理 + 看 V1.2_draft 是否需要追加豁免 |

---

## 7. 演练频率与签字

| 演练类型 | 频率 | 责任 |
|---|---|---|
| 首次部署迁移 | 部署当次 | IT 工程师 + QA |
| alembic 升级演练 | 每次升级前 UAT 一遍 | IT 工程师 |
| 跨环境迁移演练 | Q1 / Q3 各一次 | IT + CMC 业务用户抽检 |
| 备份恢复演练 | Q1 / Q3 各一次（见 RUNBOOK_BACKUP_RESTORE.md §5）| IT + QA |

每次演练记录归档：执行人、执行时间、抽检 SQL 输出 CSV、偏差说明（如有）、签字页。

---

## 8. 参考

- DM-MDM-001 V1.1 §2.3 数据库初始化与扩展
- ARCH-MDM-001 V1.1 §10 部署与运维
- 21 CFR Part 11 §11.10(a) 数据完整性 / §11.10(c) 可获取性
- EU Annex 11 §4.5 数据迁移验证
- PostgreSQL 文档：[Migrations and Versioning](https://www.postgresql.org/docs/16/migrations.html)
- Alembic 文档：[Tutorial](https://alembic.sqlalchemy.org/en/latest/tutorial.html)
