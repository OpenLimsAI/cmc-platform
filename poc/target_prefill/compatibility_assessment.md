# 靶点 / 分子域自动预填 —— 与现有 MDM 代码库的兼容性评估（只读分析）

- 评估日期：2026-08-17；代码基线：`main` @ c7bed9e；alembic head `0049_prs_smp_v21_batch3`
- 方法：只读通读 `backend/`（域/API/迁移/脚本/配置）、`frontend/src`、`deploy/`；未改任何文件
- 配套：功能验证见 `test_report.md`；PoC 脚本 `prefill_target.py`

## 0. 结论摘要

| 维度 | 结论 |
|---|---|
| 数据模型 | 完全按现有套路可落地：ORM `models.py` + 手写 alembic 迁移 + DB 触发器（取号/updated_at/审计）。`ref.*` 三张关联表就是 `bridge.molecule_target` 的现成模板；jsonb 列有 15+ 处先例，但**"外部原始快照 + 抓取时间"是新模式**（无先例，最接近的是各表 `extra JSONB`）。 |
| 编码 | 取号在数据库：`meta.code_sequence` + `meta.fn_next_code()` / `meta.fn_ensure_year_sequence()`。新前缀 = 迁移里 1 条 INSERT 或 1 个 BEFORE INSERT 触发器（抄 EQP 0040），**零 Python 改动**。bridge 表按惯例不编码。 |
| 枚举 | 硬编码三份（PG CHECK + Pydantic Literal + 前端 TS 常量）；`meta.lookup_value` 字典表存在但前端从未读取。新枚举按现状**照三份硬编码**接入即可，2 个枚举 × 3 处 = 6 个改动点。 |
| 录入→审核→发布 | 现状分两档：SRS/PRS 有状态机 + 电子签名；MM/EQP 是纯 CRUD（`status` 只是一列）。**没有** "pending_review/发布队列"概念。新域建议对标 MM/EQP（CRUD + 权限拆分 create/update/approve），预填在**后端服务**做（理由见 §4.3）。 |
| 外部调用 | `httpx` 0.28 / `tenacity` 9.1 **已在依赖里但业务代码 0 处使用**，无 HTTP 客户端封装、无缓存 helper、无超时/重试配置项——全部要新写（量不大）。**生产后端进程能否出网未知**：主机层面能 `git pull github` 且 deploy 脚本用 `--noproxy '*'` 暗示有代理，但 systemd 服务的 EnvironmentFile 不在仓库里，必须上机验证。 |
| 工作量 | 主线（新增靶点域 + 复用 srs.substance 当分子 + 后端预填服务 + 前端 4 页 + 预填向导 + 测试）**约 16–22 人日**；若要求靶点走 SRS 式状态机+电签 +3–5；若要独立"分子域"而不复用 SRS +4–6；若生产不出网改本地镜像 +5–8。 |

---

## 1. 数据模型层

### 1.1 现有实体如何定义
- **ORM 为主，DDL 全在手写 alembic 迁移里**（`backend/alembic/env.py` 只导入 audit/auth/srs 三个域的 models、`include_name` 白名单还漏了 `eqp`，autogenerate 实际不可用，49 个迁移全是手写）。
- 每域三件套：`backend/app/domains/<域>/{models,schemas,services}.py`；路由 `backend/app/api/v1/<域>.py`；注册 `backend/app/api/v1/__init__.py`（第 24–49 行 `include_router`）。
- ORM 基类 `backend/app/core/database.py:32` `Base(DeclarativeBase)`，统一命名约定（`pk_/uq_/ck_/fk_/ix_`）。**没有 mixin**：每张表逐字重复 6 列审计块 `created_at/created_by/updated_at/updated_by/deleted_at/deleted_by`（如 `backend/app/domains/eqp/models.py:82-93`），软删 = `deleted_at IS NULL`，`updated_at` 由每表 BEFORE UPDATE 触发器维护。
- 现有 schema：`auth, meta, audit, srs, prs, ars, mm, ref` 在 `deploy/postgres/init/01-init.sql` 里建；`eqp` 由迁移 0040 `CREATE SCHEMA IF NOT EXISTS` 建——**新 schema 走迁移即可**（但同时要补 `01-init.sql` search_path 与 `env.py` 白名单两处，否则日后 autogenerate/新库初始化不一致）。
- 跨 schema 外键就是普通 FK：`ForeignKey("srs.substance.substance_id")`（`backend/app/domains/ref/models.py:39-48`）。
- 关键先例——`srs.substance` **已有** `target String(128)` / `target_type String(64)` 两个自由文本列（`backend/app/domains/srs/models.py:66-67`，前端 `SubstanceListPage.tsx` 有筛选）。`dim.target` + bridge 本质上是把这两列**规范化**；后续要考虑存量数据回填（当前 SRS 真实数据为 0，回填成本为零，这是现在做的好时机）。

