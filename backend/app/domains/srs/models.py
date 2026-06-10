"""
Substance Registration System ORM 模型
对齐 DM-MDM-001 V1.0 第 7 章
"""
from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class Substance(Base):
    __tablename__ = "substance"
    __table_args__ = (
        UniqueConstraint("substance_code", name="uq_substance_substance_code"),
        # 0045：internal_code 唯一性仅约束未删行（软删后允许复用，H-08 策略 B）
        Index(
            "uq_substance_internal_code_active", "internal_code",
            unique=True, postgresql_where=text("deleted_at IS NULL"),
        ),
        CheckConstraint(
            "substance_type IN ('mab','bispecific','adc','fusion','small_molecule','oligonucleotide','other')",
            name="ck_substance_substance_type",
        ),
        CheckConstraint(
            "status IN ('draft','registered','active','restricted','deprecated','obsoleted')",
            name="ck_substance_status",
        ),
        CheckConstraint(
            "confidentiality IN ('public','internal','restricted')",
            name="ck_substance_confidentiality",
        ),
        {"schema": "srs"},
    )

    substance_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    substance_code: Mapped[str] = mapped_column(String(32), nullable=False)
    substance_type: Mapped[str] = mapped_column(String(32), nullable=False)
    internal_code: Mapped[str | None] = mapped_column(String(64))

    preferred_name: Mapped[str] = mapped_column(String(255), nullable=False)
    preferred_name_en: Mapped[str | None] = mapped_column(String(255))
    display_name: Mapped[str | None] = mapped_column(String(255))

    target: Mapped[str | None] = mapped_column(String(128))
    target_type: Mapped[str | None] = mapped_column(String(64))
    modality: Mapped[str | None] = mapped_column(String(64))

    status: Mapped[str] = mapped_column(String(32), nullable=False, default="draft")
    is_proprietary: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    confidentiality: Mapped[str] = mapped_column(String(16), nullable=False, default="internal")

    external_uuid: Mapped[UUID | None] = mapped_column(
        PgUUID(as_uuid=True), server_default=func.gen_random_uuid()
    )

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

    registered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    registered_by: Mapped[int | None] = mapped_column(BigInteger)

    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    deleted_by: Mapped[int | None] = mapped_column(BigInteger)

    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)


class SubstanceProtein(Base):
    __tablename__ = "substance_protein"
    __table_args__ = ({"schema": "srs"},)

    substance_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("srs.substance.substance_id", ondelete="CASCADE"),
        primary_key=True,
    )

    heavy_chain_sequence: Mapped[str | None] = mapped_column(Text)
    light_chain_sequence: Mapped[str | None] = mapped_column(Text)
    additional_chains: Mapped[dict | None] = mapped_column(JSONB)
    sequence_length_hc: Mapped[int | None] = mapped_column(Integer)
    sequence_length_lc: Mapped[int | None] = mapped_column(Integer)
    sequence_hash_hc: Mapped[str | None] = mapped_column(String(64))
    sequence_hash_lc: Mapped[str | None] = mapped_column(String(64))

    isotype: Mapped[str | None] = mapped_column(String(32))
    architecture: Mapped[str | None] = mapped_column(String(64))
    disulfide_bonds: Mapped[dict | None] = mapped_column(JSONB)
    glycosylation_sites: Mapped[dict | None] = mapped_column(JSONB)
    ptm_info: Mapped[dict | None] = mapped_column(JSONB)

    expression_system: Mapped[str | None] = mapped_column(String(64))
    cell_line: Mapped[str | None] = mapped_column(String(128))
    expression_vector: Mapped[str | None] = mapped_column(String(128))

    molecular_weight_da: Mapped[float | None] = mapped_column()
    pi_theoretical: Mapped[float | None] = mapped_column()
    # V1.2 §S7 决议（修订十一）：永久接受 Float — 实验测定值常带小数
    extinction_coefficient: Mapped[float | None] = mapped_column(Float)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class SubstanceStatusHistory(Base):
    __tablename__ = "substance_status_history"
    __table_args__ = ({"schema": "srs"},)

    history_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    substance_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("srs.substance.substance_id"), nullable=False
    )
    old_status: Mapped[str | None] = mapped_column(String(32))
    new_status: Mapped[str] = mapped_column(String(32), nullable=False)
    change_reason: Mapped[str] = mapped_column(Text, nullable=False)
    changed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    changed_by: Mapped[int] = mapped_column(BigInteger, nullable=False)
    e_signature_id: Mapped[int | None] = mapped_column(BigInteger)
    merged_to_substance_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("srs.substance.substance_id")
    )


