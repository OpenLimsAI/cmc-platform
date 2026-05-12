"""SRS missing subtables per DM-MDM-001 V1.0 §7.4 / §7.5 / §7.8

Revision ID: 0018_srs_subtables
Revises: 0017_prs_team_drop_upd
Create Date: 2026-05-11 23:50:00.000000

M3.0.3 第 1 步：补齐 SRS 缺失子表（详见偏离说明 §2.1.1-2.1.3）

  - srs.substance_adc       §7.4 ADC 扩展（antibody/linker/payload 父子血缘 + DAR）
  - srs.substance_small_molecule  §7.5 小分子扩展（smiles/inchi/molecular_formula）
  - srs.substance_alias     §7.8 曾用名

M3.0 阶段仅建表 + ORM；service/API/UI 留 Phase 3+ 真用到 ADC/小分子的业务流程时再上。
audit trigger 全部接入（v2 第 3 参数 parent_ref 用 substance_code 回填）。
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0018_srs_subtables"
down_revision: str | None = "0017_prs_team_drop_upd"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # ============== §7.4 srs.substance_adc ==============
    op.create_table(
        "substance_adc",
        sa.Column(
            "substance_id", sa.BigInteger,
            sa.ForeignKey("srs.substance.substance_id", ondelete="CASCADE"),
            primary_key=True,
        ),
        # 父子 substance 引用
        sa.Column("antibody_substance_id", sa.BigInteger,
                  sa.ForeignKey("srs.substance.substance_id"), nullable=False),
        sa.Column("linker_substance_id", sa.BigInteger,
                  sa.ForeignKey("srs.substance.substance_id")),
        sa.Column("payload_substance_id", sa.BigInteger,
                  sa.ForeignKey("srs.substance.substance_id"), nullable=False),
        # DAR
        sa.Column("dar_average", sa.Numeric(4, 2)),
        sa.Column("dar_distribution", postgresql.JSONB),
        sa.Column("dar_method", sa.String(64)),
        # 偶联化学
        sa.Column("conjugation_chemistry", sa.String(64)),
        sa.Column("conjugation_site", sa.String(128)),
        # 元数据
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("NOW()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("NOW()")),
        sa.CheckConstraint(
            "dar_average IS NULL OR (dar_average >= 0 AND dar_average <= 30)",
            name="ck_substance_adc_dar",
        ),
        schema="srs",
    )
    op.create_index(
        "ix_substance_adc_antibody", "substance_adc",
        ["antibody_substance_id"], schema="srs",
    )
    op.create_index(
        "ix_substance_adc_payload", "substance_adc",
        ["payload_substance_id"], schema="srs",
    )
    op.execute("""
        CREATE TRIGGER trg_substance_adc_audit
        AFTER INSERT OR UPDATE OR DELETE ON srs.substance_adc
        FOR EACH ROW EXECUTE FUNCTION audit.fn_audit_trigger(
            'substance_id', '', 'srs.substance:substance_id:substance_code:substance_id'
        );
    """)

    # ============== §7.5 srs.substance_small_molecule ==============
    op.create_table(
        "substance_small_molecule",
        sa.Column(
            "substance_id", sa.BigInteger,
            sa.ForeignKey("srs.substance.substance_id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("smiles", sa.Text),
        sa.Column("inchi", sa.Text),
        sa.Column("inchi_key", sa.String(27)),
        sa.Column("molecular_formula", sa.String(64)),
        sa.Column("molecular_weight", sa.Numeric(10, 4)),
        sa.Column("salt_form", sa.String(64)),
        sa.Column("crystal_form", sa.String(64)),
        sa.Column("stereochemistry", sa.String(64)),
        sa.Column("extra", postgresql.JSONB),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("NOW()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("NOW()")),
        schema="srs",
    )
    op.execute("""
        CREATE UNIQUE INDEX uq_substance_sm_inchi_key
        ON srs.substance_small_molecule(inchi_key)
        WHERE inchi_key IS NOT NULL
    """)
    op.execute("""
        CREATE TRIGGER trg_substance_sm_audit
        AFTER INSERT OR UPDATE OR DELETE ON srs.substance_small_molecule
        FOR EACH ROW EXECUTE FUNCTION audit.fn_audit_trigger(
            'substance_id', '', 'srs.substance:substance_id:substance_code:substance_id'
        );
    """)

    # ============== §7.8 srs.substance_alias ==============
    op.create_table(
        "substance_alias",
        sa.Column("alias_id", sa.BigInteger, sa.Identity(always=True), primary_key=True),
        sa.Column("substance_id", sa.BigInteger,
                  sa.ForeignKey("srs.substance.substance_id"), nullable=False),
        sa.Column("alias_value", sa.String(255), nullable=False),
        sa.Column("alias_type", sa.String(32)),
        sa.Column("notes", sa.Text),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("NOW()")),
        sa.Column("created_by", sa.BigInteger, nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True)),
        schema="srs",
    )
    op.execute(
        "CREATE INDEX ix_substance_alias_value "
        "ON srs.substance_alias USING gin(alias_value gin_trgm_ops)"
    )
    op.create_index(
        "ix_substance_alias_substance", "substance_alias",
        ["substance_id"], schema="srs",
    )
    op.execute("""
        CREATE TRIGGER trg_substance_alias_audit
        AFTER INSERT OR UPDATE OR DELETE ON srs.substance_alias
        FOR EACH ROW EXECUTE FUNCTION audit.fn_audit_trigger(
            'alias_id', '', 'srs.substance:substance_id:substance_code:substance_id'
        );
    """)


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_substance_alias_audit ON srs.substance_alias")
    op.execute("DROP INDEX IF EXISTS srs.ix_substance_alias_value")
    op.drop_table("substance_alias", schema="srs")

    op.execute("DROP TRIGGER IF EXISTS trg_substance_sm_audit ON srs.substance_small_molecule")
    op.execute("DROP INDEX IF EXISTS srs.uq_substance_sm_inchi_key")
    op.drop_table("substance_small_molecule", schema="srs")

    op.execute("DROP TRIGGER IF EXISTS trg_substance_adc_audit ON srs.substance_adc")
    op.drop_table("substance_adc", schema="srs")
