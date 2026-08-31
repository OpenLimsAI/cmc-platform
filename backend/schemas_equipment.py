"""
文件: backend/schemas_equipment.py
用途: 设备管理模块 Pydantic v2 数据传输对象
说明:
    - 枚举字面值在应用层校验(与 DB CHECK 约束一致)
    - response 模型使用 ConfigDict(from_attributes=True)
"""
from __future__ import annotations

from datetime import datetime, date
from decimal import Decimal
from typing import Optional, List

from pydantic import BaseModel, Field, ConfigDict, field_validator

from models_equipment import (
    EQUIPMENT_STATUS_VALUES,
    CALIBRATION_RESULT_VALUES,
    MAINTENANCE_TYPE_VALUES,
    REPAIR_TYPE_VALUES,
)


class ORMBase(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# ---------------------------------------------------------------------------
# Equipment 台账
# ---------------------------------------------------------------------------
class EquipmentCreate(BaseModel):
    equipment_code: str = Field(..., min_length=1, max_length=32)
    equipment_no: Optional[str] = Field(None, max_length=64)
    fixed_asset_no: Optional[str] = Field(None, max_length=64)
    name: str = Field(..., min_length=1, max_length=200)
    name_en: Optional[str] = Field(None, max_length=255)
    category: str = Field(..., min_length=1, max_length=50)
    model: Optional[str] = Field(None, max_length=200)
    manufacturer: Optional[str] = Field(None, max_length=100)
    serial_no: Optional[str] = Field(None, max_length=100)
    rated_power: Optional[str] = Field(None, max_length=64)
    origin: Optional[str] = Field(None, max_length=100)
    supplier: Optional[str] = Field(None, max_length=200)
    has_workstation: bool = False
    workstation_info: Optional[dict] = None
    location_room: Optional[str] = Field(None, max_length=50)
    location_detail: Optional[str] = Field(None, max_length=200)
    responsible_person: Optional[str] = Field(None, max_length=50)
    status: str = "in_use"
    purchase_date: Optional[date] = None
    commission_date: Optional[date] = None
    asset_value: Optional[Decimal] = None
    remark: Optional[str] = None

    @field_validator("status")
    @classmethod
    def _check_status(cls, v: str) -> str:
        if v not in EQUIPMENT_STATUS_VALUES:
            raise ValueError(f"status 必须是 {sorted(EQUIPMENT_STATUS_VALUES)} 之一")
        return v


class EquipmentUpdate(BaseModel):
    # equipment_code 唯一且不可修改,不在更新范围
    name: Optional[str] = Field(None, min_length=1, max_length=200)
    category: Optional[str] = Field(None, min_length=1, max_length=50)
    model: Optional[str] = Field(None, max_length=200)
    manufacturer: Optional[str] = Field(None, max_length=100)
    serial_no: Optional[str] = Field(None, max_length=100)
    location_room: Optional[str] = Field(None, max_length=50)
    location_detail: Optional[str] = Field(None, max_length=200)
    responsible_person: Optional[str] = Field(None, max_length=50)
    status: Optional[str] = None
    purchase_date: Optional[date] = None
    commission_date: Optional[date] = None
    asset_value: Optional[Decimal] = None
    remark: Optional[str] = None

    @field_validator("status")
    @classmethod
    def _check_status(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v not in EQUIPMENT_STATUS_VALUES:
            raise ValueError(f"status 必须是 {sorted(EQUIPMENT_STATUS_VALUES)} 之一")
        return v


class EquipmentDeactivateRequest(BaseModel):
    reason: Optional[str] = Field(None, max_length=200)


class EquipmentFromMdmRequest(BaseModel):
    """从 MDM 拉取主数据建台账时,本地补充的运营字段。"""
    location_room: Optional[str] = Field(None, max_length=50)
    location_detail: Optional[str] = Field(None, max_length=200)
    responsible_person: Optional[str] = Field(None, max_length=50)
    commission_date: Optional[date] = None
    status: str = "in_use"
    remark: Optional[str] = None

    @field_validator("status")
    @classmethod
    def _check_status(cls, v: str) -> str:
        if v not in EQUIPMENT_STATUS_VALUES:
            raise ValueError(f"status 必须是 {sorted(EQUIPMENT_STATUS_VALUES)} 之一")
        return v


class EquipmentBatchFromMdmRequest(BaseModel):
    """从 MDM 批量引用建档(初始化台账用,V1.4)。"""
    categories: Optional[List[str]] = None   # 仅同步这些分类;None/空 = 全部
    include_retired: bool = False            # 是否包含 MDM 已退役设备


class EquipmentBatchFromMdmResult(BaseModel):
    created: int                 # 新建台账数
    skipped_existing: int        # 本地已存在,跳过
    skipped_filtered: int        # 被分类/退役过滤,跳过
    failed: List[str] = []       # 拉取详情失败的编码


class EquipmentOut(ORMBase):
    equipment_id: int
    equipment_code: str
    equipment_no: Optional[str] = None
    fixed_asset_no: Optional[str] = None
    name: str
    name_en: Optional[str] = None
    category: str
    model: Optional[str] = None
    manufacturer: Optional[str] = None
    serial_no: Optional[str] = None
    rated_power: Optional[str] = None
    origin: Optional[str] = None
    supplier: Optional[str] = None
    has_workstation: bool = False
    workstation_info: Optional[dict] = None
    mdm_status: Optional[str] = None
    mdm_synced_at: Optional[datetime] = None
    location_room: Optional[str] = None
    location_detail: Optional[str] = None
    responsible_person: Optional[str] = None
    status: str
    purchase_date: Optional[date] = None
    commission_date: Optional[date] = None
    asset_value: Optional[Decimal] = None
    remark: Optional[str] = None
    mdm_equipment_id: Optional[int] = None
    data_source: str = "local"
    is_active: bool
    deactivated_at: Optional[datetime] = None
    deactivated_by: Optional[str] = None
    deactivate_reason: Optional[str] = None
    created_at: datetime
    created_by: Optional[str] = None
    updated_at: datetime
    updated_by: Optional[str] = None


# ---------------------------------------------------------------------------
# Calibration 计量校验
# ---------------------------------------------------------------------------
class CalibrationCreate(BaseModel):
    calibration_date: date
    calibration_agency: Optional[str] = Field(None, max_length=200)
    result: str
    certificate_no: Optional[str] = Field(None, max_length=100)
    next_calibration_date: Optional[date] = None
    remark: Optional[str] = None

    @field_validator("result")
    @classmethod
    def _check_result(cls, v: str) -> str:
        if v not in CALIBRATION_RESULT_VALUES:
            raise ValueError(f"result 必须是 {sorted(CALIBRATION_RESULT_VALUES)} 之一")
        return v


class CalibrationOut(ORMBase):
    calibration_id: int
    equipment_id: int
    calibration_date: date
    calibration_agency: Optional[str] = None
    result: str
    certificate_no: Optional[str] = None
    next_calibration_date: Optional[date] = None
    remark: Optional[str] = None
    created_at: datetime
    created_by: Optional[str] = None


# ---------------------------------------------------------------------------
# Maintenance 常规维护
# ---------------------------------------------------------------------------
class MaintenanceCreate(BaseModel):
    maintenance_date: date
    maintenance_type: str
    content: Optional[str] = None
    performed_by: str = Field(..., min_length=1, max_length=50)
    next_maintenance_date: Optional[date] = None
    remark: Optional[str] = None

    @field_validator("maintenance_type")
    @classmethod
    def _check_type(cls, v: str) -> str:
        if v not in MAINTENANCE_TYPE_VALUES:
            raise ValueError(f"maintenance_type 必须是 {sorted(MAINTENANCE_TYPE_VALUES)} 之一")
        return v


class MaintenanceOut(ORMBase):
    maintenance_id: int
    equipment_id: int
    maintenance_date: date
    maintenance_type: str
    content: Optional[str] = None
    performed_by: str
    next_maintenance_date: Optional[date] = None
    remark: Optional[str] = None
    created_at: datetime
    created_by: Optional[str] = None


# ---------------------------------------------------------------------------
# Repair 维修
# ---------------------------------------------------------------------------
class RepairCreate(BaseModel):
    report_date: date
    fault_description: str = Field(..., min_length=1)
    repair_provider: Optional[str] = Field(None, max_length=200)
    repair_type: str = "external"
    completion_date: Optional[date] = None
    repair_cost: Optional[Decimal] = None
    conclusion: Optional[str] = None
    remark: Optional[str] = None

    @field_validator("repair_type")
    @classmethod
    def _check_type(cls, v: str) -> str:
        if v not in REPAIR_TYPE_VALUES:
            raise ValueError(f"repair_type 必须是 {sorted(REPAIR_TYPE_VALUES)} 之一")
        return v


class RepairUpdate(BaseModel):
    """维修完成登记(回填完成日期/费用/结论)。"""
    completion_date: Optional[date] = None
    repair_cost: Optional[Decimal] = None
    conclusion: Optional[str] = None
    remark: Optional[str] = None


class RepairOut(ORMBase):
    repair_id: int
    equipment_id: int
    report_date: date
    fault_description: str
    repair_provider: Optional[str] = None
    repair_type: str
    completion_date: Optional[date] = None
    repair_cost: Optional[Decimal] = None
    conclusion: Optional[str] = None
    remark: Optional[str] = None
    created_at: datetime
    created_by: Optional[str] = None


# ---------------------------------------------------------------------------
# Warranty 保修(一台设备一条,PUT upsert)
# ---------------------------------------------------------------------------
class WarrantyUpsert(BaseModel):
    warranty_start: date
    warranty_end: date
    warranty_scope: Optional[str] = None
    provider_name: Optional[str] = Field(None, max_length=200)
    provider_contact: Optional[str] = Field(None, max_length=200)
    remark: Optional[str] = None

    @field_validator("warranty_end")
    @classmethod
    def _check_dates(cls, v: date, info) -> date:
        start = info.data.get("warranty_start")
        if start and v < start:
            raise ValueError("保修截止日不得早于起始日")
        return v


class WarrantyOut(ORMBase):
    warranty_id: int
    equipment_id: int
    warranty_start: date
    warranty_end: date
    warranty_scope: Optional[str] = None
    provider_name: Optional[str] = None
    provider_contact: Optional[str] = None
    remark: Optional[str] = None
    created_at: datetime
    updated_at: datetime


# ---------------------------------------------------------------------------
# Attachment 附件
# ---------------------------------------------------------------------------
class AttachmentOut(ORMBase):
    attachment_id: int
    equipment_id: int
    file_name: str
    file_size: Optional[int] = None
    file_type: Optional[str] = None
    tag: Optional[str] = None
    description: Optional[str] = None
    uploaded_at: datetime
    uploaded_by: Optional[str] = None


# ---------------------------------------------------------------------------
# 设备预警
# ---------------------------------------------------------------------------
class EquipmentAlert(BaseModel):
    equipment_id: int
    equipment_code: str
    name: str
    alert_type: str          # calibration / maintenance / warranty
    due_date: date
    days_left: int           # 负数 = 已过期
    severity: str            # red / yellow
