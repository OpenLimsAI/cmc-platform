"""
电子签名工具（21 CFR Part 11 §11.70 record/signature linking）

签名包含两层哈希：
  - signed_content_hash：被签业务对象的稳定 JSON 表征的 SHA-256；用于"内容防篡改"，
    日后审计可重算此哈希与 e_signature.signed_content_hash 对比，确认记录未被改动
  - signature_hash：在 content_hash 基础上再 mix in 签名者身份、时间、IP、含义、原因
    形成的"签名指纹"，§11.70 要求签名不能被剪切/复制到其他记录

两个哈希都用 SHA-256 hex（64 字符），与现有 substance_protein.sequence_hash 一致。
"""
import hashlib
import json
from datetime import datetime
from typing import Any


def compute_signed_content_hash(content: dict[str, Any]) -> str:
    """对被签业务对象的关键字段做稳定 SHA-256 哈希

    使用 sort_keys=True + 紧凑 separators 保证哈希稳定（与 Python 字典插入顺序无关）。
    default=str 兜底处理 datetime / Decimal / UUID 等非 JSON 原生类型。
    """
    payload = json.dumps(content, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def compute_signature_hash(
    signed_content_hash: str,
    user_id: int,
    signed_at: datetime,
    ip_address: str | None,
    meaning: str,
    reason: str,
) -> str:
    """在内容哈希之上 mix 签名上下文，形成签名指纹"""
    parts = (
        signed_content_hash,
        str(user_id),
        signed_at.isoformat(),
        ip_address or "",
        meaning,
        reason,
    )
    payload = "|".join(parts)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()
