"""Durable PM creation intent and recovery lease; no business rows are rewritten."""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "0068_pm_create_request"
down_revision = "0067_oidc_identity"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "project_pm_create_request",
        sa.Column("request_id", sa.String(36), primary_key=True),
        sa.Column("project_id", sa.BigInteger(), sa.ForeignKey("prs.project.project_id"), nullable=False),
        sa.Column("source_id", sa.String(64), nullable=False),
        sa.Column("requested_by", sa.BigInteger(), sa.ForeignKey("auth.user.user_id"), nullable=False),
        sa.Column("request_payload", JSONB(), nullable=False),
        sa.Column("payload_hash", sa.String(64), nullable=False),
        sa.Column("change_reason", sa.Text(), nullable=False),
        sa.Column("status", sa.String(32), nullable=False, server_default="pending"),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("lease_owner", sa.String(36)),
        sa.Column("lease_expires_at", sa.DateTime(timezone=True)),
        sa.Column("remote_project_id", sa.String(64)),
        sa.Column("remote_receipt", JSONB()),
        sa.Column("last_error", sa.String(64)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("project_id", name="uq_pm_create_project"),
        sa.CheckConstraint(
            "status IN ('pending','in_progress','remote_created','retryable_error',"
            "'linked','reconciliation_required')", name="ck_pm_create_status",
        ),
        sa.CheckConstraint("attempts >= 0", name="ck_pm_create_attempts"),
        schema="prs",
    )


def downgrade() -> None:
    op.execute("LOCK TABLE prs.project_pm_create_request IN ACCESS EXCLUSIVE MODE")
    if op.get_bind().execute(sa.text("SELECT EXISTS (SELECT 1 FROM prs.project_pm_create_request)")).scalar():
        raise RuntimeError("Refusing to drop nonempty PM creation intents; reconcile explicitly")
    op.drop_table("project_pm_create_request", schema="prs")
