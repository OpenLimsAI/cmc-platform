"""
/api/v1/projects 路由

M2.1：CRUD + 审计查询
M2.2：状态机 + status-history + milestones / team 子资源
M2.3 起：/projects/{code}/substances 绑定/解绑 + 反向查询
"""
from fastapi import APIRouter, Depends, Header, Query, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.responses import Pagination, success
from app.domains.audit.services import AuditService
from app.domains.auth.models import User
from app.domains.prs.schemas import (
    ProjectCreate,
    ProjectDelete,
    ProjectFilter,
    ProjectMilestoneCreate,
    ProjectMilestoneDelete,
    ProjectMilestoneUpdate,
    ProjectRelationshipCreate,
    ProjectStatusChange,
    ProjectTeamMemberCreate,
    ProjectTeamMemberRemove,
    ProjectUpdate,
)
from app.domains.prs.services import ProjectService
from app.domains.ref.schemas import (
    ProjectAssetLinkByProject,
    ProjectAssetLinkUnlink,
    ProjectSubstanceLinkCreate,
    ProjectSubstanceLinkUnlink,
)
from app.domains.ref.services import ProjectAssetLinkService, ProjectSubstanceLinkService
from app.shared.idempotency import IdempotencyService
from app.shared.permissions import require_all_permissions, require_permission

router = APIRouter()


@router.get("", summary="Project 列表")
async def list_projects(
    request: Request,
    q: str | None = None,
    project_type: str | None = None,
    project_phase: str | None = None,
    project_category: str | None = None,
    project_nature: str | None = None,
    owning_function: str | None = None,
    asset_id: int | None = None,
    status: str | None = None,
    department: str | None = None,
    project_manager_id: int | None = None,
    priority: str | None = None,
    program_name: str | None = None,
    parent_project_id: int | None = None,
    confidentiality: str | None = None,
    budget_currency: str | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    sort: str | None = None,
    user: User = Depends(require_permission("project:read")),
    db: AsyncSession = Depends(get_db),
):
    filter = ProjectFilter(
        q=q,
        project_type=project_type,
        project_phase=project_phase,
        project_category=project_category,
        project_nature=project_nature,
        owning_function=owning_function,
        asset_id=asset_id,
        status=status,
        department=department,
        project_manager_id=project_manager_id,
        priority=priority,
        program_name=program_name,
        parent_project_id=parent_project_id,
        confidentiality=confidentiality,
        budget_currency=budget_currency,
    )
    service = ProjectService(db)
    items, total = await service.list_projects(filter, page, page_size, sort)
    return success(
        data=[i.model_dump(mode="json") for i in items],
        request_id=getattr(request.state, "request_id", None),
        pagination=Pagination.make(page, page_size, total),
    )


