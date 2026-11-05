"""Real disposable PG identity/session behavior. Provider claims here are synthetic."""
import os
import time
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from app.core.config import settings
from app.core.exceptions import AccountDisabledError, PermissionDeniedError, TokenInvalidError
from app.domains.auth.models import User
from app.domains.auth.oidc.config import OIDCConfig
from app.domains.auth.oidc.models import OIDCIdentity, OIDCSession
from app.domains.auth.oidc.service import OIDCService, OIDCUnavailableError
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

_ISSUER = "http://127.0.0.1:8018"


class UnitProvider:
    """Liveness stand-in for these DB unit tests, never used by browser acceptance."""
    def __init__(self, config=None):
        self.active = True
    async def is_active(self, access, *, subject):
        return self.active


class PendingProvider(UnitProvider):
    def __init__(self, subject):
        super().__init__()
        self.subject = subject
        self.started = None
        self.resume = None
        self.nonces = set()

    async def authorization_url(self, params):
        self.nonces.add(params["nonce"])
        return "http://127.0.0.1:8018/login/oauth/authorize?state=" + params["state"]

    async def exchange(self, code, verifier, nonce, *, delegation=False):
        assert code == "pending-code" and nonce in self.nonces
        if self.started is not None:
            self.started.set()
            await self.resume.wait()
        return claims(self.subject), {"access_token": "synthetic-pending"}

    async def global_logout(self, access):
        assert access == "synthetic-old"


@pytest.fixture(autouse=True)
def unique_test_issuer(monkeypatch):
    # Each independent identity test has its own issuer, preserving the deliberate
    # one-user-per-issuer unique constraint without deleting another test's data.
    monkeypatch.setitem(globals(), "_ISSUER", "http://127.0.0.1:8018/unit/" + uuid4().hex)
    monkeypatch.setattr("app.domains.auth.oidc.service.OIDCProvider", UnitProvider)


@pytest.fixture
async def db():
    assert os.environ.get("TEST_DB") == "cmab_test"
    engine = create_async_engine(settings.DATABASE_URL, poolclass=NullPool)
    async with async_sessionmaker(engine, expire_on_commit=False)() as session:
        yield session
    await engine.dispose()


def config():
    return OIDCConfig(issuer=_ISSUER, public_url="http://127.0.0.1:5188/mdm",
                      client_id="unit-mdm", client_secret="synthetic-only", internal_url="http://127.0.0.1:8018",
                      organization="phase2-unit", account_status_visible=True,
                      pm_client_id="unit-delegate", pm_client_secret="synthetic-only")


async def actors(db):
    admin = (await db.execute(select(User).where(User.username == "admin"))).scalar_one()
    readonly = (await db.execute(select(User).where(User.username == "readonly"))).scalar_one()
    return admin, readonly


def claims(subject):
    return {"iss": _ISSUER, "sub": subject, "iat": int(time.time()),
            "exp": int(time.time()) + 600, "sid": str(uuid4()), "name": "admin", "roles": ["SYS_ADMIN"]}


async def test_no_implicit_name_or_email_binding(db):
    service = OIDCService(db, config=config())
    with pytest.raises(PermissionDeniedError):
        await service.issue_session(claims("unmapped-" + uuid4().hex), {"access_token": "synthetic-only"})


@pytest.mark.parametrize("scope", ["device", "all", "legacy"])
async def test_device_scope_and_newer_login(db, monkeypatch, scope):
    monkeypatch.setattr(settings, "MDM_OIDC_DEVICE_LOGOUT_ENABLED", scope != "legacy")
    admin, readonly = await actors(db)
    service = OIDCService(db, config=config())
    subject, other_subject = "device-" + uuid4().hex, "other-" + uuid4().hex
    await service.bind_identity(subject, admin.user_id, actor=admin, reason="合成设备范围明确映射")
    await service.bind_identity(other_subject, readonly.user_id, actor=admin, reason="合成其他用户明确映射")
    now = int(time.time())
    first = {**claims(subject), "iat": now - 5, "sid": "device-a"}
    second = {**first, "sid": "device-b"}
    raw_a, _ = await service.issue_session(first, {"access_token": "synthetic-only"})
    raw_b, _ = await service.issue_session(second, {"access_token": "synthetic-only"})
    raw_other, _ = await service.issue_session({**claims(other_subject), "sid": "other-user"}, {"access_token": "synthetic-only"})
    event = {"iss": _ISSUER, "sub": subject, "iat": now, "jti": uuid4().hex}
    if scope != "all":
        event["sid"] = "device-a"
    await service.backchannel(event)
    with pytest.raises(TokenInvalidError):
        await service.current_session(raw_a)
    if scope == "device":
        await service.current_session(raw_b)
    else:
        with pytest.raises(TokenInvalidError):
            await service.current_session(raw_b)
    await service.current_session(raw_other)
    fresh, _ = await service.issue_session({**first, "iat": now+1}, {"access_token": "synthetic-only"})
    await service.current_session(fresh)


