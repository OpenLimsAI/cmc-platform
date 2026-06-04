"""EQP Pydantic schemas

全公司仪器设备身份注册表 — 对齐 0040_eqp_equipment migration。
"""
from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

EquipmentCategory = Literal["分析仪器", "实验设备", "辅助设备", "其他"]
EquipmentStatus = Literal["active", "retired"]


class EquipmentBase(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    equipment_name: str = Field(..., max_length=255)
    equipment_name_en: str | None = Field(None, max_length=255)
    category: EquipmentCategory
    model: str | None = Field(None, max_length=200)
    manufacturer: str | None = Field(None, max_length=100)
    serial_no: str | None = Field(None, max_length=100)
    purchase_date: date | None = None
    asset_value: Decimal | None = None
    supplier: str | None = Field(None, max_length=200)
    description: str | None = None
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

    equipment_name: str | None = Field(None, max_length=255)
    equipment_name_en: str | None = Field(None, max_length=255)
    category: EquipmentCategory | None = None
    model: str | None = Field(None, max_length=200)
    manufacturer: str | None = Field(None, max_length=100)
    serial_no: str | None = Field(None, max_length=100)
    purchase_date: date | None = None
    asset_value: Decimal | None = None
    supplier: str | None = Field(None, max_length=200)
    status: EquipmentStatus | None = None
    description: str | None = None
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
