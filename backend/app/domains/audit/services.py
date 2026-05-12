"""
审计查询服务
"""
from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import (
    AssetNotFoundError,
    ProjectNotFoundError,
    SubstanceNotFoundError,
)
from app.domains.ars.models import Asset, AssetMarketId
from app.domains.audit.models import AuditLog, ChangeHistory
from app.domains.audit.schemas import AuditLogItem, ChangeHistoryItem
from app.domains.prs.models import Project, ProjectMilestone, ProjectTeam
from app.domains.ref.models import ProjectSubstanceLink
from app.domains.srs.models import Substance, SubstanceXref


class AuditService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_substance_audit_logs(
        self,
        substance_code: str,
        page: int,
        page_size: int,
        include_children: bool = True,
    ) -> tuple[list[AuditLogItem], int]:
        """查询某个 substance 的全部审计日志

        include_children=True 时连带返回 substance_protein / substance_xref 的日志，
        这是 user 在详情页"审计" Tab 期望看到的完整变更历史。
        """
        sub_result = await self.db.execute(
            select(Substance.substance_id).where(
                Substance.substance_code == substance_code,
                Substance.deleted_at.is_(None),
            )
        )
        substance_id = sub_result.scalar_one_or_none()
        if substance_id is None:
            raise SubstanceNotFoundError()

        conditions = [
            and_(AuditLog.entity_table == "substance", AuditLog.entity_id == substance_id)
        ]

        if include_children:
            conditions.append(
                and_(
                    AuditLog.entity_table == "substance_protein",
                    AuditLog.entity_id == substance_id,
                )
            )
            # 注：xref 的 audit 用 xref_id 作为 entity_id，不是 substance_id
            # 取该 substance 全部 xref_id（包含已软删的）
            xref_ids_result = await self.db.execute(
                select(SubstanceXref.xref_id).where(SubstanceXref.substance_id == substance_id)
            )
            xref_ids = [r[0] for r in xref_ids_result]
            if xref_ids:
                conditions.append(
                    and_(
                        AuditLog.entity_table == "substance_xref",
                        AuditLog.entity_id.in_(xref_ids),
                    )
                )

        where_clause = or_(*conditions)

        total = (
            await self.db.execute(select(func.count()).select_from(AuditLog).where(where_clause))
        ).scalar_one()

        page_result = await self.db.execute(
            select(AuditLog)
            .where(where_clause)
            .order_by(AuditLog.log_id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        logs = list(page_result.scalars())

        # 一次性把该页所有 log 的 change_history 拉回来，按 log_id 分组
        log_ids = [log.log_id for log in logs]
        changes_by_log: dict[int, list[ChangeHistoryItem]] = {}
        if log_ids:
            ch_result = await self.db.execute(
                select(ChangeHistory)
                .where(ChangeHistory.audit_log_id.in_(log_ids))
                .order_by(ChangeHistory.history_id)
            )
            for ch in ch_result.scalars():
                changes_by_log.setdefault(ch.audit_log_id, []).append(
                    ChangeHistoryItem(
                        field_name=ch.field_name,
                        old_value=ch.old_value,
                        new_value=ch.new_value,
                    )
                )

        items = [
            AuditLogItem(
                log_id=log.log_id,
                user_id=log.user_id,
                username=log.username,
                action=log.action,
                entity_schema=log.entity_schema,
                entity_table=log.entity_table,
                entity_id=log.entity_id,
                entity_code=log.entity_code,
                reason=log.reason,
                ip_address=str(log.ip_address) if log.ip_address else None,
                request_id=log.request_id,
                timestamp=log.timestamp,
                changes=changes_by_log.get(log.log_id, []),
            )
            for log in logs
        ]
        return items, total

    async def get_project_audit_logs(
        self,
        project_code: str,
        page: int,
        page_size: int,
        include_children: bool = True,
    ) -> tuple[list[AuditLogItem], int]:
        """查询某 project 的审计日志（M2.1 仅 project 表；M2.2 起加 milestone/team/link）"""
        proj_result = await self.db.execute(
            select(Project.project_id).where(
                Project.project_code == project_code,
                Project.deleted_at.is_(None),
            )
        )
        project_id = proj_result.scalar_one_or_none()
        if project_id is None:
            raise ProjectNotFoundError()

        conditions = [
            and_(AuditLog.entity_table == "project", AuditLog.entity_id == project_id)
        ]

        if include_children:
            # milestone：entity_id 是 milestone_id；用 project_id 反查
            mid_result = await self.db.execute(
                select(ProjectMilestone.milestone_id).where(
                    ProjectMilestone.project_id == project_id
                )
            )
            mids = [r[0] for r in mid_result]
            if mids:
                conditions.append(
                    and_(
                        AuditLog.entity_table == "project_milestone",
                        AuditLog.entity_id.in_(mids),
                    )
                )
            # team
            tid_result = await self.db.execute(
                select(ProjectTeam.team_id).where(ProjectTeam.project_id == project_id)
            )
            tids = [r[0] for r in tid_result]
            if tids:
                conditions.append(
                    and_(
                        AuditLog.entity_table == "project_team",
                        AuditLog.entity_id.in_(tids),
                    )
                )
            # ref.project_substance：trigger 写入 entity_id = project_id（§11.2 复合 PK 无单一 ID）
            # 所以这里不需要单独查 link_id；过滤条件直接用 project_id 即可
            conditions.append(
                and_(
                    AuditLog.entity_table == "project_substance",
                    AuditLog.entity_id == project_id,
                )
            )
            # ref.project_asset：同模式（§11.4 trigger 第 1 参数 = project_id）
            conditions.append(
                and_(
                    AuditLog.entity_table == "project_asset",
                    AuditLog.entity_id == project_id,
                )
            )

        where_clause = or_(*conditions)

        total = (
            await self.db.execute(select(func.count()).select_from(AuditLog).where(where_clause))
        ).scalar_one()

        page_result = await self.db.execute(
            select(AuditLog)
            .where(where_clause)
            .order_by(AuditLog.log_id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        logs = list(page_result.scalars())

        log_ids = [log.log_id for log in logs]
        changes_by_log: dict[int, list[ChangeHistoryItem]] = {}
        if log_ids:
            ch_result = await self.db.execute(
                select(ChangeHistory)
                .where(ChangeHistory.audit_log_id.in_(log_ids))
                .order_by(ChangeHistory.history_id)
            )
            for ch in ch_result.scalars():
                changes_by_log.setdefault(ch.audit_log_id, []).append(
                    ChangeHistoryItem(
                        field_name=ch.field_name,
                        old_value=ch.old_value,
                        new_value=ch.new_value,
                    )
                )

        items = [
            AuditLogItem(
                log_id=log.log_id,
                user_id=log.user_id,
                username=log.username,
                action=log.action,
                entity_schema=log.entity_schema,
                entity_table=log.entity_table,
                entity_id=log.entity_id,
                entity_code=log.entity_code,
                reason=log.reason,
                ip_address=str(log.ip_address) if log.ip_address else None,
                request_id=log.request_id,
                timestamp=log.timestamp,
                changes=changes_by_log.get(log.log_id, []),
            )
            for log in logs
        ]
        return items, total

    async def get_asset_audit_logs(
        self,
        asset_code: str,
        page: int,
        page_size: int,
        include_children: bool = True,
    ) -> tuple[list[AuditLogItem], int]:
        """查询某 asset 的审计日志（M3.1 含 asset + asset_market_id 子表）"""
        asset_result = await self.db.execute(
            select(Asset.asset_id).where(
                Asset.asset_code == asset_code,
                Asset.deleted_at.is_(None),
            )
        )
        asset_id = asset_result.scalar_one_or_none()
        if asset_id is None:
            raise AssetNotFoundError()

        conditions = [
            and_(AuditLog.entity_table == "asset", AuditLog.entity_id == asset_id)
        ]
        if include_children:
            mid_result = await self.db.execute(
                select(AssetMarketId.market_id_pk).where(
                    AssetMarketId.asset_id == asset_id
                )
            )
            mids = [r[0] for r in mid_result]
            if mids:
                conditions.append(
                    and_(
                        AuditLog.entity_table == "asset_market_id",
                        AuditLog.entity_id.in_(mids),
                    )
                )
            # ref.asset_substance：trigger 写入 entity_id = asset_id（§11.3 复合 PK 无单一 ID）
            conditions.append(
                and_(
                    AuditLog.entity_table == "asset_substance",
                    AuditLog.entity_id == asset_id,
                )
            )

        where_clause = or_(*conditions)
        total = (
            await self.db.execute(select(func.count()).select_from(AuditLog).where(where_clause))
        ).scalar_one()

        page_result = await self.db.execute(
            select(AuditLog)
            .where(where_clause)
            .order_by(AuditLog.log_id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        logs = list(page_result.scalars())

        log_ids = [log.log_id for log in logs]
        changes_by_log: dict[int, list[ChangeHistoryItem]] = {}
        if log_ids:
            ch_result = await self.db.execute(
                select(ChangeHistory)
                .where(ChangeHistory.audit_log_id.in_(log_ids))
                .order_by(ChangeHistory.history_id)
            )
            for ch in ch_result.scalars():
                changes_by_log.setdefault(ch.audit_log_id, []).append(
                    ChangeHistoryItem(
                        field_name=ch.field_name,
                        old_value=ch.old_value,
                        new_value=ch.new_value,
                    )
                )

        items = [
            AuditLogItem(
                log_id=log.log_id,
                user_id=log.user_id,
                username=log.username,
                action=log.action,
                entity_schema=log.entity_schema,
                entity_table=log.entity_table,
                entity_id=log.entity_id,
                entity_code=log.entity_code,
                reason=log.reason,
                ip_address=str(log.ip_address) if log.ip_address else None,
                request_id=log.request_id,
                timestamp=log.timestamp,
                changes=changes_by_log.get(log.log_id, []),
            )
            for log in logs
        ]
        return items, total
