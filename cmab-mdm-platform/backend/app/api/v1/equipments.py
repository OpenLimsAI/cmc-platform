"""/api/v1/equipments 路由

EQP 设备主数据 CRUD（5 端点）— 对标 materials.py。
下游 CMC LabOps Portal 通过 GET /equipments / GET /equipments/{code} 按需拉取。
"""
from fastapi import APIRouter, Depends, Header, Query, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.responses import Pagination, success
from app.domains.auth.models import User
from app.domains.eqp.schemas import (
    EquipmentCreate,
    EquipmentDelete,
    EquipmentFilter,
    EquipmentUpdate,
)
from app.domains.eqp.services import EquipmentService
from app.shared.idempotency import IdempotencyService
from app.shared.permissions import require_permission

router = APIRouter()


@router.get("", summary="Equipment 列表")
async def list_equipments(
    request: Request,
    q: str | None = None,
    category: str | None = None,
    status: str | None = None,
    equipment_status: str | None = None,
    manufacturer: str | None = None,
    department: str | None = None,
    site: str | None = None,
    criticality: str | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    sort: str | None = None,
    user: User = Depends(require_permission("equipment:read")),
    db: AsyncSession = Depends(get_db),
):
    filter = EquipmentFilter(
        q=q,
        category=category,
        status=status,
        equipment_status=equipment_status,
        manufacturer=manufacturer,
        department=department,
        site=site,
        criticality=criticality,
    )
    service = EquipmentService(db)
    items, total = await service.list_equipments(filter, page, page_size, sort)
    return success(
        data=[i.model_dump(mode="json") for i in items],
        request_id=getattr(request.state, "request_id", None),
        pagination=Pagination.make(page, page_size, total),
    )


@router.post("", status_code=status.HTTP_201_CREATED, summary="创建 Equipment")
async def create_equipment(
    payload: EquipmentCreate,
    request: Request,
    response: Response,
    idempotency_key: str | None = Header(None, alias="Idempotency-Key"),
    user: User = Depends(require_permission("equipment:create")),
    db: AsyncSession = Depends(get_db),
):
    if idempotency_key:
        cached = await IdempotencyService.check(db, user.user_id, idempotency_key, payload.model_dump(mode="json"), "equipments:create")
        if cached:
            if cached.headers.get("Location"):
                response.headers["Location"] = cached.headers["Location"]
            await db.commit()
            return cached.body

    service = EquipmentService(db)
    detail = await service.create(payload, user)
    location = f"/api/v1/equipments/{detail.equipment_code}"
    response.headers["Location"] = location

    body = success(
        data=detail.model_dump(mode="json"),
        message="Equipment 创建成功",
        request_id=getattr(request.state, "request_id", None),
    )
    # H-11：业务与提交结果同事务提交，失败一并撤回
    if idempotency_key:
        await IdempotencyService.save(
            db, user.user_id, idempotency_key, payload.model_dump(mode="json"), "equipments:create",
            status_code=201, response_body=body, location=location,
        )
    await db.commit()
    return body


@router.get("/{code}", summary="Equipment 详情")
async def get_equipment(
    code: str,
    request: Request,
    user: User = Depends(require_permission("equipment:read")),
    db: AsyncSession = Depends(get_db),
):
    service = EquipmentService(db)
    detail = await service.get_by_code(code)
    return success(
        data=detail.model_dump(mode="json"),
        request_id=getattr(request.state, "request_id", None),
    )


@router.put("/{code}", summary="更新 Equipment")
async def update_equipment(
    code: str,
    payload: EquipmentUpdate,
    request: Request,
    user: User = Depends(require_permission("equipment:update")),
    db: AsyncSession = Depends(get_db),
):
    service = EquipmentService(db)
    detail = await service.update(code, payload, user)
    return success(
        data=detail.model_dump(mode="json"),
        message="更新成功",
        request_id=getattr(request.state, "request_id", None),
    )


@router.delete("/{code}", status_code=status.HTTP_204_NO_CONTENT, summary="软删除 Equipment")
async def delete_equipment(
    code: str,
    payload: EquipmentDelete,
    user: User = Depends(require_permission("equipment:update")),
    db: AsyncSession = Depends(get_db),
):
    service = EquipmentService(db)
    await service.soft_delete(code, user, reason=payload.change_reason)
    return None
