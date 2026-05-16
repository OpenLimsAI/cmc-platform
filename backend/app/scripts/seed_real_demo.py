"""
真实 demo 数据集：3 个单抗生物类似药全流程闭环
- CMAB-101 Denosumab biosimilar（已申报 BLA / 临床等效完成）
- CMAB-205 Pembrolizumab biosimilar（Keytruda 类似药，Ph3 进行中）
- CMAB-016 Dupilumab biosimilar（Dupixent 类似药，Ph1 早期）

用法：
  docker compose -f deploy/docker-compose.dev.yml exec backend \\
    python -m app.scripts.seed_real_demo

幂等：物质按 internal_code、项目按 project_name、资产按 internal_name。
"""
import asyncio
import sys

from loguru import logger

from app.core.database import AsyncSessionLocal
from app.scripts import seed_data


# =============================================================================
# 物质（SRS）：3 个单抗
# =============================================================================

REAL_SUBSTANCES = [
    {
        "substance_type": "mab",
        "internal_code": "CMAB-101",
        "preferred_name": "地舒单抗注射液 (CMAB-101)",
        "preferred_name_en": "Denosumab biosimilar (CMAB-101)",
        "target": "RANKL",
        "target_type": "TNF 超家族配体",
        "modality": "human IgG2 mAb",
        "status": "registered",
        "confidentiality": "restricted",
        "description": (
            "抗 RANKL 全人源单抗，地舒单抗（Prolia® / Xgeva® 原研 Amgen）类似药。"
            "IgG2 同种型；阻断 RANKL 与 RANK 结合，抑制破骨细胞分化与活性。"
            "目标双适应症：绝经后骨质疏松（皮下 60 mg/6 个月）+ 实体瘤骨相关事件预防（皮下 120 mg/4 周）。"
        ),
        "protein": {
            "isotype": "IgG2",
            "expression_system": "CHO",
            "cell_line": "CHO-K1-101",
            "molecular_weight_da": 147000.0,
        },
        "xrefs": [
            {"xref_type": "INN", "xref_value": "denosumab", "xref_source": "WHO", "is_primary": True},
            {"xref_type": "CAS", "xref_value": "615258-40-7", "xref_source": "CAS"},
            {"xref_type": "OTHER", "xref_value": "TNFSF11 (HGNC gene symbol)", "xref_source": "HGNC"},
            {"xref_type": "PROJECT_CODE", "xref_value": "CMAB-101", "xref_source": "internal"},
        ],
    },
    {
        "substance_type": "mab",
        "internal_code": "CMAB-205",
        "preferred_name": "帕博利珠单抗类似药 (CMAB-205)",
        "preferred_name_en": "Pembrolizumab biosimilar (CMAB-205)",
        "target": "PD-1",
        "target_type": "免疫检查点",
        "modality": "humanized IgG4 mAb",
        "status": "active",
        "confidentiality": "restricted",
        "description": (
            "抗 PD-1 人源化单抗，Keytruda® (pembrolizumab，原研 MSD) 类似药。"
            "humanized IgG4 含 S228P 铰链稳定突变；阻断 PD-1 与 PD-L1/PD-L2 结合，"
            "恢复 T 细胞抗肿瘤活性。临床覆盖黑色素瘤、NSCLC、HNSCC 等多瘤种。"
        ),
        "protein": {
            "isotype": "IgG4",
            "expression_system": "CHO",
            "cell_line": "CHO-205",
            "molecular_weight_da": 149000.0,
        },
        "xrefs": [
            {"xref_type": "INN", "xref_value": "pembrolizumab", "xref_source": "WHO", "is_primary": True},
            {"xref_type": "CAS", "xref_value": "1374853-91-4", "xref_source": "CAS"},
            {"xref_type": "OTHER", "xref_value": "PDCD1 (HGNC gene symbol)", "xref_source": "HGNC"},
            {"xref_type": "PROJECT_CODE", "xref_value": "CMAB-205", "xref_source": "internal"},
        ],
    },
    {
        "substance_type": "mab",
        "internal_code": "CMAB-016",
        "preferred_name": "度普利尤单抗类似药 (CMAB-016)",
        "preferred_name_en": "Dupilumab biosimilar (CMAB-016)",
        "target": "IL-4Rα",
        "target_type": "受体亚基",
        "modality": "human IgG4 mAb",
        "status": "active",
        "confidentiality": "restricted",
        "description": (
            "抗 IL-4Rα 全人源单抗，Dupixent® (dupilumab，原研 Regeneron/Sanofi) 类似药。"
            "IgG4-S228P 同种型；阻断 IL-4/IL-13 双信号通路。"
            "拟开发适应症：中重度特应性皮炎、哮喘、慢性鼻窦炎伴鼻息肉。"
        ),
        "protein": {
            "isotype": "IgG4",
            "expression_system": "CHO",
            "cell_line": "CHO-016",
            "molecular_weight_da": 147000.0,
        },
        "xrefs": [
            {"xref_type": "INN", "xref_value": "dupilumab", "xref_source": "WHO", "is_primary": True},
            {"xref_type": "CAS", "xref_value": "1190264-60-8", "xref_source": "CAS"},
            {"xref_type": "OTHER", "xref_value": "IL4R (HGNC gene symbol)", "xref_source": "HGNC"},
            {"xref_type": "PROJECT_CODE", "xref_value": "CMAB-016", "xref_source": "internal"},
        ],
    },
]


