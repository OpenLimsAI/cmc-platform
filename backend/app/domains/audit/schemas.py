"""
Audit & status-history Pydantic schemas
"""
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


# ============== 状态机端点公用：嵌套签名块 + 通用响应 ==============
# 对齐 API-MDM-001 V1.1 §6.5 / §7.4 / §8.x 状态机端点契约

SignatureMeaning = Literal["approve", "review", "release", "witness", "reject"]


class SignatureBlock(BaseModel):
    """电子签名请求块（21 CFR Part 11 §11.50 / §11.200）

    GxP 关键动作必传；hold/resume/restrict 等可逆动作不需要。
    """

    password: str = Field(..., min_length=1, max_length=128)
    meaning: SignatureMeaning | None = Field(
        None, description="签名含义；未传时按 action 推断默认值（approve/review/release/witness/reject）",
    )
    reason: str = Field(..., min_length=5, max_length=2000, description="签名理由（独立于业务 comment）")


class StateChangeResponse(BaseModel):
    """状态机端点统一成功响应（API-MDM-001 V1.1 §6.5 行 1140-1155 等）"""

    model_config = ConfigDict(from_attributes=True)

    # 实体编码：三域中只一个非 None
    substance_code: str | None = None
    project_code: str | None = None
    asset_code: str | None = None

    old_status: str
    new_status: str

    # 签名 id：仅 GxP 关键动作非 None
    signature_id: int | None = None

    # 仅 substance approve / project approve / asset approve 等"注册"动作非 None
    registered_at: datetime | None = None
    registered_by: int | None = None

    # 乐观锁版本号（变更后的新值）
    version: int


class ChangeHistoryItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    field_name: str
    old_value: Any | None = None
    new_value: Any | None = None


class AuditLogItem(BaseModel):
    """审计日志条目 + 嵌入字段级 diff（仅 UPDATE 有）"""

    model_config = ConfigDict(from_attributes=True)

    log_id: int
    user_id: int | None = None
    username: str
    action: str
    entity_schema: str | None = None
    entity_table: str | None = None
    entity_id: int | None = None
    entity_code: str | None = None
    reason: str | None = None
    ip_address: str | None = None
    request_id: str | None = None
    timestamp: datetime
    changes: list[ChangeHistoryItem] = []


class StatusHistoryItem(BaseModel):
    """状态变更历史条目（substance / project / asset 三域共用）

    三个 entity_id 字段三选一非 None，取决于 ORM 来源表（substance_status_history /
    project_status_history / asset_status_history）。GET /{entity}/{code}/status-history
    端点由 path 参数固定上下文，不依赖此字段；但跨域审计 / 通用日志聚合等场景需要。
    """

    model_config = ConfigDict(from_attributes=True)

    history_id: int
    substance_id: int | None = None
    project_id: int | None = None
    asset_id: int | None = None
    old_status: str | None = None
    new_status: str
    change_reason: str
    changed_at: datetime
    changed_by: int
    e_signature_id: int | None = None


class ESignatureItem(BaseModel):
    """电子签名摘要（21 CFR Part 11 §11.50 展示要求：签名者姓名、日期时间、含义）"""

    model_config = ConfigDict(from_attributes=True)

    signature_id: int
    user_id: int
    username: str
    full_name: str
    entity_schema: str
    entity_table: str
    entity_id: int
    entity_code: str | None = None
    signature_meaning: str
    signature_reason: str
    signed_content_hash: str
    signature_hash: str
    signed_at: datetime


# ============== Phase 5.A / M5.3：全局审计 + 签名查询 ==============


class AuditLogFilter(BaseModel):
    """全局审计日志查询参数（GET /audit-logs）"""

    q: str | None = Field(None, description="模糊搜索 entity_code / reason")
    username: str | None = None
    action: str | None = Field(None, description="CREATE / UPDATE / DELETE / SIGN / LOGIN / ...")
    entity_table: str | None = Field(None, description="如 substance / project / asset / material")
    entity_code: str | None = None
    date_from: datetime | None = None
    date_to: datetime | None = None


class SignatureFilter(BaseModel):
    """电子签名查询参数（GET /signatures）"""

    username: str | None = None
    entity_table: str | None = None
    entity_code: str | None = None
    signature_meaning: str | None = None
    date_from: datetime | None = None
    date_to: datetime | None = None
