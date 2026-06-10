# CMAB MDM Portal 全面审查报告

- 日期：2026-06-10
- 审查方式：多 agent 并行审查（22 个审查任务），Critical/High 发现经独立 agent 对抗性复核（在仓库中找反证后才确认）
- 审查范围：docs/ 权威文档、backend/app 9 域 + core/shared/api/迁移链/scripts、frontend/src 全模块、backend/tests、文档↔代码匹配性
- 约束：只读审查，未修改任何现有文件，未执行任何改变状态的命令
- 渲染时间：2026-06-10 23:56；进度：18/26 个审查任务已完成并落盘

> **注意：阶段性报告**，以下任务尚未完成（受会话限额/网络影响，补跑中）：后端:be-audit、后端:be-prs、后端:be-core、后端:be-migrations、前端:materials+equipments、前端:api+stores+routes+shared、匹配性:偏离说明V1.3↔代码、匹配性:前端↔API

---

## 0. 执行摘要

- 发现总数：**283** 条（基于已完成的 18/26 个审查任务）
- 严重度分布：Critical **0** / High **19** / Medium **100** / Low **164**
- 其中 19 条 Critical/High 的对抗复核因中断未完成，已在正文标注「复核未完成」

<!-- TOP10_PLACEHOLDER -->

---

## 1. 文档审查发现

### 架构设计+数据模型(内部质量)（23 条：High 1 / Medium 10 / Low 12）

> 两份文档整体结构完整、技术细节扎实，但 V1.2（EQP 设备域）增量仅追加在修订记录与局部章节，正文图表/范围表/初始化脚本/角色清单大量未同步，形成多处自相矛盾；两份文档之间存在表清单、角色集、双权限组合、状态枚举等口径不一致；并存在 ref.material_substance、material_attribute、result 列等"幽灵对象"。共 23 项发现，多为 Medium/Low。

