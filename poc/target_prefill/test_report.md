# 靶点/分子域自动预填 PoC —— 功能验证报告

- 运行日期：2026-08-17（UTC 13:30–13:32），Mac 本机直连（显式绕开 ClashX 代理），Python 3.9 标准库
- 脚本：`poc/target_prefill/prefill_target.py`；模拟查重表：`poc/target_prefill/mock_dim_target.json`（预置 Q9NPF7 = IL-23A）
- 产物：`poc/target_prefill/output/<inn>/`：`01_chembl_molecule_search.json` / `02_chembl_mechanism.json` / `03_chembl_target_<id>.json` / `05_uniprot_<acc>.json`（原始响应）+ `prefill_form.json`（预填表单）+ `run_result.json`（每步提取结果 + HTTP 日志）；总表 `output/run_summary.json`
- 复跑：`python3 poc/target_prefill/prefill_target.py`（全部 5 例）或追加 INN 参数

## 0. 结论先行

| # | INN | 预期分支 | 实际结果 | 结论 |
|---|---|---|---|---|
| 1 | guselkumab | 单靶单抗，Q9NPF7 命中查重 → 只建关联 | **混合分支**：ChEMBL 把 IL-23 建模为 PROTEIN COMPLEX（p19 = Q9NPF7 + p40 = P29460）。Q9NPF7 命中 → 只建 bridge（`HIT_EXISTING_TARGET_ONLY_LINK`）✅；P29460 未命中 → 走 UniProt 回填出一条"新靶点"，脚本用 `binding_site_comment`（"Alpha (p19) subunit is binding site"）把 P29460 标为 `UNLIKELY` 结合亚基 | ✅ 命中分支验证通过；⚠️ 揭示"单靶点"假设在 ChEMBL 粒度下不成立（见 §2.1） |
| 2 | pembrolizumab | 单靶，未命中 → 完整 UniProt 回填 | Q15116（PD-1）SINGLE PROTEIN，1 条 mechanism，1 条新靶点预填 + 1 条 bridge，无需人工确认标记 | ✅ 全链路跑通 |
| 3 | emicizumab | 双特异性 → 多条 mechanism/target | ChEMBL 只有 **1 条** mechanism，但 target 类型为 **SELECTIVITY GROUP**（FIX + FX 两个组分）→ 拆成 2 条新靶点 + 2 条 bridge，均标 `needs_manual_confirm` | ✅ 多靶点处理通过；⚠️ "多条 mechanism"预期不成立，双抗在 ChEMBL 里可能是 1 条 mechanism + 组合 target（见 §2.2） |
| 4 | trastuzumab deruxtecan | ADC → 观察返回结构 | molecule_type = `Antibody drug conjugate`；**2 条 mechanism**：HER2 BINDING AGENT（抗体端）+ TOP1 INHIBITOR（载荷端）。脚本按 UniProt 定位把 TOP1 标 `PAYLOAD_TARGET`、HER2 标 `ANTIBODY_TARGET` | ✅ 结构可解析；⚠️ 载荷靶点是否录 bridge 是业务决策（见 §2.3） |
| 5 | notarealinnxyz | 无效 INN → 拦截 | ChEMBL 返回 HTTP 200、`total_count=0` → `REJECTED_NO_MOLECULE`，给出用户提示，不再往下调 | ✅ 拦截通过 |

- **网络**：14 次外部 GET 全部 HTTP 200，单次 1.4–4.8 s（Mac→海外直连），单用例 4–6 次调用约 8–20 s。0 次重试。
- **一处与任务描述不符（重要）**：ChEMBL `/target/{id}` 顶层 `cross_references` 在 5 个 target 上**全部为空数组**；UniProt accession 实际在 `target_components[].accession`（以及 `target_component_xrefs[xref_src_db=UniProt]`，后者还带次级 accession）。正式实现按此取值。

## 1. 逐用例记录

### 1.1 guselkumab —— 混合：命中只建关联 + 复合体另一亚基走回填

