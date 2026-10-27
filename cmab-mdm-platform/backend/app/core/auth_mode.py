"""Deployment policy for local password/JWT authentication, independent of signing."""
from app.core.config import settings
from app.core.exceptions import PermissionDeniedError


def require_native_auth_enabled() -> None:
    if not settings.MDM_NATIVE_LOGIN_ENABLED:
        raise PermissionDeniedError("原生登录未启用，请使用统一身份登录")
