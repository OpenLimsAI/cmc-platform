"""Bounded PM read-only reference client. MDM session tokens never enter this client."""
import asyncio
import re
from urllib.parse import quote, urlsplit

import httpx
from pydantic import BaseModel, Field, StrictBool, ValidationError

from app.core.exceptions import AppError, NotFoundError


class ReferenceUnavailableError(AppError):
    code = 50310
    http_status = 503
    error_type = "pm_reference_unavailable"
    default_message = "PM 项目核验不可用，请检查已批准的只读访问配置"


def safe_base_url(value: str) -> str:
    """HTTPS deployment root or explicit loopback HTTP; no identity, redirects or encoding."""
    try:
        parsed = urlsplit(value)
        valid = (
            bool(value) and value == value.strip()
            and not re.search(r"[\x00-\x20\x7f\\%]", value)
            and parsed.scheme in {"https", "http"} and bool(parsed.hostname)
            and not parsed.username and not parsed.password
            and not parsed.query and not parsed.fragment
            and (parsed.scheme == "https" or parsed.hostname in {"localhost", "127.0.0.1", "::1"})
            and all(segment not in {".", ".."} for segment in parsed.path.split("/"))
            and (parsed.port is None or 1 <= parsed.port <= 65535)
        )
    except ValueError as exc:
        raise ValueError("Unsafe application URL") from exc
    if not valid:
        raise ValueError("Unsafe application URL")
    return value.rstrip("/")


class PMReference(BaseModel):
    id: str = Field(min_length=1, max_length=64)
    code: str = Field(min_length=1, max_length=40)
    name: str = Field(min_length=1, max_length=200)
    status: str = Field(min_length=1, max_length=20)
    bindable: StrictBool


class PMReferenceClient:
    deadline_seconds: float = 5

    def __init__(self, base: str, token: str, *, transport=None):
        self.base, self.token, self.transport = base, token, transport

    async def get(self, project_id: str) -> PMReference:
        if not self.token or not self.base:
            raise ReferenceUnavailableError("尚未配置已批准的 PM 项目核验身份")
        try:
            base = safe_base_url(self.base)
            async with (
                asyncio.timeout(self.deadline_seconds),
                httpx.AsyncClient(timeout=3, follow_redirects=False, trust_env=False, transport=self.transport) as client,
                client.stream("GET", base + "/api/v1/projects/" + quote(project_id, safe="") + "/integration-reference",
                              headers={"Authorization": "Bearer " + self.token}) as response,
            ):
                if response.status_code == 404:
                    raise NotFoundError("PM 项目不存在或核验身份无权访问")
                if response.status_code != 200:
                    raise ReferenceUnavailableError()
                body = bytearray()
                async for chunk in response.aiter_bytes():
                    body.extend(chunk)
                    if len(body) > 16384:
                        raise ReferenceUnavailableError()
            result = PMReference.model_validate_json(body)
            if result.id != project_id or result.bindable != (result.status in {"活跃", "暂停"}):
                raise ReferenceUnavailableError()
            return result
        except (TimeoutError, ValueError, ValidationError, httpx.HTTPError) as exc:
            # Never expose upstream exception text, request headers or credentials.
            raise ReferenceUnavailableError() from exc