### 1.2 新增 dim.target + bridge.molecule_target 需要的文件/对象（按现有模式）

**A. 迁移**（1 个文件，抄 `2026_06_04_0100_0040_eqp_equipment.py`（主表）+ `2026_05_12_xxxx_0025_ref_as.py`（关联表））
1. `CREATE SCHEMA IF NOT EXISTS <schema>`（命名见 1.4）
2. `target` 表：`target_id BIGINT IDENTITY PK`、`target_code VARCHAR UNIQUE`、`target_name`、`uniprot_id VARCHAR(16) UNIQUE(partial where deleted_at is null)`、`gene_symbol`、`organism`、`target_type CHECK IN (5 值)`、`target_location CHECK IN (4 值)`、`aliases JSONB`、`uniprot_raw JSONB`、`chembl_raw JSONB`、`source_fetched_at TIMESTAMPTZ`、`source_version`（UniProt entryVersion / ChEMBL release）、`status CHECK`、`extra JSONB`、6 列审计块（FK → `auth.user`）
3. `molecule_target` 表：`molecule_id BIGINT FK → srs.substance.substance_id`（见 1.3）、`target_id FK`、`moa TEXT`、`action_type`、`binding_epitope_or_domain TEXT`、`relation_role CHECK('antibody_target','payload_target','other')`（ADC 载荷问题）、`chembl_mechanism_id`、`chembl_raw JSONB`、`source_fetched_at`、`needs_confirm BOOL`、审计块；PK 建议 `(molecule_id, target_id, relation_role)`（对齐 `ref.project_substance` 三列复合 PK 的写法）；双向部分索引
4. 取号：`INSERT INTO meta.code_sequence(sequence_name,prefix,padding_length) VALUES ('target','TGT-',6)` + `fn_target_assign_code()` BEFORE INSERT 触发器（照 0040 L112-131）
5. `fn_target_before_update` + `trg_target_before_update`
6. 审计：`audit.fn_audit_trigger('target_id','target_code')`；bridge 用三参形式 `audit.fn_audit_trigger('molecule_id','', 'srs.substance:substance_id:substance_code:molecule_id')`（照 0025 L64-70）
7. `meta.lookup_value` 补 `target_type` / `target_location` 两组字典行（照 0047 L86-98，目前仅"对齐设计基准"作用）
8. GIN trigram 索引 `target_name`（照 0040 的 `gin_trgm_ops`）

**B. 后端**：`app/domains/target/{models,schemas,services}.py`、`app/api/v1/targets.py`（CRUD + `/targets/{code}/molecules` 子资源，或挂在 `/substances/{code}/targets` 下——现有关联 API 都是挂父资源子路径，如 `projects.py:422-536`）、`api/v1/__init__.py` 注册、`app/scripts/seed_data.py:52-74` 加 `target:{create,read,update,approve}` 权限（见 §4 坑）、可选 `app/domains/search/services.py` + `app/shared/dashboard_service.py` 接入。
**C. 前端**：`src/api/targets.ts`、`src/api/types.ts` 手写类型（CLAUDE.md 提到的 `src/api/schema.d.ts` **实际不存在**，无人生成过）、`src/modules/targets/{constants.ts,pages/*.tsx}`、`App.tsx` 路由、`Sidebar.tsx` 菜单、`GlobalSearchBox.tsx`/`EntityCodeLink.tsx` 注册。
**D. 测试**：`backend/tests/test_target_crud.py`、`test_molecule_target_link.py`（照 `test_asset_substance_link.py`）。

