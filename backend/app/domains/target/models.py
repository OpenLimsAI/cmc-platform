"""靶点域 ORM 模型（tgt.target / tgt.target_source_snapshot / ref.molecule_target）

设计决策：docs/decisions/2026-08-17-target-domain.md
  - 主表 tgt.target：靶点"是什么"的稳定主属性，锚点 uniprot_id（未删除行内唯一）
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
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base

TARGET_TYPES = ("受体", "配体·细胞因子", "表面抗原", "酶", "其他")
TARGET_LOCATIONS = ("膜型", "可溶型", "两者都有", "胞内")
TARGET_STATUSES = ("draft", "published", "retired")
MOLECULE_TARGET_ROLES = ("antibody_target", "payload_target", "other")
SNAPSHOT_SOURCES = ("uniprot", "chembl_target", "chembl_molecule", "chembl_mechanism", "other")


class Target(Base):
    """靶点主表（tgt.target）"""

    __tablename__ = "target"
    __table_args__ = (
        UniqueConstraint("target_code", name="uq_tgt_target_code"),
        CheckConstraint(
            "target_type IN ('受体','配体·细胞因子','表面抗原','酶','其他')",
            name="ck_target_type",
        ),
        CheckConstraint(
            "target_location IN ('膜型','可溶型','两者都有','胞内')",
            name="ck_target_location",
        ),
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
    target_type: Mapped[str] = mapped_column(String(32), nullable=False)
    target_location: Mapped[str] = mapped_column(String(32), nullable=False)

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
