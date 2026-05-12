"""
ARS 业务服务层

M3.1：CRUD
M3.2：状态机 + market-id 子资源 + 电子签名
M3.3 起：ref.asset_substance / ref.project_asset 跨域绑定
"""
from datetime import UTC, datetime

from sqlalchemy import func, or_, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import (
    AssetNotFoundError,
    ConflictError,
    DuplicateCodeError,
    NotFoundError,
    SignatureRequiredError,
    StateInvalidError,
    VersionConflictError,
)
from app.domains.ars.models import Asset, AssetMarketId
from app.domains.ars.schemas import (
    AssetBrief,
    AssetCreate,
    AssetDetail,
    AssetFilter,
    AssetMarketIdCreate,
    AssetMarketIdSchema,
    AssetMarketIdUpdate,
    AssetUpdate,
)
from app.domains.audit.schemas import StatusHistoryItem
from app.domains.audit.signature_service import ESignatureService
from app.domains.auth.models import User


# 状态机：action → {当前状态: 下一状态}
# DM-MDM-001 §8.2 status ∈ {active, on_hold, terminated}（3 值）
STATE_MACHINE: dict[str, dict[str, str]] = {
    "hold":      {"active": "on_hold"},
    "resume":    {"on_hold": "active"},
    "terminate": {"active": "terminated", "on_hold": "terminated"},
}

# GxP 关键动作：terminate 不可逆，要求电子签名（21 CFR Part 11 §11.50/11.70）
SIGNATURE_REQUIRED_ACTIONS: set[str] = {"terminate"}

ACTION_TO_MEANING: dict[str, str] = {
    "hold":      "review",
    "resume":    "review",
    "terminate": "reject",
}


