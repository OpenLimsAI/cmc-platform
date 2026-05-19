"""MM Pydantic schemas

全公司物料身份注册表 — 对齐 0038_mm_material_v2 migration。
"""
from datetime import date, datetime
from decimal import Decimal
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

MaterialType = Literal["reagent", "consumable", "standard", "column"]
MaterialStatus = Literal[
    "active", "quarantine", "released", "rejected", "retired",
]

HAZARD_CLASS_VALUES = frozenset({"危化品", "易燃", "易制毒", "易制爆", "剧毒品"})

CATEGORY_VALUES = frozenset({
    "一般耗材", "关键耗材", "关键试剂", "内包材", "外包材", "劳保",
    "原辅料", "参比品", "对照品", "工艺用水/气", "标准品",
    "细胞种子", "自制包材", "试剂", "运输包装材料",
})


def _validate_hazard_class(values: list[str] | None) -> list[str] | None:
    if not values:
        return values
    bad = set(values) - HAZARD_CLASS_VALUES
    if bad:
        raise ValueError(f"hazard_class 非法值: {bad}，合法值: {sorted(HAZARD_CLASS_VALUES)}")
    return values


def _validate_category(category: str | None) -> None:
    if category is None:
        return
    if category not in CATEGORY_VALUES:
        raise ValueError(
            f"category='{category}' 不合法，"
            f"合法值: {sorted(CATEGORY_VALUES)}"
        )


class MaterialBase(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    material_name: str = Field(..., max_length=255)
    material_name_en: str | None = Field(None, max_length=255)
    material_type: MaterialType
    category: str | None = Field(None, max_length=50)
    substance_id: int | None = None
    manufacturer: str | None = Field(None, max_length=100)
    catalog_no: str | None = Field(None, max_length=100)
    spec_model: str | None = Field(None, max_length=200)
    unit: str = Field("ea", max_length=20)
    package_spec: str | None = Field(None, max_length=100)
    hazard_class: list[str] | None = None
    physical_form: str | None = Field(None, max_length=64)
    storage_condition: str | None = Field(None, max_length=64)
    source_type: str | None = Field(None, max_length=32)
    source_name: str | None = Field(None, max_length=128)
    grade: str | None = Field(None, max_length=32)
    description: str | None = None
    notes: str | None = None
    extra: dict | None = None

    @model_validator(mode="after")
    def check_hazard_and_category(self) -> Self:
        _validate_hazard_class(self.hazard_class)
        _validate_category(self.category)
        return self


class MaterialCreate(MaterialBase):
    """POST 请求体（status 默认 active；可通过 substance_code 传入 SRS 引用）"""

    material_code: str = Field(
        ...,
        min_length=1,
        max_length=20,
        description="公司物料编码，由用户手动输入（如 R-00123）",
    )
    substance_code: str | None = Field(
        None,
        description="物质业务编码（SUB-...）；如提供则 service 层解析为 substance_id",
    )


class MaterialUpdate(BaseModel):
    """PUT 请求体"""

    change_reason: str | None = None

    material_name: str | None = Field(None, max_length=255)
    material_name_en: str | None = Field(None, max_length=255)
    material_type: MaterialType | None = None
    category: str | None = Field(None, max_length=50)
    substance_id: int | None = None
    substance_code: str | None = Field(None, description="同 MaterialCreate")
    manufacturer: str | None = Field(None, max_length=100)
    catalog_no: str | None = Field(None, max_length=100)
    spec_model: str | None = Field(None, max_length=200)
    unit: str | None = Field(None, max_length=20)
    package_spec: str | None = Field(None, max_length=100)
    hazard_class: list[str] | None = None
    physical_form: str | None = Field(None, max_length=64)
    storage_condition: str | None = Field(None, max_length=64)
    source_type: str | None = Field(None, max_length=32)
    source_name: str | None = Field(None, max_length=128)
    grade: str | None = Field(None, max_length=32)
    status: MaterialStatus | None = None
    description: str | None = None
    notes: str | None = None
    extra: dict | None = None

    @model_validator(mode="after")
    def check_hazard_and_category(self) -> Self:
        _validate_hazard_class(self.hazard_class)
        _validate_category(self.category)
        return self


class MaterialDelete(BaseModel):
    change_reason: str = Field(..., min_length=5, max_length=2000)


class MaterialBrief(BaseModel):
    """列表项精简字段"""

    model_config = ConfigDict(from_attributes=True)

    material_code: str
    material_name: str
    material_name_en: str | None = None
    material_type: MaterialType
    category: str | None = None
    grade: str | None = None
    status: MaterialStatus
    unit: str | None = None
    manufacturer: str | None = None
    spec_model: str | None = None
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
    category: str | None = None
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
    """PUT 请求体"""

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