**[DOC-架构设计+数据模型(内部-01] [High/置信度:高] EQP 范围自相矛盾**
- 位置：`docs/CMAB_MDM_Portal_架构设计文档_V1_1.md:120 与 41/73`
- 问题：§1.3.2 范围外明确写'设备主数据（未来纳入 CMMS 或独立 Equipment Master）'，但适用范围(§41)、§1.2.1/§1.2.2 已将 Equipment(EQP) 列为 V1.2 新增的第五业务域。
- 为什么是问题：In-Scope/Out-of-Scope 直接冲突，读者无法判断设备域是否在本期范围内。
- 建议：§1.3.2 删除或改写设备主数据条目，§1.3.1 In-Scope 表补 EQP 行。
- 对抗复核：⏳ 复核未完成（中断），按原审查员置信度采信

**[DOC-架构设计+数据模型(内部-02] [Medium/置信度:高] V1.2 图表未含 EQP**
- 位置：`docs/CMAB_MDM_Portal_架构设计文档_V1_1.md:204-227,453-495,513-561`
- 问题：§3.1 域分治图、§4.2 容器图、§4.3 组件图、§6.1 schema 表均只画 SRS/PRS/ARS/MM，未含 V1.2 新增的 eqp 域/模块/schema。修订记录已声明五域。
- 为什么是问题：正文核心架构图与已声明的五域模型不符，易误导。
- 建议：在各架构图与 schema 清单补 eqp，或加注'V1.2 增量见数据模型§10A'。

**[DOC-架构设计+数据模型(内部-03] [Medium/置信度:高] 初始化脚本缺 eqp schema**
- 位置：`docs/CMAB_MDM_Portal_数据模型设计文档_V1_1.md:204-219,214`
- 问题：§2.3 CREATE SCHEMA 与 GRANT、default search_path 只建 auth/meta/audit/srs/ars/prs/mm/ref，未建 eqp；但 §2.1 schema 列表已含 eqp（V1.2）。
- 为什么是问题：按§2.3 初始化脚本部署将无 eqp schema，与§2.1/§10A 矛盾。
- 建议：§2.3 补 CREATE SCHEMA eqp、GRANT 与 search_path。

**[DOC-架构设计+数据模型(内部-04] [Medium/置信度:高] ref.material_substance 幽灵表**
- 位置：`docs/CMAB_MDM_Portal_架构设计文档_V1_1.md:735 与 docs/CMAB_MDM_Portal_数据模型设计文档_V1_1.md:1744-1842`
- 问题：架构§6.4 与数据模型§2.1/§3.1 列出 ref.material_substance，但数据模型§11 未定义该表，实际设计为 mm.material.substance_id 直连 FK（§10.1），代码中也无此表。
- 为什么是问题：表清单引用了不存在且与直连 FK 设计矛盾的表。
- 建议：删除 ref.material_substance 引用，统一为 mm.material 直连 FK 说明。

**[DOC-架构设计+数据模型(内部-05] [Medium/置信度:高] material_attribute 幽灵表**
- 位置：`docs/CMAB_MDM_Portal_架构设计文档_V1_1.md:734 与 docs/CMAB_MDM_Portal_数据模型设计文档_V1_1.md:147`
- 问题：架构§6.1 与数据模型§2.1 的 mm 主要表均列出 material_attribute，但数据模型§10 仅定义 material、material_batch，无 material_attribute 表，代码亦无。
- 为什么是问题：schema 清单引用未定义的表，属遗漏或残留。
- 建议：删除 material_attribute，或在§10 补该表定义。

**[DOC-架构设计+数据模型(内部-06] [Medium/置信度:高] 预设角色清单不一致**
- 位置：`docs/CMAB_MDM_Portal_架构设计文档_V1_1.md:944-956 与 docs/CMAB_MDM_Portal_数据模型设计文档_V1_1.md:483-490`
- 问题：架构§7.2.2 列 6 个角色(SystemAdmin/SubstanceSteward/ProjectManager/CMCResearcher/QAReviewer/ReadOnlyUser)，缺 REGULATORY_USER；数据模型§4.3 列 7 个，§10A.2 又增 CMC_EQUIPMENT_ADMIN/CMC_WAREHOUSE_ADMIN。
- 为什么是问题：两文档角色集不同，且命名风格 CamelCase vs UPPER_SNAKE 不统一。
- 建议：架构§7.2.2 补齐 REGULATORY_USER 及 V1.2 两角色，统一命名为 role_code。

**[DOC-架构设计+数据模型(内部-07] [Medium/置信度:高] substance 状态枚举缺 obsoleted**
- 位置：`docs/CMAB_MDM_Portal_架构设计文档_V1_1.md:245,775 与 docs/CMAB_MDM_Portal_数据模型设计文档_V1_1.md:1018-1019,713`
- 问题：架构§3.2.1/§6.3 生命周期为 Draft/Registered/Active/Restricted/Deprecated(5 值)，未含 obsoleted；数据模型 substance CHECK 与 lookup_value 含 obsoleted(6 值)，§11.1 业务规则也用 status='obsoleted'。
- 为什么是问题：架构状态机缺一个实际存在的终止态，与数据模型/约束不符。
- 建议：架构§3.2.1/§6.3 补 obsoleted 状态。

**[DOC-架构设计+数据模型(内部-08] [Medium/置信度:高] 容器图 schema 缺 meta**
- 位置：`docs/CMAB_MDM_Portal_架构设计文档_V1_1.md:481-488 与 729-738`
- 问题：§4.2 容器图 PostgreSQL Schemas 列 srs/prs/ars/mm/ref/audit/auth，缺 meta(及 eqp)；但§6.1 schema 表含 meta 且 meta 承载编码序列/字典/配置。
- 为什么是问题：同一文档内 schema 清单不一致，meta 是核心 schema 不应缺。
- 建议：§4.2 容器图补 meta(及 eqp)。

**[DOC-架构设计+数据模型(内部-09] [Medium/置信度:高] srs 表清单内部不一致**
- 位置：`docs/CMAB_MDM_Portal_数据模型设计文档_V1_1.md:144 与 939-947`
- 问题：§2.1 schema 概览的 srs 主要表只列 substance/substance_protein/substance_xref/substance_status_history，遗漏 substance_adc、substance_small_molecule、substance_alias；而§7.1 完整列出 7 张表。
- 为什么是问题：同文档两处表清单不一致，概览漏 3 张实际定义的表。
- 建议：§2.1 补齐 srs 三张缺失表，或注明仅列代表表。

**[DOC-架构设计+数据模型(内部-10] [Medium/置信度:中] audit_log 引用不存在的 result 列**
- 位置：`docs/CMAB_MDM_Portal_数据模型设计文档_V1_1.md:912 与 796-832`
- 问题：§6.4 V1.1 注 1 称失败签名'写 audit_log.action=SIGN 且 result=failed'，§15.2.2 同；但§6.2 audit_log DDL 无 result 列，action CHECK 也无对应失败枚举。
- 为什么是问题：描述的持久化字段在表结构中不存在，无法落地。
- 建议：明确失败标记落 extra JSONB 或新增 result 列并加入 DDL/CHECK。

**[DOC-架构设计+数据模型(内部-11] [Medium/置信度:中] 项目双权限组合不一致**
- 位置：`docs/CMAB_MDM_Portal_架构设计文档_V1_1.md:960 与 docs/CMAB_MDM_Portal_数据模型设计文档_V1_1.md:2280`
- 问题：架构§7.2.2 称项目状态变更要求 project:update+project:sign；数据模型§15.3 关键约束表写 project:approve+sign。资产侧两文档均为 asset:update+sign。
- 为什么是问题：同一关键动作的双权限组合在两文档取值不同，实施会歧义。
- 建议：统一项目双权限组合口径(update 或 approve)，两文档对齐。

**[DOC-架构设计+数据模型(内部-12] [Low/置信度:高] 架构 schema 表漏列子表**
- 位置：`docs/CMAB_MDM_Portal_架构设计文档_V1_1.md:731-733 与 docs/CMAB_MDM_Portal_数据模型设计文档_V1_1.md:939-947,1343-1351`
- 问题：架构§6.1 主要表列：srs 漏 substance_small_molecule/substance_alias；prs 漏 project_relationship；auth 漏 login_history/password_history，与数据模型实际定义的表不齐。
- 为什么是问题：架构表清单作为上位参考与数据模型不一致。
- 建议：补齐或在表头注明'仅列代表性表'。

**[DOC-架构设计+数据模型(内部-13] [Low/置信度:高] 有序列表编号断裂**
- 位置：`docs/CMAB_MDM_Portal_架构设计文档_V1_1.md:368-398,925-937,1368-1376`
- 问题：docx 派生导致跨标题的有序列表连续编号：§3.4.1 用 1-6、§3.4.2 续 7-10、§3.4.3 续 11-14；§7.2.1 认证流程从 15 起；§10.4 从 22 起。各场景应各自从 1 计。
- 为什么是问题：编号断裂影响可读性与引用('第 3 步'歧义)。
- 建议：重置各列表起始编号(docs-extract 后处理或源文档修正)。

**[DOC-架构设计+数据模型(内部-14] [Low/置信度:高] 迁移流程编号从 10 起**
- 位置：`docs/CMAB_MDM_Portal_数据模型设计文档_V1_1.md:2104-2114`
- 问题：§14.4.1 历史数据导入流程 6 个步骤被编号为 10-15(应为 1-6)，系 docx 列表连续编号派生 artifact。
- 为什么是问题：步骤编号与实际顺序不符，影响引用。
- 建议：重置为 1-6。

**[DOC-架构设计+数据模型(内部-15] [Low/置信度:中] 资产阶段词汇不一致**
- 位置：`docs/CMAB_MDM_Portal_架构设计文档_V1_1.md:281 与 docs/CMAB_MDM_Portal_数据模型设计文档_V1_1.md:740-748,1233-1235`
- 问题：架构§3.2.3 ARS 注册状态用 Pre-clinical/IND/Phase I-III/NDA-BLA/Approved/Marketed；数据模型 asset_phase/CHECK 用 discovery/preclinical/phase_1..3/submission/approved/marketed/discontinued。
- 为什么是问题：资产阶段枚举两文档用词不同(IND/NDA-BLA vs submission/discovery)，难映射。
- 建议：统一资产阶段术语，或在架构注明为概念描述非枚举值。

**[DOC-架构设计+数据模型(内部-16] [Low/置信度:中] 文档头版本/日期与修订记录不符**
- 位置：`docs/CMAB_MDM_Portal_数据模型设计文档_V1_1.md:16-23 与 28-32`
- 问题：封面元数据版本=V1.1、发布日期=2026-05-11，但修订记录中 V1.1 日期为 2026-05-12(05-11 实为 V1.0)，且已含 V1.2 修订行(§10A EQP)，封面版本未随之更新。架构文档同样存在。
- 为什么是问题：封面声明版本/日期与自身修订记录及实际内容(V1.2)不一致。
- 建议：封面发布日期对齐 V1.1(05-12)，并说明 md 已含 V1.2 增量。

**[DOC-架构设计+数据模型(内部-17] [Low/置信度:中] 路线图表述与阶段不符**
- 位置：`docs/CMAB_MDM_Portal_架构设计文档_V1_1.md:1030-1041`
- 问题：§8.1 称'总周期 9-12 个月达到 SRS+PRS+ARS 三模块上线'，但同表 ARS 在 Phase 3(Month 7-8)完成，Phase 4-5(Month 9-12+)为 MM/治理，文字与阶段表错位。
- 为什么是问题：概述句与阶段表时间不一致，易误读上线范围。
- 建议：改为'约 8 个月完成 SRS/PRS/ARS，9-12 个月完成 MM 与生产化'。

**[DOC-架构设计+数据模型(内部-18] [Low/置信度:中] Study 域有编码无实现**
- 位置：`docs/CMAB_MDM_Portal_架构设计文档_V1_1.md:75,755 与 docs/CMAB_MDM_Portal_数据模型设计文档_V1_1.md(无 study 表)`
- 问题：架构§1.2.1 四层编码含 Study，§6.2 给出 STD-2026-0234 编码规则，§3.3 有 Study→Project；但数据模型未定义任何 prs.study 表。
- 为什么是问题：上位文档描述的 Study 编码/实体在数据模型中完全缺失。
- 建议：注明 Study 为后续阶段，或在数据模型加占位说明。

**[DOC-架构设计+数据模型(内部-19] [Low/置信度:中] 下游系统命名不一致**
- 位置：`docs/CMAB_MDM_Portal_架构设计文档_V1_1.md:287 与 35/1684-1689`
- 问题：MM 下游系统在§3.2.4 称 'cmc-inventory（实验室运营平台）'，而修订记录 V1.2 与数据模型§10A 称 'CMC LabOps Portal（cmc-inventory 仓库）'，名称口径混用。
- 为什么是问题：同一下游系统多名易混淆。
- 建议：统一为'CMC LabOps Portal(cmc-inventory)'并全文一致。

**[DOC-架构设计+数据模型(内部-20] [Low/置信度:中] ERD 未含 ref.project_asset**
- 位置：`docs/CMAB_MDM_Portal_数据模型设计文档_V1_1.md:286-300,1814-1842`
- 问题：§3.1 核心 ERD 仅画 ref.project_substance、ref.asset_substance，未含§11.4 定义的 ref.project_asset(Project→Asset)；架构§3.3 引用方向有 Project→Asset。
- 为什么是问题：ERD 与实际定义的引用表不全，遗漏一条核心关联。
- 建议：§3.1 ERD 补 ref.project_asset。

**[DOC-架构设计+数据模型(内部-21] [Low/置信度:中] xref_type 取值口径不全**
- 位置：`docs/CMAB_MDM_Portal_数据模型设计文档_V1_1.md:805-807 与 1096`
- 问题：§6.5 注释/§7.6 注释列 xref_type 含 ChEMBL、TRADE_NAME 等，但架构§6.3 示意只写'INN/USAN/CAS/UNII/GSRS_UUID/ChEMBL/商品名'，与数据模型 CHECK 的 12 值(含 DRUGBANK/GENERIC_NAME/PROJECT_CODE/OTHER)不完全一致。
- 为什么是问题：枚举示意值不一致，可能误导实现。
- 建议：架构改为引用数据模型 CHECK 全集，避免重复枚举。

**[DOC-架构设计+数据模型(内部-22] [Low/置信度:低] ERD 类型注释与 CHECK 略偏**
- 位置：`docs/CMAB_MDM_Portal_数据模型设计文档_V1_1.md:805,826 与 1016-1017`
- 问题：§6.3(架构)及 ERD 文字 substance_type 列 'mab/bispecific/adc/fusion/small_molecule'，未含数据模型 CHECK 实际的 oligonucleotide/other；§7.2.1 字段说明写 'oligo' 而 CHECK 为 'oligonucleotide'。
- 为什么是问题：类型枚举在说明文字与 CHECK 间存在缺项/缩写不一致。
- 建议：统一类型枚举与缩写(oligonucleotide)。

**[DOC-架构设计+数据模型(内部-23] [Low/置信度:低] 后续文档清单不互相对齐**
- 位置：`docs/CMAB_MDM_Portal_架构设计文档_V1_1.md:1355-1362`
- 问题：架构§10.3 后续文档清单未列 MIGRATE-MDM-001，而数据模型§15.5 列出该文档；两文档的派生文档清单不一致。
- 为什么是问题：文档体系清单口径不统一。
- 建议：两文档同步后续文档清单。

### API规范+UI信息架构(内部质量)（24 条：Medium 12 / Low 12）

> 两份文档整体结构完整、内容详尽，但存在多处自相矛盾与跨文档不一致：错误码体系结构与域偏移冲突、版本元数据落后于正文(V1.1标头含V1.2内容)、状态机/签字动作与端点清单缺口、UI引用的资产字段与系统端点在API/数据模型中缺失、同一示例编码前后不一致、EQP设备域在搜索/路由/权限表未同步更新。多为Medium级文档质量与契约一致性问题，建议在下一版统一勘误。

**[DOC-API规范+UI信息架构-01] [Medium/置信度:高] 错误码结构与域偏移自相矛盾**
- 位置：`CMAB_MDM_Portal_API接口规范_V1_1.md:606-613 与 :657-668`
- 问题：§4.1 定义5位码前3位=HTTP状态码(HTTPABB)，§4.3 域偏移却给出 41001/42001/43001 等，前3位410/420/430 非有效HTTP码，且42001与422xx段冲突。
- 为什么是问题：两套编码规则并存，客户端按前3位解析会误判
- 建议：统一域码方案，改用后2位+独立域段或显式说明例外

**[DOC-API规范+UI信息架构-02] [Medium/置信度:高] ARS端点索引缺审计/状态历史**
- 位置：`CMAB_MDM_Portal_API接口规范_V1_1.md:790-808;CMAB_MDM_Portal_UI信息架构与线框图_V1_1.md:934-935`
- 问题：SRS/PRS 索引含 /audit-logs 与 /status-history，ARS(§5.1.5)未列；但UI资产详情页明确有'状态历史'与'审计'两个Tab，端点缺失。
- 为什么是问题：UI依赖的资产历史端点在API无定义
- 建议：在§5.1.5补 assets/{code}/audit-logs 与 status-history

**[DOC-API规范+UI信息架构-03] [Medium/置信度:高] 全局搜索未纳入EQP设备**
- 位置：`CMAB_MDM_Portal_API接口规范_V1_1.md:1710 与 :491;CMAB_MDM_Portal_UI信息架构与线框图_V1_1.md:32`
- 问题：V1.2 新增 EQP 设备域(§5.1.6A)与设备菜单，但 §8.3/§3.2.2 全局搜索 types 枚举仍仅 substance,project,asset,material，未含 equipment。
- 为什么是问题：新增域未同步到横切搜索契约
- 建议：搜索 types 增加 equipment 并更新命中字段说明

**[DOC-API规范+UI信息架构-04] [Medium/置信度:高] 搜索结果页与自身约束矛盾**
- 位置：`CMAB_MDM_Portal_UI信息架构与线框图_V1_1.md:1013-1030 与 :236-240`
- 问题：§3.2.2 标注 Phase1-3 搜索不含物料，但§7.5 结果页含'物料(4)'类型筛选与4条结果，且总数'18'=4+8+2+4 已计入物料。
- 为什么是问题：同文档内物料是否参与搜索表述冲突
- 建议：结果页线框与总数去除物料或统一标注Phase4

**[DOC-API规范+UI信息架构-05] [Medium/置信度:高] 同一物质内部代号前后冲突**
- 位置：`CMAB_MDM_Portal_UI信息架构与线框图_V1_1.md:284 与 :560,:581`
- 问题：SUB-0000123 在§3.4.2 Page Header 标为 CMAB-203，而§6.2.1/§6.2.2 详情标为 CMAB-101；API列表(:887)中 SUB-0000123=CMAB-101。
- 为什么是问题：同一示例实体编码不一致，易误导实现
- 建议：统一 SUB-0000123 内部代号为 CMAB-101

**[DOC-API规范+UI信息架构-06] [Medium/置信度:高] 版本标头落后于正文内容**
- 位置：`CMAB_MDM_Portal_API接口规范_V1_1.md:19,33;CMAB_MDM_Portal_UI信息架构与线框图_V1_1.md:18,32`
- 问题：两文档元数据'版本'仍为 V1.1/Draft，但修订记录与正文已含 V1.2 增量(EQP设备域、equipment权限、?code预填)，标头未升版。
- 为什么是问题：封面版本与实际内容不符，易引用错版
- 建议：封面版本升至V1.2或注明含V1.2增量

**[DOC-API规范+UI信息架构-07] [Medium/置信度:中] error.type字典覆盖不全**
- 位置：`CMAB_MDM_Portal_API接口规范_V1_1.md:670-698`
- 问题：§4.4 称所有401/403/422响应均带 meta.error.type，但字典漏列 40303 data_access_denied、40304 operation_not_allowed、42202 reference_in_use。
- 为什么是问题：前端按type分流时遇缺失值落入兜底
- 建议：补全403/422全部业务码到 error.type 字典

**[DOC-API规范+UI信息架构-08] [Medium/置信度:中] Project状态机含无端点转换**
- 位置：`CMAB_MDM_Portal_API接口规范_V1_1.md:2337-2354 与 :765-789`
- 问题：§11.2.2 项目状态机含 start(initiated→active)、resume(on_hold→active)、complete 转换及 on_hold 态，但§5.1.4 仅有 :approve / :terminate，无 :start/:hold/:resume/:complete。
- 为什么是问题：状态机引用的迁移在端点清单中无法触发
- 建议：补齐项目状态机端点或在图中标注自动/外部触发

**[DOC-API规范+UI信息架构-09] [Medium/置信度:中] UI签字动作与API端点不符**
- 位置：`CMAB_MDM_Portal_UI信息架构与线框图_V1_1.md:1232-1234`
- 问题：§9.2.1 声称 SRS 签字动作含 activate/obsolete、PRS 含 complete，但 API §5.1.3/5.1.4 无 :activate/:obsolete/:complete 端点(activate为自动)。
- 为什么是问题：UI交互引用了不存在的状态变更端点
- 建议：对齐UI签字动作集与API实际端点

**[DOC-API规范+UI信息架构-10] [Medium/置信度:中] UI资产字段API/模型无对应**
- 位置：`CMAB_MDM_Portal_UI信息架构与线框图_V1_1.md:939;CMAB_MDM_Portal_API接口规范_V1_1.md:1544-1568`
- 问题：§7.3.0 资产列/筛选含 modality、approval_status、target_indication、sponsor，但 API 资产 schema 与数据模型 ars.asset 仅有 indication/current_phase/status，无这些字段(modality属substance)。
- 为什么是问题：UI引用的资产属性在契约与数据模型中缺失
- 建议：对齐字段名(indication)并补 approval_status/sponsor 定义

**[DOC-API规范+UI信息架构-11] [Medium/置信度:中] UI引用未定义系统端点**
- 位置：`CMAB_MDM_Portal_UI信息架构与线框图_V1_1.md:395;CMAB_MDM_Portal_API接口规范_V1_1.md:837-848`
- 问题：§4.2.2 仪表盘卡片来源含 /api/v1/system/announcements 及'待办聚合''项目状态分布'聚合API，但 API §5.1.7 仅有 /system/info，相关端点未定义。
- 为什么是问题：UI依赖的仪表盘聚合端点无契约支撑
- 建议：API补充公告/统计聚合端点或在UI标注待定

**[DOC-API规范+UI信息架构-12] [Medium/置信度:中] 路由表未含设备及部分编辑页**
- 位置：`CMAB_MDM_Portal_UI信息架构与线框图_V1_1.md:1365-1391`
- 问题：§12.1 路由清单缺 /equipments/*(V1.2新增设备4页)、/assets/{code}/edit(§7.3.3存在)、/materials/{code}/edit，与§2.1导航及正文不符。
- 为什么是问题：路由权威清单落后于导航与页面正文
- 建议：路由表补登设备四页与缺失的编辑路由

**[DOC-API规范+UI信息架构-13] [Low/置信度:高] 章节号9.2.1重复**
- 位置：`CMAB_MDM_Portal_UI信息架构与线框图_V1_1.md:1199 与 :1222`
- 问题：存在两个'9.2.1'：'确认对话框模式'(1199)与'状态变更通用交互模式'(1222)，编号重复。
- 为什么是问题：重复编号导致交叉引用歧义
- 建议：后者改为 9.2.2 并顺延

**[DOC-API规范+UI信息架构-14] [Low/置信度:中] 域错误码段说明数值不符**
- 位置：`CMAB_MDM_Portal_API接口规范_V1_1.md:657 与 :663-668`
- 问题：§4.3 标题写'各域分配100段'，正文与示例却用 +1000/+2000 偏移(即1000段)，描述与实际不一致。
- 为什么是问题：段宽描述自相矛盾
- 建议：标题改为'各域分配1000段'

**[DOC-API规范+UI信息架构-15] [Low/置信度:中] HTTP码示例列表漏项**
- 位置：`CMAB_MDM_Portal_API接口规范_V1_1.md:610 与 :651,:655`
- 问题：§4.1 前3位示例仅列 400/401/403/404/409/422/429/500，但错误码表实含 423(42301)、503(50301)，示例不完整。
- 为什么是问题：示例与实际状态码集不一致
- 建议：示例补 423、503

**[DOC-API规范+UI信息架构-16] [Low/置信度:中] 权限可见性表缺设备行**
- 位置：`CMAB_MDM_Portal_UI信息架构与线框图_V1_1.md:161-169`
- 问题：§2.2 模块权限可见性表未含'设备'模块行，而§2.1导航与V1.2修订已加入设备(equipment:read)。
- 为什么是问题：权限矩阵未随新增模块更新
- 建议：表中增加'设备'行及各角色可见性

**[DOC-API规范+UI信息架构-17] [Low/置信度:中] 状态色映射表漏substance弃用态**
- 位置：`CMAB_MDM_Portal_UI信息架构与线框图_V1_1.md:117-125 与 :1112`
- 问题：§1.2.2 状态色表 substance 列'弃用/终止'仅列 obsoleted，未含 deprecated；而 StatusBadge(§8.3)与§8.5均含 deprecated。
- 为什么是问题：状态枚举在两处表述不全
- 建议：色映射表 substance 补 deprecated

**[DOC-API规范+UI信息架构-18] [Low/置信度:中] approve文案与响应状态不一致**
- 位置：`CMAB_MDM_Portal_API接口规范_V1_1.md:1141 与 :1166`
- 问题：§6.5 文字称'状态从 draft→registered→active'，但成功响应 new_status='registered'(未到active)，仅靠下文auto-activate隐含说明。
- 为什么是问题：示例响应与描述目标态不一致易误读
- 建议：在响应旁注明随后自动 activate

**[DOC-API规范+UI信息架构-19] [Low/置信度:中] UI引入API无对应字段**
- 位置：`CMAB_MDM_Portal_UI信息架构与线框图_V1_1.md:583,:610`
- 问题：§6.2.2/§6.2.3 详情展示'显示名称''理论 pI'等字段，API Substance/Protein schema 无 display_name、pI 字段。
- 为什么是问题：线框字段无契约来源
- 建议：确认字段来源或从线框移除

**[DOC-API规范+UI信息架构-20] [Low/置信度:中] 团队删除用数字ID违URL规范**
- 位置：`CMAB_MDM_Portal_API接口规范_V1_1.md:781`
- 问题：§5.1.4 DELETE /projects/{code}/team/{user_id} 用数字 user_id 作标识，违反 §1.2.1'对外用业务编码而非数字ID'。
- 为什么是问题：URL标识策略自相违背
- 建议：改用 username 或在§1.2.1注明子资源例外

**[DOC-API规范+UI信息架构-21] [Low/置信度:低] 登录页版本号与系统不符**
- 位置：`CMAB_MDM_Portal_UI信息架构与线框图_V1_1.md:330 与 :260,:219`
- 问题：§4.1.1 登录页页脚写'系统版本 v1.0.0'，而 API/health 与应用版本为 1.1.0，侧边栏/页脚也称显示版本号。
- 为什么是问题：示例版本号过期
- 建议：页脚版本改为与当前一致

**[DOC-API规范+UI信息架构-22] [Low/置信度:低] 示例资产AST-0023阶段不一致**
- 位置：`CMAB_MDM_Portal_UI信息架构与线框图_V1_1.md:665 与 :1028`
- 问题：§6.2.5 关联资产 AST-0023 阶段标'临床I'，§7.5 搜索结果同一资产标'Phase II'，示例阶段矛盾。
- 为什么是问题：同一示例资产阶段前后不一
- 建议：统一 AST-0023 示例阶段

**[DOC-API规范+UI信息架构-23] [Low/置信度:低] 合并入口Phase边界表述冲突**
- 位置：`CMAB_MDM_Portal_UI信息架构与线框图_V1_1.md:86 与 :1189`
- 问题：§1.1.4 称物质合并属Phase5、Phase1-3不显示入口不纳UAT；§9.2 二次确认清单又列'Substance 弃用/合并/删除'。
- 为什么是问题：合并功能是否当前可见表述不一
- 建议：§9.2 标注合并为Phase5或移除

**[DOC-API规范+UI信息架构-24] [Low/置信度:低] 抽取产物畸形JSON**
- 位置：`CMAB_MDM_Portal_API接口规范_V1_1.md:125,:512,:1825`
- 问题：派生md存在畸形/非法JSON：列表示例 data:[, ]、批量 items:[,, ]、审计 field_changes 含未转义引号，影响可读性与复制可用性。
- 为什么是问题：docx转md遗留格式瑕疵
- 建议：源docx修正示例或抽取后清洗

### 偏离说明修订链条（15 条：Medium 5 / Low 10）

> 封版衔接本身完整：V1.2 cap 0036 与 V1.3 覆盖 0037-0044 无遗漏区间，head 0044 与 alembic 实际一致，E1-E13 在四份修订清单均可对上，13 项评审决议承接基本闭环。主要问题集中在：S7 编号重复、V1.3 工作清单漏 D.4 与 React Flow 承接、ARCH 修订#9 与 0036 GUC 实现矛盾未登记勘误、V1.2 内部多处过时残留（"9 项"、277/278、OQ 分级数字 183≠174）。

**[DOC-偏离说明修订链条-01] [Medium/置信度:高] 偏离编号 S7 重复使用**
- 位置：`docs/CMAB_MDM_Portal_设计基准偏离说明_V1.2_draft.md:126 与 :990`
- 问题：§2.4 中 S7=protein hash 归一化算法加强（migration 0021）；附录 D.4 又将 extinction_coefficient INT→Float 命名为 S7（修订十一），修订历史行也写"附录 D.4 S7 决议"。同一编号指向两个完全不同的偏离项。
- 为什么是问题：S7 作为追溯键被交叉引用时语义二义，审计/吸收时易错配条目。
- 建议：D.4 改用未占用编号（如 S14），并全文替换"D.4 S7"引用。

**[DOC-偏离说明修订链条-02] [Medium/置信度:高] V1.3 工作清单遗漏 D.4 吸收项**
- 位置：`docs/CMAB_MDM_Portal_设计基准偏离说明_V1.3_draft.md:113 对照 V1.2_draft.md:1024-1029`
- 问题：V1.2 附录 D 落地表列 4 项均"⏳ 等待 V1.3 docx 修订"（D.1-D.4），但 V1.3 §5 工作项 3 只写"S5/S6、API4、ARCH9"三项，D.4 S7（extinction_coefficient，migration 0035）未列入。
- 为什么是问题：V1.3 是修订批次的决议依据，漏项将导致 docx 吸收时遗漏 D.4。
- 建议：§5 工作项 3 补"+ D.4 extinction_coefficient"。

**[DOC-偏离说明修订链条-03] [Medium/置信度:高] React Flow 决议承接缺失**
- 位置：`docs/CMAB_MDM_Portal_设计基准偏离说明_V1.3_draft.md:45,49`
- 问题：ARCH9:B 决议为"Phase 5 引入 ECharts + React Flow"。V1.3 声明 Phase 5 全部完成，但 React Flow 未引入（仅括注），§2.2 "B 决议中仍未实施项"只列 P8，§5 工作清单也无 React Flow/血缘图升级追踪项。
- 为什么是问题：B 决议部分未兑现却未登记为开口项，决议闭环断链。
- 建议：§2.2 未实施项补 React Flow（血缘图升级），并入 §5 清单或显式改决议。

**[DOC-偏离说明修订链条-04] [Medium/置信度:高] ARCH修订#9与0036实现矛盾未勘误**
- 位置：`docs/V1.1_修订清单/ARCH-MDM-001_修订清单.md:147（修订#9）`
- 问题：修订#9 要求"禁止通过 SET LOCAL 注入上下文让触发器读取，即便使用 SET LOCAL 关键字"。但 migration 0036 v3 触发器实际经 current_setting('app.*') 读取 set_config(is_local=true) 注入值（已实物核对 :71-76）。E13 只修正了 API §2.6 与 API 清单修订#20，ARCH 清单 V1.3 勘误段（E7-E11）无对应条目。
- 为什么是问题：若 ARCH V1.1 按#9 吸收，正文将与现行实现直接矛盾，且无勘误指引。
- 建议：ARCH 清单补勘误（可编 E14）联动 E13，区分连接级 SET LOCAL 与事务级 set_config。

**[DOC-偏离说明修订链条-05] [Medium/置信度:高] OQ 风险分级数字错误未勘误**
- 位置：`docs/CMAB_MDM_Portal_设计基准偏离说明_V1.2_draft.md:12（修订十段）及 :46`
- 问题：修订十两处写"107 Critical + 72 Major + 4 Minor"，总和 183≠174，与 csv_oq_traceability.md:40 实际"101+68+5"不符。V1.3 §4 称"总览已对账修正"，但 V1.2 原文未加勘误标注。
- 为什么是问题：V1.2 是只读归档合规文档，错误数字无更正痕迹，证据链对不上。
- 建议：在 V1.2 该两处加 2026-06 勘误括注，指向 csv_oq_traceability 修正值。

**[DOC-偏离说明修订链条-06] [Low/置信度:高] "9 项进评审会"残留未改**
- 位置：`docs/CMAB_MDM_Portal_设计基准偏离说明_V1.2_draft.md:654 对照 :32`
- 问题：§1 Batch G3.C 已于 2026-06-05 勘误为"8 项"并说明与 13 项的关系，但 §10 处置时间表 Batch G3.C 行仍写"9 项进 V1.2 评审会"。
- 为什么是问题：同一文档内同一事实两个数字，勘误覆盖不完整。
- 建议：§10 该行同步改为 8 项（或加同款勘误括注）。

**[DOC-偏离说明修订链条-07] [Low/置信度:高] 封版声明测试数 277/278 矛盾**
- 位置：`docs/CMAB_MDM_Portal_设计基准偏离说明_V1.2_draft.md:80 对照 :88`
- 问题：§1A 末注（2026-06-05 代码修复）写"278 测试全过"，§1B 封版声明（2026-06-06）却写"测试 174 → 277"。V1.3 §4 确认 278 在 2026-06-05 已达成。
- 为什么是问题：封版声明本身含过时数字，与文档内上一行级事实冲突。
- 建议：§1B 改 278，或注明 277 为修订十二后某时点快照。

**[DOC-偏离说明修订链条-08] [Low/置信度:高] 附录D前言"3项"未随D.4更新**
- 位置：`docs/CMAB_MDM_Portal_设计基准偏离说明_V1.2_draft.md:892 对照 :1022-1029`
- 问题：附录 D 前言写"8 项 B 决议中，3 项需吸收文字（S5/S6、API4、ARCH9）"，但修订十一已增 D.4，落地表实际 4 项待吸收。
- 为什么是问题：前言计数与正文条目数不符，易漏读 D.4。
- 建议：前言改为"3 项 B 决议 + 1 项修订十一新增（D.4），共 4 项"。

**[DOC-偏离说明修订链条-09] [Low/置信度:高] R2、A1/A2 编号断裂无说明**
- 位置：`docs/CMAB_MDM_Portal_设计基准偏离说明_V1.2_draft.md:197-228 与 :325-349`
- 问题：§4 REF 复核称 8 项偏离，编号仅 R1/R3-R8（无 R2）；§6.9 ARS 称 7 项，编号 A3-A9（无 A1/A2）。全文 grep 无 R2/A1/A2 定义，亦无"已撤销项占号"说明。
- 为什么是问题：编号断裂无解释，审计追溯时无法确认是否漏登条目。
- 建议：在两节加脚注说明缺号原因（如自我撤销项占号后撤回）。

**[DOC-偏离说明修订链条-10] [Low/置信度:高] §5 errorType 说明句被替换损坏**
- 位置：`docs/CMAB_MDM_Portal_设计基准偏离说明_V1.2_draft.md:244`
- 问题：该句为同义反复："原称 \"meta.error.type\" 的内容统一解释为 meta.error.type"，应为"原称 errorType"。ARCH/UI 修订清单仍用 errorType 术语，API 清单用 meta.error.type，桥接句失效。
- 为什么是问题：疑似全局替换误伤，术语映射说明失去信息量，跨清单术语不统一。
- 建议：恢复原文"原称 errorType ...统一解释为 meta.error.type"。

**[DOC-偏离说明修订链条-11] [Low/置信度:高] V1.3 无修订历史且日期过时**
- 位置：`docs/CMAB_MDM_Portal_设计基准偏离说明_V1.3_draft.md:12 对照 :88`
- 问题：头表日期 2026-06-06，但 §3.4 含 2026-06-08 决策（docs-check 门禁暂停）、E13（06-08）引用；文档无修订历史行（V1.2 有详尽历史表）。
- 为什么是问题：合规审计配套文档缺变更留痕，无法判断各段落生效时点。
- 建议：补修订历史表（06-06 初版 / 06-08 增补），日期字段更新。

**[DOC-偏离说明修订链条-12] [Low/置信度:高] 评审完成但签字与决议人空白**
- 位置：`docs/CMAB_MDM_Portal_V1.2_评审会议材料.md:7,12,101-108`
- 问题：头表状态"✅ 评审完成（2026-05-13）"且 13 项决议全部生效落地，但 §4 评审签字表四行全空，§1 各决议无决议人/日期落款。
- 为什么是问题：决议已被 V1.2/V1.3 作为落地依据引用，决策主体不可追溯。
- 建议：按原型期姿态补注"项目负责人直接决策（日期）"替代签字，留痕。

**[DOC-偏离说明修订链条-13] [Low/置信度:高] §7.2/§7.4 推迟状态与修订八矛盾**
- 位置：`docs/CMAB_MDM_Portal_设计基准偏离说明_V1.2_draft.md:365-374,392-394 对照 :35-43`
- 问题：§7.2.2-7.2.5（Prometheus/ELK/nginx/备份）标"未实现"、§7.4 ARCH2 标 Refresh Token 未实施，但修订八（Phase 4.B）已全部落地。§7.3 的"历史快照"口径声明仅覆盖对齐率数字，未覆盖这些状态列。
- 为什么是问题：读者按章节读取状态会得出与现状相反结论，快照口径声明范围不足。
- 建议：将 §7.3 快照口径声明扩展至各章状态列，或在 §7.2/§7.4 加"已被修订八取代"括注。

**[DOC-偏离说明修订链条-14] [Low/置信度:中] 封版后仍向归档文档增补实质内容**
- 位置：`docs/CMAB_MDM_Portal_设计基准偏离说明_V1.2_draft.md:60-90`
- 问题：§1B 规定封版后仅更新 §1A 的"登记处状态"，但 2026-06-08 新增了整条勘误 E13，且 §1A 含 cap(0036) 之后事实（EQP E7-E9、RS256 E11、06-05 代码修复注）。
- 为什么是问题：违反自定义封版规则，"只读归档"声明与实际编辑行为不符。
- 建议：新勘误一律登记入 V1.3，V1.2 §1A 只保留索引指针；或修订 §1B 措辞。

**[DOC-偏离说明修订链条-15] [Low/置信度:中] 修订十二基线日期 05-13/05-14 不一致**
- 位置：`docs/CMAB_MDM_Portal_设计基准偏离说明_V1.3_draft.md:97 对照 V1.2_draft.md:12`
- 问题：V1.3 §4 测试桥写"2026-05-13（修订十二基线，commit f477d86）174"，V1.2 修订历史与 §1B 均记修订十二为 2026-05-14。commit 存在已核实，但两文档日期标注不一致。
- 为什么是问题：封版时点是链条衔接锚点，日期歧义影响时序追溯。
- 建议：统一为"代码 commit 05-13 / 文档修订十二 05-14"双时点表述。

### README+QUICKSTART+Makefile（12 条：High 1 / Medium 3 / Low 8）

> 三文件端口（15173/18000/15432/16379）与 compose 已同步，绝大多数 make target、脚本、容器名、迁移头（0044）核对一致。主要问题集中在：生产/开发流程引用了不存在的 backend/requirements.txt；gen:api 目标端口 8000 与 docker 映射 18000 不一致；本地非 Docker 开发未提示改 DATABASE_URL 主机名；Makefile .PHONY 漏列 4 个 target、help 漏 jwt-keys；README 目录结构与文档清单略有过时。均为可执行性/一致性瑕疵，无数据安全问题。

**[DOC-README+QUICK-01] [High/置信度:中] 引用不存在的 requirements.txt**
- 位置：`README.md:248,269`
- 问题：开发流程图与生产部署步骤均写 `pip install -r backend/requirements.txt`，但仓库内无该文件，依赖实为 pyproject.toml（uv/pip install -e）。
- 为什么是问题：照文档在生产服务器执行会因找不到文件而失败。
- 建议：改为 `uv pip install -e backend` 或补生成 requirements.txt 的步骤。
- 对抗复核：⏳ 复核未完成（中断），按原审查员置信度采信

**[DOC-README+QUICK-02] [Medium/置信度:中] gen:api 端口与 dev 映射不符**
- 位置：`Makefile:93-94 / frontend/package.json:13`
- 问题：make gen-types 在宿主机跑 pnpm gen:api，其 URL 写死 http://localhost:8000，而 docker dev 后端宿主端口为 18000。
- 为什么是问题：Docker 模式下 8000 无服务，生成类型会连接失败。
- 建议：把 gen:api 的地址改为 18000 或用 HOST_BACKEND_PORT 变量。

**[DOC-README+QUICK-03] [Medium/置信度:中] 本地开发未提示改 DB 主机名**
- 位置：`README.md:206-222 / QUICKSTART.md:144-152`
- 问题：.env.example 的 DATABASE_URL 主机是 docker 内部名 `postgres:5432`；本地非 Docker 跑 alembic/uvicorn 时该主机名在宿主机无法解析。
- 为什么是问题：用户照搬会连库失败，需改为 localhost:15432。
- 建议：在本地开发段补一句：DATABASE_URL 改 localhost:15432。

**[DOC-README+QUICK-04] [Medium/置信度:中] check-schema 写死 DBA 密码**
- 位置：`Makefile:123-129`
- 问题：check-schema 的 DATABASE_URL_SYNC 硬编码 __REDACTED_POSTGRES_DBA_PASSWORD__ 默认密码，未读取 .env 的 POSTGRES_DBA_PASSWORD。
- 为什么是问题：用户改了 .env 密码后该 target 连库失败。
- 建议：改为引用环境变量而非写死默认密码。

**[DOC-README+QUICK-05] [Low/置信度:高] .PHONY 漏列 4 个 target**
- 位置：`Makefile:1`
- 问题：.PHONY 未包含已定义的 seed-demo、shell-be、shell-db、jwt-keys 四个伪目标。
- 为什么是问题：若同名文件存在会导致 target 不执行。
- 建议：把这 4 个名字补进 .PHONY。

**[DOC-README+QUICK-06] [Low/置信度:高] help 漏列 jwt-keys**
- 位置：`Makefile:5-31`
- 问题：help 文本列出了 check-schema、seed-demo 等，但未列出已存在的 jwt-keys target。
- 为什么是问题：用户从 make help 看不到该命令。
- 建议：在 help 中补一行 jwt-keys 说明。

**[DOC-README+QUICK-07] [Low/置信度:高] 目录结构漏列业务域**
- 位置：`README.md:148`
- 问题：目录结构注释写 domains（srs/prs/ars/mm），但实际还含 auth、audit、eqp、ref、search 等域，尤其 eqp 设备域已是完整域。
- 为什么是问题：结构说明与实际不符，易误导。
- 建议：补充 auth/audit/eqp/ref/search 等域。

**[DOC-README+QUICK-08] [Low/置信度:中] 文档清单仅提 V1.2 偏离说明**
- 位置：`README.md:173`
- 问题：目录结构里 docs 注释只写「V1.2 偏离说明」，但当前活跃权威是 V1.3_draft（README 上文已说明）。
- 为什么是问题：注释滞后，与正文自相矛盾。
- 建议：改为 V1.3_draft 活跃 / V1.2 归档。

**[DOC-README+QUICK-09] [Low/置信度:中] 常用命令清单与 Makefile 不同步**
- 位置：`README.md:186-198`
- 问题：README 常用命令未含已存在的 seed-demo、shell-be、shell-db、backup、restore、check-schema、jwt-keys、docs-extract/check。
- 为什么是问题：用户查 README 看不到这些命令。
- 建议：补齐或注明「完整列表见 make help」。

**[DOC-README+QUICK-10] [Low/置信度:中] 顶层目录漏列 scripts 等**
- 位置：`README.md:143-179`
- 问题：顶层目录结构未列出实际存在的 scripts/（docs/csv/jwt 工具）与 QUICKSTART.md。
- 为什么是问题：结构图不完整。
- 建议：补 scripts/ 与 QUICKSTART.md。

**[DOC-README+QUICK-11] [Low/置信度:中] README 未列 Redis 宿主端口**
- 位置：`README.md:119-124`
- 问题：README 访问段列了前端/后端/库端口但未提 Redis 16379，QUICKSTART 则明确列出，两文档详略不一致。
- 为什么是问题：轻微不一致，无功能影响。
- 建议：README 访问段补 Redis 16379 或说明无需直连。

**[DOC-README+QUICK-12] [Low/置信度:低] 示例数据与真实 demo 集不一致**
- 位置：`QUICKSTART.md:74-89 / backend/app/scripts/seed_data.py:131-187`
- 问题：QUICKSTART 描述 seed 后看到 CMAB-101/203/301/401，与 seed_data.py 一致；但与已落地的真实 demo 集（CMAB-101/205/016 denosumab 等）不同源，易混淆。
- 为什么是问题：若改用 seed_real_demo 数据，QUICKSTART 预期截图描述会对不上。
- 建议：注明 make seed 用的是基线示例集，真实 demo 另由 seed_real_demo 装载。

### RUNBOOK+OQ追溯（21 条：High 2 / Medium 6 / Low 13）

> 4 份文档整体质量较高：脚本/Makefile 目标/compose/迁移 head 等关键引用基本属实（44 个 migration、head 0044、jwt_keys fail-fast/kid 与实现一致、test_jwt_rs256 确为 7 例）。主要问题集中在：备份恢复 SOP 的恢复校验命令在生产不可执行（alembic 跑错容器、生产镜像无 pytest 且 backend 已停）；OQ 追溯矩阵 SRS/PRS 两处风险分布与逐条表不符，导致 Critical 101/Major 68 门槛数与明细加总（99/70）矛盾；以及多处跨文档数字/名称陈旧（277 vs 278、0011 迁移名、IQ"5 项"实为 1 项）。

**[DOC-RUNBOOK+OQ追溯-01] [High/置信度:高] alembic 校验跑错容器**
- 位置：`docs/RUNBOOK_BACKUP_RESTORE.md:101 与 scripts/restore_db.sh:75`
- 问题：恢复校验命令为 `docker exec cmab-mdm-postgres alembic current`，但 postgres:16-alpine 容器内没有 alembic；restore_db.sh 完成提示同样写错容器。
- 为什么是问题：灾难恢复演练时该校验步骤必然失败，SOP 不可执行。
- 建议：改为在 backend 容器或一次性 docker run（backend 镜像）中执行 alembic current。
- 对抗复核：⏳ 复核未完成（中断），按原审查员置信度采信

**[DOC-RUNBOOK+OQ追溯-02] [High/置信度:高] 生产恢复 pytest 校验不可行**
- 位置：`docs/RUNBOOK_BACKUP_RESTORE.md:94,102`
- 问题：step 1 已 stop backend，step 3 却 `docker exec cmab-mdm-backend pytest tests/ -q`；且生产镜像（Dockerfile production stage）只 COPY app/alembic，无 tests/，pytest 属 dev optional-dependencies 未安装。
- 为什么是问题：命令必失败；即便可跑，pytest 会向恢复后的生产库写入大量测试数据造成污染。
- 建议：删除生产环境 pytest 步骤，改为只读 SQL 抽检；回归测试仅在 UAT 用 make test-be（隔离 test DB）。
- 对抗复核：⏳ 复核未完成（中断），按原审查员置信度采信

**[DOC-RUNBOOK+OQ追溯-03] [Medium/置信度:高] SRS crud 风险分布不符**
- 位置：`docs/csv_oq_traceability.md:112-130`
- 问题：§3.1 标题与总览行均称 13 用例 = 8 Critical + 5 Major，但逐条表实际为 7 Critical（5 条 C 标注 + put_protein/put_adc）+ 6 Major（get/soft_delete/extended/xref/lookups/system_info）。
- 为什么是问题：风险定级直接决定 OQ 100% 通过门槛范围，明细与汇总矛盾使证据链失效。
- 建议：逐条复核定级，统一标题/总览/逐条表三处数字。

**[DOC-RUNBOOK+OQ追溯-04] [Medium/置信度:高] PRS 风险分布不符**
- 位置：`docs/csv_oq_traceability.md:174-221`
- 问题：§4 标题称 25 用例 = 14 Critical + 11 Major，但逐条表加总为 13 Critical + 12 Major（§4.1 6C+5M、§4.2 6C、§4.3 1C+7M）。
- 为什么是问题：同上，OQ 判定基数错误。
- 建议：复核 §4 各用例定级后修正标题与总览行。

**[DOC-RUNBOOK+OQ追溯-05] [Medium/置信度:高] Critical 101 与明细加总矛盾**
- 位置：`docs/csv_oq_traceability.md:40,42,353-355`
- 问题：总计行与 §9.2 门槛取 101 Critical / 68 Major，但按 §1-§8 逐条表加总为 99 Critical / 70 Major（差额即 SRS/PRS 两处）。而 06-05 勘误声明'风险分布按逐条表重新加总'，与现状自相矛盾。
- 为什么是问题：§9.2 通过判定（Critical 100% 范围）基数不可信。
- 建议：修正两处明细或总览后，同步更新 §9.2 的 101/68/5 三个门槛数。

**[DOC-RUNBOOK+OQ追溯-06] [Medium/置信度:高] OQ 命令与测试隔离架构矛盾**
- 位置：`docs/csv_oq_traceability.md:343 与 docs/RUNBOOK_BACKUP_RESTORE.md:102`
- 问题：OQ 执行命令为 `docker exec cmab-mdm-backend pytest tests/`，即 Makefile 中已标注'仅快速本地调试用'的旧路径（直打 dev 服务/dev DB，受数据漂移影响），与 make test-be → run_tests.sh 隔离 cmab_test 架构不一致。
- 为什么是问题：OQ 正式跑会污染/依赖 dev 数据，flaky 根因（§9.4）正源于此。
- 建议：OQ 执行命令改为 `make test-be`（隔离 test DB），并更新 §9.4 flaky 说明。

**[DOC-RUNBOOK+OQ追溯-07] [Medium/置信度:中] 抽检 SQL 保留字未加引号**
- 位置：`docs/RUNBOOK_DATA_MIGRATION.md:219-251`
- 问题：§5.1 计数模板首行 `FROM auth.user`：user 是 PostgreSQL 保留字，未写成 auth."user"，整段 SQL 直接执行会语法报错。
- 为什么是问题：迁移前后对比是合规判定步骤，模板不可直接执行。
- 建议：改为 `FROM auth."user"`，并实际跑通一次模板。

**[DOC-RUNBOOK+OQ追溯-08] [Medium/置信度:中] --env 变量展开依赖未说明**
- 位置：`docs/RUNBOOK_DATA_MIGRATION.md:89-94,151-156`
- 问题：`docker run --env-file ... --env DATABASE_URL_SYNC=postgresql://${POSTGRES_USER}:${POSTGRES_PASSWORD}@...` 中 ${VAR} 由宿主 shell 展开，--env-file 不会注入命令行；未提示先 source /etc/cmab-mdm/.env.prod。
- 为什么是问题：照抄执行会得到空用户名/密码的损坏 URL，迁移失败。
- 建议：步骤前加 `set -a; source /etc/cmab-mdm/.env.prod; set +a` 或改用容器内已有 env。

**[DOC-RUNBOOK+OQ追溯-09] [Low/置信度:高] 迁移 0011 名称写错**
- 位置：`docs/RUNBOOK_DATA_MIGRATION.md:39`
- 问题：全景表第 11 行写 `0011_signature_pivot（e_signature 改 service 后置 UPDATE）`，实际文件为 2026_05_11_2100_0011_auth_locked_at.py。
- 为什么是问题：追溯表与 alembic history 对不上，影响 IQ 核对。
- 建议：按实际 revision 名与内容修正该行。

**[DOC-RUNBOOK+OQ追溯-10] [Low/置信度:高] 0014-0021 日期标注不准**
- 位置：`docs/RUNBOOK_DATA_MIGRATION.md:42`
- 问题：row 14 标注文件日期 `2026_05_12_*`，实际 0014-0018 为 2026_05_11_23xx，仅 0019-0021 为 05_12。
- 为什么是问题：小误差，但追溯表声称与文件一一对应。
- 建议：改为 2026_05_11~05_12。

**[DOC-RUNBOOK+OQ追溯-11] [Low/置信度:高] 测试基线 277 已过期**
- 位置：`docs/RUNBOOK_DATA_MIGRATION.md:127`
- 问题：§2.3 写 'make test-be 277 passed（2026-06-05 基线）'，而 csv_oq_traceability.md 与 V1.3_draft §4 均为 278（2026-06-06，含 STEWARD 断言）。
- 为什么是问题：两份运维文档基线数互相矛盾，OQ 期望值取错。
- 建议：统一为 278 并注明随矩阵扩展同步更新。

**[DOC-RUNBOOK+OQ追溯-12] [Low/置信度:高] 前置条件 schema 数写错**
- 位置：`docs/RUNBOOK_DATA_MIGRATION.md:76`
- 问题：§2.1 写 'cmab_mdm 数据库 + cmab_app 账号 + 4 个 schema'，deploy/postgres/init/01-init.sql 实际创建 8 个 schema（auth/meta/audit/srs/prs/ars/mm/ref，eqp 由 0040 创建）。
- 为什么是问题：IQ 核对人按 4 个 schema 检查会误判。
- 建议：改为 8 个 schema（列名单），并注明 eqp 由 migration 0040 创建。

**[DOC-RUNBOOK+OQ追溯-13] [Low/置信度:高] PG 文档链接不存在**
- 位置：`docs/RUNBOOK_DATA_MIGRATION.md:332`
- 问题：参考链接 postgresql.org/docs/16/migrations.html 在 PostgreSQL 官方文档中不存在（无该页面）。
- 为什么是问题：参考文献失效，影响文档可信度。
- 建议：删除或改为 backup.html / Alembic 官方文档。

**[DOC-RUNBOOK+OQ追溯-14] [Low/置信度:高] IQ 追加 5 项实为 1 项**
- 位置：`docs/RUNBOOK_JWT_RS256.md:127 与 deploy/checklist_iq.md:78`
- 问题：RUNBOOK 称 checklist_iq.md '追加 RS256 检查 5 项'，实际清单中仅 4.5 一行涉及 RS256/JWT 密钥。
- 为什么是问题：IQ 证据数量声明与实际不符。
- 建议：补齐 5 项（算法/路径/权限600/kid/挂载只读）或改口径为 1 项。

**[DOC-RUNBOOK+OQ追溯-15] [Low/置信度:高] compose 挂载指引已过时**
- 位置：`docs/RUNBOOK_JWT_RS256.md:43-50`
- 问题：步骤 2 指导在 docker-compose.prod.yml backend 下'加' ./jwt:/app/secrets:ro，但 deploy/docker-compose.prod.yml:96 已包含该挂载。
- 为什么是问题：执行人会重复添加或困惑；文档与现状脱节。
- 建议：改为'确认已存在该挂载'。

**[DOC-RUNBOOK+OQ追溯-16] [Low/置信度:中] cmab_app 查 alembic_version 或无权限**
- 位置：`docs/RUNBOOK_DATA_MIGRATION.md:97-99,121`
- 问题：迁移以 POSTGRES_USER（postgres）执行，alembic_version 表 owner 为 postgres 且无显式 GRANT；用 `psql -U cmab_app` 查询可能 permission denied。
- 为什么是问题：验证步骤可能误报失败。
- 建议：改用 -U postgres 查询，或在 init 中授予 cmab_app 读权限。

**[DOC-RUNBOOK+OQ追溯-17] [Low/置信度:中] base64 -d 解码 JWT 会报错**
- 位置：`docs/RUNBOOK_JWT_RS256.md:80-85`
- 问题：验证命令 `cut -d. -f1 | base64 -d`：JWT header 为无 padding 的 base64url，长度非 4 倍数时 GNU/BSD base64 -d 通常报 invalid input。
- 为什么是问题：验证步骤照抄可能失败，误判切换未生效。
- 建议：补 padding（awk 补 = 号）或建议用 jwt-cli / python 解码。

**[DOC-RUNBOOK+OQ追溯-18] [Low/置信度:中] 22 CFR 笔误**
- 位置：`docs/csv_oq_traceability.md:54`
- 问题：§1.1 test_lockout 行写 '22 CFR Part 11 §11.300'，应为 21 CFR Part 11。
- 为什么是问题：合规文档引用法规编号错误，审计观感差。
- 建议：改为 21 CFR Part 11。

**[DOC-RUNBOOK+OQ追溯-19] [Low/置信度:中] smoke 2 用例无明细节**
- 位置：`docs/csv_oq_traceability.md:31`
- 问题：总览表含 smoke 2 用例（Minor），但 §1-§8 无对应明细小节（test_smoke.py 2 例确实存在），是 174 基线中唯一无逐条映射的模块。
- 为什么是问题：矩阵自称'逐条映射'，存在覆盖缺口。
- 建议：补 smoke 小节（2 条 Minor 映射 ARCH §7.2.1 / API §1.4）。

**[DOC-RUNBOOK+OQ追溯-20] [Low/置信度:低] Phase 5 回滚 UI 引用过期**
- 位置：`docs/RUNBOOK_BACKUP_RESTORE.md:124`
- 问题：§4.2 称单点事故走 'audit.change_history 反向重建（Phase 5 自助回滚 UI）'，但 Phase 5 已完结且未交付该功能。
- 为什么是问题：事故处置指引指向不存在的功能。
- 建议：改为 Phase 6 计划或注明当前仅可手工单表 pg_restore。

**[DOC-RUNBOOK+OQ追溯-21] [Low/置信度:低] 健康检查路径口径不一**
- 位置：`docs/RUNBOOK_BACKUP_RESTORE.md:94 与 docs/RUNBOOK_JWT_RS256.md:77`
- 问题：备份/迁移 RUNBOOK 用 /health，JWT RUNBOOK 用 /api/v1/health；两端点都存在（main.py:193/200），但跨文档口径不统一。
- 为什么是问题：非错误，但 SOP 间不一致易让执行人困惑。
- 建议：统一为 /api/v1/health（网关只代理 /api 时更稳）。

---

## 2. 后端代码审查发现（按域）

### be-auth（22 条：High 3 / Medium 8 / Low 11）

> auth 域整体结构清晰（RS256 密钥管理、refresh 旋转、旁路 session 失败计数均有设计），但存在一个高危逻辑洞：锁定窗口过期后的自动解锁只改内存、失败路径回滚丢失，且旁路 session 按 DB 中仍为 locked 的状态跳过计数，导致锁定期满后可无限暴力破解。其次 auth 全部表无审计 trigger、管理员操作不落审计；角色软删后重建撞 DB 唯一约束 500；force_password_change/密码过期/角色到期均未服务端强制；限流按用户分桶实际失效。共 22 项发现。

**[BE-be-auth-01] [High/置信度:高] 锁定期满后可无限暴力破解**
- 位置：`backend/app/domains/auth/services.py:180-186,122`
- 问题：自动解锁只在主 session 内存中改 status/locked_at，密码错时主事务 rollback 丢失；旁路 session 重读 DB 仍是 locked，因 `u.status=='active'` 条件跳过计数与再锁定。用户永远停在 locked+窗口已过状态，每次都走完整密码校验。
- 为什么是问题：账户被锁一次后，30 分钟窗口过后攻击者可无限次猜密码，暴力破解防护完全失效。
- 建议：自动解锁用旁路 session 立即持久化；或旁路计数时对 locked+窗口已过状态也累加并重置 locked_at。
- 对抗复核：⏳ 复核未完成（中断），按原审查员置信度采信

**[BE-be-auth-02] [High/置信度:高] auth 域全部表无审计追踪**
- 位置：`backend/alembic/versions/2026_05_11_1200_0001_init_schemas.py:76-165；backend/app/domains/auth/admin_service.py:201-375`
- 问题：auth.user/user_role/role/role_permission/refresh_token 均未挂 audit.fn_audit_trigger，管理员建用户、改角色、锁定、重置密码等安全敏感写操作仅 loguru 日志，不落 audit_log。
- 为什么是问题：账户与权限变更是 Part 11 审计追踪核心对象，当前可被日志轮转抹除且不可查询。
- 建议：为 auth 业务表挂 audit trigger 或在 admin service 写应用层审计记录。
- 对抗复核：⏳ 复核未完成（中断），按原审查员置信度采信

**[BE-be-auth-03] [High/置信度:高] 软删角色重建触发 500**
- 位置：`backend/app/domains/auth/admin_role_service.py:151-156,234`
- 问题：delete_role 是软删（deleted_at），但 uq_role_role_code 是全表唯一；create_role 预检排除了软删行，重建同名 role_code 时预检通过、INSERT 撞唯一约束抛 IntegrityError 500。
- 为什么是问题：删除→重建同名角色是常见操作路径，且项目约定禁止 try/except IntegrityError，必然裸 500。
- 建议：唯一约束改 partial（WHERE deleted_at IS NULL），或预检不排除软删行。
- 对抗复核：⏳ 复核未完成（中断），按原审查员置信度采信

**[BE-be-auth-04] [Medium/置信度:高] 强制改密无服务端拦截**
- 位置：`backend/app/domains/auth/services.py:249；backend/app/shared/permissions.py:25-86`
- 问题：force_password_change 仅作为 must_change_password 标志返回前端，登录仍签发全功能 token；get_current_user 不检查该标志，持临时密码用户可直接调用全部业务 API。
- 为什么是问题：绕过前端即可不改密长期使用管理员知晓的临时密码，违背重置密码设计意图。
- 建议：get_current_user 中 force_password_change=True 时仅放行 change-password/me/logout。

**[BE-be-auth-05] [Medium/置信度:高] 密码 90 天过期未强制**
- 位置：`backend/app/domains/auth/services.py:285；backend/app/shared/permissions.py:53-75`
- 问题：password_expires_at 在改密/建用户时写入，但 login 与 get_current_user 均不校验，过期密码可继续登录使用。PASSWORD_TEMP_DAYS 同样无效。
- 为什么是问题：密码生命周期策略只写不读，形同虚设，与 Part 11 §11.300(b) 定期检查要求不符。
- 建议：login 时校验 password_expires_at，过期则强制走改密流程。

**[BE-be-auth-06] [Medium/置信度:高] 角色授权 expires_at 永不生效**
- 位置：`backend/app/domains/auth/models.py:67-74,136；backend/app/shared/permissions.py:89-102`
- 问题：user_role.expires_at 字段存在，但 User.roles 关系与所有权限聚合查询均不过滤过期行，限期授权实际永久有效。
- 为什么是问题：临时授权到期不回收是纵向越权隐患，且字段存在会让管理员误以为已生效。
- 建议：roles 关系与权限查询加 expires_at IS NULL OR > now() 过滤，或移除字段。

**[BE-be-auth-07] [Medium/置信度:高] 密码复杂度与历史校验缺失**
- 位置：`backend/app/domains/auth/services.py:280-300；backend/app/domains/auth/schemas.py:68-70`
- 问题：change-password 仅 Pydantic min_length=12，无大小写/数字/符号复杂度、无新旧密码相同检查、无密码历史；WeakPasswordError/PasswordInHistoryError 定义后从未使用。
- 为什么是问题：临时密码生成器保证复杂度但用户自选密码不校验，策略不对称；错误码体系已预留说明是遗漏。
- 建议：change_password 内加复杂度校验与 new!=old 检查，按需补密码历史表。

**[BE-be-auth-08] [Medium/置信度:高] refresh 重放仅记日志不撤销链**
- 位置：`backend/app/domains/auth/services.py:357-383`
- 问题：已撤销 jti 被重用时只 logger.warning + 401，不撤销该用户其余活跃 token（token family）；docstring 声称"写审计"但无任何 DB 记录。且查询无 FOR UPDATE，并发 refresh 同一 token 会同时通过检查、双发新 token。
- 为什么是问题：refresh token 被盗后重放检测形同虚设，攻击者与受害者会话可长期并存。
- 建议：重放时撤销该用户全部活跃 refresh token 并落审计；旋转查询加 with_for_update。

**[BE-be-auth-09] [Medium/置信度:高] login/改密未显式 commit**
- 位置：`backend/app/domains/auth/services.py:226-255,300`
- 问题：refresh()/logout() 已按项目约定在 service 内显式 commit，但 login()（写 login_history、refresh_token jti、解锁状态）和 change_password()（改 hash+撤销全部 refresh）仍依赖 get_db 在 response 之后 commit。
- 为什么是问题：响应已含 refresh cookie/成功消息而事务未提交：commit 失败则 cookie 中 jti 不存在、或用户被告知改密成功实际未改。
- 建议：login 与 change_password 在返回前显式 commit，对齐 refresh/logout。

**[BE-be-auth-10] [Medium/置信度:高] 最后 SYS_ADMIN 防护可被旁路**
- 位置：`backend/app/domains/auth/admin_service.py:276-294`
- 问题：assign_roles 仅当操作对象是自己时才检查最后一个 SYS_ADMIN；持 user:manage 的非 SYS_ADMIN 账号可移除他人（系统中最后一个）SYS_ADMIN 角色。lock_user 也无此检查。
- 为什么是问题：系统可能被操作成无任何活跃 SYS_ADMIN，管理功能锁死。
- 建议：最后 SYS_ADMIN 检查改为针对目标用户而非仅自身，lock_user 同样校验。

**[BE-be-auth-11] [Medium/置信度:中] 按用户限流实际失效+代理后共桶**
- 位置：`backend/app/shared/rate_limit.py:25-44；backend/app/shared/middleware/audit_context.py:16`
- 问题：rate_limit_user_id 在 get_current_user（路由依赖阶段）才写入，而 SlowAPIMiddleware 在中间件阶段就用 key_func 检查 default_limits，此时取不到 user_id 全部退化为 IP 桶；且 IP 取 request.client.host，不读 X-Forwarded-For，nginx 后全员同一 IP。
- 为什么是问题：生产 300/min/user 实为 300/min/全公司；登录档 10/min/IP 可被单攻击者耗尽造成全员无法登录。
- 建议：IP 提取支持可信代理的 XFF；确认 slowapi 中间件与 state 写入时序，必要时改装饰器限流。

**[BE-be-auth-12] [Low/置信度:高] 失败计数读改写有竞态**
- 位置：`backend/app/domains/auth/services.py:116-127`
- 问题：_persist_login_failure 旁路 session 中 failed_login_count 读取-加一-写回，无 SELECT FOR UPDATE 或原子 UPDATE ... SET count=count+1，并发错误登录会丢计数。
- 为什么是问题：并行暴力尝试可使实际失败次数超过 LOGIN_MAX_FAILED_ATTEMPTS 才锁定。
- 建议：改为 update().values(failed_login_count=User.failed_login_count+1) 原子自增，再回读判锁。

**[BE-be-auth-13] [Low/置信度:高] 登录前泄露账户状态可枚举用户名**
- 位置：`backend/app/domains/auth/services.py:175-207`
- 问题：密码校验之前即按账户状态返回可区分错误：不存在=40101、锁定=42301(423)、禁用=40302(403)，未提供密码也能探测账户存在与状态。
- 为什么是问题：攻击者可枚举有效用户名并识别锁定/禁用账户，缩小爆破目标。
- 建议：locked/disabled 判定移到密码校验通过之后，校验失败统一返回 40101。

**[BE-be-auth-14] [Low/置信度:高] 模型与库内约束名不一致**
- 位置：`backend/app/domains/auth/models.py:80,105`
- 问题：模型声明 uq_role_code/uq_permission_code，migration 实建 uq_role_role_code/uq_permission_permission_code；User.user_id 模型为 autoincrement 而库内为 Identity(always)。
- 为什么是问题：alembic autogenerate 会产生虚假 drop/create 约束差异，存在误执行风险。
- 建议：统一模型 UniqueConstraint 名与 migration 实际名。

**[BE-be-auth-15] [Low/置信度:高] login_history 缺 user_id 索引**
- 位置：`backend/alembic/versions/2026_05_11_1200_0001_init_schemas.py:181-184；backend/app/domains/auth/services.py:434-446`
- 问题：get_my_login_history 按 user_id 过滤分页，但表只有 login_at DESC 索引，查询走全表扫描。
- 为什么是问题：登录历史只增不删，随时间增长个人中心查询线性变慢。
- 建议：加 (user_id, login_at DESC) 复合索引。

**[BE-be-auth-16] [Low/置信度:中] 用户名/邮箱大小写敏感唯一**
- 位置：`backend/app/domains/auth/admin_service.py:203-213`
- 问题：username/email 唯一性比较与 DB 约束均区分大小写，可同时存在 Admin/admin、A@x.com/a@x.com 两个账号。
- 为什么是问题：近似账号会污染审计追踪可读性，且邮箱大小写在投递语义上等价，易被冒名。
- 建议：建 lower(username)/lower(email) 函数唯一索引，预检用 ilike/func.lower。

**[BE-be-auth-17] [Low/置信度:中] refresh 无限滑动续期**
- 位置：`backend/app/domains/auth/services.py:364-372`
- 问题：每次旋转都从 now 起算 7 天新有效期，无绝对会话寿命上限，只要每 7 天活跃一次会话可永久续期。
- 为什么是问题：被盗 refresh token 若持续使用可无限存活，缺少强制再认证节点。
- 建议：在 token 链上携带首次签发时间，超过绝对上限（如 30 天）强制重新登录。

**[BE-be-auth-18] [Low/置信度:中] bcrypt 72 字节静默截断**
- 位置：`backend/app/core/security.py:15-25；backend/app/domains/auth/schemas.py:11,70,83`
- 问题：密码允许至 128 字符，但 bcrypt 仅取前 72 字节，超长部分静默忽略；passlib 新版对 bcrypt>=4 还有兼容告警。
- 为什么是问题：用户以为 100 位密码全部生效，实际前 72 字节相同即可登录。
- 建议：限制密码 ≤72 字节或预先 SHA-256 摘要后再 bcrypt。

**[BE-be-auth-19] [Low/置信度:中] 锁定用户报 account_disabled**
- 位置：`backend/app/shared/permissions.py:63-64`
- 问题：get_current_user 对 status=locked 的用户也抛 AccountDisabledError（error_type=account_disabled, 403），与登录时的 account_locked(423) 语义不一致。
- 为什么是问题：前端按 errorType 分流提示，被锁用户会看到"账户已禁用"误导信息。
- 建议：按 status 分别抛 AccountLockedError/AccountDisabledError。

**[BE-be-auth-20] [Low/置信度:中] logout 无专档限流与审计**
- 位置：`backend/app/api/v1/auth.py:96-108；backend/app/domains/auth/services.py:393-418`
- 问题：logout 端点未加 login/public 限流装饰器（仅默认档），且登出动作不写 login_history/审计，仅静默撤销。
- 为什么是问题：会话终止事件缺失会使登录历史无法还原完整会话生命周期。
- 建议：logout 写一条登出记录并复用 public_rate_limit。

**[BE-be-auth-21] [Low/置信度:中] 管理员建用户不强制改密**
- 位置：`backend/app/domains/auth/admin_service.py:217-232`
- 问题：create_user 由管理员设置初始密码且 force_password_change=False，管理员长期知晓该用户密码；与 reset_password 的强制改密策略不一致。
- 为什么是问题：共享知晓的凭据破坏电子签名个人唯一性前提（Part 11 §11.100/§11.300）。
- 建议：建用户后 force_password_change 置 True，首登强制改密。

**[BE-be-auth-22] [Low/置信度:低] get_me 返回裸 dict 绕过 schema**
- 位置：`backend/app/domains/auth/services.py:257-278；backend/app/domains/auth/schemas.py:22-41`
- 问题：UserMe schema 已定义但 get_me 手工拼 dict 直接返回，未经 Pydantic 校验/序列化，字段增删时 schema 与实际响应会静默漂移。
- 为什么是问题：OpenAPI 文档与实际响应不一致，前端契约失去保障。
- 建议：get_me 返回 UserMe.model_validate 结果并复用 schema。

### be-audit

（审查任务尚未完成，待补跑）

### be-ref（12 条：High 1 / Medium 4 / Low 7）

> ref 域为三张跨域关联表（project_substance/asset_substance/project_asset），唯一性由复合 PK 在 DB 层强制、审计走 DB trigger，整体结构良好。主要问题：主数据软删后关联变成不可解除的幽灵引用；双向列表对侧 deleted_at 过滤不对称；ref 三表 updated_at 无 touch trigger 永不刷新；并发 link 竞态未兜 IntegrityError 会 500；资产侧端点仅凭 asset:update 即可改项目关联，存在横向权限不对称。

**[BE-be-ref-01] [High/置信度:高] 主数据软删后引用无法解除**
- 位置：`backend/app/domains/ref/services.py:64-73,136-169（三个 service 的 _get_* 与 unlink 同模式）`
- 问题：srs/prs/ars 的 soft_delete 不预检 ref 活动链接；物质/项目/资产软删后链接仍 deleted_at IS NULL。而 unlink 内 _get_substance/_get_project/_get_asset 均过滤 deleted_at，对已删实体直接 404，链接永远无法通过 API 取消。
- 为什么是问题：形成不可清理的孤儿活动引用，破坏跨域引用一致性
- 建议：主实体软删前预检活动链接并阻止或级联软删；或 unlink 的 _get_* 放宽 deleted_at 过滤
- 对抗复核：⏳ 复核未完成（中断），按原审查员置信度采信

**[BE-be-ref-02] [Medium/置信度:高] 双向列表过滤不对称**
- 位置：`backend/app/domains/ref/services.py:175-181 vs 194-204（354-371/537-552 同）`
- 问题：list_for_substance/list_for_asset 过滤对侧 Project.deleted_at/Asset.deleted_at，但 list_for_project/list_for_asset 不过滤 Substance/Asset 的 deleted_at。同一链接从 A 侧可见、从 B 侧不可见，且项目侧会把已删物质显示为活动关联。
- 为什么是问题：同一数据两侧查询结果矛盾，误导用户
- 建议：三个 service 统一对侧实体 deleted_at 过滤策略，或在 item 中返回对侧 deleted 标记

**[BE-be-ref-03] [Medium/置信度:高] ref 三表 updated_at 永不刷新**
- 位置：`backend/app/domains/ref/models.py:48-50,89-92,122-125；migrations 0012/0025/0026`
- 问题：srs/prs/ars 各表有 fn_touch_updated_at BEFORE UPDATE 触发器，但 ref 三表既无触发器也无 ORM onupdate=func.now()。unlink/复活/改 notes 后 updated_at 仍是创建时间，而 updated_by 已变。
- 为什么是问题：updated_at 与 updated_by 自相矛盾，影响审计展示与排序
- 建议：新增 migration 给 ref 三表挂 touch trigger，或模型加 onupdate=func.now()

**[BE-be-ref-04] [Medium/置信度:高] 资产侧改项目关联权限不对称**
- 位置：`backend/app/api/v1/assets.py:396-433`
- 问题：POST/DELETE /assets/{code}/projects 仅要求 asset:update，即可对任意 project 建立/解除资产关联；同一操作在项目侧（/projects/{code}/assets）要求 project:update。
- 为什么是问题：仅有 asset:update 的角色可绕过项目域写权限，横向越权
- 建议：资产侧端点同时校验 project:update，或统一两侧权限要求

**[BE-be-ref-05] [Medium/置信度:中] 并发 link 竞态返回 500**
- 位置：`backend/app/domains/ref/services.py:90-133,273-317,463-503`
- 问题：唯一性由复合 PK 在 DB 层强制（好），但 service 仅做 pre-check；两请求并发绑定同一三元组时，第二个事务在 flush/commit 处抛 IntegrityError，且无全局 IntegrityError handler，返回 500 而非 409。
- 为什么是问题：竞态下用户收到 500，错误语义丢失
- 建议：按项目约定保持 pre-check，但在全局异常 handler 把唯一约束冲突映射为 409

**[BE-be-ref-06] [Low/置信度:高] 复活链接保留原创建信息**
- 位置：`backend/app/domains/ref/services.py:112-119,296-302,482-489`
- 问题：link() 复活软删行时仅清 deleted_at/by 并改 updated_by，created_at/created_by 仍是首次绑定的值，且复活路径不支持 change_reason；列表按 created_at 排序、前端展示"绑定时间"为旧时间。
- 为什么是问题：重新绑定的时间与操作人展示失真
- 建议：复活时考虑重置 created_at/created_by，或 Create schema 增加 change_reason 注入审计

**[BE-be-ref-07] [Low/置信度:中] 审计 entity_id 粒度不足**
- 位置：`backend/alembic/versions/0012/0025/0026 中 fn_audit_trigger 第一参数`
- 问题：三表复合 PK，但 audit trigger 第一参数只取 project_id/asset_id 作为 entity_id；同一 project 下多条链接（不同 substance/relation_type）的审计行 entity_id 相同，无法单凭 entity_id 定位具体链接。
- 为什么是问题：按行追溯审计需解析快照字段，检索粒度变粗
- 建议：评估 trigger 支持复合键拼接，或接受现状并在文档注明检索方式

**[BE-be-ref-08] [Low/置信度:中] unlink 原因字段可选**
- 位置：`backend/app/domains/ref/schemas.py:34-38,76-77,128-129`
- 问题：三类 unlink 的 change_reason 均为 Optional，而主实体软删（project/asset soft_delete）reason 必填。取消引用同为软删操作，但允许无理由执行。
- 为什么是问题：审计追踪完整性不一致，GMP 阶段会成缺口
- 建议：统一策略：unlink 的 change_reason 改必填，或登记为已知豁免

**[BE-be-ref-09] [Low/置信度:中] is_primary 无单主约束**
- 位置：`backend/app/domains/ref/models.py:41；services.py:75-134`
- 问题：project_substance.is_primary 在 DB 与 service 层均无"每项目至多一行 true"约束，可同时存在多条 is_primary=true，也可与 relation_type='primary' 互相矛盾（如 relation_type='reference' 且 is_primary=true）。
- 为什么是问题：主物质标记可出现多义，下游展示/统计取数不确定
- 建议：加 partial unique index (project_id) WHERE is_primary AND deleted_at IS NULL，或 service 内联动清旧主

**[BE-be-ref-10] [Low/置信度:中] DELETE 端点请求体必填**
- 位置：`backend/app/api/v1/projects.py:436-453；assets.py:359-376,419-433`
- 问题：unlink 系列 DELETE 端点的 payload 参数无默认值，FastAPI 视为必填 body；不带 body 的标准 DELETE 请求会 422，change_reason 实际可选却必须传 {}。
- 为什么是问题：对部分客户端/代理不友好，已在项目 memory 记为坑
- 建议：payload 加 Body(default=...) 允许空体，或 change_reason 改 query 参数

**[BE-be-ref-11] [Low/置信度:低] 反向查询跨域读权限放宽**
- 位置：`backend/app/api/v1/substances.py:358-389`
- 问题：GET /substances/{code}/projects 与 /assets 仅要求 substance:read，但响应携带 project_name/status、asset_internal_name/phase 等对侧域投影字段，未校验 project:read/asset:read。
- 为什么是问题：无项目/资产读权限的用户可经物质侧获取对侧信息
- 建议：确认是否设计放行；否则反向端点叠加对侧 read 权限

**[BE-be-ref-12] [Low/置信度:低] unlink 路径枚举参数未校验**
- 位置：`backend/app/api/v1/projects.py:441-453；assets.py:364-376`
- 问题：DELETE 路径中的 relation_type/component_role 为裸 str，未用 Literal/Enum 校验；非法值落到查询返回 404 而非 422。
- 为什么是问题：错误语义不精确，排错时易误判为数据不存在
- 建议：路径参数改用 Literal 类型让 FastAPI 自动校验

### be-srs（11 条：High 1 / Medium 4 / Low 6）

> SRS 域整体结构清晰、唯一性约束多在 DB 层（substance_code/external_uuid 唯一、xref(type,value) 与 internal_code 唯一），datetime 全程 aware，审计走 GUC+触发器+service 回填。但存在若干隐藏细节 bug：internal_code 软删后无法复用且会 500（设计意图与 DB 实现不符）；xref 重复未 pre-check 导致 IntegrityError 直接 500；乐观锁非原子存在丢失更新竞态；状态机 restrict 声称可逆却无反向迁移；软删除缺引用与状态守卫。多为功能/边界级问题，无明显数据损坏或越权。

**[BE-be-srs-01] [High/置信度:高] internal_code 软删后无法复用且 500**
- 位置：`backend/app/domains/srs/services.py:329-339 + alembic/versions/2026_05_12_1000_0028_srs_baseline_align.py:94-99`
- 问题：0028 想用 partial 索引让 internal_code 仅在未删行唯一，但新建索引未加 unique=True（仅普通索引），且 0001 的全量 UniqueConstraint uq_substance_internal_code 从未 drop。create/update 的 pre-check 只查 deleted_at IS NULL 会放行，DB 全量唯一约束却拒绝，复用已软删 internal_code 直接 IntegrityError 500。
- 为什么是问题：设计意图(软删后可复用编码)与 DB 实际约束不一致，阻断合法操作并暴露 500。
- 建议：0028 索引补 unique=True 并 drop 全量 uq_substance_internal_code。
- 对抗复核：⏳ 复核未完成（中断），按原审查员置信度采信

**[BE-be-srs-02] [Medium/置信度:高] xref 重复未 pre-check 致 500**
- 位置：`backend/app/domains/srs/services.py:393-408,787-806`
- 问题：substance_xref 有 partial 唯一索引 uq_substance_xref_type_value(xref_type,xref_value)，但 create() 的 xref 循环与 add_xref/update_xref 均无重复 pre-check。注册重复 INN/CAS/UNII 时抛 IntegrityError，main.py 无 IntegrityError handler，落到通用兜底返回 500 而非 409。违背项目'用 pre-check 替代 IntegrityError'约定。
- 为什么是问题：重复主标识符应给清晰冲突错误，现为 500 且事务被污染。
- 建议：add_xref/create/update_xref 增加 (type,value) 未删重复 pre-check 抛 DuplicateCodeError。

**[BE-be-srs-03] [Medium/置信度:中] 乐观锁非原子存在丢失更新**
- 位置：`backend/app/domains/srs/services.py:423-467`
- 问题：update() 以 select 读取 sub.version 后用 Python 比较 payload.version，UPDATE 不带 WHERE version=:expected，也无 SELECT FOR UPDATE。两个并发 PUT 都读 version=1、都通过校验、都 flush，触发器各自自增 version，后写覆盖先写，造成丢失更新。
- 为什么是问题：GxP 主数据并发修改下乐观锁失效，数据被静默覆盖。
- 建议：改 with_for_update 行锁，或 UPDATE...WHERE version=:expected 校验受影响行数。

**[BE-be-srs-04] [Medium/置信度:中] restrict 声称可逆却无反向迁移**
- 位置：`backend/app/domains/srs/services.py:47-53`
- 问题：注释与 schema 文档称 :restrict 为'可逆的临时风控'，但 STATE_MACHINE 无任何把 restricted 迁回 active 的动作。一旦 restrict，只能 deprecate→obsolete，无法解除限制，与设计声明矛盾。
- 为什么是问题：功能缺口：临时风控无法解除，状态被单向锁死。
- 建议：新增 unrestrict 动作 {restricted: active} 或修正文档措辞。

**[BE-be-srs-05] [Medium/置信度:中] 软删除无引用与状态守卫**
- 位置：`backend/app/domains/srs/services.py:634-652`
- 问题：soft_delete 不检查该 substance 是否被 project/asset/material 链接引用，也不限制可删除的状态（active/registered 等已注册物质同样可删）。删除后正向引用悬挂（链接仍指向已删物质），且仅需 substance:update 权限+reason，无版本/签名校验。
- 为什么是问题：已注册主数据被随意软删会破坏跨域引用一致性与 GxP 治理。
- 建议：删除前校验活动引用计数并限制 draft/obsoleted 等可删状态。

**[BE-be-srs-06] [Low/置信度:中] 排序字段 getattr 任意属性可致 500**
- 位置：`backend/app/domains/srs/services.py:130-137`
- 问题：list_substances 用 getattr(Substance, fname, None) 取排序列，仅判空。传入如 sort=metadata/registry 等类属性会返回非 Column 对象，col.desc() 抛 AttributeError → 500；虽非注入但缺白名单。
- 为什么是问题：用户可控字符串触发未处理异常。
- 建议：用显式可排序字段白名单校验 fname。

**[BE-be-srs-07] [Low/置信度:中] sameness 忽略 substance_type**
- 位置：`backend/app/domains/srs/services.py:831-939`
- 问题：CheckSamenessRequest 必传 substance_type 但 check_sameness 全程未用于过滤，序列哈希/internal_code 匹配跨所有类型返回。可能把不同 modality 的同 internal_code 或巧合哈希误列为候选。
- 为什么是问题：同一性判定结果掺入跨类型噪声，confidence 语义弱。
- 建议：匹配查询加 substance_type 过滤或在 matched_fields 标注类型差异。

**[BE-be-srs-08] [Low/置信度:中] create 对非蛋白类型静默丢弃 protein**
- 位置：`backend/app/domains/srs/services.py:366,461-464`
- 问题：create() 当 substance_type 不在 (mab,bispecific,fusion) 时即便 payload.protein 有值也静默忽略，不报错；而 update()/update_protein 同情形抛 BadRequestError。行为不一致，用户提交的 protein 数据被无声吞掉。
- 为什么是问题：同一约束在创建与更新路径表现不一致，易丢数据。
- 建议：create 对不适用类型携带 protein 时同样抛 BadRequestError。

**[BE-be-srs-09] [Low/置信度:中] is_primary 多主未约束**
- 位置：`backend/app/domains/srs/services.py:394-408,787-803`
- 问题：新增/更新 xref 设 is_primary=True 时不会取消同 substance 同 xref_type 下其它 primary，DB 也无 (substance_id,xref_type) 单 primary 约束，可出现一个物质同类型多条 is_primary。
- 为什么是问题：主标识符歧义，下游取 primary 结果不确定。
- 建议：设置 primary 时先清同类型其它 primary，或加部分唯一索引。

**[BE-be-srs-10] [Low/置信度:中] effective/expiry 日期区间未校验**
- 位置：`backend/app/domains/srs/schemas.py:93-94 + services.py:798-799`
- 问题：SubstanceXref 的 effective_date/expiry_date 无 expiry>=effective 的校验，可写入失效早于生效的区间，列表 INN/CAS 取值也未按区间过滤。
- 为什么是问题：可落入逻辑非法的生效区间。
- 建议：schema 加 model_validator 校验 expiry_date>=effective_date。

**[BE-be-srs-11] [Low/置信度:低] confidentiality 无访问分级**
- 位置：`backend/app/api/v1/substances.py:30-57,111-125`
- 问题：list/get 仅校验 substance:read，未按 confidentiality(public/internal/restricted) 对 SQL 结果做访问分级过滤；任何持 read 权限者可读 restricted 机密物质。若设计要求按密级隔离则缺失，若纯 RBAC 则可忽略。
- 为什么是问题：机密分级字段未在查询层落地为访问控制。
- 建议：确认是否需密级过滤；如需，在查询 where 注入用户可见密级集合。

### be-prs

（审查任务尚未完成，待补跑）

### be-ars（23 条：High 3 / Medium 7 / Low 13）

> ARS 域整体结构清晰，状态机/电子签名/审计主线完整。但发现多处隐藏缺陷：market_id 软删后重建会撞全量唯一约束致 500；状态机与乐观锁均为"先读后写"无行锁，并发可使 terminated 资产复活；幂等缓存在事务提交前写入 Redis，提交失败后重试永远返回假成功；软删除资产无签名要求、无引用检查且删除后审计历史不可查。共 22 项，含多条低置信度问题。

**[BE-be-ars-01] [High/置信度:高] market_id 软删后重建撞唯一约束**
- 位置：`backend/app/domains/ars/services.py:329-364; backend/alembic/versions/2026_05_12_0040_0023_ars_market_id.py:40-43`
- 问题：add_market_id 预检只过滤 deleted_at IS NULL，但 DB 的 uq_asset_market_id 是含软删行的全量约束。软删某注册号后再添加相同 (market_code,id_type,id_value) 预检通过、INSERT 触发 IntegrityError 500。
- 为什么是问题：项目约定 service 不 catch IntegrityError，异常直接冒泡且 session 报废，业务上软删重录是常见操作。
- 建议：改为 partial unique index（WHERE deleted_at IS NULL），或参照 AssetSubstanceLinkService 复活软删行。
- 对抗复核：⏳ 复核未完成（中断），按原审查员置信度采信

**[BE-be-ars-02] [High/置信度:高] 幂等缓存先于事务提交写入**
- 位置：`backend/app/api/v1/assets.py:101-105; backend/app/core/database.py:64-73`
- 问题：create_asset 在 IdempotencyService.save 写 Redis 后才由 get_db 在响应后 commit。若 commit 失败（约束/连接），Redis 已缓存 201 成功体，客户端持同一 Idempotency-Key 重试将永远命中缓存假成功，DB 无该资产。
- 为什么是问题：幂等机制把一次性提交失败放大为不可恢复的数据丢失假象，且 Location 指向不存在资源。
- 建议：按项目强一致约定在 service 内显式 commit 成功后再写幂等缓存。
- 对抗复核：⏳ 复核未完成（中断），按原审查员置信度采信

**[BE-be-ars-03] [High/置信度:中] 状态机并发竞态可复活已终止资产**
- 位置：`backend/app/domains/ars/services.py:234-275`
- 问题：change_status 先 SELECT（无 FOR UPDATE）在 Python 校验转移合法性，再无条件 UPDATE status。并发下 T1 terminate 提交后，T2 基于陈旧 active 读的 hold 仍会执行，把 terminated 改回 on_hold。
- 为什么是问题：terminate 是签名保护的不可逆 GxP 动作，竞态可绕过状态机约束使其被撤销。
- 建议：查询加 with_for_update()，或 UPDATE ... WHERE status=:old 校验影响行数。
- 对抗复核：⏳ 复核未完成（中断），按原审查员置信度采信

**[BE-be-ars-04] [Medium/置信度:高] 更新注册号无唯一性预检**
- 位置：`backend/app/domains/ars/services.py:366-395`
- 问题：update_market_id 允许修改 market_code/id_type/id_value，但没有任何重复预检；改成与同资产另一活动行相同的组合时直接撞 uq_asset_market_id 报 IntegrityError 500。
- 为什么是问题：违反项目'pre-check 替代 IntegrityError 捕获'约定，用户得到不可解读的 500。
- 建议：当三个键字段任一变化时复用 add_market_id 的唯一性预检。

**[BE-be-ars-05] [Medium/置信度:高] 已删资产审计历史返回 404**
- 位置：`backend/app/domains/audit/services.py:552-560（入口 backend/app/api/v1/assets.py:153-174）`
- 问题：get_asset_audit_logs 先按 deleted_at IS NULL 解析 asset_id，资产软删后其全部审计日志（含 DELETE 事件本身）经 API 不可检索。
- 为什么是问题：审计追踪的可检索性要求覆盖已删记录（ALCOA+），删除恰是最需要追溯的事件。
- 建议：审计查询取消 deleted_at 过滤，仅按 asset_code 解析 id。

**[BE-be-ars-06] [Medium/置信度:中] 乐观锁校验存在 TOCTOU 竞态**
- 位置：`backend/app/domains/ars/services.py:183-198`
- 问题：update() 在 Python 比较 asset.version == payload.version 后 flush，UPDATE 无 WHERE version 条件。两个并发 PUT 携带同一 version 都能通过校验，后提交者静默覆盖前者修改，触发器各自 +1 版本。
- 为什么是问题：乐观锁的并发防护目的在并发场景下失效，主数据被静默覆盖。
- 建议：UPDATE 加 WHERE version=:v 并检查 rowcount，或 SELECT FOR UPDATE 后校验。

**[BE-be-ars-07] [Medium/置信度:中] PUT 显式 null 可置空非空列**
- 位置：`backend/app/domains/ars/schemas.py:58-68; backend/app/domains/ars/services.py:189-193`
- 问题：AssetUpdate 所有字段 Optional 且 update() 用 exclude_unset；请求体显式传 "internal_name": null（或 asset_type/current_phase/is_commercial 为 null）会把 NOT NULL 列设为 None，flush 时 DB 报错 500。
- 为什么是问题：exclude_unset 不排除显式 null，必填字段被恶意或误操作置空导致 500 且 session 报废。
- 建议：对非空列加 field_validator 拒绝 None，或改用 exclude_none 处理这些字段。

**[BE-be-ars-08] [Medium/置信度:中] 软删资产不检查也不级联引用**
- 位置：`backend/app/domains/ars/services.py:202-210; backend/app/domains/ref/services.py:537-552`
- 问题：soft_delete 不检查 ref.asset_substance / ref.project_asset 活动链接，也不级联软删；且 ProjectAssetLinkService.list_for_project 的 join 不过滤 Asset.deleted_at，已删除资产仍出现在项目的资产列表中。
- 为什么是问题：跨域引用一致性破坏：链接指向已删主数据且对项目侧可见，MDM 引用完整性失守。
- 建议：删除前预检活动引用并阻止或级联软删；list_for_project 增加 Asset.deleted_at IS NULL 过滤。

**[BE-be-ars-09] [Medium/置信度:中] 软删除无签名且复用 update 权限**
- 位置：`backend/app/api/v1/assets.py:141-150`
- 问题：DELETE /assets/{code} 仅需 asset:update + change_reason，无电子签名、无独立 asset:delete 权限（seed 中也未定义）。而可恢复性更强的 terminate 反而要求双权限+签名。
- 为什么是问题：删除使资产从所有 API 消失，破坏性不低于 terminate，签名要求操作清单存在缺口。
- 建议：为删除增加 asset:sign 签名要求或引入独立 asset:delete 权限。

**[BE-be-ars-10] [Medium/置信度:中] 签名含义可与动作不符**
- 位置：`backend/app/domains/ars/services.py:258`
- 问题：sign 时 meaning 取 signature.meaning or ACTION_TO_MEANING[action]，客户端可为 terminate 传 meaning="approve" 等任意合法枚举，签名记录的含义与实际动作矛盾。
- 为什么是问题：Part 11 §11.50 要求签名含义准确反映动作，含义被篡改削弱签名证据力。
- 建议：按 action 白名单校验 meaning，不匹配即拒绝。

**[BE-be-ars-11] [Low/置信度:高] sort 参数可注入非列属性致 500**
- 位置：`backend/app/domains/ars/services.py:102-109`
- 问题：getattr(Asset, fname, None) 不限定列名，传 sort=metadata/registry 等 ORM 类属性时返回非列对象，调用 .desc() 抛 AttributeError 500。
- 为什么是问题：未做列白名单，任意已认证用户可用查询参数触发服务端异常。
- 建议：维护可排序字段白名单，非法字段忽略或返回 422。

**[BE-be-ars-12] [Low/置信度:高] 添加注册号预检-插入竞态**
- 位置：`backend/app/domains/ars/services.py:333-363`
- 问题：add_market_id 的唯一性预检与 INSERT 之间无锁，两个并发请求同组合都通过预检，第二个在 commit/flush 时 IntegrityError 500，按项目约定无 rollback 兜底。
- 为什么是问题：并发注册同一主数据标识的经典竞态，错误响应不友好且 session 损坏。
- 建议：依赖 DB 约束兜底并在 API 层把该 IntegrityError 翻译为 409（或加咨询锁）。

**[BE-be-ars-13] [Low/置信度:高] asset_market_id 无乐观锁**
- 位置：`backend/app/domains/ars/models.py:96-131; backend/app/domains/ars/services.py:366-395`
- 问题：子表无 version 字段，PUT 无并发控制，两用户同时编辑同一注册号为 last-write-wins 静默覆盖。
- 为什么是问题：注册号是法规标识符，静默覆盖会丢失另一方修改且难以察觉。
- 建议：增加 version 列或要求 If-Match/updated_at 一致性校验。

**[BE-be-ars-14] [Low/置信度:高] 签名校验先于存在性校验**
- 位置：`backend/app/domains/ars/services.py:228-234`
- 问题：change_status 中 SignatureRequiredError 在 _get_asset_or_404 之前抛出；对不存在的 code 执行 terminate（无签名）返回签名错误而非 404。
- 为什么是问题：错误语义顺序不当，亦向未授权探测方暗示端点行为。
- 建议：先取资产再做签名必要性校验。

**[BE-be-ars-15] [Low/置信度:中] MAX(history_id) 回填存在竞态**
- 位置：`backend/app/domains/ars/services.py:276-294`
- 问题：状态变更后用 UPDATE … WHERE history_id=(SELECT MAX … WHERE asset_id=:aid) 回填 reason/签名 id；同资产并发状态变更时可能回填到对方插入的历史行。
- 为什么是问题：签名与状态历史的关联是 Part 11 证据链，错绑会指向错误事件。
- 建议：让触发器 RETURNING 或按 (asset_id, old/new_status, changed_by, 本事务) 精确定位行。

**[BE-be-ars-16] [Low/置信度:中] 状态历史排序无次级键**
- 位置：`backend/app/domains/ars/services.py:306-314`
- 问题：get_status_history 仅按 changed_at DESC 排序；同一事务/同一时刻多条记录（NOW() 为事务时间戳）顺序不确定。
- 为什么是问题：状态历史顺序错乱会误导审查者对状态演进的判断。
- 建议：追加 history_id DESC 作为次级排序键。

**[BE-be-ars-17] [Low/置信度:中] 状态机端点不校验乐观锁版本**
- 位置：`backend/app/domains/ars/schemas.py:127-134; backend/app/domains/ars/services.py:213-241`
- 问题：AssetStatusChange 无 version 字段，hold/resume/terminate 不校验客户端持有的版本，stale 页面可在他人变更后直接执行状态转移。
- 为什么是问题：PUT 有乐观锁而状态机没有，防护不一致；签名 hash 中 version 也可能是陈旧值。
- 建议：请求体增加 version 并与当前行比对，不一致返回 409。

**[BE-be-ars-18] [Low/置信度:中] 资产组分列表含已删物质**
- 位置：`backend/app/domains/ref/services.py:354-371`
- 问题：AssetSubstanceLinkService.list_for_asset 的 join 不过滤 Substance.deleted_at（对称方法 list_for_substance 却过滤了 Asset.deleted_at），已软删物质仍出现在资产的组分列表。
- 为什么是问题：asset-substance 链接展示不一致，已删主数据泄漏到下游视图。
- 建议：join 条件补 Substance.deleted_at IS NULL（或随 include_deleted 控制）。

**[BE-be-ars-19] [Low/置信度:中] 取号行锁横跨响应期**
- 位置：`backend/app/domains/ars/services.py:61-63, 168-171; backend/alembic/versions/2026_05_11_1200_0001_init_schemas.py:45-65`
- 问题：create 在 service 内调 fn_next_code（UPDATE meta.code_sequence 行），但事务由 get_db 在响应序列化后才 commit，code_sequence 行锁全程持有，所有并发 create 在此串行排队。
- 为什么是问题：吞吐瓶颈且慢响应会放大锁等待；与 MM/EQP 等共用取号表时互相阻塞。
- 建议：create 完成后在 service 内显式 commit，或取号改为 PG sequence。

**[BE-be-ars-20] [Low/置信度:中] 软删不更新 updated_by**
- 位置：`backend/app/domains/ars/services.py:202-210`
- 问题：soft_delete 仅设 deleted_at/deleted_by，不设 updated_by；BEFORE UPDATE 触发器会 bump version/updated_at，行内 updated_by 仍指向上一次编辑者。
- 为什么是问题：行级审计字段自相矛盾（updated_at 新而 updated_by 旧），排查时误导。
- 建议：soft_delete 中同步设置 asset.updated_by = current_user.user_id。

**[BE-be-ars-21] [Low/置信度:中] market_id 枚举与大小写仅应用层约束**
- 位置：`backend/app/domains/ars/schemas.py:138-151; backend/alembic/versions/2026_05_12_0040_0023_ars_market_id.py:26-33`
- 问题：MarketIdStatus 枚举只在 Pydantic 层，DB 无 CHECK；market_code 不做大小写规范化，"us" 与 "US" 被视为不同记录可重复注册。
- 为什么是问题：导入脚本/直写路径可绕过枚举；大小写差异造成事实重复的法规标识。
- 建议：DB 加 CHECK，market_code 入库前统一 upper()。

**[BE-be-ars-22] [Low/置信度:低] ilike 通配符未转义**
- 位置：`backend/app/domains/ars/services.py:75-84, 94-95`
- 问题：q 与 therapeutic_area 直接拼入 %…% 的 ilike 模式，用户输入含 %/_ 时产生非预期的通配匹配（如 q="%" 命中全部）。
- 为什么是问题：非注入风险但搜索结果失真，亦可被用来全量枚举。
- 建议：对用户输入做 escape（ilike(kw, escape='\\')）。

**[BE-be-ars-23] [Low/置信度:低] 创建时编码冲突预检为死代码**
- 位置：`backend/app/domains/ars/services.py:140-144`
- 问题：fn_next_code 由计数器行锁保证单调唯一，create 中的 asset_code 重复预检永不命中；真正的兜底是 uq_asset_code。该查询徒增一次往返。
- 为什么是问题：无害但掩盖真实并发保障机制，维护者易误解。
- 建议：删除预检或注释说明仅为防御序列被人工回拨。

### be-mm（18 条：High 1 / Medium 6 / Low 11）

> MM 域整体实现规范：唯一约束落 DB、写操作走 DB 审计触发器、端点均有权限依赖、列表已避免 N+1。主要隐患集中在：批次全表唯一约束与软删预检口径不符（复用批号 500）、已删物料审计历史 404、物质/物料软删的跨域级联与口径不一致、sort 参数任意 getattr 致 500，以及导入脚本对 material_name 未截断。共 18 项发现，1 High、6 Medium、11 Low。

**[BE-be-mm-01] [High/置信度:高] 软删批次后复用批号触发500**
- 位置：`backend/app/domains/mm/services.py:380-391, 440-454; backend/alembic/versions/2026_05_13_0500_0033_mm_material_batch.py:72`
- 问题：uq_material_batch 是全表唯一约束（含软删行），但 add_batch/update_batch 的重复预检均过滤 deleted_at IS NULL。软删某批次后再以同批号新建/改名，预检通过、flush 时撞 DB 唯一约束抛 IntegrityError。
- 为什么是问题：项目约定禁止 service 捕获 IntegrityError，该异常未映射，用户得到 500 而非 44001。
- 建议：将 uq_material_batch 改为 partial unique index（WHERE deleted_at IS NULL），或预检改为全表口径并提示编码占用。
- 对抗复核：⏳ 复核未完成（中断），按原审查员置信度采信

**[BE-be-mm-02] [Medium/置信度:高] 已删物料审计历史不可查**
- 位置：`backend/app/domains/audit/services.py:281-289; backend/app/api/v1/materials.py:215-236`
- 问题：GET /materials/{code}/audit-logs 内部按 Material.deleted_at IS NULL 解析 material_id，物料软删后该端点 404，包括 DELETE 事件在内的全部审计链从 API 层不可达。
- 为什么是问题：MDM 平台审计追踪应覆盖已删除主数据，软删后审计断链是追溯缺口。
- 建议：审计查询解析 material_id 时去掉 deleted_at 过滤（或加 include_deleted 参数）。

**[BE-be-mm-03] [Medium/置信度:高] sort参数任意getattr可致500**
- 位置：`backend/app/domains/mm/services.py:147-154`
- 问题：排序字段用 getattr(Material, fname, None) 取值，sort=metadata/registry 等非列属性返回非 None 对象，调用 .desc() 抛 AttributeError 500；且可按 deleted_by/extra 等未暴露列排序。
- 为什么是问题：未做排序字段白名单，畸形参数可稳定打出 500，也泄露内部列可排序性。
- 建议：维护可排序字段白名单，非法字段忽略或返回 422。

**[BE-be-mm-04] [Medium/置信度:高] 物质软删不查物料引用**
- 位置：`backend/app/domains/srs/services.py:634-652; backend/app/domains/mm/services.py:132-142, 320-337`
- 问题：SRS soft_delete 不检查 mm.material 是否仍引用该 substance，删除后物料 substance_id 悬挂。此后 GET /substances/{code}/materials 404，而 GET /materials?substance_code= 因未滤 deleted_at 仍可查，两条路径行为矛盾。
- 为什么是问题：跨域引用完整性缺失，且同一引用的两个查询口径不一致，前端展示会自相矛盾。
- 建议：substance 软删前检查活跃 material 引用并阻止（或提示）；统一两处查询的 deleted 过滤口径。

**[BE-be-mm-05] [Medium/置信度:高] 删物料不级联处理批次**
- 位置：`backend/app/domains/mm/services.py:308-317`
- 问题：soft_delete 仅置 material 的 deleted_at，旗下批次 deleted_at 仍为 NULL、状态保持 in_stock 等。批次经 API 不可达（父 404），但任何直查 material_batch 的统计/下游（cmc-inventory 上游定位）会把孤儿批次算作有效。
- 为什么是问题：身份注册表作为下游数据上游，残留活跃批次是隐性数据完整性缺口。
- 建议：删除物料时级联软删其未删批次，或在删除前校验存在活跃批次时阻止。

**[BE-be-mm-06] [Medium/置信度:中] 并发创建竞态返回500**
- 位置：`backend/app/domains/mm/services.py:224-232, 380-391`
- 问题：create/add_batch 用 pre-check + flush，两个并发请求同 material_code（或同批号）都通过预检，第二个在 flush 撞 uq_material_code/uq_material_batch 抛 IntegrityError，未映射为 40902/44001。
- 为什么是问题：唯一性靠 DB 约束兜底是对的，但兜底路径无友好错误映射，并发下用户见 500。
- 建议：在全局异常处理器把 UniqueViolation 按约束名映射为对应 409 业务错误。

**[BE-be-mm-07] [Medium/置信度:中] 导入未截断物料名超长**
- 位置：`backend/app/scripts/import_materials_excel.py:137; backend/app/scripts/import_materials_excel_0609.py:111-119`
- 问题：两个导入脚本对 manufacturer/spec_model 等都做了 _truncate，唯独 material_name（VARCHAR(255)）未截断。Excel 出现超长名称时 commit 抛 StringDataRightTruncation，整批导入回滚，但 stats/报告仍按已解析口径输出。
- 为什么是问题：ERP 导出名称常含全描述串，超 255 字符概率不低，单行脏数据使全批失败。
- 建议：对 material_name（及 notes 拼接前缀后）统一 _truncate 或超长行记 skip_reason。

**[BE-be-mm-08] [Low/置信度:高] 编码长度20/32不一致且未strip**
- 位置：`backend/app/domains/mm/schemas.py:77-82; backend/app/domains/mm/models.py:51`
- 问题：MaterialCreate.material_code max_length=20，模型与 DB 列为 VARCHAR(32)，口径不一致；且未 strip 空白、无格式校验，"R-001 "（尾随空格）与 "R-001" 可作为两条不同物料并存。
- 为什么是问题：手输编码是身份主键，空白差异会造成肉眼不可见的重复身份。
- 建议：用 str_strip_whitespace 或 validator 去首尾空白，统一 20/32 口径并加正则约束。

**[BE-be-mm-09] [Low/置信度:高] 旧自动编码触发器残留**
- 位置：`backend/alembic/versions/2026_05_19_0100_0038_mm_material_v2.py; backend/alembic/versions/2026_05_13_0400_0032_mm_material.py:127-147`
- 问题：v2 改为用户手输编码，但 0038 未删除 trg_material_assign_code：任何路径插入空字符串/NULL 编码时仍会静默生成 MAT-yyyyXXXXXX 旧格式编码，绕过手输编码体系。
- 为什么是问题：API 层有 min_length=1 防护，但脚本/SQL 直插会产生旧格式编码混入注册表。
- 建议：在新 migration 中 DROP 该触发器，或改为插空码时直接报错。

**[BE-be-mm-10] [Low/置信度:高] hazard_class无DB层约束**
- 位置：`backend/app/domains/mm/models.py:70; backend/alembic/versions/2026_05_19_0100_0038_mm_material_v2.py:41`
- 问题：hazard_class 的 5 值白名单只在 Pydantic 校验（schemas.py:16-31），DB 列为裸 TEXT[] 无 CHECK；导入脚本、psql 直写可放入任意值，与 material_type/category 均有 DB CHECK 的做法不一致。
- 为什么是问题：审查要点要求枚举约束在数据库层强制，旁路写入会破坏字典一致性。
- 建议：加 CHECK (hazard_class <@ ARRAY[...]) 约束对齐其他枚举字段。

**[BE-be-mm-11] [Low/置信度:中] 空串substance_code误触发校验**
- 位置：`backend/app/domains/mm/services.py:286-292`
- 问题：update 中 sub_provided 判断用 payload.substance_code is not None，传 "" 时视为提供了引用，落入 substance_id 分支重新校验当前引用；若当前 substance 已 obsoleted，普通字段更新会被 403 拒绝。
- 为什么是问题：用户仅改名称等字段却因历史引用状态被拒，语义错位。
- 建议：空串视同未提供（if payload.substance_code），或 schema 校验非空。

**[BE-be-mm-12] [Low/置信度:中] 批次缺日期/数量合理性校验**
- 位置：`backend/app/domains/mm/schemas.py:184-197`
- 问题：MaterialBatch 无 expiry_date >= manufacture_date 校验，quantity_value 可为负数（DB 也无 CHECK >= 0），可登记效期早于生产日期或负库存量的批次。
- 为什么是问题：批次效期与数量是物料管理核心字段，无校验易积累脏数据。
- 建议：schema 加 model_validator 校验日期先后与 quantity_value >= 0。

**[BE-be-mm-13] [Low/置信度:中] 幂等缓存先于事务提交**
- 位置：`backend/app/api/v1/materials.py:86-96`
- 问题：POST 创建在 service flush 后即写 IdempotencyService.save（201+Location），而 DB commit 由 get_db yield 在 response 之后执行；若 commit 失败，Redis 已缓存成功响应，24h 内重放同 key 返回不存在的“幽灵物料”。
- 为什么是问题：正是项目已知的 yield 依赖 commit 时机坑，幂等缓存放大了不一致窗口。
- 建议：创建端点在 service 内显式 commit 后再写幂等缓存。

**[BE-be-mm-14] [Low/置信度:中] include_deleted结果无删除标记**
- 位置：`backend/app/domains/mm/services.py:320-361; backend/app/domains/mm/schemas.py:127-148`
- 问题：list_for_substance 支持 include_deleted=True，但返回的 MaterialBrief 无 deleted_at/已删标识字段，调用方无法区分哪些物料已删除。
- 为什么是问题：混合返回在前端会把已删物料当活跃数据展示。
- 建议：MaterialBrief 增加 deleted_at（或 is_deleted）字段。

**[BE-be-mm-15] [Low/置信度:中] 删除权限复用update未分离**
- 位置：`backend/app/api/v1/materials.py:131-140, 198-212`
- 问题：DELETE /materials/{code} 与批次删除均挂 material:update 权限，seed 权限表只有 create/read/update 三项，无 material:delete；任何有更新权的角色可软删主数据。
- 为什么是问题：删除是比更新更高危的操作，权限粒度合并削弱纵向控制。
- 建议：新增 material:delete 权限并在 DELETE 端点使用。

**[BE-be-mm-16] [Low/置信度:中] PUT变更原因可选留痕缺口**
- 位置：`backend/app/domains/mm/schemas.py:92; backend/app/domains/mm/services.py:272-276`
- 问题：MaterialUpdate.change_reason 可为 None，PUT 改 status/substance_id 等关键字段可不带原因，审计行 change_reason 为空；DELETE 却强制 ≥5 字符，口径不一致。
- 为什么是问题：主数据状态与引用变更无原因留痕，弱化审计可追溯性（原型期或为设计取舍）。
- 建议：至少对 status/substance_id 变更强制 change_reason。

**[BE-be-mm-17] [Low/置信度:低] 0609脚本列位硬编码与重复字面量**
- 位置：`backend/app/scripts/import_materials_excel_0609.py:76, 82-84`
- 问题：COL_NOTE=17/COL_UNIT=22 按固定列位取值且不校验表头，列布局再变化会静默错位入库；PRODUCT_TYPES 集合字面量重复写入两次 "注射剂"（无害但暴示笔误风险）。
- 为什么是问题：ERP 导出布局已变过一次（0429→0609），固定下标是再次错位导入的隐患。
- 建议：导入前断言第2行表头与预期列名一致，去掉重复字面量。

**[BE-be-mm-18] [Low/置信度:低] 迁移DELETE触发逐行审计**
- 位置：`backend/alembic/versions/2026_05_19_0100_0038_mm_material_v2.py:26-27`
- 问题：0038 用 DELETE FROM 清空 demo 数据，audit v3 触发器对每行做字段级展开写审计（操作者 GUC 为空、username=system），迁移期间产生大量无操作者审计记录并拖慢升级。
- 为什么是问题：迁移上下文无审计 GUC，记录归属不明；行数大时升级耗时显著。
- 建议：清库类迁移可先禁用触发器或用 TRUNCATE（按审计留存策略权衡）。

### be-eqp（18 条：Medium 6 / Low 12）

> EQP 域整体对标 mm 域、结构清晰：equipment_code 由 DB 触发器生成且有 DB 层唯一约束，审计走 trigger v3。主要问题集中在：Excel 导入工具金额"万元"解析顺序 bug 致资产值静默丢失、表头别名"编号"过宽可能把行号当设备编号；API 层 sort 参数可触发 500、PUT 显式 null 撞 NOT NULL、幂等缓存先于 commit 写入；以及若干文档/统计口径陈旧与去重口径不一致。无 Critical。

**[BE-be-eqp-01] [Medium/置信度:高] 金额万元解析顺序bug**
- 位置：`backend/app/scripts/import_equipment_excel.py:260-267`
- 问题：parse_decimal 清洗单位时循环先 replace '元' 再查 '万元'：'12万元'→'12万'→Decimal 失败→None。'万元' 分支永不生效，且即使生效也只去单位不乘 10000。
- 为什么是问题：台账中以万元计价的资产原值全部静默丢为 NULL 或量级错误。
- 建议：先去 '万元' 并乘 10000，再去 '元'；解析失败计入报告而非静默 None。

**[BE-be-eqp-02] [Medium/置信度:高] sort参数可致500**
- 位置：`backend/app/domains/eqp/services.py:65-72`
- 问题：getattr(Equipment, fname, None) 未限定列属性：sort=metadata/registry 等返回非列对象，col.desc() 抛 AttributeError → 500。mm 域同模式。
- 为什么是问题：任意带 equipment:read 权限的用户可用查询串触发未处理异常。
- 建议：用白名单或 isinstance(col, InstrumentedAttribute) 校验，再兜底默认排序。

**[BE-be-eqp-03] [Medium/置信度:高] PUT显式null撞NOT NULL**
- 位置：`backend/app/domains/eqp/services.py:143-149 + schemas.py:60-78`
- 问题：EquipmentUpdate 全字段 Optional + exclude_unset：客户端显式传 equipment_name/category/has_workstation=null 会 setattr None，flush 时 NOT NULL/CHECK 违例 → IntegrityError 500。
- 为什么是问题：违反项目约定（禁 except IntegrityError，应 pre-check），且 500 无业务错误码。
- 建议：schema 校验必填字段不可为 null，或 update 中过滤 None 的非空列。

**[BE-be-eqp-04] [Medium/置信度:中] 表头别名'编号'过宽**
- 位置：`backend/app/scripts/import_equipment_excel.py:153,289-309`
- 问题：'编号/编码' 直接映射 equipment_no，且 detect_header 先到先得。台账常见的行号列若命中（或与'设备编号'列并存且靠前），行号 1/2/3 会被当成设备编号入库并参与去重。
- 为什么是问题：设备编号是三标识之一，污染后跨文件重导会按错误编号去重漏导/错跳。
- 建议：移除裸 '编号/编码' 别名或要求含'设备'字样；报告中输出列映射供 dry-run 核对。

**[BE-be-eqp-05] [Medium/置信度:中] 幂等缓存先于commit写入**
- 位置：`backend/app/api/v1/equipments.py:74-83`
- 问题：create 在 service 仅 flush，commit 由 get_db yield 依赖在 response 后执行；IdempotencyService.save 在 commit 前已写 Redis。若 commit 失败，24h 内同 key 重试直接返回缓存的 201 假成功。
- 为什么是问题：主数据未落库但幂等层永久回放成功响应，设备实际不存在。
- 建议：按项目约定在 service 内显式 commit 后再写幂等缓存。

**[BE-be-eqp-06] [Medium/置信度:中] API创建无任何查重**
- 位置：`backend/app/domains/eqp/services.py:100-129`
- 问题：POST /equipments 对 equipment_no/serial_no+manufacturer/fixed_asset_no 既无应用层 pre-check 也无 DB 唯一约束（仅 equipment_code 唯一），同一物理设备可被重复注册；并发或重复提交（未带幂等键）直接产生重复主数据。
- 为什么是问题：身份注册表出现一机多码，下游 LabOps 拉取后引用歧义。
- 建议：至少对非空 equipment_no/serial_no 做软删感知的 pre-check 警告或加部分唯一索引。

**[BE-be-eqp-07] [Low/置信度:高] 两导入工具去重口径不一致**
- 位置：`backend/app/scripts/import_equipment_excel.py:357-368 vs import_equipment_lims.py:203-205`
- 问题：Excel 工具按未软删记录去重（软删后可重导），LIMS 工具含软删去重（软删后不可重导）；且 Excel 的 equipment_no 比对大小写敏感而自然键 lower()，QC001/qc001 视为不同。
- 为什么是问题：多源重入导入时行为不一致，易产生重复或漏导。
- 建议：统一软删口径与大小写归一化（建议 equipment_no 也 lower 后比对）。

**[BE-be-eqp-08] [Low/置信度:高] 硬编码默认数据库密码**
- 位置：`backend/app/scripts/import_equipment_lims.py:291`
- 问题：--pg-pass 默认值内嵌 '__REDACTED_POSTGRES_PASSWORD__' 字面量；另 RD_ENV 写死个人机器绝对路径 /Users/qingcheng/...。
- 为什么是问题：占位密码随仓库分发，且脚本不可移植到 Linux 侧。
- 建议：默认仅取环境变量，缺失时报错退出；路径改参数/环境变量。

**[BE-be-eqp-09] [Low/置信度:高] 导入统计与文档口径陈旧**
- 位置：`backend/app/scripts/import_equipment_excel.py:24-32,414-421,517`
- 问题：docstring 仍写 4 枚举/默认『其他』/EQP-yyyyXXXXXX（实为 5 类/通用实验室设备/EQP-yyyy-NNNNNN）；print_stats 文案同样写『其他』；db_dup 只计 duplicated 不进 skipped_by_reason，category_defaulted 把后被跳过的行也计入。
- 为什么是问题：操作者按报告核对数量时口径对不上，易误判导入结果。
- 建议：更新注释与文案；db_dup 同步计入跳过原因；defaulted 只统计实际待插入行。

**[BE-be-eqp-10] [Low/置信度:高] 工作站字段无一致性校验**
- 位置：`backend/app/domains/eqp/services.py:135-151 + schemas.py:73-75`
- 问题：has_workstation=False 时仍可写入/保留 workstation_info；置 False 不清空已有 JSONB，详情仍返回旧配置；workstation_info 键结构（brand/os/cpu 等）完全不校验。
- 为什么是问题：标志位与配置内容矛盾，下游 LabOps 拉取后语义歧义。
- 建议：schema validator 联动校验；置 False 时同时清空 workstation_info。

**[BE-be-eqp-11] [Low/置信度:高] LIKE通配符未转义**
- 位置：`backend/app/domains/eqp/services.py:36-51`
- 问题：q 与 manufacturer 过滤直接拼 %{token}%，用户输入中的 %/_ 作为通配符生效（q=_ 匹配全部）；搜索域 _search_equipment 同样。
- 为什么是问题：非预期匹配结果；全域共性问题，eqp 同样存在。
- 建议：对用户输入做 LIKE 转义（\% \_）或用 escape 参数。

**[BE-be-eqp-12] [Low/置信度:中] fixed_asset_no无唯一性**
- 位置：`backend/alembic/versions/2026_06_05_0200_0044_eqp_identifiers.py:25-34`
- 问题：固资编号（财务/ERP）未建唯一索引也无应用层查重，可重复；migration 注释只声明 equipment_no 可非唯一，fixed_asset_no 唯一性未明确。
- 为什么是问题：财务固定资产编号通常应一一对应，重复会影响资产对账。
- 建议：确认业务规则；若应唯一，加 deleted_at IS NULL 部分唯一索引。

**[BE-be-eqp-13] [Low/置信度:中] category子串匹配误判**
- 位置：`backend/app/scripts/import_equipment_lims.py:64,69 / import_equipment_excel.py:125,134-137`
- 问题：别名匹配为大小写不敏感子串：'pH'→'PH' 会命中 SPECTROPHOTOMETER 等英文名归入通用实验室设备；'GC'/'生产'/'环境' 等短词同理易误命中。
- 为什么是问题：5 类归类是横切检索/仪表盘的维度，误分类影响统计与筛选。
- 建议：短英文别名加词边界匹配；dry-run 报告中对关键词命中列出依据词。

**[BE-be-eqp-14] [Low/置信度:中] 约束发现只删一个**
- 位置：`backend/alembic/versions/2026_06_04_0300_0042_eqp_category_5class.py:44-58`
- 问题：_drop_category_constraint 用 SELECT conname INTO（取任意一条）按 '%(category)%' 模式匹配；若某机同时存在双前缀旧约束和规整约束两条，只删其一，随后 UPDATE 重映射或 ADD CONSTRAINT 会失败。
- 为什么是问题：注释已承认各机约束名不一致，多约束并存场景未覆盖。
- 建议：改为 FOR 循环删除所有匹配的 category check 约束。

**[BE-be-eqp-15] [Low/置信度:中] Excel解析静默丢值**
- 位置：`backend/app/scripts/import_equipment_excel.py:226-247,326,349`
- 问题：超长字段 _truncate 静默截断无报告标记；parse_date 非常见格式（含时间的字符串、数字序列日期）静默置 None；'if not any(row)' 会跳过仅含 0/False 的数据行。
- 为什么是问题：主数据导入丢字段不留痕，dry-run 报告也看不出。
- 建议：截断/解析失败计入行级 warning 列；空行判断改 all(v is None)。

**[BE-be-eqp-16] [Low/置信度:低] LIMS状态映射过于宽松**
- 位置：`backend/app/scripts/import_equipment_lims.py:135-136`
- 问题：仅 STATUS='R' 映射 retired，其余（含 SampleManager 的 X/U 等停用类状态）一律 active 导入。
- 为什么是问题：已停用仪器可能以 active 进入主数据并出现在检索/仪表盘。
- 建议：核对 LIMS STATUS 全枚举，明确各值映射；未知值在报告中标注。

**[BE-be-eqp-17] [Low/置信度:低] 删除复用update权限**
- 位置：`backend/app/api/v1/equipments.py:119-123 + app/scripts/seed_data.py:70-72`
- 问题：DELETE 端点用 equipment:update 鉴权，权限表无 equipment:delete；任何可改设备者均可软删（与 mm 域一致的设计，但与 SRS 等域的 delete 粒度不统一）。
- 为什么是问题：主数据删除是高敏操作，权限粒度与其他域不一致。
- 建议：确认是否有意为之；如需细分补 equipment:delete 权限并改依赖。

**[BE-be-eqp-18] [Low/置信度:低] ORM与migration定义漂移**
- 位置：`backend/app/domains/eqp/models.py:85-91`
- 问题：模型的 created_by/updated_by/deleted_by 缺 ForeignKey(auth.user) 声明（migration 0040 有 FK），主键用 autoincrement 而非 Identity(always=True)。当前测试库由 alembic 建表无功能影响，纯元数据漂移。
- 为什么是问题：若未来走 metadata.create_all 或做模型比对，FK 会缺失。
- 建议：模型补 ForeignKey 与 Identity 声明，保持与 DB 一致。

### be-search（10 条：Medium 4 / Low 6）

> 搜索域结构清晰，5 类实体权限过滤确在查询发起前按 permission code 闸断、软删过滤齐全、无硬编码密钥。主要问题：ILIKE 通配符未转义（%/_ 可注入模式）；SQL LIMIT 无 ORDER BY 导致截断任意子集、精确命中可能被漏；project.program_name 与 asset.indication 参与 SQL 匹配但 matched_field 判定缺分支；types 非法值静默吞掉。无 Critical 发现。

**[BE-be-search-01] [Medium/置信度:高] ILIKE 通配符未转义**
- 位置：`backend/app/domains/search/services.py:109,160,191,226,256`
- 问题：pat = f"%{q}%" 直接拼接用户输入，q 中的 %、_、\ 未转义。q="%" 或 "_" 会匹配全部记录；含 _ 的编号（如 lot_no 风格）会产生误命中。参数化无 SQL 注入，但存在 LIKE 通配符注入。
- 为什么是问题：用户可用单字符 % 拉取全量可见数据，且含 _ 的查询产生错误匹配结果。
- 建议：对 q 做 \、%、_ 转义后再拼 %，并在 ilike() 传 escape="\\"。

**[BE-be-search-02] [Medium/置信度:高] LIMIT 无 ORDER BY 截断任意子集**
- 位置：`backend/app/domains/search/services.py:53,120,171,202,237,270`
- 问题：五个查询均 .limit(per_type_limit) 但无 ORDER BY，PG 返回任意行；Python 端 _rank 排序发生在 DB 截断之后。当匹配数超过 per_type_limit（≥20）时，精确编码命中可能根本不在返回集里，且结果在不同执行间不稳定。
- 为什么是问题：常见前缀（如 CMAB、MAT）匹配数百条时，最相关结果可能被漏掉。
- 建议：SQL 内加 ORDER BY（精确/前缀 CASE 权重或至少按 code），或扩大候选集后再排。

**[BE-be-search-03] [Medium/置信度:高] program_name 命中缺 matched_field 分支**
- 位置：`backend/app/domains/search/services.py:169,309-319; schemas.py:9-13`
- 问题：_search_project 的 SQL 含 Project.program_name ILIKE，但 _which_field_project 不检查 program_name，schema 的 MatchedField Literal 也无该值。仅 program_name 命中的项目会被误标为 matched_field="name" 且 snippet 为空。
- 为什么是问题：用户看到命中结果但名称里没有关键字，无法理解为何命中。
- 建议：_which_field_project 增加 program_name 分支并扩展 Literal，snippet 回填 program_name。

**[BE-be-search-04] [Medium/置信度:高] indication 命中缺 matched_field 分支**
- 位置：`backend/app/domains/search/services.py:200,322-332; schemas.py:9-13`
- 问题：_search_asset 的 SQL 含 Asset.indication ILIKE，但 _which_field_asset 不检查 indication，MatchedField Literal 亦无该值。仅适应症命中的资产被误标为 matched_field="name"，snippet 为 None。
- 为什么是问题：按适应症搜索（如肿瘤名）时命中原因不可见，前端展示误导。
- 建议：_which_field_asset 增加 indication 分支并扩展 Literal，snippet 回填 indication。

**[BE-be-search-05] [Low/置信度:高] types 非法值静默忽略**
- 位置：`backend/app/api/v1/search.py:33; backend/app/domains/search/services.py:61-65`
- 问题：types 逗号拆分后未校验合法性也不区分大小写，如 types="Substance" 或拼错值时 wanted 集合不命中任何分支，直接返回全 0 结果，无 422 报错。
- 为什么是问题：调用方拼写错误得到空结果而非报错，难以排查。
- 建议：路由层校验 types 值在 5 个合法枚举内，非法值返回 422。

**[BE-be-search-06] [Low/置信度:高] xref 查询 limit 按 join 行计数**
- 位置：`backend/app/domains/search/services.py:136-156`
- 问题：xref 子查询 .limit(lim) 作用于 (xref, substance) join 行；同一 substance 有多条命中 xref（如 INN+TRADE_NAME 都含关键字）时占用多个配额，去重后有效 substance 数偏少，且哪条 xref 进入 snippet 不确定。
- 为什么是问题：xref 丰富的物质会挤掉其他应命中的物质，结果不完整。
- 建议：改为按 substance_id DISTINCT ON 或子查询去重后再 limit。

**[BE-be-search-07] [Low/置信度:中] total 为截断后数量非真实总数**
- 位置：`backend/app/domains/search/services.py:97-104; schemas.py:33`
- 问题：SearchGroup.total 与响应 total 均为截断到 limit 后的 len(items)，不是 DB 真实匹配总数，且无 offset/skip 参数，前端无法得知是否还有更多结果。
- 为什么是问题：超过 limit 的命中对用户完全不可见且无任何提示。
- 建议：若需提示更多，增加 count(*) 真实总数或 has_more 标记；否则字段改名 returned。

**[BE-be-search-08] [Low/置信度:中] matched_field 复算与 DB 匹配可能不一致**
- 位置：`backend/app/domains/search/services.py:296-366`
- 问题：DB 用 ILIKE pattern 匹配，Python 用 lower 子串复算 matched_field；当 q 含通配符或 PG/Python 大小写折叠差异（如某些 Unicode）时两侧判定不一致，回退误标为 "name"。
- 为什么是问题：是发现一的衍生，导致命中字段标注错误。
- 建议：通配符转义后两侧语义即一致；或在 SQL 内用 CASE 返回命中字段。

**[BE-be-search-09] [Low/置信度:中] limit=50 时排序无余量**
- 位置：`backend/app/domains/search/services.py:53,89-93`
- 问题：per_type_limit = max(limit, 20)，limit≤20 时取 20 给 rank 留余量，但 limit 取上限 50 时 DB 截断量与最终截断量相同（50），排序完全受任意子集影响，与发现二叠加更明显。
- 为什么是问题：limit 越大反而候选余量越小，行为不一致。
- 建议：统一取 limit 的固定倍数（如 2x）作为候选集大小。

**[BE-be-search-10] [Low/置信度:低] 停用状态记录无差别返回**
- 位置：`backend/app/domains/search/services.py:114,164,195,230,260`
- 问题：五类查询仅过滤 deleted_at，retired/terminated/rejected 等终态记录与 active 平权混排返回，仅靠前端 status 字段展示区分。
- 为什么是问题：主数据场景下搜索结果含已退役实体，可能误用旧编码。
- 建议：确认是设计意图；否则降权排序或加 include_inactive 开关。

### be-core

（审查任务尚未完成，待补跑）

### be-migrations

（审查任务尚未完成，待补跑）

---

## 3. 前端代码审查发现（按模块）

### auth+admin（17 条：High 2 / Medium 6 / Low 9）

> auth+admin 共 14 个文件全部读完，并交叉核对了 client.ts 拦截器、authStore、路由守卫与后端 auth schemas/permissions。整体结构清晰，但发现 2 个高危问题：① 改密时旧密码错误返回 401(old_password_wrong)，被拦截器一刀切登出跳登录，违反项目 401 分流约定；② 强制改密前后端均无强制守卫，临时密码可绕过改密长期使用。另有密码长度前 8/后 12 不一致、redirect 双重解码、审计筛选缺 equipment、临时密码弹窗可误关等 15 项中低危发现。

**[FE-auth+admin-01] [High/置信度:高] 改密旧密码错被强制登出**
- 位置：`frontend/src/api/client.ts:122-134 + frontend/src/modules/auth/pages/ChangePasswordPage.tsx:45-54`
- 问题：后端 OldPasswordWrongError 是 HTTP 401（error_type=old_password_wrong，exceptions.py:105）。拦截器 401 分流只豁免 signature_invalid，old_password_wrong 落入兜底分支：toast「登录已过期」+ logout + 跳登录。ChangePasswordPage 的字段级报错永远展示不出来。
- 为什么是问题：违反项目「401 双重语义分流」约定：业务再验证 401 不应一刀切跳登录
- 建议：client.ts 401 豁免清单加入 old_password_wrong，交给调用方处理
- 对抗复核：⏳ 复核未完成（中断），按原审查员置信度采信

**[FE-auth+admin-02] [High/置信度:高] 强制改密可被完全绕过**
- 位置：`backend/app/shared/permissions.py:25-88 + frontend/src/routes/ProtectedRoute.tsx:4-14`
- 问题：force_password_change 仅在 LoginPage 登录成功后跳转一次（LoginPage.tsx:25-28）。改密页在 MainLayout 内，侧边栏可直接导航走；后端 get_current_user 也不校验该标记，持临时密码可正常调用全部 API。
- 为什么是问题：与 UI 承诺「首次登录将被强制改密」不符，临时密码可长期使用
- 建议：后端依赖里拦截 force_password_change=true（仅放行改密/登出）；前端加全局守卫
- 对抗复核：⏳ 复核未完成（中断），按原审查员置信度采信

**[FE-auth+admin-03] [Medium/置信度:高] 新密码长度校验前后端不一致**
- 位置：`frontend/src/modules/auth/pages/ChangePasswordPage.tsx:111-114`
- 问题：前端规则 min:8、tooltip 写「至少 8 位」；后端 ChangePasswordRequest new_password min_length=12（auth/schemas.py:70）。同页强制改密 Alert 又写「≥12 位」，文案自相矛盾。8-11 位密码前端放行、后端 422 拒绝。
- 为什么是问题：用户按提示填 8 位必然提交失败，且报错落在 pydantic 通用文案
- 建议：前端改 min:12 并统一 tooltip/Alert 文案为 12 位

**[FE-auth+admin-04] [Medium/置信度:高] 审计筛选缺 equipment 表**
- 位置：`frontend/src/modules/admin/pages/AuditLogPage.tsx:62-78`
- 问题：ENTITY_TABLE_OPTIONS 硬编码 15 张表，未包含 EQP 域 equipment（migration 0040 已接审计 trigger v3，entity_table='equipment'）。设备域审计记录无法用「对象表」下拉筛出。
- 为什么是问题：EQP 域后加入，字典未同步，审计检索能力出现盲区
- 建议：选项中补 equipment；或改为从后端动态拉取已有 entity_table 清单

**[FE-auth+admin-05] [Medium/置信度:高] redirect 参数双重解码**
- 位置：`frontend/src/modules/auth/pages/LoginPage.tsx:31-32`
- 问题：gotoLogin/ProtectedRoute 只 encodeURIComponent 一次，而 searchParams.get 已自动解码一次，LoginPage 再 decodeURIComponent 属二次解码。路径含 % 序列时被破坏；畸形序列使 decodeURIComponent 抛 URIError，被外层 catch 吞掉后误显示「登录失败」（此时实际已登录成功）。
- 为什么是问题：编码一次解码两次，含编码字符的回跳路径损坏甚至误报登录失败
- 建议：去掉 decodeURIComponent 直接用 redirect；并校验以 / 开头再 navigate

**[FE-auth+admin-06] [Medium/置信度:高] 临时密码弹窗可误触关闭**
- 位置：`frontend/src/modules/admin/components/ResetPasswordResultModal.tsx:24-37`
- 问题：Modal 未设 maskClosable={false} / closable={false}，默认点遮罩或右上角 X 即关闭。临时密码「仅本次显示一次」，误触后无法找回，只能再次重置。
- 为什么是问题：一次性凭证展示窗口应防误关，否则需重复重置密码并产生多余审计
- 建议：设 maskClosable={false}，仅保留「我已记下」按钮显式关闭

**[FE-auth+admin-07] [Medium/置信度:中] /admin 路由无权限守卫**
- 位置：`frontend/src/App.tsx:174-179 + frontend/src/routes/ProtectedRoute.tsx:4-14`
- 问题：ProtectedRoute 只校验 token，未校验 isAdmin/user:manage。非管理员手输 /admin/users 可进入页面，仅靠后端 403 toast 和空表兜底；Sidebar 隐藏菜单属于「假权限控制」。
- 为什么是问题：后端虽有 require_permission 兜底，但页面级守卫缺失，体验与纵深防御不足
- 建议：为 /admin/* 加 RequireAdmin 路由守卫，无权限时跳 403 页

**[FE-auth+admin-08] [Medium/置信度:中] 改密成功3秒窗口竞态**
- 位置：`frontend/src/modules/auth/pages/ChangePasswordPage.tsx:36-43`
- 问题：改密后旧 token 立即失效，但前端延迟 3 秒才 logout。窗口期内任何后台请求（react-query refetch、轮询）会 401 → 拦截器 refresh 失败（refresh token 已被后端撤销）→ 弹「登录已过期」并 window.location 强跳，覆盖友好提示。
- 为什么是问题：代码注释声称避免二次跳转，但 3 秒延迟恰好留下竞态窗口
- 建议：成功后立即 logout+navigate，提示改放登录页；或窗口期暂停所有查询

**[FE-auth+admin-09] [Low/置信度:高] 密码复杂度文案无后端校验**
- 位置：`frontend/src/modules/admin/components/UserFormDrawer.tsx:135 + ChangePasswordPage.tsx:81`
- 问题：UI 多处声称「包含大小写、数字、符号」，但后端 UserCreate/ChangePasswordRequest 仅校验 min_length=12，无任何复杂度 validator；前端也未校验。纯数字 12 位可通过。
- 为什么是问题：文档/文案与实际校验不一致，给用户虚假的策略承诺
- 建议：后端加复杂度 validator 或将文案改为「建议」并与策略配置对齐

**[FE-auth+admin-10] [Low/置信度:高] 登录非401错误双重提示**
- 位置：`frontend/src/modules/auth/pages/LoginPage.tsx:33-35 + frontend/src/api/client.ts:144-161`
- 问题：423 账户锁定 / 400 等非 401 登录失败时，拦截器先 antdMessage.error(同一文案)，LoginPage catch 又渲染同文案 Alert，同屏出现两条相同提示。
- 为什么是问题：拦截器全局 toast 与页面内 Alert 职责未划清
- 建议：登录请求标记跳过全局 toast，或仅保留页面 Alert

**[FE-auth+admin-11] [Low/置信度:高] 新旧密码相同校验不联动**
- 位置：`frontend/src/modules/auth/pages/ChangePasswordPage.tsx:115-122`
- 问题：new_password 的「不能与当前密码相同」validator 读取 old_password，但未声明 dependencies:['old_password']，先填新密码再改旧密码不会重新触发校验；{ max:128 } 规则无自定义 message，报错为 antd 默认含字段名英文路径文案。
- 为什么是问题：特定填写顺序下错误状态滞留或漏判，提示文案不友好
- 建议：加 dependencies:['old_password']，max 规则补中文 message

**[FE-auth+admin-12] [Low/置信度:中] 角色分配失败可能静默**
- 位置：`frontend/src/modules/admin/components/UserRoleAssignModal.tsx:25-31`
- 问题：mutation 无 onError。拦截器对 errorType=validation_failed 且带 details 的 4xx 不 toast（client.ts:157 注释明言依赖 caller 兜底），此时保存失败无任何提示，Modal 停留原状。
- 为什么是问题：client.ts 约定每个 mutation 应有 onError 兜底，此处缺失形成静默失败
- 建议：补 onError：applyFormErrors 失败则 message.error 兜底

**[FE-auth+admin-13] [Low/置信度:中] 编辑详情拉取竞态与未捕获异常**
- 位置：`frontend/src/modules/admin/pages/UserListPage.tsx:118-129`
- 问题：openEdit/openRoleAssign 先 await get 再开抽屉，无序号/AbortController：快速点击两行时后返回的旧响应覆盖 editingUser，抽屉显示错误用户。请求失败时 onClick 内 await 形成 unhandled rejection（仅拦截器 toast，抽屉不开）。
- 为什么是问题：管理员误在错误用户上保存资料/角色，属危险操作上下文错位
- 建议：用请求序号或改为受控 query，并 try/catch 包裹

**[FE-auth+admin-14] [Low/置信度:中] 实体编码筛选每键触发查询**
- 位置：`frontend/src/modules/admin/pages/SignatureListPage.tsx:228-238`
- 问题：「实体编码」Input 在 onChange 中直接 setFilters，每敲一个字符发一次列表请求并重置页码；同页其他文本筛选（签名人）均为 onPressEnter 提交，行为不一致。
- 为什么是问题：请求放大且交互不一致，慢网下感知卡顿
- 建议：改为 onPressEnter 提交或加 debounce，与签名人输入框对齐

**[FE-auth+admin-15] [Low/置信度:中] access token 持久化 localStorage**
- 位置：`frontend/src/stores/authStore.ts:49-54`
- 问题：zustand persist 将 access token 与用户信息（含 permissions）写入 localStorage（key=cmab-mdm-auth），XSS 时可被窃取；refresh token 已走 HttpOnly Cookie，access token 却长期落盘。
- 为什么是问题：与 RS256/HttpOnly 升级的安全姿态不一致，扩大 XSS 影响面
- 建议：token 改内存保存，刷新页面时靠 refresh cookie 静默换新

**[FE-auth+admin-16] [Low/置信度:低] 字典选项与后端枚举漂移**
- 位置：`frontend/src/modules/admin/pages/AuditLogPage.tsx:45-60 + PermissionListPage.tsx:20-28`
- 问题：ACTION_OPTIONS 含 READ/RESTORE 等后端疑似从不写入的动作（筛选恒为空）；PermissionListPage RESOURCE_COLORS 缺 equipment（EQP 域权限 Tag 落默认色）。均为硬编码字典未与后端同步。
- 为什么是问题：硬编码枚举随域扩展逐渐失真，筛选项形同虚设
- 建议：核对后端实际 action 集合裁剪选项；RESOURCE_COLORS 补 equipment

**[FE-auth+admin-17] [Low/置信度:低] UI 暴露内部字段名**
- 位置：`frontend/src/modules/admin/components/ResetPasswordResultModal.tsx:47`
- 问题：面向管理员的提示文案直接写「force_password_change=TRUE」数据库字段名；同样 RoleFormDrawer 提示含 role_code 实现细节。属调试式文案残留。
- 为什么是问题：内部实现细节泄漏到 UI，文案不专业
- 建议：改为业务语言：「用户首次登录将被强制修改密码」

### substances+projects+assets（11 条：Medium 3 / Low 8）

> 三域前端整体质量较高：状态机/枚举常量与文档注释基本对齐，xref 12 枚举两侧同步，电子签名弹窗含二次确认与字段校验。主要问题集中在 API 错误处理一致性（XrefEditor、SamenessCheckButton 缺 onError 导致失败静默）、列表筛选枚举两侧不同步、里程碑日期空值处理、若干文档文案与初始状态不符。无安全/数据损坏级问题，多为 Medium/Low。

**[FE-substances+p-01] [Medium/置信度:高] xref 增删改失败静默无提示**
- 位置：`frontend/src/modules/substances/components/XrefEditor.tsx:40-68`
- 问题：create/update/deleteMutation 均无 onError；全局 QueryClient(main.tsx) 也未配 MutationCache.onError。失败时无 toast，且 onOk 同步 resolve 后弹窗已关闭，用户完全无感知。
- 为什么是问题：增删改失败用户以为成功，造成数据误判。
- 建议：三个 mutation 补 onError 弹 message.error，参照同模块其他表格。

**[FE-substances+p-02] [Medium/置信度:中] 同一性判定失败静默**
- 位置：`frontend/src/modules/substances/components/SamenessCheckButton.tsx:50-63`
- 问题：checkSameness 的 mutation 只有 onSuccess，无 onError。接口报错时按钮 loading 复位但无任何提示，用户误以为「无匹配」从而重复登记物质。
- 为什么是问题：同一性判定是防重复登记关口，静默失败风险高。
- 建议：补 onError 提示判定失败，引导重试，禁止据此放心创建。

**[FE-substances+p-03] [Medium/置信度:中] 里程碑编辑空计划日期变Invalid**
- 位置：`frontend/src/modules/projects/components/MilestoneTable.tsx:129-139`
- 问题：openEdit 中 planned_date: dayjs(m.planned_date) 未判空（actual_date 已判空）。创建时 planned_date 非必填，若为 null，dayjs(null)=Invalid Date，提交 format 得 'Invalid Date' 发往后端。
- 为什么是问题：空计划日期里程碑一经编辑即写入脏日期。
- 建议：改为 m.planned_date ? dayjs(m.planned_date) : undefined。

**[FE-substances+p-04] [Low/置信度:高] 类型/状态筛选枚举两侧不同步**
- 位置：`frontend/src/modules/substances/pages/SubstanceListPage.tsx:164-188`
- 问题：类型下拉仅 5 项，缺 constants 中的 oligonucleotide、other；状态下拉缺 obsoleted。导致这些类型/状态的物质无法被筛出，且与 SUBSTANCE_TYPE_OPTIONS 不一致。
- 为什么是问题：用户无法筛选寡核苷酸/其他/已废弃物质。
- 建议：下拉直接复用 SUBSTANCE_TYPE_OPTIONS 并补 obsoleted 状态项。

**[FE-substances+p-05] [Low/置信度:高] 项目状态历史空提示文案错误**
- 位置：`frontend/src/modules/projects/pages/ProjectDetailPage.tsx:294`
- 问题：StatusHistoryPanel emptyHint 写「项目仍在初始 draft 状态」，但项目初始状态是 proposed（已提议），无 draft 状态。文案与实际状态机不符。
- 为什么是问题：误导用户对项目状态机的理解。
- 建议：改为「项目仍在初始 proposed（已提议）状态」。

**[FE-substances+p-06] [Low/置信度:中] 靶点筛选每次按键即发请求**
- 位置：`frontend/src/modules/substances/pages/SubstanceListPage.tsx:190-199`
- 问题：靶点 Input 用 onChange 直接 setFilters.target，每个字符触发一次 list 查询（q 字段则延后到回车）。同样问题见 ProjectListPage 的 program_name/parent_project_id。无防抖。
- 为什么是问题：高频无谓请求，交互不一致。
- 建议：改用 pending 状态+回车提交，或加 debounce，统一交互。

**[FE-substances+p-07] [Low/置信度:中] 保存校验失败产生未捕获拒绝**
- 位置：`frontend/src/modules/substances/pages/SubstanceEditPage.tsx:142-143`
- 问题：handleSubmit 为 Button onClick（非 Modal onOk），await form.validateFields() 失败时 promise 拒绝无 try/catch，产生 unhandledrejection。CreatePage 的 handleSubmit 有 try/catch 兜底，两处不一致。
- 为什么是问题：控制台报未处理拒绝，代码风格不一致。
- 建议：包 try/catch，校验失败时静默或提示检查必填项。

**[FE-substances+p-08] [Low/置信度:中] 资产状态机用 update 权限把关**
- 位置：`frontend/src/modules/assets/pages/AssetDetailPage.tsx:302-318`
- 问题：资产状态变更（含 GxP 关键 terminate）StatusActionsBar 用 permission=asset:update，而物质/项目同类动作用 substance:approve/project:approve。前端权限模型不一致，且 terminate 这类高风险动作仅按编辑权限放行。
- 为什么是问题：权限粒度不一致，关键动作把关偏弱。
- 建议：确认后端是否有 asset:approve；统一关键动作走审批级权限。

**[FE-substances+p-09] [Low/置信度:中] 项目/资产创建未trim输入**
- 位置：`frontend/src/modules/projects/pages/ProjectCreatePage.tsx:56-71`
- 问题：ProjectCreatePage、AssetCreatePage（onFinish: values as payload）直接提交原始值，未像 substance 页对名称/文本做 trim。前后空格会落库，造成名称重复判定与搜索不一致。
- 为什么是问题：脏空格数据，影响检索与唯一性。
- 建议：提交前对字符串字段统一 trim，空串转 undefined。

**[FE-substances+p-10] [Low/置信度:低] 创建页xref值缺255长度校验**
- 位置：`frontend/src/modules/substances/pages/SubstanceCreatePage.tsx:405-409`
- 问题：Step3 Form.List 的 xref_value 仅 required，无 max:255；而详情页 XrefEditor 对 xref_value 有 max:255。两处校验不一致，创建时可填超长值待后端拒绝。
- 为什么是问题：校验两侧不一致，体验差。
- 建议：创建页 xref_value 补 {max:255} 规则与编辑器对齐。

**[FE-substances+p-11] [Low/置信度:低] 弹窗onOk同步resolve提前关闭**
- 位置：`frontend/src/modules/substances/components/XrefEditor.tsx:164-175`
- 问题：onOk=handleSubmit 内 mutate 为 fire-and-forget，handleSubmit 立即 resolve，Modal 在请求完成前即关闭，confirmLoading 形同虚设。此模式在多个 Modal 表格中复用。
- 为什么是问题：loading 态无效，失败时弹窗已消失。
- 建议：handleSubmit 返回 mutateAsync 的 promise，让 Modal 等待结果。

### materials+equipments

（审查任务尚未完成，待补跑）

### dashboard+profile+common（16 条：High 2 / Medium 4 / Low 10）

> 共审查 7 个文件及关联的 client.ts/ChangePasswordPage/路由守卫/后端契约。ECharts 实例销毁与 resize 由 echarts-for-react 托管，无泄漏。最严重问题集中在改密链路：输错旧密码触发 401 被拦截器误判为会话失效强制登出；新密码长度前端 8 / 后端 12 不一致；强制改密守卫可绕过。仪表盘存在非法 CSS 颜色传入 ECharts、请求失败静默成空态、状态色双轨冲突等问题。共 16 项发现。

**[FE-dashboard+pr-01] [High/置信度:高] 改密输错旧密码被强制登出**
- 位置：`frontend/src/api/client.ts:122-134, frontend/src/modules/auth/pages/ChangePasswordPage.tsx:45-54`
- 问题：后端 OldPasswordWrongError 返回 401 + errorType=old_password_wrong（exceptions.py:105-109），但 axios 拦截器 401 分支只豁免 signature_invalid，old_password_wrong 落入会话失效分支：弹"登录已过期"、logout 并跳 /login。
- 为什么是问题：ChangePasswordPage onError 的字段级红框提示永远执行不到，用户仅输错旧密码就丢失整个会话。
- 建议：拦截器 401 豁免清单加入 old_password_wrong，交由调用方处理。
- 对抗复核：⏳ 复核未完成（中断），按原审查员置信度采信

**[FE-dashboard+pr-02] [High/置信度:高] 新密码最小长度前后端不一致**
- 位置：`frontend/src/modules/auth/pages/ChangePasswordPage.tsx:111-114`
- 问题：前端校验 min:8、tooltip 写"至少 8 位"；后端 ChangePasswordRequest new_password min_length=12（auth/schemas.py:70）。8-11 位密码前端放行后端 422 拒绝。
- 为什么是问题：用户通过前端校验仍提交失败，且只得到泛化错误提示，无字段定位。
- 建议：前端规则改为 min:12，tooltip 同步改为"至少 12 位"。
- 对抗复核：⏳ 复核未完成（中断），按原审查员置信度采信

**[FE-dashboard+pr-03] [Medium/置信度:高] 强制改密可绕过**
- 位置：`frontend/src/routes/ProtectedRoute.tsx:4-13, frontend/src/modules/auth/pages/LoginPage.tsx:25-27`
- 问题：force_password_change 仅在登录成功瞬间跳一次 /profile/password?required=1；ProtectedRoute 不检查 must_change_password，后端 permissions.py 也不拦截，用户可直接导航到任意页面继续用临时密码操作。
- 为什么是问题：页面 Alert 声称"必须设置新密码后才能正常使用系统"，实际可绕过，文案与行为不符。
- 建议：ProtectedRoute 检查 user.must_change_password 强制重定向，后端 get_current_user 同步拦截。

**[FE-dashboard+pr-04] [Medium/置信度:高] 饼/柱图传入非法 CSS 颜色**
- 位置：`frontend/src/modules/dashboard/pages/DashboardPage.tsx:199, frontend/src/modules/assets/constants.ts:23-33`
- 问题：optionsToColorMap(ASSET_PHASE_OPTIONS) 把 antd Tag 预设名（default/geekblue/success/error）直接传给 ECharts itemStyle.color，这些不是合法 CSS 颜色，对应柱子渲染为黑色或继承前一色。
- 为什么是问题：资产研发阶段柱图中发现/III期/已批准/已上市/已终止等条目颜色错误，图表误导。
- 建议：为仪表盘单独维护十六进制色映射，或在 colorOf 中校验非法值回退 FALLBACK_COLORS。

**[FE-dashboard+pr-05] [Medium/置信度:高] 密码复杂度文案与后端不符**
- 位置：`frontend/src/modules/auth/pages/ChangePasswordPage.tsx:81, backend/app/domains/auth/schemas.py:70`
- 问题：强制改密 Alert 声称"新密码…包含大小写、数字与符号"，但后端仅校验长度 12-128，无任何复杂度校验；前端表单也未校验复杂度。
- 为什么是问题：文档/UI 宣称的密码策略未实现，给合规审计留下文实不符记录。
- 建议：后端补复杂度 validator，或将文案改为仅"长度 ≥12 位"。

**[FE-dashboard+pr-06] [Medium/置信度:高] 仪表盘请求失败静默成空态**
- 位置：`frontend/src/modules/dashboard/pages/DashboardPage.tsx:54-62,82-113,251`
- 问题：summary/gantt 两个 useQuery 无 isError 处理：summary 失败时五张卡片显示 0、全部图表区整体消失；gantt 失败时退化为 [] 显示"暂无可显示的项目时间线"。仅依赖拦截器 toast。
- 为什么是问题：请求失败与真实空数据不可区分，统计值 0 具误导性。
- 建议：增加 isError 分支显示错误 Result/重试按钮；卡片错误时显示"—"而非 0。

**[FE-dashboard+pr-07] [Low/置信度:高] 项目状态颜色冲突且双轨**
- 位置：`frontend/src/modules/projects/constants.ts:84-91, frontend/src/modules/dashboard/components/ProjectGanttCard.tsx:9-16`
- 问题：PROJECT_STATUS_COLOR 中 active 与 completed 均为 'green'，项目状态饼图两扇区同色无法区分；同页甘特图另维护一套色（completed=#13C2C2），同状态两图异色。
- 为什么是问题：同一仪表盘内同一状态视觉编码冲突，读图易误判。
- 建议：统一一份十六进制状态色表，completed 与 active 分色，两图共用。

**[FE-dashboard+pr-08] [Low/置信度:高] 甘特状态标签重复且措辞不一**
- 位置：`frontend/src/modules/dashboard/components/ProjectGanttCard.tsx:18-25,131`
- 问题：STATUS_LABEL 与 PROJECT_STATUS_OPTIONS 重复定义且措辞不同（提案 vs 已提议、启动 vs 已立项）；里程碑 tooltip 直接输出英文原始 status 未翻译。
- 为什么是问题：同页饼图与甘特图对同一状态显示不同中文，里程碑状态裸英文。
- 建议：复用 PROJECT_STATUS_OPTIONS 生成标签；里程碑状态接 MILESTONE_STATUS_OPTIONS 映射。

**[FE-dashboard+pr-09] [Low/置信度:高] 趋势图注释仍写 4 域**
- 位置：`frontend/src/modules/dashboard/components/TrendLineCard.tsx:19, backend/app/api/v1/dashboard.py:3`
- 问题：TrendLineCard 注释"4 域日期对齐"、后端 dashboard.py docstring "4 域 totals"，实际自 EQP 接入后均为 5 域（substance/project/asset/material/equipment）。
- 为什么是问题：注释与代码不一致，误导后续维护。
- 建议：两处注释改为 5 域。

**[FE-dashboard+pr-10] [Low/置信度:高] 里程碑数据结构注释错误**
- 位置：`frontend/src/modules/dashboard/components/ProjectGanttCard.tsx:78-90`
- 问题：注释写 "[yIdx, planned_ts, actual_or_null, name]"，实际 push 的元组是 [idx, planned_ts, milestone_name, status]，第 3/4 位含义与注释不符。
- 为什么是问题：注释误导，后续按注释改 tooltip/encode 会取错列。
- 建议：更正注释为 [yIdx, ts, name, status]。

**[FE-dashboard+pr-11] [Low/置信度:高] PlaceholderPage 死代码**
- 位置：`frontend/src/modules/common/PlaceholderPage.tsx:7`
- 问题：全仓库无任何引用（路由已全部接真实页面），组件成为遗留死代码。
- 为什么是问题：增加维护噪音，subTitle"后续 Phase 上线"已过时。
- 建议：确认无规划用途后删除。

**[FE-dashboard+pr-12] [Low/置信度:中] 登录历史/签名失败显示空态**
- 位置：`frontend/src/modules/profile/pages/ProfilePage.tsx:147-153,241-247`
- 问题：LoginHistoryTab 与 MySignaturesTab 的 useQuery 未处理 isError，请求失败时表格显示"暂无登录记录/您尚未执行过电子签名"且 total=0，与 BasicInfoTab 有错误 Result 的处理不一致。
- 为什么是问题：失败被伪装成空数据，安全自查场景（异常 IP 排查）尤其误导。
- 建议：两个 Tab 增加 isError 分支显示错误 Result。

**[FE-dashboard+pr-13] [Low/置信度:中] 翻页时表格瞬间清空**
- 位置：`frontend/src/modules/profile/pages/ProfilePage.tsx:147,241`
- 问题：分页参数进 queryKey 但未配 placeholderData(keepPreviousData)，React Query v5 切页瞬间 data=undefined，表格闪空再加载。
- 为什么是问题：翻页体验抖动，pagination total 也瞬时归 0。
- 建议：useQuery 加 placeholderData: keepPreviousData。

**[FE-dashboard+pr-14] [Low/置信度:中] 改密成功定时器未清理**
- 位置：`frontend/src/modules/auth/pages/ChangePasswordPage.tsx:40-43`
- 问题：成功后 setTimeout 3 秒执行 logout+navigate，未在组件卸载时 clearTimeout；期间用户若已手动导航，仍会被卸载组件的 navigate 闭包二次跳转。
- 为什么是问题：卸载后调用 navigate 有 react-router 警告与意外跳转风险。
- 建议：useEffect 返回清理函数 clearTimeout，或直接立即登出。

**[FE-dashboard+pr-15] [Low/置信度:低] 物料图颜色与 Tag 色板偏差**
- 位置：`frontend/src/modules/dashboard/pages/DashboardPage.tsx:209, frontend/src/modules/materials/constants.ts:7-12`
- 问题：MATERIAL_TYPE_OPTIONS 的 color（blue/green/gold/purple）是给 antd Tag 用的预设名，传给 ECharts 时按 CSS 原色渲染（如 blue=#0000FF），与系统内 Tag 实际色（#1677ff 等）不一致。
- 为什么是问题：同一物料类型在列表 Tag 与仪表盘饼图颜色不同，视觉不统一。
- 建议：仪表盘使用独立十六进制色映射。

**[FE-dashboard+pr-16] [Low/置信度:低] substance_by_status 未展示**
- 位置：`frontend/src/api/types.ts:266, frontend/src/modules/dashboard/pages/DashboardPage.tsx:147-246`
- 问题：后端 summary 返回并由类型声明的 substance_by_status 分布，DashboardPage 未渲染任何对应卡片，是唯一被丢弃的分布维度。
- 为什么是问题：接口契约与 UI 呈现不对称，疑似遗漏而非有意裁剪。
- 建议：确认是否补"物质状态分布"卡片，或注释说明有意省略。

### api+stores+routes+shared

（审查任务尚未完成，待补跑）

---

## 4. 文档与代码匹配性审查发现

### API规范↔路由（10 条：Medium 4 / Low 6）

> 逐端点比对 V1.1 规范与实际路由（含 V1.2/V1.3 偏离说明登记项过滤）。大部分缺口（refresh/merge/advance-phase/batch、状态机扩展端点、expand 替代 GET 子资源、asset_substance 三段 DELETE/无 PUT 等）均已在偏离说明登记，不计为问题。剩余未登记差异 10 项：2 个本应"已登录"的端点实际无鉴权（system/info、lookups）；规范定义的 PUT /projects/{code}/assets/{asset_code} 与 GET /users/{username}/roles 未实现；POST /signatures 被刻意去除；audit-logs:export 同步 CSV 与规范 202 异步任务不符；以及若干查询参数命名/默认值差异。多为 Medium/Low。

**[MATCH-API规范↔路由-01] [Medium/置信度:高] system/info 缺鉴权**
- 位置：`docs/CMAB_MDM_Portal_API接口规范_V1_1.md:848 ↔ backend/app/api/v1/system.py:18-19`
- 问题：规范 §5.1.7 标注 GET /api/v1/system/info 权限「已登录」，但路由无 get_current_user 依赖，docstring 明示「无需鉴权」，且无全局认证中间件，实为公开端点。偏离说明未登记此降权。
- 为什么是问题：违反规范权限契约，暴露版本/环境/配置摘要
- 建议：加 Depends(get_current_user) 或在偏离说明登记为公开

**[MATCH-API规范↔路由-02] [Medium/置信度:高] lookups 缺鉴权**
- 位置：`docs/CMAB_MDM_Portal_API接口规范_V1_1.md:842 ↔ backend/app/api/v1/lookups.py:19-23`
- 问题：规范 §5.1.7/§8.4 标注 GET /api/v1/lookups/{type} 权限「已登录」，但路由无任何鉴权依赖（docstring「无需鉴权」），实为公开。偏离说明未登记。
- 为什么是问题：与规范权限契约不一致
- 建议：补登录依赖或在偏离说明登记公开决策

**[MATCH-API规范↔路由-03] [Medium/置信度:高] 缺 PUT 项目-资产关系端点**
- 位置：`docs/CMAB_MDM_Portal_API接口规范_V1_1.md:1519 ↔ backend/app/api/v1/projects.py:457-510`
- 问题：规范 §7.5「ref.project_asset 关系端点（V1.1 新增）」明确定义 PUT /api/v1/projects/{code}/assets/{asset_code} 修改 relation_type，但 projects.py 仅实现 GET/POST/DELETE，无 PUT。偏离说明 E6 只覆盖 asset_substance，未登记此项。
- 为什么是问题：文档承诺的可变属性更新能力缺失
- 建议：实现 PUT 端点或在偏离说明登记推迟

**[MATCH-API规范↔路由-04] [Medium/置信度:中] 审计导出语义不符**
- 位置：`docs/CMAB_MDM_Portal_API接口规范_V1_1.md:1836-1862 ↔ backend/app/api/v1/admin_audit.py:67-89`
- 问题：规范 §8.5 定义 POST /api/v1/audit-logs:export 为异步任务，返回 202 Accepted + task_id/result_url；代码为同步返回 text/csv（200，max 50000 行）。响应状态码与结构均不一致，偏离说明仅泛称「CSV 导出已落地」未登记此语义差异。
- 为什么是问题：状态码与响应体契约与文档冲突
- 建议：登记同步 CSV 实现为对 §8.5 的偏离

**[MATCH-API规范↔路由-05] [Low/置信度:中] 缺 GET 用户角色端点**
- 位置：`docs/CMAB_MDM_Portal_API接口规范_V1_1.md:732 ↔ backend/app/api/v1/admin_users.py`
- 问题：规范 §5.1.2 列 GET /api/v1/users/{username}/roles（用户角色），代码仅实现 PUT roles，无独立 GET roles（角色信息靠用户详情携带）。偏离说明称 API10 已落地但未注明此端点省略。
- 为什么是问题：文档列出的端点未实现
- 建议：补 GET roles 或在偏离说明注明用详情替代

**[MATCH-API规范↔路由-06] [Low/置信度:中] POST /signatures 被去除**
- 位置：`docs/CMAB_MDM_Portal_API接口规范_V1_1.md:846,1869 ↔ backend/app/api/v1/admin_audit.py:9-11`
- 问题：规范 §5.1.7/§8.6 定义 POST /api/v1/signatures（执行独立电子签名），代码注释以 Part 11 上下文绑定为由刻意不暴露。V1.3 偏离说明称「signatures 全局端点已落地」但未明确登记 POST 的删除。
- 为什么是问题：文档定义端点缺失，登记口径含糊
- 建议：在偏离说明明确登记 POST /signatures 去除及理由

**[MATCH-API规范↔路由-07] [Low/置信度:中] 审计查询参数差异**
- 位置：`docs/CMAB_MDM_Portal_API接口规范_V1_1.md:1793-1802 ↔ backend/app/api/v1/admin_audit.py:29-46`
- 问题：规范 §8.5 查询参数为 user / entity_schema / timestamp__gte / timestamp__lt / ip_address 等；代码用 username（非 user）、date_from/date_to（非 timestamp__*），且缺 entity_schema、ip_address，另增 q。命名与覆盖均与文档不一致，未登记。
- 为什么是问题：调用方按文档构造过滤参数会失效
- 建议：对齐参数名或在偏离说明登记差异

**[MATCH-API规范↔路由-08] [Low/置信度:中] 搜索 limit 默认值不符**
- 位置：`docs/CMAB_MDM_Portal_API接口规范_V1_1.md:1711 ↔ backend/app/api/v1/search.py:29`
- 问题：规范 §8.3 全局搜索 limit「每个类型返回数量，默认 10」，代码 Query(20, ge=1, le=50) 默认 20。默认值差异未登记。
- 为什么是问题：默认返回量与文档不符
- 建议：改默认 10 或登记调整

**[MATCH-API规范↔路由-09] [Low/置信度:中] 市场注册号多出写端点**
- 位置：`docs/CMAB_MDM_Portal_API接口规范_V1_1.md:800-801 ↔ backend/app/api/v1/assets.py:286-318`
- 问题：规范 §5.1.5 仅列 GET/POST /assets/{code}/market-ids，代码额外实现 PUT 与 DELETE /market-ids/{market_id_pk}（含软删 change_reason）。属代码有文档无，偏离说明未明确登记这两个写端点。
- 为什么是问题：代码端点超出文档定义
- 建议：在偏离说明登记为实施侧加强

**[MATCH-API规范↔路由-10] [Low/置信度:低] 项目-物质解绑路径多一段**
- 位置：`docs/CMAB_MDM_Portal_API接口规范_V1_1.md:784 ↔ backend/app/api/v1/projects.py:436-453`
- 问题：规范 §5.1.4 列 DELETE /projects/{code}/substances/{sub_code}（两段），代码因复合 PK 含 relation_type 实为三段 /substances/{substance_code}/{relation_type}。偏离说明 E6 仅登记 asset_substance 同类问题，未覆盖 project_substance。
- 为什么是问题：实际删除路径与文档不一致
- 建议：比照 E6 一并登记 project_substance 三段路径

### 数据模型↔ORM+迁移（5 条：High 1 / Medium 2 / Low 2）

> 逐表比对 V1.1 数据模型文档、各域 ORM 与 alembic 迁移到达的 schema。已登记于 V1.2/V1.3 偏离说明的变更（MM v2 四类型/15枚举、EQP 五分类、Float 精度 S5/S6/S7、material_batch deleted_by、ref deleted_by FK 等）均不计入。核心枚举（substance_xref 12 值、material_type 4 值、eqp category 5 类）ORM 与最新迁移一致。发现 1 处会导致写入失败的 ORM↔迁移空约束冲突，以及 4 处文档↔代码偏离（IP 类型/空、password_history 未实现、ORM 缺声明 FK/UNIQUE、约束命名不一致）。

**[MATCH-数据模型↔ORM+迁移-01] [High/置信度:高] milestone_type 空约束 ORM↔DB 冲突**
- 位置：`backend/app/domains/prs/models.py:144 ; backend/alembic/versions/2026_05_11_1700_0006_prs_init.py:117 ; 2026_05_11_2310_0014_prs_milestone_v2.py`
- 问题：迁移 0006 建 milestone_type 为 NOT NULL，0014 未改其可空性；但 ORM(models.py:144) 与 Pydantic(schemas.py:187 `milestone_type: MilestoneType|None=None`) 均可空，service:395 直接透传 None。创建里程碑省略 type 时 DB 抛 NOT NULL 违例。
- 为什么是问题：API 允许省略但 DB 拒绝，写入 500 失败
- 建议：迁移将该列改可空，或 schema 设为必填
- 对抗复核：⏳ 复核未完成（中断），按原审查员置信度采信

**[MATCH-数据模型↔ORM+迁移-02] [Medium/置信度:高] login_history.ip_address 偏离文档**
- 位置：`backend/alembic/versions/2026_05_11_1200_0001_init_schemas.py:174 ; backend/app/domains/auth/models.py:164`
- 问题：文档 §4.6 定义 ip_address 为 INET NOT NULL，而迁移与 ORM 均为 String(45) 且可空。类型族与非空约束双重偏离，登录来源 IP 可空，弱化审计留痕。
- 为什么是问题：合规审计 IP 可被绕过且类型不符
- 建议：回归 INET NOT NULL 或在偏离说明登记

**[MATCH-数据模型↔ORM+迁移-03] [Medium/置信度:高] password_history 表文档定义未实现**
- 位置：`docs/CMAB_MDM_Portal_数据模型设计文档_V1_1.md §4.6 ; backend (无对应 ORM/迁移)`
- 问题：文档 §4.6 定义 auth.password_history（防密码重用），且 system_config seed 设 password.history_count=5，但全部 ORM 与迁移中均无该表，防重用功能未落地，亦未在偏离说明登记。
- 为什么是问题：文档承诺的合规能力缺失且无登记
- 建议：实现该表与逻辑，或在偏离说明登记推迟

**[MATCH-数据模型↔ORM+迁移-04] [Low/置信度:高] ORM 缺声明 DB 已有 FK/UNIQUE**
- 位置：`backend/app/domains/srs/models.py:30-48,139-152 ; backend/app/domains/mm/models.py:60`
- 问题：substance.external_uuid 的 UNIQUE(迁移0028)、material.substance_id 的 FK(迁移0032)、substance_status_history.changed_by/e_signature_id 的 FK(文档§7.7) 在 DB/文档存在，但 ORM __table_args__/列未声明，ORM 元数据与实际 schema 漂移。
- 为什么是问题：create_all 或元数据校验与迁移不一致
- 建议：ORM 补齐对应 ForeignKey/UniqueConstraint

**[MATCH-数据模型↔ORM+迁移-05] [Low/置信度:高] 约束命名 文档与实现不一致**
- 位置：`backend/app/domains/srs/models.py:33-34 ; docs 数据模型文档 §7.2.2`
- 问题：文档 DDL 命名 uq_substance_code / uq_substance_internal / uq_substance_external_uuid；ORM 与迁移实际为 uq_substance_substance_code / uq_substance_internal_code 等双前缀名，与 §1.2.1 命名规范及文档 DDL 不符。
- 为什么是问题：按文档名编写的运维/校验脚本会失配
- 建议：统一命名或在文档登记实际命名

### 偏离说明V1.3↔代码

（审查任务尚未完成，待补跑）

### 前端↔API

（审查任务尚未完成，待补跑）

---

## 5. 测试覆盖缺口

### be-tests（15 条：High 1 / Medium 6 / Low 8）

> 33 个测试文件域覆盖较全（auth/audit/srs/prs/ars/mm/eqp/search/dashboard/ref-link 均有），但存在若干隐患：部分测试硬编码 localhost:8000 绕过 run_tests.sh 搭建的隔离 test DB（8001），直接打/污染 dev 服务；限流测试是"假测试"（名为测 42901 实际从未触发限流）；多处条件断言/死变量导致空跑通过；auth 安全用例改全局 admin 状态且失败时不回滚；缺并发唯一性竞态、reference 数据、asset/project 幂等等覆盖。整体功能路径扎实但隔离性与断言强度有缺口。

**[TEST-be-tests-01] [High/置信度:高] 硬编码 8000 绕过隔离 test DB**
- 位置：`backend/tests/test_smoke.py:8 / test_rate_limit.py:14 / test_refresh_token.py:13`
- 问题：这三个文件模块级 BASE_URL='http://localhost:8000'，用自建 AsyncClient 直打 dev 服务；run_tests.sh 把测试服务起在 8001 并经 TEST_BASE_URL 隔离 cmab_test，这些用例完全绕过隔离，读写/污染 dev 库或在 dev 未起时失败。
- 为什么是问题：破坏 test DB 隔离，污染 dev 数据并使结果不确定
- 建议：改用 conftest 的 BASE_URL/http_client fixture，统一读 TEST_BASE_URL
- 对抗复核：⏳ 复核未完成（中断），按原审查员置信度采信

**[TEST-be-tests-02] [Medium/置信度:高] 限流 42901 是假测试**
- 位置：`backend/tests/test_rate_limit.py:28-44`
- 问题：test_login_rate_limit_hit_returns_42901 名称声称验证触发限流返回 42901+Retry-After，实际只发 1 次登录、仅断言 header 存在；docstring 自承'跳过'。限流实际触发路径完全未被测试。
- 为什么是问题：核心安全功能（限流拒绝）零覆盖却伪装已测
- 建议：改名或用低配额/IP 模拟真正打爆并断言 42901

**[TEST-be-tests-03] [Medium/置信度:高] 末位管理员保护条件断言空跑**
- 位置：`backend/tests/test_admin_users.py:259-278`
- 问题：test_cannot_remove_last_sys_admin 整个断言体包在 if rows[0]['c']==1 内；若并发/污染导致存在 >1 个活跃 SYS_ADMIN，断言全部跳过、测试无断言通过，'不可移除末位管理员'这一关键合规逻辑未被验证。
- 为什么是问题：条件断言使关键越权保护可能从未真正执行
- 建议：先确定性造出唯一 SYS_ADMIN 场景再无条件断言

**[TEST-be-tests-04] [Medium/置信度:高] 日期过滤死变量+正向未测**
- 位置：`backend/tests/test_admin_audit.py:104-124`
- 问题：test_filter_by_date_range 第 109 行算出 date_from 后从未使用；只测了 future date_from=0、past date_to=0 两个负向（应为空）场景，从未断言'有效区间包含刚建记录'这一正向语义，过滤的包含行为未被覆盖。
- 为什么是问题：死变量+只测空集，过滤正确性实质未验证
- 建议：补一条用近期 date_from 断言命中记录的正向用例

**[TEST-be-tests-05] [Medium/置信度:中] 改写全局 admin 状态且失败不回滚**
- 位置：`backend/tests/test_auth_security.py:176-227`
- 问题：test_signature_failure_persists_audit_independently 让 admin 的 failed_login_count++，仅在用例结尾(225-227)重置 status/locked_at；若中途任一 assert 失败，重置不执行，admin 可能被锁，导致后续所有依赖 admin_client 的用例级联 423 失败。
- 为什么是问题：共享账户副作用+无 teardown 保障，故障会扩散
- 建议：改用 throwaway 用户或 try/finally 保证状态复位

**[TEST-be-tests-06] [Medium/置信度:中] 缺并发唯一性竞态覆盖**
- 位置：`backend/tests/（全套）`
- 问题：所有重复键用例（internal_code/material_code/batch_number/market_id/团队角色等）均为顺序两次调用，依赖 unique_suffix 避免真实冲突；无任何并发注册同一主数据的竞态测试，DB 层唯一约束在并发下的兜底（应用层 pre-check 之外）未被验证。
- 为什么是问题：生物制药 MDM 关键风险点（并发注册重码）零覆盖
- 建议：加 asyncio.gather 并发 POST 同 code，断言恰一成功一 409

**[TEST-be-tests-07] [Medium/置信度:中] 测试体内直连 AsyncSessionLocal 违约**
- 位置：`backend/tests/test_signature.py:187-216`
- 问题：test_signature_reason_independent_from_comment 在 pytest 进程内 import 并使用 AsyncSessionLocal 读 ESignature，而 conftest/test_refresh_token 明确记载该用法触发 BaseHTTPMiddleware+asyncpg 跨 event-loop 冲突。属违反已知约束，存在 teardown 报错/偶发失败风险。
- 为什么是问题：违反项目记录的跨 loop 约束，易偶发 flaky
- 建议：改经 HTTP（/me/signatures 或 audit API）断言，避免进程内 session

**[TEST-be-tests-08] [Low/置信度:高] 幂等仅覆盖 2/4 端点**
- 位置：`backend/tests/test_idempotency.py:1-6`
- 问题：文件 docstring 称'4 个 POST 创建端点接入'，实际只测 material 与 substance；asset、project 的 Idempotency-Key 行为（含 per-user 作用域、同 key 异 body 409）未覆盖。
- 为什么是问题：声称范围与实测不符，半数端点幂等未验证
- 建议：补 asset/project 幂等用例或修正 docstring 范围

**[TEST-be-tests-09] [Low/置信度:高] 注释与代码不符**
- 位置：`backend/tests/test_rate_limit.py:48-54 / test_dashboard.py:5`
- 问题：test_metrics 注释称'连发 50 次'但循环为 range(5)；test_dashboard 模块 docstring 称'8 个分布'但实际断言 10 个分布键。注释失真易误导维护者对覆盖强度的判断。
- 为什么是问题：文档与实现漂移，降低可信度
- 建议：修正注释数量与实际循环/断言一致

**[TEST-be-tests-10] [Low/置信度:中] reference/lookup 域缺独立测试**
- 位置：`backend/tests/test_substance_crud.py:325-351`
- 问题：reference 数据（lookups、system/info、config_summary）仅在 substance_crud 内夹带 2 个浅测，且只断言含某些值/排序；无独立 ref 测试文件，无对 is_sensitive 过滤、未知 lookup type、空结果等边界覆盖。
- 为什么是问题：参考数据域覆盖薄弱，边界/敏感字段过滤未测
- 建议：补 test_ref_lookups.py 覆盖未知 type/敏感字段过滤

**[TEST-be-tests-11] [Low/置信度:中] 越权测试用错 body 误中靶心**
- 位置：`backend/tests/test_asset_state_machine.py:148-156`
- 问题：test_terminate_requires_sign_permission 发送扁平 {change_reason, password} 而非端点要求的 {comment, signature}；它断言 403 仅因权限依赖在路由层先于 body 校验执行。一旦校验顺序变化将得 400/422，且并未真正验证'签名流程需 sign 权限'。
- 为什么是问题：依赖校验顺序的脆弱断言，body schema 已错
- 建议：用正确 signature body，确保 403 来自权限而非畸形请求

**[TEST-be-tests-12] [Low/置信度:中] total==len(items) 断言不健壮**
- 位置：`backend/tests/test_global_search.py:304-305`
- 问题：test_search_response_structure 断言 group['total']==len(group['items'])，在 q='SUB-' limit=5 下，一旦命中数超过 limit，total（总数）将不等于截断后的 items 长度。当前仅因隔离库 seed 数据少而通过，语义脆弱。
- 为什么是问题：分页/截断场景下该等式会假阴性失败
- 建议：区分总数与返回数，或断言 len(items)<=limit 且<=total

**[TEST-be-tests-13] [Low/置信度:中] 硬编码 user_id=2 脆弱依赖**
- 位置：`backend/tests/test_project_milestone_team.py:131-139`
- 问题：团队用例多处硬编码 user_id:2 作为存在的 seed 用户；依赖 seed_data 用户主键顺序，一旦 seed 调整或加 --demo 数据漂移，主键变化会使这些用例误判。应按 username 解析或动态创建用户。
- 为什么是问题：测试依赖隐式 seed 主键，seed 变更即脆断
- 建议：经用户 API 动态建用户取其 user_id 再加入团队

**[TEST-be-tests-14] [Low/置信度:中] 默认指向 dev 库的脚枪**
- 位置：`backend/tests/conftest.py:36-42`
- 问题：pg_connect_kwargs 在未设 TEST_DB 时默认 database=cmab_mdm（dev）。直接 pytest（不经 run_tests.sh）时，test_auth_security/test_admin_users 等直连 DB 的写操作（建用户、改 admin 状态）会落到 dev 库，污染真实数据。
- 为什么是问题：绕过 run_tests.sh 直跑即写 dev 库
- 建议：无 TEST_DB 时 fail-fast 或默认指向非 dev 测试库

**[TEST-be-tests-15] [Low/置信度:中] 签名体含被忽略的 meaning 字段**
- 位置：`backend/tests/test_material_substance_link.py:24-33`
- 问题：_drive_substance_to 在 signature 内传入 'meaning' 字段，而其余用例的签名仅用 password+reason；该字段疑似被 schema 忽略，测试不会因其错误值报错，掩盖了潜在的签名语义校验缺失。
- 为什么是问题：无效字段静默被吞，签名语义校验未被验证
- 建议：确认 schema 是否应校验 meaning；移除或改为断言其落库

