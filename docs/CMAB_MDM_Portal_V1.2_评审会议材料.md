# CMAB MDM Portal V1.2 评审会议材料

| 项目 | 内容 |
|---|---|
| 文档编号 | REV-MDM-001 |
| 版本 | V1.2 Draft |
| 状态 | 待 CMC IT 架构组 + QA + 业务跟头评审 |
| 上位文档 | DEV-MDM-001 V1.2 Draft（偏离说明）|
| 编制 | CMC R&D 实施侧 |
| 日期 | 2026-05-13 |
| 用途 | 一页纸决议表，逐项打勾 |

## 0. 已落地内容（无需评审，仅备查）

- **数据模型 4 域 + 跨域引用对齐 ~97%**（Batch A/B/S8/D/E/F migration 0028+0029+schema 暴露）
- **G1.A 合规必修**：API1 错误码 40404/40405 修正 + UI3 签名理由独立字段 + UI4 GxP 关键动作二次确认（21 CFR Part 11 §11.50）
- **G1.B 状态机契约硬切回归 V1.1 嵌套**：请求 `{comment, signature:{password,meaning,reason}}` + 响应 `StateChangeResponse`
- **G2 中优先级 8 项**：API6 全局搜索响应分组 + API9 11 错误码 + UI1/2/5/6/10/11
- **G3.A 零评审依赖 2 项**：ARCH12 meta.lookup_value + system_config 建表 + seed；API5 POST 创建端点 Location 头

整体加权对齐率：~87% → ~88%（G3.A 后）。详见 DEV-MDM-001 V1.2 Draft 附录 A。

---

## 1. 待评审决议项（共 13 项）

### 1.1 数据模型 / 跨域引用（4 项）

| # | V1.1 出处 | 设计 vs 实施 | 处置选项 | **决议** |
|---|---|---|---|---|
| **S5** | DM §7.3 | `srs.substance_protein.molecular_weight_da` 设计 `NUMERIC(10,2)`，实施 `DOUBLE PRECISION`（Float）| A. 回归 NUMERIC（dev 库精度截断验证）<br>B. 永久接受 Float（更新文档备注质谱测定值容差范围）| ☐ A ☐ B |
| **S6** | DM §7.3 | `pi_theoretical` 设计 `NUMERIC(5,2)`，实施 Float | 同 S5 | ☐ A ☐ B |
| **P3** | DM §9.4 | `project_team UNIQUE (project_id, user_id, role)` 绝对唯一 → "离职后再加入"被代码堵死 | A. 改 partial UNIQUE `WHERE left_at IS NULL`（允许重新加入）<br>B. 保持绝对唯一 + 明确"同人同角色再加入须新建 user 记录" | ☐ A ☐ B |
| **R8** | DM §11.x | 三张 ref 表 `created_by` / `updated_by` 均无 FK 到 auth.user（设计未显式列）| A. 加 FK 约束（建 migration，与 deleted_by 一致）<br>B. 永久接受（语义 FK 由 service 层 current_user.user_id 保证） | ☐ A ☐ B |

### 1.2 PRS 上层未实施（1 项）

| # | V1.1 出处 | 设计 vs 实施 | 处置选项 | **决议** |
|---|---|---|---|---|
| **P8** | DM §9.5 | `prs.project_relationship` 表 + CHECK + UNIQUE + FK 已建（migration 0016），**无 audit trigger / service / API / 前端** | A. Phase 3+ 立即上 service/API/UI（项目血缘 / 衍生关系业务）<br>B. 推迟到 Phase 5 数据治理工具阶段<br>C. 永久不做（删表） | ☐ A ☐ B ☐ C |

### 1.3 架构 ARCH 待评审（1 项）

| # | V1.1 出处 | 设计 vs 实施 | 处置选项 | **决议** |
|---|---|---|---|---|
| **ARCH9** | ARCH §5.1 行 655-657 | 前端技术栈 V1.1 列：React Hook Form + Zod / ECharts / Recharts / React Flow / Ant Design Pro Components。当前 `frontend/package.json` **均无**；表单走 antd 原生 Form，图表与血缘图组件均无 | A. 全部引入（5 个包）<br>B. 评审挑必要项（如 ECharts 用于仪表盘 Phase 5，React Flow 物质/项目血缘图 Phase 5；其他放弃）<br>C. 全部不引入（永久接受差异，理由：antd Form 工作良好；甘特/血缘图已推迟）| ☐ A ☐ B ☐ C |

### 1.4 API V1.1 待评审（4 项）

