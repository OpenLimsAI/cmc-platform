# CMAB MDM Portal 数据迁移演练 SOP

| 项目 | 内容 |
|---|---|
| 文档编号 | RUNBOOK-MIGRATION-001 |
| 版本 | V1.0 |
| 适用 | 首次生产部署 + 后续 alembic 升级 + 跨环境数据迁移（dev → UAT / UAT → 生产）|
| 合规 | GAMP 5 / 21 CFR Part 11 §11.10(a) 数据完整性 / EU Annex 11 §4.5 数据迁移 |
| 当前 head | `0060_eqp_device_status`（共 60 个 migration，2026-09-15；已从空库实测迁移通过） |

---

## 0. 用途与范围

本 SOP 用于：
1. **首次生产部署**：从空 PG 实例完整执行 0001→0060 全部 migration；仅空库经批准加载 baseline seed
2. **alembic 升级部署**：现有 head 升级到仓库 head
3. **受控整库迁移**：仅用于获批的 UAT 克隆、服务器迁移或灾难恢复，不用开发库覆盖生产
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
| 37 | **0044_eqp_identifiers** | 2026_06_05_0200 | EQP：三标识体系 — equipment_code 定位为系统设备ID（不可改）+ 新增 equipment_no（业务）/ fixed_asset_no（财务）— 2026-06 历史基线 |

### 1.1 0045—0060 增量迁移

| revision | 内容（简） |
|---|---|
| 0045—0046 | 修复业务编码与角色编码在软删除后的唯一约束 |
| 0047—0049 | PRS 对齐 SMP-RD-NUM-001 V2.1：编号、分类、资产关联、上市后变更与项目关系 |
| 0050—0052 | 新增 `tgt` 靶点域、分子—靶点关系、UniProt 标准字段与序列 |
| 0053 | Substance 编码调整为 `SUB-0001` 四位流水号 |
| 0054 | 会话策略落库：空闲超时、滑动续期与单次登录硬上限 |
| 0055 | 部门管理员、验证部角色与可下放角色白名单 |
| 0056 | 审计日志、变更历史和登录历史索引优化 |
| 0057 | 设备清单治理字段：部门、厂区、房间、分级、分级依据与启用日期 |
| 0058 | 撤销滑动会话上线前遗留的长效 refresh token |
| 0059_eqp_alias | 设备别名/曾用名正式字段及历史 `extra` 数据搬迁 |
| **0060_eqp_device_status** | 新增独立 `equipment_status`（启用/封存/报废）并收口 MDM；保留原 `status` 主数据状态，历史设备默认启用、上线后由设备专员复核——**当前 head** |

> 注：序号 14（0014-0021）是 M3.0 多次小修迁移，本表为节省篇幅合并。完整 60 个 migration 用 `alembic history` 查看。

---

## 2. 首次生产部署迁移路径

### 2.1 前置条件

- IQ 清单（`deploy/checklist_iq.md`）全部 PASS
- Linux 原生 PG16 `mdm` 集群 :5433、Redis、nginx 与 `cmab-backend.service` 已按 IQ 清单安装
- `/opt/cmab-mdm-platform/backend/.venv` 已建立，`backend/.env` 指向 `127.0.0.1:5433/cmab_mdm`

### 2.2 执行步骤

```bash
# 1. 确认原生服务和连接目标
systemctl is-active postgresql@16-mdm redis-server nginx
grep '^DATABASE_URL_SYNC=' backend/.env   # 人工确认端口 5433、库 cmab_mdm

# 2. 安装/更新后端依赖并迁移到仓库 head
backend/.venv/bin/pip install -q -e backend
( cd backend && .venv/bin/alembic upgrade head )

# 3. 验证 head
psql -p 5433 -U cmab_app -d cmab_mdm -c "SELECT version_num FROM alembic_version"
# 应输出：0060_eqp_device_status

# 4. 仅首次创建的空库、经负责人确认后加载 baseline seed；日常升级不得执行
( cd backend && .venv/bin/python -m app.scripts.seed_data )
# 严禁带 --demo

# 5. 构建前端并安装/更新 systemd 受管单元
( cd frontend && pnpm install --prefer-offline && pnpm build )
bash deploy/linux/install_systemd.sh

# 6. 从统一门户路径健康检查
curl -fsS --noproxy '*' http://127.0.0.1:5100/mdm/api/v1/health
```

### 2.3 完成后强制验证

