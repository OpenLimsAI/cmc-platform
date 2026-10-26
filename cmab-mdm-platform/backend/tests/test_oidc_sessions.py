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
from app.domains.auth.oidc.service import OIDCService
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


async def test_cookie_auth_uses_live_mdm_user_and_rejects_cross_origin_write(db, monkeypatch):
    from app.shared.permissions import get_current_user
    from pydantic import SecretStr
    from starlette.requests import Request
    admin, readonly = await actors(db)
    cfg = config()
    for key, value in {"MDM_OIDC_ENABLED": True, "MDM_PUBLIC_URL": cfg.public_url,
                       "MDM_OIDC_ISSUER_URL": cfg.issuer, "MDM_OIDC_INTERNAL_URL": cfg.internal_url,
                       "MDM_OIDC_CLIENT_ID": cfg.client_id,
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