### 1.3 "抗体分子域" 建议复用 SRS，不另建
`srs.substance` 已经是分子主数据：`substance_type IN ('mab','bispecific','adc','fusion',…)`，配套 `srs.substance_protein`（`additional_chains/disulfide_bonds/glycosylation_sites/ptm_info` 全是 JSONB，正好对应 ChEMBL `biotherapeutic.biocomponents`）、`srs.substance_adc`（`dar_distribution`）、`srs.substance_xref`（`xref_type` 已含 `INN/USAN/ChEMBL/TRADE_NAME/…`，可直接存 ChEMBL ID、研发代号、商品名）。**建议 `bridge.molecule_target.molecule_id → srs.substance.substance_id`**，预填同时回填 substance 的 INN/xref/类型/max_phase，而不是再造一张分子表。若负责人坚持独立分子域，另加 4–6 人日且要处理与 SRS 的重复。

### 1.4 jsonb 先例
- `postgresql.JSONB` 已用于 15+ 列：各表 `extra`（srs/prs/ars/mm/eqp/meta.lookup_value/audit.audit_log）、`srs.substance_protein.additional_chains/disulfide_bonds/glycosylation_sites/ptm_info`、`srs.substance_adc.dar_distribution`、`prs.project.participating_functions/external_contract_refs/regulatory_submission_refs`、`eqp.equipment.workstation_info`、`audit.change_history.old_value/new_value`。Pydantic 侧统一 `dict | None`。**无 GIN 索引、无 server_default**。
- **"外部源原始快照 + fetched_at" 无任何先例**（grep `fetched_at/raw_payload/raw_json/source_payload` 为 0）。新增 `uniprot_raw/chembl_raw + source_fetched_at + source_version` 是新模式但技术上零障碍。注意体积：UniProt 单条原文 100–400 KB，建议入库前裁剪（见 test_report §2.7）；ChEMBL 分子原文含全长序列，同理。
- 审计触发器 v3（`0036_audit_trigger_v3.py`）会把 INSERT/UPDATE/DELETE 的**每个字段**展开进 `audit.change_history`——大 jsonb 列会让每次保存产生一条巨大的 old/new 值记录。建议：把原始 jsonb 放到**独立的快照表**（`target_source_snapshot(target_id, source, fetched_at, payload)`，append-only，不挂审计触发器或只记 INSERT），主表只留裁剪后的业务字段。这样也符合总纲"raw append-only"的精神。

### 1.5 命名冲突需负责人拍板
任务给的 `dim.` / `bridge.` 在本库无先例；本库"跨域关联"惯例是 `ref` schema（表 `<a>_<b>`，约束前缀 `pk_ref_/ck_ref_/ix_ref_`），"维度/字典"是 `meta.lookup_value`。另外 `~/code/CLAUDE.md` 总纲把 `dim.*` 定义为 `cmc_analytics.dim.*`（设备/厂商/单位字典权威源）——在 `cmab_mdm` 里再起一个 `dim` schema容易混淆。三个选项：(a) 主表放新 schema `tgt`（对齐 srs/prs/ars/mm/eqp 一域一 schema）、关联表放 `ref.molecule_target`（零命名冲突，改动最小）；(b) 严格按任务用 `dim`/`bridge`（要改 `01-init.sql`、`env.py`、且与总纲的 dim 语义打架）；(c) 主表直接放 `srs.target`（靶点视作物质域附属）。**推荐 (a)**，本文其余部分用"靶点表 / bridge 表"泛指。

---

## 2. 编码规则

- 生成逻辑**全在数据库**，Python 无 codegen 模块：
  - `meta.code_sequence`（`0001_init_schemas.py:31-45`）+ `meta.fn_next_code(p_sequence_name)`（同文件 L48-70，`UPDATE … RETURNING` 行锁保证不重号，回滚会有空号）
  - 年度序列 `meta.fn_ensure_year_sequence(kind, prefix, year, padding)`（`0013_prs_proj_v2.py:149-167`，`ON CONFLICT DO NOTHING` 自建）
  - 现有格式：`SUB-0000001`（全局 7 位）、`CMAB-PRJ-2026-0001`、`AST-…`、`MAT-2026-000001`、`EQP-2026-000001`
