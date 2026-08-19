"""/api/v1/targets 路由 —— 靶点域（tgt）

设计决策：docs/decisions/2026-08-17-target-domain.md
  - CRUD 对标 equipments.py（幂等键 / change_reason / 软删）
  - 轻档审核：POST /targets/{code}:publish / :retire（target:approve，只要 change_reason）
  - 子资源：/targets/{code}/molecules（ref.molecule_target）、/targets/{code}/snapshots（外部源快照）
  - 反向查询：GET /targets/by-molecule/{substance_code}（一期不碰 substances.py）
"""
from fastapi import APIRouter, Depends, Header, Query, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.exceptions import BadRequestError
from app.core.responses import Pagination, success
from app.domains.auth.models import User
from app.domains.target.schemas import (
    InnApplyRequest,
    InnPrefillRequest,
    MoleculeTargetLinkCreate,
    MoleculeTargetLinkDelete,
    MoleculeTargetLinkUpdate,
    TargetCreate,
    TargetDelete,
    TargetFilter,
    TargetRefreshUniprot,
    TargetSnapshotCreate,
    TargetStatusChange,
    TargetUpdate,
)
from app.domains.target.services import TargetService
from app.shared.idempotency import IdempotencyService
from app.shared.permissions import get_user_permissions, require_permission

router = APIRouter()


def _rid(request: Request):
    return getattr(request.state, "request_id", None)


# ============== 主表 CRUD ==============
@router.get("", summary="Target 列表")
async def list_targets(
    request: Request,
    q: str | None = None,
    keyword: str | None = Query(None, description="UniProt 关键词名，如 Receptor / Cytokine"),
    keyword_category: str | None = Query(None, description="关键词类别，如 Molecular function"),
    location: str | None = Query(None, description="亚细胞定位名，如 Cell membrane / Secreted"),
    entry_type: str | None = Query(None, description="Swiss-Prot / TrEMBL"),
    status: str | None = None,
    uniprot_id: str | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    sort: str | None = None,
    user: User = Depends(require_permission("target:read")),
    db: AsyncSession = Depends(get_db),
):
    filter = TargetFilter(
        q=q, keyword=keyword, keyword_category=keyword_category, location=location,
        entry_type=entry_type, status=status, uniprot_id=uniprot_id,
    )
    items, total = await TargetService(db).list_targets(filter, page, page_size, sort)
    return success(
        data=[i.model_dump(mode="json") for i in items],
        request_id=_rid(request),
        pagination=Pagination.make(page, page_size, total),
    )


@router.post("", status_code=status.HTTP_201_CREATED, summary="创建 Target（draft）")
async def create_target(
    payload: TargetCreate,
    request: Request,
    response: Response,
    idempotency_key: str | None = Header(None, alias="Idempotency-Key"),
    user: User = Depends(require_permission("target:create")),
    db: AsyncSession = Depends(get_db),
):
    if idempotency_key:
        cached = await IdempotencyService.check(user.user_id, idempotency_key, payload.model_dump(mode="json"))
        if cached:
            if cached.headers.get("Location"):
                response.headers["Location"] = cached.headers["Location"]
            return cached.body

    detail = await TargetService(db).create(payload, user)
    location = f"/api/v1/targets/{detail.target_code}"
    response.headers["Location"] = location
    body = success(data=detail.model_dump(mode="json"), message="Target 创建成功", request_id=_rid(request))
    # 先显式 commit 再写幂等缓存（对齐 H-11）
    await db.commit()
    if idempotency_key:
        await IdempotencyService.save(
            user.user_id, idempotency_key, payload.model_dump(mode="json"),
            status_code=201, response_body=body, location=location,
        )
    return body


# 注意：静态路径要放在 /{code} 之前
@router.get("/prefill/uniprot", summary="按 UniProt accession 拉取一条，返回新建靶点表单预填（只读，不落库）")
async def prefill_target_from_uniprot(
    request: Request,
    accession: str = Query(..., min_length=6, max_length=16, description="UniProt accession，如 Q15116"),
    user: User = Depends(require_permission("target:create")),
    db: AsyncSession = Depends(get_db),
):
    from app.domains.target.schemas import _normalize_accession

    try:
        acc = _normalize_accession(accession)
    except ValueError as e:
        raise BadRequestError(str(e)) from e
    data = await TargetService(db).prefill_from_uniprot(acc or "")
    return success(data=data.model_dump(mode="json"), request_id=_rid(request))


