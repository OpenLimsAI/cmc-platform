# 讨论总结：MDM 靶点/分子域 + 外部数据源架构（2026-08-17）

## 一、架构总原则（本次定调）

**MDM 管"分子是什么、靶点是什么"（稳定主属性）；cmc_analytics 管"监管状态、市场状态"（随时间变化）；INN / MDM 编码做桥。两边做小做薄，不合成大项目。**

## 二、MDM 靶点域 —— 已定决策（7 项全部拍板）

1. **Schema 命名**：主表放新 schema `tgt`，关联表 `ref.molecule_target`。不在 cmab_mdm 里用 `dim`/`bridge`（与总纲 cmc_analytics.dim 语义冲突）
2. **分子域复用 `srs.substance`**，不另建分子表；ChEMBL ID / INN / 商品名存 `srs.substance_xref`
3. **ADC 载荷靶点保留**，bridge 表加 `relation_role`（antibody_target / payload_target / other）
4. **审核流走轻档**（对标 MM/EQP：CRUD + publish + change_reason，无电签无状态机）
5. **外部原始 JSON 拆独立快照表**（append-only，不挂审计触发器），主表只留裁剪后业务字段
6. **枚举按现状三份硬编码**（PG CHECK + Pydantic Literal + 前端常量），不动字典接口
7. **一期再砍范围**：前端预填向导不做。录入量小（靶点 50–100 条），用 PoC 脚本离线批量出预填 JSON → 人工在普通表单核对保存

## 三、数据结构（最终版）

- `tgt.target`：target_code（TGT-000001 取号）/ target_name / uniprot_id（锚点，唯一）/ target_type（枚举5：受体/配体·细胞因子/表面抗原/酶/其他）/ target_location（枚举4：膜型/可溶型/两者都有/胞内）
- `ref.molecule_target`：molecule_id→srs.substance / target_id / moa / relation_role / 表位domain / needs_confirm
- 快照表：`target_source_snapshot(target_id, source, fetched_at, source_version, payload)`

## 四、PoC 关键实测结论（正式实现必须遵守）

- UniProt 号取自 ChEMBL `target_components[].accession`（顶层 cross_references 是空的）
- bridge 记录 = mechanism × target_components 笛卡尔展开（不是按 mechanism 条数）：IL-23 类是 PROTEIN COMPLEX（会带出 p40，需人工勾选结合亚基，UNLIKELY 默认灰掉）；emicizumab 是 1 mechanism + SELECTIVITY GROUP；T-DXd 是 2 mechanism（HER2 + TOP1）
- 查重必须同时匹配主 + 次级 accession（secondaryAccessions），否则漏查重
- 分子搜索"宁可让人选也不猜"：pref_name 精确 → 同义词精确 → NEEDS_MANUAL_PICK
- target_type / target_location 只是启发式建议值，UI 强制人工确认并显示依据
- ChEMBL CC BY-SA 3.0：内部使用无碍，序列/数据对外输出时注意署名，快照表留来源标注

## 五、本文档的归档与生效方式

- 本文档放 `docs/decisions/2026-08-17-target-domain.md`（无 docs 目录则新建），不放项目根目录
- **必须在项目 CLAUDE.md 加一行指针**："靶点域设计决策见 docs/decisions/2026-08-17-target-domain.md，开发前必读"——否则 Claude Code 不会自动读到本文档
- PoC 三份产物（prefill_target.py 所在 `poc/target_prefill/` 目录、test_report.md、compatibility_assessment.md）一并归档到 docs/decisions/ 旁，开发时与本文档共同作为设计输入

## 六、Linux 上机验证流程（开发前置，按顺序执行，给 Claude Code 的指令）

**Step 1：出网验证（决定一切，不通则停）**

以后端 systemd 服务的身份验证，不是登录 shell：

```bash
sudo -u <后端服务用户> env -i curl -sS https://www.ebi.ac.uk/chembl/api/data/status.json
```

- 要点：服务进程不继承交互 shell 的代理变量，必须清空环境（`env -i`）模拟服务环境；若失败再带上 `cmab-backend.service` 的 EnvironmentFile 中的代理变量重试，确认是"必须走代理"还是"完全不通"
- 通（直连或代理）→ 继续 Step 2；完全不通 → 停止开发，先回报，启动瘦镜像 Provider 方案（+5–8 人日）