- 两种调用方式并存：MM/EQP 用 **BEFORE INSERT 触发器**（service 传 `code=None`，`0040` L112-131）；SRS/ARS/PRS 在 service 里 `SELECT meta.fn_next_code(...)`。
- **target_code 复用的改动点**：只在迁移里——1 条 `INSERT INTO meta.code_sequence` (或用年度序列则不需要) + 1 个 `fn_target_assign_code` 触发器；downgrade 记得 `DELETE FROM meta.code_sequence WHERE sequence_name='target'`。格式建议 `TGT-000001`（全局、不分年，靶点不是按年产生的实体）。bridge 表不编码（对齐 `ref.*`）。

---

## 3. 枚举 / 字典管理

- **现状 = 三份硬编码**：PG `CHECK`（`eqp/models.py:33-41`、`mm/models.py:32-45`）+ Pydantic `Literal`（`eqp/schemas.py:11-18`）+ 前端常量（`src/modules/equipments/constants.ts`、`src/modules/materials/constants.ts` 连单位 `UNIT_OPTIONS` 都是硬编码）。无 PG ENUM 类型、无 Python Enum 类。EQP 的导入脚本还有第四份 `VALID_CATEGORIES`。
- 字典表 `meta.lookup_value`（`0030_meta_lookup_config.py`）+ 只读无鉴权接口 `GET /api/v1/lookups/{lookup_type}`（`api/v1/lookups.py`）**存在但前端 0 处调用**（`grep lookup frontend/src` = 0），无管理界面；只种了 substance/project/asset 五组，0047 之后靠迁移手工与 CHECK 同步。
- **两个新枚举按现状接法**：
  1. 迁移 CHECK：`target_type IN ('受体','配体·细胞因子','表面抗原','酶','其他')`、`target_location IN ('膜型','可溶型','两者都有','胞内')`（MM/EQP 的 CHECK 已直接用中文值，有先例）
  2. `schemas.py`：`TargetType = Literal[...]`、`TargetLocation = Literal[...]`
  3. 前端 `modules/targets/constants.ts`：`TARGET_TYPE_OPTIONS` / `TARGET_LOCATION_OPTIONS`
  4.（可选）`meta.lookup_value` 种两组，保持"设计基准对齐"
- 若想借这个新域**首次让前端走字典接口**：改动小（`useQuery(['lookups','target_type'])` + 一个 `useLookupOptions` hook，参考 `modules/admin/useRoleOptions.ts`），但 CHECK 与 Literal 仍是硬的，"动态生效"只是幻觉；不建议在本需求里顺手做。

---

## 4. 录入与审核流

### 4.1 现有实现位置
- 有状态机的域：SRS（`srs/services.py:48-67` `STATE_MACHINE` draft→registered→active→…，`SIGNATURE_REQUIRED_ACTIONS`，`change_status()` L655-770：FOR UPDATE 行锁 → `set_config('app.change_reason')` → `ESignatureService.sign()` → 改状态 → 补 status_history）、PRS（`prs/services.py:56-86`）、ARS（部分）。路由是冒号动词 `POST /substances/{code}:approve`（`api/v1/substances.py:181-236`），守卫 `require_all_permissions("substance:approve","substance:sign")`（`app/shared/permissions.py:136-152`，SYS_ADMIN 短路）。
- MM/EQP：**纯 CRUD，无状态机/版本/电签**（`eqp/services.py:2-3` 明说），`status` 是普通列由 PUT 改；但 update/delete 强制 `change_reason ≥ 5 字`并写入审计 GUC。
- 前端审核 UI：**没有审核队列页**，是每个详情页内嵌 `shared/components/StatusActionsBar.tsx`（按钮 + 变更原因 + 电签密码弹窗），动作表在各域 `constants.ts` 的 `AVAILABLE_ACTIONS/ACTION_LABELS`。权限显隐 `PermissionGuard` / `useAuthStore.hasPermission`。
- 权限码定义**只在** `backend/app/scripts/seed_data.py:52-74`（无迁移种权限、无 POST /permissions 接口）。⚠️ 项目 CLAUDE.md 禁止对 dev 库重跑 `make seed`——新权限码要么写一条**幂等的定向 INSERT 迁移/脚本**（照 `seed_lims_roles.py` 的幂等写法），要么请负责人在确认后跑一次 seed。

