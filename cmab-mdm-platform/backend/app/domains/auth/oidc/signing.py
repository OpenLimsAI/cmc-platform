"""Fresh IdP authentication bound to a one-time, exact business transaction.

No password or token is accepted from the browser. The original MDM session is
never replaced. Provider exchange occurs outside row locks; finalization checks
cancellation and expiry again. Consumption is part of the business transaction.
"""
import secrets
import time
from datetime import UTC, datetime, timedelta
from typing import Any, Literal
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import (
    NotFoundError,
    PermissionDeniedError,
    SignatureInvalidError,
    StateInvalidError,
)
from app.domains.auth.models import User
from app.domains.auth.oidc.config import OIDCConfig, configured
from app.domains.auth.oidc.models import OIDCIdentity, OIDCSession, OIDCSignatureChallenge
from app.domains.auth.oidc.protocol import OIDCError, digest, pkce_pair, validate_fresh_auth
from app.domains.auth.oidc.provider import OIDCProvider
from app.domains.auth.oidc.service import seal, unseal
from app.shared.permissions import get_user_permissions
from app.shared.signature import compute_signed_content_hash


class SigningRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    entity_type: Literal["project", "substance", "asset"]
    entity_code: str = Field(min_length=1, max_length=32)
    action: str = Field(min_length=1, max_length=24, pattern=r"^[a-z_]+$")
    comment: str = Field(min_length=5, max_length=2000)
    reason: str = Field(min_length=5, max_length=2000)


async def descriptor(db: AsyncSession, request: SigningRequest, user: User) -> tuple[str, str, int, str, dict[str, Any]]:
    """Read actual server state and apply the same permissions/state machines."""
    from app.domains.ars import models as ars_models
    from app.domains.ars import services as ars
    from app.domains.prs import models as prs_models
    from app.domains.prs import services as prs
    from app.domains.srs import models as srs_models
    from app.domains.srs import services as srs

    domains: dict[str, tuple[str, Any, Any, str, tuple[str, ...]]] = {
        "project": ("prs", prs_models.Project, prs, "project:approve", ("project_code", "project_name")),
        "substance": ("srs", srs_models.Substance, srs, "substance:approve", ("substance_code", "internal_code", "preferred_name")),
        "asset": ("ars", ars_models.Asset, ars, "asset:update", ("asset_code", "internal_name", "current_phase")),
    }
    schema, model, domain, permission, fields = domains[request.entity_type]
    permissions = await get_user_permissions(user, db)
    if not any(r.role_code == "SYS_ADMIN" for r in user.roles) and not {permission, request.entity_type + ":sign"}.issubset(permissions):
        raise PermissionDeniedError("当前用户没有此业务操作及签名权限")
    code = getattr(model, request.entity_type + "_code")
    item = (await db.execute(select(model).where(code == request.entity_code, model.deleted_at.is_(None))
        .with_for_update().execution_options(populate_existing=True))).scalar_one_or_none()
    if item is None:
        raise NotFoundError()
    target = domain.STATE_MACHINE.get(request.action, {}).get(item.status)
    if not target or request.action not in domain.SIGNATURE_REQUIRED_ACTIONS:
        raise StateInvalidError("当前状态不能发起此签名动作")
    content = {field: getattr(item, field) for field in fields}
    content.update(current_status=item.status, target_status=target, version=item.version,
                   comment=request.comment, signature_reason=request.reason)
    return schema, request.entity_type, getattr(item, request.entity_type + "_id"), domain.ACTION_TO_MEANING[request.action], content


