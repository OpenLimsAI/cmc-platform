"""Material Master Lite ORM 模型

对齐 DM-MDM-001 V1.1 §10。
"""
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class Material(Base):
    """§10.1 物料主表"""

    __tablename__ = "material"
    __table_args__ = (
        UniqueConstraint("material_code", name="uq_material_code"),
        CheckConstraint(
            "material_type IN ('candidate','reference','stability','buffer','raw',"
            "'intermediate','other')",
            name="ck_material_type",
        ),
        CheckConstraint(
            "grade IS NULL OR grade IN "
            "('RUO','GMP','Reference Standard','Working Standard')",
            name="ck_material_grade",
        ),
        CheckConstraint(
            "status IN ('active','quarantine','released','rejected','retired')",
            name="ck_material_status",
        ),
        {"schema": "mm"},
    )

    material_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    material_code: Mapped[str] = mapped_column(String(32), nullable=False)

    # 基本信息
    material_name: Mapped[str] = mapped_column(String(255), nullable=False)
    material_name_en: Mapped[str | None] = mapped_column(String(255))
    material_type: Mapped[str] = mapped_column(String(32), nullable=False)

    # 物质引用
    substance_id: Mapped[int | None] = mapped_column(BigInteger)

    # 物理属性
    physical_form: Mapped[str | None] = mapped_column(String(64))
    storage_condition: Mapped[str | None] = mapped_column(String(64))

    # 来源
    source_type: Mapped[str | None] = mapped_column(String(32))
    source_name: Mapped[str | None] = mapped_column(String(128))

    # 级别
    grade: Mapped[str | None] = mapped_column(String(32))

    # 状态（无状态机，PUT 直接改）
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="active")

    # 描述
    description: Mapped[str | None] = mapped_column(Text)
    notes: Mapped[str | None] = mapped_column(Text)
    extra: Mapped[dict | None] = mapped_column(JSONB)

    # 审计
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


class MaterialBatch(Base):
    """§10.2 物料批次"""

    __tablename__ = "material_batch"
    __table_args__ = (
        UniqueConstraint("material_id", "batch_number", name="uq_material_batch"),
        CheckConstraint(
            "status IN ('in_stock','in_use','depleted','expired','recalled')",
            name="ck_material_batch_status",
        ),
        {"schema": "mm"},
    )

    batch_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    material_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("mm.material.material_id"), nullable=False
    )
    batch_number: Mapped[str] = mapped_column(String(64), nullable=False)

    # 数量
    quantity_value: Mapped[Decimal | None] = mapped_column(Numeric(18, 4))
    quantity_unit: Mapped[str | None] = mapped_column(String(16))

    # 时间
    manufacture_date: Mapped[date | None] = mapped_column(Date)
    expiry_date: Mapped[date | None] = mapped_column(Date)
    receive_date: Mapped[date | None] = mapped_column(Date)

    # 状态（5 值；非 GxP 状态机，PUT 直接改）
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="in_stock")

    # 来源
    source_batch_ref: Mapped[str | None] = mapped_column(String(128))
    coa_url: Mapped[str | None] = mapped_column(Text)

    # 存储
    storage_location: Mapped[str | None] = mapped_column(String(128))
    notes: Mapped[str | None] = mapped_column(Text)
    extra: Mapped[dict | None] = mapped_column(JSONB)

    # 审计
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
