# CMAB MDM Portal V1.2 评审会议材料

| 项目 | 内容 |
|---|---|
| 文档编号 | REV-MDM-001 |
| 版本 | V1.2 Draft |
| 状态 | ✅ 评审完成（2026-05-13）|
| 上位文档 | DEV-MDM-001 V1.2 Draft（偏离说明）|
| 编制 | CMC R&D 实施侧 |
| 日期 | 2026-05-13 |
| 用途 | 一页纸决议表，逐项打勾 |
| 决议结果 | 13 项全部完成；A 决议 5 项（P3/R8/API13/UI7/UI8）已通过 Batch H 落地代码；B 决议 8 项（S5/S6/P8/ARCH9/API4/API10/API11/UI9）按各自方式登记 — UI9:B 折中方案补父/子 substance 视图也已通过 H3 落地 |

## 0. 已落地内容（无需评审，仅备查）

- **数据模型 4 域 + 跨域引用对齐 ~97%**（Batch A/B/S8/D/E/F migration 0028+0029+schema 暴露）
- **G1.A 合规必修**：API1 错误码 40404/40405 修正 + UI3 签名理由独立字段 + UI4 GxP 关键动作二次确认（21 CFR Part 11 §11.50）
- **G1.B 状态机契约硬切回归 V1.1 嵌套**：请求 `{comment, signature:{password,meaning,reason}}` + 响应 `StateChangeResponse`
- **G2 中优先级 8 项**：API6 全局搜索响应分组 + API9 11 错误码 + UI1/2/5/6/10/11
- **G3.A 零评审依赖 2 项**：ARCH12 meta.lookup_value + system_config 建表 + seed；API5 POST 创建端点 Location 头

整体加权对齐率：~87% → ~88%（G3.A 后）。详见 DEV-MDM-001 V1.2 Draft 附录 A。

---

## 1. 评审决议结果（2026-05-13 完成，13 项）

### 1.1 数据模型 / 跨域引用（4 项）

| # | V1.1 出处 | **决议** | 落地状态 |
|---|---|---|---|
| **S5** | DM §7.3 | **B**：永久接受 Float（V1.1 §7.3 下版加质谱容差备注）| ✅ 决议（仅文档登记） |
| **S6** | DM §7.3 | **B**：同 S5 | ✅ 决议（仅文档登记） |
| **P3** | DM §9.4 | **A**：partial UNIQUE WHERE left_at IS NULL | ✅ migration 0031 + service + test 重写 |
| **R8** | DM §11.x | **A**：ref 三表 created_by/updated_by 各加 FK（共 6 个） | ✅ migration 0031 |

### 1.2 PRS 上层未实施（1 项）

| # | V1.1 出处 | **决议** | 落地状态 |
|---|---|---|---|
| **P8** | DM §9.5 | **B**：project_relationship 上层推迟 Phase 5 | ✅ 决议（写入 §10 时间表） |

### 1.3 架构 ARCH 待评审（1 项）

| # | V1.1 出处 | **决议** | 落地状态 |
|---|---|---|---|
| **ARCH9** | ARCH §5.1 | **B**：仅引入 ECharts（Phase 5 仪表盘）+ React Flow（Phase 5 血缘图）；其他 3 项放弃 | ✅ 决议（Phase 5 实施时再装包） |

### 1.4 API V1.1 待评审（4 项）

| # | V1.1 出处 | **决议** | 落地状态 |
|---|---|---|---|
| **API4** | API §7.2 | **B**：保持扁平 ID + 无嵌套子资源（V1.2 §8.2 简化条目） | ✅ 决议（仅文档登记） |
| **API10** | API §5.1.2 | **B**：用户/角色/权限 12 端点 Phase 5/6 推迟 | ✅ 决议（与 Admin UI 同步） |
| **API11** | API §5.1.7 | **B**：拆分 — lookups/system 立即做，audit-logs/signatures 推 Phase 5 | ✅ H2 落地 lookups + system；其余 Phase 5 |
| **API13** | API §5.1.3 | **A**：加 PUT /protein 和 PUT /adc 独立写端点 | ✅ H2 落地（含 AdcExtension schema）|

### 1.5 UI 信息架构待评审（3 项 — UX 重大改版）

| # | V1.1 出处 | **决议** | 落地状态 |
|---|---|---|---|
| **UI7** | UI §7.2.1 | **A**：重构 Tab 1（加 Progress + Statistic + 关联跳转；甘特图保持 Phase 5 推迟） | ✅ H3 落地（computeProjectProgress + Row/Col 布局） |
| **UI8** | UI §7.3 | **A**：加 9-phase Timeline 组件 | ✅ H3 落地（Timeline mode="left"） |
| **UI9** | UI §6.2.5 | **B**：保持 2 Tab + 补父/子 substance（折中）| ✅ H3 落地（新加"血缘关系" Tab + `/substances/{code}/lineage` endpoint + LineageTab.tsx 组件） |

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
