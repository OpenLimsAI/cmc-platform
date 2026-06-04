"""EQP 业务服务层

设备主数据 CRUD（无状态机、无版本号、无电子签名 — 对标 mm 域）。
"""
from datetime import UTC, datetime

from sqlalchemy import func, or_, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import DuplicateCodeError, NotFoundError
from app.domains.auth.models import User
from app.domains.eqp.models import Equipment
from app.domains.eqp.schemas import (
    EquipmentBrief,
    EquipmentCreate,
    EquipmentDetail,
    EquipmentFilter,
    EquipmentUpdate,
)


class EquipmentService:
    def __init__(self, db: AsyncSession):
        self.db = db

    # ----------- 列表 -----------
    async def list_equipments(
        self,
        filter: EquipmentFilter,
        page: int,
        page_size: int,
        sort: str | None = None,
    ) -> tuple[list[EquipmentBrief], int]:
        stmt = select(Equipment).where(Equipment.deleted_at.is_(None))

        if filter.q:
            # 多关键词（空白分割）：token 内 OR 多字段，token 间 AND
            tokens = [t for t in filter.q.split() if t]
            for tok in tokens:
                kw = f"%{tok}%"
                stmt = stmt.where(
                    or_(
                        Equipment.equipment_code.ilike(kw),
                        Equipment.equipment_name.ilike(kw),
                        Equipment.equipment_name_en.ilike(kw),
                        Equipment.model.ilike(kw),
                        Equipment.manufacturer.ilike(kw),
                        Equipment.serial_no.ilike(kw),
                    )
                )
        if filter.category:
            categories = [c.strip() for c in filter.category.split(",")]
            stmt = stmt.where(Equipment.category.in_(categories))
        if filter.status:
            statuses = [s.strip() for s in filter.status.split(",")]
            stmt = stmt.where(Equipment.status.in_(statuses))
        if filter.manufacturer:
            stmt = stmt.where(Equipment.manufacturer.ilike(f"%{filter.manufacturer}%"))

        count_stmt = select(func.count()).select_from(stmt.subquery())
        total = (await self.db.execute(count_stmt)).scalar_one()

        if sort:
            for field in sort.split(","):
                f = field.strip()
                desc = f.startswith("-")
                fname = f.lstrip("-+")
                col = getattr(Equipment, fname, None)
                if col is not None:
                    stmt = stmt.order_by(col.desc() if desc else col.asc())
        else:
            stmt = stmt.order_by(Equipment.updated_at.desc())

        stmt = stmt.offset((page - 1) * page_size).limit(page_size)
        result = await self.db.execute(stmt)
        equipments = list(result.scalars().all())

        return [EquipmentBrief.model_validate(e) for e in equipments], total

    # ----------- 详情 -----------
    async def _get_equipment_or_404(self, code: str) -> Equipment:
        result = await self.db.execute(
            select(Equipment).where(
                Equipment.equipment_code == code,
                Equipment.deleted_at.is_(None),
            )
        )
        equipment = result.scalar_one_or_none()
        if not equipment:
            raise NotFoundError(f"未找到 equipment: {code}")
        return equipment

    async def get_by_code(self, code: str) -> EquipmentDetail:
        equipment = await self._get_equipment_or_404(code)
        return EquipmentDetail.model_validate(equipment)

    # ----------- 创建 -----------
    async def create(self, payload: EquipmentCreate, current_user: User) -> EquipmentDetail:
        if payload.equipment_code:
            existing = await self.db.execute(
                select(Equipment.equipment_id).where(
                    Equipment.equipment_code == payload.equipment_code,
                )
            )
            if existing.scalar_one_or_none() is not None:
                raise DuplicateCodeError(
                    f"设备编码 '{payload.equipment_code}' 已存在（含已删除记录），请更换编码"
                )

        equipment = Equipment(
            # 留空时传 None,由 eqp.fn_equipment_assign_code 触发器分配
            equipment_code=payload.equipment_code or None,
            equipment_name=payload.equipment_name,
            equipment_name_en=payload.equipment_name_en,
            category=payload.category,
            model=payload.model,
            manufacturer=payload.manufacturer,
            serial_no=payload.serial_no,
            purchase_date=payload.purchase_date,
            asset_value=payload.asset_value,
            supplier=payload.supplier,
            status="active",
            description=payload.description,
            notes=payload.notes,
            extra=payload.extra,
            created_by=current_user.user_id,
            updated_by=current_user.user_id,
        )
        self.db.add(equipment)
        await self.db.flush()
        await self.db.refresh(equipment)
        return EquipmentDetail.model_validate(equipment)

    # ----------- 更新 -----------
    async def update(
        self, code: str, payload: EquipmentUpdate, current_user: User
    ) -> EquipmentDetail:
        if payload.change_reason:
            await self.db.execute(
                text("SELECT set_config('app.change_reason', :r, true)"),
                {"r": payload.change_reason},
            )

        equipment = await self._get_equipment_or_404(code)

        update_data = payload.model_dump(exclude_unset=True, exclude={"change_reason"})
        for k, v in update_data.items():
            setattr(equipment, k, v)
        equipment.updated_by = current_user.user_id
        # updated_at 由 eqp.fn_equipment_before_update 触发器维护

        await self.db.flush()
        await self.db.refresh(equipment, ["updated_at"])
        return EquipmentDetail.model_validate(equipment)

    # ----------- 软删除 -----------
    async def soft_delete(self, code: str, current_user: User, reason: str) -> None:
        await self.db.execute(
            text("SELECT set_config('app.change_reason', :r, true)"),
            {"r": reason},
        )
        equipment = await self._get_equipment_or_404(code)
        equipment.deleted_at = datetime.now(UTC)
        equipment.deleted_by = current_user.user_id
        equipment.updated_by = current_user.user_id
        await self.db.flush()
