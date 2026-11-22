"""Comprehensive unit tests for cmc-oidc-auth Wave 0 shared package."""
from __future__ import annotations

import base64
from urllib.parse import parse_qs, urlsplit

import jwt
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi import Response

from cmc_oidc_auth import (
    CMCOIDCConfig,
    CookieSessionCodec,
    OIDCConfigError,
    OIDCProtocolError,
    OIDCStateError,
    OIDCTokenError,
    OriginMismatchError,
    SessionExpiredError,
    SessionInvalidError,
    build_authorization_request,
    compute_code_challenge,
    generate_pkce_pair,
    normalize_cookie_path,
    require_same_origin,
    sanitize_return_to,
    validate_authorization_callback,
    validate_fresh_auth_time,
    validate_id_token,
    validate_startup,
    verify_pkce_pair,
)

STRONG_SESSION_SECRET = "w9K4mP8vQ2xZ7nL5rT1yB6cF3hJ0sD4gA8eU2iO6pM1"
STRONG_CLIENT_SECRET = "casdoor-client-secret-9f8e7d6c5b4a"
STRONG_SIG_SECRET = "casdoor-sig-secret-1a2b3c4d5e6f"


def _prod_config(**overrides) -> CMCOIDCConfig:
    params = {
        "issuer_url": "https://iam.openlims.ai",
        "public_url": "https://www.openlims.ai/water",
        "client_id": "maibo-cmc-water",
        "client_secret": STRONG_CLIENT_SECRET,
        "session_secret": STRONG_SESSION_SECRET,
        "organization": "mabpharm",
        "env": "production",
    }
    params.update(overrides)
    return validate_startup(CMCOIDCConfig(**params))


# ---------------------------------------------------------------------------
# 1. Fail-closed startup validator & URL / secret / subpath rules
# ---------------------------------------------------------------------------
def test_startup_valid_production_config_derives_subpath_origin_and_secure():
    cfg = _prod_config()
    assert cfg.is_production is True
    assert cfg.origin == "https://www.openlims.ai"
    assert cfg.cookie_path == "/water/"
    assert cfg.secure is True
    assert cfg.callback_url == "https://www.openlims.ai/water/api/v1/auth/oidc/callback"


@pytest.mark.parametrize(
    "bad_overrides",
    [
        {"issuer_url": "http://iam.openlims.ai"},
        {"public_url": "http://www.openlims.ai/water"},
        # Loopback HTTP must still fail closed in production!
        {"issuer_url": "http://localhost:8000", "public_url": "http://localhost:1234/water"},
        {"client_id": ""},
        {"client_secret": "short"},
        {"client_secret": "CHANGE_ME_IN_PRODUCTION_1234567890"},
        {"session_secret": ""},
        {"session_secret": "too-short-secret-under-32"},
        {"session_secret": "dev-secret-key-CHANGE-ME-IN-PRODUCTION-please-32-chars"},
        {"session_secret": "__REDACTED_SESSION_SECRET_VALUE_32_CHARS__"},
        {"session_secret": "a" * 40},
        {"organization": "bad org/slash"},
        {"scopes": ("profile",)},
        # Signature client must not reuse main client_id
        {
            "signature_client_id": "maibo-cmc-water",
            "signature_client_secret": STRONG_SIG_SECRET,
        },
        # Partial signature client config must fail closed
        {"signature_client_id": "maibo-cmc-water-sig", "signature_client_secret": ""},
    ],
)
def test_startup_validator_fails_closed_on_insecure_production_settings(bad_overrides):
    with pytest.raises(OIDCConfigError):
        _prod_config(**bad_overrides)


def test_development_allows_loopback_http_but_blocks_lan_http():
    dev_cfg = validate_startup(
        CMCOIDCConfig(
            issuer_url="http://localhost:8080",
            public_url="http://localhost:1234/water",
            client_id="maibo-cmc-water-dev",
            client_secret=STRONG_CLIENT_SECRET,
            session_secret=STRONG_SESSION_SECRET,
            env="development",
        )
    )
    assert dev_cfg.is_production is False
    assert dev_cfg.secure is False
    assert dev_cfg.cookie_path == "/water/"

    with pytest.raises(OIDCConfigError):
        validate_startup(
            CMCOIDCConfig(
                issuer_url="http://172.19.0.105:8080",
                public_url="http://localhost:1234/water",
                client_id="maibo-cmc-water-dev",
                client_secret=STRONG_CLIENT_SECRET,
                session_secret=STRONG_SESSION_SECRET,
                env="development",
            )
        )