### 4.2 新域挂进去要动的模块
- **推荐档（对标 MM/EQP，原型阶段够用）**：靶点表加 `status CHECK IN ('draft','published','retired')`；`POST /targets` 建 draft（`target:create`），`PUT` 改（`target:update`），`POST /targets/{code}:publish`（`target:approve`，无电签，仅 `change_reason`）。改动 = §1.2 B/C 全部 + `seed_data.py` 权限 4 个 + 前端详情页挂 `StatusActionsBar`（复用，`requiresSignature:false`）。
- **重档（对标 SRS）**：再加 `<x>_status_history` 表 + 触发器（照 `0024_ars_status_hist.py`）、`STATE_MACHINE/SIGNATURE_REQUIRED_ACTIONS`、`target:sign` 权限、电签弹窗——+3–5 人日。原型阶段不建议。

### 4.3 外部 API 预填放前端还是后端 —— **后端服务**
理由：① 要落 `uniprot_raw/chembl_raw` + 抓取时间做审计，只有后端能保证"表单里看到的就是存下来的"；② 生产主机若靠代理出网，代理配置/白名单只在服务器侧，浏览器直连 ebi.ac.uk 在内网 PC 上大概率不通；③ 统一超时/重试/限速/日志（`request_id` 会自动进日志和审计）；④ 便于以后切"本地镜像"而前端无感。
形态建议：`POST /api/v1/targets:prefill {inn}` **同步**返回预填 JSON（不落库、不取号）；实测单例 4–6 次外部调用 8–20 s，需要 (a) httpx 每步 timeout 15–30 s、整体 ≤ 90 s；(b) 检查 nginx `proxy_read_timeout`（`deploy/nginx/linux-host/cmab-mdm.conf:21,32` 现配 `proxy_read_timeout 60s`，慢时会截断，需放宽到 120 s）；(c) 前端按钮 loading + 说明"约 20 秒"；(d) 用现有 Redis 客户端（`app/core/redis_client.py`）按 INN 缓存原始响应 24 h（照 `shared/idempotency.py` 的 `setex` 写法），重试/重开表单不再打外网。项目**没有任何任务队列/后台任务**（无 celery/arq/BackgroundTasks），做成异步作业需要新引入基础设施，不划算。
保存动作复用普通 `POST /targets` + `POST /substances/{code}/targets`，body 里带裁剪后的 raw 与 `source_fetched_at`，由 service 落库——"人工审核后发布，非自动落库"天然满足。

---

## 5. 外部调用能力 & 出网

### 5.1 可复用的
- `backend/pyproject.toml:38-39`：`httpx>=0.27`（锁 0.28.1）、`tenacity>=8.2`（锁 9.1.4）**都已声明**，但 `backend/app/` 里 httpx 只在测试用、tenacity 0 处 import → 不用加依赖，代码要新写：`app/shared/http_client.py`（`httpx.AsyncClient(timeout=..., trust_env=True/False)` 单例 + `@retry(tenacity)` 对 5xx/429/超时退避 + 域名白名单）。
- 日志：loguru + `request_id/user_id` ContextVar 自动注入（`app/core/logging.py:32-38`），外部调用只需 `logger.bind(url=..., status=..., ms=...)`。
- 缓存：Redis 客户端就绪，但**没有通用 cache_get/set helper**，要写第一个（十几行）。
- 配置：`app/core/config.py` 无任何代理/外部 URL/开关项；需新增 `PREFILL_ENABLED`、`CHEMBL_BASE_URL`、`UNIPROT_BASE_URL`、`EXTERNAL_HTTP_TIMEOUT_S`、`EXTERNAL_HTTP_PROXY`（或依赖环境变量 `HTTPS_PROXY`）。`extra="ignore"` 所以加环境变量不会炸旧配置。
- 反例注意：现有唯一外部集成是 `app/scripts/import_equipment_lims.py` 走 Oracle 内网，与本需求无关。