async def test_explicit_identity_preserves_numeric_id_and_ignores_casdoor_role(db):
    admin, readonly = await actors(db)
    before = readonly.user_id
    subject = "mapped-" + uuid4().hex
    service = OIDCService(db, config=config())
    mapping = await service.bind_identity(subject, before, actor=admin, reason="显式映射隔离验收身份")
    raw, session = await service.issue_session(claims(subject), {"access_token": "synthetic-only"})
    user, loaded = await service.current_session(raw)
    assert user.user_id == before == mapping.user_id
    assert all(r.role_code != "SYS_ADMIN" for r in user.roles)
    assert loaded.id == session.id and raw not in session.id
    assert "synthetic-only" not in session.secret_data
    await service.revoke(raw)
    logout_audit = await db.execute(text("SELECT count(*) FROM audit.audit_log WHERE action='LOGOUT' AND entity_table='oidc_session' AND entity_code=:code"), {"code": session.id})
    assert logout_audit.scalar_one() == 1
    with pytest.raises(TokenInvalidError):
        await service.current_session(raw)


async def test_mapping_disable_and_password_change_invalidate_session(db):
    admin, readonly = await actors(db)
    subject = "disabled-map-" + uuid4().hex
    service = OIDCService(db, config=config())
    mapping = await service.bind_identity(subject, readonly.user_id, actor=admin, reason="显式映射禁用检查")
    raw, _ = await service.issue_session(claims(subject), {"access_token": "synthetic-only"})
    mapping.active = False
    await db.commit()
    with pytest.raises(TokenInvalidError):
        await service.current_session(raw)
    mapping.active = True
    await db.commit()
    raw, _ = await service.issue_session(claims(subject), {"access_token": "synthetic-only"})
    original = readonly.password_changed_at
    readonly.password_changed_at = datetime.now(UTC)
    await db.commit()
    try:
        with pytest.raises(TokenInvalidError):
            await service.current_session(raw)
    finally:
        readonly.password_changed_at = original
        await db.commit()


async def test_disabled_user_and_actual_expiration_are_rejected(db):
    admin, readonly = await actors(db)
    subject = "expiry-" + uuid4().hex
    service = OIDCService(db, config=config())
    await service.bind_identity(subject, readonly.user_id, actor=admin, reason="隔离会话过期检查")
    raw, session = await service.issue_session(claims(subject), {"access_token": "synthetic-only"})
    session.expires_at = datetime.now(UTC) - timedelta(seconds=1)
    await db.commit()
    with pytest.raises(TokenInvalidError):
        await service.current_session(raw)
    readonly.status = "disabled"
    await db.commit()
    try:
        with pytest.raises(AccountDisabledError):
            await service.issue_session(claims(subject), {"access_token": "synthetic-only"})
    finally:
        readonly.status = "active"
        await db.commit()


