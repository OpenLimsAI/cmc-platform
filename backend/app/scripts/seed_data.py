"""
种子数据脚本：创建初始角色、权限、测试用户、示例 substance
仅在 dev/test 环境运行。

CLI：
  python -m app.scripts.seed_data           # 仅 baseline（权限/角色/用户 + 4 个示例 substance）
  python -m app.scripts.seed_data --demo    # baseline + 演示数据集（项目/里程碑/团队/物质绑定）
"""
import argparse
import asyncio
import hashlib
import re
import sys
from datetime import date

from loguru import logger
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import AsyncSessionLocal, engine
from app.core.security import hash_password
from app.domains.ars.models import Asset, AssetMarketId
from app.domains.auth.models import (
    Permission,
    Role,
    RolePermission,
    User,
    UserRole,
)
from app.domains.mm.models import Material, MaterialBatch
from app.domains.prs.models import (
    Project,
    ProjectMilestone,
    ProjectTeam,
)
from app.domains.ref.models import (
    AssetSubstanceLink,
    ProjectAssetLink,
    ProjectSubstanceLink,
)
from app.domains.srs.models import Substance, SubstanceProtein, SubstanceXref


def _hash_seq(seq: str | None) -> str | None:
    if not seq:
        return None
    cleaned = re.sub(r"[^A-Z]", "", seq.upper())
    return hashlib.sha256(cleaned.encode()).hexdigest() if cleaned else None


# ============== 数据定义 ==============
PERMISSIONS = [
    ("substance:create", "substance", "create", "创建物质"),
    ("substance:read", "substance", "read", "查询物质"),
    ("substance:update", "substance", "update", "更新物质"),
    ("substance:approve", "substance", "approve", "审核物质"),
    ("substance:sign", "substance", "sign", "物质电子签名"),
    ("project:create", "project", "create", "创建项目"),
    ("project:read", "project", "read", "查询项目"),
    ("project:update", "project", "update", "更新项目"),
    ("project:approve", "project", "approve", "审核项目"),
    ("project:sign", "project", "sign", "项目电子签名"),
    ("asset:create", "asset", "create", "创建资产"),
    ("asset:read", "asset", "read", "查询资产"),
    ("asset:update", "asset", "update", "更新资产"),
    ("asset:sign", "asset", "sign", "资产电子签名"),
    ("material:create", "material", "create", "创建物料"),
    ("material:read", "material", "read", "查询物料"),
    ("material:update", "material", "update", "更新物料"),
    ("equipment:create", "equipment", "create", "创建设备"),
    ("equipment:read", "equipment", "read", "查询设备"),
    ("equipment:update", "equipment", "update", "更新设备"),
    ("audit:read", "audit", "read", "查询审计日志"),
    ("user:manage", "user", "manage", "用户管理"),
    ("role:manage", "role", "manage", "角色管理"),
]

ROLES = [
    ("SYS_ADMIN", "系统管理员", "全权限，仅限 IT", "ALL"),
    ("SUBSTANCE_STEWARD", "物质数据管家",
     "Substance 域审核、合并、状态变更；跨域只读（项目/资产/物料模块可见性，对齐 UI §2.2 权限矩阵）",
     ["substance:read", "substance:update", "substance:approve", "substance:sign", "audit:read",
      "project:read", "asset:read", "material:read"]),
    ("PROJECT_MANAGER", "项目经理", "Project 域全权限",
     ["substance:read", "project:create", "project:read", "project:update", "project:approve",
      "project:sign", "asset:create", "asset:read", "asset:update", "asset:sign", "material:read"]),
    ("CMC_RESEARCHER", "研发人员", "物质/项目读写",
     ["substance:create", "substance:read", "substance:update",
      "project:read", "project:update", "asset:read", "material:create", "material:read",
      "material:update", "equipment:read"]),
    ("QA_REVIEWER", "质量审核", "电子签名权限",
     ["substance:read", "substance:sign", "project:read", "project:sign",
      "asset:read", "asset:sign", "material:read", "audit:read"]),
    ("READ_ONLY_USER", "只读用户", "仅可查询",
     ["substance:read", "project:read", "asset:read", "material:read", "equipment:read"]),
    ("CMC_WAREHOUSE_ADMIN", "库管员",
     "物料主数据读写；同时是 LabOps 物料模块写权限角色(随 JWT 下发)",
     ["material:create", "material:read", "material:update", "equipment:read"]),
    ("CMC_EQUIPMENT_ADMIN", "设备管理员",
     "设备主数据读写；同时是 LabOps 设备模块写权限角色(随 JWT 下发)",
     ["equipment:create", "equipment:read", "equipment:update", "material:read"]),
]

USERS = [
    {"username": "admin", "password": "__REDACTED_SEED_PASSWORD_1__",
     "email": "admin@cmab.com", "full_name": "系统管理员",
     "department": "IT", "title": "Admin",
     "roles": ["SYS_ADMIN"]},
    {"username": "qingcheng", "password": "__REDACTED_SEED_PASSWORD_2__",
     "email": "qingcheng@cmab.com", "full_name": "李清城",
     "full_name_en": "Li Qingcheng",
     "department": "CMC R&D", "title": "CMC Head",
     "roles": ["SUBSTANCE_STEWARD", "PROJECT_MANAGER"]},
    {"username": "researcher", "password": "__REDACTED_SEED_PASSWORD_5__",
     "email": "researcher@cmab.com", "full_name": "王研究",
     "department": "CMC R&D", "title": "Senior Scientist",
     "roles": ["CMC_RESEARCHER"]},
    {"username": "qa_reviewer", "password": "__REDACTED_SEED_PASSWORD_3__",
     "email": "qa@cmab.com", "full_name": "赵质量",
     "department": "QA", "title": "QA Manager",
     "roles": ["QA_REVIEWER"]},
    {"username": "readonly", "password": "__REDACTED_SEED_PASSWORD_4__",
     "email": "readonly@cmab.com", "full_name": "只读用户",
     "department": "Other", "title": "Viewer",
     "roles": ["READ_ONLY_USER"]},
]

