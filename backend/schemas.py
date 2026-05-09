"""
文件: backend/schemas.py
用途: Pydantic v2 数据传输对象(请求 / 响应模型)
说明:
    - 所有数量字段使用 Decimal,精确两位小数
    - Optional 字段统一以 None 兜底
    - response 模型使用 model_config = ConfigDict(from_attributes=True)
"""
from __future__ import annotations

from datetime import datetime, date
from decimal import Decimal
from typing import Optional, List, Any

from pydantic import BaseModel, Field, ConfigDict


# ---------------------------------------------------------------------------
# 通用
# ---------------------------------------------------------------------------
class ORMBase(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# ---------------------------------------------------------------------------
# Unit / Category / Location
# ---------------------------------------------------------------------------
class UnitOut(ORMBase):
    unit: str
    description: Optional[str] = None


class CategoryOut(ORMBase):
    category: str


class LocationBase(BaseModel):
    name: str
    storage_condition: Optional[str] = None
    remark: Optional[str] = None


class LocationCreate(LocationBase):
    pass


class LocationOut(LocationBase, ORMBase):
    location_id: int


# ---------------------------------------------------------------------------
# Material
# ---------------------------------------------------------------------------
class MaterialBase(BaseModel):
    category: Optional[str] = None
    name_cn: str
    grade: Optional[str] = None
    manufacturer: Optional[str] = None
    spec_model: Optional[str] = None
    catalog_no: Optional[str] = None
    unit: str
    package_spec: Optional[str] = None
    remark: Optional[str] = None
    safety_stock: Decimal = Decimal("0")


class MaterialCreate(MaterialBase):
    material_code: str = Field(..., min_length=1, max_length=20)


class MaterialUpdate(BaseModel):
    category: Optional[str] = None
    name_cn: Optional[str] = None
    grade: Optional[str] = None
    manufacturer: Optional[str] = None
    spec_model: Optional[str] = None
    catalog_no: Optional[str] = None
    unit: Optional[str] = None
    package_spec: Optional[str] = None
    remark: Optional[str] = None
    safety_stock: Optional[Decimal] = None


class MaterialOut(MaterialBase, ORMBase):
    material_code: str
    is_active: bool
    deactivated_at: Optional[datetime] = None
    deactivated_by: Optional[str] = None
    deactivate_reason: Optional[str] = None
    import_batch_id: Optional[int] = None
    created_at: datetime
    updated_at: datetime


class DeactivateRequest(BaseModel):
    # operator 已由 v1.1 鉴权自动从登录用户取,不再手填
    reason: Optional[str] = None


# ---------------------------------------------------------------------------
# Batch
# ---------------------------------------------------------------------------
class BatchBase(BaseModel):
    material_code: str
    batch_no: str
    expiry_date: Optional[date] = None
    location_id: Optional[int] = None
    received_date: date
    initial_qty: Decimal
    remark: Optional[str] = None


class BatchCreate(BatchBase):
    # operator 由 v1.1 鉴权自动从登录用户取
    pass


class BatchOut(BatchBase, ORMBase):
    batch_id: int
    created_at: datetime
    # 实时计算字段
    current_qty: Optional[Decimal] = None
    location_name: Optional[str] = None
    material_name: Optional[str] = None
    unit: Optional[str] = None


# ---------------------------------------------------------------------------
# Inventory Transaction
# ---------------------------------------------------------------------------
class TxnInRequest(BaseModel):
    """对已有批次追加入库 — operator 由鉴权自动填"""
    batch_id: int
    qty: Decimal = Field(..., gt=0)
    txn_date: date
    remark: Optional[str] = None


class TxnOutRequest(BaseModel):
    """出库:从指定批次扣减 — operator 由鉴权自动填"""
    batch_id: int
    qty: Decimal = Field(..., gt=0)
    txn_date: date
    purpose: Optional[str] = None
    remark: Optional[str] = None


class TxnAdjustRequest(BaseModel):
    """盘点调整:正负皆可 — operator 由鉴权自动填"""
    batch_id: int
    qty: Decimal  # 不限制正负
    txn_date: date
    remark: Optional[str] = None


class TxnOut(ORMBase):
    txn_id: int
    batch_id: int
    txn_type: str
    qty: Decimal
    txn_date: date
    operator: str
    purpose: Optional[str] = None
    remark: Optional[str] = None
    created_at: datetime
    # 关联展示字段
    batch_no: Optional[str] = None
    material_code: Optional[str] = None
    material_name: Optional[str] = None


# ---------------------------------------------------------------------------
# Stock 视图(实时聚合)
# ---------------------------------------------------------------------------
class StockByMaterial(BaseModel):
    material_code: str
    name_cn: str
    category: Optional[str] = None
    unit: str
    is_active: bool
    safety_stock: Decimal
    total_qty: Decimal
    low_stock: bool  # total_qty < safety_stock 且 safety_stock > 0


class StockByBatch(BaseModel):
    batch_id: int
    material_code: str
    name_cn: str
    unit: str
    batch_no: str
    expiry_date: Optional[date] = None
    location_id: Optional[int] = None
    location_name: Optional[str] = None
    received_date: date
    current_qty: Decimal
    days_to_expiry: Optional[int] = None
    is_active: bool


class ExpiryAlert(BaseModel):
    batch_id: int
    material_code: str
    name_cn: str
    unit: str
    batch_no: str
    expiry_date: date
    days_to_expiry: int
    current_qty: Decimal
    location_name: Optional[str] = None
    severity: str  # 'EXPIRED' | 'URGENT' | 'WARNING'


class LowStockAlert(BaseModel):
    material_code: str
    name_cn: str
    unit: str
    safety_stock: Decimal
    total_qty: Decimal
    gap: Decimal  # safety_stock - total_qty


# ---------------------------------------------------------------------------
# Import
# ---------------------------------------------------------------------------
class ImportPreviewRow(BaseModel):
    row_index: int  # Excel 中的行号(从 1 起,含表头?这里用业务行号)
    material_code: Optional[str] = None
    name_cn: Optional[str] = None
    action: str  # 'INSERT' | 'UPDATE' | 'ERROR'
    errors: List[str] = []
    warnings: List[str] = []
    raw: dict = {}


class ImportPreviewResult(BaseModel):
    total_rows: int
    insert_count: int
    update_count: int
    error_count: int
    leading_zero_codes: List[str] = []
    new_categories: List[str] = []
    new_units: List[str] = []
    rows: List[ImportPreviewRow] = []


class ImportCommitRequest(BaseModel):
    file_name: str
    # operator 由鉴权自动填
    auto_create_units: bool = True   # 文件中出现新单位时自动加入字典
    rows: List[dict]                 # 干跑后的逐行数据(已清洗)


class ImportCommitResult(BaseModel):
    import_id: int
    total_rows: int
    inserted_rows: int
    updated_rows: int
    failed_rows: int


class ImportLogOut(ORMBase):
    import_id: int
    file_name: Optional[str] = None
    imported_at: datetime
    operator: Optional[str] = None
    total_rows: int
    inserted_rows: int
    updated_rows: int
    failed_rows: int
    error_detail: Optional[Any] = None


# ---------------------------------------------------------------------------
# v1.1 用户 / 鉴权 / 审计
# ---------------------------------------------------------------------------
class LoginRequest(BaseModel):
    username: str = Field(..., min_length=1, max_length=50)
    password: str = Field(..., min_length=1)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_at: datetime
    user: "UserOut"


class ChangePasswordRequest(BaseModel):
    old_password: str
    new_password: str = Field(..., min_length=8)


class UserOut(ORMBase):
    id: int
    username: str
    role: str
    is_active: bool
    must_change_password: bool
    created_at: datetime
    last_login_at: Optional[datetime] = None


class UserCreate(BaseModel):
    username: str = Field(..., min_length=1, max_length=50)
    password: str = Field(..., min_length=8)
    role: str = Field(..., pattern="^(admin|user)$")


class UserUpdate(BaseModel):
    role: Optional[str] = Field(None, pattern="^(admin|user)$")
    is_active: Optional[bool] = None


class AdminResetPasswordRequest(BaseModel):
    new_password: str = Field(..., min_length=8)
    require_change_on_login: bool = True


class AuditLogOut(ORMBase):
    id: int
    user_id: Optional[int] = None
    username: Optional[str] = None
    action: str
    entity_type: Optional[str] = None
    entity_id: Optional[str] = None
    before_json: Optional[Any] = None
    after_json: Optional[Any] = None
    source_ip: Optional[str] = None
    created_at: datetime


# 让 TokenResponse 的 forward ref 解析
TokenResponse.model_rebuild()