async def test_local_role_change_is_live_and_mapping_is_audited(db):
    admin, readonly = await actors(db)
    service = OIDCService(db, config=config())
    subject = "audit-" + uuid4().hex
    mapping = await service.bind_identity(subject, readonly.user_id, actor=admin, reason="显式映射审计检查")
    raw, _ = await service.issue_session(claims(subject), {"access_token": "synthetic-only"})
    user, _ = await service.current_session(raw)
    assert user.user_id == readonly.user_id
    count = await db.execute(text("SELECT count(*) FROM audit.audit_log WHERE entity_table='oidc_identity' AND entity_id=:id"), {"id": mapping.identity_id})
    assert count.scalar_one() == 1
    assert (await db.execute(select(OIDCIdentity).where(OIDCIdentity.subject == subject))).scalar_one().user_id == readonly.user_id
    assert (await db.execute(select(OIDCSession).where(OIDCSession.identity_id == mapping.identity_id))).scalars().all()


async def test_delayed_subject_logout_revokes_old_but_not_later_login_and_replay_is_idempotent(db):
    from app.domains.auth.oidc.models import OIDCLogoutReplay
    admin, readonly = await actors(db)
    service = OIDCService(db, config=config())
    subject = "logout-" + uuid4().hex
    await service.bind_identity(subject, readonly.user_id, actor=admin, reason="隔离延迟注销事件检查")
    now = int(time.time())
    old_claims = {**claims(subject), "iat": now - 30}
    new_claims = {**claims(subject), "iat": now - 5}
    old, _ = await service.issue_session(old_claims, {"access_token": "synthetic-old"})
    new, _ = await service.issue_session(new_claims, {"access_token": "synthetic-new"})
    event = {"iss": _ISSUER, "sub": subject, "sid": "different-beego-session",
             "iat": now - 10, "jti": str(uuid4())}
    await service.backchannel(event)
    with pytest.raises(TokenInvalidError):
        await service.current_session(old)
    assert (await service.current_session(new))[0].user_id == readonly.user_id
    await service.backchannel(event)
    count = await db.execute(select(OIDCLogoutReplay).where(OIDCLogoutReplay.issuer == _ISSUER))
    assert len(count.scalars().all()) == 1
    assert (await service.current_session(new))[0].user_id == readonly.user_id


async def test_one_time_callback_and_wrong_cookie_cannot_consume_another_login(db):
    from urllib.parse import parse_qs, urlsplit

    from app.domains.auth.oidc.protocol import OIDCError
    admin, readonly = await actors(db)
    subject = "callback-" + uuid4().hex
    class Provider(UnitProvider):
        async def authorization_url(self, params):
            self.params = params
            return "http://127.0.0.1:8018/login/oauth/authorize?state=" + params["state"]
        async def exchange(self, code, verifier, nonce, *, delegation=False):
            assert code == "single-code" and nonce == self.params["nonce"]
            return claims(subject), {"access_token": "synthetic-only"}
    provider = Provider()
    service = OIDCService(db, config=config(), provider=provider)
    await service.bind_identity(subject, readonly.user_id, actor=admin, reason="隔离一次性回调检查")
    state, url = await service.begin("/projects?tab=pm")
    assert parse_qs(urlsplit(url).query)["state"] == [state]
    with pytest.raises(OIDCError):
        await service.complete("single-code", state, "another-browser")
    raw, _, target = await service.complete("single-code", state, state)
    assert target == "/projects?tab=pm" and (await service.current_session(raw))[0].user_id == readonly.user_id
    with pytest.raises(OIDCError):
        await service.complete("single-code", state, state)


