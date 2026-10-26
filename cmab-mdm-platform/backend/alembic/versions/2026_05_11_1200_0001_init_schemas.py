"""init schemas auth meta srs

Revision ID: 0001_init_schemas
Revises:
Create Date: 2026-05-11 12:00:00.000000

创建：
- 基础元数据：meta.code_sequence + 编码生成函数
- auth schema：user、role、permission、user_role、role_permission、login_history
- srs schema：substance、substance_protein、substance_xref

注：schema 本身已由 deploy/postgres/init/01-init.sql 创建。
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001_init_schemas"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # ============== meta.code_sequence + 函数 ==============
    op.create_table(
        "code_sequence",
        sa.Column("sequence_id", sa.BigInteger, sa.Identity(always=True), primary_key=True),
        sa.Column("sequence_name", sa.String(64), nullable=False),
        sa.Column("prefix", sa.String(16), nullable=False),
        sa.Column("current_value", sa.BigInteger, nullable=False, server_default="0"),
        sa.Column("padding_length", sa.Integer, nullable=False, server_default="7"),
        sa.Column("increment_step", sa.Integer, nullable=False, server_default="1"),
        sa.Column("description", sa.Text),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.UniqueConstraint("sequence_name", name="uq_code_sequence_sequence_name"),
        schema="meta",
    )

    # 编码生成函数
    op.execute("""
        CREATE OR REPLACE FUNCTION meta.fn_next_code(p_sequence_name VARCHAR)
        RETURNS VARCHAR AS $$
        DECLARE
            v_prefix   VARCHAR;
            v_value    BIGINT;
            v_padding  INT;
        BEGIN
            UPDATE meta.code_sequence
               SET current_value = current_value + increment_step,
                   updated_at    = NOW()
             WHERE sequence_name = p_sequence_name
            RETURNING prefix, current_value, padding_length
                INTO v_prefix, v_value, v_padding;

            IF NOT FOUND THEN
                RAISE EXCEPTION 'Code sequence % not found', p_sequence_name;
            END IF;

            RETURN v_prefix || LPAD(v_value::text, v_padding, '0');
        END;
        $$ LANGUAGE plpgsql;
    """)

    # 初始化 substance 序列
    op.execute("""
        INSERT INTO meta.code_sequence (sequence_name, prefix, padding_length, description)
        VALUES ('substance', 'SUB-', 7, 'Substance 编码序列：SUB-0000001 ...')
        ON CONFLICT (sequence_name) DO NOTHING;
    """)

    # ============== auth.user ==============
    op.create_table(
        "user",
        sa.Column("user_id", sa.BigInteger, sa.Identity(always=True), primary_key=True),
        sa.Column("username", sa.String(64), nullable=False),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("full_name", sa.String(128), nullable=False),
        sa.Column("full_name_en", sa.String(128)),
        sa.Column("department", sa.String(64)),
        sa.Column("title", sa.String(64)),
        sa.Column("phone", sa.String(32)),
        sa.Column("status", sa.String(16), nullable=False, server_default="active"),
        sa.Column("failed_login_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("last_login_at", sa.DateTime(timezone=True)),
        sa.Column("password_changed_at", sa.DateTime(timezone=True)),
        sa.Column("password_expires_at", sa.DateTime(timezone=True)),
        sa.Column("mfa_enabled", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.Column("created_by", sa.BigInteger),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.Column("updated_by", sa.BigInteger),
        sa.Column("deleted_at", sa.DateTime(timezone=True)),
        sa.Column("deleted_by", sa.BigInteger),
        sa.UniqueConstraint("username", name="uq_user_username"),
        sa.UniqueConstraint("email", name="uq_user_email"),
        sa.CheckConstraint(
            "status IN ('active','locked','disabled')",
            name="ck_user_status",
        ),
        schema="auth",
    )
    op.create_index(
        "ix_user_status", "user", ["status"],
        postgresql_where=sa.text("deleted_at IS NULL"), schema="auth",
    )

    # ============== auth.role ==============
    op.create_table(
        "role",
        sa.Column("role_id", sa.BigInteger, sa.Identity(always=True), primary_key=True),
        sa.Column("role_code", sa.String(32), nullable=False),
        sa.Column("role_name", sa.String(64), nullable=False),
        sa.Column("description", sa.Text),
        sa.Column("is_system", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.Column("created_by", sa.BigInteger),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.Column("updated_by", sa.BigInteger),
        sa.Column("deleted_at", sa.DateTime(timezone=True)),
        sa.Column("deleted_by", sa.BigInteger),
        sa.UniqueConstraint("role_code", name="uq_role_role_code"),
        schema="auth",
    )

    # ============== auth.permission ==============
    op.create_table(
        "permission",
        sa.Column("permission_id", sa.BigInteger, sa.Identity(always=True), primary_key=True),
        sa.Column("permission_code", sa.String(64), nullable=False),
        sa.Column("resource", sa.String(64), nullable=False),
        sa.Column("action", sa.String(32), nullable=False),
        sa.Column("description", sa.Text),
        sa.Column("is_system", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.UniqueConstraint("permission_code", name="uq_permission_permission_code"),
        sa.UniqueConstraint("resource", "action", name="uq_permission_resource_action"),
        schema="auth",
    )

    # ============== auth.user_role ==============
    op.create_table(
        "user_role",
        sa.Column("user_id", sa.BigInteger, sa.ForeignKey("auth.user.user_id"), primary_key=True),
        sa.Column("role_id", sa.BigInteger, sa.ForeignKey("auth.role.role_id"), primary_key=True),
        sa.Column("granted_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.Column("granted_by", sa.BigInteger),
        sa.Column("expires_at", sa.DateTime(timezone=True)),
        schema="auth",
    )

    # ============== auth.role_permission ==============
    op.create_table(
        "role_permission",
        sa.Column("role_id", sa.BigInteger, sa.ForeignKey("auth.role.role_id"), primary_key=True),
        sa.Column("permission_id", sa.BigInteger, sa.ForeignKey("auth.permission.permission_id"), primary_key=True),
        sa.Column("granted_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.Column("granted_by", sa.BigInteger),
        schema="auth",
    )

    # ============== auth.login_history ==============
    op.create_table(
        "login_history",
        sa.Column("login_id", sa.BigInteger, sa.Identity(always=True), primary_key=True),
        sa.Column("user_id", sa.BigInteger, sa.ForeignKey("auth.user.user_id")),
        sa.Column("username_input", sa.String(64), nullable=False),
        sa.Column("success", sa.Boolean, nullable=False),
        sa.Column("failure_reason", sa.String(64)),
        sa.Column("ip_address", sa.String(45)),
        sa.Column("user_agent", sa.Text),
        sa.Column("login_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        schema="auth",
    )
    op.create_index(
        "ix_login_history_login_at", "login_history", [sa.text("login_at DESC")],
        schema="auth",
    )

    # ============== srs.substance ==============
    op.create_table(
        "substance",
        sa.Column("substance_id", sa.BigInteger, sa.Identity(always=True), primary_key=True),
        sa.Column("substance_code", sa.String(32), nullable=False),
        sa.Column("substance_type", sa.String(32), nullable=False),
        sa.Column("internal_code", sa.String(64)),
        sa.Column("preferred_name", sa.String(255), nullable=False),
        sa.Column("preferred_name_en", sa.String(255)),
        sa.Column("display_name", sa.String(255)),
        sa.Column("target", sa.String(128)),
        sa.Column("target_type", sa.String(64)),
        sa.Column("modality", sa.String(64)),
        sa.Column("status", sa.String(32), nullable=False, server_default="draft"),
        sa.Column("is_proprietary", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("confidentiality", sa.String(16), nullable=False, server_default="internal"),
        sa.Column("external_uuid", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()")),
        sa.Column("description", sa.Text),
        sa.Column("notes", sa.Text),
        sa.Column("extra", postgresql.JSONB),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.Column("created_by", sa.BigInteger, nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.Column("updated_by", sa.BigInteger, nullable=False),
        sa.Column("registered_at", sa.DateTime(timezone=True)),
        sa.Column("registered_by", sa.BigInteger),
        sa.Column("deleted_at", sa.DateTime(timezone=True)),
        sa.Column("deleted_by", sa.BigInteger),
        sa.Column("version", sa.Integer, nullable=False, server_default="1"),
        sa.UniqueConstraint("substance_code", name="uq_substance_substance_code"),
        sa.UniqueConstraint("internal_code", name="uq_substance_internal_code"),
        sa.CheckConstraint(
            "substance_type IN ('mab','bispecific','adc','fusion','small_molecule','oligonucleotide','other')",
            name="ck_substance_substance_type",
        ),
        sa.CheckConstraint(
            "status IN ('draft','registered','active','restricted','deprecated','obsoleted')",
            name="ck_substance_status",
        ),
        sa.CheckConstraint(
            "confidentiality IN ('public','internal','restricted')",
            name="ck_substance_confidentiality",
        ),
        schema="srs",
    )
    op.create_index(
        "ix_substance_substance_type", "substance", ["substance_type"],
        postgresql_where=sa.text("deleted_at IS NULL"), schema="srs",
    )
    op.create_index(
        "ix_substance_status", "substance", ["status"],
        postgresql_where=sa.text("deleted_at IS NULL"), schema="srs",
    )
    op.create_index(
        "ix_substance_target", "substance", ["target"],
        postgresql_where=sa.text("deleted_at IS NULL"), schema="srs",
    )
    op.execute(
        "CREATE INDEX ix_substance_preferred_name "
        "ON srs.substance USING gin(preferred_name gin_trgm_ops)"
    )

    # ============== srs.substance_protein ==============
    op.create_table(
        "substance_protein",
        sa.Column(
            "substance_id", sa.BigInteger,
            sa.ForeignKey("srs.substance.substance_id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("heavy_chain_sequence", sa.Text),
        sa.Column("light_chain_sequence", sa.Text),
        sa.Column("additional_chains", postgresql.JSONB),
        sa.Column("sequence_length_hc", sa.Integer),
        sa.Column("sequence_length_lc", sa.Integer),
        sa.Column("sequence_hash_hc", sa.String(64)),
        sa.Column("sequence_hash_lc", sa.String(64)),
        sa.Column("isotype", sa.String(32)),
        sa.Column("architecture", sa.String(64)),
        sa.Column("disulfide_bonds", postgresql.JSONB),
        sa.Column("glycosylation_sites", postgresql.JSONB),
        sa.Column("ptm_info", postgresql.JSONB),
        sa.Column("expression_system", sa.String(64)),
        sa.Column("cell_line", sa.String(128)),
        sa.Column("expression_vector", sa.String(128)),
        sa.Column("molecular_weight_da", sa.Float),
        sa.Column("pi_theoretical", sa.Float),
        sa.Column("extinction_coefficient", sa.Integer),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        schema="srs",
    )

    # ============== srs.substance_xref ==============
    op.create_table(
        "substance_xref",
        sa.Column("xref_id", sa.BigInteger, sa.Identity(always=True), primary_key=True),
        sa.Column("substance_id", sa.BigInteger,
                  sa.ForeignKey("srs.substance.substance_id"), nullable=False),
        sa.Column("xref_type", sa.String(32), nullable=False),
        sa.Column("xref_value", sa.String(255), nullable=False),
        sa.Column("xref_source", sa.String(64)),
        sa.Column("region", sa.String(16)),
        sa.Column("is_primary", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("notes", sa.Text),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.Column("created_by", sa.BigInteger, nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.Column("updated_by", sa.BigInteger, nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True)),
        sa.Column("deleted_by", sa.BigInteger),
        sa.CheckConstraint(
            "xref_type IN ('INN','USAN','CAS','UNII','GSRS_UUID','ChEMBL','DRUGBANK',"
            "'TRADE_NAME','GENERIC_NAME','HISTORICAL_CODE','PROJECT_CODE','OTHER')",
            name="ck_substance_xref_xref_type",
        ),
        schema="srs",
    )
    op.create_index(
        "ix_substance_xref_substance_id", "substance_xref", ["substance_id"],
        schema="srs",
    )


def downgrade() -> None:
    op.drop_table("substance_xref", schema="srs")
    op.drop_table("substance_protein", schema="srs")
    op.drop_table("substance", schema="srs")
    op.drop_table("login_history", schema="auth")
    op.drop_table("role_permission", schema="auth")
    op.drop_table("user_role", schema="auth")
    op.drop_table("permission", schema="auth")
    op.drop_table("role", schema="auth")
    op.drop_table("user", schema="auth")
    op.execute("DROP FUNCTION IF EXISTS meta.fn_next_code(VARCHAR)")
    op.drop_table("code_sequence", schema="meta")
