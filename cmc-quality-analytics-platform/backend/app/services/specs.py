# -*- coding: utf-8 -*-
"""规格限度（SPEC LIMITS）查找——移植自旧工具 components/spec_limits.py。

与旧工具差异（已适配 staging 现实）：
1) 项目键别名：staging 的 project_id 形如 '009'/'015'，旧 spec 键是 'CMAB009'/'CMAB015'，
   查找时自动尝试 'CMAB'+project_id 等候选。
2) 单位：旧 spec 的百分比限度是小数(0.98=98%)，而 staging 的百分比值是百分数(99.4)。
   本模块返回原始小数限度；is_pct 的 ×100 换算由调用方(release_service)按属性 is_pct 处理。

限度值（DEFAULT/PROJECT_SPEC_LIMITS）逐字移植旧工具，便于业务核对。
DDM 目标态为中台 dim.spec_master；本模块为 Phase 1 临时承载，待其就绪后切换只读。
"""
from functools import lru_cache

DEFAULT_SPEC_LIMITS = {
    "fc_man5_pct": (None, 0.10),
    "sec_aggregate_pct": (None, 0.01),
    "sec_monomer_pct": (1, None),
    "sec_fragment_pct": (None, None),
    "undigested_iex_acidic_peaks_pct": (None, 0.35),
    "undigested_iex_main_peak_pct": (0.45, None),
    "undigested_iex_basic_peaks_pct": (None, 25),
    "undigested_iex_main_plus_basic_peaks_pct": (0.65, None),
    "r_ce_nghc_pct": (None, 0.04),
    "r_ce_purity_pct": (0.960, None),
    "nr_ce_main_peak_pct": (0.920, None),
    "bioactivity_pct": (0.8, 1.2),
    "binding_activity_pct": (0.8, 1.2),
    "hcp_residual_ppm": (None, 100),
    "hcd_residual_pg_per_mg": (None, 1),
    "protein_a_l_residual_ppm": (None, 100),
    "content_mg_per_vial": (0.92, 1.08),
    "net_content_variation_pct": (-0.05, 0.05),
    "moisture_pct": (None, 0.018),
    "ps80_content_mg_per_vial": (0.25, 0.75),
    "sucrose_mg_per_vial": (400, 600),
    "osmotic_mosmol_per_kg": (130, 200),
    "ph_value": (6.9, 7.5),
    "insoluble_particles_gte_10um": (None, 6000),
    "insoluble_particles_gte_25um": (None, 600),
    "turbidity_ntu": (None, 18),
}