# =============================================================================
# 项目（PRS）：每个药按生物类似药 BLA 申报工作流分若干项目
# =============================================================================

REAL_PROJECTS = [
    # ---------------- CMAB-101 Denosumab ----------------
    {
        "name": "CMAB-101 CMC 工艺开发与放大",
        "name_en": "CMAB-101 CMC Development & Scale-up",
        "project_type": "cmc",
        "phase": "phase_3",
        "status": "completed",
        "therapeutic_area": "骨质疏松 / 肿瘤支持治疗",
        "indication": "类似药 CMC 全程",
        "planned_start_date": "2021-04-01",
        "planned_end_date": "2024-06-30",
        "actual_start_date": "2021-05-10",
        "actual_end_date": "2024-08-20",
        "owner_username": "qingcheng",
        "department": "CMC R&D",
        "description": "细胞株（MCB/WCB）+ 原液/制剂工艺开发与三批次工艺验证（PV）+ 工艺转移至商业化车间。",
        "milestones": [
            {"name": "细胞株锁定（MCB 制备）", "type": "gate", "planned_date": "2022-03-31", "actual_date": "2022-04-15", "status": "completed"},
            {"name": "工艺锁定（PPQ 启动）", "type": "gate", "planned_date": "2023-06-30", "actual_date": "2023-07-10", "status": "completed"},
            {"name": "工艺验证 PPQ 三批完成", "type": "deliverable", "planned_date": "2023-12-15", "actual_date": "2024-01-08", "status": "completed"},
            {"name": "稳定性 24 个月数据", "type": "deliverable", "planned_date": "2024-06-30", "actual_date": "2024-08-20", "status": "completed"},
        ],
        "team": [
            ("qingcheng", "PM"),
            ("qingcheng", "CMC Lead"),
            ("researcher", "Upstream Lead"),
            ("qa_reviewer", "QA Lead"),
        ],
        "link_substance": "CMAB-101",
        "link_relation": "primary",
    },
    {
        "name": "CMAB-101 临床等效性 III 期",
        "name_en": "CMAB-101 Phase III Equivalence Study",
        "project_type": "clinical",
        "phase": "phase_3",
        "status": "completed",
        "therapeutic_area": "骨质疏松",
        "indication": "绝经后女性骨质疏松（与原研 Prolia 头对头）",
        "planned_start_date": "2022-10-01",
        "planned_end_date": "2024-12-31",
        "actual_start_date": "2022-11-20",
        "actual_end_date": "2024-12-10",
        "owner_username": "qingcheng",
        "department": "Clinical",
        "description": "随机双盲对照头对头研究：12 个月主疗效终点（腰椎 BMD 变化率）+ PK/PD/安全性/免疫原性。",
        "milestones": [
            {"name": "Ph1 PK 等效完成", "type": "gate", "planned_date": "2022-06-30", "actual_date": "2022-07-15", "status": "completed"},
            {"name": "Ph3 首例入组", "type": "decision", "planned_date": "2022-11-30", "actual_date": "2022-12-05", "status": "completed"},
            {"name": "主疗效终点（12 个月）", "type": "deliverable", "planned_date": "2024-03-31", "actual_date": "2024-04-22", "status": "completed"},
            {"name": "临床总结报告（CSR）锁定", "type": "deliverable", "planned_date": "2024-09-30", "actual_date": "2024-11-18", "status": "completed"},
        ],
        "team": [
            ("qingcheng", "PM"),
            ("researcher", "Clinical Lead"),
            ("qa_reviewer", "QA Reviewer"),
        ],
        "link_substance": "CMAB-101",
        "link_relation": "primary",
    },
    {
        "name": "CMAB-101 NMPA 注册申报（BLA）",
        "name_en": "CMAB-101 NMPA BLA Submission",
        "project_type": "regulatory",
        "phase": "phase_3",
        "status": "active",
        "therapeutic_area": "骨质疏松 / 肿瘤支持治疗",
        "indication": "双适应症同时申报",
        "planned_start_date": "2025-01-01",
        "planned_end_date": "2026-12-31",
        "actual_start_date": "2025-02-10",
        "owner_username": "qingcheng",
        "department": "Regulatory",
        "description": "NMPA 生物制品 BLA 整合申报（M2-M5）；首轮发补响应进行中。",
        "milestones": [
            {"name": "Pre-BLA 沟通会", "type": "decision", "planned_date": "2024-12-15", "actual_date": "2024-12-20", "status": "completed"},
            {"name": "BLA 受理", "type": "gate", "planned_date": "2025-03-31", "actual_date": "2025-04-08", "status": "completed"},
            {"name": "首轮发补响应", "type": "deliverable", "planned_date": "2025-11-30", "actual_date": "2025-12-15", "status": "completed"},
            {"name": "现场核查（PAI）", "type": "decision", "planned_date": "2026-06-30", "status": "planned"},
            {"name": "NMPA 上市批准", "type": "decision", "planned_date": "2026-12-15", "status": "planned"},
        ],
        "team": [
            ("qingcheng", "PM"),
            ("qa_reviewer", "Reg Lead"),
        ],
        "link_substance": "CMAB-101",
        "link_relation": "primary",
    },

    # ---------------- CMAB-205 Pembrolizumab ----------------
    {
        "name": "CMAB-205 CMC 工艺开发",
        "name_en": "CMAB-205 CMC Development",
        "project_type": "cmc",
        "phase": "phase_2",
        "status": "completed",
        "therapeutic_area": "肿瘤免疫",
        "indication": "类似药 CMC 全程",
        "planned_start_date": "2022-08-01",
        "planned_end_date": "2024-12-31",
        "actual_start_date": "2022-09-12",
        "actual_end_date": "2024-12-05",
        "owner_username": "qingcheng",
        "department": "CMC R&D",
        "description": "高产量克隆筛选（>5 g/L 滴度目标）+ 工艺优化 + 制剂处方（100 mg/4 mL 浓溶液）。",
        "milestones": [
            {"name": "细胞株锁定（高产克隆）", "type": "gate", "planned_date": "2023-08-31", "actual_date": "2023-09-20", "status": "completed"},
            {"name": "Pilot 200L 工艺锁定", "type": "gate", "planned_date": "2024-05-31", "actual_date": "2024-06-18", "status": "completed"},
            {"name": "2000L 工艺转移完成", "type": "deliverable", "planned_date": "2024-12-15", "actual_date": "2024-12-30", "status": "completed"},
        ],
        "team": [
            ("qingcheng", "PM"),
            ("qingcheng", "CMC Lead"),
            ("researcher", "DSP Lead"),
        ],
        "link_substance": "CMAB-205",
        "link_relation": "primary",
    },
    {
        "name": "CMAB-205 临床 III 期头对头等效研究",
        "name_en": "CMAB-205 Phase III Head-to-Head Equivalence",
        "project_type": "clinical",
        "phase": "phase_3",
        "status": "active",
        "therapeutic_area": "肿瘤免疫",
        "indication": "晚期 NSCLC 一线（与 Keytruda 头对头）",
        "planned_start_date": "2025-03-01",
        "planned_end_date": "2027-12-31",
        "actual_start_date": "2025-04-15",
        "owner_username": "qingcheng",
        "department": "Clinical",
        "description": "随机双盲多中心对照研究 N=580，主终点 ORR，次要 PFS/OS/PK/免疫原性。",
        "milestones": [
            {"name": "Ph1 PK 桥接完成", "type": "gate", "planned_date": "2024-10-31", "actual_date": "2024-11-22", "status": "completed"},
            {"name": "Ph3 首例入组", "type": "decision", "planned_date": "2025-04-30", "actual_date": "2025-05-12", "status": "completed"},
            {"name": "入组完成（580 例）", "type": "decision", "planned_date": "2026-09-30", "status": "in_progress"},
            {"name": "主终点 ORR 读出", "type": "deliverable", "planned_date": "2027-03-31", "status": "planned"},
        ],
        "team": [
            ("qingcheng", "PM"),
            ("researcher", "Clinical Lead"),
            ("qa_reviewer", "Safety Reviewer"),
        ],
        "link_substance": "CMAB-205",
        "link_relation": "primary",
    },

    # ---------------- CMAB-016 Dupilumab ----------------
    {
        "name": "CMAB-016 早期 CMC 与细胞株开发",
        "name_en": "CMAB-016 Early CMC & Cell Line Development",
        "project_type": "cmc",
        "phase": "phase_1",
        "status": "active",
        "therapeutic_area": "免疫炎症（特应性皮炎）",
        "indication": "类似药 CMC 早期",
        "planned_start_date": "2025-06-01",
        "planned_end_date": "2027-06-30",
        "actual_start_date": "2025-07-08",
        "owner_username": "researcher",
        "department": "CMC R&D",
        "description": "宿主细胞株选育（CHO-K1 系列）+ 上游摇瓶筛选 + 早期下游工艺（IND 用工艺）。",
        "milestones": [
            {"name": "候选克隆筛选（Top10）", "type": "gate", "planned_date": "2025-12-31", "actual_date": "2026-01-10", "status": "completed"},
            {"name": "工程批 50L 完成", "type": "deliverable", "planned_date": "2026-08-31", "status": "in_progress"},
            {"name": "GLP 毒理批生产", "type": "decision", "planned_date": "2027-02-28", "status": "planned"},
        ],
        "team": [
            ("qingcheng", "PM"),
            ("researcher", "CMC Lead"),
            ("researcher", "USP Scientist"),
        ],
        "link_substance": "CMAB-016",
        "link_relation": "primary",
    },
    {
        "name": "CMAB-016 IND 申报与 Ph1 PK 桥接",
        "name_en": "CMAB-016 IND Filing & Phase I PK Bridging",
        "project_type": "regulatory",
        "phase": "phase_1",
        "status": "initiated",
        "therapeutic_area": "免疫炎症",
        "indication": "中重度特应性皮炎",
        "planned_start_date": "2026-09-01",
        "planned_end_date": "2028-06-30",
        "owner_username": "qingcheng",
        "department": "Regulatory",
        "description": "中国 IND 申报 + 健康志愿者 PK 等效桥接（与 Dupixent 头对头单剂量交叉）。",
        "milestones": [
            {"name": "Pre-IND 沟通", "type": "decision", "planned_date": "2026-12-31", "status": "planned"},
            {"name": "IND 受理", "type": "gate", "planned_date": "2027-04-30", "status": "planned"},
            {"name": "Ph1 首例给药", "type": "decision", "planned_date": "2027-08-31", "status": "planned"},
        ],
        "team": [
            ("qingcheng", "PM"),
            ("qa_reviewer", "Reg Lead"),
        ],
        "link_substance": "CMAB-016",
        "link_relation": "primary",
    },
]