def test_from_env_fails_closed_when_disabled_or_missing_secret():
    env = {
        "CMC_OIDC_ENABLED": "true",
        "CMC_OIDC_ENV": "production",
        "CMC_OIDC_ISSUER_URL": "https://iam.openlims.ai",
        "CMC_OIDC_PUBLIC_URL": "https://www.openlims.ai/ops",
        "CMC_OIDC_CLIENT_ID": "maibo-cmc-ops",
        "CMC_OIDC_CLIENT_SECRET": STRONG_CLIENT_SECRET,
        "CMC_OIDC_SESSION_SECRET": STRONG_SESSION_SECRET,
    }
    cfg = CMCOIDCConfig.from_env(env)
    assert cfg.cookie_path == "/ops/"

    with pytest.raises(OIDCConfigError):
        CMCOIDCConfig.from_env({**env, "CMC_OIDC_ENABLED": "false"})

    with pytest.raises(OIDCConfigError):
        CMCOIDCConfig.from_env({**env, "CMC_OIDC_SESSION_SECRET": ""})


def test_normalize_cookie_path_rules():
    assert normalize_cookie_path("/") == "/"
    assert normalize_cookie_path("/water") == "/water/"
    assert normalize_cookie_path("/water/") == "/water/"
    assert normalize_cookie_path("/cmc/water") == "/cmc/water/"
    for invalid in ("", "water", "/water/../ops", "/water?a=1", "/water#frag", "/water\\x"):
        with pytest.raises(OIDCConfigError):
            normalize_cookie_path(invalid)


# ---------------------------------------------------------------------------
# 2. PKCE S256 + Authorization URL builder + Callback state/verifier validation
# ---------------------------------------------------------------------------
def test_pkce_rfc7636_s256_vector_and_pair_verification():
    # RFC 7636 Appendix B test vector
    rfc_verifier = "dBjftJeZ4CVP-mB92K27uhbUJU1p1r_wW1gFWFOEjXk"
    rfc_challenge = "E9Melhoa2OwvFrEMTJguCHaoeK1t8URWbuGJSstw-cM"
    assert compute_code_challenge(rfc_verifier) == rfc_challenge
    assert verify_pkce_pair(rfc_verifier, rfc_challenge) is True
    assert verify_pkce_pair(rfc_verifier, rfc_challenge[:-1] + "X") is False

    verifier, challenge = generate_pkce_pair()
    assert len(verifier) >= 64
    assert verify_pkce_pair(verifier, challenge) is True

    with pytest.raises(OIDCProtocolError):
        compute_code_challenge("too-short")


def test_sanitize_return_to_blocks_open_redirects_and_sensitive_queries():
    assert sanitize_return_to("/trends?water_type=WFI", default="/overview") == "/trends?water_type=WFI"
    for unsafe in (
        None,
        "",
        "https://evil.example/phish",
        "//evil.example/phish",
        "/\\evil.example",
        "/trends/../admin",
        "/trends%2f..%2fadmin",
        "/login?next=/",
        "/auth-complete",
        "/api/v1/context",
        "/trends?access_token=secret",
        "/trends?code=abc&state=xyz",
        "/trends#fragment",
    ):
        assert sanitize_return_to(unsafe, default="/overview") == "/overview"


