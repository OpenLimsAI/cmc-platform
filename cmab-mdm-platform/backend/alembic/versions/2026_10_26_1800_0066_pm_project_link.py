"""MDM-owned one-to-one PM project association; no existing business data changes."""
import sqlalchemy as sa
from alembic import op

revision = "0066_pm_project_link"
down_revision = "0065_master_write_protection"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "project_pm_link",
        sa.Column("link_id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("project_id", sa.BigInteger(), sa.ForeignKey("prs.project.project_id"), nullable=False),
        sa.Column("pm_project_id", sa.String(64), nullable=False),
        sa.Column("pm_project_code", sa.String(40), nullable=False),
        sa.Column("pm_project_name", sa.String(200), nullable=False),
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("created_by", sa.BigInteger(), sa.ForeignKey("auth.user.user_id"), nullable=False),
        sa.Column("change_reason", sa.Text(), nullable=False),
        sa.UniqueConstraint("project_id", name="uq_project_pm_link_project_id"),
        sa.UniqueConstraint("pm_project_id", name="uq_project_pm_link_pm_project_id"),
        schema="prs",
    )


def downgrade() -> None:
    # Acquire the DDL lock before checking, so concurrent creation cannot lose mappings.
    op.execute("LOCK TABLE prs.project_pm_link IN ACCESS EXCLUSIVE MODE")
    if op.get_bind().execute(sa.text("SELECT EXISTS (SELECT 1 FROM prs.project_pm_link)")).scalar():
        raise RuntimeError("Refusing to drop nonempty PM mappings; archive and approve explicitly")
    op.drop_table("project_pm_link", schema="prs")