SAMPLE_SUBSTANCES = [
    {
        "substance_type": "mab",
        "internal_code": "CMAB-101",
        "preferred_name": "Anti-HER2 mAb (biosimilar)",
        "preferred_name_en": "Anti-HER2 monoclonal antibody",
        "target": "HER2",
        "target_type": "受体",
        "modality": "humanized IgG1 mAb",
        "status": "active",
        "confidentiality": "internal",
        "description": "公司首个商业化单抗（曲妥珠单抗生物类似药）",
        "protein": {
            "isotype": "IgG1",
            "expression_system": "CHO-K1",
            "cell_line": "CHO-K1-101",
            "molecular_weight_da": 145531.5,
            "heavy_chain_sequence": "EVQLVESGGGLVQPGGSLRLSCAASGFNIKDTYIHWVRQAPGKGLEWVARIYPTNGYTRYADSVKGRFTISADTSKNTAYLQMNSLRAEDTAVYYCSRWGGDGFYAMDYWGQGTLVTVSS",
            "light_chain_sequence": "DIQMTQSPSSLSASVGDRVTITCRASQDVNTAVAWYQQKPGKAPKLLIYSASFLYSGVPSRFSGSRSGTDFTLTISSLQPEDFATYYCQQHYTTPPTFGQGTKVEIK",
        },
        "xrefs": [
            {"xref_type": "INN", "xref_value": "trastuzumab biosimilar", "xref_source": "WHO", "is_primary": True},
            {"xref_type": "CAS", "xref_value": "180288-69-1", "xref_source": "CAS"},
        ],
    },
    {
        "substance_type": "mab",
        "internal_code": "CMAB-203",
        "preferred_name": "Anti-PD-L1 mAb",
        "preferred_name_en": "Anti-PD-L1 monoclonal antibody",
        "target": "PD-L1",
        "target_type": "受体",
        "modality": "humanized IgG1 mAb",
        "status": "active",
        "confidentiality": "restricted",
        "description": "针对实体瘤的人源化 IgG1 抗 PD-L1 单抗",
        "protein": {
            "isotype": "IgG1",
            "expression_system": "CHO-K1",
            "molecular_weight_da": 148000.5,
        },
        "xrefs": [
            {"xref_type": "PROJECT_CODE", "xref_value": "CMAB-203-PJ", "xref_source": "internal"},
        ],
    },
    {
        "substance_type": "bispecific",
        "internal_code": "CMAB-301",
        "preferred_name": "Bispecific HER2 x CD3",
        "target": "HER2 x CD3",
        "target_type": "受体",
        "modality": "BiTE-like bispecific",
        "status": "draft",
        "confidentiality": "restricted",
        "description": "在研双特异性抗体，靶向 HER2 阳性肿瘤细胞与 T 细胞",
    },
    {
        "substance_type": "adc",
        "internal_code": "CMAB-401",
        "preferred_name": "HER2-ADC (DXd)",
        "target": "HER2",
        "modality": "Antibody-drug conjugate",
        "status": "registered",
        "confidentiality": "restricted",
        "description": "HER2-ADC，参考 Enhertu 类似设计",
    },
]


async def seed_permissions(db: AsyncSession):
    logger.info("Seeding permissions...")
    for code, resource, action, desc in PERMISSIONS:
        existing = await db.execute(
            select(Permission).where(Permission.permission_code == code)
        )
        if existing.scalar_one_or_none():
            continue
        db.add(Permission(
            permission_code=code, resource=resource,
            action=action, description=desc, is_system=True,
        ))
    await db.flush()


async def seed_roles(db: AsyncSession):
    logger.info("Seeding roles & role-permissions...")
    perm_result = await db.execute(select(Permission))
    perm_map = {p.permission_code: p.permission_id for p in perm_result.scalars()}

    for role_code, role_name, desc, perm_codes in ROLES:
        existing = await db.execute(
            select(Role).where(Role.role_code == role_code)
        )
        role = existing.scalar_one_or_none()
        if not role:
            role = Role(role_code=role_code, role_name=role_name,
                        description=desc, is_system=True)
            db.add(role)
            await db.flush()

        # 关联权限
        if perm_codes == "ALL":
            target_codes = list(perm_map.keys())
        else:
            target_codes = perm_codes

        for code in target_codes:
            pid = perm_map.get(code)
            if not pid:
                continue
            existing_rp = await db.execute(
                select(RolePermission).where(
                    RolePermission.role_id == role.role_id,
                    RolePermission.permission_id == pid,
                )
            )
            if not existing_rp.scalar_one_or_none():
                db.add(RolePermission(role_id=role.role_id, permission_id=pid))
    await db.flush()


async def seed_users(db: AsyncSession):
    logger.info("Seeding users...")
    role_result = await db.execute(select(Role))
    role_map = {r.role_code: r.role_id for r in role_result.scalars()}

    for u in USERS:
        existing = await db.execute(
            select(User).where(User.username == u["username"])
        )
        user = existing.scalar_one_or_none()
        if user:
            continue

        user = User(
            username=u["username"],
            email=u["email"],
            password_hash=hash_password(u["password"]),
            full_name=u["full_name"],
            full_name_en=u.get("full_name_en"),
            department=u.get("department"),
            title=u.get("title"),
            status="active",
        )
        db.add(user)
        await db.flush()

        for role_code in u["roles"]:
            rid = role_map.get(role_code)
            if rid:
                db.add(UserRole(user_id=user.user_id, role_id=rid))
    await db.flush()


