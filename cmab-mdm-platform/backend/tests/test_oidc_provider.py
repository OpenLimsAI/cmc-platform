"""Defensive provider boundary unit tests; no real identity provider is used here."""
import base64
import copy
import logging

import httpx
import pytest
from app.core.logging import OIDCCallbackFilter
from app.domains.auth.oidc.config import OIDCConfig
from app.domains.auth.oidc.protocol import OIDCError
from app.domains.auth.oidc.provider import _CACHE, OIDCProvider
from cryptography.hazmat.primitives.asymmetric import rsa
from jose import jwt


def provider():
    return OIDCProvider(OIDCConfig(issuer="http://127.0.0.1:8018", public_url="http://127.0.0.1:5188/mdm",
        client_id="unit", client_secret="synthetic-only", internal_url="http://127.0.0.1:8018",
        organization="phase2-unit", account_status_visible=True))


async def test_malformed_jwt_has_safe_protocol_error():
    with pytest.raises(OIDCError):
        await provider().signing_key("not-a-jwt")


async def test_non_object_discovery_has_safe_protocol_error(monkeypatch):
    p = provider()
    _CACHE.clear()
    async def request(*args, **kwargs):
        return ["not-metadata"]
    monkeypatch.setattr(p, "request", request)
    with pytest.raises(OIDCError):
        await p.discovery()


@pytest.mark.parametrize("body", [None, ["ok"]])
async def test_malformed_global_logout_is_not_confirmed(monkeypatch, body):
    p = provider()
    async def request(*args, **kwargs):
        return body
    monkeypatch.setattr(p, "request", request)
    with pytest.raises(OIDCError):
        await p.global_logout("synthetic-access")


@pytest.mark.parametrize("before,after,valid", [
    ({"active": True, "client_id": "unit", "sub": "synthetic"}, {"active": False}, True),
    ({"active": True, "client_id": "unit", "sub": "synthetic"}, {"active": True}, False),
    ({"active": True, "client_id": "unit", "sub": "synthetic"}, {}, False),
    ({"active": False}, {"active": False}, False),
    ({"active": True, "client_id": "other", "sub": "synthetic"}, {"active": False}, False),
])
async def test_global_logout_requires_valid_session_and_observed_revocation(monkeypatch, before, after, valid):
    p = provider()
    introspections = []
    async def discovery():
        return {"introspection_endpoint": p.config.issuer + "/api/login/oauth/introspect"}
    async def request(method, url, **kwargs):
        if url.endswith("/introspect"):
            introspections.append(True)
            return before if len(introspections) == 1 else after
        assert url.endswith("/api/sso-logout")
        assert kwargs["params"] == {"logoutAll": "true"}
        return {"status": "ok"}
    monkeypatch.setattr(p, "discovery", discovery)
    monkeypatch.setattr(p, "request", request)
    if valid:
        await p.global_logout("synthetic-access")
        assert len(introspections) == 2
    else:
        with pytest.raises(OIDCError):
            await p.global_logout("synthetic-access")


@pytest.mark.parametrize("disabled_field", ["isForbidden", "isDeleted"])
async def test_active_old_token_cannot_keep_disabled_provider_account_alive(monkeypatch, disabled_field):
    p = provider()
    async def discovery():
        return {"introspection_endpoint": p.config.issuer + "/api/login/oauth/introspect"}
    async def request(method, url, **kwargs):
        if method == "POST":
            return {"active": True, "client_id": p.config.client_id, "sub": "verified-subject"}
        return {"status": "ok", "data": {"id": "verified-subject", "owner": "phase2-unit",
                "isForbidden": disabled_field == "isForbidden", "isDeleted": disabled_field == "isDeleted"}}
    monkeypatch.setattr(p, "discovery", discovery)
    monkeypatch.setattr(p, "request", request)
    assert await p.is_active("synthetic-still-valid-old-token", subject="verified-subject") is False


_ACTIVE_ACCOUNT = {"status": "ok", "data": {"id": "verified-subject", "owner": "phase2-unit",
                    "isForbidden": False, "isDeleted": False}}


async def test_active_account_is_read_with_own_token_and_fixed_organization(monkeypatch):
    p = provider()
    requests = []
    async def discovery():
        return {"introspection_endpoint": p.config.issuer + "/api/login/oauth/introspect"}
    async def request(method, url, **kwargs):
        requests.append((method, url, kwargs))
        if method == "POST":
            return {"active": True, "client_id": p.config.client_id, "sub": "verified-subject"}
        return {**_ACTIVE_ACCOUNT, "data": {**_ACTIVE_ACCOUNT["data"], "roles": ["SYS_ADMIN"]}}
    monkeypatch.setattr(p, "discovery", discovery)
    monkeypatch.setattr(p, "request", request)
    assert await p.is_active("synthetic-self-token", subject="verified-subject") is True
    assert len(requests) == 2
    method, url, kwargs = requests[-1]
    assert (method, url) == ("GET", p.config.issuer + "/api/get-user")
    assert kwargs["params"] == {"owner": "phase2-unit", "userId": "verified-subject"}
    assert kwargs["headers"] == {"Authorization": "Bearer synthetic-self-token"}
    assert "synthetic-self-token" not in url + str(kwargs["params"])


