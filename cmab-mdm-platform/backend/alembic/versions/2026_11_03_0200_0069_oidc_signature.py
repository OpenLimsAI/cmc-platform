"""One-time fresh OIDC signing evidence; no historical records or passwords change."""
import sqlalchemy as sa
from alembic import op

revision = "0069_oidc_signature"
down_revision = "0068_pm_create_request"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("oidc_signature_challenge",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("session_id", sa.String(64), sa.ForeignKey("auth.oidc_session.id"), nullable=False),
        sa.Column("identity_id", sa.BigInteger(), sa.ForeignKey("auth.oidc_identity.identity_id"), nullable=False),
        sa.Column("user_id", sa.BigInteger(), sa.ForeignKey("auth.user.user_id"), nullable=False),
        sa.Column("issuer", sa.String(512), nullable=False),
        sa.Column("subject", sa.String(255), nullable=False),
        sa.Column("audience", sa.String(255), nullable=False),
        sa.Column("entity_schema", sa.String(16), nullable=False),
        sa.Column("entity_table", sa.String(32), nullable=False),
        sa.Column("entity_id", sa.BigInteger(), nullable=False),
        sa.Column("content_hash", sa.String(64), nullable=False),
        sa.Column("meaning", sa.String(32), nullable=False),
        sa.Column("state_hash", sa.String(64), nullable=False),
        sa.Column("secret_data", sa.Text(), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("authenticated_at", sa.BigInteger()),
        sa.Column("signature_id", sa.BigInteger(), sa.ForeignKey("audit.e_signature.signature_id"), unique=True),
        sa.CheckConstraint("status IN ('pending','verifying','ready','cancelled','failed','consumed')", name="oidc_signature_status"),
        schema="auth")


def downgrade():
    op.execute("LOCK TABLE auth.oidc_signature_challenge IN ACCESS EXCLUSIVE MODE")
    if op.get_bind().execute(sa.text("SELECT EXISTS (SELECT 1 FROM auth.oidc_signature_challenge)")).scalar():
        raise RuntimeError("Preserve signing evidence: restore a backup or retain this table")
    op.drop_table("oidc_signature_challenge", schema="auth")