async def seed_substances(db: AsyncSession):
    logger.info("Seeding sample substances...")
    # 取 admin 用户 ID 作为创建人
    admin_result = await db.execute(select(User).where(User.username == "admin"))
    admin = admin_result.scalar_one()

    for s in SAMPLE_SUBSTANCES:
        existing = await db.execute(
            select(Substance).where(Substance.internal_code == s["internal_code"])
        )
        if existing.scalar_one_or_none():
            continue

        # 调用编码生成函数
        code_result = await db.execute(text("SELECT meta.fn_next_code('substance')"))
        code = code_result.scalar_one()

        sub = Substance(
            substance_code=code,
            substance_type=s["substance_type"],
            internal_code=s["internal_code"],
            preferred_name=s["preferred_name"],
            preferred_name_en=s.get("preferred_name_en"),
            target=s.get("target"),
            target_type=s.get("target_type"),
            modality=s.get("modality"),
            status=s.get("status", "draft"),
            confidentiality=s.get("confidentiality", "internal"),
            description=s.get("description"),
            created_by=admin.user_id,
            updated_by=admin.user_id,
        )
        db.add(sub)
        await db.flush()

        if s.get("protein"):
            p = s["protein"]
            hc, lc = p.get("heavy_chain_sequence"), p.get("light_chain_sequence")
            db.add(SubstanceProtein(
                substance_id=sub.substance_id,
                heavy_chain_sequence=hc,
                light_chain_sequence=lc,
                sequence_length_hc=len(re.sub(r"[^A-Z]", "", (hc or "").upper())) or None,
                sequence_length_lc=len(re.sub(r"[^A-Z]", "", (lc or "").upper())) or None,
                sequence_hash_hc=_hash_seq(hc),
                sequence_hash_lc=_hash_seq(lc),
                isotype=p.get("isotype"),
                expression_system=p.get("expression_system"),
                cell_line=p.get("cell_line"),
                molecular_weight_da=p.get("molecular_weight_da"),
            ))

        for x in s.get("xrefs", []):
            db.add(SubstanceXref(
                substance_id=sub.substance_id,
                xref_type=x["xref_type"],
                xref_value=x["xref_value"],
                xref_source=x.get("xref_source"),
                is_primary=x.get("is_primary", False),
                created_by=admin.user_id,
                updated_by=admin.user_id,
            ))
    await db.flush()


# ============== 演示数据（--demo 启用）==============
# 命名约定：物质用 CMAB-D## internal_code；项目名以 [DEMO] 前缀做幂等识别。
# 数据风格力求贴近真实 CMC 业务（PD-1/TIGIT/HER2/CD3/KRAS 都是当前热门靶点）。

DEMO_SUBSTANCES = [
    {
        "substance_type": "mab",
        "internal_code": "CMAB-D01",
        "preferred_name": "Anti-PD-1 mAb (CMAB-D01)",
        "preferred_name_en": "Anti-PD-1 monoclonal antibody",
        "target": "PD-1",
        "target_type": "免疫检查点",
        "modality": "humanized IgG4 mAb",
        "status": "active",
        "confidentiality": "restricted",
        "description": "公司自研抗 PD-1 单抗，IgG4 骨架降低 ADCC",
        "protein": {
            "isotype": "IgG4",
            "expression_system": "CHO-K1",
            "cell_line": "CHO-K1-D01",
            "molecular_weight_da": 146300.0,
        },
        "xrefs": [
            {"xref_type": "INN", "xref_value": "cmabolimab", "xref_source": "internal", "is_primary": True},
            {"xref_type": "PROJECT_CODE", "xref_value": "CMAB-D01-PJ", "xref_source": "internal"},
        ],
    },
    {
        "substance_type": "mab",
        "internal_code": "CMAB-D02",
        "preferred_name": "Anti-TIGIT mAb (CMAB-D02)",
        "preferred_name_en": "Anti-TIGIT monoclonal antibody",
        "target": "TIGIT",
        "target_type": "免疫检查点",
        "modality": "humanized IgG1 mAb",
        "status": "registered",
        "confidentiality": "restricted",
        "description": "抗 TIGIT 单抗，与抗 PD-1 联用的免疫治疗组合方向",
        "protein": {
            "isotype": "IgG1",
            "expression_system": "CHO-K1",
            "molecular_weight_da": 147800.0,
        },
        "xrefs": [
            {"xref_type": "INN", "xref_value": "cmtigib", "xref_source": "internal", "is_primary": True},
        ],
    },
    {
        "substance_type": "bispecific",
        "internal_code": "CMAB-D03",
        "preferred_name": "CD19 x CD3 BiTE (CMAB-D03)",
        "preferred_name_en": "CD19 x CD3 bispecific T-cell engager",
        "target": "CD19 x CD3",
        "target_type": "肿瘤靶 / T 细胞激活",
        "modality": "BiTE-like bispecific",
        "status": "draft",
        "confidentiality": "restricted",
        "description": "针对 B 细胞白血病的 CD19/CD3 双特异性 T 细胞衔接器",
    },
    {
        "substance_type": "adc",
        "internal_code": "CMAB-D04",
        "preferred_name": "HER2-DXd ADC (CMAB-D04)",
        "preferred_name_en": "HER2 antibody-drug conjugate (DXd)",
        "target": "HER2",
        "target_type": "受体",
        "modality": "Antibody-drug conjugate",
        "status": "registered",
        "confidentiality": "restricted",
        "description": "HER2 靶向 ADC，使用拓扑异构酶抑制剂 DXd 作为弹头",
        "xrefs": [
            {"xref_type": "PROJECT_CODE", "xref_value": "CMAB-D04-PJ", "xref_source": "internal"},
        ],
    },
    {
        "substance_type": "small_molecule",
        "internal_code": "CMAB-D05",
        "preferred_name": "KRAS G12C inhibitor (CMAB-D05)",
        "preferred_name_en": "Covalent KRAS G12C inhibitor",
        "target": "KRAS G12C",
        "target_type": "致癌驱动突变",
        "modality": "Small molecule (covalent)",
        "status": "draft",
        "confidentiality": "restricted",
        "description": "针对 KRAS G12C 突变的共价小分子抑制剂",
        "xrefs": [
            {"xref_type": "CAS", "xref_value": "DEMO-KRAS-CAS", "xref_source": "internal"},
        ],
    },
    {
        "substance_type": "fusion",
        "internal_code": "CMAB-D06",
        "preferred_name": "CTLA4-Ig fusion (CMAB-D06)",
        "preferred_name_en": "CTLA4-Fc fusion protein",
        "target": "CD80 / CD86",
        "target_type": "免疫调节",
        "modality": "Fc fusion protein",
        "status": "active",
        "confidentiality": "internal",
        "description": "CTLA4-Fc 融合蛋白（参考 abatacept 类设计）",
        "protein": {
            "isotype": "IgG1",
            "expression_system": "CHO-K1",
            "molecular_weight_da": 92300.0,
        },
    },
]