@pytest.mark.parametrize("action", ["local_logout", "global_logout", "native_login"])
@pytest.mark.parametrize("phase", ["pending", "exchange_in_flight", "completed_before_response"])
async def test_browser_logout_or_native_login_cancels_its_pending_callback(db, monkeypatch, action, phase):
    import asyncio
    import inspect
    import re
    from http.cookies import SimpleCookie
    from pathlib import Path

    import app.api.v1.oidc as oidc_api
    from app.api.v1.auth import login
    from app.domains.auth.oidc.models import OIDCLogin
    from app.domains.auth.oidc.protocol import OIDCError, digest
    from app.domains.auth.oidc.service import LOGIN_COOKIE, SESSION_COOKIE
    from app.domains.auth.schemas import LoginRequest
    from starlette.requests import Request
    from starlette.responses import Response

    admin, readonly = await actors(db)
    cfg = config()
    provider = PendingProvider("cancel-" + uuid4().hex)
    service = OIDCService(db, config=cfg, provider=provider)
    await service.bind_identity(provider.subject, readonly.user_id, actor=admin, reason="隔离浏览器待完成回调撤销")
    old_raw, _ = await service.issue_session(claims(provider.subject), {"access_token": "synthetic-old"})
    state, _ = await service.begin("/projects")
    other_browser, _ = await service.begin("/projects")
    monkeypatch.setattr(settings, "MDM_OIDC_ENABLED", True)
    monkeypatch.setattr(settings, "MDM_NATIVE_LOGIN_ENABLED", True)
    monkeypatch.setattr(settings, "MDM_PUBLIC_URL", cfg.public_url)
    monkeypatch.setattr("app.domains.auth.oidc.config.configured", lambda: cfg)
    monkeypatch.setattr(oidc_api, "OIDCService", lambda connection: OIDCService(connection, config=cfg, provider=provider))
    request = Request({"type": "http", "method": "POST", "path": "/api/v1/auth/oidc/logout",
        "headers": [(b"origin", cfg.origin.encode()),
                    (b"cookie", (LOGIN_COOKIE + "=" + state + "; " + SESSION_COOKIE + "=" + old_raw).encode())],
        "client": ("127.0.0.1", 12345)})
    callback = None
    completed_raw = None
    if phase == "exchange_in_flight":
        provider.started, provider.resume = asyncio.Event(), asyncio.Event()
        callback = asyncio.create_task(service.complete("pending-code", state, state, raw_session=old_raw))
        await asyncio.wait_for(provider.started.wait(), timeout=3)
    elif phase == "completed_before_response":
        completed_raw, _, _ = await service.complete("pending-code", state, state, raw_session=old_raw)
    try:
        # A real second database session models the independent logout/login request.
        async with async_sessionmaker(db.bind, expire_on_commit=False)() as action_db:
            if action == "native_login":
                source = Path("tests/conftest.py").read_text()
                password = re.search(r'_login\(http_client, "admin", "([^"]+)"\)', source).group(1)
                response = Response()
                result = await inspect.unwrap(login)(request=request, payload=LoginRequest(username="admin", password=password), response=response, db=action_db)
                assert result["data"]["user"]["username"] == "admin"
            else:
                response = await oidc_api.oidc_logout(oidc_api.LogoutRequest(**{"global": action == "global_logout"}), request, action_db)
                assert response.status_code == 200
        if callback is not None:
            provider.resume.set()
            with pytest.raises(OIDCError):
                await asyncio.wait_for(callback, timeout=3)
        elif completed_raw:
            with pytest.raises(TokenInvalidError):
                await service.current_session(completed_raw)
        else:
            with pytest.raises(OIDCError):
                await service.complete("pending-code", state, state, raw_session=old_raw)
        assert await db.get(OIDCLogin, digest(state), populate_existing=True) is None
        cleared = []
        for header in response.headers.getlist("set-cookie"):
            cookie = SimpleCookie(header)
            if LOGIN_COOKIE in cookie:
                cleared.append((cookie[LOGIN_COOKIE]["path"], cookie[LOGIN_COOKIE]["max-age"]))
        assert cleared == [(cfg.cookie_path, "0")]
        # Another browser's independent state remains usable.
        another_raw, _, _ = await service.complete("pending-code", other_browser, other_browser)
        assert (await service.current_session(another_raw))[0].user_id == readonly.user_id
    finally:
        if callback is not None:
            provider.resume.set()
            await asyncio.gather(callback, return_exceptions=True)


