# Excel 字段与数据库字段对应核对

2026-09-16。本次只读核对本机旧项目 data 目录的15个工作簿、第5行英文和第6行中文表头、实际导入代码及数据库目录。没有修改工作簿、业务代码、权限或数据。

## 主键与当前筛选来源

- 旧 Excel 写入 cmc_analytics.quality.quality_data，真实主键为 id（bigint，数据库生成）。Excel 前面的项目、组别、产线、样品、批号等是业务维度，不是该主键。旧代码 id_vars 指宽表转长表时保留并重复的列，不保证组合唯一。
- 新页面当前读取 staging.stg_sample/stg_test/stg_result，各表主键均为 (source_system, source_id)。source_id 是来源样品/检测/结果编号，不是项目编号或业务批号；三表同时按来源系统和父记录编号关联。
- 新 QC 项目、产线、组别实际分别取 stg_sample.project_id / production_line_id / group_id，没有读取上述 Excel 旧表。英文字段同名不能证明来源业务含义已统一。
- 本次共享表实查项目包含320041-1、310071-1，产线标签包含迈博太科、生产三部，组别包含迈博太科；Excel示例为CMAB007/CMAB009、DS1/FF1、IH。不能自行推断两套编码如何换算。
- 当前账号没有 quality 旧表读取权限，因此只能确认表头、代码路径和数据库字段/主键，不能据此断言旧表每条数据都已正确落库。

## 前十列

| Excel列 | 中文表头 | 英文表头 / 旧表字段 | 当前新页情况 |
|---|---|---|---|
| A | 请验日期 | `sample_submission_date` | 请验日期筛选未接入；received_dt 不得未经核对当作请验日期 |
| B | 组别 | `group_id` | 取staging组别，并非Excel组别 |
| C | 生产线代码 | `production_line_id` | 取staging产线标签，并非Excel生产线代码 |
| D | 项目代码 | `project_id` | 取staging项目，并非Excel项目代码 |
| E | 样品类别 | `sample_type` | 取staging样品类型 |
| F | 原批号 | `batch_number` | 取staging业务批号，值须原样保留 |
| G | 检验类别 | `test_type` | 取staging检验类别，新旧集合不同 |
| H | 放置状态 | `placement_status` | 未读取、未提供筛选、未参与稳定性分面 |
| I | 时间节点 | `timepoint` | 读取staging时间点作横轴 |
| J | 单位(次/小时/天/月/年) | `timepoint_unit` | 读取staging时间单位；不是检测结果单位 |

## 全部实际表头

下表覆盖15个文件的非空表头；文件编号见文末。指标列的英文名保存到 attribute_name，单元格数值保存到 value，不会在数据库创建每个指标的独立列。旧代码随后排除非数值/非有限结果，图谱“一致”等定性结果不会以数值结果保留。