# 项目：每个项目以 [DEMO] 前缀作幂等识别
DEMO_PROJECTS = [
    {
        "name": "[DEMO] Anti-PD-1 CMC 开发",
        "name_en": "Anti-PD-1 CMC Development",
        "project_type": "cmc",
        "phase": "phase_2",
        "status": "active",
        "therapeutic_area": "肿瘤",
        "indication": "非小细胞肺癌（NSCLC）/ 黑色素瘤",
        "planned_start_date": "2025-01-15",
        "planned_end_date": "2027-06-30",
        "actual_start_date": "2025-03-01",
        "owner_username": "qingcheng",
        "description": "CMAB-D01 的 CMC 开发主项目，覆盖工艺优化、放大、稳定性研究",
        "milestones": [
            {"name": "GMP 生产用细胞株锁定", "type": "gate", "planned_date": "2025-06-30", "actual_date": "2025-07-12", "status": "completed"},
            {"name": "IND 申报", "type": "decision", "planned_date": "2025-12-15", "actual_date": "2025-12-20", "status": "completed"},
            {"name": "Ph2 首例患者给药", "type": "decision", "planned_date": "2026-04-01", "actual_date": "2026-04-15", "status": "completed"},
            {"name": "中期数据读出", "type": "deliverable", "planned_date": "2026-12-01", "status": "planned"},
        ],
        "team": [
            ("qingcheng", "PM"),
            ("qingcheng", "CMC Lead"),
            ("researcher", "Research"),
            ("qa_reviewer", "QA Lead"),
        ],
        "link_substance": "CMAB-D01",
        "link_relation": "primary",
    },
    {
        "name": "[DEMO] Anti-TIGIT 临床开发",
        "name_en": "Anti-TIGIT Clinical Development",
        "project_type": "clinical",
        "phase": "phase_1",
        "status": "active",
        "therapeutic_area": "肿瘤",
        "indication": "实体瘤（联合抗 PD-1）",
        "planned_start_date": "2025-09-01",
        "planned_end_date": "2027-12-31",
        "actual_start_date": "2025-10-10",
        "owner_username": "qingcheng",
        "description": "CMAB-D02 的 Ph1 单药+联合用药剂量爬坡",
        "milestones": [
            {"name": "preIND 沟通", "type": "decision", "planned_date": "2025-08-15", "actual_date": "2025-08-20", "status": "completed"},
            {"name": "IND 批准", "type": "decision", "planned_date": "2025-12-30", "actual_date": "2026-01-10", "status": "completed"},
            {"name": "Ph1 剂量爬坡完成", "type": "decision", "planned_date": "2026-09-01", "status": "planned"},
        ],
        "team": [
            ("qingcheng", "PM"),
            ("researcher", "Clinical Lead"),
        ],
        "link_substance": "CMAB-D02",
        "link_relation": "primary",
    },
    {
        "name": "[DEMO] CD19xCD3 双抗发现",
        "name_en": "CD19xCD3 Bispecific Discovery",
        "project_type": "preclinical",  # §9.2 收敛：discovery → preclinical
        "phase": "discovery",
        "status": "proposed",  # §9.2 draft → proposed
        "therapeutic_area": "血液肿瘤",
        "indication": "复发难治 B-ALL",
        "planned_start_date": "2026-02-01",
        "planned_end_date": "2027-06-30",
        "owner_username": "researcher",
        "department": "CMC R&D",
        "description": "候选先导分子筛选与亲和力优化",
        "milestones": [
            {"name": "候选先导分子选定", "type": "gate", "planned_date": "2026-06-30", "status": "planned"},
            {"name": "毒理研究启动", "type": "decision", "planned_date": "2026-11-01", "status": "planned"},
        ],
        "team": [
            ("researcher", "PM"),
            ("researcher", "Research"),
        ],
        "link_substance": "CMAB-D03",
        "link_relation": "primary",
    },
    {
        "name": "[DEMO] KRAS G12C 小分子早期发现",
        "name_en": "KRAS G12C Small Molecule Early Discovery",
        "project_type": "preclinical",
        "phase": "discovery",
        "status": "initiated",  # planned → initiated
        "therapeutic_area": "肿瘤",
        "indication": "KRAS G12C+ NSCLC / 结直肠癌",
        "planned_start_date": "2026-06-01",
        "planned_end_date": "2028-12-31",
        "owner_username": "researcher",
        "department": "CMC R&D",
        "description": "针对 KRAS G12C 共价抑制剂的化学优化",
        "milestones": [
            {"name": "苗头化合物筛选", "type": "gate", "planned_date": "2026-12-01", "status": "planned"},
        ],
        "team": [
            ("researcher", "PM"),
        ],
        "link_substance": "CMAB-D05",
        "link_relation": "primary",
    },
]


