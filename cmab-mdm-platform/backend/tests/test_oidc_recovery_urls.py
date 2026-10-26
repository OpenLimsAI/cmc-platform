"""Malformed local OIDC URLs must not disable explicitly allowed native recovery."""
import inspect
import json
import os
import re
from http.cookies import SimpleCookie
from pathlib import Path

import pytest
from app.core.config import settings
from app.domains.auth.oidc.config import checked_url, configured
from app.domains.auth.oidc.protocol import OIDCError
from pydantic import SecretStr
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool
from starlette.requests import Request
from starlette.responses import Response


@pytest.fixture
async def db():
    assert os.environ.get("TEST_DB") == "cmab_test"
    assert settings.DATABASE_URL_SYNC.endswith("/cmab_test")
    engine = create_async_engine(settings.DATABASE_URL, poolclass=NullPool)
    async with async_sessionmaker(engine, expire_on_commit=False)() as session:
        yield session
    await engine.dispose()


def local_config(monkeypatch, broken_key=None):
    for key, value in {
        "MDM_OIDC_ENABLED": True, "MDM_NATIVE_LOGIN_ENABLED": True,
        "MDM_PUBLIC_URL": "http://127.0.0.1:5188/mdm", "MDM_OIDC_ISSUER_URL": "http://127.0.0.1:8018",
        "MDM_OIDC_INTERNAL_URL": "http://127.0.0.1:8018", "MDM_OIDC_CLIENT_ID": "recovery-test",
        "MDM_OIDC_CLIENT_SECRET": SecretStr("synthetic-recovery-only"),
        "MDM_OIDC_ORGANIZATION": "phase2-unit", "MDM_OIDC_ACCOUNT_STATUS_VISIBLE": True,
        "CORS_ORIGINS": "http://127.0.0.1:5188",
    }.items():
        monkeypatch.setattr(settings, key, value)
    if broken_key:
        value = {"MDM_OIDC_ORGANIZATION": "", "MDM_OIDC_ACCOUNT_STATUS_VISIBLE": False}.get(broken_key, "http://[")
        monkeypatch.setattr(settings, broken_key, value)


@pytest.mark.parametrize("value", ["http://[", "https://[not-ipv6]/mdm"])
def test_malformed_configured_url_is_a_safe_oidc_error(value):
    with pytest.raises(OIDCError):
        checked_url(value)


@pytest.mark.parametrize("broken_key", ["MDM_OIDC_ISSUER_URL", "MDM_PUBLIC_URL", "MDM_OIDC_ORGANIZATION", "MDM_OIDC_ACCOUNT_STATUS_VISIBLE"])
async def test_config_reports_native_recovery_when_url_parser_rejects(monkeypatch, broken_key):
    from app.api.v1.oidc import oidc_config
    local_config(monkeypatch, broken_key)
    response = await oidc_config()
    assert response.status_code == 200
    assert json.loads(response.body)["data"] == {"enabled": False, "native_login_enabled": True}


@pytest.mark.parametrize("broken_key", ["MDM_OIDC_ISSUER_URL", "MDM_PUBLIC_URL", "MDM_OIDC_ORGANIZATION", "MDM_OIDC_ACCOUNT_STATUS_VISIBLE"])
async def test_native_recovery_login_survives_invalid_oidc_configuration(db, monkeypatch, broken_key):
    from app.api.v1.auth import REFRESH_COOKIE_NAME, login
    from app.domains.auth.schemas import LoginRequest
    local_config(monkeypatch, broken_key)
    fixture = Path("tests/conftest.py").read_text()
    password = re.search(r'_login\(http_client, "admin", "([^"]+)"\)', fixture).group(1)
    request = Request({"type": "http", "method": "POST", "path": "/api/v1/auth/login",
        "headers": [(b"origin", b"http://127.0.0.1:5188")], "client": ("127.0.0.1", 12345)})
    response = Response()
    result = await inspect.unwrap(login)(request=request, payload=LoginRequest(username="admin", password=password), response=response, db=db)
    assert result["data"]["user"]["username"] == "admin"
    # Inspect only the non-secret attribute, never print the refresh token.
    paths = []
    for header in response.headers.getlist("set-cookie"):
        cookie = SimpleCookie(header)
        if REFRESH_COOKIE_NAME in cookie:
            paths.append(cookie[REFRESH_COOKIE_NAME]["path"])
    expected = "/api/v1/auth" if broken_key == "MDM_PUBLIC_URL" else "/mdm/api/v1/auth"
    assert paths == [expected]


@pytest.mark.parametrize(("key", "value"), [
    ("MDM_OIDC_ORGANIZATION", ""), ("MDM_OIDC_ORGANIZATION", "other/organization"),
    ("MDM_OIDC_ORGANIZATION", "untrusted organization"),
    ("MDM_OIDC_ACCOUNT_STATUS_VISIBLE", False),
])
def test_enabled_oidc_requires_fixed_organization_and_visibility_confirmation(monkeypatch, key, value):
    local_config(monkeypatch)
    monkeypatch.setattr(settings, key, value)
    with pytest.raises(OIDCError):
        configured()


def test_config_carries_explicit_account_status_boundary(monkeypatch):
    local_config(monkeypatch)
    config = configured()
    assert config.organization == "phase2-unit" and config.account_status_visible is True
