"""PRS 对齐 SMP-RD-NUM-001 V2.1 第三批（C1 §7A + C3 legacy）

Revision ID: 0049_prs_smp_v21_batch3
Revises: 0048_prs_smp_v21_batch2
Create Date: 2026-07-15 03:00:00.000000

- C1 §7A/§10.3 上市后变更合规字段：
    regulatory_change_level (minor/moderate/major)
    pre_approval_required (bool)
    comparability_study_ref (ICH Q5E 可比性研究 Study ID)
    regulatory_submission_refs (监管申报编号数组)
  条件必填在 service 层：project_nature ∈ (cmc_change, lcm) 必填变更级别；
  级别 = major → pre_approval_required 强制 true。
- C3 §11.8 历史遗留编号：legacy_project_id（老编号存档，只读参考）

约束命名遵循本库 metadata 约定（双前缀 ck_project_ck_*）。
C2（project_relationship 合并/拆分落地）复用既有表，无需 migration。
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0049_prs_smp_v21_batch3"
down_revision: str | None = "0048_prs_smp_v21_batch2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # ============== C1 §7A 上市后变更合规字段 ==============
    op.add_column(
        "project", sa.Column("regulatory_change_level", sa.String(16), nullable=True), schema="prs"
    )
    op.add_column(
        "project", sa.Column("pre_approval_required", sa.Boolean, nullable=True), schema="prs"
    )
    op.add_column(
        "project", sa.Column("comparability_study_ref", sa.String(50), nullable=True), schema="prs"
    )
    op.add_column(
        "project",
        sa.Column("regulatory_submission_refs", postgresql.JSONB, nullable=True),
        schema="prs",
    )
    op.execute(
        "ALTER TABLE prs.project ADD CONSTRAINT ck_project_ck_regulatory_change_level "
        "CHECK (regulatory_change_level IS NULL OR "
        "regulatory_change_level IN ('minor','moderate','major'))"
    )

    # ============== C3 §11.8 历史遗留编号 ==============
    op.add_column(
        "project", sa.Column("legacy_project_id", sa.String(32), nullable=True), schema="prs"
    )

    # ============== lookup_value ==============
    op.execute("""
        INSERT INTO meta.lookup_value (lookup_type, lookup_code, lookup_name, lookup_name_en, sort_order) VALUES
            ('regulatory_change_level', 'minor',    '微小变更', 'Minor',    10),
            ('regulatory_change_level', 'moderate', '中等变更', 'Moderate', 20),
            ('regulatory_change_level', 'major',    '重大变更', 'Major',    30)
        ON CONFLICT (lookup_type, lookup_code) DO NOTHING;
    """)


def downgrade() -> None:
    op.execute("DELETE FROM meta.lookup_value WHERE lookup_type='regulatory_change_level'")
    op.drop_column("project", "legacy_project_id", schema="prs")
    op.execute("ALTER TABLE prs.project DROP CONSTRAINT IF EXISTS ck_project_ck_regulatory_change_level")
    for col in (
        "regulatory_submission_refs", "comparability_study_ref",
        "pre_approval_required", "regulatory_change_level",
    ):
        op.drop_column("project", col, schema="prs")
