"""tgt.target 改为 UniProt 标准字段：去掉自定义 target_type/target_location，新增 UniProt 核心字段

Revision ID: 0051_tgt_uniprot_fields
Revises: 0050_tgt_target
Create Date: 2026-08-18 02:00:00.000000

负责人决策（2026-08-18）：自定义的"靶点类型 5 选 1 / 靶点定位 4 选 1"不是标准分类，废除；
改为直接存 UniProt 受控词表/字段（全部自动拉取，人不手填）：
  - keywords（KW 编号 + 类别，多值）替代"类型"；subcellular_locations（SL 编号 + 拓扑，多值）替代"定位"
  - cd_antigen_names / gene_synonyms / ec_numbers / domains / protein_existence / entry_type
  - sequence_length / mol_weight / sequence_md5（身份校验，不存全序列）
  - uniprot_entry_version / uniprot_fetched_at（溯源，配合快照表）
生产库当时 0 条靶点，直接 drop 列无数据迁移。
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0051_tgt_uniprot_fields"
down_revision: str | None = "0050_tgt_target"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # ---- 去掉自定义枚举 ----
    op.drop_index("ix_tgt_target_type", table_name="target", schema="tgt")
    op.drop_index("ix_tgt_target_location", table_name="target", schema="tgt")
    op.drop_constraint("ck_target_type", "target", schema="tgt", type_="check")
    op.drop_constraint("ck_target_location", "target", schema="tgt", type_="check")
    op.drop_column("target", "target_type", schema="tgt")
    op.drop_column("target", "target_location", schema="tgt")
    op.execute("DELETE FROM meta.lookup_value WHERE lookup_type IN ('target_type','target_location')")

    # ---- UniProt 标准字段（全部可空：无 UniProt 号的特殊靶点仍可手填名称/基因兜底）----
    op.add_column("target", sa.Column("entry_type", sa.String(64)), schema="tgt")            # UniProtKB reviewed (Swiss-Prot) / unreviewed (TrEMBL)
    op.add_column("target", sa.Column("protein_existence", sa.String(64)), schema="tgt")     # 1: Evidence at protein level ...
    op.add_column("target", sa.Column("cd_antigen_names", postgresql.JSONB), schema="tgt")   # ["CD279"]
    op.add_column("target", sa.Column("gene_synonyms", postgresql.JSONB), schema="tgt")      # ["SGRF"]
    op.add_column("target", sa.Column("tax_id", sa.Integer), schema="tgt")                   # 9606
    op.add_column("target", sa.Column("keywords", postgresql.JSONB), schema="tgt")           # [{"id":"KW-0675","name":"Receptor","category":"Molecular function"}]
    op.add_column("target", sa.Column("subcellular_locations", postgresql.JSONB), schema="tgt")  # [{"id":"SL-0039","location":"Cell membrane","topology":"Single-pass type I membrane protein","topology_id":"SL-9905"}]
    op.add_column("target", sa.Column("ec_numbers", postgresql.JSONB), schema="tgt")         # ["2.7.10.1"]
    op.add_column("target", sa.Column("domains", postgresql.JSONB), schema="tgt")            # [{"type":"Domain","description":"Protein kinase","start":720,"end":987}]
    op.add_column("target", sa.Column("sequence_length", sa.Integer), schema="tgt")
    op.add_column("target", sa.Column("mol_weight", sa.Integer), schema="tgt")               # Da
    op.add_column("target", sa.Column("sequence_md5", sa.String(32)), schema="tgt")
    op.add_column("target", sa.Column("uniprot_entry_version", sa.Integer), schema="tgt")
    op.add_column("target", sa.Column("uniprot_fetched_at", sa.DateTime(timezone=True)), schema="tgt")

    # jsonb 包含查询（关键词 / 定位筛选）
    op.execute("CREATE INDEX ix_tgt_target_keywords ON tgt.target USING gin(keywords jsonb_path_ops)")
    op.execute("CREATE INDEX ix_tgt_target_subcell ON tgt.target USING gin(subcellular_locations jsonb_path_ops)")
    op.create_index(
        "ix_tgt_target_entry_type", "target", ["entry_type"],
        postgresql_where=sa.text("deleted_at IS NULL"), schema="tgt",
    )


def downgrade() -> None:
    op.drop_index("ix_tgt_target_entry_type", table_name="target", schema="tgt")
    op.execute("DROP INDEX IF EXISTS tgt.ix_tgt_target_subcell")
    op.execute("DROP INDEX IF EXISTS tgt.ix_tgt_target_keywords")
    for col in ("uniprot_fetched_at", "uniprot_entry_version", "sequence_md5", "mol_weight", "sequence_length",
                "domains", "ec_numbers", "subcellular_locations", "keywords", "tax_id", "gene_synonyms",
                "cd_antigen_names", "protein_existence", "entry_type"):
        op.drop_column("target", col, schema="tgt")

    op.add_column("target", sa.Column("target_type", sa.String(32), nullable=False, server_default="其他"), schema="tgt")
    op.add_column("target", sa.Column("target_location", sa.String(32), nullable=False, server_default="膜型"), schema="tgt")
    op.create_check_constraint("ck_target_type", "target",
                               "target_type IN ('受体','配体·细胞因子','表面抗原','酶','其他')", schema="tgt")
    op.create_check_constraint("ck_target_location", "target",
                               "target_location IN ('膜型','可溶型','两者都有','胞内')", schema="tgt")
    op.create_index("ix_tgt_target_type", "target", ["target_type"],
                    postgresql_where=sa.text("deleted_at IS NULL"), schema="tgt")
    op.create_index("ix_tgt_target_location", "target", ["target_location"],
                    postgresql_where=sa.text("deleted_at IS NULL"), schema="tgt")
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
          ('target_location', '胞内',    '胞内',         'intracellular',      40)
        ON CONFLICT (lookup_type, lookup_code) DO NOTHING
    """)