@pytest.mark.parametrize("change", ["missing", "empty", "status", "data", "id", "owner", "forbidden_missing",
                                  "deleted_missing", "forbidden_zero", "deleted_string"])
async def test_account_status_requires_strict_self_record(monkeypatch, change):
    p = provider()
    body = copy.deepcopy(_ACTIVE_ACCOUNT)
    if change == "missing":
        body = None
    elif change == "empty":
        body = {}
    elif change == "status":
        body["status"] = "error"
    elif change == "data":
        body["data"] = None
    elif change == "id":
        body["data"]["id"] = "another-subject"
    elif change == "owner":
        body["data"]["owner"] = "another-organization"
    elif change == "forbidden_missing":
        del body["data"]["isForbidden"]
    elif change == "deleted_missing":
        del body["data"]["isDeleted"]
    elif change == "forbidden_zero":
        body["data"]["isForbidden"] = 0
    else:
        body["data"]["isDeleted"] = "false"
    async def discovery():
        return {}
    async def request(method, url, **kwargs):
        return {"active": True, "client_id": p.config.client_id, "sub": "verified-subject"} if method == "POST" else body
    monkeypatch.setattr(p, "discovery", discovery)
    monkeypatch.setattr(p, "request", request)
    assert await p.is_active("synthetic-self-token", subject="verified-subject") is False


@pytest.mark.parametrize("status", [401, 403, 404, 500, 503])
async def test_account_status_denial_is_inactive_but_outage_is_error(monkeypatch, status):
    p = provider()
    async def discovery():
        return {}
    def handler(request):
        if request.method == "POST":
            return httpx.Response(200, json={"active": True, "client_id": p.config.client_id, "sub": "verified-subject"})
        assert request.url.path == "/api/get-user"
        return httpx.Response(status)
    client = httpx.AsyncClient
    monkeypatch.setattr(p, "discovery", discovery)
    monkeypatch.setattr(httpx, "AsyncClient", lambda **kwargs: client(transport=httpx.MockTransport(handler), **kwargs))
    if status >= 500:
        with pytest.raises(OIDCError):
            await p.is_active("synthetic-self-token", subject="verified-subject")
    else:
        assert await p.is_active("synthetic-self-token", subject="verified-subject") is False


async def test_account_status_network_outage_is_error(monkeypatch):
    p = provider()
    async def discovery():
        return {}
    def handler(request):
        if request.method == "POST":
            return httpx.Response(200, json={"active": True, "client_id": p.config.client_id, "sub": "verified-subject"})
        raise httpx.ConnectError("synthetic unavailable", request=request)
    client = httpx.AsyncClient
    monkeypatch.setattr(p, "discovery", discovery)
    monkeypatch.setattr(httpx, "AsyncClient", lambda **kwargs: client(transport=httpx.MockTransport(handler), **kwargs))
    with pytest.raises(OIDCError):
        await p.is_active("synthetic-self-token", subject="verified-subject")


async def test_inactive_introspection_does_not_query_account(monkeypatch):
    p = provider()
    async def discovery():
        return {}
    async def request(method, url, **kwargs):
        assert method == "POST"
        return {"active": False}
    monkeypatch.setattr(p, "discovery", discovery)
    monkeypatch.setattr(p, "request", request)
    assert await p.is_active("synthetic-self-token", subject="verified-subject") is False


async def test_weak_provider_rsa_is_rejected(monkeypatch):
    p = provider()
    _CACHE.clear()
    weak = rsa.generate_private_key(public_exponent=65537, key_size=1024)
    def encoded(value):
        return base64.urlsafe_b64encode(value.to_bytes((value.bit_length()+7)//8,"big")).rstrip(b"=").decode()
    numbers = weak.public_key().public_numbers()
    jwk = {"kid": "weak", "kty": "RSA", "use": "sig", "alg": "RS256", "n": encoded(numbers.n), "e": encoded(numbers.e)}
    async def discovery():
        return {"jwks_uri": p.config.issuer + "/.well-known/jwks"}
    async def request(*args, **kwargs):
        return {"keys": [jwk]}
    monkeypatch.setattr(p, "discovery", discovery)
    monkeypatch.setattr(p, "request", request)
    token = jwt.encode({"sub": "synthetic"}, "synthetic", algorithm="HS256", headers={"kid": "weak"})
    # Only the header is needed here; pin it to RSA without requesting a provider token.
    header, payload, signature = token.split(".")
    import json
    header = base64.urlsafe_b64encode(json.dumps({"alg":"RS256","kid":"weak"}).encode()).rstrip(b"=").decode()
    with pytest.raises(OIDCError):
        await p.signing_key(".".join([header,payload,signature]))


def test_authorization_code_query_is_removed_from_request_logging():
    record = logging.LogRecord("uvicorn.access", logging.INFO, "", 1, '%s - "%s %s HTTP/%s" %d',
        ("local", "GET", "/api/v1/auth/oidc/callback?code=synthetic-secret&state=synthetic-state", "1.1", 303), None)
    assert OIDCCallbackFilter().filter(record)
    assert "synthetic-secret" not in record.getMessage() and "synthetic-state" not in record.getMessage()
    assert "/api/v1/auth/oidc/callback" in record.getMessage()
