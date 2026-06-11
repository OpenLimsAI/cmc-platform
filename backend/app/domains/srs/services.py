"""
SRS 业务服务层
"""
import hashlib
import re
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import func, or_, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import (
    BadRequestError,
    DuplicateCodeError,
    SignatureRequiredError,
    StateInvalidError,
    SubstanceNotFoundError,
    VersionConflictError,
    XrefNotFoundError,
)
from app.domains.audit.signature_service import ESignatureService
from app.domains.audit.schemas import StatusHistoryItem
from app.domains.auth.models import User
from app.domains.srs.models import (
    Substance,
    SubstanceProtein,
    SubstanceStatusHistory,
    SubstanceXref,
)
from app.domains.srs.schemas import (
    CheckSamenessRequest,
    CheckSamenessResponse,
    SamenessMatch,
    SubstanceBrief,
    SubstanceCreate,
    SubstanceDetail,
    SubstanceFilter,
    SubstanceUpdate,
    SubstanceXref as SubstanceXrefSchema,
    SubstanceXrefCreate,
    SubstanceXrefUpdate,
)


# 状态机：action → {当前状态: 下一状态}
# 设计依据 ARCH-MDM-001 §11.2.1
STATE_MACHINE: dict[str, dict[str, str]] = {
    "approve":   {"draft": "registered"},
    "activate":  {"registered": "active"},
    "restrict":  {"active": "restricted"},
    "deprecate": {"active": "deprecated", "restricted": "deprecated"},
    "obsolete":  {"deprecated": "obsoleted"},
}

# GxP 关键动作：21 CFR Part 11 §11.50/11.70 要求电子签名
# :restrict 是可逆的临时风控，不要求签名
SIGNATURE_REQUIRED_ACTIONS: set[str] = {"approve", "activate", "deprecate", "obsolete"}

# action → e_signature.signature_meaning
ACTION_TO_MEANING: dict[str, str] = {
    "approve":   "approve",
    "activate":  "approve",
    "restrict":  "review",
    "deprecate": "reject",
    "obsolete":  "reject",
}


def _clean_sequence(seq: str | None) -> str | None:
    if seq is None:
        return None
    return re.sub(r"[^A-Z]", "", seq.upper())


def _hash_sequence(seq: str | None) -> str | None:
    cleaned = _clean_sequence(seq)
    if not cleaned:
        return None
    return hashlib.sha256(cleaned.encode()).hexdigest()


