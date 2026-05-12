"""
Audit & status-history Pydantic schemas
"""
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict


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
    """状态变更历史条目"""

    model_config = ConfigDict(from_attributes=True)

    history_id: int
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
