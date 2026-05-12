"""
ref 业务服务层：跨域 link / unlink + 双向列表

DM-MDM-001 V1.0 §11：
  - §11.2 project ↔ substance（ProjectSubstanceLinkService）
  - §11.3 asset   ↔ substance（AssetSubstanceLinkService）
  - §11.4 project ↔ asset    （ProjectAssetLinkService）

业务规则：
  - SUBSTANCE_STATUS_FORBID_LINK：obsoleted 物质不允许参与新关联
  - ASSET_STATUS_FORBID_LINK：terminated 资产不允许参与新关联（业务侧已停止开发）
软删除 deleted_at（取消引用），保留审计。
"""
from datetime import UTC, datetime

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import (
    AssetNotFoundError,
    BadRequestError,
    ConflictError,
    NotFoundError,
    ProjectNotFoundError,
    SubstanceNotFoundError,
)
from app.domains.ars.models import Asset
from app.domains.auth.models import User
from app.domains.prs.models import Project
from app.domains.ref.models import AssetSubstanceLink, ProjectAssetLink, ProjectSubstanceLink
from app.domains.ref.schemas import (
    AssetSubstanceLinkCreate,
    AssetSubstanceLinkItem,
    ProjectAssetLinkItem,
    ProjectSubstanceLinkCreate,
    ProjectSubstanceLinkItem,
)
from app.domains.srs.models import Substance


# 关联业务规则
SUBSTANCE_STATUS_FORBID_LINK = {"obsoleted"}
ASSET_STATUS_FORBID_LINK = {"terminated"}