| 列位置 | 中文表头 | 英文表头 | 旧数据库对应（quality.quality_data） | 文件编号 |
|---|---|---|---|---|
| A | 请验日期 | `sample_submission_date` | `sample_submission_date` | 1,2,3,4,5,6,7,8,9,10,11,12,13,14,15 |
| B | 组别 | `group_id` | `group_id` | 1,2,3,4,5,6,7,8,9,10,11,12,13,14,15 |
| C | 生产线代码 | `production_line_id` | `production_line_id` | 1,2,3,4,5,6,7,8,9,10,11,12,13,14,15 |
| D | 项目代码 | `project_id` | `project_id` | 1,2,3,4,5,6,7,8,9,10,11,12,13,14,15 |
| E | 样品类别 | `sample_type` | `sample_type` | 1,2,3,4,5,6,7,8,9,10,11,12,13,14,15 |
| F | 原批号 | `batch_number` | `batch_number` | 1,2,3,4,5,6,7,8,9,10,11,12,13,15 |
| G | 检验类别 | `test_type` | `test_type` | 1,2,3,4,5,6,7,8,9,10,11,12,13,14,15 |
| H | 放置状态 | `placement_status` | `placement_status` | 1,2,3,4,5,6,7,8,9,10,11,12,13,14,15 |
| I | 时间节点 | `timepoint` | `timepoint` | 1,2,3,4,5,6,7,8,9,10,11,12,13,14,15 |
| J | 单位(次/小时/天/月/年) | `timepoint_unit` | `timepoint_unit` | 1,2,3,4,5,6,7,8,9,10,11,12,13,14,15 |
| K | 肽图(图谱) | `peptide_map_chart` | `attribute_name = peptide_map_chart`；单元格 → `value` | 1,2,3,4,5,6,7,8,9,10,11,12,13,14,15 |
| L | 肽图(肽段) | `peptide_map_peptides` | `attribute_name = peptide_map_peptides`；单元格 → `value` | 1,2,3,4,5,6,7,8,9,10,11,12,13,14,15 |
| M | cIEF(图谱) | `cief_chart` | `attribute_name = cief_chart`；单元格 → `value` | 1,2,3,4,5,6,7,8,9,10,11,12,13,14,15 |
| N | IEF/cIEF(主峰pI差异) | `ief_cief_main_pi_diff` | `attribute_name = ief_cief_main_pi_diff`；单元格 → `value` | 1,2,3,4,5,6,7,8,9,10,11,12,13,14,15 |
| O | IEF/cIEF(主峰pI) | `ief_cief_main_pi` | `attribute_name = ief_cief_main_pi`；单元格 → `value` | 1,2,3,4,5,6,7,8,9,10,11,12,13,14,15 |
| P,AM,AP | Fab_Man5(％) | `fab_man5_pct` | `attribute_name = fab_man5_pct`；单元格 → `value` | 1,3,7,8,9,10,11,12,13,15 |
| Q,AW,AZ | Fab_去核心岩藻糖比例(％) | `fab_afucosylation_pct` | `attribute_name = fab_afucosylation_pct`；单元格 → `value` | 1,3,7,8,9,10,11,12,13,15 |
| R,AX,BA | Fab_岩藻糖二天线寡糖比例(％) | `fab_fucosylated_biantennary_pct` | `attribute_name = fab_fucosylated_biantennary_pct`；单元格 → `value` | 1,3,7,8,9,10,11,12,13,15 |
| S,AY,BB | Fab_高甘露糖糖形比例(％) | `fab_high_mannose_pct` | `attribute_name = fab_high_mannose_pct`；单元格 → `value` | 1,3,7,8,9,10,11,12,13,15 |
| R,T,U,AA,BA,BD | R_CE迁移时间(min) | `r_ce_migration_time` | `attribute_name = r_ce_migration_time`；单元格 → `value` | 1,2,3,5,6,7,8,9,10,11,12,13,15 |
| S,U,V,AB,AD,BB,BE | R_CE纯度(％) | `r_ce_purity_pct` | `attribute_name = r_ce_purity_pct`；单元格 → `value` | 1,2,3,4,5,6,7,8,9,10,11,12,13,14,15 |
| T,U,V,W,AC,AF,BC,BF,BG | R_CE _NGHC非糖基化重链(％) | `r_ce_nghc_pct` | `attribute_name = r_ce_nghc_pct`；单元格 → `value` | 1,2,3,4,5,6,7,8,9,10,11,12,13,14,15 |
| U,V,W,X,AD,AG,BD,BG,BH,BI | NR_CE图谱 | `nr_ce_chart` | `attribute_name = nr_ce_chart`；单元格 → `value` | 1,2,3,4,5,6,7,8,9,10,11,12,13,14,15 |
| V,X,Z,AE,AI,BF,BI,BJ,BK | NR_CE主峰(％) | `nr_ce_main_peak_pct` | `attribute_name = nr_ce_main_peak_pct`；单元格 → `value` | 1,2,3,4,5,6,7,8,9,10,11,12,13,14,15 |
| W,Y,AA,AF,AJ,BG,BJ,BK,BL | SEC聚合体(％) | `sec_aggregate_pct` | `attribute_name = sec_aggregate_pct`；单元格 → `value` | 1,2,3,4,5,6,7,8,9,10,11,12,13,14,15 |
| X,Z,AB,AG,AK,BH,BK,BL,BM | SEC单体(％) | `sec_monomer_pct` | `attribute_name = sec_monomer_pct`；单元格 → `value` | 1,2,3,4,5,6,7,8,9,10,11,12,13,14,15 |
| Y,AA,AC,AL,BI,BM,BN | SEC片段(％) | `sec_fragment_pct` | `attribute_name = sec_fragment_pct`；单元格 → `value` | 1,3,4,5,6,8,9,10,11,12,13,14,15 |
| Z,AB,AD,AI,AM,BJ,BM,BO,BP | IEX图谱 | `iex_chart` | `attribute_name = iex_chart`；单元格 → `value` | 1,2,3,4,5,6,7,8,9,10,11,12,13,14,15 |
| AA,AC,AE,AJ,AN,BK,BN,BP,BQ | IEX相对保留时间 | `iex_relative_retention_time` | `attribute_name = iex_relative_retention_time`；单元格 → `value` | 1,2,3,4,5,6,7,8,9,10,11,12,13,14,15 |
| AB,AD,AF,AK,AO,BL,BQ,BR | 未酶切IEX酸性峰(％) | `undigested_iex_acidic_peaks_pct` | `attribute_name = undigested_iex_acidic_peaks_pct`；单元格 → `value` | 1,2,3,4,5,6,8,9,10,11,12,13,14,15 |
| AE,AP,BM,BO,BR,BS | CPB酶切后IEX酸性峰(％) | `cpb_treated_iex_acidic_peaks_pct` | `attribute_name = cpb_treated_iex_acidic_peaks_pct`；单元格 → `value` | 1,3,4,7,8,9,10,11,12,13,14,15 |
| AC,AF,AG,AL,AQ,BN,BS,BT | 未酶切IEX主峰(％) | `undigested_iex_main_peak_pct` | `attribute_name = undigested_iex_main_peak_pct`；单元格 → `value` | 1,2,3,4,5,6,8,9,10,11,12,13,14,15 |
| AG,AR,BO,BP,BT,BU | CPB酶切后IEX主峰(％) | `cpb_treated_iex_main_peak_pct` | `attribute_name = cpb_treated_iex_main_peak_pct`；单元格 → `value` | 1,3,4,7,8,9,10,11,12,13,14,15 |
| AD,AH,AM,AS,BP,BU,BV | 未酶切IEX碱性峰(％) | `undigested_iex_basic_peaks_pct` | `attribute_name = undigested_iex_basic_peaks_pct`；单元格 → `value` | 1,2,3,4,5,6,8,9,10,11,12,13,14,15 |
| AI,AT,BQ,BV,BW | CPB酶切后IEX碱性峰(％) | `cpb_treated_iex_basic_peaks_pct` | `attribute_name = cpb_treated_iex_basic_peaks_pct`；单元格 → `value` | 1,3,4,7,8,9,10,11,12,13,14,15 |
| AI,AJ,AN,AU,BR,BW,BX | 未酶切IEX主峰及碱性峰(％) | `undigested_iex_main_plus_basic_peaks_pct` | `attribute_name = undigested_iex_main_plus_basic_peaks_pct`；单元格 → `value` | 1,2,3,4,6,8,9,10,11,12,13,14,15 |
| AK,AV,BR,BS,BX,BY | CPB酶切后IEX主峰及碱性峰(％) | `cpb_treated_iex_main_plus_basic_peaks_pct` | `attribute_name = cpb_treated_iex_main_plus_basic_peaks_pct`；单元格 → `value` | 1,3,4,7,8,9,10,11,12,13,14,15 |
| AL,CI,CJ | HIC疏水峰1(％) | `hic_peak1_pct` | `attribute_name = hic_peak1_pct`；单元格 → `value` | 1,8,9,10,11,12,15 |
| AM,CJ,CK | HIC疏水峰2(％) | `hic_peak2_pct` | `attribute_name = hic_peak2_pct`；单元格 → `value` | 1,8,9,10,11,12,15 |
| AN,CK,CM | HIC疏水峰3(％) | `hic_peak3_pct` | `attribute_name = hic_peak3_pct`；单元格 → `value` | 1,8,9,10,11,12,15 |
| AE,AN,AO,AQ,AR,BC,BV,CF,CR,CT | 生物活性(％) | `bioactivity_pct` | `attribute_name = bioactivity_pct`；单元格 → `value` | 1,2,3,4,5,6,7,8,9,10,11,12,13,14,15 |
| AF,AO,AP,AR,AS,BD,BW,CG,CS,CU | 生物活性EC50值(ng/ml) | `bioactivity_ec50_ng_per_ml` | `attribute_name = bioactivity_ec50_ng_per_ml`；单元格 → `value` | 1,2,3,4,5,6,7,8,9,10,11,12,13,14,15 |
| AG,AP,AQ,AS,AT,BE,BX,CH,CT | 结合活性(％) | `binding_activity_pct` | `attribute_name = binding_activity_pct`；单元格 → `value` | 1,2,3,4,5,6,7,8,9,10,11,12,13,14 |
| AH,AQ,AR,AT,AU,BF,BY,CI,CU,CX | 结合活性EC50值(ng/ml) | `binding_activity_ec50_ng_per_ml` | `attribute_name = binding_activity_ec50_ng_per_ml`；单元格 → `value` | 1,2,3,4,5,6,7,8,9,10,11,12,13,14,15 |
| AI,AR,AS,AU,AV,BG,BZ,CJ,CV,CY | 蛋白含量(mg/瓶) | `content_mg_per_vial` | `attribute_name = content_mg_per_vial`；单元格 → `value` | 1,2,3,4,5,6,7,8,9,10,11,12,13,14,15 |
| AJ,AS,AT,AV,AW,BH,CA,CK,CW,CZ | 蛋白含量(g/L) | `content_g_per_l` | `attribute_name = content_g_per_l`；单元格 → `value` | 1,2,3,4,5,6,7,8,9,10,11,12,13,14,15 |
| AL,AU,AY,AZ,BK,CM,DA,DD | 聚山梨酯80含量(g/L) | `ps80_content_g_per_l` | `attribute_name = ps80_content_g_per_l`；单元格 → `value` | 1,2,3,4,5,6,8,9,10,11,12,13,14,15 |
| AV,CB,DB,DE | 聚山梨酯20含量(g/L) | `ps20_content_g_per_l` | `attribute_name = ps20_content_g_per_l`；单元格 → `value` | 1,7,8,9,10,11,12,15 |
| AM,AV,AW,AZ,BB,BM,CC,CN,DD,DH | 外观及性状 | `appearance_characteristics` | `attribute_name = appearance_characteristics`；单元格 → `value` | 1,2,3,4,5,6,7,8,9,10,11,12,13,14,15 |
| AN,AW,AX,BA,BC,BN,CD,CO,DE,DI | 外观浊度(NTU) | `turbidity_ntu` | `attribute_name = turbidity_ntu`；单元格 → `value` | 1,2,3,4,5,6,7,8,9,10,11,12,13,14,15 |
| AO,AX,AY,BD,BO,CE,CP,DF,DJ | 胶塞外观 | `stopper_appearance` | `attribute_name = stopper_appearance`；单元格 → `value` | 1,3,4,5,6,7,8,9,10,11,12,13,14,15 |
| AZ,BB,DG,DK | 复溶时间 | `reconstitution_time_min` | `attribute_name = reconstitution_time_min`；单元格 → `value` | 1,2,8,9,10,11,12,15 |
| AP,AY,BA,BC,BE,BP,CF,CQ,DH,DL | pH值 | `ph_value` | `attribute_name = ph_value`；单元格 → `value` | 1,2,3,4,5,6,7,8,9,10,11,12,13,14,15 |
| AQ,AZ,BB,BD,BF,BQ,CG,CR,DI,DM | 渗透压(mOmsmol/kg) | `osmotic_mosmol_per_kg` | `attribute_name = osmotic_mosmol_per_kg`；单元格 → `value` | 1,2,3,4,5,6,7,8,9,10,11,12,13,14,15 |
| BC,BF,DK,DO | 装量差异(％) | `net_content_variation_pct` | `attribute_name = net_content_variation_pct`；单元格 → `value` | 1,2,8,9,10,11,12,15 |
| AS,BB,BD,BG,BH,BS,CI,CT,DL,DP | 不溶性微粒(≥10μm) | `insoluble_particles_gte_10um` | `attribute_name = insoluble_particles_gte_10um`；单元格 → `value` | 1,2,3,4,5,6,7,8,9,10,11,12,13,14,15 |
| AT,BC,BE,BH,BI,BT,CJ,CU,DM,DQ | 不溶性微粒(≥25μm) | `insoluble_particles_gte_25um` | `attribute_name = insoluble_particles_gte_25um`；单元格 → `value` | 1,2,3,4,5,6,7,8,9,10,11,12,13,14,15 |
| AU,BD,BF,BI,BJ,BU,CK,CV,DN,DR | 可见异物 | `visible_foreign_particles` | `attribute_name = visible_foreign_particles`；单元格 → `value` | 1,2,3,4,5,6,7,8,9,10,11,12,13,14,15 |
| BG,BJ,DO,DS | 水分(％) | `moisture_pct` | `attribute_name = moisture_pct`；单元格 → `value` | 1,2,8,9,10,11,12,15 |
| AV,BE,BH,BK,BL,BY,CL,CX,DQ,DW | 需氧菌 | `aerobic_bacteria` | `attribute_name = aerobic_bacteria`；单元格 → `value` | 1,2,3,4,5,6,7,8,9,10,11,12,13,14,15 |
| AW,BF,BI,BL,BM,BZ,CM,CY,DR,DX | 霉菌和酵母菌 | `mold_and_yeast` | `attribute_name = mold_and_yeast`；单元格 → `value` | 1,2,3,4,5,6,7,8,9,10,11,12,13,14,15 |
| AX,BG,BJ,BM,BN,CA,CN,CZ,DS,DY | 无菌检查 | `sterility_test` | `attribute_name = sterility_test`；单元格 → `value` | 1,2,3,4,5,6,7,8,9,10,11,12,13,14,15 |
| AY,BH,BK,BN,BO,CB,CO,DA,DT,DZ | 细菌内毒素 | `bacterial_endotoxin` | `attribute_name = bacterial_endotoxin`；单元格 → `value` | 1,2,3,4,5,6,7,8,9,10,11,12,13,14,15 |
| AZ,BI,BL,BO,BP,CC,CP,DB,DU,EA | 异常毒性 | `abnormal_toxicity` | `attribute_name = abnormal_toxicity`；单元格 → `value` | 1,2,3,4,5,6,7,8,9,10,11,12,13,14,15 |
| P,Q,T | Fc_Man5(％) | `fc_man5_pct` | `attribute_name = fc_man5_pct`；单元格 → `value` | 2,3,6,7,8,9,10,11,12,13,14,15 |
| Q,R,U | Fc_G1(％) | `fc_g1_pct` | `attribute_name = fc_g1_pct`；单元格 → `value` | 2,3,7,8,9,10,11,12,13,14,15 |
| R,S,V | Fc_G1'(％) | `fc_g1_prime_pct` | `attribute_name = fc_g1_prime_pct`；单元格 → `value` | 2,3,7,8,9,10,11,12,13,14,15 |
| S,T,W | Fc_G1F(％) | `fc_g1f_pct` | `attribute_name = fc_g1f_pct`；单元格 → `value` | 2,3,7,8,9,10,11,12,13,14,15 |
| T,U,X | Fc_G1F'(％) | `fc_g1f_prime_pct` | `attribute_name = fc_g1f_prime_pct`；单元格 → `value` | 2,3,7,8,9,10,11,12,13,14,15 |
| U,V,Y | Fc_Man6(％) | `fc_man6_pct` | `attribute_name = fc_man6_pct`；单元格 → `value` | 2,3,7,8,9,10,11,12,13,14,15 |
| V,W,Z | Fc_G2(％) | `fc_g2_pct` | `attribute_name = fc_g2_pct`；单元格 → `value` | 2,3,7,8,9,10,11,12,13,15 |
| W,X,Z,AA | Fc_G2F(％) | `fc_g2f_pct` | `attribute_name = fc_g2f_pct`；单元格 → `value` | 2,3,7,8,9,10,11,12,13,14,15 |
| X,Y,AB | Fc_G2F_NeuAc1(％) | `fc_g2f_neuac1_pct` | `attribute_name = fc_g2f_neuac1_pct`；单元格 → `value` | 2,3,7,8,9,10,11,12,13,15 |
| Y,Z,AC | Fc_G2F_NeuAc2(％) | `fc_g2f_neuac2_pct` | `attribute_name = fc_g2f_neuac2_pct`；单元格 → `value` | 2,3,7,8,9,10,11,12,13,15 |
| Z,AC,AF | Fc_高甘露糖糖形比例(％) | `fc_high_mannose_pct` | `attribute_name = fc_high_mannose_pct`；单元格 → `value` | 2,3,7,8,9,10,11,12,13 |
| AH,BL,BN,BO | SEC主峰保留时间差(min) | `sec_main_rt_delta_min` | `attribute_name = sec_main_rt_delta_min`；单元格 → `value` | 2,7,8,9,10,11,12,15 |
| AK,AO,AZ,BS,CC,CO,CQ | 宿主细胞蛋白残留(ppm) | `hcp_residual_ppm` | `attribute_name = hcp_residual_ppm`；单元格 → `value` | 2,3,4,6,7,8,9,10,11,12,13,14,15 |
| AL,AP,BA,BT,CD,CP,CR | 宿主细胞DNA(pg/mg) | `hcd_residual_pg_per_mg` | `attribute_name = hcd_residual_pg_per_mg`；单元格 → `value` | 2,3,4,6,7,8,9,10,11,12,13,14,15 |
| AW,CY,DB | 蔗糖含量(mg/瓶) | `sucrose_mg_per_vial` | `attribute_name = sucrose_mg_per_vial`；单元格 → `value` | 2,8,9,10,11,12,15 |
| AK,AT,AX,AY,BJ,CL,CZ,DC | 聚山梨酯80含量(mg/瓶) | `ps80_content_mg_per_vial` | `attribute_name = ps80_content_mg_per_vial`；单元格 → `value` | 2,3,4,5,6,8,9,10,11,12,13,14,15 |
| AR,BA,BE,BG,BR,CH,CS,DJ,DN | 装量(ml) | `deliverable_volume_ml` | `attribute_name = deliverable_volume_ml`；单元格 → `value` | 2,3,4,5,6,7,8,9,10,11,12,13,14,15 |
| P,S | Fc_G0F(％) | `fc_g0f_pct` | `attribute_name = fc_g0f_pct`；单元格 → `value` | 3,7,8,9,10,11,12,13,14,15 |
| AA,AD | Fc_去核心岩藻糖比例(％) | `fc_afucosylation_pct` | `attribute_name = fc_afucosylation_pct`；单元格 → `value` | 3,7,8,9,10,11,12,13,15 |
| AB,AE | Fc_岩藻糖二天线寡糖比例(％) | `fc_fucosylated_biantennary_pct` | `attribute_name = fc_fucosylated_biantennary_pct`；单元格 → `value` | 3,7,8,9,10,11,12,13,15 |
| Q,AD,AG | Fc_唾液酸糖型(％) | `fc_sialylation_pct` | `attribute_name = fc_sialylation_pct`；单元格 → `value` | 3,6,7,8,9,10,11,12,13,15 |
| P,R,AA,AE,AH | sum_去核心岩藻糖比例(％) | `sum_afucosylation_pct` | `attribute_name = sum_afucosylation_pct`；单元格 → `value` | 3,4,6,7,8,9,10,11,12,13,14,15 |
| P,Q,S,AB,AF,AI | sum_岩藻糖二天线寡糖比例(％) | `sum_fucosylated_biantennary_pct` | `attribute_name = sum_fucosylated_biantennary_pct`；单元格 → `value` | 3,4,5,6,7,8,9,10,11,12,13,14,15 |
| Q,R,T,AC,AG,AJ | sum_高甘露糖糖型比例(％) | `sum_high_mannose_pct` | `attribute_name = sum_high_mannose_pct`；单元格 → `value` | 3,4,5,6,7,8,9,10,11,12,13,14,15 |
| AH,AK | sum_唾液酸糖型(％) | `sum_sialylation_pct` | `attribute_name = sum_sialylation_pct`；单元格 → `value` | 3,7,8,9,10,11,12,13,15 |
| AI,AL | Fab_G0_GlcNAc(％) | `fab_g0_glcnac_pct` | `attribute_name = fab_g0_glcnac_pct`；单元格 → `value` | 3,7,8,9,10,11,12,13,15 |
| AJ,AM | Fab_G0F_GlcNAc(％) | `fab_g0f_glcnac_pct` | `attribute_name = fab_g0f_glcnac_pct`；单元格 → `value` | 3,7,8,9,10,11,12,13,15 |
| AK,AN | Fab_G0(％) | `fab_g0_pct` | `attribute_name = fab_g0_pct`；单元格 → `value` | 3,7,8,9,10,11,12,13,15 |
| AL,AO | Fab_G0F(％) | `fab_g0f_pct` | `attribute_name = fab_g0f_pct`；单元格 → `value` | 3,7,8,9,10,11,12,13,15 |
| AN,AQ | Fab_G1(％) | `fab_g1_pct` | `attribute_name = fab_g1_pct`；单元格 → `value` | 3,7,8,9,10,11,12,13,15 |
| AO,AR | Fab_G1'(％) | `fab_g1_prime_pct` | `attribute_name = fab_g1_prime_pct`；单元格 → `value` | 3,7,8,9,10,11,12,13,15 |
| AP,AS | Fab_G1F(％) | `fab_g1f_pct` | `attribute_name = fab_g1f_pct`；单元格 → `value` | 3,7,8,9,10,11,12,13,15 |
| AQ,AT | Fab_G1F'(％) | `fab_g1f_prime_pct` | `attribute_name = fab_g1f_prime_pct`；单元格 → `value` | 3,7,8,9,10,11,12,13,15 |
| AR,AU | Fab_Man6(％) | `fab_man6_pct` | `attribute_name = fab_man6_pct`；单元格 → `value` | 3,7,8,9,10,11,12,13,15 |
| AS,AV | Fab_G2(％) | `fab_g2_pct` | `attribute_name = fab_g2_pct`；单元格 → `value` | 3,7,8,9,10,11,12,13,15 |
| AT,AW | Fab_G2F(％) | `fab_g2f_pct` | `attribute_name = fab_g2f_pct`；单元格 → `value` | 3,7,8,9,10,11,12,13,15 |
| AU,AX | Fab_G2F_NeuAc1(％) | `fab_g2f_neuac1_pct` | `attribute_name = fab_g2f_neuac1_pct`；单元格 → `value` | 3,7,8,9,10,11,12,13,15 |
| AV,AY | Fab_G2F_NeuAc2(％) | `fab_g2f_neuac2_pct` | `attribute_name = fab_g2f_neuac2_pct`；单元格 → `value` | 3,7,8,9,10,11,12,13,15 |
| AZ,BC | Fab_唾液酸糖型比例(％) | `fab_sialylation_pct` | `attribute_name = fab_sialylation_pct`；单元格 → `value` | 3,7,8,9,10,11,12,13,15 |
| W,Y,AH,BE,BH,BI,BJ | NR_CE片段(％) | `nr_ce_fragment_pct` | `attribute_name = nr_ce_fragment_pct`；单元格 → `value` | 3,4,6,7,8,9,10,11,12,13,14,15 |
| AJ,BT,BY,BZ | IEX非相关物质峰(％) | `iex_unrelated_peaks_pct` | `attribute_name = iex_unrelated_peaks_pct`；单元格 → `value` | 3,6,8,9,10,11,12,13,15 |
| BU,BZ,CA | IEX_P1峰(％) | `iex_p1_main_peak_pct` | `attribute_name = iex_p1_main_peak_pct`；单元格 → `value` | 3,8,9,10,11,12,13,15 |
| BV,CA,CB | IEX_P2峰(％) | `iex_p2_main_peak_pct` | `attribute_name = iex_p2_main_peak_pct`；单元格 → `value` | 3,8,9,10,11,12,13,15 |
| BW,CB,CC | IEX_P3峰(％) | `iex_p3_main_peak_pct` | `attribute_name = iex_p3_main_peak_pct`；单元格 → `value` | 3,8,9,10,11,12,13,15 |
| BX,CC,CD | IEX_P4峰(％) | `iex_p4_main_peak_pct` | `attribute_name = iex_p4_main_peak_pct`；单元格 → `value` | 3,8,9,10,11,12,13,15 |
| BY,CD,CE | IEX_P5峰(％) | `iex_p5_main_peak_pct` | `attribute_name = iex_p5_main_peak_pct`；单元格 → `value` | 3,8,9,10,11,12,13,15 |
| BZ,CE,CF | IEX_P1_to_P5(％) | `iex_p1_to_p5_total_area_pct` | `attribute_name = iex_p1_to_p5_total_area_pct`；单元格 → `value` | 3,8,9,10,11,12,13,15 |
| CA,CF,CG | IEX_P1_to_P5及酸性峰面积之和(％) | `iex_p1_to_p5_acidic_total_area_pct` | `attribute_name = iex_p1_to_p5_acidic_total_area_pct`；单元格 → `value` | 3,8,9,10,11,12,13,15 |
| CB,CG,CH | IEX_P1_to_P5及碱性峰面积之和(％) | `iex_p1_to_p5_basic_total_area_pct` | `attribute_name = iex_p1_to_p5_basic_total_area_pct`；单元格 → `value` | 3,8,9,10,11,12,13,15 |
| AM,AQ,BB,BU,CE,CQ,CS | 蛋白A/L残留(ppm) | `protein_a_l_residual_ppm` | `attribute_name = protein_a_l_residual_ppm`；单元格 → `value` | 3,4,6,7,8,9,10,11,12,13,14,15 |
| BK,BX,CW,DP,DV | 微生物限度(微生物总数)cfu/ml | `microbial_limit_total_cfu_per_ml` | `attribute_name = microbial_limit_total_cfu_per_ml`；单元格 → `value` | 3,4,8,9,10,11,12,13,14,15 |
| T,AE,BF | R_CE新峰校正峰(％) | `r_ce_new_peak_corr_pct` | `attribute_name = r_ce_new_peak_corr_pct`；单元格 → `value` | 4,8,9,10,11,12,14,15 |
| AL,AW,CL,CN | RP反相色谱主峰前(％) | `rp_pre_main_peak_pct` | `attribute_name = rp_pre_main_peak_pct`；单元格 → `value` | 4,8,9,10,11,12,14,15 |
| AM,AX,CM,CO | RP反相色谱主峰(％) | `rp_main_peak_pct` | `attribute_name = rp_main_peak_pct`；单元格 → `value` | 4,8,9,10,11,12,14,15 |
| AN,AY,CN,CP | RP反相色谱主峰后(％) | `rp_post_main_peak_pct` | `attribute_name = rp_post_main_peak_pct`；单元格 → `value` | 4,8,9,10,11,12,14,15 |
| AX,BI,CX,DA | 甲硫氨酸(mmol/L) | `methionine_mmol_per_l` | `attribute_name = methionine_mmol_per_l`；单元格 → `value` | 4,8,9,10,11,12,14,15 |
| BA,BL,DC,DG | 游离巯基含量(mol/mol) | `free_thiol_mol_per_mol` | `attribute_name = free_thiol_mol_per_mol`；单元格 → `value` | 4,8,9,10,11,12,14,15 |
| P | Fc_G0_GlcNAc(％) | `fc_g0_glcnac_pct` | `attribute_name = fc_g0_glcnac_pct`；单元格 → `value` | 7,8,9,10,11,12,14,15 |
| Q | Fc_G0F_GlcNAc(％) | `fc_g0f_glcnac_pct` | `attribute_name = fc_g0f_glcnac_pct`；单元格 → `value` | 7,8,9,10,11,12,14,15 |
| R | Fc_G0(％) | `fc_g0_pct` | `attribute_name = fc_g0_pct`；单元格 → `value` | 7,8,9,10,11,12,14,15 |
| CQ,DV,EB | R_CE轻链校正峰面积百分比(％) | `r_ce_lc_corr_peak_area_pct` | `attribute_name = r_ce_lc_corr_peak_area_pct`；单元格 → `value` | 7,8,9,10,11,12,15 |
| CR,DW,EC | R_CE重链校正峰面积百分比(％) | `r_ce_hc_corr_peak_area_pct` | `attribute_name = r_ce_hc_corr_peak_area_pct`；单元格 → `value` | 7,8,9,10,11,12,15 |
| CS,DX,ED | R_CE三者校正峰面积百分比之和(％) | `r_ce_total_corr_peaks_pct` | `attribute_name = r_ce_total_corr_peaks_pct`；单元格 → `value` | 7,8,9,10,11,12,15 |
| CH,CI | HIC疏水主峰(％) | `hic_main_peak_pct` | `attribute_name = hic_main_peak_pct`；单元格 → `value` | 8,9,10,11,12,15 |
| DY,EE | IEX酸式1峰(％) | `iex_acidic1_peak_pct` | `attribute_name = iex_acidic1_peak_pct`；单元格 → `value` | 8,9,10,11,12,15 |
| DZ,EF | IEX主峰前峰(％) | `iex_pre_main_peak_pct` | `attribute_name = iex_pre_main_peak_pct`；单元格 → `value` | 8,9,10,11,12,15 |
| EA,EG | IEX碱式1峰(％) | `iex_basic1_peak_pct` | `attribute_name = iex_basic1_peak_pct`；单元格 → `value` | 8,9,10,11,12,15 |
| EB,EH | IEX碱式2峰(％) | `iex_basic2_peak_pct` | `attribute_name = iex_basic2_peak_pct`；单元格 → `value` | 8,9,10,11,12,15 |
| EC,EI | IEX碱式变异体A(％) | `iex_basic_variant_a_pct` | `attribute_name = iex_basic_variant_a_pct`；单元格 → `value` | 8,9,10,11,12,15 |
| ED,EJ | IEX碱式变异体B(％) | `iex_basic_variant_b_pct` | `attribute_name = iex_basic_variant_b_pct`；单元格 → `value` | 8,9,10,11,12,15 |
| EE,EK | 质量肽图谱轻链覆盖率(％) | `lc_coverage_pct` | `attribute_name = lc_coverage_pct`；单元格 → `value` | 8,9,10,11,12,15 |
| EF,EL | 质量肽图谱重链覆盖率(％) | `hc_coverage_pct` | `attribute_name = hc_coverage_pct`；单元格 → `value` | 8,9,10,11,12,15 |
| EG,EM | 报告CDR区鉴定结果 | `cdr_identification_result` | `attribute_name = cdr_identification_result`；单元格 → `value` | 8,9,10,11,12,15 |
| EH,EN | 报告重链主要翻译后修饰 | `hc_main_ptm` | `attribute_name = hc_main_ptm`；单元格 → `value` | 8,9,10,11,12,15 |
| EI,EO | 报告轻链主要翻译后修饰 | `lc_main_ptm` | `attribute_name = lc_main_ptm`；单元格 → `value` | 8,9,10,11,12,15 |
| EJ,EP | 报告糖基化位点 | `glycosylation_sites` | `attribute_name = glycosylation_sites`；单元格 → `value` | 8,9,10,11,12,15 |
| EK,EL,EQ | 二硫键 | `disulfide_bonds` | `attribute_name = disulfide_bonds`；单元格 → `value` | 8,9,10,11,12,15 |
| EL,EM,ER | 圆二色谱 | `circular_dichroism` | `attribute_name = circular_dichroism`；单元格 → `value` | 8,9,10,11,12,15 |
| EM,EN,ES | Fab与Ag亲和力 | `fab_ag_affinity` | `attribute_name = fab_ag_affinity`；单元格 → `value` | 8,9,10,11,12,15 |
| EN,EO,ET | Fc与FcRn亲和力 | `fc_fcrn_affinity` | `attribute_name = fc_fcrn_affinity`；单元格 → `value` | 8,9,10,11,12,15 |
| EO,EP,EU | 轻链分子量(Da) | `lc_mw_da` | `attribute_name = lc_mw_da`；单元格 → `value` | 8,9,10,11,12,15 |
| EP,EQ,EV | 轻链分子量(ppm) | `lc_mw_ppm` | `attribute_name = lc_mw_ppm`；单元格 → `value` | 8,9,10,11,12,15 |
| EQ,ER,EW | 重链分子量(Da) | `hc_mw_da` | `attribute_name = hc_mw_da`；单元格 → `value` | 8,9,10,11,12,15 |
| ER,ES | 重链分子量(ppm) | `hc_mw_ppm` | `attribute_name = hc_mw_ppm`；单元格 → `value` | 8,9,10,11,12 |
| ET | 亚单位轻链主峰分子量ppm | `subunit_lc_main_peak_mw_ppm` | `attribute_name = subunit_lc_main_peak_mw_ppm`；单元格 → `value` | 12 |
| EU | 亚单位重链主峰分子量ppm | `subunit_hc_main_peak_mw_ppm` | `attribute_name = subunit_hc_main_peak_mw_ppm`；单元格 → `value` | 12 |
| DC | 备注 | `` | 英文表头缺失，不能确认有效映射 | 13 |
| F | 批号 | `batch_number` | `batch_number` | 14 |
| BV,DT | 自动注射笔外观 | `auto_injector_appearance` | `attribute_name = auto_injector_appearance`；单元格 → `value` | 14,15 |
| BW,DU | 自动注射笔剂量准确度 | `auto_injector_dosage_accuracy` | `attribute_name = auto_injector_dosage_accuracy`；单元格 → `value` | 14,15 |
| AF | Fc_高甘露糖糖型比例(％) | `fc_high_mannose_pct` | `attribute_name = fc_high_mannose_pct`；单元格 → `value` | 15 |
| BH | R_CE其他杂质校正峰(％) | `r_ce_other_ impurity_pct` | `attribute_name = r_ce_other_ impurity_pct`；单元格 → `value` | 15 |
| CL | HIC疏水峰1+峰2(％) | `hic_peak1_to_peak2_pct` | `attribute_name = hic_peak1_to_peak2_pct`；单元格 → `value` | 15 |
| CV | 结合活性（鉴别） | `binding_activity` | `attribute_name = binding_activity`；单元格 → `value` | 15 |
| CW | 结合活性(％) | `binding_activity_pct2` | `attribute_name = binding_activity_pct2`；单元格 → `value` | 15 |
| DF | 聚山梨酯20含量(％W/V) | `ps20_content_pct_w_per_v` | `attribute_name = ps20_content_pct_w_per_v`；单元格 → `value` | 15 |
| EX | 亚单位轻链主峰分子量ppm | `subunit_lc_main peak_mw_ppm` | `attribute_name = subunit_lc_main peak_mw_ppm`；单元格 → `value` | 15 |
| EY | 亚单位重链主峰分子量ppm | `subunit_hc_main peak_mw_ppm` | `attribute_name = subunit_hc_main peak_mw_ppm`；单元格 → `value` | 15 |

