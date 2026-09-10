"""EQP Pydantic schemas

全公司仪器设备身份注册表 — 对齐 0040_eqp_equipment migration。
"""
from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

EquipmentCategory = Literal[
    "分析仪器",
    "工艺/制备设备",
    "通用实验室设备",
    "公用工程/环境与支持系统",
    "IT/自动化与数据系统",
]
EquipmentStatus = Literal["active", "retired"]

# 设备分级（0056）：字典按分类走 —— 分析仪器(检验设备)用 USP 口径 A/B/C，
# 其他分类(生产/公用/通用/IT)用 关键/一般。DB 有同名 CHECK 约束兜底。
ANALYTICAL_CATEGORY = "分析仪器"
CRITICALITY_ANALYTICAL = ("A", "B", "C")
CRITICALITY_GENERAL = ("关键", "一般")
EquipmentCriticality = Literal["A", "B", "C", "关键", "一般"]


def allowed_criticalities(category: str | None) -> tuple[str, ...]:
    """该分类允许的分级取值。category 为空时返回全集（留给服务层按现值判定）。"""
    if category is None:
        return CRITICALITY_ANALYTICAL + CRITICALITY_GENERAL
    return (
        CRITICALITY_ANALYTICAL
        if category == ANALYTICAL_CATEGORY
        else CRITICALITY_GENERAL
    )


class EquipmentBase(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    equipment_name: str = Field(..., max_length=255, description="设备名称（中文）")
    equipment_name_en: str | None = Field(None, max_length=255, description="设备名称（英文）")
    category: EquipmentCategory
    equipment_no: str | None = Field(None, max_length=64, description="设备编号（业务/历史号）")
    fixed_asset_no: str | None = Field(None, max_length=64, description="固资编号")
    model: str | None = Field(None, max_length=200)
    manufacturer: str | None = Field(None, max_length=100)
    serial_no: str | None = Field(None, max_length=100)
    rated_power: str | None = Field(None, max_length=64, description="额定功率（自由文本，如 1500W）")
    origin: str | None = Field(None, max_length=100, description="产地")
    purchase_date: date | None = None
    asset_value: Decimal | None = None
    supplier: str | None = Field(None, max_length=200)
    department: str | None = Field(None, max_length=64, description="使用部门")
    site: str | None = Field(None, max_length=64, description="厂区（南楼/北楼/祥泰路）")
    room: str | None = Field(None, max_length=100, description="房间/存放位置")
    criticality: EquipmentCriticality | None = Field(
        None, description="设备分级：分析仪器 A/B/C；其他分类 关键/一般"
    )
    criticality_basis: str | None = Field(None, description="分级依据")
    commission_date: date | None = Field(None, description="首次启用日期")
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

    设备ID(equipment_code)一律由系统生成 EQP-yyyy-NNNNNN，不接受手填——
    与物质编码一致。业务/历史号请填 equipment_no（设备编号）。
    """

    @model_validator(mode="after")
    def _check_criticality(self) -> "EquipmentCreate":
        if self.criticality and self.criticality not in allowed_criticalities(self.category):
            allowed = "/".join(allowed_criticalities(self.category))
            raise ValueError(f"分类「{self.category}」的设备分级只能是 {allowed}")
        return self


class EquipmentUpdate(BaseModel):
    """PUT 请求体（equipment_code 不可修改）"""

    change_reason: str | None = None

    equipment_name: str | None = Field(None, max_length=255, description="设备名称（中文）")
    equipment_name_en: str | None = Field(None, max_length=255, description="设备名称（英文）")
    category: EquipmentCategory | None = None
    equipment_no: str | None = Field(None, max_length=64, description="设备编号（业务/历史号）")
    fixed_asset_no: str | None = Field(None, max_length=64, description="固资编号")
    model: str | None = Field(None, max_length=200)
    manufacturer: str | None = Field(None, max_length=100)
    serial_no: str | None = Field(None, max_length=100)
    rated_power: str | None = Field(None, max_length=64, description="额定功率")
    origin: str | None = Field(None, max_length=100, description="产地")
    purchase_date: date | None = None
    asset_value: Decimal | None = None
    supplier: str | None = Field(None, max_length=200)
    status: EquipmentStatus | None = None
    department: str | None = Field(None, max_length=64, description="使用部门")
    site: str | None = Field(None, max_length=64, description="厂区")
    room: str | None = Field(None, max_length=100, description="房间/存放位置")
    criticality: EquipmentCriticality | None = None
    criticality_basis: str | None = Field(None, description="分级依据")
    commission_date: date | None = None
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
    equipment_no: str | None = None
    fixed_asset_no: str | None = None
    equipment_name: str
    equipment_name_en: str | None = None
    category: EquipmentCategory
    model: str | None = None
    manufacturer: str | None = None
    serial_no: str | None = None
    department: str | None = None
    site: str | None = None
    room: str | None = None
    criticality: EquipmentCriticality | None = None
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
    department: str | None = None
    site: str | None = None
    criticality: str | None = None
