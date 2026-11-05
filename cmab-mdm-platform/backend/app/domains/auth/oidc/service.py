"""Explicit MDM identity mapping, bounded opaque sessions, and user delegation."""
import base64
import hashlib
import json
import secrets
import time
from datetime import UTC, datetime, timedelta

from cryptography.fernet import Fernet, InvalidToken
from sqlalchemy import and_, delete, or_, select, text, update
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.core.exceptions import (
    AccountDisabledError,
    AppError,
    ConflictError,
    PermissionDeniedError,
    TokenInvalidError,
)
from app.domains.audit.models import AuditLog
from app.domains.auth.models import LoginHistory, User
from app.domains.auth.oidc.config import configured
from app.domains.auth.oidc.models import OIDCIdentity, OIDCLogin, OIDCLogoutReplay, OIDCSession
from app.domains.auth.oidc.protocol import OIDCError, digest, pkce_pair, safe_return_to
from app.domains.auth.oidc.provider import OIDCProvider
from app.domains.auth.services import AuthService
from app.domains.auth.session_policy import load_session_policy
from app.shared.audit_context import audit_ip, audit_request_id

SESSION_COOKIE = "mdm_oidc_session"
LOGIN_COOKIE = "mdm_oidc_login"


def _cipher():
    key = hashlib.sha256(("mdm-oidc-state-v1:" + settings.SECRET_KEY).encode()).digest()
    return Fernet(base64.urlsafe_b64encode(key))


def seal(value):
    return _cipher().encrypt(json.dumps(value, separators=(",", ":")).encode()).decode()


def unseal(value):
    try:
        return json.loads(_cipher().decrypt(value.encode()))
    except (InvalidToken, ValueError, TypeError):
        raise TokenInvalidError("会话已失效，请重新登录") from None


def password_version(user):
    return user.password_changed_at.astimezone(UTC).isoformat() if user.password_changed_at else None


async def _revoke_session_id(db, session_id):
    if not session_id:
        return
    changed = (await db.execute(update(OIDCSession).where(OIDCSession.id == session_id,
        OIDCSession.revoked_at.is_(None)).values(revoked_at=datetime.now(UTC)).returning(OIDCSession.identity_id))).scalar_one_or_none()
    if changed is not None:
        identity = await db.get(OIDCIdentity, changed)
        assert identity is not None
        user = await db.get(User, identity.user_id)
        assert user is not None
        db.add(AuditLog(user_id=user.user_id, username=user.username, action="LOGOUT",
            entity_schema="auth", entity_table="oidc_session", entity_code=session_id,
            reason="OIDC 本地会话撤销", request_id=audit_request_id.get(), ip_address=audit_ip.get()))


async def revoke_session(db, raw):
    """Local revocation must remain available even if provider config is broken."""
    if not raw:
        return
    await _revoke_session_id(db, digest(raw))
    await db.commit()


async def cancel_login(db, state):
    """Cancel only the transaction identified by this browser's opaque cookie.

    A short-lived completed receipt also fences a callback response that has not
    reached the browser yet. It contains only the created session's hash ID.
    """
    if not state or len(state) > 128:
        return
    item = (await db.execute(delete(OIDCLogin).where(OIDCLogin.id == digest(state)).returning(OIDCLogin))).scalar_one_or_none()
    if item is not None:
        try:
            data = unseal(item.secret_data)
        except TokenInvalidError:
            data = {}
        session_id = data.get("completed_session_id") if isinstance(data, dict) else None
        if isinstance(session_id, str) and len(session_id) == 64:
            await _revoke_session_id(db, session_id)
    await db.commit()


class PMDelegationRequiredError(PermissionDeniedError):
    error_type = "pm_delegation_required"
    default_message = "请先通过统一身份授权当前用户调用 PM"


class OIDCUnavailableError(AppError):
    code = 50312
    http_status = 503
    error_type = "identity_unavailable"
    default_message = "统一身份服务暂不可用，未放行当前请求"


def require_origin(request, config, *, allow_missing=False):
    origin = request.headers.get("origin")
    if origin != config.origin and not (allow_missing and not origin):
        raise PermissionDeniedError("请求来源不匹配")


