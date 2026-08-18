"""tgt 靶点域：tgt.target + tgt.target_source_snapshot + ref.molecule_target

Revision ID: 0050_tgt_target
Revises: 0049_prs_smp_v21_batch3
Create Date: 2026-08-18 01:00:00.000000

设计决策见 docs/decisions/2026-08-17-target-domain.md（7 项拍板）：
  1. 主表放新 schema tgt，关联表放 ref（不用 dim/bridge）
  2. 分子域复用 srs.substance：ref.molecule_target.molecule_id → srs.substance.substance_id
  3. ADC 载荷靶点保留：relation_role ∈ antibody_target / payload_target / other
  4. 审核流走轻档（对标 mm/eqp）：status draft/published/retired，无状态机表、无电签
  5. 外部原始 JSON 拆独立快照表 tgt.target_source_snapshot（append-only，不挂审计触发器）
  6. 枚举硬编码 CHECK（target_type 5 值 / target_location 4 值）
  7. 编码 TGT-NNNNNN 全局序列（靶点不按年产生），BEFORE INSERT 触发器取号

一期只增不改：不动 srs.substance 任何 DDL。
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0050_tgt_target"
down_revision: str | None = "0049_prs_smp_v21_batch3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # ============== tgt schema ==============
    op.execute("CREATE SCHEMA IF NOT EXISTS tgt")

    # ============== tgt.target ==============
    op.create_table(
        "target",
        sa.Column("target_id", sa.BigInteger, sa.Identity(always=True), primary_key=True),
        sa.Column("target_code", sa.String(32), nullable=False),
        # 主属性（稳定；监管/市场状态不在 MDM）
        sa.Column("target_name", sa.String(255), nullable=False),
        sa.Column("uniprot_id", sa.String(16)),          # 锚点：UniProt 主 accession（可空以容纳非蛋白/未知靶点）
        sa.Column("gene_symbol", sa.String(64)),
        sa.Column("organism", sa.String(128), server_default="Homo sapiens"),
        sa.Column("aliases", postgresql.JSONB),          # 别名/短名/次级 accession 列表（查重时匹配次级 accession）
        sa.Column("target_type", sa.String(32), nullable=False),
        sa.Column("target_location", sa.String(32), nullable=False),
        # 轻档审核：draft → published → retired（PUT/动作端点直接改，无状态机表）
        sa.Column("status", sa.String(32), nullable=False, server_default="draft"),
        # 描述
        sa.Column("description", sa.Text),
        sa.Column("notes", sa.Text),
        sa.Column("extra", postgresql.JSONB),
        # 审计
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.Column("created_by", sa.BigInteger, sa.ForeignKey("auth.user.user_id"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.Column("updated_by", sa.BigInteger, sa.ForeignKey("auth.user.user_id"), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True)),
        sa.Column("deleted_by", sa.BigInteger, sa.ForeignKey("auth.user.user_id")),
        # 约束
        sa.UniqueConstraint("target_code", name="uq_tgt_target_code"),
        sa.CheckConstraint(
            "target_type IN ('受体','配体·细胞因子','表面抗原','酶','其他')",
            name="ck_target_type",
        ),
        sa.CheckConstraint(
            "target_location IN ('膜型','可溶型','两者都有','胞内')",
            name="ck_target_location",
        ),
        sa.CheckConstraint(
            "status IN ('draft','published','retired')",
            name="ck_target_status",
        ),
        schema="tgt",
    )

    # uniprot_id 唯一（未删除行内）——查重锚点
    op.create_index(
        "uq_tgt_target_uniprot_id", "target", ["uniprot_id"],
        unique=True, postgresql_where=sa.text("deleted_at IS NULL AND uniprot_id IS NOT NULL"),
        schema="tgt",
    )
    op.create_index(
        "ix_tgt_target_type", "target", ["target_type"],
        postgresql_where=sa.text("deleted_at IS NULL"), schema="tgt",
    )
    op.create_index(
        "ix_tgt_target_location", "target", ["target_location"],
        postgresql_where=sa.text("deleted_at IS NULL"), schema="tgt",
    )
    op.create_index(
        "ix_tgt_target_status", "target", ["status"],
        postgresql_where=sa.text("deleted_at IS NULL"), schema="tgt",
    )
    op.execute(
        "CREATE INDEX ix_tgt_target_name "
        "ON tgt.target USING gin(target_name gin_trgm_ops)"
    )

    # ============== BEFORE UPDATE: 维护 updated_at ==============
    op.execute("""
        CREATE OR REPLACE FUNCTION tgt.fn_target_before_update()
        RETURNS TRIGGER AS $$
        BEGIN
            NEW.updated_at := NOW();
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
    """)
    op.execute("""
        CREATE TRIGGER trg_target_before_update
        BEFORE UPDATE ON tgt.target
        FOR EACH ROW EXECUTE FUNCTION tgt.fn_target_before_update();
    """)

    # ============== 取号：TGT-NNNNNN 全局序列 ==============
    op.execute("""
        INSERT INTO meta.code_sequence (sequence_name, prefix, padding_length, description)
        VALUES ('target', 'TGT-', 6, 'Target master code (tgt.target), global sequence')
        ON CONFLICT (sequence_name) DO NOTHING
    """)
    op.execute("""
        CREATE OR REPLACE FUNCTION tgt.fn_target_assign_code()
        RETURNS TRIGGER AS $$
        BEGIN
            IF NEW.target_code IS NULL OR NEW.target_code = '' THEN
                NEW.target_code := meta.fn_next_code('target');
            END IF;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
    """)
    op.execute("""
        CREATE TRIGGER trg_target_assign_code
        BEFORE INSERT ON tgt.target
        FOR EACH ROW EXECUTE FUNCTION tgt.fn_target_assign_code();
    """)

    # ============== 接入审计 v3 ==============
    op.execute("""
        CREATE TRIGGER trg_target_audit
        AFTER INSERT OR UPDATE OR DELETE ON tgt.target
        FOR EACH ROW EXECUTE FUNCTION audit.fn_audit_trigger('target_id', 'target_code');
    """)

    # ============== tgt.target_source_snapshot（append-only，不挂审计）==============
    op.create_table(
        "target_source_snapshot",
        sa.Column("snapshot_id", sa.BigInteger, sa.Identity(always=True), primary_key=True),
        sa.Column("target_id", sa.BigInteger,
                  sa.ForeignKey("tgt.target.target_id"), nullable=False),
        sa.Column("source", sa.String(32), nullable=False),          # uniprot / chembl_target / chembl_molecule / chembl_mechanism
        sa.Column("source_id", sa.String(64)),                       # 外部 ID：UniProt accession / ChEMBL ID
        sa.Column("source_version", sa.String(64)),                  # UniProt entryVersion / ChEMBL release 等
        sa.Column("source_url", sa.Text),
        sa.Column("fetched_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("payload", postgresql.JSONB, nullable=False),      # 裁剪后的原始 JSON（来源署名见 license 字段）
        sa.Column("license", sa.String(64)),                         # 如 'CC BY-SA 3.0 (ChEMBL)' / 'CC BY 4.0 (UniProt)'
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.Column("created_by", sa.BigInteger, sa.ForeignKey("auth.user.user_id"), nullable=False),
        sa.CheckConstraint(
            "source IN ('uniprot','chembl_target','chembl_molecule','chembl_mechanism','other')",
            name="ck_target_snapshot_source",
        ),
        schema="tgt",
    )
    op.create_index(
        "ix_tgt_snapshot_target", "target_source_snapshot",
        ["target_id", "source", "fetched_at"], schema="tgt",
    )

    # ============== ref.molecule_target（分子↔靶点，分子 = srs.substance）==============
    op.create_table(
        "molecule_target",
        sa.Column("molecule_id", sa.BigInteger,
                  sa.ForeignKey("srs.substance.substance_id"), nullable=False),
        sa.Column("target_id", sa.BigInteger,
                  sa.ForeignKey("tgt.target.target_id"), nullable=False),
        sa.Column("relation_role", sa.String(32), nullable=False, server_default="antibody_target"),
        sa.Column("moa", sa.Text),                                   # 作用机制（ChEMBL mechanism_of_action 或人工）
        sa.Column("action_type", sa.String(64)),                     # INHIBITOR / BINDING AGENT / ...
        sa.Column("binding_epitope_or_domain", sa.Text),             # 结合表位 / 结构域 / 亚基
        sa.Column("chembl_mechanism_id", sa.BigInteger),             # ChEMBL mec_id（可空）
        sa.Column("needs_confirm", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("notes", sa.Text),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.Column("created_by", sa.BigInteger, nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.Column("updated_by", sa.BigInteger, nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True)),
        sa.Column("deleted_by", sa.BigInteger),
        sa.PrimaryKeyConstraint(
            "molecule_id", "target_id", "relation_role",
            name="pk_ref_molecule_target",
        ),
        sa.CheckConstraint(
            "relation_role IN ('antibody_target','payload_target','other')",
            name="ck_ref_mt_role",
        ),
        schema="ref",
    )
    op.create_index(
        "ix_ref_mt_molecule", "molecule_target", ["molecule_id"],
        postgresql_where=sa.text("deleted_at IS NULL"), schema="ref",
    )
    op.create_index(
        "ix_ref_mt_target", "molecule_target", ["target_id"],
        postgresql_where=sa.text("deleted_at IS NULL"), schema="ref",
    )
    # 审计：第 1 参数 target_id，第 3 参数 parent_ref 回填 target_code（对齐 0025 ref_as 写法）
    op.execute("""
        CREATE TRIGGER trg_ref_mt_audit
        AFTER INSERT OR UPDATE OR DELETE ON ref.molecule_target
        FOR EACH ROW EXECUTE FUNCTION audit.fn_audit_trigger(
            'target_id', '', 'tgt.target:target_id:target_code:target_id'
        );
    """)

    # ============== meta.lookup_value 字典（对齐设计基准，前端暂不读）==============
    op.execute("""
        INSERT INTO meta.lookup_value (lookup_type, lookup_code, lookup_name, lookup_name_en, sort_order)
        VALUES
          ('target_type', '受体',        '受体',         'receptor',           10),
          ('target_type', '配体·细胞因子', '配体·细胞因子', 'ligand_cytokine',    20),
          ('target_type', '表面抗原',    '表面抗原',     'surface_antigen',    30),
          ('target_type', '酶',          '酶',           'enzyme',             40),
          ('target_type', '其他',        '其他',         'other',              90),
          ('target_location', '膜型',    '膜型',         'membrane',           10),
          ('target_location', '可溶型',  '可溶型',       'soluble',            20),
          ('target_location', '两者都有','两者都有',     'both',               30),
          ('target_location', '胞内',    '胞内',         'intracellular',      40),
          ('target_status', 'draft',     '草稿',         'draft',              10),
          ('target_status', 'published', '已发布',       'published',          20),
          ('target_status', 'retired',   '已退役',       'retired',            30),
          ('molecule_target_role', 'antibody_target', '抗体结合靶点', 'antibody_target', 10),
          ('molecule_target_role', 'payload_target',  '载荷作用靶点', 'payload_target',  20),
          ('molecule_target_role', 'other',           '其他',         'other',           90)
        ON CONFLICT (lookup_type, lookup_code) DO NOTHING
    """)


def downgrade() -> None:
    op.execute(
        "DELETE FROM meta.lookup_value WHERE lookup_type IN "
        "('target_type','target_location','target_status','molecule_target_role')"
    )
    op.execute("DROP TRIGGER IF EXISTS trg_ref_mt_audit ON ref.molecule_target")
    op.drop_table("molecule_target", schema="ref")
    op.drop_table("target_source_snapshot", schema="tgt")
    op.execute("DROP TRIGGER IF EXISTS trg_target_audit ON tgt.target")
    op.execute("DROP TRIGGER IF EXISTS trg_target_assign_code ON tgt.target")
    op.execute("DROP FUNCTION IF EXISTS tgt.fn_target_assign_code()")
    op.execute("DROP TRIGGER IF EXISTS trg_target_before_update ON tgt.target")
    op.execute("DROP FUNCTION IF EXISTS tgt.fn_target_before_update()")
    op.drop_table("target", schema="tgt")
    op.execute("DELETE FROM meta.code_sequence WHERE sequence_name = 'target'")
    op.execute("DROP SCHEMA IF EXISTS tgt")
