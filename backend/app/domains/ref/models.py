"""
ref schema 跨域引用 ORM 模型

DM-MDM-001 V1.0 §11：
  - §11.2 ref.project_substance：复合 PK (project_id, substance_id, relation_type)
  - §11.3 ref.asset_substance：  复合 PK (asset_id, substance_id, component_role)
  - §11.4 ref.project_asset：    复合 PK (project_id, asset_id)，relation_type 是属性

软删除 deleted_at（语义 = 取消引用）；不硬删，保留审计。
"""
from datetime import datetime

from sqlalchemy import BigInteger, Boolean, CheckConstraint, DateTime, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class ProjectSubstanceLink(Base):
    """项目↔物质关联表（DM-MDM-001 §11.2）"""

    __tablename__ = "project_substance"
    __table_args__ = (
        CheckConstraint(
            "relation_type IN ('primary','secondary','reference','control','derivative')",
            name="ck_ref_ps_type",
        ),
        {"schema": "ref"},
    )

    project_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("prs.project.project_id"), primary_key=True
    )
    substance_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("srs.substance.substance_id"), primary_key=True
    )
    relation_type: Mapped[str] = mapped_column(
        String(32), primary_key=True, default="primary"
    )

    is_primary: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
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


class AssetSubstanceLink(Base):
    """资产↔物质组分表（DM-MDM-001 §11.3）

    component_role 表达资产中物质的角色（ADC 的主体/抗体/连接子/载荷；制剂的辅料/杂质等）。
    复合 PK 含 component_role：一个资产可以多次绑定同一物质用作不同组分（理论上）。
    """

    __tablename__ = "asset_substance"
    __table_args__ = (
        CheckConstraint(
            "component_role IN ('main_component','antibody','linker','payload','excipient','impurity')",
            name="ck_ref_as_role",
        ),
        {"schema": "ref"},
    )

    asset_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("ars.asset.asset_id"), primary_key=True
    )
    substance_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("srs.substance.substance_id"), primary_key=True
    )
    component_role: Mapped[str] = mapped_column(
        String(32), primary_key=True, default="main_component"
    )

    is_active_ingredient: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
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


class ProjectAssetLink(Base):
    """项目↔资产关联表（DM-MDM-001 §11.4）

    与 §11.2 不同：relation_type 是属性不是 PK 的一部分。
    一对 (project, asset) 在某时刻只能有一个 relation_type 关联。
    """

    __tablename__ = "project_asset"
    __table_args__ = ({"schema": "ref"},)

    project_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("prs.project.project_id"), primary_key=True
    )
    asset_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("ars.asset.asset_id"), primary_key=True
    )
    relation_type: Mapped[str] = mapped_column(
        String(32), nullable=False, default="primary"
    )
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