@router.post("", status_code=status.HTTP_201_CREATED, summary="创建 Project")
async def create_project(
    payload: ProjectCreate,
    request: Request,
    response: Response,
    idempotency_key: str | None = Header(None, alias="Idempotency-Key"),
    user: User = Depends(require_permission("project:create")),
    db: AsyncSession = Depends(get_db),
):
    if idempotency_key:
        cached = await IdempotencyService.check(user.user_id, idempotency_key, payload.model_dump())
        if cached:
            if cached.headers.get("Location"):
                response.headers["Location"] = cached.headers["Location"]
            return cached.body

    service = ProjectService(db)
    detail = await service.create(payload, user)
    location = f"/api/v1/projects/{detail.project_code}"
    response.headers["Location"] = location

    body = success(
        data=detail.model_dump(mode="json"),
        message="Project 创建成功",
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


@router.get("/{code}", summary="Project 详情")
async def get_project(
    code: str,
    request: Request,
    user: User = Depends(require_permission("project:read")),
    db: AsyncSession = Depends(get_db),
):
    service = ProjectService(db)
    detail = await service.get_by_code(code)
    return success(
        data=detail.model_dump(mode="json"),
        request_id=getattr(request.state, "request_id", None),
    )


@router.put("/{code}", summary="更新 Project")
async def update_project(
    code: str,
    payload: ProjectUpdate,
    request: Request,
    user: User = Depends(require_permission("project:update")),
    db: AsyncSession = Depends(get_db),
):
    service = ProjectService(db)
    detail = await service.update(code, payload, user)
    return success(
        data=detail.model_dump(mode="json"),
        message="更新成功",
        request_id=getattr(request.state, "request_id", None),
    )


@router.delete("/{code}", status_code=status.HTTP_204_NO_CONTENT, summary="软删除 Project")
async def delete_project(
    code: str,
    payload: ProjectDelete,
    user: User = Depends(require_permission("project:update")),
    db: AsyncSession = Depends(get_db),
):
    service = ProjectService(db)
    await service.soft_delete(code, user, reason=payload.change_reason)
    return None


# ============== 状态机端点（路径冒号语法，AIP-136）==============
async def _state_change(
    code: str,
    action: str,
    payload: ProjectStatusChange,
    request: Request,
    user: User,
    db: AsyncSession,
):
    service = ProjectService(db)
    result = await service.change_status(
        code, action, payload.comment, user, signature=payload.signature,
    )
    return success(
        data=result.model_dump(mode="json"),
        message=f"状态已变更为 {result.new_status}",
        request_id=getattr(request.state, "request_id", None),
    )


# GxP 关键动作（approve / complete / terminate）：要求 approve + sign 双权限
@router.post("/{code}:approve", summary="审批立项 (draft → planned) — 需电子签名")
async def approve_project(
    code: str,
    payload: ProjectStatusChange,
    request: Request,
    user: User = Depends(require_all_permissions("project:approve", "project:sign")),
    db: AsyncSession = Depends(get_db),
):
    return await _state_change(code, "approve", payload, request, user, db)


# :start / :hold / :resume 是项目进度跟踪，非合规关键转移，不要求签名
@router.post("/{code}:start", summary="启动 (planned → active)")
async def start_project(
    code: str,
    payload: ProjectStatusChange,
    request: Request,
    user: User = Depends(require_permission("project:approve")),
    db: AsyncSession = Depends(get_db),
):
    return await _state_change(code, "start", payload, request, user, db)


@router.post("/{code}:hold", summary="暂停 (active → on_hold)")
async def hold_project(
    code: str,
    payload: ProjectStatusChange,
    request: Request,
    user: User = Depends(require_permission("project:approve")),
    db: AsyncSession = Depends(get_db),
):
    return await _state_change(code, "hold", payload, request, user, db)


@router.post("/{code}:resume", summary="恢复 (on_hold → active)")
async def resume_project(
    code: str,
    payload: ProjectStatusChange,
    request: Request,
    user: User = Depends(require_permission("project:approve")),
    db: AsyncSession = Depends(get_db),
):
    return await _state_change(code, "resume", payload, request, user, db)


@router.post("/{code}:complete", summary="完成 (active → completed) — 需电子签名")
async def complete_project(
    code: str,
    payload: ProjectStatusChange,
    request: Request,
    user: User = Depends(require_all_permissions("project:approve", "project:sign")),
    db: AsyncSession = Depends(get_db),
):
    return await _state_change(code, "complete", payload, request, user, db)


@router.post(
    "/{code}:terminate",
    summary="终止 (draft/planned/active/on_hold → terminated) — 需电子签名",
)
async def terminate_project(
    code: str,
    payload: ProjectStatusChange,
    request: Request,
    user: User = Depends(require_all_permissions("project:approve", "project:sign")),
    db: AsyncSession = Depends(get_db),
):
    return await _state_change(code, "terminate", payload, request, user, db)


@router.post(
    "/{code}:cancel",
    summary="取消 (proposed/initiated → cancelled) — 需电子签名",
)
async def cancel_project(
    code: str,
    payload: ProjectStatusChange,
    request: Request,
    user: User = Depends(require_all_permissions("project:approve", "project:sign")),
    db: AsyncSession = Depends(get_db),
):
    # SMP-RD-NUM-001 V2.1 §11.3：cancelled 仅用于尚未启动的项目
    return await _state_change(code, "cancel", payload, request, user, db)


@router.get("/{code}/status-history", summary="Project 状态变更历史")
async def get_project_status_history(
    code: str,
    request: Request,
    user: User = Depends(require_permission("project:read")),
    db: AsyncSession = Depends(get_db),
):
    service = ProjectService(db)
    items = await service.get_status_history(code)
    return success(
        data=[i.model_dump(mode="json") for i in items],
        request_id=getattr(request.state, "request_id", None),
    )


# ============== 里程碑子资源 ==============
@router.get("/{code}/milestones", summary="项目里程碑列表")
async def list_milestones(
    code: str,
    request: Request,
    user: User = Depends(require_permission("project:read")),
    db: AsyncSession = Depends(get_db),
):
    service = ProjectService(db)
    items = await service.list_milestones(code)
    return success(
        data=[i.model_dump(mode="json") for i in items],
        request_id=getattr(request.state, "request_id", None),
    )


@router.post(
    "/{code}/milestones",
    status_code=status.HTTP_201_CREATED,
    summary="添加里程碑",
)
async def add_milestone(
    code: str,
    payload: ProjectMilestoneCreate,
    request: Request,
    user: User = Depends(require_permission("project:update")),
    db: AsyncSession = Depends(get_db),
):
    service = ProjectService(db)
    m = await service.add_milestone(code, payload, user)
    return success(
        data=m.model_dump(mode="json"),
        message="里程碑已添加",
        request_id=getattr(request.state, "request_id", None),
    )


@router.put("/{code}/milestones/{milestone_id}", summary="更新里程碑（含状态变更）")
async def update_milestone(
    code: str,
    milestone_id: int,
    payload: ProjectMilestoneUpdate,
    request: Request,
    user: User = Depends(require_permission("project:update")),
    db: AsyncSession = Depends(get_db),
):
    service = ProjectService(db)
    m = await service.update_milestone(code, milestone_id, payload, user)
    return success(
        data=m.model_dump(mode="json"),
        message="里程碑已更新",
        request_id=getattr(request.state, "request_id", None),
    )


@router.delete(
    "/{code}/milestones/{milestone_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="软删除里程碑",
)
async def delete_milestone(
    code: str,
    milestone_id: int,
    payload: ProjectMilestoneDelete,
    user: User = Depends(require_permission("project:update")),
    db: AsyncSession = Depends(get_db),
):
    service = ProjectService(db)
    await service.delete_milestone(code, milestone_id, user, reason=payload.change_reason)
    return None


# ============== 团队子资源 ==============
@router.get("/{code}/team", summary="项目团队成员列表")
async def list_team(
    code: str,
    request: Request,
    include_left: bool = Query(False, description="是否包含已离开成员"),
    user: User = Depends(require_permission("project:read")),
    db: AsyncSession = Depends(get_db),
):
    service = ProjectService(db)
    items = await service.list_team(code, include_left=include_left)
    return success(
        data=[i.model_dump(mode="json") for i in items],
        request_id=getattr(request.state, "request_id", None),
    )


@router.post(
    "/{code}/team",
    status_code=status.HTTP_201_CREATED,
    summary="添加团队成员",
)
async def add_team_member(
    code: str,
    payload: ProjectTeamMemberCreate,
    request: Request,
    user: User = Depends(require_permission("project:update")),
    db: AsyncSession = Depends(get_db),
):
    service = ProjectService(db)
    m = await service.add_team_member(code, payload, user)
    return success(
        data=m.model_dump(mode="json"),
        message="成员已添加",
        request_id=getattr(request.state, "request_id", None),
    )


@router.delete(
    "/{code}/team/{team_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="移除团队成员（写 left_at，不硬删）",
)
async def remove_team_member(
    code: str,
    team_id: int,
    payload: ProjectTeamMemberRemove,
    user: User = Depends(require_permission("project:update")),
    db: AsyncSession = Depends(get_db),
):
    service = ProjectService(db)
    await service.remove_team_member(
        code, team_id, user, reason=payload.change_reason
    )
    return None


# ============== 物质关联子资源（ref.project_substance）==============
# DM-MDM-001 §11.2：复合 PK (project_id, substance_id, relation_type)，
# API 路径相应使用 (substance_code, relation_type) 定位
@router.get("/{code}/substances", summary="项目关联的物质列表")
async def list_project_substances(
    code: str,
    request: Request,
    include_deleted: bool = Query(False, description="是否包含已取消的历史引用"),
    user: User = Depends(require_permission("project:read")),
    db: AsyncSession = Depends(get_db),
):
    service = ProjectSubstanceLinkService(db)
    items = await service.list_for_project(code, include_deleted=include_deleted)
    return success(
        data=[i.model_dump(mode="json") for i in items],
        request_id=getattr(request.state, "request_id", None),
    )


@router.post(
    "/{code}/substances",
    status_code=status.HTTP_201_CREATED,
    summary="绑定物质到项目",
)
async def link_substance_to_project(
    code: str,
    payload: ProjectSubstanceLinkCreate,
    request: Request,
    user: User = Depends(require_permission("project:update")),
    db: AsyncSession = Depends(get_db),
):
    service = ProjectSubstanceLinkService(db)
    item = await service.link(code, payload, user)
    return success(
        data=item.model_dump(mode="json"),
        message="物质已绑定",
        request_id=getattr(request.state, "request_id", None),
    )


@router.delete(
    "/{code}/substances/{substance_code}/{relation_type}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="取消物质引用（软删除，保留审计）",
)
async def unlink_substance_from_project(
    code: str,
    substance_code: str,
    relation_type: str,
    payload: ProjectSubstanceLinkUnlink,
    user: User = Depends(require_permission("project:update")),
    db: AsyncSession = Depends(get_db),
):
    service = ProjectSubstanceLinkService(db)
    await service.unlink(
        code, substance_code, relation_type, user, reason=payload.change_reason
    )
    return None


# ============== 资产关联子资源（§11.4 ref.project_asset）==============
@router.get("/{code}/assets", summary="项目关联的资产列表")
async def list_project_assets(
    code: str,
    request: Request,
    include_deleted: bool = Query(False),
    user: User = Depends(require_permission("project:read")),
    db: AsyncSession = Depends(get_db),
):
    service = ProjectAssetLinkService(db)
    items = await service.list_for_project(code, include_deleted=include_deleted)
    return success(
        data=[i.model_dump(mode="json") for i in items],
        request_id=getattr(request.state, "request_id", None),
    )


@router.post(
    "/{code}/assets",
    status_code=status.HTTP_201_CREATED,
    summary="为项目关联资产（terminated 资产禁止）",
)
async def link_asset_to_project(
    code: str,
    payload: ProjectAssetLinkByProject,
    request: Request,
    user: User = Depends(require_permission("project:update")),
    db: AsyncSession = Depends(get_db),
):
    service = ProjectAssetLinkService(db)
    item = await service.link(
        code, payload.asset_code, payload.relation_type, payload.notes, user
    )
    return success(
        data=item.model_dump(mode="json"),
        message="资产已关联",
        request_id=getattr(request.state, "request_id", None),
    )


@router.delete(
    "/{code}/assets/{asset_code}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="取消资产引用",
)
async def unlink_asset_from_project(
    code: str,
    asset_code: str,
    payload: ProjectAssetLinkUnlink,
    user: User = Depends(require_permission("project:update")),
    db: AsyncSession = Depends(get_db),
):
    service = ProjectAssetLinkService(db)
    await service.unlink(code, asset_code, user, reason=payload.change_reason)
    return None


# ============== 项目关系子资源（SMP §11.4-11.6 合并/拆分/衍生）==============
@router.get("/{code}/relationships", summary="项目关系列表（含 in/out 方向）")
async def list_project_relationships(
    code: str,
    request: Request,
    user: User = Depends(require_permission("project:read")),
    db: AsyncSession = Depends(get_db),
):
    service = ProjectService(db)
    items = await service.list_relationships(code)
    return success(
        data=[i.model_dump(mode="json") for i in items],
        request_id=getattr(request.state, "request_id", None),
    )


@router.post(
    "/{code}/relationships",
    status_code=status.HTTP_201_CREATED,
    summary="新建项目关系（merged_into/split_from/derived_from/depends_on/blocks）",
)
async def add_project_relationship(
    code: str,
    payload: ProjectRelationshipCreate,
    request: Request,
    user: User = Depends(require_permission("project:update")),
    db: AsyncSession = Depends(get_db),
):
    service = ProjectService(db)
    item = await service.add_relationship(code, payload, user)
    return success(
        data=item.model_dump(mode="json"),
        message="关系已建立",
        request_id=getattr(request.state, "request_id", None),
    )


@router.delete(
    "/{code}/relationships/{relationship_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="删除项目关系",
)
async def delete_project_relationship(
    code: str,
    relationship_id: int,
    user: User = Depends(require_permission("project:update")),
    db: AsyncSession = Depends(get_db),
):
    service = ProjectService(db)
    await service.delete_relationship(code, relationship_id, user)
    return None


@router.get("/{code}/audit-logs", summary="Project 审计历史")
async def get_project_audit_logs(
    code: str,
    request: Request,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    include_children: bool = Query(
        True,
        description="是否包含 milestone / team / project_substance 子表的审计日志（M2.1 暂无子表数据）",
    ),
    user: User = Depends(require_permission("audit:read")),
    db: AsyncSession = Depends(get_db),
):
    service = AuditService(db)
    items, total = await service.get_project_audit_logs(
        code, page, page_size, include_children=include_children
    )
    return success(
        data=[i.model_dump(mode="json") for i in items],
        request_id=getattr(request.state, "request_id", None),
        pagination=Pagination.make(page, page_size, total),
    )
