"""成功提交结果与业务在同一事务保存；不是业务审计的替代品。"""
from datetime import datetime
from uuid import UUID

from sqlalchemy import BigInteger, DateTime, ForeignKey, Integer, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class IdempotencyResult(Base):
    __tablename__ = "idempotency_result"
    __table_args__ = {"schema": "meta"}

    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("auth.user.user_id"), primary_key=True)
    request_key: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True)
    operation: Mapped[str] = mapped_column(String(64))
    body_hash: Mapped[str] = mapped_column(String(64))
    status_code: Mapped[int] = mapped_column(Integer)
    response_body: Mapped[dict] = mapped_column(JSONB)
    headers: Mapped[dict] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
