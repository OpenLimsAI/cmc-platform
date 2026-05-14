"""
/api/v1/assets 路由

M3.1：CRUD + 审计查询
M3.2：状态机 + market-id 子资源
M3.3：跨域绑定 ref.asset_substance / ref.project_asset
"""
from fastapi import APIRouter, Depends, Header, Query, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.responses import Pagination, success
from app.domains.ars.schemas import (
    AssetCreate,
    AssetDelete,
    AssetFilter,
    AssetMarketIdCreate,
    AssetMarketIdDelete,
    AssetMarketIdUpdate,
    AssetStatusChange,
    AssetUpdate,
)
from app.domains.ars.services import AssetService
from app.domains.audit.services import AuditService
from app.domains.auth.models import User
from app.domains.ref.schemas import (
    AssetSubstanceLinkCreate,
    AssetSubstanceLinkUnlink,
    ProjectAssetLinkByAsset,
    ProjectAssetLinkUnlink,
)
from app.domains.ref.services import (
    AssetSubstanceLinkService,
    ProjectAssetLinkService,
)
from app.shared.idempotency import IdempotencyService
from app.shared.permissions import require_all_permissions, require_permission

router = APIRouter()


@router.get("", summary="Asset 列表")
async def list_assets(
    request: Request,
    q: str | None = None,
    asset_type: str | None = None,
    current_phase: str | None = None,
    status: str | None = None,
    therapeutic_area: str | None = None,
    is_commercial: bool | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    sort: str | None = None,
    user: User = Depends(require_permission("asset:read")),
    db: AsyncSession = Depends(get_db),
):
    filter = AssetFilter(
        q=q,
        asset_type=asset_type,
        current_phase=current_phase,
        status=status,
        therapeutic_area=therapeutic_area,
        is_commercial=is_commercial,
    )
    service = AssetService(db)
    items, total = await service.list_assets(filter, page, page_size, sort)
    return success(
        data=[i.model_dump(mode="json") for i in items],
        request_id=getattr(request.state, "request_id", None),
        pagination=Pagination.make(page, page_size, total),
    )


@router.post("", status_code=status.HTTP_201_CREATED, summary="创建 Asset")
async def create_asset(
    payload: AssetCreate,
    request: Request,
    response: Response,
    idempotency_key: str | None = Header(None, alias="Idempotency-Key"),
    user: User = Depends(require_permission("asset:create")),
    db: AsyncSession = Depends(get_db),
):
    if idempotency_key:
        cached = await IdempotencyService.check(user.user_id, idempotency_key, payload.model_dump())
        if cached:
            if cached.headers.get("Location"):
                response.headers["Location"] = cached.headers["Location"]
            return cached.body

    service = AssetService(db)
    detail = await service.create(payload, user)
    # API5 / V1.1 §8.2：POST 创建必须设 Location 头
    location = f"/api/v1/assets/{detail.asset_code}"
    response.headers["Location"] = location

    body = success(
        data=detail.model_dump(mode="json"),
        message="Asset 创建成功",
        request_id=getattr(request.state, "request_id", None),
    )
    if idempotency_key:
        await IdempotencyService.save(
            user.user_id, idempotency_key, payload.model_dump(),
            status_code=201, response_body=body, location=location,
        )
    return body


@router.get("/{code}", summary="Asset 详情")
async def get_asset(
    code: str,
    request: Request,
    user: User = Depends(require_permission("asset:read")),
    db: AsyncSession = Depends(get_db),
):
    service = AssetService(db)
    detail = await service.get_by_code(code)
    return success(
        data=detail.model_dump(mode="json"),
        request_id=getattr(request.state, "request_id", None),
    )


@router.put("/{code}", summary="更新 Asset")
async def update_asset(
    code: str,
    payload: AssetUpdate,
    request: Request,
    user: User = Depends(require_permission("asset:update")),
    db: AsyncSession = Depends(get_db),
):
    service = AssetService(db)
    detail = await service.update(code, payload, user)
    return success(
        data=detail.model_dump(mode="json"),
        message="更新成功",
        request_id=getattr(request.state, "request_id", None),
    )


