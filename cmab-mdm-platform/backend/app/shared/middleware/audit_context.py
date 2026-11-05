"""
审计上下文中间件 - 提取请求级网络信息（IP、UA），写入 request.state 与 ContextVar

用户信息（user_id、username）在认证后由 get_current_user 写入 ContextVar；
注入到 PostgreSQL session 由 get_db / get_current_user 通过 set_audit_session_vars 完成。
"""
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

from app.shared.audit_context import audit_ip


class AuditContextMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        ip = request.client.host if request.client else "unknown"
        request.state.ip_address = ip
        request.state.user_agent = request.headers.get("User-Agent", "")
        audit_ip.set(ip)
        return await call_next(request)