# ============== §11.2 ProjectSubstance ==============
class ProjectSubstanceLinkService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def _get_project(self, code: str) -> Project:
        result = await self.db.execute(
            select(Project).where(
                Project.project_code == code, Project.deleted_at.is_(None)
            )
        )
        proj = result.scalar_one_or_none()
        if not proj:
            raise ProjectNotFoundError(f"未找到 project: {code}")
        return proj

    async def _get_substance(self, code: str) -> Substance:
        result = await self.db.execute(
            select(Substance).where(
                Substance.substance_code == code, Substance.deleted_at.is_(None)
            )
        )
        sub = result.scalar_one_or_none()
        if not sub:
            raise SubstanceNotFoundError(f"未找到 substance: {code}")
        return sub

    async def link(
        self, project_code: str, payload: ProjectSubstanceLinkCreate, current_user: User
    ) -> ProjectSubstanceLinkItem:
        proj = await self._get_project(project_code)
        sub = await self._get_substance(payload.substance_code)

        if sub.status in SUBSTANCE_STATUS_FORBID_LINK:
            raise BadRequestError(
                f"substance {sub.substance_code} 当前状态为 '{sub.status}'，不允许建立新关联"
            )

        existing = await self.db.execute(
            select(ProjectSubstanceLink).where(
                ProjectSubstanceLink.project_id == proj.project_id,
                ProjectSubstanceLink.substance_id == sub.substance_id,
                ProjectSubstanceLink.relation_type == payload.relation_type,
                ProjectSubstanceLink.deleted_at.is_(None),
            )
        )
        if existing.scalar_one_or_none():
            raise ConflictError(
                f"substance {sub.substance_code} 已通过 relation_type='{payload.relation_type}'"
                f" 关联到 {project_code}"
            )

        soft_deleted = await self.db.execute(
            select(ProjectSubstanceLink).where(
                ProjectSubstanceLink.project_id == proj.project_id,
                ProjectSubstanceLink.substance_id == sub.substance_id,
                ProjectSubstanceLink.relation_type == payload.relation_type,
                ProjectSubstanceLink.deleted_at.is_not(None),
            )
        )
        existing_link = soft_deleted.scalar_one_or_none()
        if existing_link is not None:
            existing_link.deleted_at = None
            existing_link.deleted_by = None
            existing_link.is_primary = payload.is_primary
            existing_link.notes = payload.notes
            existing_link.updated_by = current_user.user_id
            link = existing_link
        else:
            link = ProjectSubstanceLink(
                project_id=proj.project_id,
                substance_id=sub.substance_id,
                relation_type=payload.relation_type,
                is_primary=payload.is_primary,
                notes=payload.notes,
                created_by=current_user.user_id,
                updated_by=current_user.user_id,
            )
            self.db.add(link)

        await self.db.flush()
        await self.db.commit()
        return self._compose_item(link, proj, sub)

    async def unlink(
        self,
        project_code: str,
        substance_code: str,
        relation_type: str,
        current_user: User,
        reason: str | None = None,
    ) -> None:
        if reason:
            await self.db.execute(
                text("SELECT set_config('app.change_reason', :r, true)"),
                {"r": reason},
            )
        proj = await self._get_project(project_code)
        sub = await self._get_substance(substance_code)
        result = await self.db.execute(
            select(ProjectSubstanceLink).where(
                ProjectSubstanceLink.project_id == proj.project_id,
                ProjectSubstanceLink.substance_id == sub.substance_id,
                ProjectSubstanceLink.relation_type == relation_type,
                ProjectSubstanceLink.deleted_at.is_(None),
            )
        )
        link = result.scalar_one_or_none()
        if not link:
            raise NotFoundError(
                f"未找到活动引用：project={project_code} substance={substance_code}"
                f" relation_type={relation_type}"
            )
        link.deleted_at = datetime.now(UTC)
        link.deleted_by = current_user.user_id
        link.updated_by = current_user.user_id
        await self.db.flush()
        await self.db.commit()

    async def list_for_project(
        self, project_code: str, include_deleted: bool = False
    ) -> list[ProjectSubstanceLinkItem]:
        proj = await self._get_project(project_code)
        stmt = (
            select(ProjectSubstanceLink, Substance)
            .join(Substance, Substance.substance_id == ProjectSubstanceLink.substance_id)
            .where(ProjectSubstanceLink.project_id == proj.project_id)
        )
        if not include_deleted:
            stmt = stmt.where(ProjectSubstanceLink.deleted_at.is_(None))
        stmt = stmt.order_by(
            ProjectSubstanceLink.is_primary.desc(),
            ProjectSubstanceLink.relation_type.asc(),
            ProjectSubstanceLink.created_at.desc(),
        )
        result = await self.db.execute(stmt)
        return [self._compose_item(link, proj, sub) for link, sub in result.all()]

    async def list_for_substance(
        self, substance_code: str, include_deleted: bool = False
    ) -> list[ProjectSubstanceLinkItem]:
        sub = await self._get_substance(substance_code)
        stmt = (
            select(ProjectSubstanceLink, Project)
            .join(Project, Project.project_id == ProjectSubstanceLink.project_id)
            .where(
                ProjectSubstanceLink.substance_id == sub.substance_id,
                Project.deleted_at.is_(None),
            )
        )
        if not include_deleted:
            stmt = stmt.where(ProjectSubstanceLink.deleted_at.is_(None))
        stmt = stmt.order_by(ProjectSubstanceLink.created_at.desc())
        result = await self.db.execute(stmt)
        return [self._compose_item(link, proj, sub) for link, proj in result.all()]

    @staticmethod
    def _compose_item(
        link: ProjectSubstanceLink, proj: Project, sub: Substance
    ) -> ProjectSubstanceLinkItem:
        return ProjectSubstanceLinkItem(
            relation_type=link.relation_type,
            is_primary=link.is_primary,
            notes=link.notes,
            created_at=link.created_at,
            created_by=link.created_by,
            updated_at=link.updated_at,
            updated_by=link.updated_by,
            deleted_at=link.deleted_at,
            deleted_by=link.deleted_by,
            project_code=proj.project_code,
            project_name=proj.project_name,
            project_status=proj.status,
            project_type=proj.project_type,
            substance_code=sub.substance_code,
            substance_preferred_name=sub.preferred_name,
            substance_status=sub.status,
            substance_type=sub.substance_type,
        )