@router.delete("/{code}", status_code=status.HTTP_204_NO_CONTENT, summary="软删除 Asset")
async def delete_asset(
    code: str,
    payload: AssetDelete,
    user: User = Depends(require_permission("asset:update")),
    db: AsyncSession = Depends(get_db),
):
    service = AssetService(db)
    await service.soft_delete(code, user, reason=payload.change_reason)
    return None


@router.get("/{code}/audit-logs", summary="Asset 审计历史")
async def get_asset_audit_logs(
    code: str,
    request: Request,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    include_children: bool = Query(
        True,
        description="是否包含 asset_market_id 子表的审计日志",
    ),
    user: User = Depends(require_permission("audit:read")),
    db: AsyncSession = Depends(get_db),
):
    service = AuditService(db)
    items, total = await service.get_asset_audit_logs(
        code, page, page_size, include_children=include_children
    )
    return success(
        data=[i.model_dump(mode="json") for i in items],
        request_id=getattr(request.state, "request_id", None),
        pagination=Pagination.make(page, page_size, total),
    )


# ============== 状态机端点（DM-MDM-001 §8.2 status ∈ active/on_hold/terminated）==============
async def _state_change(
    code: str,
    action: str,
    payload: AssetStatusChange,
    request: Request,
    user: User,
    db: AsyncSession,
):
    service = AssetService(db)
    result = await service.change_status(
        code, action, payload.comment, user, signature=payload.signature,
    )
    return success(
        data=result.model_dump(mode="json"),
        message=f"状态已变更为 {result.new_status}",
        request_id=getattr(request.state, "request_id", None),
    )


@router.post("/{code}:hold", summary="暂停 (active → on_hold)")
async def hold_asset(
    code: str,
    payload: AssetStatusChange,
    request: Request,
    user: User = Depends(require_permission("asset:update")),
    db: AsyncSession = Depends(get_db),
):
    return await _state_change(code, "hold", payload, request, user, db)


@router.post("/{code}:resume", summary="恢复 (on_hold → active)")
async def resume_asset(
    code: str,
    payload: AssetStatusChange,
    request: Request,
    user: User = Depends(require_permission("asset:update")),
    db: AsyncSession = Depends(get_db),
):
    return await _state_change(code, "resume", payload, request, user, db)


@router.post(
    "/{code}:terminate",
    summary="终止 (active/on_hold → terminated) — 需电子签名",
)
async def terminate_asset(
    code: str,
    payload: AssetStatusChange,
    request: Request,
    # terminate 是 GxP 关键不可逆动作；要求 asset:update + asset:sign 双权限
    user: User = Depends(require_all_permissions("asset:update", "asset:sign")),
    db: AsyncSession = Depends(get_db),
):
    return await _state_change(code, "terminate", payload, request, user, db)


@router.get("/{code}/status-history", summary="Asset 状态变更历史")
async def get_asset_status_history(
    code: str,
    request: Request,
    user: User = Depends(require_permission("asset:read")),
    db: AsyncSession = Depends(get_db),
):
    service = AssetService(db)
    items = await service.get_status_history(code)
    return success(
        data=[i.model_dump(mode="json") for i in items],
        request_id=getattr(request.state, "request_id", None),
    )


# ============== 多市场注册号子资源（§8.3）==============
@router.get("/{code}/market-ids", summary="多市场注册号列表")
async def list_market_ids(
    code: str,
    request: Request,
    user: User = Depends(require_permission("asset:read")),
    db: AsyncSession = Depends(get_db),
):
    service = AssetService(db)
    items = await service.list_market_ids(code)
    return success(
        data=[i.model_dump(mode="json") for i in items],
        request_id=getattr(request.state, "request_id", None),
    )


@router.post(
    "/{code}/market-ids",
    status_code=status.HTTP_201_CREATED,
    summary="添加多市场注册号",
)
async def add_market_id(
    code: str,
    payload: AssetMarketIdCreate,
    request: Request,
    user: User = Depends(require_permission("asset:update")),
    db: AsyncSession = Depends(get_db),
):
    service = AssetService(db)
    m = await service.add_market_id(code, payload, user)
    return success(
        data=m.model_dump(mode="json"),
        message="多市场注册号已添加",
        request_id=getattr(request.state, "request_id", None),
    )


