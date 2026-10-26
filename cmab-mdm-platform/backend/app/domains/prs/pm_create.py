"""Durable create-and-link saga. Remote calls occur outside MDM transactions."""
import asyncio
import json
import re
from contextlib import suppress
from datetime import UTC, date, datetime, timedelta
from hashlib import sha256
from typing import Literal
from urllib.parse import quote
from uuid import UUID, uuid4

import httpx
from pydantic import BaseModel, ConfigDict, Field, StrictBool, ValidationError, model_validator
from sqlalchemy import or_, select, text

from app.core.config import settings
from app.core.exceptions import AppError, BadRequestError, ConflictError, NotFoundError
from app.domains.prs.models import ProjectPMCreateRequest, ProjectPMLink
from app.domains.prs.pm_links import ProjectPMLinkService
from app.domains.prs.pm_reference import PMReference, safe_base_url
from app.domains.prs.services import ProjectService

Stage = Literal["临床前", "IND", "Ph1/2", "Ph3", "BLA", "商业化", "上市后"]


class PMProjectInput(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    code: str = Field(min_length=1, max_length=40)
    name: str = Field(min_length=1, max_length=200)
    product_type: Literal["单抗", "多抗", "其他"]
    current_stage: Stage
    target_stage: Stage
    owner_id: str = Field(min_length=1, max_length=64)
    planned_start: date
    planned_end: date
    description: str | None = Field(default=None, max_length=10000)

    @model_validator(mode="after")
    def safe_fields(self):
        if self.planned_end < self.planned_start:
            raise ValueError("计划结束不能早于计划开始")
        if any(re.search(r"[\x00-\x1f\x7f]", value) for value in [self.code, self.name, self.owner_id]):
            raise ValueError("项目编号、名称和负责人ID不能含控制字符")
        return self


class CreatePMProject(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    client_request_id: UUID
    change_reason: str = Field(min_length=5, max_length=1000)
    project: PMProjectInput


class PMCreateReceipt(BaseModel):
    request_id: UUID
    source_id: str = Field(min_length=1, max_length=64)
    source_project_id: str = Field(min_length=1, max_length=32, pattern=r"^[0-9]+$")
    project_id: str = Field(min_length=1, max_length=64, pattern=r"^[A-Za-z0-9][A-Za-z0-9_.-]*$")
    code: str = Field(min_length=1, max_length=40)
    name: str = Field(min_length=1, max_length=200)
    status: str = Field(min_length=1, max_length=20)
    bindable: StrictBool
    created_by: str = Field(min_length=1, max_length=64)
    project: PMReference

    @model_validator(mode="after")
    def matching_reference(self):
        if (self.project.id, self.project.code, self.project.name, self.project.status, self.project.bindable) != (
            self.project_id, self.code, self.name, self.status, self.bindable,
        ) or self.bindable != (self.status in {"活跃", "暂停"}):
            raise ValueError("Inconsistent PM receipt")
        return self


class PMCreateRemoteError(AppError):
    code = 50371
    http_status = 503
    error_type = "pm_create_unavailable"
    default_message = "PM 创建结果暂不能确认，请使用原请求重试，不要另建项目"


class PMCreatePermissionError(AppError):
    code = 40371
    http_status = 403
    error_type = "pm_create_permission_denied"
    default_message = "当前委托身份没有 PM 创建权限，请确认该用户的 PM 权限后重试原请求"


class PMCreateConflictError(AppError):
    code = 40971
    http_status = 409
    error_type = "pm_create_conflict"
    default_message = "PM 请求或项目已存在冲突，请核对原请求状态，不能换键重复创建"


class PMCreateRejectedError(AppError):
    code = 40071
    http_status = 400
    error_type = "pm_create_rejected"
    default_message = "PM 拒绝创建输入，请核对已保存的请求并进行对账，不能自动改写原请求"


class PMCreateClient:
    deadline_seconds = 8

    def __init__(self, base: str, token: str, *, transport=None):
        self.base, self.token, self.transport = base, token, transport

    async def _request(self, method: str, path: str, payload=None):
        if not self.base or not self.token:
            raise PMCreateRemoteError("尚未配置 PM 用户委托访问")
        try:
            base = safe_base_url(self.base)
            async with (
                asyncio.timeout(self.deadline_seconds),
                httpx.AsyncClient(timeout=6, trust_env=False, follow_redirects=False, transport=self.transport) as client,
                client.stream(method, base + "/api/v1/integration/mdm/" + path,
                              json=payload, headers={"Authorization": "Bearer " + self.token}) as response,
            ):
                if response.status_code == 404 and method == "GET" and path.startswith("projects/"):
                    return None
                if response.status_code in {401, 403}:
                    raise PMCreatePermissionError()
                if response.status_code == 409:
                    raise PMCreateConflictError()
                if response.status_code in {400, 422}:
                    raise PMCreateRejectedError()
                if response.status_code not in {200, 201}:
                    raise PMCreateRemoteError()
                data = bytearray()
                async for chunk in response.aiter_bytes():
                    data.extend(chunk)
                    if len(data) > 65536:
                        raise PMCreateRemoteError()
            return json.loads(data)
        except (TimeoutError, ValueError, httpx.HTTPError):
            # No upstream body, headers, exception URL or credential enters a response/log.
            raise PMCreateRemoteError() from None

    async def lookup(self, request_id: UUID | str):
        value = await self._request("GET", "projects/" + quote(str(request_id), safe=""))
        if value is None:
            return None
        try:
            result = PMCreateReceipt.model_validate(value)
            if str(result.request_id) != str(request_id):
                raise ValueError("Wrong request")
            return result
        except (ValidationError, ValueError):
            raise PMCreateRemoteError() from None

    async def create(self, request: dict):
        value = await self._request("POST", "projects", request)
        try:
            result = PMCreateReceipt.model_validate(value)
            validate_receipt(result, request)
            return result
        except (ValidationError, ValueError):
            raise PMCreateRemoteError() from None

    async def owners(self):
        value = await self._request("GET", "owners")
        try:
            if not isinstance(value, dict) or not isinstance(value["items"], list) or len(value["items"]) > 500:
                raise ValueError("Invalid owner list")
            items = []
            for item in value["items"]:
                identifier, name = item["id"], item["display_name"]
                if not isinstance(identifier, str) or not 0 < len(identifier) <= 64 or not isinstance(name, str) or not 0 < len(name) <= 200:
                    raise ValueError("Invalid owner")
                items.append({"id": identifier, "display_name": name})
            current = value["current_user_id"]
            options = value["options"]
            if not isinstance(current, str) or not 0 < len(current) <= 64:
                raise ValueError("Invalid user")
            normalized = {}
            for key in ["product_types", "stages"]:
                values = options[key]
                if not isinstance(values, list) or not 0 < len(values) <= 50 or any(not isinstance(v, str) or not 0 < len(v) <= 64 for v in values):
                    raise ValueError("Invalid options")
                normalized[key] = values
            return {"items": items, "current_user_id": current, "options": normalized}
        except (KeyError, TypeError, ValueError):
            raise PMCreateRemoteError() from None


def validate_receipt(receipt: PMCreateReceipt, request: dict):
    if (str(receipt.request_id), receipt.source_id, receipt.source_project_id, receipt.code, receipt.name) != (
        request["request_id"], request["source_id"], request["source_project_id"], request["project"]["code"], request["project"]["name"],
    ):
        raise ValueError("Wrong PM receipt identity")


class ProjectPMCreateService:
    lease_seconds = 30

    def __init__(self, db, pm, *, source_id="mdm"):
        self.db, self.pm, self.source_id = db, pm, source_id
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,63}", source_id):
            raise PMCreateRemoteError("PM 来源命名空间配置无效")

    async def get(self, code):
        project = await ProjectService(self.db)._get_project_or_404(code)
        operation = (await self.db.execute(select(ProjectPMCreateRequest).where(ProjectPMCreateRequest.project_id == project.project_id).execution_options(populate_existing=True))).scalar_one_or_none()
        return {"operation": await self._describe(operation, project.project_code) if operation else None}

    async def create(self, code, body: CreatePMProject, user):
        canonical = {"project": body.project.model_dump(mode="json"), "change_reason": body.change_reason}
        fingerprint = sha256(json.dumps(canonical, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode()).hexdigest()
        key = int.from_bytes(sha256(("mdm-pm-create:" + str(body.client_request_id)).encode()).digest()[:8], signed=True)
        await self.db.execute(text("SELECT pg_advisory_xact_lock(:key)"), {"key": key})
        project = await ProjectService(self.db)._get_project_or_404(code, for_update=True)
        rows = (await self.db.execute(select(ProjectPMCreateRequest).where(or_(
            ProjectPMCreateRequest.project_id == project.project_id,
            ProjectPMCreateRequest.request_id == str(body.client_request_id),
        )).with_for_update().execution_options(populate_existing=True))).scalars().all()
        if rows:
            if len(rows) != 1 or rows[0].request_id != str(body.client_request_id) or rows[0].project_id != project.project_id or rows[0].payload_hash != fingerprint:
                raise ConflictError("登记项目已有其他创建请求，必须使用原请求核对或重试")
            if rows[0].requested_by != user.user_id:
                raise ConflictError("必须由原发起人恢复该 PM 创建请求")
        else:
            link = (await self.db.execute(select(ProjectPMLink).where(ProjectPMLink.project_id == project.project_id))).scalar_one_or_none()
            if link:
                raise ConflictError("登记项目已有关联，不能再创建执行项目")
            if project.status in {"completed", "terminated", "cancelled"}:
                raise BadRequestError("已关闭的登记项目不能创建执行项目")
            self.db.add(ProjectPMCreateRequest(request_id=str(body.client_request_id), project_id=project.project_id,
                source_id=self.source_id, requested_by=user.user_id, request_payload=canonical,
                payload_hash=fingerprint, change_reason=body.change_reason, status="pending", attempts=0))
        await self.db.commit()
        return await self._execute(code, str(body.client_request_id), user)

    async def retry(self, code, user):
        project = await ProjectService(self.db)._get_project_or_404(code)
        operation = (await self.db.execute(select(ProjectPMCreateRequest).where(ProjectPMCreateRequest.project_id == project.project_id).execution_options(populate_existing=True))).scalar_one_or_none()
        if operation is None:
            raise NotFoundError("该登记项目没有可恢复的 PM 创建请求")
        if operation.requested_by != user.user_id:
            raise ConflictError("必须由原发起人恢复该 PM 创建请求")
        request_id = operation.request_id
        await self.db.commit()
        return await self._execute(code, request_id, user)

    async def _execute(self, code, request_id, user):
        operation = (await self.db.execute(select(ProjectPMCreateRequest).where(ProjectPMCreateRequest.request_id == request_id).with_for_update().execution_options(populate_existing=True))).scalar_one()
        now = datetime.now(UTC)
        if operation.status in {"linked", "reconciliation_required"} or (operation.lease_expires_at and operation.lease_expires_at > now):
            await self.db.commit()
            return await self.get(code)
        claim = str(uuid4())
        operation.lease_owner, operation.lease_expires_at = claim, now + timedelta(seconds=self.lease_seconds)
        operation.status, operation.last_error = "in_progress", None
        operation.attempts += 1
        operation.updated_at = now
        request = {"request_id": request_id, "source_id": operation.source_id,
                   "source_project_id": str(operation.project_id), "project": operation.request_payload["project"]}
        known_remote = bool(operation.remote_receipt)
        await self.db.commit()  # Release all DB locks before the bounded HTTP call.
        try:
            remote = await self.pm.lookup(request_id)
            if remote is None:
                if known_remote:
                    raise PMCreateConflictError("PM 已知回执丢失，需对账，禁止重建")
                remote = await self.pm.create(request)
            try:
                validate_receipt(remote, request)
            except ValueError:
                raise PMCreateRemoteError() from None
            await self._remember_remote(request_id, claim, remote)
            return await self._finish(code, request_id, claim, remote, user)
        except PMCreatePermissionError:
            await self._fail(request_id, claim, "retryable_error", "pm_permission_denied")
            raise
        except PMCreateConflictError:
            await self._fail(request_id, claim, "reconciliation_required", "pm_conflict")
            raise
        except PMCreateRejectedError:
            await self._fail(request_id, claim, "reconciliation_required", "pm_input_rejected")
            raise
        except PMCreateRemoteError:
            await self._fail(request_id, claim, "retryable_error", "pm_unavailable")
            return await self.get(code)

    async def _remember_remote(self, request_id, claim, remote):
        row = (await self.db.execute(select(ProjectPMCreateRequest).where(ProjectPMCreateRequest.request_id == request_id).with_for_update().execution_options(populate_existing=True))).scalar_one()
        if row.lease_owner == claim:
            row.remote_receipt, row.remote_project_id = remote.model_dump(mode="json"), remote.project_id
            row.status, row.updated_at = "remote_created", datetime.now(UTC)
        await self.db.commit()

    async def _finish(self, code, request_id, claim, remote, user):
        row = (await self.db.execute(select(ProjectPMCreateRequest).where(ProjectPMCreateRequest.request_id == request_id).execution_options(populate_existing=True))).scalar_one()
        if row.lease_owner != claim:
            await self.db.commit()
            return await self.get(code)
        reason = row.change_reason
        try:
            await ProjectPMLinkService(self.db).bind_verified(code, remote.project, reason, user,
                commit=False, creation_request_id=request_id)
        except (ConflictError, BadRequestError, NotFoundError):
            await self.db.rollback()
            await self._fail(request_id, claim, "reconciliation_required", "local_link_conflict")
            return await self.get(code)
        row = (await self.db.execute(select(ProjectPMCreateRequest).where(ProjectPMCreateRequest.request_id == request_id).with_for_update().execution_options(populate_existing=True))).scalar_one()
        if row.lease_owner != claim:
            await self.db.rollback()
            return await self.get(code)
        row.status, row.last_error, row.updated_at = "linked", None, datetime.now(UTC)
        row.lease_owner, row.lease_expires_at = None, None
        await self.db.commit()  # Mapping, its single audit event and completion are atomic.
        return await self.get(code)

    async def _fail(self, request_id, claim, status, reason):
        row = (await self.db.execute(select(ProjectPMCreateRequest).where(ProjectPMCreateRequest.request_id == request_id).with_for_update().execution_options(populate_existing=True))).scalar_one()
        if row.lease_owner == claim:
            row.status, row.last_error, row.updated_at = status, reason, datetime.now(UTC)
            row.lease_owner, row.lease_expires_at = None, None
        await self.db.commit()

    async def _describe(self, operation, code):
        link = (await self.db.execute(select(ProjectPMLink).where(ProjectPMLink.project_id == operation.project_id))).scalar_one_or_none()
        now = datetime.now(UTC)
        url = None
        if operation.status == "linked" and link:
            with suppress(ValueError):
                url = safe_base_url(settings.PM_PUBLIC_URL) + "/projects/" + quote(link.pm_project_id, safe="")
        return {"request_id": operation.request_id, "project_code": code, "status": operation.status,
                "attempts": operation.attempts, "created_at": operation.created_at.isoformat(),
                "updated_at": operation.updated_at.isoformat(), "remote_project_id": operation.remote_project_id,
                "last_error": operation.last_error, "project": operation.request_payload["project"],
                "can_retry": operation.status not in {"linked", "reconciliation_required"} and (operation.lease_expires_at is None or operation.lease_expires_at <= now),
                "link": {"link_id": link.link_id, "pm_project_id": link.pm_project_id} if link else None,
                "pm_url": url}