# 资产：每个以 internal_name 作幂等识别
# 跨域绑定：
#   - asset_substance：用 substance_internal_code 指向 DEMO_SUBSTANCES 里的物质
#   - project_asset：用 project_name 指向 DEMO_PROJECTS 里的项目
DEMO_ASSETS = [
    {
        "internal_name": "[DEMO] Anti-PD-1 注射液",
        "trade_name": "Cmaboline",
        "inn_name": "cmabolimab",
        "asset_type": "mab",
        "therapeutic_area": "肿瘤",
        "indication": "晚期非小细胞肺癌（NSCLC）一线、黑色素瘤",
        "dosage_form": "冻干粉针",
        "strength": "100 mg/瓶",
        "route_of_administration": "静脉注射",
        "current_phase": "marketed",
        "status": "active",
        "is_commercial": True,
        "first_approval_date": "2025-12-20",
        "first_launch_date": "2026-02-01",
        "description": "公司首款 PD-1 抑制剂上市产品（NMPA 批准）",
        "market_ids": [
            {
                "market_code": "CN",
                "id_type": "NMPA_APPROVAL",
                "id_value": "国药准字 S20260001",
                "issuing_authority": "NMPA",
                "application_date": "2025-12-15",
                "approval_date": "2025-12-20",
                "status": "approved",
            },
        ],
        "components": [
            {"substance_internal_code": "CMAB-D01", "component_role": "main_component"},
        ],
        "projects": [
            {"project_name": "[DEMO] Anti-PD-1 CMC 开发", "relation_type": "primary"},
        ],
    },
    {
        "internal_name": "[DEMO] Anti-TIGIT 注射液",
        "trade_name": None,
        "inn_name": "cmtigib",
        "asset_type": "mab",
        "therapeutic_area": "肿瘤",
        "indication": "实体瘤（拟联合 PD-1 治疗）",
        "dosage_form": "注射液",
        "strength": "200 mg/瓶",
        "route_of_administration": "静脉注射",
        "current_phase": "phase_1",
        "status": "active",
        "is_commercial": False,
        "description": "TIGIT 抑制剂候选药物，临床早期",
        "components": [
            {"substance_internal_code": "CMAB-D02", "component_role": "main_component"},
        ],
        "projects": [
            {"project_name": "[DEMO] Anti-TIGIT 临床开发", "relation_type": "primary"},
        ],
    },
    {
        "internal_name": "[DEMO] CD19xCD3 BiTE",
        "asset_type": "bispecific",
        "therapeutic_area": "血液肿瘤",
        "indication": "复发难治 B-ALL",
        "current_phase": "discovery",
        "status": "active",
        "is_commercial": False,
        "description": "CD19/CD3 双抗早期发现",
        "components": [
            {"substance_internal_code": "CMAB-D03", "component_role": "main_component"},
        ],
        "projects": [
            {"project_name": "[DEMO] CD19xCD3 双抗发现", "relation_type": "primary"},
        ],
    },
    {
        "internal_name": "[DEMO] HER2-DXd ADC",
        "trade_name": None,
        "inn_name": None,
        "asset_type": "adc",
        "therapeutic_area": "肿瘤",
        "indication": "HER2 阳性乳腺癌、胃癌",
        "dosage_form": "冻干粉针",
        "strength": "100 mg/瓶",
        "route_of_administration": "静脉注射",
        "current_phase": "phase_3",
        "status": "active",
        "is_commercial": False,
        "description": "HER2 靶向抗体偶联药物（DXd 弹头），Ph3 数据读出阶段",
        "components": [
            {"substance_internal_code": "CMAB-D04", "component_role": "main_component"},
        ],
    },
]


# 物料：每个以 (material_name) 作幂等识别（material_code 由触发器分配，幂等用 name）
# 跨域绑定：substance_internal_code → DEMO_SUBSTANCES 中的物质
DEMO_MATERIALS = [
    {
        "material_code": "R-0001",
        "material_name": "[DEMO] PBS 10× 缓冲液",
        "material_name_en": "PBS 10x Buffer",
        "material_type": "reagent",
        "category": "试剂",
        "grade": "GR",
        "unit": "瓶",
        "manufacturer": "Gibco / Thermo Fisher",
        "catalog_no": "70011-044",
        "package_spec": "500 mL/瓶",
        "physical_form": "solution",
        "storage_condition": "2-8°C",
        "source_type": "vendor",
        "source_name": "Gibco / Thermo Fisher",
        "description": "10 倍浓缩磷酸盐缓冲液，用于细胞培养与制剂配制",
        "batches": [
            {
                "batch_number": "GIBCO-2026-PBS-A01",
                "quantity_value": "500",
                "quantity_unit": "mL",
                "manufacture_date": "2026-01-10",
                "expiry_date": "2027-06-10",
                "receive_date": "2026-02-01",
                "source_batch_ref": "Lot 2481003",
                "storage_location": "BLDG-1 Cold Room 01",
                "status": "in_stock",
            },
        ],
    },
    {
        "material_code": "C-0001",
        "material_name": "[DEMO] 0.22 μm PES 过滤膜",
        "material_name_en": "0.22 um PES Membrane Filter",
        "material_type": "consumable",
        "category": "一般耗材",
        "unit": "盒",
        "manufacturer": "Millipore",
        "catalog_no": "SLGP033RS",
        "package_spec": "50 片/盒",
        "physical_form": "membrane",
        "storage_condition": "RT (15-25°C)",
        "source_type": "vendor",
        "source_name": "Millipore / Merck",
        "description": "无菌 PES 针头式过滤器，0.22 μm 孔径",
        "batches": [
            {
                "batch_number": "MPE-2026-F01",
                "quantity_value": "3",
                "quantity_unit": "盒",
                "receive_date": "2026-03-15",
                "storage_location": "BLDG-2 Consumable Store",
                "status": "in_stock",
            },
        ],
    },
    {
        "material_code": "S-0001",
        "material_name": "[DEMO] USP Anti-PD-1 参比标准品",
        "material_name_en": "USP Anti-PD-1 Reference Standard",
        "material_type": "standard",
        "category": "参比品",
        "grade": "USP Reference Standard",
        "unit": "瓶",
        "manufacturer": "USP",
        "catalog_no": "1234567",
        "package_spec": "1 mg/vial",
        "physical_form": "lyophilized",
        "storage_condition": "2-8°C",
        "source_type": "vendor",
        "source_name": "USP Store",
        "substance_internal_code": "CMAB-D01",
        "description": "美国药典抗PD-1参比标准品，用于含量与效价测定",
        "batches": [
            {
                "batch_number": "RS-USP-2026-01",
                "quantity_value": "5",
                "quantity_unit": "vial",
                "manufacture_date": "2025-06-01",
                "expiry_date": "2027-06-01",
                "receive_date": "2026-01-10",
                "source_batch_ref": "USP-LOT-2025-PD1",
                "storage_location": "BLDG-2 RS-cabinet-01",
                "status": "in_stock",
            },
        ],
    },
    {
        "material_code": "COL-0001",
        "material_name": "[DEMO] Waters XBridge C18 色谱柱",
        "material_name_en": "Waters XBridge C18 HPLC Column",
        "material_type": "column",
        "category": "关键耗材",
        "unit": "根",
        "manufacturer": "Waters",
        "catalog_no": "186003117",
        "spec_model": "4.6×250 mm, 5 μm",
        "package_spec": "1 根/盒",
        "storage_condition": "RT (15-25°C)",
        "source_type": "vendor",
        "source_name": "Waters China",
        "description": "反相 C18 液相色谱柱，用于蛋白纯度分析",
        "batches": [
            {
                "batch_number": "COL-W-2026-001",
                "quantity_value": "1",
                "quantity_unit": "根",
                "receive_date": "2026-04-01",
                "storage_location": "HPLC Lab Column Cabinet",
                "status": "in_use",
            },
        ],
    },
]