@pytest.mark.parametrize("confirmation", ["inactive", "still_active", "unavailable"])
async def test_confirmed_global_logout_returns_only_fixed_local_login(db, monkeypatch, confirmation):
    import json
    from http.cookies import SimpleCookie

    import app.api.v1.oidc as oidc_api
    from app.domains.auth.oidc.protocol import OIDCError
    from app.domains.auth.oidc.provider import OIDCProvider
    from app.domains.auth.oidc.service import LOGIN_COOKIE, SESSION_COOKIE
    from starlette.requests import Request

    admin, readonly = await actors(db)
    cfg = config()
    subject = "return-" + uuid4().hex
    class Provider(OIDCProvider):
        introspections = 0
        async def is_active(self, access, *, subject):
            return True
        async def discovery(self):
            return {"introspection_endpoint": cfg.issuer + "/api/login/oauth/introspect"}
        async def request(self, method, url, **kwargs):
            assert method == "POST"
            if url.endswith("/api/sso-logout"):
                assert kwargs["params"] == {"logoutAll": "true"}
                return {"status": "ok"}
            self.introspections += 1
            if self.introspections == 1:
                return {"active": True, "client_id": cfg.client_id, "sub": subject}
            if confirmation == "unavailable":
                raise OIDCError("Synthetic confirmation unavailable")
            return {"active": confirmation != "inactive"}
    provider = Provider(cfg)
    service = OIDCService(db, config=cfg, provider=provider)
    await service.bind_identity(subject, readonly.user_id, actor=admin, reason="隔离统一退出固定返回地址")
    raw, _ = await service.issue_session(claims(subject), {"access_token": "synthetic-global-access"})
    monkeypatch.setattr(oidc_api, "OIDCService", lambda connection: service)
    request = Request({"type": "http", "method": "POST", "path": "/api/v1/auth/oidc/logout",
        "headers": [(b"origin", cfg.origin.encode()), (b"cookie", (SESSION_COOKIE + "=" + raw).encode())],
        "client": ("127.0.0.1", 12345)})
    response = await oidc_api.oidc_logout(oidc_api.LogoutRequest(**{"global": True}), request, db)
    body = json.loads(response.body)["data"]
    assert body["local_logout"] is True
    assert provider.introspections == 2
    if confirmation == "inactive":
        assert body["global_logout"] is True and "warning" not in body
        assert body["logout_url"] == body["login_url"] == cfg.public_url + "/login?reason=logout"
    else:
        assert body["global_logout"] is False and body["warning"]
        assert "logout_url" not in body
    assert "synthetic-global-access" not in response.body.decode()
    cleared = set()
    for header in response.headers.getlist("set-cookie"):
        cookie = SimpleCookie(header)
        for name in (LOGIN_COOKIE, SESSION_COOKIE):
            if name in cookie and cookie[name]["max-age"] == "0" and cookie[name]["path"] == cfg.cookie_path:
                cleared.add(name)
    assert cleared == {LOGIN_COOKIE, SESSION_COOKIE}
    with pytest.raises(TokenInvalidError):
        await service.current_session(raw)


async def test_cookie_auth_uses_live_mdm_user_and_rejects_cross_origin_write(db, monkeypatch):
    from app.shared.permissions import get_current_user
    from pydantic import SecretStr
    from starlette.requests import Request
    admin, readonly = await actors(db)
    cfg = config()
    for key, value in {"MDM_OIDC_ENABLED": True, "MDM_PUBLIC_URL": cfg.public_url,
                       "MDM_OIDC_ISSUER_URL": cfg.issuer, "MDM_OIDC_INTERNAL_URL": cfg.internal_url,
                       "MDM_OIDC_CLIENT_ID": cfg.client_id,
                       "MDM_OIDC_ORGANIZATION": cfg.organization, "MDM_OIDC_ACCOUNT_STATUS_VISIBLE": True,
                       "MDM_OIDC_CLIENT_SECRET": SecretStr("synthetic-only")}.items():
        monkeypatch.setattr(settings, key, value)
    service = OIDCService(db, config=cfg)
    subject = "cookie-" + uuid4().hex
    await service.bind_identity(subject, readonly.user_id, actor=admin, reason="隔离cookie权限入口验证")
    raw, _ = await service.issue_session(claims(subject), {"access_token": "synthetic-only"})
    scope = {"type": "http", "method": "GET", "path": "/api/v1/projects", "headers": [
        (b"cookie", ("mdm_oidc_session="+raw).encode())], "client": ("127.0.0.1", 12345)}
    request = Request(scope)
    user = await get_current_user(request, authorization=None, db=db)
    assert user.user_id == readonly.user_id and request.state.oidc_session
    bad = Request({**scope, "method": "POST", "headers": scope["headers"]+[(b"origin", b"https://evil.test")]})
    with pytest.raises(PermissionDeniedError):
        await get_current_user(bad, authorization=None, db=db)


