"""
文件: backend/models_equipment.py
用途: SQLAlchemy 2.0 ORM 模型,对应 sql/equipment_init.sql 中 equipment_mgmt 的 7 张表
关键点:
    - 金额 Numeric(12,2),Python 端用 Decimal
    - created_by 等存 MDM 用户名快照,不对 MDM 库建外键
    - equipment 软删除(is_active),禁止物理删除
"""
from __future__ import annotations

from datetime import datetime, date
from decimal import Decimal
from typing import Optional

from sqlalchemy import (
    String,
    Integer,
    BigInteger,
    Boolean,
    Date,
    DateTime,
    Numeric,
    Text,
    ForeignKey,
    UniqueConstraint,
    CheckConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from database import Base

# 设备状态合法值
EQUIPMENT_STATUS_VALUES = {"in_use", "out_of_service", "scrapped", "in_repair", "in_calibration"}
CALIBRATION_RESULT_VALUES = {"qualified", "unqualified", "limited_use"}
MAINTENANCE_TYPE_VALUES = {"daily", "periodic", "special"}
REPAIR_TYPE_VALUES = {"internal", "external"}
ATTACHMENT_TAG_VALUES = {"sop", "certificate", "contract", "photo", "other"}


class Equipment(Base):
    __tablename__ = "equipment"
    __table_args__ = (
        UniqueConstraint("equipment_code", name="uq_equipment_code"),
        CheckConstraint(
            "status IN ('in_use','out_of_service','scrapped','in_repair','in_calibration')",
            name="ck_equipment_status",
        ),
        {"schema": "equipment_mgmt"},
    )

    equipment_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    # —— MDM 快照字段(权威源 eqp.equipment,建档/sync-mdm 时整体覆盖) ——
    equipment_code: Mapped[str] = mapped_column(String(32), nullable=False)
    equipment_no: Mapped[Optional[str]] = mapped_column(String(64))       # V1.4: 业务编号(如 QC001)
    fixed_asset_no: Mapped[Optional[str]] = mapped_column(String(64))     # V1.4: 固定资产号
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    name_en: Mapped[Optional[str]] = mapped_column(String(255))           # V1.4: 英文名称
    category: Mapped[str] = mapped_column(String(50), nullable=False)
    model: Mapped[Optional[str]] = mapped_column(String(200))
    manufacturer: Mapped[Optional[str]] = mapped_column(String(100))
    serial_no: Mapped[Optional[str]] = mapped_column(String(100))
    rated_power: Mapped[Optional[str]] = mapped_column(String(64))        # V1.4: 额定功率
    origin: Mapped[Optional[str]] = mapped_column(String(100))            # V1.4: 产地
    supplier: Mapped[Optional[str]] = mapped_column(String(200))          # V1.4: 供应商
    has_workstation: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)  # V1.4
    workstation_info: Mapped[Optional[dict]] = mapped_column(JSONB)       # V1.4: 工作站配置
    purchase_date: Mapped[Optional[date]] = mapped_column(Date)           # V1.4: 归属改 MDM 快照
    asset_value: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 2))  # V1.4: 归属改 MDM 快照
    mdm_status: Mapped[Optional[str]] = mapped_column(String(32))         # V1.4: active/retired
    mdm_synced_at: Mapped[Optional[datetime]] = mapped_column(DateTime)   # V1.4: 快照同步时间
    # —— 本地运营字段(LabOps 维护) ——
    location_room: Mapped[Optional[str]] = mapped_column(String(50))
    location_detail: Mapped[Optional[str]] = mapped_column(String(200))
    responsible_person: Mapped[Optional[str]] = mapped_column(String(50))
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="in_use")
    commission_date: Mapped[Optional[date]] = mapped_column(Date)
    remark: Mapped[Optional[str]] = mapped_column(Text)
    # MDM 引用: 主数据权威源在 MDM eqp 域;mdm=从 MDM 拉取,local=本地建(待补登 MDM)
    # DB 列为 BIGINT(对应 MDM eqp.equipment 大整数主键),ORM 对齐 BigInteger
    mdm_equipment_id: Mapped[Optional[int]] = mapped_column(BigInteger)
    data_source: Mapped[str] = mapped_column(String(20), nullable=False, default="local")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    deactivated_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    deactivated_by: Mapped[Optional[str]] = mapped_column(String(50))
    deactivate_reason: Mapped[Optional[str]] = mapped_column(String(200))
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    created_by: Mapped[Optional[str]] = mapped_column(String(50))
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_by: Mapped[Optional[str]] = mapped_column(String(50))