### 5.2 生产是否允许出网（只看配置的判断）
- **主机层面很可能能出网**：`deploy/deploy.sh:26` `git pull --ff-only origin main`（origin = github.com）、L32 `pnpm install --prefer-offline`、README 写在服务器 `pip install`；`uv.lock` 全部指向 pypi.org 官方源，无任何内网镜像配置。
- **很可能经代理**：`deploy.sh:43` 与 `checklist_iq.md` 多处 `curl --noproxy '*'`——只有主机设了 `http_proxy` 才需要这样写。
- **后端服务进程能否出网 = 未知**：`cmab-backend.service` 的 `EnvironmentFile` 不在仓库；systemd 服务不继承交互 shell 的代理变量。上线前必须在 Linux 上以 `prometheus` 用户、在服务环境里跑一次 `curl https://www.ebi.ac.uk/chembl/api/data/status.json` 验证；若走代理，需要在 EnvironmentFile 加 `HTTPS_PROXY` + `NO_PROXY=127.0.0.1,localhost`（httpx 默认 `trust_env=True` 会自动用），并注意总纲说下游系统 httpx 要 `trust_env=False` 绕 ClashX——那是 Mac 开发机的事，Linux 上要反过来。
- 本次 PoC 只在 Mac 直连验证通过（14 次调用全 200）。

### 5.3 若不允许出网：本地镜像方案接入成本
- 数据量：UniProt 人类 reviewed 全集约 2.05 万条（`stream` 接口 `?query=organism_id:9606+AND+reviewed:true&format=json` 全量约 2–3 GB；用 `fields=` 裁剪成 TSV 只有几十 MB）；ChEMBL 官方 PostgreSQL dump（chembl_35 压缩 ~4.5 GB，恢复后 25–30 GB、200+ 张表）。
- 本项目**没有 FDW/dblink**（`01-init.sql` 只装 pgcrypto/pg_trgm/btree_gin/unaccent，IQ 清单 2.7 明确要求"只有这 4 个"），没有 COPY/pg_restore 之外的批量装载代码。全量 ChEMBL 塞进 `cmab_mdm` 不合规（业务库放外部参考库全量），放 `mdm_pg` 另建库或放 `cmc_analytics` 都要走 `cmc-schema-migrations` 立项。
- **务实做法（推荐）**：不装全量，做"瘦镜像"——只抽 PoC 用到的 3 个 ChEMBL 实体（molecule 基本信息+同义词、mechanism、target_components）成 3 张表（几十 MB），UniProt 用 `fields=` 裁剪版 TSV 一张表；由一个 `app/scripts/import_ref_chembl_uniprot.py`（照 `import_equipment_lims.py` 结构：`--dry-run` + CSV 报告）离线导入到 `cmab_mdm.ref_ext`（或新库），刷新频率跟 ChEMBL 半年一版、UniProt 两月一版。预填 service 抽象成 `TargetSourceProvider` 接口，`HttpProvider` / `LocalMirrorProvider` 二选一由配置切换。
- 成本：瘦镜像首次 5–8 人日（含抽取脚本、表、Provider、验证），每次刷新 0.5 人日；全量 dump 方案 8–12 人日 + 存储与运维负担，不推荐。

---

## 6. 工作量估算与风险

### 6.1 按模块（人日，含自测；"改动"= 改现有文件，"新增"= 新文件，"复用"= 直接用）