PROJECT_SPEC_LIMITS = {
    "CMAB008": {
        "DS": {
            "fc_man5_pct": (None, 0.10),
            "sec_aggregate_pct": (None, 0.02),
            "sec_monomer_pct": (0.98, None),
            "sec_fragment_pct": (None, None),
            "r_ce_purity_pct": (0.960, None),
            "r_ce_nghc_pct": (None, 0.04),
            "nr_ce_main_peak_pct": (0.920, None),
            "undigested_iex_acidic_peaks_pct": (None, 0.35),
            "undigested_iex_main_peak_pct": (0.45, None),
            "undigested_iex_basic_peaks_pct": (None, 25),
            "undigested_iex_main_plus_basic_peaks_pct": (0.65, None),
            "hcp_residual_ppm": (None, 100),
            "hcd_residual_pg_per_mg": (None, 1),
            "protein_a_l_residual_ppm": (None, 50),
            "bioactivity_pct": (0.8, 1.2),
            "binding_activity_pct": (0.8, 1.2),
            "content_g_per_l": (20.0, 40.0),
            "ph_value": (6.9, 7.5),
            "osmotic_mosmol_per_kg": (320, 420),
            "ps80_content_g_per_l": (0.05, 0.15),
        },
        "DP": {
            "sec_aggregate_pct": (None, 0.02),
            "sec_monomer_pct": (0.98, None),
            "sec_fragment_pct": (None, None),
            "undigested_iex_acidic_peaks_pct": (None, 0.35),
            "undigested_iex_main_peak_pct": (0.45, None),
            "undigested_iex_basic_peaks_pct": (None, 25),
            "undigested_iex_main_plus_basic_peaks_pct": (0.65, None),
            "r_ce_purity_pct": (0.960, None),
            "r_ce_nghc_pct": (None, 0.04),
            "nr_ce_main_peak_pct": (0.920, None),
            "bioactivity_pct": (0.8, 1.2),
            "binding_activity_pct": (0.8, 1.2),
            "content_mg_per_vial": (0.92, 1.08),
            "insoluble_particles_gte_10um": (None, 6000),
            "insoluble_particles_gte_25um": (None, 600),
            "net_content_variation_pct": (-0.05, 0.05),
            "moisture_pct": (None, 0.018),
            "ph_value": (6.9, 7.5),
            "osmotic_mosmol_per_kg": (130, 200),
            "sucrose_mg_per_vial": (400, 600),
            "ps80_content_mg_per_vial": (0.25, 0.75),
        },
    },
    "CMAB009": {
        "DS": {
            "fc_man5_pct": (None, 0.05),
            "fc_sialylation_pct": (0.21, 0.41),
            "sec_aggregate_pct": (None, None),
            "sec_monomer_pct": (0.95, None),
            "sec_fragment_pct": (None, None),
            "r_ce_purity_pct": (0.950, None),
            "r_ce_nghc_pct": (None, None),
            "nr_ce_main_peak_pct": (0.920, None),
            "undigested_iex_acidic_peaks_pct": (None, 0.25),
            "iex_p1_to_p5_total_area_pct": (0.65, None),
            "undigested_iex_basic_peaks_pct": (None, 0.15),
            "hcp_residual_ppm": (None, 100),
            "hcd_residual_pg_per_mg": (None, 1.0),
            "protein_a_l_residual_ppm": (None, 50),
            "bioactivity_pct": (0.7, 1.3),
            "binding_activity_pct": (0.7, 1.3),
            "content_g_per_l": (15.0, 40.0),
            "ph_value": (6.8, 7.4),
            "osmotic_mosmol_per_kg": (280, 340),
            "ps80_content_g_per_l": (0.035, 0.105),
            "turbidity_ntu": (None, 18),
        },
        "DP": {
            "sec_aggregate_pct": (None, None),
            "sec_monomer_pct": (0.95, None),
            "sec_fragment_pct": (None, None),
            "undigested_iex_acidic_peaks_pct": (None, 0.25),
            "iex_p1_to_p5_total_area_pct": (0.65, None),
            "undigested_iex_basic_peaks_pct": (None, 0.15),
            "r_ce_purity_pct": (0.950, None),
            "r_ce_nghc_pct": (None, None),
            "nr_ce_main_peak_pct": (0.920, None),
            "bioactivity_pct": (0.70, 1.3),
            "binding_activity_pct": (0.70, 1.3),
            "content_mg_per_vial": (90, 110),
            "insoluble_particles_gte_10um": (None, 6000),
            "insoluble_particles_gte_25um": (None, 600),
            "ph_value": (6.8, 7.4),
            "osmotic_mosmol_per_kg": (280, 340),
            "ps80_content_g_per_l": (0.035, 0.105),
            "turbidity_ntu": (None, 18),
        },
    },
    "CMAB015": {
        "DS": {
            "fc_man5_pct": (None, 0.10),
            "sec_aggregate_pct": (None, 0.025),
            "sec_monomer_pct": (0.975, None),
            "sec_fragment_pct": (None, 0.015),
            "r_ce_purity_pct": (0.950, None),
            "r_ce_nghc_pct": (None, None),
            "nr_ce_main_peak_pct": (0.920, None),
            "cpb_treated_iex_acidic_peaks_pct": (None, 0.16),
            "cpb_treated_iex_main_peak_pct": (0.731, None),
            "cpb_treated_iex_basic_peaks_pct": (None, 0.18),
            "rp_pre_main_peak_pct": (None, 0.10),
            "rp_main_peak_pct": (0.81, None),
            "rp_post_main_peak_pct": (None, 0.130),
            "hcp_residual_ppm": (None, 100),
            "hcd_residual_pg_per_mg": (None, 1.0),
            "protein_a_l_residual_ppm": (None, 50),
            "bioactivity_pct": (0.80, 1.20),
            "binding_activity_pct": (0.80, 1.20),
            "content_g_per_l": (142.5, 157.5),
            "ph_value": (5.6, 6.1),
            "osmotic_mosmol_per_kg": (300, 400),
            "free_thiol_mol_per_mol": (2.0, 2.7),
            "methionine_mmol_per_l": (12.5, None),
            "ps80_content_g_per_l": (0.10, 0.30),
            "turbidity_ntu": (None, 18),
        },
        "DP": {
            "sec_aggregate_pct": (None, 0.025),
            "sec_monomer_pct": (0.975, None),
            "sec_fragment_pct": (None, 0.015),
            "cpb_treated_iex_acidic_peaks_pct": (None, 0.16),
            "cpb_treated_iex_main_peak_pct": (0.731, None),
            "cpb_treated_iex_basic_peaks_pct": (None, 0.18),
            "r_ce_purity_pct": (0.950, None),
            "r_ce_nghc_pct": (None, None),
            "nr_ce_main_peak_pct": (0.950, None),
            "rp_pre_main_peak_pct": (None, 0.10),
            "rp_main_peak_pct": (0.81, None),
            "rp_post_main_peak_pct": (None, 0.130),
            "bioactivity_pct": (0.80, 1.2),
            "binding_activity_pct": (0.80, 1.2),
            "content_g_per_l": (135, 165),
            "insoluble_particles_gte_10um": (None, 6000),
            "insoluble_particles_gte_25um": (None, 600),
            "ph_value": (5.6, 6.1),
            "osmotic_mosmol_per_kg": (280, 340),
            "ps80_content_g_per_l": (0.035, 0.105),
            "turbidity_ntu": (None, 18),
        },
    },
}

