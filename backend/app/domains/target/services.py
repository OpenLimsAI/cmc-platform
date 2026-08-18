"""靶点域业务服务层

轻档审核（对标 mm/eqp）：CRUD + publish/retire（只要 change_reason，无电签、无状态机表）。
关联（ref.molecule_target）与快照（tgt.target_source_snapshot）作为 /targets/{code} 子资源。

async SQLAlchemy 约定：不 try/except IntegrityError，一律 pre-check；updated_at 由 DB 触发器维护。
"""
from datetime import UTC, datetime

from sqlalchemy import Text, cast, func, or_, select, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import (
    BadRequestError,
    ConflictError,
    NotFoundError,
    OperationNotAllowedError,
)
from app.domains.auth.models import User
from app.domains.srs.models import Substance
from app.domains.target.models import MoleculeTargetLink, Target, TargetSourceSnapshot
from app.domains.target.prefill import UNIPROT_BASE, build_uniprot_prefill
from app.domains.target.schemas import (
    MoleculeTargetLinkCreate,
    MoleculeTargetLinkOut,
    MoleculeTargetLinkUpdate,
    TargetBrief,
    TargetCreate,
    TargetDetail,
    TargetFilter,
    TargetPrefillResponse,
    TargetSnapshotBrief,
    TargetSnapshotCreate,
    TargetSnapshotDetail,
    TargetUpdate,
)

# 轻档"状态机"：只允许这两步（draft/retired → published 需人工核对后发布；published → retired）
STATUS_ACTIONS: dict[str, dict[str, str]] = {
    "publish": {"draft": "published", "retired": "published"},
    "retire": {"published": "retired", "draft": "retired"},
}


async def _set_change_reason(db: AsyncSession, reason: str | None) -> None:
    if reason:
        await db.execute(
            text("SELECT set_config('app.change_reason', :r, true)"), {"r": reason}
        )


