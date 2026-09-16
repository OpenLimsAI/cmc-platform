"""只展示可信身份与能力；登录/刷新/登出直接由门户同源 MDM 处理。"""
from fastapi import APIRouter, Depends, Response

from app.core.auth import CurrentUser, require_user
from app.core.config import Settings, get_auth_settings
from app.core.envelope import envelope
from app.core.security import authentication_required, auth_configured

router = APIRouter(prefix="/auth", tags=["auth"])


@router.get("/status")
def auth_status(auth_settings: Settings = Depends(get_auth_settings)) -> dict:
    return envelope(data={
        "auth_required": authentication_required(auth_settings),
        "configured": auth_configured(auth_settings),
    })


@router.get("/me")
def current_user(
    response: Response,
    user: CurrentUser = Depends(require_user),
    auth_settings: Settings = Depends(get_auth_settings),
) -> dict:
    response.headers["Cache-Control"] = "no-store"
    return envelope(data={
        "username": user.username,
        "full_name": user.full_name,
        "subject": user.subject,
        "roles": list(user.roles),
        "can_read": user.has_any_role(auth_settings.read_roles),
        "can_preview": user.has_any_role(auth_settings.import_preview_roles),
        "can_commit": False,
    })