class OIDCService:
    def __init__(self, db, *, config=None, provider=None):
        self.db = db
        self.config = config or configured()
        self.provider = provider or OIDCProvider(self.config)

    async def bind_identity(self, subject, user_id, *, actor, reason):
        if not subject or len(subject) > 255 or not isinstance(user_id, int) or len(reason.strip()) < 5:
            raise PermissionDeniedError("必须显式确认身份、数字ID与映射原因")
        permissions = await AuthService(self.db)._get_user_permissions(actor)
        if actor.status != "active" or ("user:manage" not in permissions and not any(r.role_code == "SYS_ADMIN" for r in actor.roles)):
            raise PermissionDeniedError()
        key = int.from_bytes(hashlib.sha256((self.config.issuer + ":" + subject).encode()).digest()[:8], signed=True)
        await self.db.execute(text("SELECT pg_advisory_xact_lock(:key)"), {"key": key})
        user = (await self.db.execute(select(User).where(User.user_id == user_id, User.deleted_at.is_(None)).with_for_update())).scalar_one_or_none()
        if user is None:
            raise PermissionDeniedError("映射目标不存在")
        existing = (await self.db.execute(select(OIDCIdentity).where(OIDCIdentity.issuer == self.config.issuer,
            or_(OIDCIdentity.subject == subject, OIDCIdentity.user_id == user_id)))).scalars().all()
        if existing:
            if len(existing) == 1 and existing[0].subject == subject and existing[0].user_id == user_id:
                return existing[0]
            raise ConflictError("该身份或数字用户已有其他映射，不允许自动改绑")
        item = OIDCIdentity(issuer=self.config.issuer, subject=subject, user_id=user_id,
                            active=True, created_by=actor.user_id, change_reason=reason.strip())
        self.db.add(item)
        await self.db.flush()
        self.db.add(AuditLog(user_id=actor.user_id, username=actor.username, action="CREATE", entity_schema="auth",
            entity_table="oidc_identity", entity_id=item.identity_id, reason=reason.strip(),
            request_id=audit_request_id.get(), change_summary="显式关联 OIDC 身份与原数字用户"))
        await self.db.commit()
        return item

    async def _identity_user(self, issuer, subject):
        identity = (await self.db.execute(select(OIDCIdentity).where(OIDCIdentity.issuer == issuer,
            OIDCIdentity.subject == subject, OIDCIdentity.active.is_(True)))).scalar_one_or_none()
        if identity is None:
            raise PermissionDeniedError("统一身份尚未显式映射到 MDM，或映射已停用")
        user = (await self.db.execute(select(User).options(selectinload(User.roles)).where(
            User.user_id == identity.user_id, User.deleted_at.is_(None)))).scalar_one_or_none()
        if user is None or user.status != "active":
            raise AccountDisabledError()
        return identity, user

    async def _was_logged_out(self, subject, issued_at, sid=None):
        now = datetime.now(UTC)
        conditions = [OIDCLogoutReplay.issuer == self.config.issuer, OIDCLogoutReplay.expires_at > now,
                      OIDCLogoutReplay.issued_at >= issued_at]
        match = OIDCLogoutReplay.subject == subject
        if settings.MDM_OIDC_DEVICE_LOGOUT_ENABLED:
            match = and_(or_(OIDCLogoutReplay.subject == subject, OIDCLogoutReplay.subject.is_(None)),
                         or_(OIDCLogoutReplay.sid.is_(None), OIDCLogoutReplay.sid == "", OIDCLogoutReplay.sid == sid))
        elif sid:
            match = or_(match, OIDCLogoutReplay.subject.is_(None) & (OIDCLogoutReplay.sid == sid))
        return (await self.db.execute(select(OIDCLogoutReplay.id).where(*conditions, match).limit(1))).scalar_one_or_none() is not None

    async def issue_session(self, claims, tokens, *, commit=True):
        if claims.get("iss") != self.config.issuer:
            raise TokenInvalidError()
        identity, user = await self._identity_user(claims["iss"], claims["sub"])
        if await self._was_logged_out(identity.subject, claims["iat"], claims.get("sid")):
            raise TokenInvalidError("该次身份认证已经注销，请重新发起登录")
        now = datetime.now(UTC)
        policy = await load_session_policy(self.db)
        expires = min(datetime.fromtimestamp(claims["exp"], UTC), now + timedelta(seconds=self.config.session_max_seconds),
                      now + timedelta(hours=policy.absolute_max_hours))
        if expires <= now:
            raise TokenInvalidError()
        raw = secrets.token_urlsafe(48)
        item = OIDCSession(id=digest(raw), identity_id=identity.identity_id, issued_at=now, expires_at=expires,
            idle_expires_at=min(expires, now + timedelta(minutes=policy.idle_minutes_for([r.role_code for r in user.roles]))),
            provider_issued_at=claims["iat"], provider_sid=claims.get("sid"), password_version=password_version(user),
            secret_data=seal({"access_token": tokens["access_token"], "client_id": self.config.client_id}))
        self.db.add(item)
        user.last_login_at = now
        self.db.add(LoginHistory(user_id=user.user_id, username_input=user.username, success=True, ip_address=audit_ip.get()))
        self.db.add(AuditLog(user_id=user.user_id, username=user.username, action="LOGIN", ip_address=audit_ip.get(),
            request_id=audit_request_id.get(), reason="OIDC 已验证并使用显式数字用户映射登录"))
        if commit:
            await self.db.commit()
        return raw, item

    async def current_session(self, raw):
        if not raw or len(raw) > 128:
            raise TokenInvalidError()
        self.db.info.pop("oidc_identity_presentation", None)
        item = (await self.db.execute(select(OIDCSession).where(OIDCSession.id == digest(raw)))).scalar_one_or_none()
        now = datetime.now(UTC)
        if item is None or item.revoked_at or item.expires_at <= now or item.idle_expires_at <= now:
            raise TokenInvalidError("统一登录会话已到期，请重新登录")
        identity = (await self.db.execute(select(OIDCIdentity).where(OIDCIdentity.identity_id == item.identity_id))).scalar_one()
        if not identity.active or identity.issuer != self.config.issuer or unseal(item.secret_data).get("client_id") != self.config.client_id:
            raise TokenInvalidError("身份映射已停用")
        _, user = await self._identity_user(identity.issuer, identity.subject)
        if item.password_version != password_version(user) or await self._was_logged_out(identity.subject, item.provider_issued_at, item.provider_sid):
            raise TokenInvalidError("统一登录会话已撤销")
        try:
            active = await self.provider.is_active(unseal(item.secret_data)["access_token"], subject=identity.subject)
        except OIDCError:
            raise OIDCUnavailableError() from None
        if not active:
            await self.revoke(raw)
            raise TokenInvalidError("统一身份凭证已撤销，请重新登录")
        presentation = getattr(self.provider, "identity_presentation", None)
        if isinstance(presentation, dict) and all(isinstance(presentation.get(key), str) for key in ("displayName", "identityUsername")):
            self.db.info["oidc_identity_presentation"] = {key: presentation[key] for key in ("displayName", "identityUsername")}
        policy = await load_session_policy(self.db)
        item.idle_expires_at = min(item.expires_at, now + timedelta(minutes=policy.idle_minutes_for([r.role_code for r in user.roles])))
        await self.db.commit()
        return user, item

    async def revoke(self, raw):
        await revoke_session(self.db, raw)

    async def begin(self, return_to, *, old_state=None, delegation_session=None):
        verifier, challenge = pkce_pair()
        state, nonce = secrets.token_urlsafe(48), secrets.token_urlsafe(48)
        delegation = delegation_session is not None
        if delegation and (not self.config.pm_client_id or not self.config.pm_client_secret):
            raise PMDelegationRequiredError("PM 委托客户端尚未配置")
        params = {"client_id": self.config.pm_client_id if delegation else self.config.client_id,
            "redirect_uri": self.config.callback(delegation), "response_type": "code", "scope": "openid profile email",
            "state": state, "nonce": nonce, "code_challenge_method": "S256", "code_challenge": challenge}
        url = await self.provider.authorization_url(params)
        if old_state:
            await self.db.execute(delete(OIDCLogin).where(OIDCLogin.id == digest(old_state)))
        await self.db.execute(delete(OIDCLogin).where(OIDCLogin.expires_at < datetime.now(UTC)))
        self.db.add(OIDCLogin(id=digest(state), expires_at=datetime.now(UTC) + timedelta(minutes=5),
            secret_data=seal({"verifier": verifier, "nonce": nonce, "return_to": safe_return_to(return_to),
                              "session_id": delegation_session.id if delegation else None, "delegation": delegation})))
        await self.db.commit()
        return state, url

    async def complete(self, code, state, cookie_state, *, raw_session=None, delegation=False):
        if not state or not cookie_state or len(state) > 128 or not secrets.compare_digest(state, cookie_state):
            raise OIDCError("state")
        item = (await self.db.execute(select(OIDCLogin).where(OIDCLogin.id == digest(state))
            .with_for_update().execution_options(populate_existing=True))).scalar_one_or_none()
        if item is None or item.expires_at < datetime.now(UTC):
            await self.db.commit()
            raise OIDCError("state")
        data = unseal(item.secret_data)
        if not isinstance(data, dict) or data.get("claimed") or data["delegation"] != delegation:
            await self.db.commit()
            raise OIDCError("state")
        data["claimed"] = True
        item.secret_data = seal(data)
        # Keep the cancellable transaction, but release all locks before HTTP.
        await self.db.commit()
        claims, tokens = await self.provider.exchange(code, data["verifier"], data["nonce"], delegation=delegation)
        session = None
        if delegation:
            _, session = await self.current_session(raw_session)
            identity = (await self.db.execute(select(OIDCIdentity).where(OIDCIdentity.identity_id == session.identity_id))).scalar_one()
            if session.id != data["session_id"] or identity.issuer != claims["iss"] or identity.subject != claims["sub"]:
                raise OIDCError("Delegated subject must match the MDM session")
        # Logout/native recovery may have cancelled while the provider answered.
        # Finalization and its short-lived receipt commit together under this lock.
        item = (await self.db.execute(select(OIDCLogin).where(OIDCLogin.id == digest(state))
            .with_for_update().execution_options(populate_existing=True))).scalar_one_or_none()
        if item is None or item.expires_at < datetime.now(UTC):
            await self.db.rollback()
            raise OIDCError("state")
        receipt = unseal(item.secret_data)
        if not isinstance(receipt, dict) or receipt.get("claimed") is not True or receipt.get("completed_session_id"):
            await self.db.rollback()
            raise OIDCError("state")
        if delegation:
            assert session is not None
            secret = unseal(session.secret_data)
            secret.update(pm_access_token=tokens["access_token"], pm_expires_at=tokens["expires_at"], pm_subject=claims["sub"])
            session.secret_data = seal(secret)
            item.secret_data = seal({**receipt, "completed_session_id": session.id})
            await self.db.commit()
            return None, session, data["return_to"]
        raw, session = await self.issue_session(claims, tokens, commit=False)
        item.secret_data = seal({**receipt, "completed_session_id": session.id})
        if raw_session:
            await _revoke_session_id(self.db, digest(raw_session))
        await self.db.commit()
        return raw, session, data["return_to"]

    async def backchannel(self, claims):
        now = datetime.now(UTC)
        key = digest(self.config.issuer + ":" + claims["jti"])
        lock = int.from_bytes(hashlib.sha256(key.encode()).digest()[:8], signed=True)
        await self.db.execute(text("SELECT pg_advisory_xact_lock(:key)"), {"key": lock})
        if await self.db.get(OIDCLogoutReplay, key):
            return
        self.db.add(OIDCLogoutReplay(id=key, issuer=self.config.issuer, subject=claims.get("sub"), sid=claims.get("sid"),
            issued_at=claims["iat"], expires_at=now + timedelta(seconds=self.config.session_max_seconds + 600)))
        # Fixed Casdoor 3.152 global logout can carry a different sid. Our documented
        # conservative policy invalidates all existing MDM sessions for verified sub.
        if claims.get("sub"):
            identities = select(OIDCIdentity.identity_id).where(OIDCIdentity.issuer == self.config.issuer, OIDCIdentity.subject == claims["sub"])
            condition = OIDCSession.identity_id.in_(identities)
        else:
            condition = OIDCSession.provider_sid == claims["sid"]
        if settings.MDM_OIDC_DEVICE_LOGOUT_ENABLED and claims.get("sid"):
            condition = and_(condition, OIDCSession.provider_sid == claims["sid"])
        await self.db.execute(update(OIDCSession).where(condition, OIDCSession.provider_issued_at <= claims["iat"]).values(revoked_at=now))
        await self.db.commit()


async def pm_delegate(request, db):
    if not settings.MDM_OIDC_ENABLED or not request.cookies.get(SESSION_COOKIE):
        raise PMDelegationRequiredError()
    service = OIDCService(db)
    _, session = await service.current_session(request.cookies[SESSION_COOKIE])
    request.state.oidc_session = session
    secret = unseal(session.secret_data)
    if not secret.get("pm_access_token") or secret.get("pm_expires_at", 0) <= time.time():
        raise PMDelegationRequiredError()
    return secret["pm_access_token"]