| 步骤 | HTTP | 耗时 | URL |
|---|---|---|---|
| 1 molecule/search | 200 | 2.25s | https://www.ebi.ac.uk/chembl/api/data/molecule/search.json?q=guselkumab&limit=20 |
| 2 mechanism | 200 | 3.27s | https://www.ebi.ac.uk/chembl/api/data/mechanism.json?molecule_chembl_id=CHEMBL2364648 |
| 3 target | 200 | 2.41s | https://www.ebi.ac.uk/chembl/api/data/target/CHEMBL2364154.json |
| 4 查重 | — | — | Q9NPF7 → 命中 TGT-000001；P29460 → 未命中 |
| 5 uniprot | 200 | 2.83s | https://rest.uniprot.org/uniprotkb/P29460.json（仅未命中者） |

关键提取：
- 分子：CHEMBL2364648 / GUSELKUMAB / Antibody / max_phase 4 / 首批 2017 / 研发代号 CNTO 1959 / 商品名 Tremfya / biotherapeutic 含 HC(446 aa)+LC(217 aa) 序列
- mechanism（1 条）：`Interleukin-23 inhibitor` / INHIBITOR / target CHEMBL2364154 / `binding_site_comment = "Alpha (p19) subunit is binding site"`
- target：Interleukin-23 / **PROTEIN COMPLEX** / 组分 P29460(IL12B, p40) + Q9NPF7(IL23A, p19)
- 预填：`targets_existing_hit=[TGT-000001]`；`targets_new=[P29460 IL-12 subunit beta, 建议 配体·细胞因子 / 可溶型]`；bridge 2 条（Q9NPF7→TGT-000001 `LIKELY` 结合亚基；P29460→`<NEW>` `UNLIKELY`），两条均 `needs_manual_confirm=true`

### 1.2 pembrolizumab —— 完整回填分支

| 步骤 | HTTP | 耗时 | URL |
|---|---|---|---|
| 1 | 200 | 2.29s | …/molecule/search.json?q=pembrolizumab&limit=20 |
| 2 | 200 | 2.21s | …/mechanism.json?molecule_chembl_id=CHEMBL3137343 |
| 3 | 200 | 1.47s | …/target/CHEMBL3307223.json |
| 4 | — | — | Q15116 未命中 |
| 5 | 200 | 2.13s | https://rest.uniprot.org/uniprotkb/Q15116.json |

- 分子：CHEMBL3137343 / PEMBROLIZUMAB / Antibody / phase 4 / 2014 / MK-3475, SCH-900475 / Keytruda
- mechanism：`Programmed cell death protein 1 inhibitor` / INHIBITOR / CHEMBL3307223 (SINGLE PROTEIN)
- UniProt Q15116：PDCD1 / 288 aa / `cdAntigenNames=[CD279]` / 定位 Cell membrane, Single-pass type I
- 预填 dim.target：target_name=Programmed cell death protein 1，uniprot_id=Q15116，**target_type=表面抗原**（依据 cdAntigenNames；UniProt 该条目 Molecular-function 关键词为空，靠 Receptor 关键词判不出），**target_location=膜型**；bridge 1 条，无需强制确认

### 1.3 emicizumab —— 双抗：1 条 mechanism，SELECTIVITY GROUP 拆 2 靶

| 步骤 | HTTP | 耗时 | URL |
|---|---|---|---|
| 1 | 200 | 3.73s | …/molecule/search.json?q=emicizumab&limit=20 |
| 2 | 200 | 1.45s | …/mechanism.json?molecule_chembl_id=CHEMBL3833393 |
| 3 | 200 | 1.62s | …/target/CHEMBL2111424.json |
| 5 | 200 / 200 | 3.42s / 2.71s | https://rest.uniprot.org/uniprotkb/P00740.json、…/P00742.json |

- 分子：CHEMBL3833393 / EMICIZUMAB / Antibody / phase 4 / 2017 / ACE-910 / Hemlibra；biotherapeutic 组分明确列出 "Heavy chain: anti-FX" 与 "Heavy chain: anti-FIXa"（双抗的臂信息在这里，可作为 bridge 的 domain/臂 提示来源）
- mechanism（**仅 1 条**）：`Coagulation factor IX and X other` / action_type **OTHER** / target CHEMBL2111424
- target：`Coagulation factor IX and X` / **SELECTIVITY GROUP** / 组分 P00740(F9) + P00742(F10)
- 预填：2 条新靶点（FIX、FX 均建议 酶 / 可溶型）+ 2 条 bridge（moa 都是 "…other"，`needs_manual_confirm=true`）

