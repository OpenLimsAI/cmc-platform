"""
文件: backend/models.py
用途: SQLAlchemy 2.0 ORM 模型,对应 sql/init.sql 中 material_mgmt 的 9 张表
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
    BigInteger,
    SmallInteger,
    Boolean,
    Date,
    DateTime,
    Numeric,
    Text,
    ForeignKey,
    UniqueConstraint,
    CheckConstraint,
    Computed,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, ARRAY
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
    __table_args__ = (
        UniqueConstraint("room_no", "cabinet_no", "layer_no", name="uq_location_triple"),
        CheckConstraint("layer_no >= 1", name="ck_location_layer_positive"),
        {"schema": "material_mgmt"},
    )

    location_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    room_no: Mapped[str] = mapped_column(String(20), nullable=False)
    cabinet_no: Mapped[str] = mapped_column(String(20), nullable=False)
    layer_no: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    # 生成列;ORM 只读不写
    name: Mapped[str] = mapped_column(
        String(80),
        Computed("room_no || '-' || cabinet_no || '-L' || layer_no", persisted=True),
    )
    storage_condition: Mapped[Optional[str]] = mapped_column(String(50))
    remark: Mapped[Optional[str]] = mapped_column(Text)


# ---------------------------------------------------------------------------
# 存放位置层级树(覆盖层) - v1.5
#   bulk 叶子(CABINET_LAYER/FRIDGE_SHELF)通过 location_id 1:1 回链 location;
#   批次仍挂 location_id,现有库存逻辑零改动。CELL 叶子(期2)location_id 为空。
# ---------------------------------------------------------------------------
class StorageNode(Base):
    __tablename__ = "storage_node"
    __table_args__ = (
        CheckConstraint(
            "node_type IN ('ROOM','CABINET','CABINET_LAYER','FRIDGE','FRIDGE_SHELF',"
            "'RACK','RACK_LAYER','BOX','CELL')",
            name="ck_storage_node_type",
        ),
        CheckConstraint(
            "capacity_kind IS NULL OR capacity_kind IN ('bulk','cell')",
            name="ck_storage_capacity_kind",
        ),
        {"schema": "material_mgmt"},
    )

    node_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    parent_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("material_mgmt.storage_node.node_id", ondelete="CASCADE")
    )
    node_type: Mapped[str] = mapped_column(String(20), nullable=False)
    code: Mapped[str] = mapped_column(String(40), nullable=False)
    label: Mapped[Optional[str]] = mapped_column(String(80))
    path: Mapped[Optional[str]] = mapped_column(String(255))
    depth: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=0)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    capacity_kind: Mapped[Optional[str]] = mapped_column(String(10))  # bulk / cell
    location_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("material_mgmt.location.location_id")
    )
    temp_category: Mapped[Optional[str]] = mapped_column(String(20))  # normal/2-8/-20/-80
    temp_text: Mapped[Optional[str]] = mapped_column(String(50))
    # 冰箱(FRIDGE)绑定 MDM 设备:equipment_no 业务编号(绑定/显示 join 键),
    # equipment_code MDM 内部码(EQP-...)快照;其余节点为 NULL。
    equipment_no: Mapped[Optional[str]] = mapped_column(String(64))
    equipment_code: Mapped[Optional[str]] = mapped_column(String(32))
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    remark: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, server_default=func.now())

    location: Mapped[Optional["Location"]] = relationship()


# ---------------------------------------------------------------------------
# 孔位单占用(期2 -80℃ 一孔一管)
#   空孔 = 没有 status='stored' 的行;部分唯一索引(uq_cell_occupied)保证单占用。
# ---------------------------------------------------------------------------
class CellOccupancy(Base):
    __tablename__ = "cell_occupancy"
    __table_args__ = (
        CheckConstraint("status IN ('stored','removed')", name="ck_cell_occ_status"),
        {"schema": "material_mgmt"},
    )

    occupancy_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    cell_node_id: Mapped[int] = mapped_column(
        ForeignKey("material_mgmt.storage_node.node_id", ondelete="CASCADE"), nullable=False
    )
    batch_id: Mapped[int] = mapped_column(
        ForeignKey("material_mgmt.batch.batch_id"), nullable=False
    )
    sample_label: Mapped[Optional[str]] = mapped_column(String(100))
    status: Mapped[str] = mapped_column(String(10), nullable=False, default="stored")
    stored_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, server_default=func.now())
    stored_by: Mapped[Optional[str]] = mapped_column(String(50))
    removed_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    remark: Mapped[Optional[str]] = mapped_column(Text)


# ---------------------------------------------------------------------------
# 物料主数据
# ---------------------------------------------------------------------------
class Material(Base):
    __tablename__ = "material"
    __table_args__ = {"schema": "material_mgmt"}

    material_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    material_code: Mapped[str] = mapped_column(String(20), nullable=False)
    category: Mapped[Optional[str]] = mapped_column(String(50))
    # 入库表单的"大类"; 4 个值之一: reagent / consumable / standard / column
    # 老物料没分类的可以为 NULL, 入库时回退到普通表单
    material_type: Mapped[Optional[str]] = mapped_column(String(20))
    name_cn: Mapped[str] = mapped_column(String(200), nullable=False)
    name_en: Mapped[Optional[str]] = mapped_column(String(255))  # MDM material_name_en 快照
    grade: Mapped[Optional[str]] = mapped_column(String(50))
    manufacturer: Mapped[Optional[str]] = mapped_column(String(100))
    spec_model: Mapped[Optional[str]] = mapped_column(String(200))
    catalog_no: Mapped[Optional[str]] = mapped_column(String(100))
    unit: Mapped[str] = mapped_column(
        String(20), ForeignKey("material_mgmt.unit_dict.unit"), nullable=False
    )
    package_spec: Mapped[Optional[str]] = mapped_column(String(100))
    # 危化品分类(多选):危化品 / 易燃 / 易制毒 / 易制爆 / 剧毒品
    hazard_class: Mapped[Optional[List[str]]] = mapped_column(ARRAY(Text))
    remark: Mapped[Optional[str]] = mapped_column(Text)
    safety_stock: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0"))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    deactivated_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    deactivated_by: Mapped[Optional[str]] = mapped_column(String(50))
    deactivate_reason: Mapped[Optional[str]] = mapped_column(String(200))
    data_source: Mapped[Optional[str]] = mapped_column(String(10), default="local")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, server_default=func.now())

    batches: Mapped[List["Batch"]] = relationship(back_populates="material")


# ---------------------------------------------------------------------------
# 批次
# ---------------------------------------------------------------------------
class Batch(Base):
    __tablename__ = "batch"
    __table_args__ = (
        UniqueConstraint(
            "material_id", "batch_no", "location_id", name="uq_batch_material_no_loc"
        ),
        {"schema": "material_mgmt"},
    )

    batch_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    material_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("material_mgmt.material.material_id"), nullable=False
    )
    batch_no: Mapped[str] = mapped_column(String(100), nullable=False)
    expiry_date: Mapped[Optional[date]] = mapped_column(Date)
    location_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("material_mgmt.location.location_id"), nullable=False
    )
    received_date: Mapped[date] = mapped_column(Date, nullable=False)
    initial_qty: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    remark: Mapped[Optional[str]] = mapped_column(Text)
    # 入库时所在 tab 的类型: reagent / consumable / standard / column
    # 老批次没这个概念留 NULL, 新批次入库时由前端 tab 写入
    intake_type: Mapped[Optional[str]] = mapped_column(String(20))
    # 入库表单"类型特定"字段; 都是 nullable, 没用到的类型留 NULL
    concentration: Mapped[Optional[str]] = mapped_column(String(50))                   # 标准物质 浓度
    extinction_coefficient: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 2))  # 标准物质 消光系数
    serial_no: Mapped[Optional[str]] = mapped_column(String(100))                      # 色谱柱
    asset_no: Mapped[Optional[str]] = mapped_column(String(100))                       # 色谱柱 编号
    responsible_person: Mapped[Optional[str]] = mapped_column(String(50))              # 色谱柱
    project_no: Mapped[Optional[str]] = mapped_column(String(100))                     # 标准品 项目编号
    originator_batch_no: Mapped[Optional[str]] = mapped_column(String(100))            # 标准品 原研药批号
    aliquot_date: Mapped[Optional[date]] = mapped_column(Date)                         # 标准品 分装日期
    aliquot_spec: Mapped[Optional[str]] = mapped_column(String(50))                    # 标准品 分装规格(数值+单位, 例 "100 uL/支")
    intake_operator_name: Mapped[Optional[str]] = mapped_column(String(128))           # 入库登记操作人姓名(快照)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, server_default=func.now())

    material: Mapped["Material"] = relationship(back_populates="batches")
    location: Mapped["Location"] = relationship()
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
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, server_default=func.now())

    batch: Mapped["Batch"] = relationship(back_populates="txns")


# ---------------------------------------------------------------------------
# 审计追踪（用户由 MDM 管理，此处仅记录操作日志）
# ---------------------------------------------------------------------------
class AuditLog(Base):
    __tablename__ = "audit_log"
    __table_args__ = {"schema": "material_mgmt"}

    # DB 列为 BIGSERIAL(高频审计写入),ORM 对齐 BigInteger 防溢出
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[Optional[int]] = mapped_column(Integer)
    username: Mapped[Optional[str]] = mapped_column(String(50))
    full_name: Mapped[Optional[str]] = mapped_column(String(128))    # 操作人姓名快照(可读性)
    action: Mapped[str] = mapped_column(String(50), nullable=False)
    entity_type: Mapped[Optional[str]] = mapped_column(String(50))
    entity_id: Mapped[Optional[str]] = mapped_column(String(50))
    before_json: Mapped[Optional[dict]] = mapped_column(JSONB)
    after_json: Mapped[Optional[dict]] = mapped_column(JSONB)
    source_ip: Mapped[Optional[str]] = mapped_column(String(45))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, server_default=func.now())