## 自动生成字段与新模板的区别

表头还存在需要单独核对的差异：放行文件 BH 列为 `r_ce_other_ impurity_pct`（中间含空格）；EX/EY 为 `subunit_lc_main peak_mw_ppm` / `subunit_hc_main peak_mw_ppm`，另一文件使用下划线版本。旧代码只清理首尾空白和部分不可见字符，不统一这些内部空格；这些名称可能成为不同检测项，影响指标选择，不能未经业务核对直接合并。文件13的 DC 列只有中文“备注”，第5行英文表头为空，也不能当作质量检测项。以上均未修改。

- id：数据库生成的结果行主键；source_file：文件名；update_time：导入时间。旧导入把 data_source 固定设为 QC_LIMS，该文字标签不能证明数据来自QC ETL或已批准。
- data_type：旧页面导入先按文件名推断，再按检验类别中的“放行/稳定”修正；振荡试验等可能依赖文件名回退。旧命令行脚本分类有差异，须统一核对。
- sub_lot：旧表及配置有此字段；Excel未提供则补空，不得取代原批号。
- 旧 quality_data 没有独立的检测结果 unit 列。结果单位常在中文表头或指标名后缀中；timepoint_unit 只代表时间单位。百分数原值不能未经确认自动放大或缩小。
- 新QAP五列草案模板仅做内存结构预览：project_code → source_project_ref；batch_number → batch_number；attribute → source_attribute；value → value_raw；unit → source_unit。没有确认导入、没有数据库落表映射。
- 五列草案没有覆盖旧Excel的组别、生产线、样品、类别、放置状态、时间点和时间单位，不能视为旧Excel完整导入模板。