@router.post("/prefill/inn", summary="按 INN 走 ChEMBL→UniProt 全链路，返回候选靶点/关联（只读，不落库；约 5–20 秒）")
async def prefill_targets_from_inn(
    payload: InnPrefillRequest,
    request: Request,
    user: User = Depends(require_permission("target:update")),
    db: AsyncSession = Depends(get_db),
):
    data = await TargetService(db).prefill_from_inn(payload.inn.strip())
    return success(data=data.model_dump(mode="json"), request_id=_rid(request))


@router.post("/prefill/inn:apply", status_code=status.HTTP_201_CREATED,
             summary="应用 INN 预填：缺的靶点建草稿（+快照）、全部建关联、回填物质标识符")
async def apply_inn_prefill(
    payload: InnApplyRequest,
    request: Request,
    user: User = Depends(require_permission("target:update")),
    db: AsyncSession = Depends(get_db),
):
    perms = await get_user_permissions(user, db)
    can_create = "target:create" in perms or any(r.role_code == "SYS_ADMIN" for r in user.roles)
    result = await TargetService(db).apply_inn_prefill(payload, user, can_create=can_create)
    return success(data=result.model_dump(mode="json"), message="已应用 INN 预填", request_id=_rid(request))


@router.get("/by-molecule/{substance_code}", summary="某分子（substance）的全部靶点关联")
async def list_targets_of_molecule(
    substance_code: str,
    request: Request,
    user: User = Depends(require_permission("target:read")),
    db: AsyncSession = Depends(get_db),
):
    items = await TargetService(db).list_targets_of_molecule(substance_code)
    return success(data=[i.model_dump(mode="json") for i in items], request_id=_rid(request))


@router.get("/{code}", summary="Target 详情")
async def get_target(
    code: str,
    request: Request,
    user: User = Depends(require_permission("target:read")),
    db: AsyncSession = Depends(get_db),
):
    detail = await TargetService(db).get_by_code(code)
    return success(data=detail.model_dump(mode="json"), request_id=_rid(request))


@router.put("/{code}", summary="更新 Target")
async def update_target(
    code: str,
    payload: TargetUpdate,
    request: Request,
    user: User = Depends(require_permission("target:update")),
    db: AsyncSession = Depends(get_db),
):
    detail = await TargetService(db).update(code, payload, user)
    return success(data=detail.model_dump(mode="json"), message="更新成功", request_id=_rid(request))


@router.delete("/{code}", status_code=status.HTTP_204_NO_CONTENT, summary="软删除 Target")
async def delete_target(
    code: str,
    payload: TargetDelete,
    user: User = Depends(require_permission("target:update")),
    db: AsyncSession = Depends(get_db),
):
    await TargetService(db).soft_delete(code, user, reason=payload.change_reason)
    return None


# ============== 轻档审核动作 ==============
@router.post("/{code}:publish", summary="发布 Target（draft/retired → published，需 change_reason）")
async def publish_target(
    code: str,
    payload: TargetStatusChange,
    request: Request,
    user: User = Depends(require_permission("target:approve")),
    db: AsyncSession = Depends(get_db),
):
    detail = await TargetService(db).change_status(code, "publish", payload.change_reason, user)
    return success(data=detail.model_dump(mode="json"), message="已发布", request_id=_rid(request))


@router.post("/{code}:retire", summary="退役 Target（published/draft → retired，需 change_reason）")
async def retire_target(
    code: str,
    payload: TargetStatusChange,
    request: Request,
    user: User = Depends(require_permission("target:approve")),
    db: AsyncSession = Depends(get_db),
):
    detail = await TargetService(db).change_status(code, "retire", payload.change_reason, user)
    return success(data=detail.model_dump(mode="json"), message="已退役", request_id=_rid(request))


@router.post("/{code}:refresh-uniprot", summary="按当前 uniprot_id 重新拉取 UniProt，覆盖标准字段并追加快照")
async def refresh_target_from_uniprot(
    code: str,
    payload: TargetRefreshUniprot,
    request: Request,
    user: User = Depends(require_permission("target:update")),
    db: AsyncSession = Depends(get_db),
):
    detail = await TargetService(db).refresh_from_uniprot(code, payload.change_reason, user)
    return success(data=detail.model_dump(mode="json"), message="已从 UniProt 刷新", request_id=_rid(request))


