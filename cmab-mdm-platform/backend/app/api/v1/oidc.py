"""Opt-in independent MDM OIDC session; no bearer tokens are returned to the browser."""
import time
from datetime import UTC, datetime
from urllib.parse import parse_qs, urlencode

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse, RedirectResponse
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.core.exceptions import (
    AccountDisabledError,
    AppError,
    PermissionDeniedError,
    TokenInvalidError,
    TokenMissingError,
)
from app.core.responses import success
from app.domains.auth.oidc.config import configured
from app.domains.auth.oidc.protocol import OIDCError
from app.domains.auth.oidc.service import (
    LOGIN_COOKIE,
    SESSION_COOKIE,
    OIDCService,
    cancel_login,
    require_origin,
    unseal,
)
from app.domains.auth.password_policy import requires_password_change
from app.domains.auth.services import AuthService
from app.shared.permissions import get_current_user

router = APIRouter()
HEADERS = {"Cache-Control": "no-store", "Pragma": "no-cache", "Referrer-Policy": "no-referrer"}


def _unavailable():
    return JSONResponse(status_code=503, content={"code": 50311, "message": "统一登录未启用或配置不可用，可使用已允许的原生恢复入口", "data": None}, headers=HEADERS)


def clear_session_cookie(response, config):
    response.delete_cookie(SESSION_COOKIE, path=config.cookie_path, secure=config.secure, httponly=True, samesite="lax")


def clear_login_cookie(response, config):
    response.delete_cookie(LOGIN_COOKIE, path=config.cookie_path, secure=config.secure, httponly=True, samesite="lax")


def _cookie(response, name, value, config, age):
    response.set_cookie(name, value, max_age=max(1, int(age)), path=config.cookie_path,
                        secure=config.secure, httponly=True, samesite="lax")


@router.get("/config")
async def oidc_config():
    # Configuration is local. Provider outages must not prevent explicit native recovery.
    enabled = settings.MDM_OIDC_ENABLED
    if enabled:
        try:
            configured()
        except OIDCError:
            enabled = False
    return JSONResponse(success(data={"enabled": enabled, "native_login_enabled": settings.MDM_NATIVE_LOGIN_ENABLED}), headers=HEADERS)


@router.get("/login")
@router.get("/pm-login")
async def oidc_login(request: Request, return_to: str = "/projects", db: AsyncSession = Depends(get_db)):
    try:
        service = OIDCService(db)
        delegation = request.url.path.endswith("/pm-login")
        session = None
        if delegation:
            # Apply the same live MDM authorization and password lifecycle gate.
            await get_current_user(request, authorization=None, db=db)
            _, session = await service.current_session(request.cookies.get(SESSION_COOKIE))
        state, url = await service.begin(return_to, old_state=request.cookies.get(LOGIN_COOKIE), delegation_session=session)
        response = RedirectResponse(url, status_code=303, headers=HEADERS)
        _cookie(response, LOGIN_COOKIE, state, service.config, 300)
        return response
    except OIDCError:
        return _unavailable()


@router.get("/callback")
@router.get("/pm-callback")
async def oidc_callback(request: Request, code: str = "", state: str = "", error: str = "", db: AsyncSession = Depends(get_db)):
    config = None
    failure = "disabled"
    try:
        service = OIDCService(db)
        config = service.config
        if error:
            raise OIDCError("provider")
        raw, session, target = await service.complete(code, state, request.cookies.get(LOGIN_COOKIE),
            raw_session=request.cookies.get(SESSION_COOKIE), delegation=request.url.path.endswith("/pm-callback"))
        response = RedirectResponse(config.public_url + "/auth-complete?" + urlencode({"return_to": target}), status_code=303, headers=HEADERS)
        response.delete_cookie(LOGIN_COOKIE, path=config.cookie_path, secure=config.secure, httponly=True, samesite="lax")
        if raw:
            _cookie(response, SESSION_COOKIE, raw, config, (session.expires_at - datetime.now(UTC)).total_seconds())
        return response
    except AccountDisabledError:
        failure = "account"
    except PermissionDeniedError:
        failure = "mapping"
    except TokenInvalidError:
        failure = "session"
    except OIDCError as exc:
        failure = "disabled" if not config else ("state" if str(exc) == "state" else "provider")
    if config:
        await db.rollback()
        await AuthService._persist_login_failure(user_id=None, username="oidc", ip=getattr(request.state, "ip_address", None),
            ua=getattr(request.state, "user_agent", None), failure_reason="oidc_" + failure)
    target = (config.public_url if config else "/mdm") + "/login?oidc_error=" + failure
    response = RedirectResponse(target, status_code=303, headers=HEADERS)
    if config:
        response.delete_cookie(LOGIN_COOKIE, path=config.cookie_path, secure=config.secure, httponly=True, samesite="lax")
    return response