async def seed_demo_data(db: AsyncSession):
    """演示数据集：物质 + 项目 + 里程碑 + 团队 + 资产 + 物料 + 跨域绑定"""
    logger.info("Seeding demo data (--demo)...")

    # 1) 物质（DEMO_SUBSTANCES）
    admin_result = await db.execute(select(User).where(User.username == "admin"))
    admin = admin_result.scalar_one()

    sub_code_by_internal: dict[str, tuple[int, str]] = {}  # internal_code → (substance_id, substance_code)
    for s in DEMO_SUBSTANCES:
        existing = await db.execute(
            select(Substance).where(Substance.internal_code == s["internal_code"])
        )
        sub = existing.scalar_one_or_none()
        if sub:
            sub_code_by_internal[s["internal_code"]] = (sub.substance_id, sub.substance_code)
            continue

        code_result = await db.execute(text("SELECT meta.fn_next_code('substance')"))
        code = code_result.scalar_one()
        sub = Substance(
            substance_code=code,
            substance_type=s["substance_type"],
            internal_code=s["internal_code"],
            preferred_name=s["preferred_name"],
            preferred_name_en=s.get("preferred_name_en"),
            target=s.get("target"),
            target_type=s.get("target_type"),
            modality=s.get("modality"),
            status=s.get("status", "draft"),
            confidentiality=s.get("confidentiality", "internal"),
            description=s.get("description"),
            created_by=admin.user_id,
            updated_by=admin.user_id,
        )
        db.add(sub)
        await db.flush()

        if s.get("protein"):
            p = s["protein"]
            hc, lc = p.get("heavy_chain_sequence"), p.get("light_chain_sequence")
            db.add(SubstanceProtein(
                substance_id=sub.substance_id,
                heavy_chain_sequence=hc,
                light_chain_sequence=lc,
                sequence_length_hc=len(re.sub(r"[^A-Z]", "", (hc or "").upper())) or None,
                sequence_length_lc=len(re.sub(r"[^A-Z]", "", (lc or "").upper())) or None,
                sequence_hash_hc=_hash_seq(hc),
                sequence_hash_lc=_hash_seq(lc),
                isotype=p.get("isotype"),
                expression_system=p.get("expression_system"),
                cell_line=p.get("cell_line"),
                molecular_weight_da=p.get("molecular_weight_da"),
            ))

        for x in s.get("xrefs", []):
            db.add(SubstanceXref(
                substance_id=sub.substance_id,
                xref_type=x["xref_type"],
                xref_value=x["xref_value"],
                xref_source=x.get("xref_source"),
                is_primary=x.get("is_primary", False),
                created_by=admin.user_id,
                updated_by=admin.user_id,
            ))
        await db.flush()
        sub_code_by_internal[s["internal_code"]] = (sub.substance_id, sub.substance_code)

    # 2) 用户名 → user_id 映射（用于 owner / team / link）
    user_result = await db.execute(select(User))
    user_by_name = {u.username: u for u in user_result.scalars()}

    # 3) 项目 + 里程碑 + 团队 + 跨域 link
    for proj_def in DEMO_PROJECTS:
        existing_proj = await db.execute(
            select(Project).where(Project.project_name == proj_def["name"])
        )
        proj = existing_proj.scalar_one_or_none()
        if not proj:
            # 按年序列 (§9.2)
            code_result = await db.execute(
                text(
                    "SELECT meta.fn_next_code("
                    "meta.fn_ensure_year_sequence('project', 'PRJ-', "
                    "EXTRACT(YEAR FROM NOW())::INT, 4))"
                )
            )
            pcode = code_result.scalar_one()
            manager = user_by_name.get(proj_def["owner_username"])
            proj = Project(
                project_code=pcode,
                project_name=proj_def["name"],
                project_name_en=proj_def.get("name_en"),
                project_type=proj_def["project_type"],
                project_phase=proj_def.get("phase"),
                status=proj_def.get("status", "proposed"),
                planned_start_date=_to_date(proj_def.get("planned_start_date")),
                planned_end_date=_to_date(proj_def.get("planned_end_date")),
                actual_start_date=_to_date(proj_def.get("actual_start_date")),
                actual_end_date=_to_date(proj_def.get("actual_end_date")),
                project_manager_id=manager.user_id if manager else None,
                department=proj_def.get("department"),
                objective=proj_def.get("objective"),
                description=proj_def.get("description"),
                # therapeutic_area / indication 不在 §9.2 ；放 extra JSONB 兜底
                extra={
                    k: v for k, v in {
                        "therapeutic_area": proj_def.get("therapeutic_area"),
                        "indication": proj_def.get("indication"),
                    }.items() if v
                } or None,
                created_by=admin.user_id,
                updated_by=admin.user_id,
            )
            db.add(proj)
            await db.flush()

        # 里程碑（§9.3：无 deleted_at；type 仅 gate/deliverable/decision；status 用新枚举）
        for m_def in proj_def.get("milestones", []):
            m_existing = await db.execute(
                select(ProjectMilestone).where(
                    ProjectMilestone.project_id == proj.project_id,
                    ProjectMilestone.milestone_name == m_def["name"],
                )
            )
            if m_existing.scalar_one_or_none():
                continue
            db.add(ProjectMilestone(
                project_id=proj.project_id,
                milestone_name=m_def["name"],
                milestone_type=m_def["type"],
                planned_date=_to_date(m_def.get("planned_date")),
                actual_date=_to_date(m_def.get("actual_date")),
                status=m_def.get("status", "planned"),
                description=m_def.get("description"),
                created_by=admin.user_id,
                updated_by=admin.user_id,
            ))

        # 团队成员（§9.4：role 任意字符串 + 绝对唯一）
        for team_username, role in proj_def.get("team", []):
            u = user_by_name.get(team_username)
            if not u:
                continue
            t_existing = await db.execute(
                select(ProjectTeam).where(
                    ProjectTeam.project_id == proj.project_id,
                    ProjectTeam.user_id == u.user_id,
                    ProjectTeam.role == role,
                )
            )
            if t_existing.scalar_one_or_none():
                continue
            db.add(ProjectTeam(
                project_id=proj.project_id,
                user_id=u.user_id,
                role=role,
                created_by=admin.user_id,
            ))

        # 跨域 link（§11.2：复合 PK + relation_type）
        link_internal = proj_def.get("link_substance")
        if link_internal and link_internal in sub_code_by_internal:
            relation_type = proj_def.get("link_relation", "primary")
            sub_id, _ = sub_code_by_internal[link_internal]
            link_existing = await db.execute(
                select(ProjectSubstanceLink).where(
                    ProjectSubstanceLink.project_id == proj.project_id,
                    ProjectSubstanceLink.substance_id == sub_id,
                    ProjectSubstanceLink.relation_type == relation_type,
                    ProjectSubstanceLink.deleted_at.is_(None),
                )
            )
            if not link_existing.scalar_one_or_none():
                db.add(ProjectSubstanceLink(
                    project_id=proj.project_id,
                    substance_id=sub_id,
                    relation_type=relation_type,
                    is_primary=True,
                    created_by=admin.user_id,
                    updated_by=admin.user_id,
                ))

    await db.flush()

    # 4) 资产 + 多市场注册号 + 跨域绑定（asset_substance / project_asset）
    await _seed_demo_assets(db, admin, sub_code_by_internal)

    # 5) 物料 + 批次 + 物质引用（Phase 4.A M4.5）
    await _seed_demo_materials(db, admin, sub_code_by_internal)