# ============== 子资源：分子关联 ref.molecule_target ==============
@router.get("/{code}/molecules", summary="Target 关联的分子列表")
async def list_target_molecules(
    code: str,
    request: Request,
    user: User = Depends(require_permission("target:read")),
    db: AsyncSession = Depends(get_db),
):
    items = await TargetService(db).list_molecules(code)
    return success(data=[i.model_dump(mode="json") for i in items], request_id=_rid(request))


@router.post("/{code}/molecules", status_code=status.HTTP_201_CREATED, summary="关联分子到 Target")
async def add_target_molecule(
    code: str,
    payload: MoleculeTargetLinkCreate,
    request: Request,
    user: User = Depends(require_permission("target:update")),
    db: AsyncSession = Depends(get_db),
):
    item = await TargetService(db).add_molecule(code, payload, user)
    return success(data=item.model_dump(mode="json"), message="关联成功", request_id=_rid(request))


@router.put("/{code}/molecules/{substance_code}/{relation_role}", summary="更新分子-靶点关联属性")
async def update_target_molecule(
    code: str,
    substance_code: str,
    relation_role: str,
    payload: MoleculeTargetLinkUpdate,
    request: Request,
    user: User = Depends(require_permission("target:update")),
    db: AsyncSession = Depends(get_db),
):
    item = await TargetService(db).update_molecule(code, substance_code, relation_role, payload, user)
    return success(data=item.model_dump(mode="json"), message="更新成功", request_id=_rid(request))


@router.delete(
    "/{code}/molecules/{substance_code}/{relation_role}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="取消分子-靶点关联（软删）",
)
async def remove_target_molecule(
    code: str,
    substance_code: str,
    relation_role: str,
    payload: MoleculeTargetLinkDelete,
    user: User = Depends(require_permission("target:update")),
    db: AsyncSession = Depends(get_db),
):
    await TargetService(db).remove_molecule(code, substance_code, relation_role, payload.change_reason, user)
    return None


# ============== 审计历史 ==============
@router.get("/{code}/audit-logs", summary="Target 审计历史（主表 + 分子关联）")
async def get_target_audit_logs(
    code: str,
    request: Request,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    include_children: bool = Query(True, description="是否包含 ref.molecule_target 关联表的审计"),
    user: User = Depends(require_permission("audit:read")),
    db: AsyncSession = Depends(get_db),
):
    items, total = await TargetService(db).get_audit_logs(code, page, page_size, include_children)
    return success(
        data=[i.model_dump(mode="json") for i in items],
        request_id=_rid(request),
        pagination=Pagination.make(page, page_size, total),
    )


# ============== 子资源：外部源快照 ==============
@router.get("/{code}/snapshots", summary="Target 外部源快照列表（不含 payload）")
async def list_target_snapshots(
    code: str,
    request: Request,
    user: User = Depends(require_permission("target:read")),
    db: AsyncSession = Depends(get_db),
):
    items = await TargetService(db).list_snapshots(code)
    return success(data=[i.model_dump(mode="json") for i in items], request_id=_rid(request))


@router.get("/{code}/snapshots/{snapshot_id}", summary="快照详情（含 payload）")
async def get_target_snapshot(
    code: str,
    snapshot_id: int,
    request: Request,
    user: User = Depends(require_permission("target:read")),
    db: AsyncSession = Depends(get_db),
):
    item = await TargetService(db).get_snapshot(code, snapshot_id)
    return success(data=item.model_dump(mode="json"), request_id=_rid(request))


@router.post("/{code}/snapshots", status_code=status.HTTP_201_CREATED, summary="追加外部源快照（append-only）")
async def add_target_snapshot(
    code: str,
    payload: TargetSnapshotCreate,
    request: Request,
    user: User = Depends(require_permission("target:update")),
    db: AsyncSession = Depends(get_db),
):
    item = await TargetService(db).add_snapshot(code, payload, user)
    return success(data=item.model_dump(mode="json"), message="快照已保存", request_id=_rid(request))