### 1.4 trastuzumab deruxtecan —— ADC：2 条 mechanism（抗体端 + 载荷端）

| 步骤 | HTTP | 耗时 | URL |
|---|---|---|---|
| 1 | 200 | 3.54s | …/molecule/search.json?q=trastuzumab+deruxtecan&limit=20（total_count=18，pref_name 精确匹配选中 CHEMBL4297844，score 74；次高 TRASTUZUMAB 37） |
| 2 | 200 | 3.28s | …/mechanism.json?molecule_chembl_id=CHEMBL4297844 |
| 3 | 200 / 200 | 1.88s / 3.85s | …/target/CHEMBL1824.json、…/target/CHEMBL1781.json |
| 5 | 200 / 200 | 3.65s / 4.78s | https://rest.uniprot.org/uniprotkb/P04626.json、…/P11387.json |

- 分子：CHEMBL4297844 / TRASTUZUMAB DERUXTECAN / **molecule_type = "Antibody drug conjugate"** / phase 4 / 2019 / DS-8201 / Enhertu / usan_stem `-mab; -mab; -tecan`；biotherapeutic.biocomponents 里除 HC/LC 外还有 "Disulfide bridges"、"Glycosylation sites (N)" 等非蛋白组分（component_type=null）——ADC 的 linker/payload 结构不在 mechanism 里而散在 biotherapeutic
- mechanism：① `Receptor protein-tyrosine kinase erbB-2 binding agent` / **BINDING AGENT** / CHEMBL1824；② `DNA topoisomerase I inhibitor` / INHIBITOR / CHEMBL1781
- 预填：HER2 P04626（受体 / 膜型，`adc_role_hint=ANTIBODY_TARGET`）；TOP1 P11387（酶 / 胞内，`adc_role_hint=PAYLOAD_TARGET`）；2 条 bridge 均需人工确认

### 1.5 notarealinnxyz —— 拦截

- `…/molecule/search.json?q=notarealinnxyz&limit=20` → HTTP 200，`page_meta.total_count=0`，`molecules=[]`
- 脚本输出：`outcome=REJECTED_NO_MOLECULE`，`user_message="ChEMBL 查无「notarealinnxyz」（total_count=0）。请检查 INN 拼写；若为新分子/未收录，请走人工录入。"`，未再发出任何后续请求（http_calls 仅 1 条）

## 2. 发现的问题 / 需要业务拍板的点

### 2.1 "一个抗体一个 UniProt" 在 ChEMBL 粒度下不成立（guselkumab）
ChEMBL 用 `target_type` 区分 SINGLE PROTEIN / PROTEIN COMPLEX / SELECTIVITY GROUP / PROTEIN FAMILY 等。IL-23 抑制剂类（guselkumab/risankizumab/tildrakizumab）在 ChEMBL 里都挂在 PROTEIN COMPLEX，会同时带出 p19 与 p40。以 `uniprot_id` 为 dim.target 锚点时，**必须由人从组分里选结合亚基**。脚本已用 `binding_site_comment` 给 LIKELY/UNLIKELY 提示，但该字段并非每条 mechanism 都有（本次 5 例仅 guselkumab 有）。
→ 建议：预填表单里 PROTEIN COMPLEX 的每个组分默认"未勾选"，UNLIKELY 的默认灰掉，由审核人勾选。

### 2.2 双抗不一定是"多条 mechanism"（emicizumab）
emicizumab 是 1 条 mechanism + SELECTIVITY GROUP。而 ADC（trastuzumab deruxtecan）反而是 2 条 mechanism。所以"多条 bridge"应从 **mechanism × target_components 的笛卡尔展开** 得到，而不是只看 mechanism 条数（脚本已按此实现）。另外 emicizumab 的 action_type=OTHER、moa="…other"，MoA 字段需人工改写。