**Step 2：PoC 脚本 Linux 复跑**

```bash
python3 poc/target_prefill/prefill_target.py
```

- 此前仅在 Mac 直连验证过。注意：脚本当时显式绕开了 Mac 的 ClashX 代理；Linux 上若 Step 1 证明走代理，需允许 trust_env（正式实现 httpx 同理，方向与 Mac 相反）
- 预期：5 用例结果与 test_report.md 一致（14 次外调全 200）
- Step 1 + Step 2 都通过 → 按第七节范围开工

## 七、一期开发范围与改动边界（给 Claude Code 的约束）

**改动性质：几乎纯增量，现有字段一律不动。**

- 全新对象：schema `tgt`（target 表 + 快照表 + 取号/updated_at/审计触发器）、`ref.molecule_target`、`domains/target/*`、`api/v1/targets.py`、批量预填脚本（移植 PoC 逻辑）、`shared/http_client.py`、测试文件
- 允许触碰的现有文件仅四处，且均为"注册点"非"改逻辑"：`api/v1/__init__.py`（加一行路由注册）、权限种子（写幂等定向 INSERT 脚本，禁止重跑 make seed）、`01-init.sql`（search_path 补一行）、`alembic/env.py`（白名单补一行，顺手补 eqp）
- **明确禁止**：改 `srs.substance` 任何 DDL（只往 `substance_xref` 插数据行）；动旧的 `target`/`target_type` 自由文本列（存量为 0，原样保留，二期处理）；引入任务队列等新基础设施
- 回滚面：drop schema `tgt` + `ref.molecule_target` 两处即可，现有功能零影响
- 测试约束：外部调用一律 MockTransport/respx 打桩，测试不许真出网

## 八、待办（按优先级）

1. **【前置，明日】** 第六节 Step 1 + Step 2 上机验证
2. 一期开发（Claude Code，预计占用本人 2–3 个工作日碎片时间）：迁移（tgt 表 + bridge + 快照表 + 取号触发器）→ 后端 CRUD + publish → 基础前端页 → 批量预填脚本（移植 PoC）→ 测试
3. 二期（后续）：SRS 联动回填、bridge 前端面板、搜索/仪表盘接入、旧自由文本列过渡
4. 独立小任务（1–2 天，与上面并行）：cmc_analytics 建 `ref.fda_purple_book` + `ref.ema_products` 两张参考表 + 月度导入脚本（Purple Book CSV / EMA Excel），用 INN 关联 MDM 编码，服务 biosimilar 立项筛选（专营权到期扫描）

## 九、收益定位（防止跑偏）

省人工录入不是本项目收益（手工录完全部也就 2–3 天）。真实收益：消灭 srs.substance 的 target 自由文本列、建立 uniprot_id 锚点让靶点数据可与 FTO/竞品/立项分析 join、趁 SRS 存量为零零成本切换规范。

## 参考文件

- PoC 产物：`poc/target_prefill/`（脚本 / test_report.md / compatibility_assessment.md）
- 工作量基线：传统口径一期 8–10 人日，Claude Code 实际瓶颈是决策与 review 时间

## 补充（2026-08-18，一期落地后）

- 一期已上线（migration 0050，commit 8d30ed3）；Linux 出网验证：直连、无需代理；ChEMBL 官方 REST 当日故障，Step 2 待其恢复补跑。
- 应负责人要求增加"新建靶点页按 UniProt accession 一键拉取"（`GET /targets/prefill/uniprot`）：只调 UniProt 单条、不落库；保存时同步存 UniProt 快照。这不是决策 7 里砍掉的"INN 全链路预填向导"（那条仍留二期），只是减少手填字段。
- **2026-08-18 负责人二次决策：废除自定义"靶点类型 5 选 1 / 靶点定位 4 选 1"（不是标准分类），改为 UniProt 标准字段（migration 0051）**：
  keywords（KW 编号+类别，多值）、subcellular_locations（SL 编号+拓扑，多值）、cd_antigen_names、gene_synonyms、ec_numbers、
  domains、entry_type、protein_existence、tax_id、sequence_length/mol_weight/sequence_md5、uniprot_entry_version/fetched_at。
  全部由「拉取」自动带出、人不手填；详情页可「从 UniProt 重新拉取」整体覆盖并追加快照。第三节的 target_type/target_location 与第 6 条"枚举硬编码"对靶点主表不再适用。
