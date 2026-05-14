"""MM Pydantic schemas

对齐 DM-MDM-001 V1.1 §10 + API-MDM-001 V1.1 §5.1.6 / §8.2。
"""
from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

MaterialType = Literal[
    "candidate", "reference", "stability", "buffer", "raw", "intermediate", "other",
]
MaterialGrade = Literal[
    "RUO", "GMP", "Reference Standard", "Working Standard",
]
MaterialStatus = Literal[
    "active", "quarantine", "released", "rejected", "retired",
]


class MaterialBase(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    material_name: str = Field(..., max_length=255)
    material_name_en: str | None = Field(None, max_length=255)
    material_type: MaterialType
    substance_id: int | None = None
    physical_form: str | None = Field(None, max_length=64)
    storage_condition: str | None = Field(None, max_length=64)
    source_type: str | None = Field(None, max_length=32)
    source_name: str | None = Field(None, max_length=128)
    grade: MaterialGrade | None = None
    description: str | None = None
    notes: str | None = None
    extra: dict | None = None


class MaterialCreate(MaterialBase):
    """POST 请求体（status 默认 active；可通过 substance_code 传入 SRS 引用）

    若同时传 substance_id 与 substance_code，以 substance_code 解析为准。
    """

    substance_code: str | None = Field(
        None,
        description="物质业务编码（SUB-...）；如提供则 service 层解析为 substance_id",
    )


class MaterialUpdate(BaseModel):
    """PUT 请求体（无 version 乐观锁，§10.1 字段集无 version 列）

    status 可直接 PUT 更新（无状态机）。
    """

    change_reason: str | None = None

    material_name: str | None = Field(None, max_length=255)
    material_name_en: str | None = Field(None, max_length=255)
    material_type: MaterialType | None = None
    substance_id: int | None = None
    substance_code: str | None = Field(None, description="同 MaterialCreate")
    physical_form: str | None = Field(None, max_length=64)
    storage_condition: str | None = Field(None, max_length=64)
    source_type: str | None = Field(None, max_length=32)
    source_name: str | None = Field(None, max_length=128)
    grade: MaterialGrade | None = None
    status: MaterialStatus | None = None
    description: str | None = None
    notes: str | None = None
    extra: dict | None = None


class MaterialDelete(BaseModel):
    change_reason: str = Field(..., min_length=5, max_length=2000)


class MaterialBrief(BaseModel):
    """列表项精简字段"""

    model_config = ConfigDict(from_attributes=True)

    material_code: str
    material_name: str
    material_name_en: str | None = None
    material_type: MaterialType
    grade: MaterialGrade | None = None
    status: MaterialStatus
    physical_form: str | None = None
    source_name: str | None = None
    substance_id: int | None = None
    substance_code: str | None = None
    created_at: datetime
    updated_at: datetime


class MaterialDetail(MaterialBase):
    """详情响应"""

    material_id: int
    material_code: str
    status: MaterialStatus
    substance_code: str | None = None

    created_at: datetime
    created_by: int
    updated_at: datetime
    updated_by: int
    deleted_at: datetime | None = None
    deleted_by: int | None = None


class MaterialFilter(BaseModel):
    """列表查询过滤"""

    q: str | None = None
    material_type: str | None = None
    status: str | None = None
    grade: str | None = None
    substance_code: str | None = None
    source_type: str | None = None


# ============== material_batch (§10.2) ==============
MaterialBatchStatus = Literal[
    "in_stock", "in_use", "depleted", "expired", "recalled",
]


class MaterialBatchBase(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    batch_number: str = Field(..., max_length=64)
    quantity_value: Decimal | None = None
    quantity_unit: str | None = Field(None, max_length=16)
    manufacture_date: date | None = None
    expiry_date: date | None = None
    receive_date: date | None = None
    source_batch_ref: str | None = Field(None, max_length=128)
    coa_url: str | None = None
    storage_location: str | None = Field(None, max_length=128)
    notes: str | None = None
    extra: dict | None = None


class MaterialBatchCreate(MaterialBatchBase):
    """POST 请求体（status 默认 in_stock）"""


class MaterialBatchUpdate(BaseModel):
    """PUT 请求体（无版本号，status 可直接 PUT）"""

    change_reason: str | None = None

    batch_number: str | None = Field(None, max_length=64)
    quantity_value: Decimal | None = None
    quantity_unit: str | None = Field(None, max_length=16)
    manufacture_date: date | None = None
    expiry_date: date | None = None
    receive_date: date | None = None
    status: MaterialBatchStatus | None = None
    source_batch_ref: str | None = Field(None, max_length=128)
    coa_url: str | None = None
    storage_location: str | None = Field(None, max_length=128)
    notes: str | None = None
    extra: dict | None = None


class MaterialBatchDelete(BaseModel):
    change_reason: str = Field(..., min_length=5, max_length=2000)


class MaterialBatchSchema(MaterialBatchBase):
    batch_id: int
    material_id: int
    status: MaterialBatchStatus

    created_at: datetime
    created_by: int
    updated_at: datetime
    updated_by: int
    deleted_at: datetime | None = None
    deleted_by: int | None = None