class SigningService:
    def __init__(self, db: AsyncSession, *, config: OIDCConfig | None = None, provider: OIDCProvider | None = None) -> None:
        self.db = db
        self.config = config or configured()
        if (settings.MDM_SIGNATURE_MODE != "oidc_fresh" or not self.config.signature_client_id
                or not self.config.signature_client_secret
                or self.config.signature_client_id in {self.config.client_id, self.config.pm_client_id}):
            raise OIDCError("Independent fresh signature authentication is unavailable")
        self.provider = provider or OIDCProvider(self.config)

    async def begin(self, request: SigningRequest, *, user: User, session: OIDCSession) -> dict[str, Any]:
        identity = await self.db.get(OIDCIdentity, session.identity_id)
        if identity is None or not identity.active or identity.user_id != user.user_id or identity.issuer != self.config.issuer:
            raise SignatureInvalidError("签名身份映射不可用")
        presentation = {}
        if self.config.signature_password_only:
            credentials = unseal(session.secret_data)
            if not isinstance(credentials, dict) or credentials.get("client_id") != self.config.client_id:
                raise OIDCError("Signing session audience is unavailable")
            access = credentials.get("access_token")
            if not isinstance(access, str) or not access:
                raise OIDCError("Signing session access is unavailable")
            # This network read is before acquiring the business row lock.
            presentation = {"login_hint": await self.provider.signing_login_hint(access, subject=identity.subject),
                            "language": "zh"}
        schema, table, entity_id, meaning, content = await descriptor(self.db, request, user)
        state, nonce = secrets.token_urlsafe(32), secrets.token_urlsafe(32)
        verifier, challenge = pkce_pair()
        now = datetime.now(UTC)
        item = OIDCSignatureChallenge(id=secrets.token_hex(32), session_id=session.id,
            identity_id=identity.identity_id, user_id=user.user_id, issuer=identity.issuer,
            subject=identity.subject, audience=self.config.signature_client_id,
            entity_schema=schema, entity_table=table, entity_id=entity_id,
            content_hash=compute_signed_content_hash(content), meaning=meaning, state_hash=digest(state),
            secret_data=seal({"verifier": verifier, "nonce": nonce}), status="pending",
            created_at=now, expires_at=now + timedelta(seconds=120))
        url = await self.provider.authorization_url({"client_id": item.audience,
            "redirect_uri": self.config.callback(signing=True), "response_type": "code", "scope": "openid profile",
            "prompt": "login", "max_age": "0", "state": state, "nonce": nonce,
            "code_challenge_method": "S256", "code_challenge": challenge, "popup": "1", "popup_type": "iframe",
            **presentation})
        self.db.add(item)
        await self.db.commit()
        parsed = urlsplit(self.config.issuer)
        return {"challenge_id": item.id, "state": state, "authorization_url": url,
            "issuer_origin": f"{parsed.scheme}://{parsed.netloc}", "expires_at": item.expires_at.isoformat()}

    async def _owned(self, challenge_id: str, *, user: User, session: OIDCSession, lock: bool = False) -> OIDCSignatureChallenge:
        statement = select(OIDCSignatureChallenge).where(OIDCSignatureChallenge.id == challenge_id)
        if lock:
            statement = statement.with_for_update().execution_options(populate_existing=True)
        item = (await self.db.execute(statement)).scalar_one_or_none()
        if (item is None or item.user_id != user.user_id or item.session_id != session.id
                or item.identity_id != session.identity_id or item.issuer != self.config.issuer
                or item.audience != self.config.signature_client_id):
            raise SignatureInvalidError("签名挑战不属于当前会话")
        return item

    async def complete(self, challenge_id: str, *, code: str, state: str, user: User, session: OIDCSession) -> dict[str, str]:
        item = await self._owned(challenge_id, user=user, session=session, lock=True)
        if (item.status != "pending" or item.expires_at <= datetime.now(UTC)
                or not state or not secrets.compare_digest(item.state_hash, digest(state))):
            raise SignatureInvalidError("签名挑战已失效或已使用")
        secret = unseal(item.secret_data)
        item.status = "verifying"
        await self.db.commit()
        try:
            claims, _ = await self.provider.exchange(code, secret["verifier"], secret["nonce"], signing=True)
            authenticated = validate_fresh_auth(claims, started_at=int(item.created_at.timestamp()))
            if claims["iss"] != item.issuer or claims["sub"] != item.subject:
                raise OIDCError("Signing identity must match current MDM user")
        except (OIDCError, KeyError):
            item = await self._owned(challenge_id, user=user, session=session, lock=True)
            if item.status == "verifying":
                item.status, item.secret_data = "failed", ""
                await self.db.commit()
            raise SignatureInvalidError("再次认证失败：必须使用当前用户重新验证") from None
        item = await self._owned(challenge_id, user=user, session=session, lock=True)
        if item.status != "verifying" or item.expires_at <= datetime.now(UTC):
            raise SignatureInvalidError("签名挑战已取消或过期")
        item.status, item.authenticated_at, item.secret_data = "ready", authenticated, ""
        await self.db.commit()
        return {"challenge_id": item.id, "status": "ready"}

    async def cancel(self, challenge_id: str, *, user: User, session: OIDCSession) -> None:
        item = await self._owned(challenge_id, user=user, session=session, lock=True)
        if item.status not in {"consumed", "failed", "cancelled"}:
            item.status, item.secret_data = "cancelled", ""
            await self.db.commit()

    async def receipt(self, challenge_id: str, *, user: User, session: OIDCSession) -> dict[str, Any]:
        item = await self._owned(challenge_id, user=user, session=session)
        return {"status": item.status, "signature_id": item.signature_id,
            "authenticated_at": item.authenticated_at, "issuer": item.issuer, "audience": item.audience}


async def consume(db: AsyncSession, challenge_id: str, *, user: User, entity_schema: str,
        entity_table: str, entity_id: int, meaning: str, content_hash: str) -> OIDCSignatureChallenge:
    """Called under the business row lock; caller commits signature + state together."""
    item = (await db.execute(select(OIDCSignatureChallenge).where(OIDCSignatureChallenge.id == challenge_id)
        .with_for_update().execution_options(populate_existing=True))).scalar_one_or_none()
    session_id = db.info.get("oidc_session_id")
    now = datetime.now(UTC)
    if (item is None or not session_id or item.session_id != session_id or item.user_id != user.user_id
            or item.status != "ready" or item.expires_at <= now
            or (item.entity_schema, item.entity_table, item.entity_id, item.meaning, item.content_hash)
            != (entity_schema, entity_table, entity_id, meaning, content_hash)):
        raise SignatureInvalidError("签名证明已失效、已使用或业务内容发生变化，请重新认证")
    session = (await db.execute(select(OIDCSession).where(OIDCSession.id == session_id)
        .with_for_update().execution_options(populate_existing=True))).scalar_one_or_none()
    identity = (await db.execute(select(OIDCIdentity).where(OIDCIdentity.identity_id == item.identity_id)
        .with_for_update().execution_options(populate_existing=True))).scalar_one_or_none()
    if (session is None or session.revoked_at or session.expires_at <= now or session.idle_expires_at <= now
            or identity is None or not identity.active or identity.user_id != user.user_id
            or identity.issuer != item.issuer or identity.subject != item.subject
            or session.identity_id != identity.identity_id):
        raise SignatureInvalidError("签名会话或身份已撤销")
    try:
        validate_fresh_auth({"auth_time": item.authenticated_at}, started_at=int(item.created_at.timestamp()), now=int(time.time()))
    except OIDCError:
        raise SignatureInvalidError("再次认证已过期") from None
    item.status = "consumed"
    return item
