"""drop prs.project_team.updated_at / updated_by

Revision ID: 0017_prs_team_drop_upd
Revises: 0016_prs_relation
Create Date: 2026-05-11 23:40:00.000000

DM-MDM-001 V1.0 §9.4 prs.project_team 不含 updated_at / updated_by 字段；
Phase 1 初始迁移 0001 顺手加上了，与 §9.4 不一致。本迁移移除。
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0017_prs_team_drop_upd"
down_revision: str | None = "0016_prs_relation"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 顺手把依赖 updated_at 的 touch 触发器一并 drop（§9.4 表无 updated_at 字段，touch 失效）
    op.execute("DROP TRIGGER IF EXISTS trg_project_team_touch ON prs.project_team")
    op.drop_column("project_team", "updated_by", schema="prs")
    op.drop_column("project_team", "updated_at", schema="prs")


def downgrade() -> None:
    op.add_column(
        "project_team",
        sa.Column(
            "updated_at", sa.DateTime(timezone=True),
            nullable=False, server_default=sa.text("NOW()"),
        ),
        schema="prs",
    )
    op.add_column(
        "project_team",
        sa.Column("updated_by", sa.BigInteger, nullable=True),
        schema="prs",
    )
    op.execute("""
        CREATE TRIGGER trg_project_team_touch
        BEFORE UPDATE ON prs.project_team
        FOR EACH ROW EXECUTE FUNCTION prs.fn_touch_updated_at();
    """)
