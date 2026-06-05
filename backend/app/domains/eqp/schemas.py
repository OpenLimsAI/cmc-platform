"""EQP Pydantic schemas

全公司仪器设备身份注册表 — 对齐 0040_eqp_equipment migration。
"""
from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

EquipmentCategory = Literal[
    "分析仪器",
    "工艺/制备设备",
    "通用实验室设备",
    "公用工程/环境与支持系统",
    "IT/自动化与数据系统",
]
EquipmentStatus = Literal["active", "retired"]


class EquipmentBase(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    equipment_name: str = Field(..., max_length=255, description="设备名称（中文）")
    equipment_name_en: str | None = Field(None, max_length=255, description="设备名称（英文）")
    category: EquipmentCategory
    model: str | None = Field(None, max_length=200)
    manufacturer: str | None = Field(None, max_length=100)
    serial_no: str | None = Field(None, max_length=100)
    rated_power: str | None = Field(None, max_length=64, description="额定功率（自由文本，如 1500W）")
    origin: str | None = Field(None, max_length=100, description="产地")
    purchase_date: date | None = None
    asset_value: Decimal | None = None
    supplier: str | None = Field(None, max_length=200)
    has_workstation: bool = Field(False, description="是否附带专用工作站")
    workstation_info: dict | None = Field(
        None,
        description="工作站/本机硬件配置：brand/model/serial/os/cpu/gpu/ram/disk/monitor_*",
    )
    description: str | None = Field(None, description="主要性能参数描述")
    notes: str | None = None
    extra: dict | None = None


class EquipmentCreate(EquipmentBase):
    """POST 请求体（status 默认 active）

    equipment_code 可留空 → 触发器自动分配 EQP-yyyyXXXXXX;
    也可手动传入(如沿用部门历史编号),唯一性由 service 预检 + DB 约束兜底。
    """

    equipment_code: str | None = Field(
        None,
        max_length=32,
        description="设备编码;留空自动生成 EQP-yyyyXXXXXX",
    )


class EquipmentUpdate(BaseModel):
    """PUT 请求体（equipment_code 不可修改）"""

    change_reason: str | None = None

    equipment_name: str | None = Field(None, max_length=255, description="设备名称（中文）")
    equipment_name_en: str | None = Field(None, max_length=255, description="设备名称（英文）")
    category: EquipmentCategory | None = None
    model: str | None = Field(None, max_length=200)
    manufacturer: str | None = Field(None, max_length=100)
    serial_no: str | None = Field(None, max_length=100)
    rated_power: str | None = Field(None, max_length=64, description="额定功率")
    origin: str | None = Field(None, max_length=100, description="产地")
    purchase_date: date | None = None
    asset_value: Decimal | None = None
    supplier: str | None = Field(None, max_length=200)
    status: EquipmentStatus | None = None
    has_workstation: bool | None = None
    workstation_info: dict | None = None
    description: str | None = Field(None, description="主要性能参数描述")
    notes: str | None = None
    extra: dict | None = None


class EquipmentDelete(BaseModel):
    change_reason: str = Field(..., min_length=5, max_length=2000)


class EquipmentBrief(BaseModel):
    """列表项精简字段"""

    model_config = ConfigDict(from_attributes=True)

    equipment_code: str
    equipment_name: str
    equipment_name_en: str | None = None
    category: EquipmentCategory
    model: str | None = None
    manufacturer: str | None = None
    serial_no: str | None = None
    status: EquipmentStatus
    created_at: datetime
    updated_at: datetime


class EquipmentDetail(EquipmentBase):
    """详情响应"""

    equipment_id: int
    equipment_code: str
    status: EquipmentStatus

    created_at: datetime
    created_by: int
    updated_at: datetime
    updated_by: int
    deleted_at: datetime | None = None
    deleted_by: int | None = None


class EquipmentFilter(BaseModel):
    """列表查询过滤"""

    q: str | None = None
    category: str | None = None
    status: str | None = None
    manufacturer: str | None = None
