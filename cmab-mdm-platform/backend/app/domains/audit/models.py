"""
Audit & e-signature ORM 模型
对齐 DM-MDM-001 §6.2 - §6.4
"""
from datetime import datetime

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import INET, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class AuditLog(Base):
    __tablename__ = "audit_log"
    __table_args__ = (
        CheckConstraint(
            "action IN ('CREATE','READ','UPDATE','DELETE','RESTORE',"
            "'APPROVE','REJECT','SIGN','LOGIN','LOGOUT','LOGIN_FAILED',"
            "'EXPORT','IMPORT','PERMISSION_CHANGE')",
            name="ck_audit_log_action",
        ),
        {"schema": "audit"},
    )

    log_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int | None] = mapped_column(BigInteger)
    username: Mapped[str] = mapped_column(String(64), nullable=False)
    session_id: Mapped[str | None] = mapped_column(String(64))
    action: Mapped[str] = mapped_column(String(32), nullable=False)
    entity_schema: Mapped[str | None] = mapped_column(String(32))
    entity_table: Mapped[str | None] = mapped_column(String(64))
    entity_id: Mapped[int | None] = mapped_column(BigInteger)
    entity_code: Mapped[str | None] = mapped_column(String(64))
    change_summary: Mapped[str | None] = mapped_column(Text)
    reason: Mapped[str | None] = mapped_column(Text)
    ip_address: Mapped[str | None] = mapped_column(INET)
    user_agent: Mapped[str | None] = mapped_column(Text)
    request_id: Mapped[str | None] = mapped_column(String(64))
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    extra: Mapped[dict | None] = mapped_column(JSONB)


class ChangeHistory(Base):
    __tablename__ = "change_history"
    __table_args__ = ({"schema": "audit"},)

    history_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    audit_log_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("audit.audit_log.log_id"), nullable=False
    )
    field_name: Mapped[str] = mapped_column(String(64), nullable=False)
    old_value: Mapped[dict | None] = mapped_column(JSONB)
    new_value: Mapped[dict | None] = mapped_column(JSONB)


class ESignature(Base):
    """电子签名（21 CFR Part 11 §11.50/11.70/11.100/11.200）"""

    __tablename__ = "e_signature"
    __table_args__ = (
        CheckConstraint(
            "signature_meaning IN ('approve','review','release','witness','reject')",
            name="ck_e_signature_meaning",
        ),
        {"schema": "audit"},
    )

    signature_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("auth.user.user_id"), nullable=False
    )
    username: Mapped[str] = mapped_column(String(64), nullable=False)
    full_name: Mapped[str] = mapped_column(String(128), nullable=False)

    entity_schema: Mapped[str] = mapped_column(String(32), nullable=False)
    entity_table: Mapped[str] = mapped_column(String(64), nullable=False)
    entity_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    entity_code: Mapped[str | None] = mapped_column(String(64))

    signature_meaning: Mapped[str] = mapped_column(String(64), nullable=False)
    signature_reason: Mapped[str] = mapped_column(Text, nullable=False)
    signed_content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    signature_hash: Mapped[str] = mapped_column(String(64), nullable=False)

    ip_address: Mapped[str | None] = mapped_column(INET)
    user_agent: Mapped[str | None] = mapped_column(Text)
    signed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    audit_log_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("audit.audit_log.log_id")
    )