class TargetService:
    def __init__(self, db: AsyncSession):
        self.db = db

    # ----------- 列表 -----------
    async def list_targets(
        self, filter: TargetFilter, page: int, page_size: int, sort: str | None = None
    ) -> tuple[list[TargetBrief], int]:
        stmt = select(Target).where(Target.deleted_at.is_(None))

        if filter.q:
            for tok in [t for t in filter.q.split() if t]:
                kw = f"%{tok}%"
                stmt = stmt.where(
                    or_(
                        Target.target_code.ilike(kw),
                        Target.target_name.ilike(kw),
                        Target.uniprot_id.ilike(kw),
                        Target.gene_symbol.ilike(kw),
                        # JSONB 数组转文本模糊匹配（数据量小，够用）
                        cast(Target.aliases, Text).ilike(kw),
                        cast(Target.cd_antigen_names, Text).ilike(kw),
                        cast(Target.gene_synonyms, Text).ilike(kw),
                    )
                )
        if filter.keyword:
            kw_obj: dict = {"name": filter.keyword.strip()}
            if filter.keyword_category:
                kw_obj["category"] = filter.keyword_category.strip()
            stmt = stmt.where(Target.keywords.contains(cast([kw_obj], JSONB)))
        if filter.location:
            # 亚细胞定位名前缀/包含匹配（如 "Cell membrane" / "Secreted" / "Nucleus"）
            stmt = stmt.where(cast(Target.subcellular_locations, Text).ilike(f"%{filter.location.strip()}%"))
        if filter.entry_type:
            stmt = stmt.where(Target.entry_type.ilike(f"%{filter.entry_type.strip()}%"))
        if filter.status:
            stmt = stmt.where(Target.status.in_([s.strip() for s in filter.status.split(",")]))
        if filter.uniprot_id:
            stmt = stmt.where(Target.uniprot_id == filter.uniprot_id.strip().upper())

        total = (await self.db.execute(select(func.count()).select_from(stmt.subquery()))).scalar_one()

        if sort:
            for field in sort.split(","):
                f = field.strip()
                desc = f.startswith("-")
                col = getattr(Target, f.lstrip("-+"), None)
                if col is not None:
                    stmt = stmt.order_by(col.desc() if desc else col.asc())
        else:
            stmt = stmt.order_by(Target.updated_at.desc())

        stmt = stmt.offset((page - 1) * page_size).limit(page_size)
        rows = list((await self.db.execute(stmt)).scalars().all())
        return [TargetBrief.model_validate(t) for t in rows], total

    # ----------- 详情 -----------
    async def _get_target_or_404(self, code: str) -> Target:
        result = await self.db.execute(
            select(Target).where(Target.target_code == code, Target.deleted_at.is_(None))
        )
        target = result.scalar_one_or_none()
        if not target:
            raise NotFoundError(f"未找到 target: {code}")
        return target

    async def get_by_code(self, code: str) -> TargetDetail:
        return TargetDetail.model_validate(await self._get_target_or_404(code))

    # ----------- 查重（主 + 次级 accession）-----------
    async def find_by_accession(self, accession: str) -> Target | None:
        """按 UniProt accession 查重：命中 uniprot_id 或 aliases 里的次级 accession。"""
        acc = accession.strip().upper()
        result = await self.db.execute(
            select(Target).where(
                Target.deleted_at.is_(None),
                or_(Target.uniprot_id == acc, Target.aliases.contains([acc])),
            ).order_by(Target.target_id)
        )
        return result.scalars().first()

    async def _ensure_uniprot_unique(self, uniprot_id: str | None, exclude_id: int | None = None) -> None:
        if not uniprot_id:
            return
        existing = await self.find_by_accession(uniprot_id)
        if existing and existing.target_id != exclude_id:
            raise ConflictError(
                f"uniprot_id {uniprot_id} 已存在于 {existing.target_code}（{existing.target_name}），"
                f"请改为建立分子-靶点关联而不是新建靶点"
            )

    # ----------- 创建 -----------
    async def create(self, payload: TargetCreate, current_user: User) -> TargetDetail:
        uniprot_id = payload.uniprot_id.strip().upper() if payload.uniprot_id else None
        await self._ensure_uniprot_unique(uniprot_id)
        data = payload.model_dump(exclude_unset=False, mode="json", exclude={"uniprot_id"})
        target = Target(
            target_code=None,  # 由 tgt.fn_target_assign_code 触发器取号 TGT-NNNNNN
            uniprot_id=uniprot_id,
            status="draft",
            created_by=current_user.user_id,
            updated_by=current_user.user_id,
            **{k: v for k, v in data.items() if k != "uniprot_fetched_at"},
            uniprot_fetched_at=payload.uniprot_fetched_at,
        )
        self.db.add(target)
        await self.db.flush()
        await self.db.refresh(target)
        return TargetDetail.model_validate(target)

    # ----------- 更新 -----------
    async def update(self, code: str, payload: TargetUpdate, current_user: User) -> TargetDetail:
        await _set_change_reason(self.db, payload.change_reason)
        target = await self._get_target_or_404(code)
        update_data = payload.model_dump(exclude_unset=True, mode="json", exclude={"change_reason", "uniprot_fetched_at"})
        if payload.model_fields_set & {"uniprot_fetched_at"}:
            update_data["uniprot_fetched_at"] = payload.uniprot_fetched_at
        if "uniprot_id" in update_data and update_data["uniprot_id"]:
            update_data["uniprot_id"] = update_data["uniprot_id"].strip().upper()
            await self._ensure_uniprot_unique(update_data["uniprot_id"], exclude_id=target.target_id)
        for k, v in update_data.items():
            setattr(target, k, v)
        target.updated_by = current_user.user_id
        await self.db.flush()
        await self.db.refresh(target, ["updated_at"])
        return TargetDetail.model_validate(target)

    # ----------- 状态动作（轻档）-----------
    async def change_status(
        self, code: str, action: str, reason: str, current_user: User
    ) -> TargetDetail:
        transitions = STATUS_ACTIONS.get(action)
        if transitions is None:
            raise OperationNotAllowedError(f"未知动作: {action}")
        await _set_change_reason(self.db, reason)
        target = await self._get_target_or_404(code)
        new_status = transitions.get(target.status)
        if new_status is None:
            raise OperationNotAllowedError(
                f"target {code} 当前状态 {target.status} 不允许 {action}"
            )
        target.status = new_status
        target.updated_by = current_user.user_id
        await self.db.flush()
        await self.db.refresh(target, ["updated_at"])
        return TargetDetail.model_validate(target)

    # ----------- 软删除 -----------
    async def soft_delete(self, code: str, current_user: User, reason: str) -> None:
        await _set_change_reason(self.db, reason)
        target = await self._get_target_or_404(code)
        target.deleted_at = datetime.now(UTC)
        target.deleted_by = current_user.user_id
        target.updated_by = current_user.user_id
        await self.db.flush()

    # ============================================================
    # ref.molecule_target 子资源
    # ============================================================
    async def _get_substance_or_404(self, substance_code: str) -> Substance:
        result = await self.db.execute(
            select(Substance).where(
                Substance.substance_code == substance_code, Substance.deleted_at.is_(None)
            )
        )
        sub = result.scalar_one_or_none()
        if not sub:
            raise NotFoundError(f"未找到 substance: {substance_code}")
        return sub

    @staticmethod
    def _link_out(link: MoleculeTargetLink, sub: Substance, target: Target) -> MoleculeTargetLinkOut:
        return MoleculeTargetLinkOut(
            molecule_id=link.molecule_id,
            substance_code=sub.substance_code,
            substance_name=sub.preferred_name,
            target_id=link.target_id,
            target_code=target.target_code,
            target_name=target.target_name,
            relation_role=link.relation_role,  # type: ignore[arg-type]  # DB CHECK 保证枚举
            moa=link.moa,
            action_type=link.action_type,
            binding_epitope_or_domain=link.binding_epitope_or_domain,
            chembl_mechanism_id=link.chembl_mechanism_id,
            needs_confirm=link.needs_confirm,
            notes=link.notes,
            created_at=link.created_at,
            updated_at=link.updated_at,
        )

    async def list_molecules(self, code: str) -> list[MoleculeTargetLinkOut]:
        target = await self._get_target_or_404(code)
        result = await self.db.execute(
            select(MoleculeTargetLink, Substance)
            .join(Substance, Substance.substance_id == MoleculeTargetLink.molecule_id)
            .where(
                MoleculeTargetLink.target_id == target.target_id,
                MoleculeTargetLink.deleted_at.is_(None),
            )
            .order_by(MoleculeTargetLink.created_at)
        )
        return [self._link_out(link, sub, target) for link, sub in result.all()]

    async def list_targets_of_molecule(self, substance_code: str) -> list[MoleculeTargetLinkOut]:
        """反向：某分子的全部靶点关联（供二期 SRS 侧面板复用；一期挂在 /targets/by-molecule/{code}）"""
        sub = await self._get_substance_or_404(substance_code)
        result = await self.db.execute(
            select(MoleculeTargetLink, Target)
            .join(Target, Target.target_id == MoleculeTargetLink.target_id)
            .where(
                MoleculeTargetLink.molecule_id == sub.substance_id,
                MoleculeTargetLink.deleted_at.is_(None),
                Target.deleted_at.is_(None),
            )
            .order_by(MoleculeTargetLink.created_at)
        )
        return [self._link_out(link, sub, target) for link, target in result.all()]

    async def add_molecule(
        self, code: str, payload: MoleculeTargetLinkCreate, current_user: User
    ) -> MoleculeTargetLinkOut:
        target = await self._get_target_or_404(code)
        sub = await self._get_substance_or_404(payload.substance_code)

        active = await self.db.execute(
            select(MoleculeTargetLink).where(
                MoleculeTargetLink.molecule_id == sub.substance_id,
                MoleculeTargetLink.target_id == target.target_id,
                MoleculeTargetLink.relation_role == payload.relation_role,
                MoleculeTargetLink.deleted_at.is_(None),
            )
        )
        if active.scalar_one_or_none():
            raise ConflictError(
                f"substance {sub.substance_code} 已以 relation_role='{payload.relation_role}' 关联到 {code}"
            )

        # 软删过的同键行 → 重激活（对齐 ref 域写法，避免 PK 冲突）
        soft_deleted = await self.db.execute(
            select(MoleculeTargetLink).where(
                MoleculeTargetLink.molecule_id == sub.substance_id,
                MoleculeTargetLink.target_id == target.target_id,
                MoleculeTargetLink.relation_role == payload.relation_role,
                MoleculeTargetLink.deleted_at.is_not(None),
            )
        )
        link = soft_deleted.scalar_one_or_none()
        fields = payload.model_dump(exclude={"substance_code", "relation_role"})
        if link is not None:
            link.deleted_at = None
            link.deleted_by = None
            for k, v in fields.items():
                setattr(link, k, v)
            link.updated_by = current_user.user_id
        else:
            link = MoleculeTargetLink(
                molecule_id=sub.substance_id,
                target_id=target.target_id,
                relation_role=payload.relation_role,
                created_by=current_user.user_id,
                updated_by=current_user.user_id,
                **fields,
            )
            self.db.add(link)
        await self.db.flush()
        await self.db.refresh(link)
        return self._link_out(link, sub, target)

    async def _get_link_or_404(
        self, target: Target, sub: Substance, relation_role: str
    ) -> MoleculeTargetLink:
        result = await self.db.execute(
            select(MoleculeTargetLink).where(
                MoleculeTargetLink.molecule_id == sub.substance_id,
                MoleculeTargetLink.target_id == target.target_id,
                MoleculeTargetLink.relation_role == relation_role,
                MoleculeTargetLink.deleted_at.is_(None),
            )
        )
        link = result.scalar_one_or_none()
        if not link:
            raise NotFoundError(
                f"未找到关联: {sub.substance_code} ↔ {target.target_code} ({relation_role})"
            )
        return link

    async def update_molecule(
        self, code: str, substance_code: str, relation_role: str,
        payload: MoleculeTargetLinkUpdate, current_user: User,
    ) -> MoleculeTargetLinkOut:
        await _set_change_reason(self.db, payload.change_reason)
        target = await self._get_target_or_404(code)
        sub = await self._get_substance_or_404(substance_code)
        link = await self._get_link_or_404(target, sub, relation_role)
        for k, v in payload.model_dump(exclude_unset=True, exclude={"change_reason"}).items():
            setattr(link, k, v)
        link.updated_by = current_user.user_id
        link.updated_at = datetime.now(UTC)  # 关联表无 before_update 触发器（对齐 ref 域）
        await self.db.flush()
        await self.db.refresh(link)
        return self._link_out(link, sub, target)

    async def remove_molecule(
        self, code: str, substance_code: str, relation_role: str, reason: str, current_user: User
    ) -> None:
        await _set_change_reason(self.db, reason)
        target = await self._get_target_or_404(code)
        sub = await self._get_substance_or_404(substance_code)
        link = await self._get_link_or_404(target, sub, relation_role)
        link.deleted_at = datetime.now(UTC)
        link.deleted_by = current_user.user_id
        link.updated_by = current_user.user_id
        await self.db.flush()

    # ============================================================
    # tgt.target_source_snapshot 子资源（append-only）
    # ============================================================
    async def list_snapshots(self, code: str) -> list[TargetSnapshotBrief]:
        target = await self._get_target_or_404(code)
        result = await self.db.execute(
            select(TargetSourceSnapshot)
            .where(TargetSourceSnapshot.target_id == target.target_id)
            .order_by(TargetSourceSnapshot.fetched_at.desc(), TargetSourceSnapshot.snapshot_id.desc())
        )
        return [TargetSnapshotBrief.model_validate(s) for s in result.scalars().all()]

    async def get_snapshot(self, code: str, snapshot_id: int) -> TargetSnapshotDetail:
        target = await self._get_target_or_404(code)
        result = await self.db.execute(
            select(TargetSourceSnapshot).where(
                TargetSourceSnapshot.target_id == target.target_id,
                TargetSourceSnapshot.snapshot_id == snapshot_id,
            )
        )
        snap = result.scalar_one_or_none()
        if not snap:
            raise NotFoundError(f"未找到 snapshot {snapshot_id} of {code}")
        return TargetSnapshotDetail.model_validate(snap)

    async def add_snapshot(
        self, code: str, payload: TargetSnapshotCreate, current_user: User
    ) -> TargetSnapshotBrief:
        target = await self._get_target_or_404(code)
        snap = TargetSourceSnapshot(
            target_id=target.target_id,
            source=payload.source,
            source_id=payload.source_id,
            source_version=payload.source_version,
            source_url=payload.source_url,
            fetched_at=payload.fetched_at,
            payload=payload.payload,
            license=payload.license,
            created_by=current_user.user_id,
        )
        self.db.add(snap)
        await self.db.flush()
        await self.db.refresh(snap)
        return TargetSnapshotBrief.model_validate(snap)

    # ============================================================
    # UniProt 单条预填（新建靶点页「拉取」）：只读外部 GET，不落库
    # ============================================================
    async def prefill_from_uniprot(self, accession: str, *, transport=None) -> TargetPrefillResponse:
        from app.shared.http_client import ExternalHttpClient, ExternalHttpError

        acc = accession.strip().upper()
        existing = await self.find_by_accession(acc)
        try:
            async with ExternalHttpClient({"rest.uniprot.org"}, timeout_s=20.0, retries=2, transport=transport) as client:
                status, entry = await client.get_json(f"{UNIPROT_BASE}/{acc}.json")
        except ExternalHttpError as e:
            raise BadRequestError(f"UniProt 拉取失败：{e.detail or e.status}") from e
        if status == 404 or not entry:
            raise NotFoundError(f"UniProt 无此 accession: {acc}")
        data = build_uniprot_prefill(entry, acc)
        return TargetPrefillResponse(
            accession=acc,
            existing=TargetBrief.model_validate(existing) if existing else None,
            **data,
        )

    async def refresh_from_uniprot(self, code: str, reason: str, current_user: User, *, transport=None) -> TargetDetail:
        """按当前 uniprot_id 重新拉取 UniProt，整体覆盖标准字段并追加快照（notes / status 不动）。"""
        await _set_change_reason(self.db, reason)
        target = await self._get_target_or_404(code)
        if not target.uniprot_id:
            raise BadRequestError(f"target {code} 没有 uniprot_id，无法从 UniProt 刷新")
        pre = await self.prefill_from_uniprot(target.uniprot_id, transport=transport)
        form = pre.form.model_dump(mode="json", exclude_none=False)
        fetched_at = pre.form.uniprot_fetched_at
        for k, v in form.items():
            if k in ("uniprot_id", "uniprot_fetched_at"):
                continue
            setattr(target, k, v)
        target.uniprot_fetched_at = fetched_at
        target.updated_by = current_user.user_id
        await self.db.flush()
        snap = TargetSourceSnapshot(
            target_id=target.target_id,
            source=pre.snapshot.source, source_id=pre.snapshot.source_id,
            source_version=pre.snapshot.source_version, source_url=pre.snapshot.source_url,
            fetched_at=pre.snapshot.fetched_at, payload=pre.snapshot.payload, license=pre.snapshot.license,
            created_by=current_user.user_id,
        )
        self.db.add(snap)
        await self.db.flush()
        await self.db.refresh(target)
        return TargetDetail.model_validate(target)

    # ============================================================
    # 审计日志：主表 + 关联表（ref.molecule_target 审计以 target_id 为 entity_id）
    # ============================================================
    async def get_audit_logs(self, code: str, page: int, page_size: int, include_children: bool = True):
        from sqlalchemy import and_

        from app.domains.audit.models import AuditLog
        from app.domains.audit.services import AuditService

        target = await self._get_target_or_404(code)
        conditions = [and_(AuditLog.entity_schema == "tgt", AuditLog.entity_table == "target",
                           AuditLog.entity_id == target.target_id)]
        if include_children:
            conditions.append(and_(AuditLog.entity_schema == "ref", AuditLog.entity_table == "molecule_target",
                                   AuditLog.entity_id == target.target_id))
        return await AuditService(self.db).get_entity_audit_logs(conditions, page, page_size)
