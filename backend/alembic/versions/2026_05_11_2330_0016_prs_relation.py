"""prs.project_relationship per DM-MDM-001 V1.0 §9.5

Revision ID: 0016_prs_relation
Revises: 0015_prs_team_v2
Create Date: 2026-05-11 23:30:00.000000

M3.0.2 第 4 步：新建 §9.5 prs.project_relationship 表。

字段层面只建表 + 索引 + CHECK，service/API/前端实现留 Phase 3 起按需上线。
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0016_prs_relation"
down_revision: str | None = "0015_prs_team_v2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "project_relationship",
        sa.Column("relationship_id", sa.BigInteger, sa.Identity(always=True), primary_key=True),
        sa.Column("from_project_id", sa.BigInteger,
                  sa.ForeignKey("prs.project.project_id"), nullable=False),
        sa.Column("to_project_id", sa.BigInteger,
                  sa.ForeignKey("prs.project.project_id"), nullable=False),
        sa.Column("relationship_type", sa.String(32), nullable=False),
        sa.Column("notes", sa.Text),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.Column("created_by", sa.BigInteger, nullable=False),
        sa.UniqueConstraint(
            "from_project_id", "to_project_id", "relationship_type",
            name="uq_project_relationship",
        ),
        sa.CheckConstraint(
            "from_project_id != to_project_id",
            name="ck_project_rel_self",
        ),
        sa.CheckConstraint(
            "relationship_type IN ('merged_into','split_from','derived_from','depends_on','blocks')",
            name="ck_project_rel_type",
        ),
        schema="prs",
    )


def downgrade() -> None:
    op.drop_table("project_relationship", schema="prs")