async def test_logout_subject_does_not_revoke_another_subject_reusing_sid(db):
    admin, readonly = await actors(db)
    service = OIDCService(db, config=config())
    first, second = "first-" + uuid4().hex, "second-" + uuid4().hex
    await service.bind_identity(first, readonly.user_id, actor=admin, reason="隔离共享sid主体A")
    await service.bind_identity(second, admin.user_id, actor=admin, reason="隔离共享sid主体B")
    a, _ = await service.issue_session({**claims(first), "sid": "shared-beego-id"}, {"access_token": "synthetic-a"})
    b, _ = await service.issue_session({**claims(second), "sid": "shared-beego-id"}, {"access_token": "synthetic-b"})
    await service.backchannel({"iss": _ISSUER, "sub": first, "sid": "shared-beego-id", "iat": int(time.time()), "jti": str(uuid4())})
    with pytest.raises(TokenInvalidError):
        await service.current_session(a)
    assert (await service.current_session(b))[0].user_id == admin.user_id


async def test_native_recovery_survives_invalid_oidc_configuration(db, monkeypatch):
    import inspect
    import re
    from pathlib import Path

    from app.api.v1.auth import login
    from app.domains.auth.schemas import LoginRequest
    from starlette.requests import Request
    from starlette.responses import Response
    monkeypatch.setattr(settings, "MDM_OIDC_ENABLED", True)
    monkeypatch.setattr(settings, "MDM_PUBLIC_URL", "")
    monkeypatch.setattr(settings, "MDM_OIDC_CLIENT_SECRET", None)
    monkeypatch.setattr(settings, "CORS_ORIGINS", "http://127.0.0.1:5188")
    source = Path("tests/conftest.py").read_text()
    password = re.search(r'_login\(http_client, "admin", "([^"]+)"\)', source).group(1)
    request = Request({"type":"http", "method":"POST", "path":"/api/v1/auth/login", "headers":[(b"origin",b"http://127.0.0.1:5188")], "client":("127.0.0.1",12345)})
    response = Response()
    result = await inspect.unwrap(login)(request=request, payload=LoginRequest(username="admin", password=password), response=response, db=db)
    assert result["data"]["user"]["username"] == "admin"


async def test_provider_revocation_blocks_cookie_even_when_no_backchannel_arrived(db):
    admin, readonly = await actors(db)
    service = OIDCService(db, config=config())
    subject = "offline-revoke-" + uuid4().hex
    await service.bind_identity(subject, readonly.user_id, actor=admin, reason="隔离丢通知撤销检查")
    raw, _ = await service.issue_session(claims(subject), {"access_token": "synthetic-only"})
    assert (await service.current_session(raw))[0].user_id == readonly.user_id
    service.provider.active = False
    with pytest.raises(TokenInvalidError):
        await service.current_session(raw)
    service.provider.active = True
    # Provider restoration does not revive a cookie already revoked locally.
    with pytest.raises(TokenInvalidError):
        await service.current_session(raw)
    fresh, _ = await service.issue_session(claims(subject), {"access_token": "synthetic-new"})
    assert (await service.current_session(fresh))[0].user_id == readonly.user_id


async def test_provider_outage_fails_closed_then_recovers_transient_session(db, monkeypatch):
    from app.domains.auth.oidc.protocol import OIDCError
    admin, readonly = await actors(db)
    service = OIDCService(db, config=config())
    subject = "outage-" + uuid4().hex
    await service.bind_identity(subject, readonly.user_id, actor=admin, reason="隔离上游不可达恢复检查")
    raw, session = await service.issue_session(claims(subject), {"access_token": "synthetic-only"})
    original = service.provider.is_active
    async def unavailable(access, *, subject):
        raise OIDCError("Synthetic provider unavailable")
    monkeypatch.setattr(service.provider, "is_active", unavailable)
    with pytest.raises(OIDCUnavailableError):
        await service.current_session(raw)
    assert session.revoked_at is None
    monkeypatch.setattr(service.provider, "is_active", original)
    assert (await service.current_session(raw))[0].user_id == readonly.user_id