class AssetService:
    def __init__(self, db: AsyncSession):
        self.db = db

    # ----------- 编码生成 -----------
    async def _next_asset_code(self) -> str:
        result = await self.db.execute(text("SELECT meta.fn_next_code('asset')"))
        return result.scalar_one()

    # ----------- 列表 -----------
    async def list_assets(
        self,
        filter: AssetFilter,
        page: int,
        page_size: int,
        sort: str | None = None,
    ) -> tuple[list[AssetBrief], int]:
        stmt = select(Asset).where(Asset.deleted_at.is_(None))

        if filter.q:
            kw = f"%{filter.q}%"
            stmt = stmt.where(
                or_(
                    Asset.asset_code.ilike(kw),
                    Asset.internal_name.ilike(kw),
                    Asset.trade_name.ilike(kw),
                    Asset.inn_name.ilike(kw),
                )
            )
        if filter.asset_type:
            types = [t.strip() for t in filter.asset_type.split(",")]
            stmt = stmt.where(Asset.asset_type.in_(types))
        if filter.current_phase:
            phases = [p.strip() for p in filter.current_phase.split(",")]
            stmt = stmt.where(Asset.current_phase.in_(phases))
        if filter.status:
            statuses = [s.strip() for s in filter.status.split(",")]
            stmt = stmt.where(Asset.status.in_(statuses))
        if filter.therapeutic_area:
            stmt = stmt.where(Asset.therapeutic_area.ilike(f"%{filter.therapeutic_area}%"))
        if filter.is_commercial is not None:
            stmt = stmt.where(Asset.is_commercial == filter.is_commercial)

        count_stmt = select(func.count()).select_from(stmt.subquery())
        total = (await self.db.execute(count_stmt)).scalar_one()

        if sort:
            for field in sort.split(","):
                f = field.strip()
                desc = f.startswith("-")
                fname = f.lstrip("-+")
                col = getattr(Asset, fname, None)
                if col is not None:
                    stmt = stmt.order_by(col.desc() if desc else col.asc())
        else:
            stmt = stmt.order_by(Asset.updated_at.desc())

        stmt = stmt.offset((page - 1) * page_size).limit(page_size)
        result = await self.db.execute(stmt)
        assets = list(result.scalars().all())
        return [AssetBrief.model_validate(a) for a in assets], total

    # ----------- 详情 -----------
    async def _get_asset_or_404(self, code: str) -> Asset:
        result = await self.db.execute(
            select(Asset).where(
                Asset.asset_code == code,
                Asset.deleted_at.is_(None),
            )
        )
        asset = result.scalar_one_or_none()
        if not asset:
            raise AssetNotFoundError(f"未找到 asset: {code}")
        return asset

    async def get_by_code(self, code: str) -> AssetDetail:
        asset = await self._get_asset_or_404(code)
        return AssetDetail.model_validate(asset)

    # ----------- 创建 -----------
    async def create(self, payload: AssetCreate, current_user: User) -> AssetDetail:
        # asset_code 由 BEFORE INSERT 触发器兜底；这里显式取号便于返回
        code = await self._next_asset_code()

        exists = await self.db.execute(
            select(Asset.asset_id).where(Asset.asset_code == code)
        )
        if exists.scalar_one_or_none():
            raise DuplicateCodeError(f"asset_code 冲突: {code}")

        asset = Asset(
            asset_code=code,
            internal_name=payload.internal_name,
            trade_name=payload.trade_name,
            inn_name=payload.inn_name,
            asset_type=payload.asset_type,
            therapeutic_area=payload.therapeutic_area,
            indication=payload.indication,
            dosage_form=payload.dosage_form,
            strength=payload.strength,
            route_of_administration=payload.route_of_administration,
            current_phase=payload.current_phase,
            is_commercial=payload.is_commercial,
            first_approval_date=payload.first_approval_date,
            first_launch_date=payload.first_launch_date,
            description=payload.description,
            notes=payload.notes,
            extra=payload.extra,
            status="active",
            created_by=current_user.user_id,
            updated_by=current_user.user_id,
        )
        self.db.add(asset)
        await self.db.flush()
        await self.db.refresh(asset)
        return AssetDetail.model_validate(asset)

    # ----------- 更新 -----------
    async def update(
        self, code: str, payload: AssetUpdate, current_user: User
    ) -> AssetDetail:
        if payload.change_reason:
            await self.db.execute(
                text("SELECT set_config('app.change_reason', :r, true)"),
                {"r": payload.change_reason},
            )

        asset = await self._get_asset_or_404(code)
        if asset.version != payload.version:
            raise VersionConflictError(
                f"版本号不匹配（服务器: {asset.version}，请求: {payload.version}）"
            )

        update_data = payload.model_dump(
            exclude_unset=True, exclude={"version", "change_reason"}
        )
        for k, v in update_data.items():
            setattr(asset, k, v)
        asset.updated_by = current_user.user_id
        # version / updated_at / phase_change_at 由 ars.fn_asset_before_update 触发器维护

        await self.db.flush()
        await self.db.refresh(asset, ["version", "updated_at", "phase_change_at"])
        return AssetDetail.model_validate(asset)

    # ----------- 软删除 -----------
    async def soft_delete(self, code: str, current_user: User, reason: str) -> None:
        await self.db.execute(
            text("SELECT set_config('app.change_reason', :r, true)"),
            {"r": reason},
        )
        asset = await self._get_asset_or_404(code)
        asset.deleted_at = datetime.now(UTC)
        asset.deleted_by = current_user.user_id
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
        """状态机入口（API-MDM-001 V1.1 §8.x）"""
        from app.domains.audit.schemas import SignatureBlock, StateChangeResponse

        transitions = STATE_MACHINE.get(action)
        if not transitions:
            raise StateInvalidError(f"未知动作: {action}")

        requires_sig = action in SIGNATURE_REQUIRED_ACTIONS
        if requires_sig and signature is None:
            raise SignatureRequiredError(
                f"动作 '{action}' 为 GxP 关键转移，必须提供 signature 对象进行电子签名"
            )

        asset = await self._get_asset_or_404(code)
        old_status = asset.status
        next_status = transitions.get(old_status)
        if not next_status:
            raise StateInvalidError(
                f"当前状态 '{old_status}' 不能执行 '{action}'"
                f"（允许的起始状态：{list(transitions)}）"
            )

        await self.db.execute(
            text("SELECT set_config('app.change_reason', :r, true)"),
            {"r": comment},
        )

        sig = None
        if signature is not None:
            sig_service = ESignatureService(self.db)
            sig = await sig_service.sign(
                user=current_user,
                password=signature.password,
                entity_schema="ars",
                entity_table="asset",
                entity_id=asset.asset_id,
                entity_code=asset.asset_code,
                meaning=signature.meaning or ACTION_TO_MEANING[action],
                reason=signature.reason,
                content_for_hash={
                    "asset_code": asset.asset_code,
                    "internal_name": asset.internal_name,
                    "current_status": old_status,
                    "target_status": next_status,
                    "current_phase": asset.current_phase,
                    "version": asset.version,
                    "comment": comment,
                    "signature_reason": signature.reason,
                },
            )

        asset.status = next_status
        asset.updated_by = current_user.user_id

        await self.db.flush()
        await self.db.execute(
            text(
                """
                UPDATE ars.asset_status_history
                   SET change_reason  = :reason,
                       e_signature_id = :sid
                 WHERE history_id = (
                     SELECT MAX(history_id)
                       FROM ars.asset_status_history
                      WHERE asset_id = :aid
                 )
                """
            ),
            {
                "reason": comment,
                "sid": sig.signature_id if sig is not None else None,
                "aid": asset.asset_id,
            },
        )
        await self.db.refresh(asset, ["version", "updated_at"])
        await self.db.commit()
        return StateChangeResponse(
            asset_code=asset.asset_code,
            old_status=old_status,
            new_status=asset.status,
            signature_id=sig.signature_id if sig is not None else None,
            version=asset.version,
        )

    # ----------- 状态历史 -----------
    async def get_status_history(self, code: str) -> list[StatusHistoryItem]:
        from app.domains.ars.models import AssetStatusHistory
        asset = await self._get_asset_or_404(code)
        result = await self.db.execute(
            select(AssetStatusHistory)
            .where(AssetStatusHistory.asset_id == asset.asset_id)
            .order_by(AssetStatusHistory.changed_at.desc())
        )
        return [StatusHistoryItem.model_validate(h) for h in result.scalars()]

    # ----------- 多市场注册号 -----------
    async def list_market_ids(self, code: str) -> list[AssetMarketIdSchema]:
        asset = await self._get_asset_or_404(code)
        result = await self.db.execute(
            select(AssetMarketId)
            .where(
                AssetMarketId.asset_id == asset.asset_id,
                AssetMarketId.deleted_at.is_(None),
            )
            .order_by(AssetMarketId.market_code.asc(), AssetMarketId.market_id_pk.asc())
        )
        return [AssetMarketIdSchema.model_validate(m) for m in result.scalars()]

    async def add_market_id(
        self, code: str, payload: AssetMarketIdCreate, current_user: User
    ) -> AssetMarketIdSchema:
        asset = await self._get_asset_or_404(code)
        # 预检唯一性 (asset_id, market_code, id_type, id_value)
        existing = await self.db.execute(
            select(AssetMarketId.market_id_pk).where(
                AssetMarketId.asset_id == asset.asset_id,
                AssetMarketId.market_code == payload.market_code,
                AssetMarketId.id_type == payload.id_type,
                AssetMarketId.id_value == payload.id_value,
                AssetMarketId.deleted_at.is_(None),
            )
        )
        if existing.scalar_one_or_none():
            raise ConflictError(
                f"已存在相同的多市场注册号：{payload.market_code}/{payload.id_type}/{payload.id_value}"
            )

        m = AssetMarketId(
            asset_id=asset.asset_id,
            market_code=payload.market_code,
            id_type=payload.id_type,
            id_value=payload.id_value,
            issuing_authority=payload.issuing_authority,
            application_date=payload.application_date,
            approval_date=payload.approval_date,
            expiry_date=payload.expiry_date,
            status=payload.status,
            notes=payload.notes,
            created_by=current_user.user_id,
            updated_by=current_user.user_id,
        )
        self.db.add(m)
        await self.db.flush()
        return AssetMarketIdSchema.model_validate(m)

    async def update_market_id(
        self,
        code: str,
        market_id_pk: int,
        payload: AssetMarketIdUpdate,
        current_user: User,
    ) -> AssetMarketIdSchema:
        if payload.change_reason:
            await self.db.execute(
                text("SELECT set_config('app.change_reason', :r, true)"),
                {"r": payload.change_reason},
            )
        asset = await self._get_asset_or_404(code)
        result = await self.db.execute(
            select(AssetMarketId).where(
                AssetMarketId.market_id_pk == market_id_pk,
                AssetMarketId.asset_id == asset.asset_id,
                AssetMarketId.deleted_at.is_(None),
            )
        )
        m = result.scalar_one_or_none()
        if not m:
            raise NotFoundError(f"market_id_pk={market_id_pk} 不属于 {code} 或已删除")

        data = payload.model_dump(exclude_unset=True, exclude={"change_reason"})
        for k, v in data.items():
            setattr(m, k, v)
        m.updated_by = current_user.user_id
        await self.db.flush()
        return AssetMarketIdSchema.model_validate(m)

    async def delete_market_id(
        self, code: str, market_id_pk: int, current_user: User, reason: str
    ) -> None:
        await self.db.execute(
            text("SELECT set_config('app.change_reason', :r, true)"),
            {"r": reason},
        )
        asset = await self._get_asset_or_404(code)
        result = await self.db.execute(
            select(AssetMarketId).where(
                AssetMarketId.market_id_pk == market_id_pk,
                AssetMarketId.asset_id == asset.asset_id,
                AssetMarketId.deleted_at.is_(None),
            )
        )
        m = result.scalar_one_or_none()
        if not m:
            raise NotFoundError(f"market_id_pk={market_id_pk} 不属于 {code} 或已删除")
        m.deleted_at = datetime.now(UTC)
        m.deleted_by = current_user.user_id
        m.updated_by = current_user.user_id
        await self.db.flush()
