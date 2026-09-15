"""EQP 业务服务层

设备主数据 CRUD（主数据状态与设备状态分离；设备状态由 MDM 设备专员维护）。
"""
from datetime import UTC, datetime

from sqlalchemy import func, or_, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import InvalidValueError, NotFoundError
from app.domains.auth.models import User
from app.domains.eqp.models import Equipment
from app.domains.eqp.schemas import (
    EquipmentBrief,
    EquipmentCreate,
    EquipmentDetail,
    EquipmentFilter,
    EquipmentUpdate,
    allowed_criticalities,
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
                        Equipment.equipment_no.ilike(kw),
                        Equipment.fixed_asset_no.ilike(kw),
                        Equipment.equipment_name.ilike(kw),
                        Equipment.equipment_name_en.ilike(kw),
                        Equipment.alias.ilike(kw),  # 0059：按旧称也能搜到
                        Equipment.model.ilike(kw),
                        Equipment.manufacturer.ilike(kw),
                        Equipment.serial_no.ilike(kw),
                        Equipment.department.ilike(kw),
                        Equipment.site.ilike(kw),
                        Equipment.room.ilike(kw),
                    )
                )
        if filter.category:
            categories = [c.strip() for c in filter.category.split(",")]
            stmt = stmt.where(Equipment.category.in_(categories))
        if filter.status:
            statuses = [s.strip() for s in filter.status.split(",")]
            stmt = stmt.where(Equipment.status.in_(statuses))
        if filter.equipment_status:
            equipment_statuses = [s.strip() for s in filter.equipment_status.split(",")]
            stmt = stmt.where(Equipment.equipment_status.in_(equipment_statuses))
        if filter.manufacturer:
            stmt = stmt.where(Equipment.manufacturer.ilike(f"%{filter.manufacturer}%"))
        if filter.department:
            depts = [d.strip() for d in filter.department.split(",")]
            stmt = stmt.where(Equipment.department.in_(depts))
        if filter.site:
            sites = [x.strip() for x in filter.site.split(",")]
            stmt = stmt.where(Equipment.site.in_(sites))
        if filter.criticality:
            crits = [c.strip() for c in filter.criticality.split(",")]
            stmt = stmt.where(Equipment.criticality.in_(crits))

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
        equipment = Equipment(
            # 设备ID 一律留空 → 由 eqp.fn_equipment_assign_code 触发器生成 EQP-yyyy-NNNNNN
            equipment_code=None,
            equipment_no=payload.equipment_no,
            fixed_asset_no=payload.fixed_asset_no,
            equipment_name=payload.equipment_name,
            equipment_name_en=payload.equipment_name_en,
            alias=payload.alias,
            category=payload.category,
            model=payload.model,
            manufacturer=payload.manufacturer,
            serial_no=payload.serial_no,
            rated_power=payload.rated_power,
            origin=payload.origin,
            manufacture_date=payload.manufacture_date,
            asset_value=payload.asset_value,
            supplier=payload.supplier,
            department=payload.department,
            site=payload.site,
            room=payload.room,
            criticality=payload.criticality,
            criticality_basis=payload.criticality_basis,
            commission_date=payload.commission_date,
            status="active",
            equipment_status="enabled",
            has_workstation=payload.has_workstation,
            workstation_info=payload.workstation_info,
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

        # 两类状态变更都必须给出原因，供审计触发器记录。
        master_status_changed = update_data.get("status", equipment.status) != equipment.status
        equipment_status_changed = (
            update_data.get("equipment_status", equipment.equipment_status)
            != equipment.equipment_status
        )
        if (master_status_changed or equipment_status_changed) and len(
            (payload.change_reason or "").strip()
        ) < 5:
            raise InvalidValueError("变更主数据状态或设备状态时必须填写变更原因（至少 5 个字符）")

        # 分级字典跟着分类走：本次改了分类就按新分类判，否则按现有分类判
        new_category = update_data.get("category", equipment.category)
        new_criticality = update_data.get("criticality", equipment.criticality)
        if new_criticality and new_criticality not in allowed_criticalities(new_category):
            allowed = "/".join(allowed_criticalities(new_category))
            raise InvalidValueError(
                f"分类「{new_category}」的设备分级只能是 {allowed}，当前为「{new_criticality}」；"
                "改分类时请一并调整分级"
            )
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