| # | V1.1 出处 | 设计 vs 实施 | 处置选项 | **决议** |
|---|---|---|---|---|
| **API4** | API §7.2 行 1346-1382 | 项目创建 V1.1 用 `project_manager_username` / `sponsor_username` + 嵌套 `related_substances` / `related_assets` / `team`；实施只接 ID，无嵌套子资源 | A. 改回嵌套（Breaking change，影响 PRS 前端 + 测试，同 G1.B 性质）<br>B. 保持扁平 ID（实施侧简化，写入 V1.2 §8.2 简化条目）| ☐ A ☐ B |
| **API10** | API §5.1.2 行 720-735 | 用户 / 角色 / 权限 12 端点（list/create/lock/unlock/reset-password/角色分配等）全部缺 | A. Phase 4 一并建（与 Admin UI 同步）<br>B. Phase 5/6 推迟（V1.2_draft §9.2.6 UI 已推迟）| ☐ A ☐ B |
| **API11** | API §5.1.7 行 821-832 + §8.4-§8.6 | 全局功能 5 端点：`GET /audit-logs` / `POST /audit-logs:export` / `GET /lookups/{type}` / `GET/POST /signatures` / `GET /system/info` | A. Phase 4 立即做（已有 lookup_value/system_config 表，lookups 端点简单）<br>B. 拆分：lookups/system 端点立即做（ARCH12 已建表），audit-logs/signatures 推迟 Phase 5<br>C. 全部 Phase 5 推迟 | ☐ A ☐ B ☐ C |
| **API13** | API §5.1.3 行 750-756 | `GET/PUT /substances/{code}/protein` / `/adc`、`GET /substances/{code}/xrefs` 独立子资源端点；V1.2 §8.2 已记 GET 用 expand 替代，写端点也未实现 | A. 加写端点（PUT /protein, PUT /adc）<br>B. 永久接受 expand 简化模式（V1.2 §8.2 正式入文档）| ☐ A ☐ B |

### 1.5 UI 信息架构待评审（3 项 — UX 重大改版）

| # | V1.1 出处 | 设计 vs 实施 | 处置选项 | **决议** |
|---|---|---|---|---|
| **UI7** | UI §7.2.1 行 859-887 | 项目详情 Tab 1「概览」V1.1 要求含进度条 / 时间轴 / 团队预览卡 / 关联预览卡；实施仅 Descriptions 字段表 | A. 重构 Tab 1（加进度条 + 团队预览 + 关联预览；甘特图保持推迟）<br>B. 推迟到 Phase 5（与甘特图一起）<br>C. 永久接受现状（写入 V1.2 §9.x 简化条目）| ☐ A ☐ B ☐ C |
| **UI8** | UI §7.3 行 925 | 资产详情 Tab 1 V1.1 要求含「当前阶段时间线」；实施仅 `phase_change_at` 单字段 | A. 加阶段时间线 Timeline 组件<br>B. 推迟到 Phase 5<br>C. 永久接受现状 | ☐ A ☐ B ☐ C |
| **UI9** | UI §6.2.5 行 648-677 | 物质详情「关联」V1.1 设计是 1 Tab × 5 分组（项目/资产/物料/父substance/子substance），实施拆为 2 Tab，缺**父/子 substance 视图**（ADC ↔ antibody 反向引用）| A. 回退合并为 1 Tab × 5 分组 + 补父/子 substance 视图（ADC 业务必需）<br>B. 保持 2 Tab + 补父/子 substance（折中）<br>C. 永久接受现状（不补父/子 substance，ADC 反向追溯能力缺失） | ☐ A ☐ B ☐ C |

---

## 2. 已决推迟到 Phase 4（无需评审，仅备查）

| # | 内容 | 说明 |
|---|---|---|
| ARCH11 | API 限流（slowapi + 4 档 + X-RateLimit-* + 42901 + Retry-After）| 与生产部署 + Redis 一起做 |
| API7 | Idempotency-Key 24h 幂等 + 40905 | 强依赖 Redis；与 ARCH11 同步 |
| API5 子资源 | xref/milestone/team/market_id 等 POST 子资源 Location 头 | G3.A 主资源已做；子资源 V1.1 未明示要求 |
| API12 | `GET /substances/{code}/materials` 反向列表 | 跟 MM 物料域 Phase 4 一起建 |

---

## 3. Phase 4 / Phase 5 范围预案（评审会同步确认）

### Phase 4（生产化 + MM 物料域）

- MM（V1.1 §10）整域：models + service + API + UI + 审计接入 + 全局搜索接入
- ARCH11 限流 + API7 Idempotency-Key + ARCH13 Refresh Token
- Prometheus metrics + 集中日志 + nginx 反代 + k8s manifest
- 数据库备份策略 + 至少一次恢复演练（可审计记录）
- CSV 验证 IQ/OQ 文档包

### Phase 5（Admin + 数据治理 + 体验增强）

- Admin UI：用户 / 角色 / 权限矩阵 / 编码序列 / 字典 / 配置
- API10 用户角色权限 12 端点（如 1.4 决议为 B 路径）
- API11 audit-logs/signatures 端点（如 1.4 决议为 B 或 C）
- 数据治理工具：merge / reject / batch / advance-phase
- Redis 应用层接入（如 G3.B 评审决定不推迟则提前）
- UI7/UI8/UI9 改版（如 1.5 决议为 B）
- fuzzy matching 同一性判定

---

## 4. 评审签字

| 评审人 | 角色 | 决议（同意 / 修订 / 驳回） | 签字 | 日期 |
|---|---|---|---|---|
| | CMC IT 架构组负责人 | | | |
| | QA 质量管理部负责人 | | | |
| | 业务负责人（CMC R&D） | | | |
| | 项目负责人 | | | |

---

## 5. 注释

- 本文件仅作评审决议表使用；实施依据见 DEV-MDM-001 V1.2 Draft 偏离说明
- "永久接受差异"决议需同步更新 V1.1 上位文档下一版（或在 V1.2 §8.2 / §9.x 加正式备注）
- "Phase 4/5 推迟"决议需写入 DEV-MDM-001 V1.2 §10 处置时间表