# =============================================================================
# 资产（ARS）：剂型 / 包装规格层面
# =============================================================================

REAL_ASSETS = [
    # ---- CMAB-101：双适应症 双剂型 ----
    {
        "internal_name": "CMAB-101 注射液 60mg/1mL（骨质疏松）",
        "trade_name": None,  # 上市前不设
        "inn_name": "denosumab",
        "asset_type": "mab",
        "therapeutic_area": "骨质疏松",
        "indication": "绝经后女性骨质疏松、男性骨质疏松、糖皮质激素诱导骨流失",
        "dosage_form": "预充式注射器（PFS）",
        "strength": "60 mg / 1 mL",
        "route_of_administration": "皮下注射（每 6 个月一次）",
        "current_phase": "phase_3",
        "status": "active",
        "is_commercial": False,
        "description": "对标 Prolia® 规格；NMPA BLA 审评中。",
        "components": [
            {"substance_internal_code": "CMAB-101", "component_role": "main_component"},
        ],
        "projects": [
            {"project_name": "CMAB-101 NMPA 注册申报（BLA）", "relation_type": "primary"},
            {"project_name": "CMAB-101 临床等效性 III 期", "relation_type": "primary"},
        ],
    },
    {
        "internal_name": "CMAB-101 注射液 120mg/1.7mL（骨相关事件）",
        "trade_name": None,
        "inn_name": "denosumab",
        "asset_type": "mab",
        "therapeutic_area": "肿瘤支持治疗",
        "indication": "预防实体瘤骨转移导致的骨相关事件（SRE）+ 不可手术巨细胞瘤",
        "dosage_form": "西林瓶（Vial）",
        "strength": "120 mg / 1.7 mL",
        "route_of_administration": "皮下注射（每 4 周一次）",
        "current_phase": "phase_3",
        "status": "active",
        "is_commercial": False,
        "description": "对标 Xgeva® 规格；与 60mg 共享原液工艺，制剂差异化。",
        "components": [
            {"substance_internal_code": "CMAB-101", "component_role": "main_component"},
        ],
        "projects": [
            {"project_name": "CMAB-101 NMPA 注册申报（BLA）", "relation_type": "primary"},
        ],
    },

    # ---- CMAB-205：浓溶液静脉滴注 ----
    {
        "internal_name": "CMAB-205 注射用浓溶液 100mg/4mL",
        "trade_name": None,
        "inn_name": "pembrolizumab",
        "asset_type": "mab",
        "therapeutic_area": "肿瘤免疫",
        "indication": "晚期 NSCLC 一线、黑色素瘤、HNSCC、cHL 等（拟同步申报）",
        "dosage_form": "注射用浓溶液（输液稀释）",
        "strength": "100 mg / 4 mL",
        "route_of_administration": "静脉滴注（30 分钟，每 3 周一次）",
        "current_phase": "phase_3",
        "status": "active",
        "is_commercial": False,
        "description": "对标 Keytruda® 100mg/4mL；高浓度处方降低输注体积。",
        "components": [
            {"substance_internal_code": "CMAB-205", "component_role": "main_component"},
        ],
        "projects": [
            {"project_name": "CMAB-205 临床 III 期头对头等效研究", "relation_type": "primary"},
            {"project_name": "CMAB-205 CMC 工艺开发", "relation_type": "primary"},
        ],
    },

    # ---- CMAB-016：预充注射器皮下注射 ----
    {
        "internal_name": "CMAB-016 注射液 300mg/2mL",
        "trade_name": None,
        "inn_name": "dupilumab",
        "asset_type": "mab",
        "therapeutic_area": "免疫炎症",
        "indication": "中重度特应性皮炎；后续扩展哮喘、慢鼻窦炎伴鼻息肉",
        "dosage_form": "预充式注射器（PFS）",
        "strength": "300 mg / 2 mL",
        "route_of_administration": "皮下注射（每 2 周一次）",
        "current_phase": "phase_1",
        "status": "active",
        "is_commercial": False,
        "description": "对标 Dupixent® 300mg PFS 规格；早期 CMC 阶段。",
        "components": [
            {"substance_internal_code": "CMAB-016", "component_role": "main_component"},
        ],
        "projects": [
            {"project_name": "CMAB-016 早期 CMC 与细胞株开发", "relation_type": "primary"},
        ],
    },
]


async def main() -> None:
    # monkey-patch seed_data 模块级常量，复用既有 seed_demo_data 函数
    seed_data.DEMO_SUBSTANCES = REAL_SUBSTANCES
    seed_data.DEMO_PROJECTS = REAL_PROJECTS
    seed_data.DEMO_ASSETS = REAL_ASSETS
    seed_data.DEMO_MATERIALS = []  # 本次不加物料；如有需要后续单独加

    async with AsyncSessionLocal() as db:
        await seed_data.seed_demo_data(db)
        await db.commit()

    logger.info(
        f"✓ 真实 demo 装入完成："
        f"{len(REAL_SUBSTANCES)} 物质 + {len(REAL_PROJECTS)} 项目 + {len(REAL_ASSETS)} 资产"
    )


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception as e:
        logger.exception("种子失败")
        sys.exit(1)
