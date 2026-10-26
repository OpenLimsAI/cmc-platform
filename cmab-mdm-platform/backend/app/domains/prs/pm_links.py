"""One-to-one mappings: MDM transactions only, no cross-database writes."""
from contextlib import suppress
from datetime import UTC, datetime
from hashlib import sha256
from urllib.parse import quote

from sqlalchemy import or_, select, text

from app.core.config import settings
from app.core.exceptions import BadRequestError, ConflictError, NotFoundError
from app.domains.audit.models import AuditLog
from app.domains.prs.models import Project, ProjectPMCreateRequest, ProjectPMLink
from app.domains.prs.pm_reference import PMReferenceClient, ReferenceUnavailableError, safe_base_url
from app.domains.prs.services import ProjectService
from app.shared.audit_context import audit_request_id


class ProjectPMLinkService:
    def __init__(self, db, reference=None):
        self.db = db
        self.reference = reference or PMReferenceClient(
            settings.PM_REFERENCE_API_URL,
            settings.PM_REFERENCE_ACCESS_TOKEN.get_secret_value() if settings.PM_REFERENCE_ACCESS_TOKEN else "",
        )

    async def bind(self, code, pm_id, reason, user):
        return await self._bind(code, pm_id, reason, user)

    async def bind_verified(self, code, reference, reason, user, *, commit=True, creation_request_id=None):
        """Internal creation receipt only; not an API accepting browser summaries."""
        return await self._bind(code, reference.id, reason, user, verified=reference,
                                commit=commit, creation_request_id=creation_request_id)

    async def _bind(self, code, pm_id, reason, user, *, verified=None, commit=True, creation_request_id=None):
        # Global PM-id lock followed by local project row lock gives stable ordering.
        key = int.from_bytes(sha256(("mdm-pm:" + pm_id).encode()).digest()[:8], signed=True)
        await self.db.execute(text("SELECT pg_advisory_xact_lock(:key)"), {"key": key})
        project = await ProjectService(self.db)._get_project_or_404(code, for_update=True)
        creation = (await self.db.execute(select(ProjectPMCreateRequest).where(
            ProjectPMCreateRequest.project_id == project.project_id,
        ))).scalar_one_or_none()
        if creation and creation.status != "linked" and creation.request_id != creation_request_id:
            raise ConflictError("已有 PM 创建请求，必须先恢复或对账，不能另行绑定")
        existing = (await self.db.execute(select(ProjectPMLink).where(or_(
            ProjectPMLink.project_id == project.project_id, ProjectPMLink.pm_project_id == pm_id,
        )))).scalars().all()
        if existing:
            if len(existing) == 1 and existing[0].project_id == project.project_id and existing[0].pm_project_id == pm_id:
                return await self.describe(existing[0], verified=verified)
            raise ConflictError("登记项目或 PM 执行项目已有其他关联，不允许自动改绑")
        if project.status in {"completed", "terminated", "cancelled"}:
            raise BadRequestError("已关闭的登记项目不能建立新执行关联")
        reference = verified or await self.reference.get(pm_id)
        if not reference.bindable:
            raise BadRequestError("已完成或归档的 PM 项目不能建立新关联")
        link = ProjectPMLink(project_id=project.project_id, pm_project_id=reference.id,
                             pm_project_code=reference.code, pm_project_name=reference.name,
                             verified_at=datetime.now(UTC), created_by=user.user_id, change_reason=reason)
        self.db.add(link)
        await self.db.flush()
        self.db.add(AuditLog(user_id=user.user_id, username=user.username, action="CREATE",
                             entity_schema="prs", entity_table="project_pm_link", entity_id=link.link_id,
                             entity_code=code, reason=reason, request_id=audit_request_id.get(),
                             change_summary="建立一对一 PM 执行项目关联",
                             extra={"project_id": project.project_id, "pm_project_id": pm_id}))
        if commit:
            await self.db.commit()
        return await self.describe(link, verified=reference)

    async def get(self, code):
        project = await ProjectService(self.db)._get_project_or_404(code)
        link = (await self.db.execute(select(ProjectPMLink).where(ProjectPMLink.project_id == project.project_id))).scalar_one_or_none()
        return await self.describe(link)

    async def resolve(self, pm_id):
        project = (await self.db.execute(select(Project).join(ProjectPMLink, ProjectPMLink.project_id == Project.project_id)
                       .where(ProjectPMLink.pm_project_id == pm_id, Project.deleted_at.is_(None)))).scalar_one_or_none()
        if project is None:
            raise NotFoundError("该 PM 项目尚未关联有效的 MDM 登记项目")
        return {"project_code": project.project_code}

    async def describe(self, link, verified=None):
        if link is None:
            return {"link": None, "remote_status": "unlinked", "pm_url": None, "reference": None}
        status = "verified"
        try:
            reference = verified or await self.reference.get(link.pm_project_id)
            if not reference.bindable:
                status = "inactive"
        except NotFoundError:
            status, reference = "missing", None
        except ReferenceUnavailableError:
            status = "not_configured" if not getattr(self.reference, "base", None) or not getattr(self.reference, "token", None) else "unavailable"
            reference = None
        url = None
        if status in {"verified", "inactive"}:
            with suppress(ValueError):
                url = safe_base_url(settings.PM_PUBLIC_URL) + "/projects/" + quote(link.pm_project_id, safe="")
        return {"link": {"link_id": link.link_id, "project_id": link.project_id,
                         "pm_project_id": link.pm_project_id, "pm_project_code": link.pm_project_code,
                         "pm_project_name": link.pm_project_name, "verified_at": link.verified_at.isoformat(),
                         "created_at": link.created_at.isoformat(), "created_by": link.created_by},
                "remote_status": status, "reference": reference.model_dump() if reference else None, "pm_url": url}