| 模块 | 必须改动 | 新增 | 可复用 | 估算 |
|---|---|---|---|---|
| A 迁移：靶点表 + bridge 表 + 取号触发器 + updated_at 触发器 + 审计挂载 + lookup 种子 + 索引 | `01-init.sql`、`alembic/env.py` 白名单（顺手补 eqp） | 1 个迁移文件 | `meta.fn_next_code`、`audit.fn_audit_trigger` 三参形式、0040/0025 模板 | 1.5–2 |
| B 后端靶点域 CRUD + publish + bridge 子资源 | `api/v1/__init__.py`、`seed_data.py` 权限、`search/services.py`、`dashboard_service.py`（后两者可选） | `domains/target/*`、`api/v1/targets.py` | 权限守卫、幂等键、审计 GUC 写法 | 3–4 |
| C 预填服务（httpx 封装 + tenacity + 白名单 + Redis 缓存 + 4 步链路 + 启发式建议 + `:prefill` 端点 + 配置项） | `core/config.py` | `shared/http_client.py`、`domains/target/prefill_service.py`、`shared/cache.py` | httpx/tenacity 依赖已在、loguru 上下文、Redis 客户端；PoC 脚本逻辑可直接移植 | 3–4 |
| D SRS 侧接入：substance 回填 INN/xref/类型；`/substances/{code}/targets` 子资源；`target/target_type` 旧列过渡 | `srs/services.py`、`api/v1/substances.py`、`srs/schemas.py` | — | `substance_xref` 已有 ChEMBL/INN 类型 | 1–1.5 |
| E 前端：靶点 4 页 + 常量 + 路由/菜单/搜索/EntityCodeLink + 预填向导（输入 INN → 展示候选/警告 → 勾选亚基/角色 → 生成表单）+ substance 详情页靶点面板 | `App.tsx`、`Sidebar.tsx`、`GlobalSearchBox.tsx`、`EntityCodeLink.tsx`、`SubstanceDetailPage.tsx`、`api/types.ts` | `api/targets.ts`、`modules/targets/*` | `StatusActionsBar`、`PermissionGuard`、`AuditLogPanel`、EQP 页面模板 | 5–7 |
| F 测试：CRUD/权限/关联/预填（httpx 用 `respx` 或 MockTransport 打桩，**测试不许真出网**）+ 审计触发器验证 | — | 3–4 个 test 文件 | conftest 登录夹具、隔离测试库 | 1.5–2 |
| G 部署与验证：Linux 服务环境出网验证、EnvironmentFile 代理项、nginx 超时、`.env.prod.example` 文档 | `deploy/deploy.sh`（可选健康检查）、`.env*.example`、README | — | deploy.sh 流程 | 0.5–1 |
| **主线合计** | | | | **16–22 人日** |
| 可选：靶点走 SRS 式状态机 + 电签 + status_history | | | | +3–5 |
| 可选：独立"分子域"而非复用 srs.substance | | | | +4–6 |
| 兜底：生产不出网 → 瘦镜像 Provider | | | | +5–8 |

### 6.2 前三风险
1. **生产后端进程出网未验证**（§5.2）。是整条链路的前提；配置里判断不出来。缓解：本周就在 172.19.0.105 以服务身份 curl 一次；提前定好 Provider 抽象，出不了网走瘦镜像。
2. **数据语义比想象复杂，"自动"只能到"建议"**：ChEMBL 靶点粒度是 PROTEIN COMPLEX / SELECTIVITY GROUP（IL-23 带出 p40、双抗是 1 条 mechanism 拆 2 靶）、ADC 会带出载荷靶点、target_type/location 是启发式（PD-1 UniProt 没有 Receptor 关键词，只能靠 CD 号）。若不在设计里加 `relation_role`、亚基勾选、`needs_confirm` 标记，审核人会被误导。缓解：预填一律标"建议+依据"，UI 强制人工勾选；bridge 加 `relation_role`。
3. **约定层面的摩擦点会拖工期**：(a) 权限码只能靠 `seed_data.py` 而 dev 库禁重跑 seed，需另写幂等脚本/迁移；(b) `dim/bridge` 命名与本库 `ref/meta` 惯例及总纲 `cmc_analytics.dim` 语义冲突，需负责人先拍板（§1.5）；(c) 审计触发器 v3 逐字段展开会被大 jsonb 拖累，raw 要拆到独立快照表；(d) 枚举三处硬编码 + 前端类型全手写（`schema.d.ts` 不存在），改一处漏一处。这些都不难，但每个都得先做决定，建议立项时一次定完。

### 6.3 建议的最小切分（如果要分期）
- **第 1 期（~8–10 人日）**：A + B（CRUD，不含 publish）+ C（预填端点，先只回 JSON）+ E 里的"预填向导 + 靶点列表/详情" —— 就能在 UI 里输入 INN 看到预填结果并保存靶点。
- **第 2 期（~6–8 人日）**：D（SRS 联动）+ bridge 前端面板 + publish 流 + 搜索/仪表盘 + 部署验证。
- 瘦镜像仅在第 1 期出网验证失败时启动。
