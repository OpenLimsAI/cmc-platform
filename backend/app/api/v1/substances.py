"""
/api/v1/substances 路由
"""
from fastapi import APIRouter, Depends, Query, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.responses import Pagination, success
from app.domains.audit.services import AuditService
from app.domains.auth.models import User
from app.domains.srs.schemas import (
    AdcExtension,
    CheckSamenessRequest,
    ProteinExtension,
    SubstanceCreate,
    SubstanceDelete,
    SubstanceFilter,
    SubstanceStatusChange,
    SubstanceUpdate,
    SubstanceXrefCreate,
    SubstanceXrefUpdate,
)
from app.domains.srs.services import SubstanceService
from app.shared.permissions import require_all_permissions, require_permission

router = APIRouter()


@router.get("", summary="Substance 列表")
async def list_substances(
    request: Request,
    q: str | None = None,
    substance_type: str | None = None,
    status: str | None = None,
    target: str | None = None,
    confidentiality: str | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    sort: str | None = None,
    user: User = Depends(require_permission("substance:read")),
    db: AsyncSession = Depends(get_db),
):
    filter = SubstanceFilter(
        q=q,
        substance_type=substance_type,
        status=status,
        target=target,
        confidentiality=confidentiality,
    )
    service = SubstanceService(db)
    items, total = await service.list_substances(filter, page, page_size, sort)
    return success(
        data=[i.model_dump() for i in items],
        request_id=getattr(request.state, "request_id", None),
        pagination=Pagination.make(page, page_size, total),
    )


@router.post(":check-sameness", summary="同一性判定（提交前预查）")
async def check_substance_sameness(
    payload: CheckSamenessRequest,
    request: Request,
    user: User = Depends(require_permission("substance:read")),
    db: AsyncSession = Depends(get_db),
):
    service = SubstanceService(db)
    result = await service.check_sameness(payload)
    return success(
        data=result.model_dump(mode="json"),
        request_id=getattr(request.state, "request_id", None),
    )


@router.post("", status_code=status.HTTP_201_CREATED, summary="创建 Substance")
async def create_substance(
    payload: SubstanceCreate,
    request: Request,
    response: Response,
    user: User = Depends(require_permission("substance:create")),
    db: AsyncSession = Depends(get_db),
):
    service = SubstanceService(db)
    detail = await service.create(payload, user)
    # API5 / V1.1 §6.2 行 971-972：POST 创建必须设 Location 头
    response.headers["Location"] = f"/api/v1/substances/{detail.substance_code}"
    return success(
        data=detail.model_dump(mode="json"),
        message="Substance 创建成功",
        request_id=getattr(request.state, "request_id", None),
    )


@router.get("/{code}", summary="Substance 详情")
async def get_substance(
    code: str,
    request: Request,
    expand: str | None = None,
    user: User = Depends(require_permission("substance:read")),
    db: AsyncSession = Depends(get_db),
):
    expand_list = [e.strip() for e in expand.split(",")] if expand else []
    service = SubstanceService(db)
    detail = await service.get_by_code(code, expand=expand_list)
    return success(
        data=detail.model_dump(mode="json"),
        request_id=getattr(request.state, "request_id", None),
    )


@router.put("/{code}", summary="更新 Substance")
async def update_substance(
    code: str,
    payload: SubstanceUpdate,
    request: Request,
    user: User = Depends(require_permission("substance:update")),
    db: AsyncSession = Depends(get_db),
):
    service = SubstanceService(db)
    detail = await service.update(code, payload, user)
    return success(
        data=detail.model_dump(mode="json"),
        message="更新成功",
        request_id=getattr(request.state, "request_id", None),
    )


@router.delete("/{code}", status_code=status.HTTP_204_NO_CONTENT, summary="软删除 Substance")
async def delete_substance(
    code: str,
    payload: SubstanceDelete,
    user: User = Depends(require_permission("substance:update")),
    db: AsyncSession = Depends(get_db),
):
    service = SubstanceService(db)
    await service.soft_delete(code, user, reason=payload.change_reason)
    return None


# ============== 状态机端点 ==============
# 路径使用冒号语法（Google AIP-136 / API-MDM-001 §1.2.2）
# FastAPI/Starlette 默认 path param 正则 [^/]+ 会回溯让出 ':<verb>' 字面匹配

