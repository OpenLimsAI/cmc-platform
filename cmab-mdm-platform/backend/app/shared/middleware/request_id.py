"""
请求 ID 中间件 - 为每个请求分配唯一 ID 用于链路追踪
"""
from uuid import uuid4

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.shared.audit_context import audit_request_id


class RequestIDMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        request_id = request.headers.get("X-Request-ID") or f"req_{uuid4().hex[:16]}"
        request.state.request_id = request_id
        audit_request_id.set(request_id)
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response