async def _seed_demo_materials(
    db: AsyncSession,
    admin: User,
    sub_code_by_internal: dict[str, tuple[int, str]],
) -> None:
    for mat_def in DEMO_MATERIALS:
        # 幂等：按 material_name 查
        existing = await db.execute(
            select(Material).where(Material.material_name == mat_def["material_name"])
        )
        material = existing.scalar_one_or_none()
        if not material:
            sub_id: int | None = None
            sub_internal = mat_def.get("substance_internal_code")
            if sub_internal and sub_internal in sub_code_by_internal:
                sub_id, _ = sub_code_by_internal[sub_internal]

            material = Material(
                material_code=mat_def["material_code"],
                material_name=mat_def["material_name"],
                material_name_en=mat_def.get("material_name_en"),
                material_type=mat_def["material_type"],
                category=mat_def.get("category"),
                substance_id=sub_id,
                manufacturer=mat_def.get("manufacturer"),
                catalog_no=mat_def.get("catalog_no"),
                spec_model=mat_def.get("spec_model"),
                unit=mat_def.get("unit", "ea"),
                package_spec=mat_def.get("package_spec"),
                hazard_class=mat_def.get("hazard_class"),
                physical_form=mat_def.get("physical_form"),
                storage_condition=mat_def.get("storage_condition"),
                source_type=mat_def.get("source_type"),
                source_name=mat_def.get("source_name"),
                grade=mat_def.get("grade"),
                description=mat_def.get("description"),
                created_by=admin.user_id,
                updated_by=admin.user_id,
            )
            db.add(material)
            await db.flush()

        for b_def in mat_def.get("batches", []):
            b_existing = await db.execute(
                select(MaterialBatch).where(
                    MaterialBatch.material_id == material.material_id,
                    MaterialBatch.batch_number == b_def["batch_number"],
                )
            )
            if b_existing.scalar_one_or_none():
                continue
            db.add(MaterialBatch(
                material_id=material.material_id,
                batch_number=b_def["batch_number"],
                quantity_value=b_def.get("quantity_value"),
                quantity_unit=b_def.get("quantity_unit"),
                manufacture_date=_to_date(b_def.get("manufacture_date")),
                expiry_date=_to_date(b_def.get("expiry_date")),
                receive_date=_to_date(b_def.get("receive_date")),
                status=b_def.get("status", "in_stock"),
                source_batch_ref=b_def.get("source_batch_ref"),
                storage_location=b_def.get("storage_location"),
                notes=b_def.get("notes"),
                created_by=admin.user_id,
                updated_by=admin.user_id,
            ))

    await db.flush()