def test_authorization_request_and_callback_roundtrip_and_tamper_rejection():
    cfg = _prod_config(
        signature_client_id="maibo-cmc-water-sig",
        signature_client_secret=STRONG_SIG_SECRET,
    )
    now = 1_760_000_000
    tx = build_authorization_request(cfg, return_to="/trends?water_type=PW", now=now)

    parsed = urlsplit(tx.authorization_url)
    assert f"{parsed.scheme}://{parsed.netloc}{parsed.path}" == "https://iam.openlims.ai/login/oauth/authorize"
    query = parse_qs(parsed.query)
    assert query["client_id"] == ["maibo-cmc-water"]
    assert query["redirect_uri"] == ["https://www.openlims.ai/water/api/v1/auth/oidc/callback"]
    assert query["response_type"] == ["code"]
    assert query["code_challenge_method"] == ["S256"]
    assert query["code_challenge"] == [tx.code_challenge]
    assert query["state"] == [tx.state]
    assert query["nonce"] == [tx.nonce]
    assert verify_pkce_pair(tx.code_verifier, tx.code_challenge)

    pending = validate_authorization_callback(
        query_code="auth-code-12345",
        query_state=tx.state,
        sealed_login_cookie=tx.sealed_login_cookie,
        config=cfg,
        now=now + 30,
    )
    assert pending.code == "auth-code-12345"
    assert pending.code_verifier == tx.code_verifier
    assert pending.nonce == tx.nonce
    assert pending.return_to == "/trends?water_type=PW"
    assert pending.signing is False

    # Mismatched query state rejected
    with pytest.raises(OIDCStateError):
        validate_authorization_callback(
            query_code="auth-code-12345",
            query_state="x" * 64,
            sealed_login_cookie=tx.sealed_login_cookie,
            config=cfg,
            now=now + 30,
        )

    # Expired login state cookie rejected
    with pytest.raises(OIDCStateError):
        validate_authorization_callback(
            query_code="auth-code-12345",
            query_state=tx.state,
            sealed_login_cookie=tx.sealed_login_cookie,
            config=cfg,
            now=now + 301,
        )

    # IdP error parameter rejected
    with pytest.raises(OIDCStateError):
        validate_authorization_callback(
            query_code="auth-code-12345",
            query_state=tx.state,
            sealed_login_cookie=tx.sealed_login_cookie,
            config=cfg,
            error="access_denied",
            now=now + 10,
        )

    # Normal login cookie cannot complete a step-up signing flow
    with pytest.raises(OIDCStateError):
        validate_authorization_callback(
            query_code="auth-code-12345",
            query_state=tx.state,
            sealed_login_cookie=tx.sealed_login_cookie,
            config=cfg,
            signing=True,
            now=now + 10,
        )


def test_authorization_request_rejects_untrusted_endpoint_host():
    cfg = _prod_config()
    with pytest.raises(OIDCProtocolError):
        build_authorization_request(cfg, "https://evil-idp.example/authorize")


# ---------------------------------------------------------------------------
# 3. Encrypted / HMAC-signed path-scoped HttpOnly; SameSite=Lax; Secure cookie
# ---------------------------------------------------------------------------
def test_cookie_session_codec_roundtrip_attributes_and_isolation():
    cfg = _prod_config()
    water_session = CookieSessionCodec.from_config(cfg, purpose="session")
    now = 1_760_000_000

    resp = Response()
    token = water_session.set_cookie(
        resp,
        {"sub": "u-101", "username": "zhangsan", "roles": ["CMC_WATER_VIEWER"]},
        ttl_seconds=1800,
        now=now,
    )
    set_cookie_header = resp.headers["set-cookie"]
    assert "cmc_oidc_session=" in set_cookie_header
    assert "HttpOnly" in set_cookie_header
    assert "Path=/water/" in set_cookie_header
    assert "SameSite=lax" in set_cookie_header
    assert "Secure" in set_cookie_header
    assert "Max-Age=1800" in set_cookie_header
    # Cookie ciphertext is opaque (must not leak plaintext claims)
    assert "zhangsan" not in token
    assert "CMC_WATER_VIEWER" not in token

    unsealed = water_session.unseal(token, now=now + 60)
    assert unsealed == {"sub": "u-101", "username": "zhangsan", "roles": ["CMC_WATER_VIEWER"]}

    # Tampering a character invalidates Fernet HMAC
    tampered = token[:-4] + ("AAAA" if not token.endswith("AAAA") else "BBBB")
    with pytest.raises(SessionInvalidError):
        water_session.unseal(tampered, now=now + 60)

    # Cross-path replay (/water/ cookie presented to /ops/ codec with same secret) fails!
    ops_session = CookieSessionCodec(
        STRONG_SESSION_SECRET,
        cookie_path="/ops/",
        purpose="session",
    )
    with pytest.raises(SessionInvalidError):
        ops_session.unseal(token, now=now + 60)

    # Cross-purpose replay (session cookie presented to login_state codec) fails!
    water_login = CookieSessionCodec.from_config(cfg, purpose="login_state")
    with pytest.raises(SessionInvalidError):
        water_login.unseal(token, now=now + 60)

    # Expiration enforced strictly
    with pytest.raises(SessionExpiredError):
        water_session.unseal(token, now=now + 1800)


