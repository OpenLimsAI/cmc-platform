"""
文件: backend/models.py
用途: SQLAlchemy 2.0 ORM 模型,对应 sql/init.sql 中 7 张表
关键点:
    - 数量统一 Numeric(12,2),Python 端用 Decimal,杜绝浮点误差
    - material_code 用 String(20),保留前导 0
    - 库存数量绝不落表,只记录 inventory_txn,实时聚合
"""
from __future__ import annotations

from datetime import datetime, date
from decimal import Decimal
from typing import Optional, List

from sqlalchemy import (
    String,
    Integer,
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
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database import Base


# ---------------------------------------------------------------------------
# 字典表
# ---------------------------------------------------------------------------
class UnitDict(Base):
    __tablename__ = "unit_dict"
    __table_args__ = {"schema": "material_mgmt"}

    unit: Mapped[str] = mapped_column(String(20), primary_key=True)
    description: Mapped[Optional[str]] = mapped_column(String(100))


class CategoryDict(Base):
    __tablename__ = "category_dict"
    __table_args__ = {"schema": "material_mgmt"}

    category: Mapped[str] = mapped_column(String(50), primary_key=True)


class Location(Base):
    __tablename__ = "location"
    __table_args__ = {"schema": "material_mgmt"}

    location_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    storage_condition: Mapped[Optional[str]] = mapped_column(String(50))
    remark: Mapped[Optional[str]] = mapped_column(Text)


# ---------------------------------------------------------------------------
# 导入日志
# ---------------------------------------------------------------------------
class ImportLog(Base):
    __tablename__ = "import_log"
    __table_args__ = {"schema": "material_mgmt"}

    import_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    file_name: Mapped[Optional[str]] = mapped_column(String(200))
    imported_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    operator: Mapped[Optional[str]] = mapped_column(String(50))
    total_rows: Mapped[int] = mapped_column(Integer, default=0)
    inserted_rows: Mapped[int] = mapped_column(Integer, default=0)
    updated_rows: Mapped[int] = mapped_column(Integer, default=0)
    failed_rows: Mapped[int] = mapped_column(Integer, default=0)
    error_detail: Mapped[Optional[dict]] = mapped_column(JSONB)


# ---------------------------------------------------------------------------
# 物料主数据
# ---------------------------------------------------------------------------
class Material(Base):
    __tablename__ = "material"
    __table_args__ = {"schema": "material_mgmt"}

    material_code: Mapped[str] = mapped_column(String(20), primary_key=True)
    category: Mapped[Optional[str]] = mapped_column(String(50))
    name_cn: Mapped[str] = mapped_column(String(200), nullable=False)
    grade: Mapped[Optional[str]] = mapped_column(String(50))
    manufacturer: Mapped[Optional[str]] = mapped_column(String(100))
    spec_model: Mapped[Optional[str]] = mapped_column(String(200))
    catalog_no: Mapped[Optional[str]] = mapped_column(String(100))
    unit: Mapped[str] = mapped_column(
        String(20), ForeignKey("material_mgmt.unit_dict.unit"), nullable=False
    )
    package_spec: Mapped[Optional[str]] = mapped_column(String(100))
    remark: Mapped[Optional[str]] = mapped_column(Text)
    safety_stock: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0"))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    deactivated_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    deactivated_by: Mapped[Optional[str]] = mapped_column(String(50))
    deactivate_reason: Mapped[Optional[str]] = mapped_column(String(200))
    import_batch_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("material_mgmt.import_log.import_id")
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    batches: Mapped[List["Batch"]] = relationship(back_populates="material")


# ---------------------------------------------------------------------------
# 批次
# ---------------------------------------------------------------------------
class Batch(Base):
    __tablename__ = "batch"
    __table_args__ = (
        UniqueConstraint("material_code", "batch_no", name="uq_batch_material_no"),
        {"schema": "material_mgmt"},
    )

    batch_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    material_code: Mapped[str] = mapped_column(
        String(20), ForeignKey("material_mgmt.material.material_code"), nullable=False
    )
    batch_no: Mapped[str] = mapped_column(String(100), nullable=False)
    expiry_date: Mapped[Optional[date]] = mapped_column(Date)
    location_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("material_mgmt.location.location_id")
    )
    received_date: Mapped[date] = mapped_column(Date, nullable=False)
    initial_qty: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    remark: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    material: Mapped["Material"] = relationship(back_populates="batches")
    location: Mapped[Optional["Location"]] = relationship()
    txns: Mapped[List["InventoryTxn"]] = relationship(back_populates="batch")


# ---------------------------------------------------------------------------
# 出入库流水(库存计算唯一来源)
# ---------------------------------------------------------------------------
class InventoryTxn(Base):
    __tablename__ = "inventory_txn"
    __table_args__ = (
        CheckConstraint("txn_type IN ('IN','OUT','ADJUST')", name="ck_txn_type"),
        {"schema": "material_mgmt"},
    )

    txn_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    batch_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("material_mgmt.batch.batch_id"), nullable=False
    )
    txn_type: Mapped[str] = mapped_column(String(10), nullable=False)
    qty: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    txn_date: Mapped[date] = mapped_column(Date, nullable=False)
    operator: Mapped[str] = mapped_column(String(50), nullable=False)
    purpose: Mapped[Optional[str]] = mapped_column(String(200))
    remark: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    batch: Mapped["Batch"] = relationship(back_populates="txns")


# ---------------------------------------------------------------------------
# v1.1 用户系统 + 审计追踪
# ---------------------------------------------------------------------------
class AppUser(Base):
    __tablename__ = "app_user"
    __table_args__ = (
        CheckConstraint("role IN ('admin','user')", name="ck_app_user_role"),
        {"schema": "material_mgmt"},
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String(50), nullable=False, unique=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(20), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    must_change_password: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    last_login_at: Mapped[Optional[datetime]] = mapped_column(DateTime)


class AuthSession(Base):
    __tablename__ = "auth_session"
    __table_args__ = {"schema": "material_mgmt"}

    token: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("material_mgmt.app_user.id", ondelete="CASCADE"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    source_ip: Mapped[Optional[str]] = mapped_column(String(45))

    user: Mapped["AppUser"] = relationship()


class AuditLog(Base):
    __tablename__ = "audit_log"
    __table_args__ = {"schema": "material_mgmt"}

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("material_mgmt.app_user.id", ondelete="SET NULL")
    )
    username: Mapped[Optional[str]] = mapped_column(String(50))  # 冗余,user 删后仍可查
    action: Mapped[str] = mapped_column(String(50), nullable=False)
    entity_type: Mapped[Optional[str]] = mapped_column(String(50))
    entity_id: Mapped[Optional[str]] = mapped_column(String(50))
    before_json: Mapped[Optional[dict]] = mapped_column(JSONB)
    after_json: Mapped[Optional[dict]] = mapped_column(JSONB)
    source_ip: Mapped[Optional[str]] = mapped_column(String(45))
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