class SubstanceService:
    def __init__(self, db: AsyncSession):
        self.db = db

    # ----------- 编码生成 -----------
    async def _next_substance_code(self) -> str:
        result = await self.db.execute(text("SELECT meta.fn_next_code('substance')"))
        row = result.scalar_one()
        return row

    # ----------- 列表查询 -----------
    async def list_substances(
        self,
        filter: SubstanceFilter,
        page: int,
        page_size: int,
        sort: str | None = None,
    ) -> tuple[list[SubstanceBrief], int]:
        # 基础查询
        stmt = select(Substance).where(Substance.deleted_at.is_(None))

        # 过滤
        if filter.q:
            kw = f"%{filter.q}%"
            stmt = stmt.where(
                or_(
                    Substance.substance_code.ilike(kw),
                    Substance.internal_code.ilike(kw),
                    Substance.preferred_name.ilike(kw),
                    Substance.preferred_name_en.ilike(kw),
                )
            )
        if filter.substance_type:
            types = [t.strip() for t in filter.substance_type.split(",")]
            stmt = stmt.where(Substance.substance_type.in_(types))
        if filter.status:
            statuses = [s.strip() for s in filter.status.split(",")]
            stmt = stmt.where(Substance.status.in_(statuses))
        if filter.target:
            stmt = stmt.where(Substance.target.ilike(f"%{filter.target}%"))
        if filter.confidentiality:
            stmt = stmt.where(Substance.confidentiality == filter.confidentiality)

        # 计数
        count_stmt = select(func.count()).select_from(stmt.subquery())
        total = (await self.db.execute(count_stmt)).scalar_one()

        # 排序
        if sort:
            for field in sort.split(","):
                f = field.strip()
                desc = f.startswith("-")
                fname = f.lstrip("-+")
                col = getattr(Substance, fname, None)
                if col is not None:
                    stmt = stmt.order_by(col.desc() if desc else col.asc())
        else:
            stmt = stmt.order_by(Substance.updated_at.desc())

        # 分页
        stmt = stmt.offset((page - 1) * page_size).limit(page_size)

        result = await self.db.execute(stmt)
        substances = list(result.scalars().all())

        # 一条 IN 查询批量加载本页的 INN/CAS，避免逐行 N+1
        xref_map: dict[int, dict[str, str]] = {}
        if substances:
            sub_ids = [s.substance_id for s in substances]
            xref_result = await self.db.execute(
                select(
                    SubstanceXref.substance_id,
                    SubstanceXref.xref_type,
                    SubstanceXref.xref_value,
                ).where(
                    SubstanceXref.substance_id.in_(sub_ids),
                    SubstanceXref.xref_type.in_(("INN", "CAS")),
                    SubstanceXref.deleted_at.is_(None),
                )
            )
            for sub_id, xtype, xval in xref_result.all():
                # 同类型多条只取第一条（与原 _get_xref limit(1) 行为一致）
                xref_map.setdefault(sub_id, {}).setdefault(xtype, xval)

        # UI6（V1.1 §6.1 行 420-426）：批量聚合 ref.project_substance / ref.asset_substance
        # + mm.material 反查（M4.3 启用 material_count）
        project_count_map: dict[int, int] = {}
        asset_count_map: dict[int, int] = {}
        material_count_map: dict[int, int] = {}
        if substances:
            from app.domains.mm.models import Material
            from app.domains.ref.models import (
                AssetSubstanceLink,
                ProjectSubstanceLink,
            )

            sub_ids = [s.substance_id for s in substances]
            proj_count_result = await self.db.execute(
                select(ProjectSubstanceLink.substance_id, func.count())
                .where(
                    ProjectSubstanceLink.substance_id.in_(sub_ids),
                    ProjectSubstanceLink.deleted_at.is_(None),
                )
                .group_by(ProjectSubstanceLink.substance_id)
            )
            project_count_map = {sid: cnt for sid, cnt in proj_count_result.all()}

            asset_count_result = await self.db.execute(
                select(AssetSubstanceLink.substance_id, func.count())
                .where(
                    AssetSubstanceLink.substance_id.in_(sub_ids),
                    AssetSubstanceLink.deleted_at.is_(None),
                )
                .group_by(AssetSubstanceLink.substance_id)
            )
            asset_count_map = {sid: cnt for sid, cnt in asset_count_result.all()}

            mat_count_result = await self.db.execute(
                select(Material.substance_id, func.count())
                .where(
                    Material.substance_id.in_(sub_ids),
                    Material.deleted_at.is_(None),
                )
                .group_by(Material.substance_id)
            )
            material_count_map = {sid: cnt for sid, cnt in mat_count_result.all() if sid}

        items: list[SubstanceBrief] = []
        for sub in substances:
            xrefs_for_sub = xref_map.get(sub.substance_id, {})
            items.append(
                SubstanceBrief(
                    substance_code=sub.substance_code,
                    substance_type=sub.substance_type,
                    internal_code=sub.internal_code,
                    preferred_name=sub.preferred_name,
                    preferred_name_en=sub.preferred_name_en,
                    target=sub.target,
                    status=sub.status,
                    confidentiality=sub.confidentiality,
                    inn=xrefs_for_sub.get("INN"),
                    cas_number=xrefs_for_sub.get("CAS"),
                    project_count=project_count_map.get(sub.substance_id, 0),
                    asset_count=asset_count_map.get(sub.substance_id, 0),
                    material_count=material_count_map.get(sub.substance_id, 0),
                    created_at=sub.created_at,
                    updated_at=sub.updated_at,
                )
            )
        return items, total

    # ----------- 详情 -----------
    async def get_by_code(self, code: str, expand: list[str] | None = None) -> SubstanceDetail:
        result = await self.db.execute(
            select(Substance).where(
                Substance.substance_code == code,
                Substance.deleted_at.is_(None),
            )
        )
        sub = result.scalar_one_or_none()
        if not sub:
            raise SubstanceNotFoundError(f"未找到 substance: {code}")

        detail_data: dict[str, Any] = {
            "substance_id": sub.substance_id,
            "substance_code": sub.substance_code,
            "substance_type": sub.substance_type,
            "internal_code": sub.internal_code,
            "preferred_name": sub.preferred_name,
            "preferred_name_en": sub.preferred_name_en,
            "target": sub.target,
            "target_type": sub.target_type,
            "modality": sub.modality,
            "is_proprietary": sub.is_proprietary,
            "confidentiality": sub.confidentiality,
            "external_uuid": sub.external_uuid,
            "description": sub.description,
            "notes": sub.notes,
            "extra": sub.extra,
            "status": sub.status,
            "version": sub.version,
            "created_at": sub.created_at,
            "created_by": sub.created_by,
            "updated_at": sub.updated_at,
            "updated_by": sub.updated_by,
            "registered_at": sub.registered_at,
            "registered_by": sub.registered_by,
            "xrefs": [],
            "protein": None,
        }

        expand = expand or []

        if "protein" in expand or sub.substance_type in ("mab", "bispecific", "fusion"):
            p_result = await self.db.execute(
                select(SubstanceProtein).where(SubstanceProtein.substance_id == sub.substance_id)
            )
            protein = p_result.scalar_one_or_none()
            if protein:
                detail_data["protein"] = {
                    "heavy_chain_sequence": protein.heavy_chain_sequence,
                    "light_chain_sequence": protein.light_chain_sequence,
                    "additional_chains": protein.additional_chains,
                    "sequence_length_hc": protein.sequence_length_hc,
                    "sequence_length_lc": protein.sequence_length_lc,
                    "sequence_hash_hc": protein.sequence_hash_hc,
                    "sequence_hash_lc": protein.sequence_hash_lc,
                    "isotype": protein.isotype,
                    "architecture": protein.architecture,
                    "disulfide_bonds": protein.disulfide_bonds,
                    "glycosylation_sites": protein.glycosylation_sites,
                    "ptm_info": protein.ptm_info,
                    "expression_system": protein.expression_system,
                    "cell_line": protein.cell_line,
                    "expression_vector": protein.expression_vector,
                    "molecular_weight_da": protein.molecular_weight_da,
                    "pi_theoretical": protein.pi_theoretical,
                    "extinction_coefficient": protein.extinction_coefficient,
                }

        # xrefs 默认加载
        x_result = await self.db.execute(
            select(SubstanceXref).where(
                SubstanceXref.substance_id == sub.substance_id,
                SubstanceXref.deleted_at.is_(None),
            )
        )
        detail_data["xrefs"] = [
            {
                "xref_id": x.xref_id,
                "xref_type": x.xref_type,
                "xref_value": x.xref_value,
                "xref_source": x.xref_source,
                "region": x.region,
                "is_primary": x.is_primary,
                "effective_date": x.effective_date,
                "expiry_date": x.expiry_date,
                "notes": x.notes,
            }
            for x in x_result.scalars().all()
        ]

        return SubstanceDetail(**detail_data)

    # ----------- 创建 -----------
    async def create(self, payload: SubstanceCreate, current_user: User) -> SubstanceDetail:
        # 检查 internal_code 唯一性
        if payload.internal_code:
            exists = await self.db.execute(
                select(Substance.substance_id).where(
                    Substance.internal_code == payload.internal_code,
                    Substance.deleted_at.is_(None),
                )
            )
            if exists.scalar_one_or_none():
                raise DuplicateCodeError(
                    f"internal_code 已存在: {payload.internal_code}"
                )

        # 生成编码
        code = await self._next_substance_code()

        sub = Substance(
            substance_code=code,
            substance_type=payload.substance_type,
            internal_code=payload.internal_code,
            preferred_name=payload.preferred_name,
            preferred_name_en=payload.preferred_name_en,
            target=payload.target,
            target_type=payload.target_type,
            modality=payload.modality,
            is_proprietary=payload.is_proprietary,
            confidentiality=payload.confidentiality,
            description=payload.description,
            notes=payload.notes,
            extra=payload.extra,
            status="draft",
            created_by=current_user.user_id,
            updated_by=current_user.user_id,
        )
        self.db.add(sub)
        await self.db.flush()

        # 蛋白扩展
        if payload.protein and payload.substance_type in ("mab", "bispecific", "fusion"):
            p = payload.protein
            hc = _clean_sequence(p.heavy_chain_sequence)
            lc = _clean_sequence(p.light_chain_sequence)
            protein = SubstanceProtein(
                substance_id=sub.substance_id,
                heavy_chain_sequence=p.heavy_chain_sequence,
                light_chain_sequence=p.light_chain_sequence,
                additional_chains=p.additional_chains,
                sequence_length_hc=len(hc) if hc else None,
                sequence_length_lc=len(lc) if lc else None,
                sequence_hash_hc=_hash_sequence(p.heavy_chain_sequence),
                sequence_hash_lc=_hash_sequence(p.light_chain_sequence),
                isotype=p.isotype,
                architecture=p.architecture,
                disulfide_bonds=p.disulfide_bonds,
                glycosylation_sites=p.glycosylation_sites,
                ptm_info=p.ptm_info,
                expression_system=p.expression_system,
                cell_line=p.cell_line,
                expression_vector=p.expression_vector,
                molecular_weight_da=p.molecular_weight_da,
                pi_theoretical=p.pi_theoretical,
                extinction_coefficient=p.extinction_coefficient,
            )
            self.db.add(protein)

        # xrefs
        for x in payload.xrefs:
            xref = SubstanceXref(
                substance_id=sub.substance_id,
                xref_type=x.xref_type,
                xref_value=x.xref_value,
                xref_source=x.xref_source,
                region=x.region,
                is_primary=x.is_primary,
                effective_date=x.effective_date,
                expiry_date=x.expiry_date,
                notes=x.notes,
                created_by=current_user.user_id,
                updated_by=current_user.user_id,
            )
            self.db.add(xref)

        await self.db.flush()
        return await self.get_by_code(code)

    # ----------- 更新 -----------
    async def update(
        self, code: str, payload: SubstanceUpdate, current_user: User
    ) -> SubstanceDetail:
        if payload.change_reason:
            await self.db.execute(
                text("SELECT set_config('app.change_reason', :r, true)"),
                {"r": payload.change_reason},
            )

        result = await self.db.execute(
            select(Substance).where(
                Substance.substance_code == code,
                Substance.deleted_at.is_(None),
            )
        )
        sub = result.scalar_one_or_none()
        if not sub:
            raise SubstanceNotFoundError()

        if sub.version != payload.version:
            raise VersionConflictError(
                f"版本号不匹配（服务器: {sub.version}，请求: {payload.version}）"
            )

        # 检查 internal_code 唯一性（如有变更）
        if payload.internal_code and payload.internal_code != sub.internal_code:
            exists = await self.db.execute(
                select(Substance.substance_id).where(
                    Substance.internal_code == payload.internal_code,
                    Substance.deleted_at.is_(None),
                    Substance.substance_id != sub.substance_id,
                )
            )
            if exists.scalar_one_or_none():
                raise DuplicateCodeError(f"internal_code 已存在: {payload.internal_code}")

        update_data = payload.model_dump(
            exclude_unset=True,
            exclude={"version", "change_reason", "protein"},
        )
        for k, v in update_data.items():
            setattr(sub, k, v)
        sub.updated_by = current_user.user_id
        # version 与 updated_at 由 srs.fn_substance_before_update 触发器维护

        # protein 子结构 upsert
        if payload.protein is not None:
            if sub.substance_type not in ("mab", "bispecific", "fusion"):
                raise BadRequestError(
                    f"protein 信息不适用于 {sub.substance_type} 类型物质"
                )
            await self._upsert_protein(sub.substance_id, payload.protein)

        await self.db.flush()
        # 触发器修改了 version/updated_at，ORM identity map 不会自动同步，需显式 refresh
        await self.db.refresh(sub, ["version", "updated_at"])
        return await self.get_by_code(code)

    async def _upsert_protein(self, substance_id: int, payload) -> None:
        result = await self.db.execute(
            select(SubstanceProtein).where(SubstanceProtein.substance_id == substance_id)
        )
        protein = result.scalar_one_or_none()
        if protein is None:
            protein = SubstanceProtein(substance_id=substance_id)
            self.db.add(protein)

        # 只 set 用户显式传入的字段（model_dump exclude_unset 区分"未传"与"传 None"）
        data = payload.model_dump(exclude_unset=True)
        for k, v in data.items():
            setattr(protein, k, v)

        if "heavy_chain_sequence" in data:
            cleaned = _clean_sequence(data["heavy_chain_sequence"])
            protein.sequence_length_hc = len(cleaned) if cleaned else None
            protein.sequence_hash_hc = _hash_sequence(data["heavy_chain_sequence"])
        if "light_chain_sequence" in data:
            cleaned = _clean_sequence(data["light_chain_sequence"])
            protein.sequence_length_lc = len(cleaned) if cleaned else None
            protein.sequence_hash_lc = _hash_sequence(data["light_chain_sequence"])

    # ----------- API13:A 子资源 PUT 端点 -----------
    async def update_protein(self, code: str, payload, current_user: User):
        """V1.1 §5.1.3 行 750：PUT /substances/{code}/protein 独立子资源端点
        V1.2 评审 API13:A 决议（2026-05-13）"""
        from app.domains.srs.schemas import SubstanceDetail  # 局部避免循环

        sub = await self._get_substance_or_404(code)
        if sub.substance_type not in ("mab", "bispecific", "fusion"):
            raise BadRequestError(
                f"PUT /protein 不适用于 substance_type={sub.substance_type}"
            )
        await self._upsert_protein(sub.substance_id, payload)
        sub.updated_by = current_user.user_id
        await self.db.flush()
        await self.db.commit()
        return await self.get_by_code(code, expand=["protein"])

    async def update_adc(self, code: str, payload, current_user: User):
        """V1.1 §5.1.3 行 752：PUT /substances/{code}/adc 独立子资源端点
        V1.2 评审 API13:A 决议（2026-05-13）

        父子 substance 用 code 表达（前端友好），service 内查 ID。
        """
        from app.domains.srs.models import SubstanceADC

        sub = await self._get_substance_or_404(code)
        if sub.substance_type != "adc":
            raise BadRequestError(
                f"PUT /adc 仅适用于 substance_type='adc'，当前 {sub.substance_type}"
            )

        # 把 *_substance_code 解析为 substance_id
        data = payload.model_dump(exclude_unset=True)
        for code_key, id_key in [
            ("antibody_substance_code", "antibody_substance_id"),
            ("linker_substance_code", "linker_substance_id"),
            ("payload_substance_code", "payload_substance_id"),
        ]:
            if code_key in data:
                ref_code = data.pop(code_key)
                if ref_code is None:
                    data[id_key] = None
                    continue
                r = await self.db.execute(
                    select(Substance.substance_id).where(
                        Substance.substance_code == ref_code,
                        Substance.deleted_at.is_(None),
                    )
                )
                rid = r.scalar_one_or_none()
                if rid is None:
                    raise SubstanceNotFoundError(
                        f"父/子 substance {code_key}={ref_code} 不存在"
                    )
                data[id_key] = rid

        # upsert SubstanceADC
        result = await self.db.execute(
            select(SubstanceADC).where(SubstanceADC.substance_id == sub.substance_id)
        )
        adc = result.scalar_one_or_none()
        if adc is None:
            adc = SubstanceADC(substance_id=sub.substance_id)
            self.db.add(adc)
        for k, v in data.items():
            setattr(adc, k, v)

        sub.updated_by = current_user.user_id
        await self.db.flush()
        await self.db.commit()
        return adc

    # ----------- UI9 父子 substance 血缘（V1.2 评审 UI9:B）-----------
    async def get_lineage(self, code: str) -> dict:
        """返回当前 substance 的父/子 substance 血缘（ADC 关系树）

        - parents: 当前 ADC 的 antibody / linker / payload 父物质（仅 ADC 类型时有）
        - children: 反向 — 哪些 ADC 把当前 substance 当 antibody/linker/payload
        """
        from app.domains.srs.models import SubstanceADC

        sub = await self._get_substance_or_404(code)

        def _to_brief(s: Substance) -> dict:
            return {
                "substance_code": s.substance_code,
                "preferred_name": s.preferred_name,
                "substance_type": s.substance_type,
                "status": s.status,
            }

        parents: dict[str, dict | None] = {"antibody": None, "linker": None, "payload": None}
        if sub.substance_type == "adc":
            adc_result = await self.db.execute(
                select(SubstanceADC).where(SubstanceADC.substance_id == sub.substance_id)
            )
            adc = adc_result.scalar_one_or_none()
            if adc:
                for role, sid in [
                    ("antibody", adc.antibody_substance_id),
                    ("linker", adc.linker_substance_id),
                    ("payload", adc.payload_substance_id),
                ]:
                    if sid is None:
                        continue
                    r = await self.db.execute(
                        select(Substance).where(Substance.substance_id == sid)
                    )
                    parent = r.scalar_one_or_none()
                    if parent:
                        parents[role] = _to_brief(parent)

        # 子方向：哪些 ADC 引用了当前 substance
        children_result = await self.db.execute(
            select(SubstanceADC, Substance)
            .join(Substance, Substance.substance_id == SubstanceADC.substance_id)
            .where(
                (SubstanceADC.antibody_substance_id == sub.substance_id)
                | (SubstanceADC.linker_substance_id == sub.substance_id)
                | (SubstanceADC.payload_substance_id == sub.substance_id),
                Substance.deleted_at.is_(None),
            )
        )
        children = []
        for adc, child in children_result.all():
            role = (
                "antibody" if adc.antibody_substance_id == sub.substance_id
                else "linker" if adc.linker_substance_id == sub.substance_id
                else "payload"
            )
            children.append({**_to_brief(child), "as_role": role})

        return {
            "self_type": sub.substance_type,
            "parents": parents,
            "children": children,
        }

    # ----------- 软删除 -----------
    async def soft_delete(self, code: str, current_user: User, reason: str | None = None):
        if reason:
            await self.db.execute(
                text("SELECT set_config('app.change_reason', :r, true)"),
                {"r": reason},
            )
        result = await self.db.execute(
            select(Substance).where(
                Substance.substance_code == code,
                Substance.deleted_at.is_(None),
            )
        )
        sub = result.scalar_one_or_none()
        if not sub:
            raise SubstanceNotFoundError()
        sub.deleted_at = datetime.now(UTC)
        sub.deleted_by = current_user.user_id
        # audit.fn_audit_trigger 会检测 deleted_at 由 NULL → NOT NULL 并把 action 写为 'DELETE'
        await self.db.flush()

    # ----------- 状态机 -----------
    async def change_status(
        self,
        code: str,
        action: str,
        comment: str,
        current_user: User,
        signature: "SignatureBlock | None" = None,
    ) -> "StateChangeResponse":
        """状态机入口（API-MDM-001 V1.1 §6.5）

        - comment: 业务变更原因（写入 audit_log.reason + substance_status_history.change_reason）
        - signature: GxP 关键动作必传（password + meaning + reason）；service 据此校验

        返回 StateChangeResponse（V1.1 §6.5 行 1140-1155）。
        """
        from app.domains.audit.schemas import SignatureBlock, StateChangeResponse  # 局部导入避免循环

        transitions = STATE_MACHINE.get(action)
        if not transitions:
            raise StateInvalidError(f"未知动作: {action}")

        # GxP 关键动作必须电子签名
        requires_sig = action in SIGNATURE_REQUIRED_ACTIONS
        if requires_sig and signature is None:
            raise SignatureRequiredError(
                f"动作 '{action}' 为 GxP 关键转移，必须提供 signature 对象进行电子签名"
            )

        result = await self.db.execute(
            select(Substance)
            .where(
                Substance.substance_code == code,
                Substance.deleted_at.is_(None),
            )
            # H-12：行锁防 check-then-act 竞态（并发状态变更串行化，后到者按新状态校验）
            .with_for_update()
        )
        sub = result.scalar_one_or_none()
        if not sub:
            raise SubstanceNotFoundError()

        old_status = sub.status
        next_status = transitions.get(old_status)
        if not next_status:
            raise StateInvalidError(
                f"当前状态 '{old_status}' 不能执行 '{action}'（允许的起始状态：{list(transitions)}）"
            )

        # 写入 change_reason GUC — 仅 audit.fn_audit_trigger 仍读（写入 audit_log.reason）
        # srs.fn_substance_status_change 已不读 GUC（migration 0028），改为 service 后置 UPDATE
        await self.db.execute(
            text("SELECT set_config('app.change_reason', :r, true)"),
            {"r": comment},
        )

        # 电子签名：验证密码、写 e_signature
        sig = None
        if signature is not None:
            sig_service = ESignatureService(self.db)
            sig = await sig_service.sign(
                user=current_user,
                password=signature.password,
                entity_schema="srs",
                entity_table="substance",
                entity_id=sub.substance_id,
                entity_code=sub.substance_code,
                meaning=signature.meaning or ACTION_TO_MEANING[action],
                reason=signature.reason,
                content_for_hash={
                    "substance_code": sub.substance_code,
                    "internal_code": sub.internal_code,
                    "preferred_name": sub.preferred_name,
                    "current_status": old_status,
                    "target_status": next_status,
                    "version": sub.version,
                    "comment": comment,
                    "signature_reason": signature.reason,
                },
            )

        sub.status = next_status
        sub.updated_by = current_user.user_id

        # approve 同时记录注册时间/人
        if action == "approve":
            sub.registered_at = datetime.now(UTC)
            sub.registered_by = current_user.user_id

        await self.db.flush()
        # 触发器写入 substance_status_history（change_reason='status changed', e_signature_id=NULL）
        # service 显式回填实际 change_reason 与 e_signature_id
        await self.db.execute(
            text(
                """
                UPDATE srs.substance_status_history
                   SET change_reason  = :reason,
                       e_signature_id = :sid
                 WHERE history_id = (
                     SELECT MAX(history_id)
                       FROM srs.substance_status_history
                      WHERE substance_id = :sub_id
                 )
                """
            ),
            {
                "reason": comment,
                "sid": sig.signature_id if sig is not None else None,
                "sub_id": sub.substance_id,
            },
        )
        await self.db.refresh(sub, ["version", "updated_at"])
        await self.db.commit()
        return StateChangeResponse(
            substance_code=sub.substance_code,
            old_status=old_status,
            new_status=sub.status,
            signature_id=sig.signature_id if sig is not None else None,
            registered_at=sub.registered_at if action == "approve" else None,
            registered_by=sub.registered_by if action == "approve" else None,
            version=sub.version,
        )

    # ----------- xrefs 子资源 -----------
    async def _get_substance_or_404(self, code: str) -> Substance:
        result = await self.db.execute(
            select(Substance).where(
                Substance.substance_code == code,
                Substance.deleted_at.is_(None),
            )
        )
        sub = result.scalar_one_or_none()
        if not sub:
            raise SubstanceNotFoundError()
        return sub

    async def add_xref(
        self, code: str, payload: SubstanceXrefCreate, current_user: User
    ) -> SubstanceXrefSchema:
        sub = await self._get_substance_or_404(code)
        xref = SubstanceXref(
            substance_id=sub.substance_id,
            xref_type=payload.xref_type,
            xref_value=payload.xref_value,
            xref_source=payload.xref_source,
            region=payload.region,
            is_primary=payload.is_primary,
            effective_date=payload.effective_date,
            expiry_date=payload.expiry_date,
            notes=payload.notes,
            created_by=current_user.user_id,
            updated_by=current_user.user_id,
        )
        self.db.add(xref)
        await self.db.flush()
        return SubstanceXrefSchema.model_validate(xref)

    async def update_xref(
        self, code: str, xref_id: int, payload: SubstanceXrefUpdate, current_user: User
    ) -> SubstanceXrefSchema:
        sub = await self._get_substance_or_404(code)
        result = await self.db.execute(
            select(SubstanceXref).where(
                SubstanceXref.xref_id == xref_id,
                SubstanceXref.substance_id == sub.substance_id,
                SubstanceXref.deleted_at.is_(None),
            )
        )
        xref = result.scalar_one_or_none()
        if not xref:
            raise XrefNotFoundError(f"xref_id={xref_id} 不属于 {code} 或已删除")

        data = payload.model_dump(exclude_unset=True)
        for k, v in data.items():
            setattr(xref, k, v)
        xref.updated_by = current_user.user_id
        await self.db.flush()
        return SubstanceXrefSchema.model_validate(xref)

    # ----------- 同一性判定 -----------
    async def check_sameness(self, payload: CheckSamenessRequest) -> CheckSamenessResponse:
        """精确匹配版同一性判定：序列 SHA-256 + internal_code

        命中策略：
          - HC 哈希一致 OR LC 哈希一致 → 候选
          - internal_code 精确一致 → 候选
        候选 confidence：
          - HC + LC 都中：1.0
          - HC 或 LC 单独中：0.85（高度疑似，序列相同但另一条链未知/不同）
          - 只 internal_code 中：0.6（编码冲突，序列差异，需人工核查）
        """
        hc_hash = _hash_sequence(payload.heavy_chain_sequence)
        lc_hash = _hash_sequence(payload.light_chain_sequence)
        ic = payload.internal_code.strip() if payload.internal_code else None

        if not (hc_hash or lc_hash or ic):
            return CheckSamenessResponse(matches=[], input_summary={
                "heavy_chain_hash": None,
                "light_chain_hash": None,
                "internal_code": None,
            })

        # 序列哈希候选：JOIN substance_protein
        seq_match_subs: dict[int, set[str]] = {}  # substance_id → matched fields
        if hc_hash or lc_hash:
            conditions = []
            if hc_hash:
                conditions.append(SubstanceProtein.sequence_hash_hc == hc_hash)
            if lc_hash:
                conditions.append(SubstanceProtein.sequence_hash_lc == lc_hash)
            from sqlalchemy import or_

            seq_result = await self.db.execute(
                select(
                    SubstanceProtein.substance_id,
                    SubstanceProtein.sequence_hash_hc,
                    SubstanceProtein.sequence_hash_lc,
                ).where(or_(*conditions))
            )
            for sub_id, db_hc, db_lc in seq_result.all():
                fields = seq_match_subs.setdefault(sub_id, set())
                if hc_hash and db_hc == hc_hash:
                    fields.add("heavy_chain_sequence")
                if lc_hash and db_lc == lc_hash:
                    fields.add("light_chain_sequence")

        # internal_code 候选
        ic_match_sub_id: int | None = None
        if ic:
            ic_result = await self.db.execute(
                select(Substance.substance_id).where(
                    Substance.internal_code == ic,
                    Substance.deleted_at.is_(None),
                )
            )
            ic_match_sub_id = ic_result.scalar_one_or_none()
            if ic_match_sub_id is not None:
                seq_match_subs.setdefault(ic_match_sub_id, set()).add("internal_code")

        if not seq_match_subs:
            return CheckSamenessResponse(matches=[], input_summary={
                "heavy_chain_hash": hc_hash,
                "light_chain_hash": lc_hash,
                "internal_code": ic,
            })

        # 取这些 substance 的展示字段
        sub_result = await self.db.execute(
            select(Substance).where(
                Substance.substance_id.in_(list(seq_match_subs.keys())),
                Substance.deleted_at.is_(None),
            )
        )
        matches: list[SamenessMatch] = []
        for sub in sub_result.scalars():
            fields = seq_match_subs.get(sub.substance_id, set())
            has_hc = "heavy_chain_sequence" in fields
            has_lc = "light_chain_sequence" in fields
            has_ic = "internal_code" in fields

            if has_hc and has_lc:
                confidence = 1.0
            elif has_hc or has_lc:
                confidence = 0.85
            elif has_ic:
                confidence = 0.6
            else:
                confidence = 0.0

            matches.append(
                SamenessMatch(
                    substance_code=sub.substance_code,
                    preferred_name=sub.preferred_name,
                    status=sub.status,
                    substance_type=sub.substance_type,
                    matched_fields=sorted(fields),
                    confidence=confidence,
                )
            )
        matches.sort(key=lambda m: -m.confidence)

        return CheckSamenessResponse(
            matches=matches,
            input_summary={
                "heavy_chain_hash": hc_hash,
                "light_chain_hash": lc_hash,
                "internal_code": ic,
            },
        )

    # ----------- 状态历史查询 -----------
    async def get_status_history(self, code: str) -> list[StatusHistoryItem]:
        sub = await self._get_substance_or_404(code)
        result = await self.db.execute(
            select(SubstanceStatusHistory)
            .where(SubstanceStatusHistory.substance_id == sub.substance_id)
            .order_by(SubstanceStatusHistory.changed_at.desc())
        )
        return [StatusHistoryItem.model_validate(h) for h in result.scalars()]

    async def delete_xref(self, code: str, xref_id: int, current_user: User) -> None:
        sub = await self._get_substance_or_404(code)
        result = await self.db.execute(
            select(SubstanceXref).where(
                SubstanceXref.xref_id == xref_id,
                SubstanceXref.substance_id == sub.substance_id,
                SubstanceXref.deleted_at.is_(None),
            )
        )
        xref = result.scalar_one_or_none()
        if not xref:
            raise XrefNotFoundError(f"xref_id={xref_id} 不属于 {code} 或已删除")
        xref.deleted_at = datetime.now(UTC)
        xref.deleted_by = current_user.user_id
        await self.db.flush()
