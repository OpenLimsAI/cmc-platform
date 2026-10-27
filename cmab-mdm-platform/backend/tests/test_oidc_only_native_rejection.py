"""Native credentials must never authenticate when this deployment disables them.

These are policy unit tests, not real Casdoor/browser acceptance. They exercise
public entry points and the underlying issuer before any database mutation.
"""
import inspect

import pytest
from app.api.v1 import auth, oidc
from app.core.config import settings
from app.core.exceptions import PermissionDeniedError
from app.domains.auth.schemas import LoginRequest
from app.domains.auth.services import AuthService
from app.shared import permissions
from fastapi import Request, Response


class NoDatabase:
    async def execute(self, *args, **kwargs):
        pytest.fail("Disabled native authentication reached the database")


def request(path="/api/v1/auth/refresh"):
    return Request({"type": "http", "method": "POST", "path": path,
                    "headers": [], "query_string": b"", "scheme": "https",
                    "server": ("mdm.example.test", 443), "client": ("127.0.0.1", 1234)})


@pytest.fixture(autouse=True)
def native_disabled(monkeypatch):
    monkeypatch.setattr(settings, "MDM_NATIVE_LOGIN_ENABLED", False)


async def test_password_login_is_rejected_without_looking_up_a_user():
    with pytest.raises(PermissionDeniedError):
        await inspect.unwrap(auth.login)(
            request("/api/v1/auth/login"),
            LoginRequest(username="synthetic-only", password="synthetic-password-123"),
            Response(), NoDatabase(),
        )


@pytest.mark.parametrize("cookie", [None, "synthetic-previous-refresh"])
async def test_refresh_cannot_issue_tokens_or_rotate_cookies(monkeypatch, cookie):
    calls = []

    class NativeService:
        def __init__(self, db):
            calls.append("constructed")

        async def refresh(self, **kwargs):
            pytest.fail("Disabled refresh reached the native issuer")

    monkeypatch.setattr(auth, "AuthService", NativeService)
    response = Response()
    with pytest.raises(PermissionDeniedError):
        await inspect.unwrap(auth.refresh)(request(), response, cookie, NoDatabase())
    assert calls == []
    assert "set-cookie" not in response.headers


@pytest.mark.parametrize("oidc_enabled", [True, False])
async def test_old_native_bearer_is_not_a_fallback_when_oidc_is_unavailable(monkeypatch, oidc_enabled):
    monkeypatch.setattr(settings, "MDM_OIDC_ENABLED", oidc_enabled)

    def decode_native(*args, **kwargs):
        pytest.fail("Disabled local Bearer reached JWT validation")

    monkeypatch.setattr(permissions, "decode_token", decode_native)
    with pytest.raises(PermissionDeniedError):
        await permissions.get_current_user(request(), "Bearer synthetic-old-access", NoDatabase())


async def test_native_password_issuer_also_enforces_the_deployment_policy():
    with pytest.raises(PermissionDeniedError):
        await AuthService(NoDatabase()).login(
            username="synthetic-only", password="synthetic-password-123", ip=None, ua=None,
        )


async def test_native_refresh_issuer_also_enforces_the_deployment_policy(monkeypatch):
    def decode_native(*args, **kwargs):
        pytest.fail("Disabled native issuer attempted to decode a refresh token")

    monkeypatch.setattr("app.domains.auth.services.decode_token", decode_native)
    with pytest.raises(PermissionDeniedError):
        await AuthService(NoDatabase()).refresh("synthetic-previous-refresh", ip=None, ua=None)


async def test_provider_failure_does_not_advertise_a_disabled_recovery_path(monkeypatch):
    from app.domains.auth.oidc.protocol import OIDCError

    class UnavailableProvider:
        def __init__(self, db):
            raise OIDCError("synthetic-unavailable")

    monkeypatch.setattr(oidc, "OIDCService", UnavailableProvider)
    response = await oidc.oidc_login(request(), db=NoDatabase())
    assert response.status_code == 503
    assert "原生" not in response.body.decode()
    assert "location" not in response.headers