class EquipmentCalibration(Base):
    __tablename__ = "equipment_calibration"
    __table_args__ = (
        CheckConstraint(
            "result IN ('qualified','unqualified','limited_use')",
            name="ck_calibration_result",
        ),
        {"schema": "equipment_mgmt"},
    )

    calibration_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    equipment_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("equipment_mgmt.equipment.equipment_id"), nullable=False
    )
    calibration_date: Mapped[date] = mapped_column(Date, nullable=False)
    calibration_agency: Mapped[Optional[str]] = mapped_column(String(200))
    result: Mapped[str] = mapped_column(String(20), nullable=False)
    certificate_no: Mapped[Optional[str]] = mapped_column(String(100))
    next_calibration_date: Mapped[Optional[date]] = mapped_column(Date)
    remark: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    created_by: Mapped[Optional[str]] = mapped_column(String(50))


class EquipmentMaintenance(Base):
    __tablename__ = "equipment_maintenance"
    __table_args__ = (
        CheckConstraint(
            "maintenance_type IN ('daily','periodic','special')",
            name="ck_maintenance_type",
        ),
        {"schema": "equipment_mgmt"},
    )

    maintenance_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    equipment_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("equipment_mgmt.equipment.equipment_id"), nullable=False
    )
    maintenance_date: Mapped[date] = mapped_column(Date, nullable=False)
    maintenance_type: Mapped[str] = mapped_column(String(30), nullable=False)
    content: Mapped[Optional[str]] = mapped_column(Text)
    performed_by: Mapped[str] = mapped_column(String(50), nullable=False)
    next_maintenance_date: Mapped[Optional[date]] = mapped_column(Date)
    remark: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    created_by: Mapped[Optional[str]] = mapped_column(String(50))


class EquipmentRepair(Base):
    __tablename__ = "equipment_repair"
    __table_args__ = (
        CheckConstraint("repair_type IN ('internal','external')", name="ck_repair_type"),
        {"schema": "equipment_mgmt"},
    )

    repair_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    equipment_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("equipment_mgmt.equipment.equipment_id"), nullable=False
    )
    report_date: Mapped[date] = mapped_column(Date, nullable=False)
    fault_description: Mapped[str] = mapped_column(Text, nullable=False)
    repair_provider: Mapped[Optional[str]] = mapped_column(String(200))
    repair_type: Mapped[str] = mapped_column(String(20), nullable=False, default="external")
    completion_date: Mapped[Optional[date]] = mapped_column(Date)
    repair_cost: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 2))
    conclusion: Mapped[Optional[str]] = mapped_column(Text)
    remark: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    created_by: Mapped[Optional[str]] = mapped_column(String(50))


class EquipmentWarranty(Base):
    __tablename__ = "equipment_warranty"
    __table_args__ = (
        UniqueConstraint("equipment_id", name="uq_warranty_equipment"),
        CheckConstraint("warranty_end >= warranty_start", name="ck_warranty_dates"),
        {"schema": "equipment_mgmt"},
    )

    warranty_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    equipment_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("equipment_mgmt.equipment.equipment_id"), nullable=False
    )
    warranty_start: Mapped[date] = mapped_column(Date, nullable=False)
    warranty_end: Mapped[date] = mapped_column(Date, nullable=False)
    warranty_scope: Mapped[Optional[str]] = mapped_column(Text)
    provider_name: Mapped[Optional[str]] = mapped_column(String(200))
    provider_contact: Mapped[Optional[str]] = mapped_column(String(200))
    remark: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class EquipmentAttachment(Base):
    __tablename__ = "equipment_attachment"
    __table_args__ = (
        CheckConstraint(
            "tag IS NULL OR tag IN ('sop','certificate','contract','photo','other')",
            name="ck_attachment_tag",
        ),
        {"schema": "equipment_mgmt"},
    )

    attachment_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    equipment_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("equipment_mgmt.equipment.equipment_id"), nullable=False
    )
    file_name: Mapped[str] = mapped_column(String(255), nullable=False)
    file_path: Mapped[str] = mapped_column(String(500), nullable=False)
    file_size: Mapped[Optional[int]] = mapped_column(Integer)
    file_type: Mapped[Optional[str]] = mapped_column(String(20))
    tag: Mapped[Optional[str]] = mapped_column(String(30))
    description: Mapped[Optional[str]] = mapped_column(String(200))
    uploaded_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    uploaded_by: Mapped[Optional[str]] = mapped_column(String(50))


class EquipmentReminder(Base):
    __tablename__ = "equipment_reminder"
    __table_args__ = (
        CheckConstraint(
            "reminder_type IN ('calibration','maintenance','warranty')",
            name="ck_reminder_type",
        ),
        {"schema": "equipment_mgmt"},
    )

    reminder_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    equipment_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("equipment_mgmt.equipment.equipment_id"), nullable=False
    )
    reminder_type: Mapped[str] = mapped_column(String(30), nullable=False)
    due_date: Mapped[date] = mapped_column(Date, nullable=False)
    advance_days: Mapped[int] = mapped_column(Integer, nullable=False, default=30)
    is_resolved: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    resolved_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    resolved_by: Mapped[Optional[str]] = mapped_column(String(50))
    remark: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
