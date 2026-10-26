"""Opt-in explicit OIDC identity and revocable session tables; existing users unchanged."""
import sqlalchemy as sa
from alembic import op

revision = "0067_oidc_identity"
down_revision = "0066_pm_project_link"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("oidc_identity",
        sa.Column("identity_id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("issuer", sa.String(512), nullable=False),
        sa.Column("subject", sa.String(255), nullable=False),
        sa.Column("user_id", sa.BigInteger(), sa.ForeignKey("auth.user.user_id"), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("created_by", sa.BigInteger(), sa.ForeignKey("auth.user.user_id"), nullable=False),
        sa.Column("change_reason", sa.Text(), nullable=False),
        sa.UniqueConstraint("issuer", "subject", name="uq_oidc_identity_subject"),
        sa.UniqueConstraint("issuer", "user_id", name="uq_oidc_identity_user"), schema="auth")
    op.create_table("oidc_login", sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("secret_data", sa.Text(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False), schema="auth")
    op.create_table("oidc_session", sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("identity_id", sa.BigInteger(), sa.ForeignKey("auth.oidc_identity.identity_id"), nullable=False),
        sa.Column("issued_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("idle_expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("provider_issued_at", sa.BigInteger(), nullable=False),
        sa.Column("provider_sid", sa.String(255)), sa.Column("password_version", sa.String(64)),
        sa.Column("secret_data", sa.Text(), nullable=False), sa.Column("revoked_at", sa.DateTime(timezone=True)), schema="auth")
    op.create_index("ix_auth_oidc_session_identity_id", "oidc_session", ["identity_id"], schema="auth")
    op.create_table("oidc_logout_replay", sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("issuer", sa.String(512), nullable=False), sa.Column("subject", sa.String(255)),
        sa.Column("sid", sa.String(255)), sa.Column("issued_at", sa.BigInteger(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False), schema="auth")


def downgrade():
    op.execute("LOCK TABLE auth.oidc_identity IN ACCESS EXCLUSIVE MODE")
    if op.get_bind().execute(sa.text("SELECT EXISTS (SELECT 1 FROM auth.oidc_identity)")).scalar():
        raise RuntimeError("Refusing to remove identity mappings; disable OIDC and preserve identity history")
    for table in ("oidc_logout_replay", "oidc_session", "oidc_login", "oidc_identity"):
        op.drop_table(table, schema="auth")