| 验证项 | 命令 | 期望 |
|---|---|---|
| alembic head | `psql -p 5433 -U cmab_app -d cmab_mdm -c "SELECT * FROM alembic_version"` | `0060_eqp_device_status` |
| schema 对齐 | `make check-schema`（仅本地 Docker 开发环境） | exit 0 |
| 权限表 | `psql -c "SELECT permission_code FROM auth.permission ORDER BY 1"` | 与当前 `seed_data.py` 和定向权限脚本逐项一致 |
| 角色表 | `psql -c "SELECT role_code FROM auth.role WHERE deleted_at IS NULL ORDER BY 1"` | 当前 baseline 14 个角色码逐项存在（含 DISPLAY_MODE、DEPT_ADMIN、QV_*） |
| code_sequence | `psql -c "SELECT sequence_name FROM meta.code_sequence ORDER BY 1"` | substance/project/asset/material/equipment/target 六域就绪 |
| audit trigger 在位 | 查询 `pg_trigger` 中 `trg_%_audit` 并导出 schema/table/trigger | 与当前 migration 定义逐项一致，不以历史固定数量判断 |
| 自动化回归 | 本地隔离环境跑 `make test-be` | 共 409 项；设备状态相关项通过。最近两次全量运行各有 1 项既有账户管理用例偶发失败（失败点不同，2026-09-15 待治理）；不等于 OQ 映射已完整 |

---

## 3. alembic 升级部署（增量）

### 3.1 升级时机

任何新增 migration（当前 head 之后即 `0061+`）合并到 main 后，先在 UAT 跑通，再走生产升级。

### 3.2 升级步骤

```bash
# 1. 备份当前生产数据（强制；不可跳过）
sudo -u prometheus env BACKUP_MODE=native bash scripts/backup_db.sh
# 记录备份文件名 + 大小 + 时间戳 → 升级单

# 2. 停后端；如需完全停流量，先由 nginx 切维护页
sudo systemctl stop cmab-backend

# 3. 拉取代码并更新依赖
git pull --ff-only origin main
backend/.venv/bin/pip install -q -e backend

# 4. 跑增量 migration
( cd backend && .venv/bin/alembic upgrade head )

# 5. 验证新 head
psql -p 5433 -U cmab_app -d cmab_mdm -c "SELECT version_num FROM alembic_version"

# 6. 构建前端并重启后端
( cd frontend && pnpm install --prefer-offline && pnpm build )
sudo systemctl restart cmab-backend

# 7. smoke 测试
curl -fsS --noproxy '*' http://127.0.0.1:5100/mdm/api/v1/health

# 8. 如使用维护页，恢复 nginx 正常路由
```

### 3.3 升级失败回滚

- 数据无变更（仅 schema 失败）：`alembic downgrade <prev_head>`
- 数据已变更：必须从 step 1 备份 + `scripts/restore_db.sh` 完整回滚（参考 `RUNBOOK_BACKUP_RESTORE.md` §4.1）
- 任何回滚必须 1 小时内启动；超过则启动 CAPA + 偏差报告

---

## 4. 受控的整库迁移（UAT / 灾难恢复）

日常发布只通过 Git + Alembic 同步结构，**不把开发库整库覆盖到生产**。开发库含真实物料、
设备数据及开发账号，整库迁移只能用于已批准的 UAT 克隆、服务器迁移或灾难恢复，并须先停写、
记录源/目标 migration head 和备份校验值。

### 4.1 整体迁移模板

```bash
# === 源环境（dev）===
bash scripts/backup_db.sh
# 产出 backups/cmab_mdm_<host>_<ts>.dump

# === 目标环境（UAT/新主机）===
# 1. 将明确的一份 dump 传到受控备份目录，并记录 sha256
scp backups/<明确文件名>.dump uat-host:<受控备份目录>/
shasum -a 256 backups/<明确文件名>.dump

# 2. 在目标主机按 RUNBOOK_BACKUP_RESTORE §4 执行对应部署形态的恢复
#    Linux 原生环境不得运行 scripts/restore_db.sh；该脚本当前只支持 Mac Docker

# 3. 验证 migration head、计数、审计和抽样字段（见 §5）
```

### 4.2 禁止直接 dev → 生产整库覆盖

- 当前 dev 已包含真实物料/设备数据，但这不构成整库覆盖生产的授权；需要迁移某一业务域时应使用经审核的专项导入脚本和对账报告。
- **绝对不要把 dev 的演示/测试数据带到生产**。全新生产空库仅执行迁移和经批准的 baseline seed。
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
UNION ALL SELECT 'auth.refresh_token', count(*) FROM auth.refresh_token
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
UNION ALL SELECT 'eqp.equipment',        count(*) FROM eqp.equipment
UNION ALL SELECT 'tgt.target',           count(*) FROM tgt.target
UNION ALL SELECT 'tgt.target_source_snapshot', count(*) FROM tgt.target_source_snapshot
UNION ALL SELECT 'ref.project_substance',count(*) FROM ref.project_substance
UNION ALL SELECT 'ref.asset_substance',  count(*) FROM ref.asset_substance
UNION ALL SELECT 'ref.project_asset',    count(*) FROM ref.project_asset
UNION ALL SELECT 'ref.molecule_target',  count(*) FROM ref.molecule_target
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
