"""
审计查询服务
"""
import csv
import io

from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import (
    AssetNotFoundError,
    MaterialNotFoundError,
    ProjectNotFoundError,
    SubstanceNotFoundError,
)
from app.domains.ars.models import Asset, AssetMarketId
from app.domains.audit.models import AuditLog, ChangeHistory, ESignature
from app.domains.audit.schemas import (
    AuditLogFilter,
    AuditLogItem,
    ChangeHistoryItem,
    ESignatureItem,
    SignatureFilter,
)
from app.domains.auth.models import User
from app.domains.mm.models import Material, MaterialBatch
from app.domains.prs.models import Project, ProjectMilestone, ProjectPMLink, ProjectRelationship, ProjectTeam
from app.domains.srs.models import Substance, SubstanceXref

# CSV 导出列定义（21 CFR Part 11 §11.10(c) 审计归档；用户决策 CSV-only）
_AUDIT_CSV_HEADERS = [
    "log_id",
    "timestamp",
    "username",
    "user_id",
    "action",
    "entity_schema",
    "entity_table",
    "entity_id",
    "entity_code",
    "reason",
    "ip_address",
    "request_id",
    "changes",  # 序列化为 "field1: old→new; field2: old→new"
]

# 导出上限：单次最多 50000 行（生产可由 settings 控制；超量请按时间段切片）
AUDIT_EXPORT_MAX_ROWS = 50000


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
                change_summary=log.change_summary,
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
            pm_link_ids = select(ProjectPMLink.link_id).where(ProjectPMLink.project_id == project_id)
            conditions.append(and_(AuditLog.entity_schema == "prs", AuditLog.entity_table == "project_pm_link",
                                   AuditLog.entity_id.in_(pm_link_ids)))
            relationship_ids = select(ProjectRelationship.relationship_id).where(or_(
                ProjectRelationship.from_project_id == project_id,
                ProjectRelationship.to_project_id == project_id,
            ))
            conditions.append(and_(AuditLog.entity_schema == "prs", AuditLog.entity_table == "project_relationship",
                                   AuditLog.entity_id.in_(relationship_ids)))
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
                change_summary=log.change_summary,
                ip_address=str(log.ip_address) if log.ip_address else None,
                request_id=log.request_id,
                timestamp=log.timestamp,
                changes=changes_by_log.get(log.log_id, []),
            )
            for log in logs
        ]
        return items, total

    async def get_material_audit_logs(
        self,
        material_code: str,
        page: int,
        page_size: int,
        include_children: bool = True,
    ) -> tuple[list[AuditLogItem], int]:
        """查询某 material 的审计日志（M4.1 仅 material 主表；M4.2 起加 material_batch 子表）"""
        mat_result = await self.db.execute(
            select(Material.material_id).where(
                Material.material_code == material_code,
                Material.deleted_at.is_(None),
            )
        )
        material_id = mat_result.scalar_one_or_none()
        if material_id is None:
            raise MaterialNotFoundError()

        conditions = [
            and_(AuditLog.entity_table == "material", AuditLog.entity_id == material_id)
        ]
        if include_children:
            bid_result = await self.db.execute(
                select(MaterialBatch.batch_id).where(
                    MaterialBatch.material_id == material_id
                )
            )
            bids = [r[0] for r in bid_result]
            if bids:
                conditions.append(
                    and_(
                        AuditLog.entity_table == "material_batch",
                        AuditLog.entity_id.in_(bids),
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
                change_summary=log.change_summary,
                ip_address=str(log.ip_address) if log.ip_address else None,
                request_id=log.request_id,
                timestamp=log.timestamp,
                changes=changes_by_log.get(log.log_id, []),
            )
            for log in logs
        ]
        return items, total

    # ----------- 通用：按 (schema, table, id 集合) 条件查审计（新域接入用，靶点域首用）-----------
    async def get_entity_audit_logs(
        self,
        conditions: list,
        page: int,
        page_size: int,
    ) -> tuple[list[AuditLogItem], int]:
        """conditions: 若干 sqlalchemy 条件（如 and_(AuditLog.entity_table=='target', AuditLog.entity_id==1)），
        之间取 OR；返回分页 AuditLogItem（含字段级 diff）。"""
        if not conditions:
            return [], 0
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
                    ChangeHistoryItem(field_name=ch.field_name, old_value=ch.old_value, new_value=ch.new_value)
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
                change_summary=log.change_summary,
                ip_address=str(log.ip_address) if log.ip_address else None,
                request_id=log.request_id,
                timestamp=log.timestamp,
                changes=changes_by_log.get(log.log_id, []),
            )
            for log in logs
        ]
        return items, total

    # ----------- Phase 5.A / M5.3：全局审计 + 签名查询 -----------

    def _apply_audit_filters(self, stmt, filter: AuditLogFilter):
        if filter.username:
            stmt = stmt.where(AuditLog.username == filter.username)
        if filter.action:
            stmt = stmt.where(AuditLog.action == filter.action)
        if filter.entity_table:
            stmt = stmt.where(AuditLog.entity_table == filter.entity_table)
        if filter.entity_code:
            stmt = stmt.where(AuditLog.entity_code == filter.entity_code)
        if filter.date_from:
            stmt = stmt.where(AuditLog.timestamp >= filter.date_from)
        if filter.date_to:
            stmt = stmt.where(AuditLog.timestamp <= filter.date_to)
        if filter.q:
            pattern = f"%{filter.q}%"
            stmt = stmt.where(
                or_(
                    AuditLog.entity_code.ilike(pattern),
                    AuditLog.reason.ilike(pattern),
                )
            )
        return stmt

    async def list_global_audit_logs(
        self,
        filter: AuditLogFilter,
        page: int,
        page_size: int,
    ) -> tuple[list[AuditLogItem], int]:
        """全局审计日志查询（API11 顶层端点）。结果含字段级 diff。"""
        base_stmt = select(AuditLog)
        base_stmt = self._apply_audit_filters(base_stmt, filter)
        count_stmt = self._apply_audit_filters(
            select(func.count()).select_from(AuditLog), filter
        )
        total = (await self.db.execute(count_stmt)).scalar_one()

        page_result = await self.db.execute(
            base_stmt
            .order_by(AuditLog.log_id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        logs = list(page_result.scalars())

        # 按稳定的用户 ID 批量补充当前姓名；保留停用/软删除账号的历史日志。
        user_ids = {log.user_id for log in logs if log.user_id is not None}
        names_by_user: dict[int, str | None] = {}
        if user_ids:
            names_result = await self.db.execute(
                select(User.user_id, User.full_name).where(User.user_id.in_(user_ids))
            )
            names_by_user = {
                user_id: full_name if full_name and full_name.strip() else None
                for user_id, full_name in names_result
            }

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
                full_name=names_by_user.get(log.user_id) if log.user_id is not None else None,
                action=log.action,
                entity_schema=log.entity_schema,
                entity_table=log.entity_table,
                entity_id=log.entity_id,
                entity_code=log.entity_code,
                reason=log.reason,
                change_summary=log.change_summary,
                ip_address=str(log.ip_address) if log.ip_address else None,
                request_id=log.request_id,
                timestamp=log.timestamp,
                changes=changes_by_log.get(log.log_id, []),
            )
            for log in logs
        ]
        return items, total

    async def export_audit_logs_csv(self, filter: AuditLogFilter) -> tuple[str, int]:
        """导出审计日志为 CSV 字符串。返回 (csv_text, row_count)。

        合规：单次最多导出 AUDIT_EXPORT_MAX_ROWS 行（默认 50000）。超量提示用户按
        date_from / date_to 切片再导。CSV 编码 UTF-8 BOM，Excel 直接打开不乱码。

        实现注意：change_history 查询用 SQL 子查询（select(...).scalar_subquery()），
        而不是先取 50000 个 log_id 再 IN 绑定 — asyncpg 单次 bind 参数上限 32767，
        50000 行直接 IN 列表会 InterfaceError。
        """
        stmt = select(AuditLog)
        stmt = self._apply_audit_filters(stmt, filter)
        stmt = stmt.order_by(AuditLog.log_id.desc()).limit(AUDIT_EXPORT_MAX_ROWS)
        result = await self.db.execute(stmt)
        logs = list(result.scalars())

        changes_by_log: dict[int, list[ChangeHistory]] = {}
        if logs:
            log_id_subq = (
                self._apply_audit_filters(select(AuditLog.log_id), filter)
                .order_by(AuditLog.log_id.desc())
                .limit(AUDIT_EXPORT_MAX_ROWS)
                .scalar_subquery()
            )
            ch_result = await self.db.execute(
                select(ChangeHistory)
                .where(ChangeHistory.audit_log_id.in_(log_id_subq))
                .order_by(ChangeHistory.history_id)
            )
            for ch in ch_result.scalars():
                changes_by_log.setdefault(ch.audit_log_id, []).append(ch)

        def _format_change(ch: ChangeHistory) -> str:
            def _v(x):
                return "" if x is None else str(x)
            return f"{ch.field_name}: {_v(ch.old_value)}→{_v(ch.new_value)}"

        buf = io.StringIO()
        buf.write("﻿")  # UTF-8 BOM（Excel 友好）
        writer = csv.writer(buf, quoting=csv.QUOTE_MINIMAL)
        writer.writerow(_AUDIT_CSV_HEADERS)
        for log in logs:
            chs = changes_by_log.get(log.log_id, [])
            changes_text = "; ".join(_format_change(c) for c in chs) if chs else ""
            writer.writerow([
                log.log_id,
                log.timestamp.isoformat(),
                log.username,
                log.user_id or "",
                log.action,
                log.entity_schema or "",
                log.entity_table or "",
                log.entity_id or "",
                log.entity_code or "",
                log.reason or "",
                str(log.ip_address) if log.ip_address else "",
                log.request_id or "",
                changes_text,
            ])
        return buf.getvalue(), len(logs)

    def _apply_signature_filters(self, stmt, filter: SignatureFilter):
        if filter.username:
            stmt = stmt.where(ESignature.username == filter.username)
        if filter.entity_table:
            stmt = stmt.where(ESignature.entity_table == filter.entity_table)
        if filter.entity_code:
            stmt = stmt.where(ESignature.entity_code == filter.entity_code)
        if filter.signature_meaning:
            stmt = stmt.where(ESignature.signature_meaning == filter.signature_meaning)
        if filter.date_from:
            stmt = stmt.where(ESignature.signed_at >= filter.date_from)
        if filter.date_to:
            stmt = stmt.where(ESignature.signed_at <= filter.date_to)
        return stmt

    async def list_signatures(
        self,
        filter: SignatureFilter,
        page: int,
        page_size: int,
    ) -> tuple[list[ESignatureItem], int]:
        """电子签名全局列表（GxP 21 CFR Part 11 §11.50 监管查询）"""
        base_stmt = select(ESignature)
        base_stmt = self._apply_signature_filters(base_stmt, filter)
        count_stmt = self._apply_signature_filters(
            select(func.count()).select_from(ESignature), filter
        )
        total = (await self.db.execute(count_stmt)).scalar_one()

        page_result = await self.db.execute(
            base_stmt
            .order_by(ESignature.signature_id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        sigs = list(page_result.scalars())
        items = [ESignatureItem.model_validate(s) for s in sigs]
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
                change_summary=log.change_summary,
                ip_address=str(log.ip_address) if log.ip_address else None,
                request_id=log.request_id,
                timestamp=log.timestamp,
                changes=changes_by_log.get(log.log_id, []),
            )
            for log in logs
        ]
        return items, total