async def _state_change(
    code: str,
    action: str,
    payload: SubstanceStatusChange,
    request: Request,
    user: User,
    db: AsyncSession,
):
    service = SubstanceService(db)
    result = await service.change_status(
        code, action, payload.comment, user, signature=payload.signature,
    )
    return success(
        data=result.model_dump(mode="json"),
        message=f"状态已变更为 {result.new_status}",
        request_id=getattr(request.state, "request_id", None),
    )


# GxP 关键动作（approve / activate / deprecate / obsolete）：要求 approve + sign 双权限
@router.post("/{code}:approve", summary="审核通过 (draft → registered) — 需电子签名")
async def approve_substance(
    code: str,
    payload: SubstanceStatusChange,
    request: Request,
    user: User = Depends(require_all_permissions("substance:approve", "substance:sign")),
    db: AsyncSession = Depends(get_db),
):
    return await _state_change(code, "approve", payload, request, user, db)


@router.post("/{code}:activate", summary="激活 (registered → active) — 需电子签名")
async def activate_substance(
    code: str,
    payload: SubstanceStatusChange,
    request: Request,
    user: User = Depends(require_all_permissions("substance:approve", "substance:sign")),
    db: AsyncSession = Depends(get_db),
):
    return await _state_change(code, "activate", payload, request, user, db)


# :restrict 是可逆的临时风控，不要求签名
@router.post("/{code}:restrict", summary="限制访问 (active → restricted)")
async def restrict_substance(
    code: str,
    payload: SubstanceStatusChange,
    request: Request,
    user: User = Depends(require_permission("substance:approve")),
    db: AsyncSession = Depends(get_db),
):
    return await _state_change(code, "restrict", payload, request, user, db)


@router.post("/{code}:deprecate", summary="弃用 (active/restricted → deprecated) — 需电子签名")
async def deprecate_substance(
    code: str,
    payload: SubstanceStatusChange,
    request: Request,
    user: User = Depends(require_all_permissions("substance:approve", "substance:sign")),
    db: AsyncSession = Depends(get_db),
):
    return await _state_change(code, "deprecate", payload, request, user, db)


@router.post("/{code}:obsolete", summary="废弃 (deprecated → obsoleted) — 需电子签名")
async def obsolete_substance(
    code: str,
    payload: SubstanceStatusChange,
    request: Request,
    user: User = Depends(require_all_permissions("substance:approve", "substance:sign")),
    db: AsyncSession = Depends(get_db),
):
    return await _state_change(code, "obsolete", payload, request, user, db)


# ============== xrefs 子资源 ==============
@router.post(
    "/{code}/xrefs",
    status_code=status.HTTP_201_CREATED,
    summary="添加 Substance 标识符",
)
async def add_substance_xref(
    code: str,
    payload: SubstanceXrefCreate,
    request: Request,
    user: User = Depends(require_permission("substance:update")),
    db: AsyncSession = Depends(get_db),
):
    service = SubstanceService(db)
    xref = await service.add_xref(code, payload, user)
    return success(
        data=xref.model_dump(mode="json"),
        message="标识符已添加",
        request_id=getattr(request.state, "request_id", None),
    )


@router.put("/{code}/xrefs/{xref_id}", summary="更新 Substance 标识符")
async def update_substance_xref(
    code: str,
    xref_id: int,
    payload: SubstanceXrefUpdate,
    request: Request,
    user: User = Depends(require_permission("substance:update")),
    db: AsyncSession = Depends(get_db),
):
    service = SubstanceService(db)
    xref = await service.update_xref(code, xref_id, payload, user)
    return success(
        data=xref.model_dump(mode="json"),
        message="标识符已更新",
        request_id=getattr(request.state, "request_id", None),
    )


@router.delete(
    "/{code}/xrefs/{xref_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="软删除 Substance 标识符",
)
async def delete_substance_xref(
    code: str,
    xref_id: int,
    user: User = Depends(require_permission("substance:update")),
    db: AsyncSession = Depends(get_db),
):
    service = SubstanceService(db)
    await service.delete_xref(code, xref_id, user)
    return None