## 已定位缺口及待修正方向（尚未实施）

1. Excel历史入口的项目、产线、组别等筛选须从旧quality_data实际字段读取，不能以gmp_labvantage历史staging选项代替。先准备只读适配及权限方案，涉及授权/连接配置变更再确认。
2. 保留Excel项目原码，例如CMAB007，不自行改为007/007_2，也不替换为产品编号或研究编号；跨来源对应关系待业务确认。
3. 完整模板和筛选应以实际前十列为基础，补齐放置状态等缺失维度，避免不同放置状态无说明混算；不能只凭这些维度相同就删除复测记录。
4. 本次不修改已存数据或主键。先核对字段语义，再实施兼容读取和筛选修正。

## 本机核验文件

1. `新项目第一表-007稳定性数据.xlsx`，工作表 `原始数据表`，表头第5—6行。
2. `新项目第一表-008稳定性数据.xlsx`，工作表 `原始数据表`，表头第5—6行。
3. `新项目第一表-009稳定性数据.xlsx`，工作表 `原始数据表`，表头第5—6行。
4. `新项目第一表-015稳定性数据.xlsx`，工作表 `原始数据表`，表头第5—6行。
5. `新项目第一表-017稳定性数据.xlsx`，工作表 `原始数据表`，表头第5—6行。
6. `新项目第一表-515稳定性数据.xlsx`，工作表 `原始数据表`，表头第5—6行。
7. `新项目第一表-807稳定性数据.xlsx`，工作表 `原始数据表`，表头第5—6行。
8. `新项目第一表-809稳定性数据.xlsx`，工作表 `原始数据表`，表头第5—6行。
9. `新项目第一表-819稳定性数据.xlsx`，工作表 `原始数据表`，表头第5—6行。
10. `新项目第一表-820稳定性数据.xlsx`，工作表 `原始数据表`，表头第5—6行。
11. `新项目第一表-AS1501稳定性数据.xlsx`，工作表 `原始数据表`，表头第5—6行。
12. `新项目第一表-企业标准品稳定性数据.xlsx`，工作表 `原始数据表`，表头第5—6行。
13. `项目第一表_009稳定性数据.xlsx`，工作表 `原始数据表`，表头第5—6行。
14. `项目第一表_015稳定性数据.xlsx`，工作表 `原始数据表`，表头第5—6行。
15. `项目第一表_放行检验结果汇总..xlsx`，工作表 `原始数据表`，表头第5—6行。

代码依据：旧项目 config/fields.yaml、analytics/data_loader.py:210、analytics/transformers.py:118、etl/import_service.py:61；新项目 backend/app/repositories/quality_repository.py、backend/app/services/imports/templates.py。主键及数据库字段来自本次本机 pg_catalog 只读核查。没有执行历史 quality_setup.sql。
