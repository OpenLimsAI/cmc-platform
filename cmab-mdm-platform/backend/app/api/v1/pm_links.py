"""Authenticated mapping endpoints; existing MDM permissions and numeric identity."""
from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.core.exceptions import AppError
from app.core.responses import success
from app.domains.auth.models import User
from app.domains.prs.pm_create import CreatePMProject, PMCreateClient, ProjectPMCreateService
from app.domains.prs.pm_links import ProjectPMLinkService
from app.domains.prs.pm_reference import PMReferenceClient
from app.shared.permissions import require_permission

router = APIRouter()


class BindPMProject(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    pm_project_id: str = Field(min_length=1, max_length=64, pattern=r"^[A-Za-z0-9][A-Za-z0-9_.-]*$")
    change_reason: str = Field(min_length=5, max_length=1000)


@router.get("/projects/{code}/pm-link")
async def get_pm_link(code: str, request: Request, user: User = Depends(require_permission("project:read")), db: AsyncSession = Depends(get_db)):
    reference = await _manual_reference(request, db, required=False)
    return success(data=await ProjectPMLinkService(db, reference).get(code))


@router.post("/projects/{code}/pm-link")
async def bind_pm_link(code: str, payload: BindPMProject, request: Request, user: User = Depends(require_permission("project:update")), db: AsyncSession = Depends(get_db)):
    reference = await _manual_reference(request, db, required=True)
    return success(data=await ProjectPMLinkService(db, reference).bind(code, payload.pm_project_id, payload.change_reason, user))


@router.get("/integration/pm-projects/{pm_id}")
async def resolve_pm_link(pm_id: str, user: User = Depends(require_permission("project:read")), db: AsyncSession = Depends(get_db)):
    return success(data=await ProjectPMLinkService(db).resolve(pm_id))


async def _creation_client(request: Request, db: AsyncSession):
    # Only a separately issued PM audience user delegation may create a project.
    # Never silently upgrade phase1's global read-only reference configuration.
    from app.domains.auth.oidc.service import pm_delegate
    token = await pm_delegate(request, db)
    return PMCreateClient(getattr(settings, "MDM_PM_API_URL", ""), token)


async def _manual_reference(request: Request, db: AsyncSession, *, required):
    if getattr(request.state, "oidc_session", None) is None:
        return None  # Existing native mode retains its explicitly configured phase1 identity.
    from app.domains.auth.oidc.service import pm_delegate
    try:
        token = await pm_delegate(request, db)
    except AppError as exc:
        if required or exc.error_type != "pm_delegation_required":
            raise
        token = ""  # Keep snapshots readable without falling back to a different principal.
    return PMReferenceClient(getattr(settings, "MDM_PM_API_URL", ""), token)


@router.get("/integration/pm/owners")
async def pm_owners(request: Request, user: User = Depends(require_permission("project:update")), db: AsyncSession = Depends(get_db)):
    return success(data=await (await _creation_client(request, db)).owners())


@router.get("/projects/{code}/pm-create")
async def get_pm_creation(code: str, user: User = Depends(require_permission("project:read")), db: AsyncSession = Depends(get_db)):
    return success(data=await ProjectPMCreateService(db, None).get(code))


@router.post("/projects/{code}/pm-create")
async def create_pm_project(code: str, payload: CreatePMProject, request: Request,
                            user: User = Depends(require_permission("project:update")), db: AsyncSession = Depends(get_db)):
    client = await _creation_client(request, db)
    service = ProjectPMCreateService(db, client, source_id=getattr(settings, "MDM_PM_SOURCE_ID", "mdm"))
    return success(data=await service.create(code, payload, user))


@router.post("/projects/{code}/pm-create/retry")
async def retry_pm_project(code: str, request: Request,
                           user: User = Depends(require_permission("project:update")), db: AsyncSession = Depends(get_db)):
    client = await _creation_client(request, db)
    service = ProjectPMCreateService(db, client, source_id=getattr(settings, "MDM_PM_SOURCE_ID", "mdm"))
    return success(data=await service.retry(code, user))