@router.get("/session")
async def oidc_session(request: Request, db: AsyncSession = Depends(get_db)):
    if not settings.MDM_OIDC_ENABLED or not request.cookies.get(SESSION_COOKIE):
        raise TokenMissingError()
    user = await get_current_user(request, authorization=None, db=db)
    session = request.state.oidc_session
    permissions = await AuthService(db)._get_user_permissions(user)
    secret = unseal(session.secret_data)
    return JSONResponse(success(data={"mode": "oidc", "expires_at": session.expires_at.isoformat(),
        "pm_delegated": bool(secret.get("pm_access_token") and secret.get("pm_expires_at", 0) > time.time()),
        "user": {"user_id": user.user_id, "username": user.username, "full_name": user.full_name,
                 "department": user.department, "title": user.title, "must_change_password": requires_password_change(user),
                 "roles": [role.role_code for role in user.roles], "permissions": permissions}}), headers=HEADERS)


class LogoutRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    global_: bool = Field(default=False, alias="global")


@router.post("/logout")
async def oidc_logout(payload: LogoutRequest, request: Request, db: AsyncSession = Depends(get_db)):
    try:
        service = OIDCService(db)
    except OIDCError:
        return _unavailable()
    require_origin(request, service.config)
    raw = request.cookies.get(SESSION_COOKIE)
    access = None
    try:
        _, session = await service.current_session(raw)
        access = unseal(session.secret_data).get("access_token")
    except AppError:
        pass
    await cancel_login(db, request.cookies.get(LOGIN_COOKIE))
    await service.revoke(raw)
    global_ok = False
    data = {"local_logout": True, "global_logout": False, "login_url": service.config.public_url + "/login?reason=logout"}
    if payload.global_:
        if access:
            try:
                await service.provider.global_logout(access)
                global_ok = True
            except OIDCError:
                pass
        if not global_ok:
            data["warning"] = "MDM 已退出，但统一身份注销未确认；门户或 PM 会话可能仍有效。"
    data["global_logout"] = global_ok
    if global_ok:
        # No id_token_hint/access token in URL. Provider browser logout clears its
        # own cookie and only uses the client's explicitly registered local return.
        data["logout_url"] = service.config.issuer + "/api/logout?" + urlencode({
            "client_id": service.config.client_id, "post_logout_redirect_uri": data["login_url"]})
    response = JSONResponse(success(data=data), headers=HEADERS)
    clear_session_cookie(response, service.config)
    clear_login_cookie(response, service.config)
    return response


@router.post("/backchannel-logout")
async def backchannel_logout(request: Request, db: AsyncSession = Depends(get_db)):
    data = bytearray()
    async for chunk in request.stream():
        data.extend(chunk)
        if len(data) > 16384:
            raise PermissionDeniedError("注销通知超过限制")
    try:
        fields = parse_qs(data.decode(), strict_parsing=True)
        if set(fields) != {"logout_token"} or len(fields["logout_token"]) != 1:
            raise OIDCError()
        service = OIDCService(db)
        claims = await service.provider.verify_logout(fields["logout_token"][0])
        await service.backchannel(claims)
        return JSONResponse({"status": "ok"}, headers=HEADERS)
    except (OIDCError, ValueError, KeyError):
        raise PermissionDeniedError("注销通知无效") from None