### 2.3 ADC 载荷靶点要不要进 bridge（业务决策）
trastuzumab deruxtecan 会带出 TOP1（胞内酶，载荷 DXd 的靶点）。若 `bridge.molecule_target` 定义为"抗体结合靶点"，则 TOP1 不应入表；若定义为"分子的全部 MoA 靶点"，则应入。脚本用 UniProt 定位=胞内 做了 `PAYLOAD_TARGET` 提示，仅供参考。**建议在 bridge 上加一列 `relation_role`（antibody_target / payload_target / other）** 而不是丢弃。

### 2.4 target_type / target_location 只能给"建议值"
两个枚举都是启发式：
- target_type：Cytokine/Growth factor 关键词→配体·细胞因子；Receptor 关键词→受体；`cdAntigenNames`（CD 号）→表面抗原；酶类关键词或 EC 号→酶；否则其他。5 例 6 个靶点结果：IL-12B 配体·细胞因子 ✅、PD-1 表面抗原 ✅（PD-1 也可视为受体，业务定）、FIX/FX 酶 ✅、HER2 受体 ✅（HER2 有 CD340，但 Receptor 规则优先）、TOP1 酶 ✅。
- target_location：SUBCELLULAR LOCATION 含 membrane→膜型；Secreted/extracellular→可溶型；同时含→两者都有；仅核/胞质→胞内。6 个靶点全部合理。但可溶型 vs "两者都有"（如 TNF、膜结合前体后脱落的靶点）会有歧义，需人工。
→ 预填表单里两项都带 `*_reason` 字段说明依据，并强制 `needs_manual_confirm=true`。

### 2.5 查重要同时匹配次级 accession
ChEMBL `target_component_xrefs` 里 UniProt 项包含次级 accession（如 Q9NPF7 还列了 Q6NZ80/Q6NZ82/Q9H2A5）；UniProt 条目也有 `secondaryAccessions`。正式实现查重时应同时匹配主 + 次级 accession，否则同一蛋白因历史 accession 不同会漏查重。PoC 只按主 accession 匹配。

### 2.6 分子搜索的"精确匹配"策略
`/molecule/search` 是模糊检索：`trastuzumab deruxtecan` 返回 18 个候选（含 trastuzumab、datopotamab deruxtecan…）。脚本策略：pref_name 精确等于 INN → 选中；否则同义词（INN/USAN 类型）精确等于 → 选中；否则 `NEEDS_MANUAL_PICK` 返回候选列表让人选。5 例都走了 pref_name 精确匹配。正式实现建议同样"宁可让人选也不猜"。

### 2.7 其他观察
- ChEMBL 返回 `max_phase` 是浮点（4.0），INN 大写；`biotherapeutic.biocomponents` 带全长 HC/LC 序列（约 450 aa），可作为分子域序列字段的来源，但要注意版权/引用（ChEMBL CC BY-SA 3.0）。
- 本次 5 例 mechanism 里 `parent_molecule_chembl_id` 都等于本体；脚本已实现"本体无 mechanism 则回退 parent"分支，未被触发。
- UniProt 条目体积大（含 references/features/xrefs，单条 100–400 KB）；正式实现存 jsonb 建议**只存裁剪后的子集**（proteinDescription/genes/organism/keywords/comments[FUNCTION,SUBCELLULAR LOCATION,SUBUNIT]/features[Domain,Region,Topological domain,Transmembrane]/sequence 元数据/entryAudit）+ 原文件落对象存储或按需重抓，否则表膨胀明显。也可以在 UniProt URL 上加 `?fields=` 只取需要的字段。
- ChEMBL 分页默认 limit=20，mechanism 通常 <20 条无需翻页；正式实现仍应处理 `page_meta.next`。

## 3. 未验证 / 超出本次范围
- 网络：只在 Mac 直连验证。Linux 生产主机（172.19.0.105）后端进程能否出网未验证（见兼容性评估 §5）。
- 未做速率限制/并发压力测试（ChEMBL/UniProt 均建议合理限速；UniProt 要求带 User-Agent，脚本已加）。
- 未验证 RS256/鉴权等与现有系统的集成——PoC 是独立脚本，不碰现有服务。