# ============== §11.3 AssetSubstance ==============
class AssetSubstanceLinkService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def _get_asset(self, code: str) -> Asset:
        result = await self.db.execute(
            select(Asset).where(Asset.asset_code == code, Asset.deleted_at.is_(None))
        )
        asset = result.scalar_one_or_none()
        if not asset:
            raise AssetNotFoundError(f"未找到 asset: {code}")
        return asset

    async def _get_substance(self, code: str) -> Substance:
        result = await self.db.execute(
            select(Substance).where(
                Substance.substance_code == code, Substance.deleted_at.is_(None)
            )
        )
        sub = result.scalar_one_or_none()
        if not sub:
            raise SubstanceNotFoundError(f"未找到 substance: {code}")
        return sub

    async def link(
        self, asset_code: str, payload: AssetSubstanceLinkCreate, current_user: User
    ) -> AssetSubstanceLinkItem:
        asset = await self._get_asset(asset_code)
        sub = await self._get_substance(payload.substance_code)

        if asset.status in ASSET_STATUS_FORBID_LINK:
            raise BadRequestError(
                f"asset {asset.asset_code} 当前状态为 '{asset.status}'，不允许建立新关联"
            )
        if sub.status in SUBSTANCE_STATUS_FORBID_LINK:
            raise BadRequestError(
                f"substance {sub.substance_code} 当前状态为 '{sub.status}'，不允许建立新关联"
            )

        existing = await self.db.execute(
            select(AssetSubstanceLink).where(
                AssetSubstanceLink.asset_id == asset.asset_id,
                AssetSubstanceLink.substance_id == sub.substance_id,
                AssetSubstanceLink.component_role == payload.component_role,
                AssetSubstanceLink.deleted_at.is_(None),
            )
        )
        if existing.scalar_one_or_none():
            raise ConflictError(
                f"substance {sub.substance_code} 已通过 component_role='{payload.component_role}'"
                f" 关联到 {asset_code}"
            )

        soft_deleted = await self.db.execute(
            select(AssetSubstanceLink).where(
                AssetSubstanceLink.asset_id == asset.asset_id,
                AssetSubstanceLink.substance_id == sub.substance_id,
                AssetSubstanceLink.component_role == payload.component_role,
                AssetSubstanceLink.deleted_at.is_not(None),
            )
        )
        existing_link = soft_deleted.scalar_one_or_none()
        if existing_link is not None:
            existing_link.deleted_at = None
            existing_link.is_active_ingredient = payload.is_active_ingredient
            existing_link.notes = payload.notes
            existing_link.updated_by = current_user.user_id
            link = existing_link
        else:
            link = AssetSubstanceLink(
                asset_id=asset.asset_id,
                substance_id=sub.substance_id,
                component_role=payload.component_role,
                is_active_ingredient=payload.is_active_ingredient,
                notes=payload.notes,
                created_by=current_user.user_id,
                updated_by=current_user.user_id,
            )
            self.db.add(link)

        await self.db.flush()
        await self.db.commit()
        return self._compose_item(link, asset, sub)

    async def unlink(
        self,
        asset_code: str,
        substance_code: str,
        component_role: str,
        current_user: User,
        reason: str | None = None,
    ) -> None:
        if reason:
            await self.db.execute(
                text("SELECT set_config('app.change_reason', :r, true)"),
                {"r": reason},
            )
        asset = await self._get_asset(asset_code)
        sub = await self._get_substance(substance_code)
        result = await self.db.execute(
            select(AssetSubstanceLink).where(
                AssetSubstanceLink.asset_id == asset.asset_id,
                AssetSubstanceLink.substance_id == sub.substance_id,
                AssetSubstanceLink.component_role == component_role,
                AssetSubstanceLink.deleted_at.is_(None),
            )
        )
        link = result.scalar_one_or_none()
        if not link:
            raise NotFoundError(
                f"未找到活动引用：asset={asset_code} substance={substance_code}"
                f" component_role={component_role}"
            )
        link.deleted_at = datetime.now(UTC)
        link.updated_by = current_user.user_id
        await self.db.flush()
        await self.db.commit()

    async def list_for_asset(
        self, asset_code: str, include_deleted: bool = False
    ) -> list[AssetSubstanceLinkItem]:
        asset = await self._get_asset(asset_code)
        stmt = (
            select(AssetSubstanceLink, Substance)
            .join(Substance, Substance.substance_id == AssetSubstanceLink.substance_id)
            .where(AssetSubstanceLink.asset_id == asset.asset_id)
        )
        if not include_deleted:
            stmt = stmt.where(AssetSubstanceLink.deleted_at.is_(None))
        stmt = stmt.order_by(
            AssetSubstanceLink.is_active_ingredient.desc(),
            AssetSubstanceLink.component_role.asc(),
            AssetSubstanceLink.created_at.desc(),
        )
        result = await self.db.execute(stmt)
        return [self._compose_item(link, asset, sub) for link, sub in result.all()]

    async def list_for_substance(
        self, substance_code: str, include_deleted: bool = False
    ) -> list[AssetSubstanceLinkItem]:
        sub = await self._get_substance(substance_code)
        stmt = (
            select(AssetSubstanceLink, Asset)
            .join(Asset, Asset.asset_id == AssetSubstanceLink.asset_id)
            .where(
                AssetSubstanceLink.substance_id == sub.substance_id,
                Asset.deleted_at.is_(None),
            )
        )
        if not include_deleted:
            stmt = stmt.where(AssetSubstanceLink.deleted_at.is_(None))
        stmt = stmt.order_by(AssetSubstanceLink.created_at.desc())
        result = await self.db.execute(stmt)
        return [self._compose_item(link, asset, sub) for link, asset in result.all()]

    @staticmethod
    def _compose_item(
        link: AssetSubstanceLink, asset: Asset, sub: Substance
    ) -> AssetSubstanceLinkItem:
        return AssetSubstanceLinkItem(
            component_role=link.component_role,
            is_active_ingredient=link.is_active_ingredient,
            notes=link.notes,
            created_at=link.created_at,
            created_by=link.created_by,
            updated_at=link.updated_at,
            updated_by=link.updated_by,
            deleted_at=link.deleted_at,
            asset_code=asset.asset_code,
            asset_internal_name=asset.internal_name,
            asset_type=asset.asset_type,
            asset_status=asset.status,
            asset_phase=asset.current_phase,
            substance_code=sub.substance_code,
            substance_preferred_name=sub.preferred_name,
            substance_status=sub.status,
            substance_type=sub.substance_type,
        )


