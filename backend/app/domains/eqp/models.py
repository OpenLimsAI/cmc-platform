"""Equipment Master ORM 模型

全公司仪器设备身份注册表，作为下游 CMC LabOps Portal(cmc-inventory) 的数据上游。
仅管主数据(身份/采购属性);运营数据(在用状态/位置/负责人/校验/维护/维修)在 LabOps。
"""
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class Equipment(Base):
    """设备主表（身份注册）"""

    __tablename__ = "equipment"
    __table_args__ = (
        UniqueConstraint("equipment_code", name="uq_eqp_equipment_code"),
        CheckConstraint(
            "category IN ('分析仪器','工艺/制备设备','通用实验室设备',"
            "'公用工程/环境与支持系统','IT/自动化与数据系统')",
            name="ck_equipment_category",
        ),
        CheckConstraint(
            "status IN ('active','retired')",
            name="ck_equipment_status",
        ),
        # 分级字典按分类走：分析仪器(检验设备)=A/B/C(USP)；其他分类=关键/一般（0056）
        CheckConstraint(
            "criticality IS NULL "
            "OR (category = '分析仪器' AND criticality IN ('A','B','C')) "
            "OR (category <> '分析仪器' AND criticality IN ('关键','一般'))",
            name="ck_equipment_criticality",
        ),
        {"schema": "eqp"},
    )

    equipment_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    # 设备ID：系统生成 EQP-yyyy-NNNNNN，全局唯一、不可改（主数据主标识）
    equipment_code: Mapped[str] = mapped_column(String(32), nullable=False)
    # 设备编号(业务/历史号，如 QC001) + 固资编号(财务)
    equipment_no: Mapped[str | None] = mapped_column(String(64))
    fixed_asset_no: Mapped[str | None] = mapped_column(String(64))

    # 基本信息
    equipment_name: Mapped[str] = mapped_column(String(255), nullable=False)
    equipment_name_en: Mapped[str | None] = mapped_column(String(255))
    category: Mapped[str] = mapped_column(String(64), nullable=False)

    # 厂商 & 规格(身份属性)
    model: Mapped[str | None] = mapped_column(String(200))
    manufacturer: Mapped[str | None] = mapped_column(String(100))
    serial_no: Mapped[str | None] = mapped_column(String(100))
    rated_power: Mapped[str | None] = mapped_column(String(64))  # 额定功率(自由文本)
    origin: Mapped[str | None] = mapped_column(String(100))  # 产地

    # 采购属性
    purchase_date: Mapped[date | None] = mapped_column(Date)
    asset_value: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    supplier: Mapped[str | None] = mapped_column(String(200))

    # 公司级设备清单治理字段（0056，负责人 2026-09-10）
    department: Mapped[str | None] = mapped_column(String(64))  # 使用部门
    site: Mapped[str | None] = mapped_column(String(64))  # 厂区
    room: Mapped[str | None] = mapped_column(String(100))  # 房间/存放位置
    criticality: Mapped[str | None] = mapped_column(String(16))  # 分级 A/B/C 或 关键/一般
    criticality_basis: Mapped[str | None] = mapped_column(Text)  # 分级依据
    commission_date: Mapped[date | None] = mapped_column(Date)  # 首次启用日期

    # 主数据状态(无状态机,PUT 直接改;运营状态在 LabOps)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="active")

    # 附带专用工作站（如自带控制电脑的分析仪器；IT 类设备本身即电脑）
    has_workstation: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    workstation_info: Mapped[dict | None] = mapped_column(JSONB)

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
