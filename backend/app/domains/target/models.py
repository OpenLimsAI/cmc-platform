"""靶点域 ORM 模型（tgt.target / tgt.target_source_snapshot / ref.molecule_target）

设计决策：docs/decisions/2026-08-17-target-domain.md
  - 主表 tgt.target：靶点"是什么"的稳定主属性，锚点 uniprot_id（未删除行内唯一）；
    0051 起字段直接对齐 UniProt 标准（keywords / subcellular_locations / cd_antigen_names / ec_numbers…），
    自定义"类型/定位"枚举已废除
  - 快照表 tgt.target_source_snapshot：外部源（UniProt / ChEMBL）裁剪后的原始 JSON，append-only，不挂审计
  - 关联表 ref.molecule_target：分子（= srs.substance）↔ 靶点，PK (molecule_id, target_id, relation_role)
  - 轻档审核：status draft/published/retired，无状态机表、无电签（对标 mm/eqp）
"""
from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base

TARGET_STATUSES = ("draft", "published", "retired")
MOLECULE_TARGET_ROLES = ("antibody_target", "payload_target", "other")
SNAPSHOT_SOURCES = ("uniprot", "chembl_target", "chembl_molecule", "chembl_mechanism", "other")


class Target(Base):
    """靶点主表（tgt.target）"""

    __tablename__ = "target"
    __table_args__ = (
        UniqueConstraint("target_code", name="uq_tgt_target_code"),
        CheckConstraint(
            "status IN ('draft','published','retired')",
            name="ck_target_status",
        ),
        {"schema": "tgt"},
    )

    target_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    # 靶点编码 TGT-NNNNNN：留空由 tgt.fn_target_assign_code 触发器取号
    target_code: Mapped[str] = mapped_column(String(32), nullable=False)

    target_name: Mapped[str] = mapped_column(String(255), nullable=False)
    uniprot_id: Mapped[str | None] = mapped_column(String(16))
    gene_symbol: Mapped[str | None] = mapped_column(String(64))
    organism: Mapped[str | None] = mapped_column(String(128), default="Homo sapiens")
    # 别名 / 短名 / 次级 accession（list[str]）——查重需同时匹配主+次级 accession
    aliases: Mapped[list | None] = mapped_column(JSONB)

    # ---- UniProt 标准字段（0051；全部自动拉取，可空以容纳无 UniProt 号的特殊靶点）----
    entry_type: Mapped[str | None] = mapped_column(String(64))          # UniProtKB reviewed (Swiss-Prot) / unreviewed (TrEMBL)
    protein_existence: Mapped[str | None] = mapped_column(String(64))   # "1: Evidence at protein level"
    cd_antigen_names: Mapped[list | None] = mapped_column(JSONB)        # ["CD279"]
    gene_synonyms: Mapped[list | None] = mapped_column(JSONB)           # ["SGRF"]
    tax_id: Mapped[int | None] = mapped_column(Integer)                 # 9606
    keywords: Mapped[list | None] = mapped_column(JSONB)                # [{"id","name","category"}]
    subcellular_locations: Mapped[list | None] = mapped_column(JSONB)   # [{"id","location","topology","topology_id","molecule"}]
    ec_numbers: Mapped[list | None] = mapped_column(JSONB)              # ["2.7.10.1"]
    domains: Mapped[list | None] = mapped_column(JSONB)                 # [{"type","description","start","end"}]
    sequence_length: Mapped[int | None] = mapped_column(Integer)
    mol_weight: Mapped[int | None] = mapped_column(Integer)             # Da
    sequence_md5: Mapped[str | None] = mapped_column(String(32))
    sequence_crc64: Mapped[str | None] = mapped_column(String(16))
    sequence: Mapped[str | None] = mapped_column(Text)                  # 完整单字母序列（UniProt canonical）
    uniprot_entry_version: Mapped[int | None] = mapped_column(Integer)
    uniprot_fetched_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    status: Mapped[str] = mapped_column(String(32), nullable=False, default="draft")

    description: Mapped[str | None] = mapped_column(Text)
    notes: Mapped[str | None] = mapped_column(Text)
    extra: Mapped[dict | None] = mapped_column(JSONB)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    created_by: Mapped[int] = mapped_column(BigInteger, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_by: Mapped[int] = mapped_column(BigInteger, nullable=False)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    deleted_by: Mapped[int | None] = mapped_column(BigInteger)


class TargetSourceSnapshot(Base):
    """外部源快照（tgt.target_source_snapshot）——append-only，不挂审计触发器"""

    __tablename__ = "target_source_snapshot"
    __table_args__ = (
        CheckConstraint(
            "source IN ('uniprot','chembl_target','chembl_molecule','chembl_mechanism','other')",
            name="ck_target_snapshot_source",
        ),
        {"schema": "tgt"},
    )

    snapshot_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    target_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("tgt.target.target_id"), nullable=False
    )
    source: Mapped[str] = mapped_column(String(32), nullable=False)
    source_id: Mapped[str | None] = mapped_column(String(64))
    source_version: Mapped[str | None] = mapped_column(String(64))
    source_url: Mapped[str | None] = mapped_column(Text)
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False)
    license: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    created_by: Mapped[int] = mapped_column(BigInteger, nullable=False)


class MoleculeTargetLink(Base):
    """分子↔靶点关联（ref.molecule_target）；分子 = srs.substance"""

    __tablename__ = "molecule_target"
    __table_args__ = (
        CheckConstraint(
            "relation_role IN ('antibody_target','payload_target','other')",
            name="ck_ref_mt_role",
        ),
        {"schema": "ref"},
    )

    molecule_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("srs.substance.substance_id"), primary_key=True
    )
    target_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("tgt.target.target_id"), primary_key=True
    )
    relation_role: Mapped[str] = mapped_column(
        String(32), primary_key=True, default="antibody_target"
    )
    moa: Mapped[str | None] = mapped_column(Text)
    action_type: Mapped[str | None] = mapped_column(String(64))
    binding_epitope_or_domain: Mapped[str | None] = mapped_column(Text)
    chembl_mechanism_id: Mapped[int | None] = mapped_column(BigInteger)
    needs_confirm: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    notes: Mapped[str | None] = mapped_column(Text)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    created_by: Mapped[int] = mapped_column(BigInteger, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_by: Mapped[int] = mapped_column(BigInteger, nullable=False)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    deleted_by: Mapped[int | None] = mapped_column(BigInteger)
