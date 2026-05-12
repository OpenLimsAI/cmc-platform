"""
Asset Registration System ORM 模型
对齐 DM-MDM-001 V1.0 §8
"""
from datetime import date, datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class Asset(Base):
    """§8.2 资产主表"""

    __tablename__ = "asset"
    __table_args__ = (
        UniqueConstraint("asset_code", name="uq_asset_code"),
        CheckConstraint(
            "asset_type IN ('mab','bispecific','adc','fusion','small_molecule',"
            "'combination','other')",
            name="ck_asset_type",
        ),
        CheckConstraint(
            "current_phase IN ('discovery','preclinical','phase_1','phase_2','phase_3',"
            "'submission','approved','marketed','discontinued')",
            name="ck_asset_phase",
        ),
        CheckConstraint(
            "status IN ('active','on_hold','terminated')",
            name="ck_asset_status",
        ),
        {"schema": "ars"},
    )

    asset_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    asset_code: Mapped[str] = mapped_column(String(32), nullable=False)

    # 基本信息
    internal_name: Mapped[str] = mapped_column(String(255), nullable=False)
    trade_name: Mapped[str | None] = mapped_column(String(255))
    inn_name: Mapped[str | None] = mapped_column(String(255))

    # 资产属性
    asset_type: Mapped[str] = mapped_column(String(32), nullable=False)
    therapeutic_area: Mapped[str | None] = mapped_column(String(64))
    indication: Mapped[str | None] = mapped_column(Text)
    dosage_form: Mapped[str | None] = mapped_column(String(64))
    strength: Mapped[str | None] = mapped_column(String(64))
    route_of_administration: Mapped[str | None] = mapped_column(String(32))

    # 阶段（业务进度）
    current_phase: Mapped[str] = mapped_column(String(32), nullable=False, default="discovery")
    phase_change_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # 状态（管控状态，状态机管理）
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="active")

    # 商业属性
    is_commercial: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    first_approval_date: Mapped[date | None] = mapped_column(Date)
    first_launch_date: Mapped[date | None] = mapped_column(Date)

    # 描述
    description: Mapped[str | None] = mapped_column(Text)
    notes: Mapped[str | None] = mapped_column(Text)
    extra: Mapped[dict | None] = mapped_column(JSONB)

    # 审计
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    created_by: Mapped[int] = mapped_column(BigInteger, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_by: Mapped[int] = mapped_column(BigInteger, nullable=False)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    deleted_by: Mapped[int | None] = mapped_column(BigInteger)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)


class AssetMarketId(Base):
    """§8.3 多市场注册标识符"""

    __tablename__ = "asset_market_id"
    __table_args__ = (
        UniqueConstraint(
            "asset_id", "market_code", "id_type", "id_value",
            name="uq_asset_market_id",
        ),
        {"schema": "ars"},
    )

    market_id_pk: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    asset_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("ars.asset.asset_id"), nullable=False
    )
    market_code: Mapped[str] = mapped_column(String(8), nullable=False)
    id_type: Mapped[str] = mapped_column(String(32), nullable=False)
    id_value: Mapped[str] = mapped_column(String(128), nullable=False)
    issuing_authority: Mapped[str | None] = mapped_column(String(128))
    application_date: Mapped[date | None] = mapped_column(Date)
    approval_date: Mapped[date | None] = mapped_column(Date)
    expiry_date: Mapped[date | None] = mapped_column(Date)
    status: Mapped[str | None] = mapped_column(String(32))
    notes: Mapped[str | None] = mapped_column(Text)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    created_by: Mapped[int] = mapped_column(BigInteger, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_by: Mapped[int] = mapped_column(BigInteger, nullable=False)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    deleted_by: Mapped[int | None] = mapped_column(BigInteger)


class AssetStatusHistory(Base):
    """实施侧补齐（§8.1 列了但 §8 缺 DDL）；与 §7.7 / §9.5 同构"""

    __tablename__ = "asset_status_history"
    __table_args__ = ({"schema": "ars"},)

    history_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    asset_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("ars.asset.asset_id"), nullable=False
    )
    old_status: Mapped[str | None] = mapped_column(String(32))
    new_status: Mapped[str] = mapped_column(String(32), nullable=False)
    change_reason: Mapped[str] = mapped_column(Text, nullable=False)
    changed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    changed_by: Mapped[int] = mapped_column(BigInteger, nullable=False)
    e_signature_id: Mapped[int | None] = mapped_column(BigInteger)