async def _seed_demo_assets(
    db: AsyncSession,
    admin: User,
    sub_code_by_internal: dict[str, tuple[int, str]],
) -> None:
    for asset_def in DEMO_ASSETS:
        # 幂等：按 internal_name 查
        existing = await db.execute(
            select(Asset).where(Asset.internal_name == asset_def["internal_name"])
        )
        asset = existing.scalar_one_or_none()
        if not asset:
            code_result = await db.execute(text("SELECT meta.fn_next_code('asset')"))
            acode = code_result.scalar_one()
            asset = Asset(
                asset_code=acode,
                internal_name=asset_def["internal_name"],
                trade_name=asset_def.get("trade_name"),
                inn_name=asset_def.get("inn_name"),
                asset_type=asset_def["asset_type"],
                therapeutic_area=asset_def.get("therapeutic_area"),
                indication=asset_def.get("indication"),
                dosage_form=asset_def.get("dosage_form"),
                strength=asset_def.get("strength"),
                route_of_administration=asset_def.get("route_of_administration"),
                current_phase=asset_def.get("current_phase", "discovery"),
                status=asset_def.get("status", "active"),
                is_commercial=asset_def.get("is_commercial", False),
                first_approval_date=_to_date(asset_def.get("first_approval_date")),
                first_launch_date=_to_date(asset_def.get("first_launch_date")),
                description=asset_def.get("description"),
                created_by=admin.user_id,
                updated_by=admin.user_id,
            )
            db.add(asset)
            await db.flush()

        # 多市场注册号
        for mid in asset_def.get("market_ids", []):
            mid_existing = await db.execute(
                select(AssetMarketId).where(
                    AssetMarketId.asset_id == asset.asset_id,
                    AssetMarketId.market_code == mid["market_code"],
                    AssetMarketId.id_type == mid["id_type"],
                    AssetMarketId.id_value == mid["id_value"],
                )
            )
            if mid_existing.scalar_one_or_none():
                continue
            db.add(AssetMarketId(
                asset_id=asset.asset_id,
                market_code=mid["market_code"],
                id_type=mid["id_type"],
                id_value=mid["id_value"],
                issuing_authority=mid.get("issuing_authority"),
                application_date=_to_date(mid.get("application_date")),
                approval_date=_to_date(mid.get("approval_date")),
                expiry_date=_to_date(mid.get("expiry_date")),
                status=mid.get("status"),
                created_by=admin.user_id,
                updated_by=admin.user_id,
            ))

        # asset_substance（§11.3）
        for comp in asset_def.get("components", []):
            sub_internal = comp["substance_internal_code"]
            if sub_internal not in sub_code_by_internal:
                continue
            sub_id, _ = sub_code_by_internal[sub_internal]
            role = comp["component_role"]
            link_existing = await db.execute(
                select(AssetSubstanceLink).where(
                    AssetSubstanceLink.asset_id == asset.asset_id,
                    AssetSubstanceLink.substance_id == sub_id,
                    AssetSubstanceLink.component_role == role,
                    AssetSubstanceLink.deleted_at.is_(None),
                )
            )
            if link_existing.scalar_one_or_none():
                continue
            db.add(AssetSubstanceLink(
                asset_id=asset.asset_id,
                substance_id=sub_id,
                component_role=role,
                is_active_ingredient=comp.get("is_active_ingredient", True),
                created_by=admin.user_id,
                updated_by=admin.user_id,
            ))

        # project_asset（§11.4）
        for proj_link in asset_def.get("projects", []):
            proj_existing = await db.execute(
                select(Project).where(Project.project_name == proj_link["project_name"])
            )
            proj = proj_existing.scalar_one_or_none()
            if not proj:
                continue
            pa_existing = await db.execute(
                select(ProjectAssetLink).where(
                    ProjectAssetLink.project_id == proj.project_id,
                    ProjectAssetLink.asset_id == asset.asset_id,
                    ProjectAssetLink.deleted_at.is_(None),
                )
            )
            if pa_existing.scalar_one_or_none():
                continue
            db.add(ProjectAssetLink(
                project_id=proj.project_id,
                asset_id=asset.asset_id,
                relation_type=proj_link.get("relation_type", "primary"),
                created_by=admin.user_id,
                updated_by=admin.user_id,
            ))

    await db.flush()


def _to_date(v: str | None) -> date | None:
    return date.fromisoformat(v) if v else None


async def main(seed_demo: bool = False):
    logger.info("=" * 60)
    logger.info("CMAB MDM Portal - 种子数据加载")
    logger.info(f"  模式：{'baseline + demo' if seed_demo else 'baseline 仅'}")
    logger.info("=" * 60)

    async with AsyncSessionLocal() as db:
        try:
            await seed_permissions(db)
            await seed_roles(db)
            await seed_users(db)
            await seed_substances(db)
            if seed_demo:
                await seed_demo_data(db)
            await db.commit()
            logger.info("✓ 种子数据加载完成")
            logger.info("")
            logger.info("可用测试账号：")
            for u in USERS:
                logger.info(f"  {u['username']:<15} {u['password']:<20} 角色: {u['roles']}")
            if seed_demo:
                logger.info("")
                logger.info(
                    f"✓ 演示数据：{len(DEMO_SUBSTANCES)} 物质 + {len(DEMO_PROJECTS)} 项目 + "
                    f"{len(DEMO_ASSETS)} 资产 + {len(DEMO_MATERIALS)} 物料"
                    f"（含里程碑/团队/市场注册号/批次/跨域绑定）"
                )
        except Exception as e:
            await db.rollback()
            logger.error(f"加载失败: {e}")
            raise
        finally:
            await engine.dispose()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="CMAB MDM Portal 种子数据加载")
    parser.add_argument(
        "--demo",
        action="store_true",
        help="同时加载演示数据集（项目/里程碑/团队/跨域绑定）；生产部署应省略此 flag",
    )
    args = parser.parse_args()
    sys.exit(asyncio.run(main(seed_demo=args.demo)))