class SubstanceXref(Base):
    __tablename__ = "substance_xref"
    __table_args__ = (
        CheckConstraint(
            "xref_type IN ('INN','USAN','CAS','UNII','GSRS_UUID','ChEMBL','DRUGBANK',"
            "'TRADE_NAME','GENERIC_NAME','HISTORICAL_CODE','PROJECT_CODE','OTHER')",
            name="ck_substance_xref_xref_type",
        ),
        {"schema": "srs"},
    )

    xref_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    substance_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("srs.substance.substance_id"), nullable=False
    )
    xref_type: Mapped[str] = mapped_column(String(32), nullable=False)
    xref_value: Mapped[str] = mapped_column(String(255), nullable=False)
    xref_source: Mapped[str | None] = mapped_column(String(64))
    region: Mapped[str | None] = mapped_column(String(16))
    is_primary: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
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

    # M3.0.3：§7.6 加 effective_date / expiry_date（生效与失效区间）
    effective_date: Mapped[date | None] = mapped_column(Date)
    expiry_date: Mapped[date | None] = mapped_column(Date)


class SubstanceADC(Base):
    """§7.4 ADC 扩展：父子 substance 血缘 + DAR"""

    __tablename__ = "substance_adc"
    __table_args__ = (
        CheckConstraint(
            "dar_average IS NULL OR (dar_average >= 0 AND dar_average <= 30)",
            name="ck_substance_adc_dar",
        ),
        {"schema": "srs"},
    )

    substance_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("srs.substance.substance_id", ondelete="CASCADE"),
        primary_key=True,
    )
    antibody_substance_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("srs.substance.substance_id"), nullable=False
    )
    linker_substance_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("srs.substance.substance_id")
    )
    payload_substance_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("srs.substance.substance_id"), nullable=False
    )

    dar_average: Mapped[Decimal | None] = mapped_column(Numeric(4, 2))
    dar_distribution: Mapped[dict | None] = mapped_column(JSONB)
    dar_method: Mapped[str | None] = mapped_column(String(64))

    conjugation_chemistry: Mapped[str | None] = mapped_column(String(64))
    conjugation_site: Mapped[str | None] = mapped_column(String(128))

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class SubstanceSmallMolecule(Base):
    """§7.5 小分子扩展：smiles / inchi / molecular_formula"""

    __tablename__ = "substance_small_molecule"
    __table_args__ = ({"schema": "srs"},)

    substance_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("srs.substance.substance_id", ondelete="CASCADE"),
        primary_key=True,
    )
    smiles: Mapped[str | None] = mapped_column(Text)
    inchi: Mapped[str | None] = mapped_column(Text)
    inchi_key: Mapped[str | None] = mapped_column(String(27))
    molecular_formula: Mapped[str | None] = mapped_column(String(64))
    molecular_weight: Mapped[Decimal | None] = mapped_column(Numeric(10, 4))
    salt_form: Mapped[str | None] = mapped_column(String(64))
    crystal_form: Mapped[str | None] = mapped_column(String(64))
    stereochemistry: Mapped[str | None] = mapped_column(String(64))
    extra: Mapped[dict | None] = mapped_column(JSONB)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class SubstanceAlias(Base):
    """§7.8 物质曾用名 / 项目代号"""

    __tablename__ = "substance_alias"
    __table_args__ = ({"schema": "srs"},)

    alias_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    substance_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("srs.substance.substance_id"), nullable=False
    )
    alias_value: Mapped[str] = mapped_column(String(255), nullable=False)
    alias_type: Mapped[str | None] = mapped_column(String(32))
    notes: Mapped[str | None] = mapped_column(Text)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    created_by: Mapped[int] = mapped_column(BigInteger, nullable=False)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
