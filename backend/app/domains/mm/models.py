"""Material Master ORM 模型

全公司物料身份注册表，作为下游 cmc-inventory 的数据上游。
"""
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class Material(Base):
    """物料主表（身份注册）"""

    __tablename__ = "material"
    __table_args__ = (
        UniqueConstraint("material_code", name="uq_material_code"),
        CheckConstraint(
            "material_type IN ('reagent','consumable','standard','column')",
            name="ck_material_type",
        ),
        CheckConstraint(
            "status IN ('active','quarantine','released','rejected','retired')",
            name="ck_material_status",
        ),
        CheckConstraint(
            "category IS NULL OR category IN ("
            "'一般耗材','关键耗材','关键试剂','内包材','外包材','劳保',"
            "'原辅料','参比品','对照品','工艺用水/气','标准品',"
            "'细胞种子','自制包材','试剂','运输包装材料')",
            name="ck_material_category",
        ),
        {"schema": "mm"},
    )

    material_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    material_code: Mapped[str] = mapped_column(String(32), nullable=False)

    # 基本信息
    material_name: Mapped[str] = mapped_column(String(255), nullable=False)
    material_name_en: Mapped[str | None] = mapped_column(String(255))
    material_type: Mapped[str] = mapped_column(String(32), nullable=False)
    category: Mapped[str | None] = mapped_column(String(50))

    # 物质引用
    substance_id: Mapped[int | None] = mapped_column(BigInteger)

    # 供应商 & 规格
    manufacturer: Mapped[str | None] = mapped_column(String(100))
    catalog_no: Mapped[str | None] = mapped_column(String(100))
    spec_model: Mapped[str | None] = mapped_column(String(200))
    unit: Mapped[str] = mapped_column(String(20), nullable=False, default="ea")
    package_spec: Mapped[str | None] = mapped_column(String(100))

    # 危化品分类（多选）
    hazard_class: Mapped[list[str] | None] = mapped_column(ARRAY(String))

    # 物理属性
    physical_form: Mapped[str | None] = mapped_column(String(64))
    storage_condition: Mapped[str | None] = mapped_column(String(64))

    # 来源
    source_type: Mapped[str | None] = mapped_column(String(32))
    source_name: Mapped[str | None] = mapped_column(String(128))

    # 级别（自由文本）
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
        Index(
            "uq_material_batch_active", "material_id", "batch_number", unique=True,
            postgresql_where=text("deleted_at IS NULL"),
        ),
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