# ============== API13:A 子资源独立写端点（V1.2 评审决议 2026-05-13）==============
@router.put("/{code}/protein", summary="更新 Substance 蛋白扩展（独立子资源）")
async def update_substance_protein(
    code: str,
    payload: ProteinExtension,
    request: Request,
    user: User = Depends(require_permission("substance:update")),
    db: AsyncSession = Depends(get_db),
):
    service = SubstanceService(db)
    detail = await service.update_protein(code, payload, user)
    return success(
        data=detail.model_dump(mode="json"),
        message="protein 已更新",
        request_id=getattr(request.state, "request_id", None),
    )


@router.put("/{code}/adc", summary="更新 Substance ADC 扩展（独立子资源）")
async def update_substance_adc(
    code: str,
    payload: AdcExtension,
    request: Request,
    user: User = Depends(require_permission("substance:update")),
    db: AsyncSession = Depends(get_db),
):
    service = SubstanceService(db)
    adc = await service.update_adc(code, payload, user)
    return success(
        data={
            "substance_id": adc.substance_id,
            "antibody_substance_id": adc.antibody_substance_id,
            "linker_substance_id": adc.linker_substance_id,
            "payload_substance_id": adc.payload_substance_id,
            "dar_average": float(adc.dar_average) if adc.dar_average is not None else None,
            "dar_distribution": adc.dar_distribution,
            "dar_method": adc.dar_method,
            "conjugation_chemistry": adc.conjugation_chemistry,
            "conjugation_site": adc.conjugation_site,
        },
        message="adc 已更新",
        request_id=getattr(request.state, "request_id", None),
    )


# ============== UI9 父子 substance 血缘（V1.2 评审 UI9:B 决议）==============
@router.get(
    "/{code}/lineage",
    summary="物质血缘关系（ADC 父结构 + 反向 ADC 子引用）",
)
async def get_substance_lineage(
    code: str,
    request: Request,
    user: User = Depends(require_permission("substance:read")),
    db: AsyncSession = Depends(get_db),
):
    service = SubstanceService(db)
    lineage = await service.get_lineage(code)
    return success(
        data=lineage,
        request_id=getattr(request.state, "request_id", None),
    )


# ============== 审计与状态历史 ==============
@router.get("/{code}/projects", summary="该物质关联的项目列表（反向查询）")
async def list_substance_projects(
    code: str,
    request: Request,
    include_deleted: bool = Query(False, description="是否包含已取消的历史引用"),
    user: User = Depends(require_permission("substance:read")),
    db: AsyncSession = Depends(get_db),
):
    from app.domains.ref.services import ProjectSubstanceLinkService
    service = ProjectSubstanceLinkService(db)
    items = await service.list_for_substance(code, include_deleted=include_deleted)
    return success(
        data=[i.model_dump(mode="json") for i in items],
        request_id=getattr(request.state, "request_id", None),
    )


@router.get("/{code}/assets", summary="该物质参与组分的资产列表（反向查询）")
async def list_substance_assets(
    code: str,
    request: Request,
    include_deleted: bool = Query(False, description="是否包含已取消的历史引用"),
    user: User = Depends(require_permission("substance:read")),
    db: AsyncSession = Depends(get_db),
):
    from app.domains.ref.services import AssetSubstanceLinkService
    service = AssetSubstanceLinkService(db)
    items = await service.list_for_substance(code, include_deleted=include_deleted)
    return success(
        data=[i.model_dump(mode="json") for i in items],
        request_id=getattr(request.state, "request_id", None),
    )


@router.get("/{code}/audit-logs", summary="Substance 审计历史")
async def get_substance_audit_logs(
    code: str,
    request: Request,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    include_children: bool = Query(
        True,
        description="是否包含 substance_protein / substance_xref 的审计日志（默认包含）",
    ),
    user: User = Depends(require_permission("audit:read")),
    db: AsyncSession = Depends(get_db),
):
    service = AuditService(db)
    items, total = await service.get_substance_audit_logs(
        code, page, page_size, include_children=include_children
    )
    return success(
        data=[i.model_dump(mode="json") for i in items],
        request_id=getattr(request.state, "request_id", None),
        pagination=Pagination.make(page, page_size, total),
    )


@router.get("/{code}/status-history", summary="Substance 状态变更历史")
async def get_substance_status_history(
    code: str,
    request: Request,
    user: User = Depends(require_permission("substance:read")),
    db: AsyncSession = Depends(get_db),
):
    service = SubstanceService(db)
    items = await service.get_status_history(code)
    return success(
        data=[i.model_dump(mode="json") for i in items],
        request_id=getattr(request.state, "request_id", None),
    )
