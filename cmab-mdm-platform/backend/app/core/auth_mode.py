"""Deployment policy for local password/JWT authentication, independent of signing."""
from app.core.config import settings
from app.core.exceptions import PermissionDeniedError


def native_auth_enabled() -> bool:
    return settings.MDM_NATIVE_LOGIN_ENABLED and settings.MDM_SIGNATURE_MODE != "oidc_fresh"


def require_native_auth_enabled() -> None:
    if not native_auth_enabled():
        raise PermissionDeniedError("原生登录未启用，请使用统一身份登录")


def require_local_password_management() -> None:
    if settings.MDM_SIGNATURE_MODE == "oidc_fresh":
        raise PermissionDeniedError("密码由 Casdoor 管理，MDM 不接收或维护签名密码")
