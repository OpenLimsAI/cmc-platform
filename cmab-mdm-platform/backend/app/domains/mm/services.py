"""MM 业务服务层

M4.1：mm.material CRUD（无状态机、无版本号、无电子签名）
M4.2：material_batch 子资源
M4.3：substance↔material 跨域反向查询 + obsoleted 物质禁绑业务规则
"""
from datetime import UTC, datetime

from sqlalchemy import func, or_, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import (
    DuplicateCodeError,
    MaterialBatchNumberDuplicateError,
    MaterialNotFoundError,
    NotFoundError,
    OperationNotAllowedError,
    SubstanceNotFoundError,
)
from app.domains.auth.models import User
from app.domains.mm.models import Material, MaterialBatch
from app.domains.mm.schemas import (
    MaterialBatchCreate,
    MaterialBatchSchema,
    MaterialBatchUpdate,
    MaterialBrief,
    MaterialCreate,
    MaterialDetail,
    MaterialFilter,
    MaterialUpdate,
)
from app.domains.srs.models import Substance
from app.shared.master_edit import locked_master


class MaterialService:
    def __init__(self, db: AsyncSession):
        self.db = db

    # ----------- 物质引用解析 -----------
    async def _resolve_substance_ref(
        self,
        substance_id: int | None,
        substance_code: str | None,
    ) -> int | None:
        """优先以 substance_code 解析；如同时给 id，substance_code 覆盖。

        校验：被引用 substance 必须存在且未删除；status='obsoleted' 时禁绑（V1.1 §11.1 业务规则）。
        """
        if substance_code:
            result = await self.db.execute(
                select(Substance).where(
                    Substance.substance_code == substance_code,
                    Substance.deleted_at.is_(None),
                )
            )
            sub = result.scalar_one_or_none()
            if not sub:
                raise SubstanceNotFoundError(f"未找到 substance: {substance_code}")
            if sub.status == "obsoleted":
                raise OperationNotAllowedError(
                    f"substance '{substance_code}' 已处于 obsoleted 状态，不允许新建物料引用"
                )
            return sub.substance_id

        if substance_id is None:
            return None

        result = await self.db.execute(
            select(Substance).where(
                Substance.substance_id == substance_id,
                Substance.deleted_at.is_(None),
            )
        )
        sub = result.scalar_one_or_none()
        if not sub:
            raise SubstanceNotFoundError(f"未找到 substance_id: {substance_id}")
        if sub.status == "obsoleted":
            raise OperationNotAllowedError(
                f"substance_id={substance_id} 已处于 obsoleted 状态，不允许新建物料引用"
            )
        return sub.substance_id

    async def _substance_code(self, substance_id: int | None) -> str | None:
        if substance_id is None:
            return None
        result = await self.db.execute(
            select(Substance.substance_code).where(Substance.substance_id == substance_id)
        )
        return result.scalar_one_or_none()

    # ----------- 列表 -----------
    async def list_materials(
        self,
        filter: MaterialFilter,
        page: int,
        page_size: int,
        sort: str | None = None,
    ) -> tuple[list[MaterialBrief], int]:
        stmt = select(Material).where(Material.deleted_at.is_(None))

        if filter.q:
            # 多关键词（空白分割）：token 内 OR 多字段，token 间 AND
            # 不限大小写（ILIKE）— 编码 / 名称(中英) / 来源 / 生产商 / 货号 / 规格型号
            tokens = [t for t in filter.q.split() if t]
            for tok in tokens:
                kw = f"%{tok}%"
                stmt = stmt.where(
                    or_(
                        Material.material_code.ilike(kw),
                        Material.material_name.ilike(kw),
                        Material.material_name_en.ilike(kw),
                        Material.source_name.ilike(kw),
                        Material.manufacturer.ilike(kw),
                        Material.catalog_no.ilike(kw),
                        Material.spec_model.ilike(kw),
                    )
                )
        if filter.material_type:
            types = [t.strip() for t in filter.material_type.split(",")]
            stmt = stmt.where(Material.material_type.in_(types))
        if filter.status:
            statuses = [s.strip() for s in filter.status.split(",")]
            stmt = stmt.where(Material.status.in_(statuses))
        if filter.grade:
            grades = [g.strip() for g in filter.grade.split(",")]
            stmt = stmt.where(Material.grade.in_(grades))
        if filter.category:
            categories = [c.strip() for c in filter.category.split(",")]
            stmt = stmt.where(Material.category.in_(categories))
        if filter.source_type:
            stmt = stmt.where(Material.source_type == filter.source_type)
        if filter.substance_code:
            sub_result = await self.db.execute(
                select(Substance.substance_id).where(
                    Substance.substance_code == filter.substance_code
                )
            )
            sub_id = sub_result.scalar_one_or_none()
            if sub_id is None:
                # 引用了不存在的 substance_code 直接返回空列表
                return [], 0
            stmt = stmt.where(Material.substance_id == sub_id)

        count_stmt = select(func.count()).select_from(stmt.subquery())
        total = (await self.db.execute(count_stmt)).scalar_one()

        if sort:
            for field in sort.split(","):
                f = field.strip()
                desc = f.startswith("-")
                fname = f.lstrip("-+")
                col = getattr(Material, fname, None)
                if col is not None:
                    stmt = stmt.order_by(col.desc() if desc else col.asc())
        else:
            stmt = stmt.order_by(Material.updated_at.desc())

        stmt = stmt.offset((page - 1) * page_size).limit(page_size)
        result = await self.db.execute(stmt)
        materials = list(result.scalars().all())

        # 批量解析 substance_code（避免 N+1）
        sub_ids = {m.substance_id for m in materials if m.substance_id is not None}
        sub_code_map: dict[int, str] = {}
        if sub_ids:
            sub_rows = await self.db.execute(
                select(Substance.substance_id, Substance.substance_code).where(
                    Substance.substance_id.in_(sub_ids)
                )
            )
            sub_code_map = {sid: scode for sid, scode in sub_rows}

        return (
            [
                MaterialBrief(
                    version=m.version,
                    material_code=m.material_code,
                    material_name=m.material_name,
                    material_name_en=m.material_name_en,
                    material_type=m.material_type,
                    category=m.category,
                    grade=m.grade,
                    status=m.status,
                    unit=m.unit,
                    manufacturer=m.manufacturer,
                    spec_model=m.spec_model,
                    physical_form=m.physical_form,
                    source_name=m.source_name,
                    substance_id=m.substance_id,
                    substance_code=sub_code_map.get(m.substance_id) if m.substance_id else None,
                    created_at=m.created_at,
                    updated_at=m.updated_at,
                )
                for m in materials
            ],
            total,
        )

    # ----------- 详情 -----------
    async def _get_material_or_404(self, code: str, *, for_update: bool = False) -> Material:
        stmt = select(Material).where(
            Material.material_code == code, Material.deleted_at.is_(None),
        )
        if for_update:
            stmt = stmt.with_for_update(of=Material).execution_options(populate_existing=True)
        result = await self.db.execute(stmt)
        material = result.scalar_one_or_none()
        if not material:
            raise MaterialNotFoundError(f"未找到 material: {code}")
        return material

    async def get_by_code(self, code: str) -> MaterialDetail:
        material = await self._get_material_or_404(code)
        sub_code = await self._substance_code(material.substance_id)
        detail = MaterialDetail.model_validate(material)
        detail.substance_code = sub_code
        return detail

    # ----------- 创建 -----------
    async def create(self, payload: MaterialCreate, current_user: User) -> MaterialDetail:
        resolved_sub_id = await self._resolve_substance_ref(
            payload.substance_id, payload.substance_code,
        )

        existing = await self.db.execute(
            select(Material.material_id).where(
                Material.material_code == payload.material_code,
            )
        )
        if existing.scalar_one_or_none() is not None:
            raise DuplicateCodeError(
                f"物料编码 '{payload.material_code}' 已存在（含已删除记录），请更换编码"
            )

        material = Material(
            material_code=payload.material_code,
            material_name=payload.material_name,
            material_name_en=payload.material_name_en,
            material_type=payload.material_type,
            category=payload.category,
            substance_id=resolved_sub_id,
            manufacturer=payload.manufacturer,
            catalog_no=payload.catalog_no,
            spec_model=payload.spec_model,
            unit=payload.unit,
            package_spec=payload.package_spec,
            hazard_class=payload.hazard_class,
            physical_form=payload.physical_form,
            storage_condition=payload.storage_condition,
            source_type=payload.source_type,
            source_name=payload.source_name,
            grade=payload.grade,
            status="active",
            description=payload.description,
            notes=payload.notes,
            extra=payload.extra,
            created_by=current_user.user_id,
            updated_by=current_user.user_id,
        )
        self.db.add(material)
        await self.db.flush()
        await self.db.refresh(material)

        sub_code = await self._substance_code(material.substance_id)
        detail = MaterialDetail.model_validate(material)
        detail.substance_code = sub_code
        return detail

    # ----------- 更新 -----------
    async def update(
        self, code: str, payload: MaterialUpdate, current_user: User
    ) -> MaterialDetail:
        if payload.change_reason:
            await self.db.execute(
                text("SELECT set_config('app.change_reason', :r, true)"),
                {"r": payload.change_reason},
            )

        material = await locked_master(self.db, Material, "material_code", code, payload.version)

        update_data = payload.model_dump(
            exclude_unset=True,
            exclude={"version", "change_reason", "substance_code"},
        )

        # 物质引用解析（substance_code 优先；只有显式传一边才动 substance_id）
        sub_provided = "substance_id" in update_data or payload.substance_code is not None
        if sub_provided:
            resolved_sub_id = await self._resolve_substance_ref(
                update_data.get("substance_id", material.substance_id),
                payload.substance_code,
            )
            update_data["substance_id"] = resolved_sub_id

        for k, v in update_data.items():
            setattr(material, k, v)
        material.updated_by = current_user.user_id
        # updated_at 由 mm.fn_material_before_update 触发器维护

        await self.db.flush()
        await self.db.refresh(material, ["updated_at", "version"])

        sub_code = await self._substance_code(material.substance_id)
        detail = MaterialDetail.model_validate(material)
        detail.substance_code = sub_code
        await self.db.commit()
        return detail

    # ----------- 软删除 -----------
    async def soft_delete(self, code: str, current_user: User, reason: str) -> None:
        await self.db.execute(
            text("SELECT set_config('app.change_reason', :r, true)"),
            {"r": reason},
        )
        material = await self._get_material_or_404(code)
        material.deleted_at = datetime.now(UTC)
        material.deleted_by = current_user.user_id
        material.updated_by = current_user.user_id
        await self.db.flush()

    # ============== substance 反向查询（M4.3）==============
    async def list_for_substance(
        self, substance_code: str, include_deleted: bool = False
    ) -> list[MaterialBrief]:
        """查询某 substance 下所有 material（material.substance_id 直接 FK，无 ref 中间表）"""
        sub_result = await self.db.execute(
            select(Substance.substance_id).where(
                Substance.substance_code == substance_code,
                Substance.deleted_at.is_(None),
            )
        )
        sub_id = sub_result.scalar_one_or_none()
        if sub_id is None:
            raise SubstanceNotFoundError(f"未找到 substance: {substance_code}")

        stmt = select(Material).where(Material.substance_id == sub_id)
        if not include_deleted:
            stmt = stmt.where(Material.deleted_at.is_(None))
        stmt = stmt.order_by(Material.updated_at.desc())

        result = await self.db.execute(stmt)
        materials = list(result.scalars())
        return [
            MaterialBrief(
                version=m.version,
                material_code=m.material_code,
                material_name=m.material_name,
                material_name_en=m.material_name_en,
                material_type=m.material_type,
                category=m.category,
                grade=m.grade,
                status=m.status,
                unit=m.unit,
                manufacturer=m.manufacturer,
                spec_model=m.spec_model,
                physical_form=m.physical_form,
                source_name=m.source_name,
                substance_id=m.substance_id,
                substance_code=substance_code,
                created_at=m.created_at,
                updated_at=m.updated_at,
            )
            for m in materials
        ]

    # ============== material_batch 子资源（§10.2）==============
    async def list_batches(self, code: str) -> list[MaterialBatchSchema]:
        material = await self._get_material_or_404(code)
        result = await self.db.execute(
            select(MaterialBatch)
            .where(
                MaterialBatch.material_id == material.material_id,
                MaterialBatch.deleted_at.is_(None),
            )
            .order_by(MaterialBatch.receive_date.desc().nullslast(), MaterialBatch.batch_id.asc())
        )
        return [MaterialBatchSchema.model_validate(b) for b in result.scalars()]

    async def add_batch(
        self, code: str, payload: MaterialBatchCreate, current_user: User
    ) -> MaterialBatchSchema:
        # 同物料的批次写操作共用父行锁，避免两个查重同时通过。
        material = await self._get_material_or_404(code, for_update=True)
        # 唯一性只约束未软删除批次；历史同号记录保留。
        existing = await self.db.execute(
            select(MaterialBatch.batch_id).where(
                MaterialBatch.material_id == material.material_id,
                MaterialBatch.batch_number == payload.batch_number,
                MaterialBatch.deleted_at.is_(None),
            )
        )
        if existing.scalar_one_or_none():
            raise MaterialBatchNumberDuplicateError(
                f"物料 {code} 下已存在批号: {payload.batch_number}"
            )

        batch = MaterialBatch(
            material_id=material.material_id,
            batch_number=payload.batch_number,
            quantity_value=payload.quantity_value,
            quantity_unit=payload.quantity_unit,
            manufacture_date=payload.manufacture_date,
            expiry_date=payload.expiry_date,
            receive_date=payload.receive_date,
            source_batch_ref=payload.source_batch_ref,
            coa_url=payload.coa_url,
            storage_location=payload.storage_location,
            notes=payload.notes,
            extra=payload.extra,
            created_by=current_user.user_id,
            updated_by=current_user.user_id,
        )
        self.db.add(batch)
        await self.db.flush()
        await self.db.refresh(batch)
        await self.db.commit()
        return MaterialBatchSchema.model_validate(batch)

    async def update_batch(
        self,
        code: str,
        batch_id: int,
        payload: MaterialBatchUpdate,
        current_user: User,
    ) -> MaterialBatchSchema:
        if payload.change_reason:
            await self.db.execute(
                text("SELECT set_config('app.change_reason', :r, true)"),
                {"r": payload.change_reason},
            )
        material = await self._get_material_or_404(code, for_update=True)
        result = await self.db.execute(
            select(MaterialBatch).where(
                MaterialBatch.batch_id == batch_id,
                MaterialBatch.material_id == material.material_id,
                MaterialBatch.deleted_at.is_(None),
            )
        )
        batch = result.scalar_one_or_none()
        if not batch:
            raise NotFoundError(f"batch_id={batch_id} 不属于 {code} 或已删除")

        data = payload.model_dump(exclude_unset=True, exclude={"change_reason"})

        # 若改 batch_number，需重检 UNIQUE
        new_bnum = data.get("batch_number")
        if new_bnum and new_bnum != batch.batch_number:
            dup = await self.db.execute(
                select(MaterialBatch.batch_id).where(
                    MaterialBatch.material_id == material.material_id,
                    MaterialBatch.batch_number == new_bnum,
                    MaterialBatch.batch_id != batch_id,
                    MaterialBatch.deleted_at.is_(None),
                )
            )
            if dup.scalar_one_or_none():
                raise MaterialBatchNumberDuplicateError(
                    f"物料 {code} 下已存在批号: {new_bnum}"
                )

        for k, v in data.items():
            setattr(batch, k, v)
        batch.updated_by = current_user.user_id
        await self.db.flush()
        await self.db.refresh(batch, ["updated_at"])
        await self.db.commit()
        return MaterialBatchSchema.model_validate(batch)

    async def delete_batch(
        self, code: str, batch_id: int, current_user: User, reason: str
    ) -> None:
        await self.db.execute(
            text("SELECT set_config('app.change_reason', :r, true)"),
            {"r": reason},
        )
        material = await self._get_material_or_404(code, for_update=True)
        result = await self.db.execute(
            select(MaterialBatch).where(
                MaterialBatch.batch_id == batch_id,
                MaterialBatch.material_id == material.material_id,
                MaterialBatch.deleted_at.is_(None),
            )
        )
        batch = result.scalar_one_or_none()
        if not batch:
            raise NotFoundError(f"batch_id={batch_id} 不属于 {code} 或已删除")
        batch.deleted_at = datetime.now(UTC)
        batch.deleted_by = current_user.user_id
        batch.updated_by = current_user.user_id
        await self.db.flush()
        await self.db.commit()
