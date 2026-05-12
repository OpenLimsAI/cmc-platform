"""
ARS Pydantic schemas
对齐 DM-MDM-001 V1.0 §8
"""
from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

AssetType = Literal[
    "mab", "bispecific", "adc", "fusion", "small_molecule", "combination", "other",
]
AssetPhase = Literal[
    "discovery", "preclinical", "phase_1", "phase_2", "phase_3",
    "submission", "approved", "marketed", "discontinued",
]
AssetStatus = Literal["active", "on_hold", "terminated"]


class AssetBase(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    internal_name: str = Field(..., max_length=255)
    trade_name: str | None = Field(None, max_length=255)
    inn_name: str | None = Field(None, max_length=255)
    asset_type: AssetType
    therapeutic_area: str | None = Field(None, max_length=64)
    indication: str | None = None
    dosage_form: str | None = Field(None, max_length=64)
    strength: str | None = Field(None, max_length=64)
    route_of_administration: str | None = Field(None, max_length=32)
    current_phase: AssetPhase = "discovery"
    is_commercial: bool = False
    first_approval_date: date | None = None
    first_launch_date: date | None = None
    description: str | None = None
    notes: str | None = None
    extra: dict | None = None


class AssetCreate(AssetBase):
    """POST 请求体（status 起始固定为 active）"""
    pass


class AssetUpdate(BaseModel):
    """PUT 请求体（乐观锁 + change_reason）

    status 不在此处变更，走 :hold / :resume / :terminate 状态机端点。
    current_phase 可直接通过 PUT 更新（不走状态机）。
    """

    version: int = Field(..., description="乐观锁版本号")
    change_reason: str | None = None

    internal_name: str | None = Field(None, max_length=255)
    trade_name: str | None = Field(None, max_length=255)
    inn_name: str | None = Field(None, max_length=255)
    asset_type: AssetType | None = None
    therapeutic_area: str | None = Field(None, max_length=64)
    indication: str | None = None
    dosage_form: str | None = Field(None, max_length=64)
    strength: str | None = Field(None, max_length=64)
    route_of_administration: str | None = Field(None, max_length=32)
    current_phase: AssetPhase | None = None
    is_commercial: bool | None = None
    first_approval_date: date | None = None
    first_launch_date: date | None = None
    description: str | None = None
    notes: str | None = None
    extra: dict | None = None


class AssetDelete(BaseModel):
    change_reason: str = Field(..., min_length=5, max_length=2000)


class AssetBrief(BaseModel):
    """列表项精简字段"""

    model_config = ConfigDict(from_attributes=True)

    asset_code: str
    internal_name: str
    trade_name: str | None = None
    inn_name: str | None = None
    asset_type: AssetType
    therapeutic_area: str | None = None
    current_phase: AssetPhase
    status: AssetStatus
    is_commercial: bool
    created_at: datetime
    updated_at: datetime


class AssetDetail(AssetBase):
    """详情响应"""

    asset_id: int
    asset_code: str
    status: AssetStatus
    phase_change_at: datetime | None = None
    version: int

    created_at: datetime
    created_by: int
    updated_at: datetime
    updated_by: int
    deleted_at: datetime | None = None
    deleted_by: int | None = None


class AssetFilter(BaseModel):
    """列表查询过滤"""

    q: str | None = None
    asset_type: str | None = None
    current_phase: str | None = None
    status: str | None = None
    therapeutic_area: str | None = None
    is_commercial: bool | None = None


# ============== 状态机 ==============
class AssetStatusChange(BaseModel):
    """状态机端点（:hold / :resume / :terminate）请求体

    terminate 是 GxP 关键动作要求电子签名；hold / resume 不要求。
    """

    change_reason: str = Field(..., min_length=5, max_length=2000)
    password: str | None = Field(
        None, min_length=1, max_length=128,
        description="当前用户密码；仅 :terminate 要求电子签名",
    )


# ============== 多市场注册号（§8.3）==============
MarketIdStatus = Literal["pending", "approved", "withdrawn", "expired"]


class AssetMarketIdBase(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    market_code: str = Field(..., max_length=8, description="CN/US/EU/JP/...")
    id_type: str = Field(..., max_length=32, description="NDC/EMA_PROCEDURE/NMPA_APPROVAL/PMDA/...")
    id_value: str = Field(..., max_length=128)
    issuing_authority: str | None = Field(None, max_length=128)
    application_date: date | None = None
    approval_date: date | None = None
    expiry_date: date | None = None
    status: MarketIdStatus | None = None
    notes: str | None = None


class AssetMarketIdCreate(AssetMarketIdBase):
    pass


class AssetMarketIdUpdate(BaseModel):
    change_reason: str | None = None

    market_code: str | None = Field(None, max_length=8)
    id_type: str | None = Field(None, max_length=32)
    id_value: str | None = Field(None, max_length=128)
    issuing_authority: str | None = Field(None, max_length=128)
    application_date: date | None = None
    approval_date: date | None = None
    expiry_date: date | None = None
    status: MarketIdStatus | None = None
    notes: str | None = None


class AssetMarketIdDelete(BaseModel):
    change_reason: str = Field(..., min_length=5, max_length=2000)


class AssetMarketIdSchema(AssetMarketIdBase):
    market_id_pk: int
    asset_id: int
    created_at: datetime
    created_by: int
    updated_at: datetime
    updated_by: int
    deleted_at: datetime | None = None
    deleted_by: int | None = None
