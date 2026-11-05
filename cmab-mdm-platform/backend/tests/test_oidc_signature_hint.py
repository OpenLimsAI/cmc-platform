"""Password-only presentation still binds a verified provider identity; UNIT tests."""
import httpx
import pytest
from app.domains.auth.oidc.config import OIDCConfig
from app.domains.auth.oidc.protocol import OIDCError
from app.domains.auth.oidc.provider import OIDCProvider
from app.domains.auth.oidc.signing import SigningRequest
from pydantic import ValidationError


@pytest.mark.parametrize("case", ["valid", "list_audience", "wrong_subject", "wrong_issuer", "wrong_audience",
    "multiple_audiences", "missing_username", "display_name_only", "blank_username", "control_username", "denied", "outage"])
async def test_signing_hint_is_only_the_verified_own_userinfo_username(monkeypatch, case):
    config = OIDCConfig(issuer="http://localhost:19181", public_url="http://localhost:19190/mdm",
        client_id="synthetic-login", client_secret="unit-only", organization="synthetic", account_status_visible=True)
    provider = OIDCProvider(config)
    calls = []

    def handler(request):
        calls.append((request.method, request.url.path))
        assert request.url.path == "/api/userinfo" and not request.url.query
        assert request.headers["authorization"] == "Bearer unit-synthetic-access"
        if case == "denied":
            return httpx.Response(401, json={"error": "invalid_token"})
        if case == "outage":
            return httpx.Response(503)
        data = {"iss": config.issuer, "sub": "verified-subject", "aud": config.client_id,
            "preferred_username": "e2e.signer", "name": "Display name is not a login name"}
        if case == "list_audience":
            data["aud"] = [config.client_id]
        if case == "wrong_subject":
            data["sub"] = "other-user"
        if case == "wrong_issuer":
            data["iss"] = "https://another.invalid"
        if case == "wrong_audience":
            data["aud"] = "another-client"
        if case == "multiple_audiences":
            data["aud"] = [config.client_id, "another-client"]
        if case in {"missing_username", "display_name_only"}:
            del data["preferred_username"]
        if case == "blank_username":
            data["preferred_username"] = " "
        if case == "control_username":
            data["preferred_username"] = "e2e.signer\n"
        return httpx.Response(200, json=data)

    real_client = httpx.AsyncClient
    monkeypatch.setattr(httpx, "AsyncClient", lambda **kw: real_client(transport=httpx.MockTransport(handler), **kw))
    if case in {"valid", "list_audience"}:
        assert await provider.signing_login_hint("unit-synthetic-access", subject="verified-subject") == "e2e.signer"
    else:
        with pytest.raises(OIDCError):
            await provider.signing_login_hint("unit-synthetic-access", subject="verified-subject")
    assert calls == [("GET", "/api/userinfo")]


def test_signing_request_never_accepts_a_browser_selected_username_or_password():
    body = {"entity_type":"project", "entity_code":"SYNTHETIC", "action":"approve", "comment":"合成测试审批说明", "reason":"合成测试签名意图"}
    for field in ("username", "login_hint", "password"):
        with pytest.raises(ValidationError):
            SigningRequest(**body, **{field: "never-trusted"})
