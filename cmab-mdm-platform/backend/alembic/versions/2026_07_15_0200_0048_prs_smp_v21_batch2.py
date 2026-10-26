"""PRS 对齐 SMP-RD-NUM-001 V2.1 第二批（B1-B7）

Revision ID: 0048_prs_smp_v21_batch2
Revises: 0047_prs_smp_v21_batch1
Create Date: 2026-07-15 02:00:00.000000

SMP-RD-NUM-001 V2.1 差异整改第二批（项目分类 + MDM 字段）：
- B1 §7.4(a) project_category：asset_related / non_asset
- B2 §7.4(b) project_nature：9 值 portfolio 分类
- B3 §7.5      asset_id：项目→资产 1:N 权威绑定（asset_related 时 service 强制必填）
- B4 §10.3     owning_function（受控归属）+ participating_functions
- B5 §10.3     approval_date/reference/year + governance_approval_ref + status_reason
- B6 §10.3     sap_wbs_mapping + external_contract_refs + partner_reference
- B7 §10.3     project_phase 由自由文本改受控枚举

约束命名遵循本库 metadata 约定 ck_%(table)s_%(constraint_name)s → 双前缀。
数据现状：PRS 项目 0 行，仅 seed phase 需 remap（phase_N → pN）。
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0048_prs_smp_v21_batch2"
down_revision: str | None = "0047_prs_smp_v21_batch1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_NATURE = (
    "nme", "indication_expansion", "geographic_expansion", "lcm",
    "regulatory_commitment", "cmc_change", "bd_evaluation", "platform", "discovery",
)
_OWNING = ("rd", "clinical", "cmc", "regulatory", "qa", "it", "bd", "finance", "pmo", "other")
_PHASE = ("discovery", "lead_opt", "ind_enabling", "p1", "p2", "p3", "filed", "post_marketing")


def upgrade() -> None:
    # ============== B1/B2/B4 分类与归属（NOT NULL + server_default 兜底空表）==============
    op.add_column(
        "project",
        sa.Column("project_category", sa.String(16), nullable=False, server_default="non_asset"),
        schema="prs",
    )
    op.add_column(
        "project",
        sa.Column("project_nature", sa.String(32), nullable=False, server_default="discovery"),
        schema="prs",
    )
    op.add_column(
        "project",
        sa.Column("owning_function", sa.String(32), nullable=False, server_default="rd"),
        schema="prs",
    )
    op.add_column(
        "project",
        sa.Column("participating_functions", postgresql.JSONB, nullable=True),
        schema="prs",
    )

    # ============== B3 asset_id（1:N 权威绑定；条件必填在 service 层）==============
    op.add_column(
        "project",
        sa.Column("asset_id", sa.BigInteger, nullable=True),
        schema="prs",
    )
    op.create_foreign_key(
        "fk_project_asset_asset_id",
        "project", "asset",
        ["asset_id"], ["asset_id"],
        source_schema="prs", referent_schema="ars",
    )
    op.create_index("ix_project_asset_id", "project", ["asset_id"], schema="prs")

    # ============== B5 审批与治理字段 ==============
    op.add_column("project", sa.Column("approval_date", sa.Date, nullable=True), schema="prs")
    op.add_column("project", sa.Column("approval_reference", sa.String(50), nullable=True), schema="prs")
    op.add_column("project", sa.Column("approval_year", sa.Integer, nullable=True), schema="prs")
    op.add_column("project", sa.Column("governance_approval_ref", sa.String(50), nullable=True), schema="prs")
    op.add_column("project", sa.Column("status_reason", sa.Text, nullable=True), schema="prs")

    # ============== B6 对接字段 ==============
    op.add_column("project", sa.Column("sap_wbs_mapping", sa.String(50), nullable=True), schema="prs")
    op.add_column("project", sa.Column("external_contract_refs", postgresql.JSONB, nullable=True), schema="prs")
    op.add_column("project", sa.Column("partner_reference", sa.String(200), nullable=True), schema="prs")

    # ============== B7 project_phase remap + 受控 CHECK ==============
    op.execute("UPDATE prs.project SET project_phase='p1' WHERE project_phase='phase_1'")
    op.execute("UPDATE prs.project SET project_phase='p2' WHERE project_phase='phase_2'")
    op.execute("UPDATE prs.project SET project_phase='p3' WHERE project_phase='phase_3'")
    _phase_in = ",".join(f"'{v}'" for v in _PHASE)
    op.execute(f"UPDATE prs.project SET project_phase=NULL "
               f"WHERE project_phase IS NOT NULL AND project_phase NOT IN ({_phase_in})")

    # ============== CHECK 约束（双前缀命名）==============
    _cat_in = "'asset_related','non_asset'"
    _nature_in = ",".join(f"'{v}'" for v in _NATURE)
    _own_in = ",".join(f"'{v}'" for v in _OWNING)
    op.execute(f"ALTER TABLE prs.project ADD CONSTRAINT ck_project_ck_project_category "
               f"CHECK (project_category IN ({_cat_in}))")
    op.execute(f"ALTER TABLE prs.project ADD CONSTRAINT ck_project_ck_project_nature "
               f"CHECK (project_nature IN ({_nature_in}))")
    op.execute(f"ALTER TABLE prs.project ADD CONSTRAINT ck_project_ck_owning_function "
               f"CHECK (owning_function IN ({_own_in}))")
    op.execute(f"ALTER TABLE prs.project ADD CONSTRAINT ck_project_ck_project_phase "
               f"CHECK (project_phase IS NULL OR project_phase IN ({_phase_in}))")

    # ============== lookup_value 展示字典 ==============
    op.execute("""
        INSERT INTO meta.lookup_value (lookup_type, lookup_code, lookup_name, lookup_name_en, sort_order) VALUES
            ('project_category', 'asset_related', '资产相关', 'Asset-related', 10),
            ('project_category', 'non_asset',     '非资产',   'Non-asset',     20),
            ('project_nature', 'nme',                   '新分子实体',   'NME',                    10),
            ('project_nature', 'indication_expansion',  '适应症拓展',   'Indication Expansion',   20),
            ('project_nature', 'geographic_expansion',  '地区拓展',     'Geographic Expansion',   30),
            ('project_nature', 'lcm',                   '生命周期管理', 'Lifecycle Management',    40),
            ('project_nature', 'regulatory_commitment', '监管承诺',     'Regulatory Commitment',  50),
            ('project_nature', 'cmc_change',            'CMC 变更',     'CMC Change',             60),
            ('project_nature', 'bd_evaluation',         'BD 评估',      'BD Evaluation',          70),
            ('project_nature', 'platform',              '平台能力',     'Platform',               80),
            ('project_nature', 'discovery',             '发现',         'Discovery',              90),
            ('owning_function', 'rd',         '研发',   'R&D',        10),
            ('owning_function', 'clinical',   '临床',   'Clinical',   20),
            ('owning_function', 'cmc',        'CMC',    'CMC',        30),
            ('owning_function', 'regulatory', '注册',   'Regulatory', 40),
            ('owning_function', 'qa',         '质量',   'QA',         50),
            ('owning_function', 'it',         'IT',     'IT',         60),
            ('owning_function', 'bd',         '商务拓展','BD',         70),
            ('owning_function', 'finance',    '财务',   'Finance',    80),
            ('owning_function', 'pmo',        'PMO',    'PMO',        90),
            ('owning_function', 'other',      '其他',   'Other',      99),
            ('project_phase', 'discovery',      '发现',       'Discovery',       10),
            ('project_phase', 'lead_opt',       '先导优化',   'Lead Optimization', 20),
            ('project_phase', 'ind_enabling',   'IND 使能',   'IND-enabling',    30),
            ('project_phase', 'p1',             'I 期',       'Phase 1',         40),
            ('project_phase', 'p2',             'II 期',      'Phase 2',         50),
            ('project_phase', 'p3',             'III 期',     'Phase 3',         60),
            ('project_phase', 'filed',          '已申报',     'Filed',           70),
            ('project_phase', 'post_marketing', '上市后',     'Post-marketing',  80)
        ON CONFLICT (lookup_type, lookup_code) DO NOTHING;
    """)


def downgrade() -> None:
    op.execute(
        "DELETE FROM meta.lookup_value WHERE lookup_type IN "
        "('project_category','project_nature','owning_function','project_phase')"
    )
    for c in (
        "ck_project_ck_project_category",
        "ck_project_ck_project_nature",
        "ck_project_ck_owning_function",
        "ck_project_ck_project_phase",
    ):
        op.execute(f"ALTER TABLE prs.project DROP CONSTRAINT IF EXISTS {c}")

    # phase remap 回退
    op.execute("UPDATE prs.project SET project_phase='phase_1' WHERE project_phase='p1'")
    op.execute("UPDATE prs.project SET project_phase='phase_2' WHERE project_phase='p2'")
    op.execute("UPDATE prs.project SET project_phase='phase_3' WHERE project_phase='p3'")

    for col in (
        "partner_reference", "external_contract_refs", "sap_wbs_mapping",
        "status_reason", "governance_approval_ref", "approval_year",
        "approval_reference", "approval_date",
    ):
        op.drop_column("project", col, schema="prs")

    op.drop_index("ix_project_asset_id", table_name="project", schema="prs")
    op.drop_constraint("fk_project_asset_asset_id", "project", schema="prs", type_="foreignkey")
    op.drop_column("project", "asset_id", schema="prs")

    for col in ("participating_functions", "owning_function", "project_nature", "project_category"):
        op.drop_column("project", col, schema="prs")
