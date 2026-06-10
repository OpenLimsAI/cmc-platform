"""/api/v1/materials 路由

M4.1：mm.material CRUD（5 端点）+ 审计查询
M4.2：material_batch 子资源
M4.3：substance 反向查询（在 substances.py）
"""
from fastapi import APIRouter, Depends, Header, Query, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.responses import Pagination, success
from app.domains.audit.services import AuditService
from app.domains.auth.models import User
from app.domains.mm.schemas import (
    MaterialBatchCreate,
    MaterialBatchDelete,
    MaterialBatchUpdate,
    MaterialCreate,
    MaterialDelete,
    MaterialFilter,
    MaterialUpdate,
)
from app.domains.mm.services import MaterialService
from app.shared.idempotency import IdempotencyService
from app.shared.permissions import require_permission

router = APIRouter()


@router.get("", summary="Material 列表")
async def list_materials(
    request: Request,
    q: str | None = None,
    material_type: str | None = None,
    category: str | None = None,
    status: str | None = None,
    grade: str | None = None,
    substance_code: str | None = None,
    source_type: str | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    sort: str | None = None,
    user: User = Depends(require_permission("material:read")),
    db: AsyncSession = Depends(get_db),
):
    filter = MaterialFilter(
        q=q,
        material_type=material_type,
        category=category,
        status=status,
        grade=grade,
        substance_code=substance_code,
        source_type=source_type,
    )
    service = MaterialService(db)
    items, total = await service.list_materials(filter, page, page_size, sort)
    return success(
        data=[i.model_dump(mode="json") for i in items],
        request_id=getattr(request.state, "request_id", None),
        pagination=Pagination.make(page, page_size, total),
    )


@router.post("", status_code=status.HTTP_201_CREATED, summary="创建 Material")
async def create_material(
    payload: MaterialCreate,
    request: Request,
    response: Response,
    idempotency_key: str | None = Header(None, alias="Idempotency-Key"),
    user: User = Depends(require_permission("material:create")),
    db: AsyncSession = Depends(get_db),
):
    if idempotency_key:
        cached = await IdempotencyService.check(user.user_id, idempotency_key, payload.model_dump())
        if cached:
            if cached.headers.get("Location"):
                response.headers["Location"] = cached.headers["Location"]
            return cached.body

    service = MaterialService(db)
    detail = await service.create(payload, user)
    # API5 / V1.1 §8.2：POST 创建必须设 Location 头
    location = f"/api/v1/materials/{detail.material_code}"
    response.headers["Location"] = location

    body = success(
        data=detail.model_dump(mode="json"),
        message="Material 创建成功",
        request_id=getattr(request.state, "request_id", None),
    )
    # H-11：先显式 commit 再写幂等缓存，避免 commit 失败后 Redis 留下假成功
    await db.commit()
    if idempotency_key:
        await IdempotencyService.save(
            user.user_id, idempotency_key, payload.model_dump(),
            status_code=201, response_body=body, location=location,
        )
    return body


@router.get("/{code}", summary="Material 详情")
async def get_material(
    code: str,
    request: Request,
    user: User = Depends(require_permission("material:read")),
    db: AsyncSession = Depends(get_db),
):
    service = MaterialService(db)
    detail = await service.get_by_code(code)
    return success(
        data=detail.model_dump(mode="json"),
        request_id=getattr(request.state, "request_id", None),
    )


@router.put("/{code}", summary="更新 Material")
async def update_material(
    code: str,
    payload: MaterialUpdate,
    request: Request,
    user: User = Depends(require_permission("material:update")),
    db: AsyncSession = Depends(get_db),
):
    service = MaterialService(db)
    detail = await service.update(code, payload, user)
    return success(
        data=detail.model_dump(mode="json"),
        message="更新成功",
        request_id=getattr(request.state, "request_id", None),
    )


@router.delete("/{code}", status_code=status.HTTP_204_NO_CONTENT, summary="软删除 Material")
async def delete_material(
    code: str,
    payload: MaterialDelete,
    user: User = Depends(require_permission("material:update")),
    db: AsyncSession = Depends(get_db),
):
    service = MaterialService(db)
    await service.soft_delete(code, user, reason=payload.change_reason)
    return None


# ============== material_batch 子资源（§10.2 + API §5.1.6）==============
@router.get("/{code}/batches", summary="批次列表")
async def list_material_batches(
    code: str,
    request: Request,
    user: User = Depends(require_permission("material:read")),
    db: AsyncSession = Depends(get_db),
):
    service = MaterialService(db)
    items = await service.list_batches(code)
    return success(
        data=[i.model_dump(mode="json") for i in items],
        request_id=getattr(request.state, "request_id", None),
    )


@router.post(
    "/{code}/batches",
    status_code=status.HTTP_201_CREATED,
    summary="添加批次",
)
async def add_material_batch(
    code: str,
    payload: MaterialBatchCreate,
    request: Request,
    user: User = Depends(require_permission("material:update")),
    db: AsyncSession = Depends(get_db),
):
    service = MaterialService(db)
    b = await service.add_batch(code, payload, user)
    return success(
        data=b.model_dump(mode="json"),
        message="批次已添加",
        request_id=getattr(request.state, "request_id", None),
    )


@router.put("/{code}/batches/{batch_id}", summary="更新批次")
async def update_material_batch(
    code: str,
    batch_id: int,
    payload: MaterialBatchUpdate,
    request: Request,
    user: User = Depends(require_permission("material:update")),
    db: AsyncSession = Depends(get_db),
):
    service = MaterialService(db)
    b = await service.update_batch(code, batch_id, payload, user)
    return success(
        data=b.model_dump(mode="json"),
        message="已更新",
        request_id=getattr(request.state, "request_id", None),
    )


@router.delete(
    "/{code}/batches/{batch_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="删除批次（软删除）",
)
async def delete_material_batch(
    code: str,
    batch_id: int,
    payload: MaterialBatchDelete,
    user: User = Depends(require_permission("material:update")),
    db: AsyncSession = Depends(get_db),
):
    service = MaterialService(db)
    await service.delete_batch(code, batch_id, user, reason=payload.change_reason)
    return None


@router.get("/{code}/audit-logs", summary="Material 审计历史")
async def get_material_audit_logs(
    code: str,
    request: Request,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    include_children: bool = Query(
        True,
        description="是否包含 material_batch 子表的审计日志（M4.2 后启用）",
    ),
    user: User = Depends(require_permission("audit:read")),
    db: AsyncSession = Depends(get_db),
):
    audit = AuditService(db)
    items, total = await audit.get_material_audit_logs(
        code, page, page_size, include_children=include_children
    )
    return success(
        data=[i.model_dump(mode="json") for i in items],
        request_id=getattr(request.state, "request_id", None),
        pagination=Pagination.make(page, page_size, total),
    )