# ---------------------------------------------------------------------------
# 4. Same-origin mutation guard (Origin / Referer check)
# ---------------------------------------------------------------------------
def test_same_origin_guard_allows_matching_origin_and_safe_methods():
    expected = "https://www.openlims.ai"
    # Safe methods bypass mutation check even without Origin
    require_same_origin({}, expected, method="GET")
    require_same_origin({}, expected, method="HEAD")

    # Matching Origin on POST/DELETE succeeds
    require_same_origin({"Origin": "https://www.openlims.ai"}, expected, method="POST")
    require_same_origin({"origin": "https://WWW.OPENLIMS.AI"}, expected, method="DELETE")

    # Missing Origin + matching Referer fallback succeeds when enabled
    require_same_origin(
        {"Referer": "https://www.openlims.ai/water/trends?x=1"},
        expected,
        method="POST",
        allow_referer_fallback=True,
    )


@pytest.mark.parametrize(
    "headers,allow_referer",
    [
        ({}, True),
        ({"Origin": "null"}, True),
        ({"Origin": "https://evil.example"}, True),
        ({"Origin": "http://www.openlims.ai"}, True),
        ({"Origin": "https://www.openlims.ai:8443"}, True),
        # Wrong Origin MUST NOT be rescued by a matching Referer
        (
            {
                "Origin": "https://evil.example",
                "Referer": "https://www.openlims.ai/water/",
            },
            True,
        ),
        ({"Referer": "https://evil.example/water/"}, True),
        # Referer rejected when fallback is disabled
        ({"Referer": "https://www.openlims.ai/water/"}, False),
    ],
)
def test_same_origin_guard_rejects_cross_origin_or_missing_headers(headers, allow_referer):
    with pytest.raises(OriginMismatchError):
        require_same_origin(
            headers,
            "https://www.openlims.ai",
            method="POST",
            allow_referer_fallback=allow_referer,
        )


# ---------------------------------------------------------------------------
# 5. RS256 ID token & oidc_fresh auth_time validation
# ---------------------------------------------------------------------------
def _generate_rsa_jwk_and_pem(bits: int = 2048):
    priv = rsa.generate_private_key(public_exponent=65537, key_size=bits)
    pem = priv.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    )
    nums = priv.public_key().public_numbers()
    n_bytes = nums.n.to_bytes((nums.n.bit_length() + 7) // 8, "big")
    e_bytes = nums.e.to_bytes((nums.e.bit_length() + 7) // 8, "big")
    jwk = {
        "kty": "RSA",
        "use": "sig",
        "alg": "RS256",
        "kid": "casdoor-key-1",
        "n": base64.urlsafe_b64encode(n_bytes).rstrip(b"=").decode("ascii"),
        "e": base64.urlsafe_b64encode(e_bytes).rstrip(b"=").decode("ascii"),
    }
    return pem, jwk


def test_validate_id_token_and_fresh_auth_time():
    pem, jwk = _generate_rsa_jwk_and_pem()
    now = 1_760_000_100
    token = jwt.encode(
        {
            "iss": "https://iam.openlims.ai",
            "aud": "maibo-cmc-water-sig",
            "azp": "maibo-cmc-water-sig",
            "sub": "user-uuid-42",
            "iat": now,
            "exp": now + 600,
            "nonce": "nonce-xyz-1234567890",
            "auth_time": now - 2,
        },
        pem,
        algorithm="RS256",
        headers={"kid": "casdoor-key-1"},
    )
    claims = validate_id_token(
        token,
        jwk,
        issuer="https://iam.openlims.ai",
        audience="maibo-cmc-water-sig",
        nonce="nonce-xyz-1234567890",
        now=now,
    )
    assert claims["sub"] == "user-uuid-42"
    assert validate_fresh_auth_time(claims, started_at=now - 5, now=now) == now - 2

    # Stale auth_time (before signature challenge started) fails oidc_fresh
    with pytest.raises(OIDCTokenError):
        validate_fresh_auth_time(claims, started_at=now - 1, now=now)

    # Wrong nonce fails
    with pytest.raises(OIDCTokenError):
        validate_id_token(
            token,
            jwk,
            issuer="https://iam.openlims.ai",
            audience="maibo-cmc-water-sig",
            nonce="wrong-nonce",
            now=now,
        )

    # HS256 algorithm confusion attempt fails immediately
    hs_token = jwt.encode(
        {
            "iss": "https://iam.openlims.ai",
            "aud": "maibo-cmc-water-sig",
            "sub": "user-uuid-42",
            "iat": now,
            "exp": now + 600,
        },
        STRONG_SESSION_SECRET,
        algorithm="HS256",
    )
    with pytest.raises(OIDCTokenError):
        validate_id_token(
            hs_token,
            jwk,
            issuer="https://iam.openlims.ai",
            audience="maibo-cmc-water-sig",
            now=now,
        )
