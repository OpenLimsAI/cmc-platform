"""Authenticated mapping endpoints; existing MDM permissions and numeric identity."""
from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.responses import success
from app.domains.auth.models import User
from app.domains.prs.pm_links import ProjectPMLinkService
from app.shared.permissions import require_permission

router = APIRouter()


class BindPMProject(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    pm_project_id: str = Field(min_length=1, max_length=64, pattern=r"^[A-Za-z0-9][A-Za-z0-9_.-]*$")
    change_reason: str = Field(min_length=5, max_length=1000)


@router.get("/projects/{code}/pm-link")
async def get_pm_link(code: str, user: User = Depends(require_permission("project:read")), db: AsyncSession = Depends(get_db)):
    return success(data=await ProjectPMLinkService(db).get(code))


@router.post("/projects/{code}/pm-link")
async def bind_pm_link(code: str, payload: BindPMProject, user: User = Depends(require_permission("project:update")), db: AsyncSession = Depends(get_db)):
    return success(data=await ProjectPMLinkService(db).bind(code, payload.pm_project_id, payload.change_reason, user))


@router.get("/integration/pm-projects/{pm_id}")
async def resolve_pm_link(pm_id: str, user: User = Depends(require_permission("project:read")), db: AsyncSession = Depends(get_db)):
    return success(data=await ProjectPMLinkService(db).resolve(pm_id))