_SAMPLE_TYPE_MAP = {
    "原液": "DS",
    "成品": "DP",
    "制剂": "DP",
    "原研药": "INN",
    "原研": "INN",
}


def normalize_sample_type(stype):
    if stype is None:
        return None
    return _SAMPLE_TYPE_MAP.get(str(stype).strip(), None)


def _project_candidates(project_id: str) -> list[str]:
    """staging '009'/'009_2' → 候选 spec 键：原值、CMAB009、CMAB+前缀。"""
    p = str(project_id).strip().upper()
    base = p.split("_")[0]
    cands = [p, f"CMAB{p}", f"CMAB{base}"]
    # 去重保序
    seen, out = set(), []
    for c in cands:
        if c not in seen:
            seen.add(c)
            out.append(c)
    return out


@lru_cache(maxsize=2048)
def get_spec_limit(project_id, attribute, sample_type=None):
    """获取 (LSL, USL)（小数口径，与旧工具一致）。未定义返回 (None, None)。"""
    if project_id is None or attribute is None:
        return (None, None)
    st = normalize_sample_type(sample_type)
    for proj in _project_candidates(project_id):
        proj_dict = PROJECT_SPEC_LIMITS.get(proj)
        if not proj_dict:
            continue
        if st and st in proj_dict and attribute in proj_dict[st]:
            return proj_dict[st][attribute]
        if "COMMON" in proj_dict and attribute in proj_dict["COMMON"]:
            return proj_dict["COMMON"][attribute]
    if attribute in DEFAULT_SPEC_LIMITS:
        return DEFAULT_SPEC_LIMITS[attribute]
    return (None, None)