@router.put("/{code}/market-ids/{market_id_pk}", summary="更新多市场注册号")
async def update_market_id(
    code: str,
    market_id_pk: int,
    payload: AssetMarketIdUpdate,
    request: Request,
    user: User = Depends(require_permission("asset:update")),
    db: AsyncSession = Depends(get_db),
):
    service = AssetService(db)
    m = await service.update_market_id(code, market_id_pk, payload, user)
    return success(
        data=m.model_dump(mode="json"),
        message="已更新",
        request_id=getattr(request.state, "request_id", None),
    )


@router.delete(
    "/{code}/market-ids/{market_id_pk}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="删除多市场注册号（软删除，保留审计）",
)
async def delete_market_id(
    code: str,
    market_id_pk: int,
    payload: AssetMarketIdDelete,
    user: User = Depends(require_permission("asset:update")),
    db: AsyncSession = Depends(get_db),
):
    service = AssetService(db)
    await service.delete_market_id(code, market_id_pk, user, reason=payload.change_reason)
    return None


# ============== 物质组分关联（§11.3 ref.asset_substance）==============
@router.get("/{code}/substances", summary="资产关联的物质组分列表")
async def list_asset_substances(
    code: str,
    request: Request,
    include_deleted: bool = Query(False),
    user: User = Depends(require_permission("asset:read")),
    db: AsyncSession = Depends(get_db),
):
    service = AssetSubstanceLinkService(db)
    items = await service.list_for_asset(code, include_deleted=include_deleted)
    return success(
        data=[i.model_dump(mode="json") for i in items],
        request_id=getattr(request.state, "request_id", None),
    )


@router.post(
    "/{code}/substances",
    status_code=status.HTTP_201_CREATED,
    summary="为资产绑定物质组分（terminated 资产禁止）",
)
async def link_substance_to_asset(
    code: str,
    payload: AssetSubstanceLinkCreate,
    request: Request,
    user: User = Depends(require_permission("asset:update")),
    db: AsyncSession = Depends(get_db),
):
    service = AssetSubstanceLinkService(db)
    item = await service.link(code, payload, user)
    return success(
        data=item.model_dump(mode="json"),
        message="物质组分已绑定",
        request_id=getattr(request.state, "request_id", None),
    )


@router.delete(
    "/{code}/substances/{substance_code}/{component_role}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="取消物质组分引用",
)
async def unlink_substance_from_asset(
    code: str,
    substance_code: str,
    component_role: str,
    payload: AssetSubstanceLinkUnlink,
    user: User = Depends(require_permission("asset:update")),
    db: AsyncSession = Depends(get_db),
):
    service = AssetSubstanceLinkService(db)
    await service.unlink(
        code, substance_code, component_role, user, reason=payload.change_reason
    )
    return None


# ============== 项目关联（§11.4 ref.project_asset，资产侧）==============
@router.get("/{code}/projects", summary="资产关联的项目列表（反向查询）")
async def list_asset_projects(
    code: str,
    request: Request,
    include_deleted: bool = Query(False),
    user: User = Depends(require_permission("asset:read")),
    db: AsyncSession = Depends(get_db),
):
    service = ProjectAssetLinkService(db)
    items = await service.list_for_asset(code, include_deleted=include_deleted)
    return success(
        data=[i.model_dump(mode="json") for i in items],
        request_id=getattr(request.state, "request_id", None),
    )


@router.post(
    "/{code}/projects",
    status_code=status.HTTP_201_CREATED,
    summary="将资产关联到项目（terminated 资产禁止）",
)
async def link_project_to_asset(
    code: str,
    payload: ProjectAssetLinkByAsset,
    request: Request,
    user: User = Depends(require_permission("asset:update")),
    db: AsyncSession = Depends(get_db),
):
    service = ProjectAssetLinkService(db)
    item = await service.link(
        payload.project_code, code, payload.relation_type, payload.notes, user
    )
    return success(
        data=item.model_dump(mode="json"),
        message="已关联项目",
        request_id=getattr(request.state, "request_id", None),
    )


@router.delete(
    "/{code}/projects/{project_code}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="取消项目引用",
)
async def unlink_project_from_asset(
    code: str,
    project_code: str,
    payload: ProjectAssetLinkUnlink,
    user: User = Depends(require_permission("asset:update")),
    db: AsyncSession = Depends(get_db),
):
    service = ProjectAssetLinkService(db)
    await service.unlink(project_code, code, user, reason=payload.change_reason)
    return None