# ============== §11.4 ProjectAsset ==============
class ProjectAssetLinkService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def _get_project(self, code: str) -> Project:
        result = await self.db.execute(
            select(Project).where(
                Project.project_code == code, Project.deleted_at.is_(None)
            )
        )
        proj = result.scalar_one_or_none()
        if not proj:
            raise ProjectNotFoundError(f"未找到 project: {code}")
        return proj

    async def _get_asset(self, code: str) -> Asset:
        result = await self.db.execute(
            select(Asset).where(Asset.asset_code == code, Asset.deleted_at.is_(None))
        )
        asset = result.scalar_one_or_none()
        if not asset:
            raise AssetNotFoundError(f"未找到 asset: {code}")
        return asset

    async def link(
        self,
        project_code: str,
        asset_code: str,
        relation_type: str,
        notes: str | None,
        current_user: User,
    ) -> ProjectAssetLinkItem:
        proj = await self._get_project(project_code)
        asset = await self._get_asset(asset_code)

        if asset.status in ASSET_STATUS_FORBID_LINK:
            raise BadRequestError(
                f"asset {asset.asset_code} 当前状态为 '{asset.status}'，不允许建立新关联"
            )

        # §11.4 复合 PK 只到 (project_id, asset_id)
        existing = await self.db.execute(
            select(ProjectAssetLink).where(
                ProjectAssetLink.project_id == proj.project_id,
                ProjectAssetLink.asset_id == asset.asset_id,
                ProjectAssetLink.deleted_at.is_(None),
            )
        )
        if existing.scalar_one_or_none():
            raise ConflictError(
                f"asset {asset.asset_code} 已关联到 project {project_code}"
            )

        soft_deleted = await self.db.execute(
            select(ProjectAssetLink).where(
                ProjectAssetLink.project_id == proj.project_id,
                ProjectAssetLink.asset_id == asset.asset_id,
                ProjectAssetLink.deleted_at.is_not(None),
            )
        )
        existing_link = soft_deleted.scalar_one_or_none()
        if existing_link is not None:
            existing_link.deleted_at = None
            existing_link.relation_type = relation_type
            existing_link.notes = notes
            existing_link.updated_by = current_user.user_id
            link = existing_link
        else:
            link = ProjectAssetLink(
                project_id=proj.project_id,
                asset_id=asset.asset_id,
                relation_type=relation_type,
                notes=notes,
                created_by=current_user.user_id,
                updated_by=current_user.user_id,
            )
            self.db.add(link)

        await self.db.flush()
        await self.db.commit()
        return self._compose_item(link, proj, asset)

    async def unlink(
        self,
        project_code: str,
        asset_code: str,
        current_user: User,
        reason: str | None = None,
    ) -> None:
        if reason:
            await self.db.execute(
                text("SELECT set_config('app.change_reason', :r, true)"),
                {"r": reason},
            )
        proj = await self._get_project(project_code)
        asset = await self._get_asset(asset_code)
        result = await self.db.execute(
            select(ProjectAssetLink).where(
                ProjectAssetLink.project_id == proj.project_id,
                ProjectAssetLink.asset_id == asset.asset_id,
                ProjectAssetLink.deleted_at.is_(None),
            )
        )
        link = result.scalar_one_or_none()
        if not link:
            raise NotFoundError(
                f"未找到活动引用：project={project_code} asset={asset_code}"
            )
        link.deleted_at = datetime.now(UTC)
        link.updated_by = current_user.user_id
        await self.db.flush()
        await self.db.commit()

    async def list_for_project(
        self, project_code: str, include_deleted: bool = False
    ) -> list[ProjectAssetLinkItem]:
        proj = await self._get_project(project_code)
        stmt = (
            select(ProjectAssetLink, Asset)
            .join(Asset, Asset.asset_id == ProjectAssetLink.asset_id)
            .where(ProjectAssetLink.project_id == proj.project_id)
        )
        if not include_deleted:
            stmt = stmt.where(ProjectAssetLink.deleted_at.is_(None))
        stmt = stmt.order_by(
            ProjectAssetLink.relation_type.asc(), ProjectAssetLink.created_at.desc()
        )
        result = await self.db.execute(stmt)
        return [self._compose_item(link, proj, asset) for link, asset in result.all()]

    async def list_for_asset(
        self, asset_code: str, include_deleted: bool = False
    ) -> list[ProjectAssetLinkItem]:
        asset = await self._get_asset(asset_code)
        stmt = (
            select(ProjectAssetLink, Project)
            .join(Project, Project.project_id == ProjectAssetLink.project_id)
            .where(
                ProjectAssetLink.asset_id == asset.asset_id,
                Project.deleted_at.is_(None),
            )
        )
        if not include_deleted:
            stmt = stmt.where(ProjectAssetLink.deleted_at.is_(None))
        stmt = stmt.order_by(ProjectAssetLink.created_at.desc())
        result = await self.db.execute(stmt)
        return [self._compose_item(link, proj, asset) for link, proj in result.all()]

    @staticmethod
    def _compose_item(
        link: ProjectAssetLink, proj: Project, asset: Asset
    ) -> ProjectAssetLinkItem:
        return ProjectAssetLinkItem(
            relation_type=link.relation_type,
            notes=link.notes,
            created_at=link.created_at,
            created_by=link.created_by,
            updated_at=link.updated_at,
            updated_by=link.updated_by,
            deleted_at=link.deleted_at,
            project_code=proj.project_code,
            project_name=proj.project_name,
            project_status=proj.status,
            project_type=proj.project_type,
            asset_code=asset.asset_code,
            asset_internal_name=asset.internal_name,
            asset_type=asset.asset_type,
            asset_status=asset.status,
            asset_phase=asset.current_phase,
        )
