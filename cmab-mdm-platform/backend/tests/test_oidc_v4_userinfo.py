"""Explicit official-v4 live-state contract; transport doubles are not E2E."""

import httpx
import pytest
from app.domains.auth.oidc.config import OIDCConfig
from app.domains.auth.oidc.protocol import OIDCError
from app.domains.auth.oidc.provider import OIDCProvider


@pytest.mark.parametrize(
    "case",
    [
        "valid",
        "wrong_subject",
        "wrong_issuer",
        "wrong_audience",
        "missing_audience",
        "error_body",
        "denied",
        "outage",
    ],
)
async def test_explicit_v4_live_userinfo_never_falls_back_or_accepts_another_identity(
    monkeypatch, case
):
    config = OIDCConfig(
        issuer="http://localhost:19081",
        public_url="http://localhost:19090/mdm",
        client_id="unit-v4",
        client_secret="synthetic-only",
        organization="synthetic",
        account_status_visible=True,
        account_status_mode="casdoor_v4_userinfo",
    )
    p = OIDCProvider(config)
    calls = []

    async def discovery():
        return {}

    def handler(request):
        calls.append((request.method, request.url.path))
        if request.method == "POST":
            return httpx.Response(
                200, json={"active": True, "client_id": "unit-v4", "sub": "same-user"}
            )
        assert request.url.path == "/api/userinfo"
        assert request.headers["authorization"] == "Bearer synthetic-input"
        assert not request.url.query
        if case == "denied":
            return httpx.Response(401, json={"error": "invalid_token"})
        if case == "outage":
            return httpx.Response(503)
        body = {"sub": "same-user", "iss": config.issuer, "aud": "unit-v4",
                "preferred_username": "e2e.signer", "name": "Synthetic signer"}
        if case == "wrong_subject":
            body["sub"] = "someone-else"
        if case == "wrong_issuer":
            body["iss"] = "https://other.invalid"
        if case == "wrong_audience":
            body["aud"] = "another-client"
        if case == "missing_audience":
            del body["aud"]
        if case == "error_body":
            body = {"status": "error"}
        return httpx.Response(200, json=body)

    real_client = httpx.AsyncClient
    monkeypatch.setattr(p, "discovery", discovery)
    monkeypatch.setattr(
        httpx, "AsyncClient", lambda **kw: real_client(transport=httpx.MockTransport(handler), **kw)
    )
    if case == "outage":
        with pytest.raises(OIDCError):
            await p.is_active("synthetic-input", subject="same-user")
    else:
        assert await p.is_active("synthetic-input", subject="same-user") is (case == "valid")
    assert p.identity_presentation == ({"identityUsername": "e2e.signer", "displayName": "Synthetic signer"} if case == "valid" else None)
    assert all(path != "/api/get-account" for _, path in calls)
