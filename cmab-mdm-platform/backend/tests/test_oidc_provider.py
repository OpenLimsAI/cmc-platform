"""Defensive provider boundary unit tests; no real identity provider is used here."""
import base64
import logging

import pytest
from app.core.logging import OIDCCallbackFilter
from app.domains.auth.oidc.config import OIDCConfig
from app.domains.auth.oidc.protocol import OIDCError
from app.domains.auth.oidc.provider import _CACHE, OIDCProvider
from cryptography.hazmat.primitives.asymmetric import rsa
from jose import jwt


def provider():
    return OIDCProvider(OIDCConfig(issuer="http://127.0.0.1:8018", public_url="http://127.0.0.1:5188/mdm",
        client_id="unit", client_secret="synthetic-only", internal_url="http://127.0.0.1:8018"))


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
