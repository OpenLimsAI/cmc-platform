"""Identity mapping and revocable server sessions; no upstream roles are imported."""
from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class OIDCIdentity(Base):
    __tablename__ = "oidc_identity"
    __table_args__ = (UniqueConstraint("issuer", "subject", name="uq_oidc_identity_subject"),
                      UniqueConstraint("issuer", "user_id", name="uq_oidc_identity_user"), {"schema": "auth"})
    identity_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    issuer: Mapped[str] = mapped_column(String(512), nullable=False)
    subject: Mapped[str] = mapped_column(String(255), nullable=False)
    user_id: Mapped[int] = mapped_column(ForeignKey("auth.user.user_id"), nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    created_by: Mapped[int] = mapped_column(ForeignKey("auth.user.user_id"), nullable=False)
    change_reason: Mapped[str] = mapped_column(Text, nullable=False)


class OIDCLogin(Base):
    __tablename__ = "oidc_login"
    __table_args__ = ({"schema": "auth"},)
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    secret_data: Mapped[str] = mapped_column(Text, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class OIDCSession(Base):
    __tablename__ = "oidc_session"
    __table_args__ = ({"schema": "auth"},)
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    identity_id: Mapped[int] = mapped_column(ForeignKey("auth.oidc_identity.identity_id"), nullable=False, index=True)
    issued_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    idle_expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    provider_issued_at: Mapped[int] = mapped_column(BigInteger, nullable=False)
    provider_sid: Mapped[str | None] = mapped_column(String(255))
    password_version: Mapped[str | None] = mapped_column(String(64))
    secret_data: Mapped[str] = mapped_column(Text, nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class OIDCLogoutReplay(Base):
    __tablename__ = "oidc_logout_replay"
    __table_args__ = ({"schema": "auth"},)
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    issuer: Mapped[str] = mapped_column(String(512), nullable=False)
    subject: Mapped[str | None] = mapped_column(String(255))
    sid: Mapped[str | None] = mapped_column(String(255))
    issued_at: Mapped[int] = mapped_column(BigInteger, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
