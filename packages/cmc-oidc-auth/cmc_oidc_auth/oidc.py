"""Casdoor OIDC + PKCE protocol helpers, callback state validation, and JWT verification."""
from __future__ import annotations

import asyncio
import base64
import hashlib
import json
import re
import secrets
import time
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any
from urllib.parse import unquote, urlencode, urlsplit

import httpx
import jwt
from jwt import PyJWK

from cmc_oidc_auth.config import CMCOIDCConfig, OIDCError, checked_url
from cmc_oidc_auth.cookie_session import CookieSessionCodec, SessionError


class OIDCProtocolError(OIDCError):
    """Raised on OIDC protocol, discovery, or token exchange failures."""


class OIDCStateError(OIDCProtocolError):
    """Raised when callback state, PKCE state cookie, or IdP error parameter fails validation."""


class OIDCTokenError(OIDCProtocolError):
    """Raised when ID token or fresh authentication verification fails."""


_PKCE_VERIFIER_RE = re.compile(r"^[A-Za-z0-9._~-]{43,128}$")
_SENSITIVE_QUERY_RE = re.compile(
    r"(?:^|[&?])[^=&]*(?:token|secret|cookie|authorization|code|state)[^=&]*=",
    re.IGNORECASE,
)


def compute_code_challenge(verifier: str) -> str:
    """Compute RFC 7636 S256 code_challenge from a validated PKCE code_verifier."""
    if not isinstance(verifier, str) or not _PKCE_VERIFIER_RE.fullmatch(verifier):
        raise OIDCProtocolError("Invalid PKCE code_verifier format")
    digest = hashlib.sha256(verifier.encode("ascii")).digest()
    return base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")


def generate_pkce_pair() -> tuple[str, str]:
    """Generate a cryptographic (code_verifier, code_challenge) S256 pair."""
    verifier = secrets.token_urlsafe(64)
    return verifier, compute_code_challenge(verifier)


def verify_pkce_pair(verifier: str, expected_challenge: str) -> bool:
    """Verify in constant time that verifier hashes to expected_challenge."""
    if not isinstance(expected_challenge, str) or not expected_challenge:
        return False
    try:
        actual = compute_code_challenge(verifier)
    except OIDCProtocolError:
        return False
    return secrets.compare_digest(actual, expected_challenge)


def sanitize_return_to(value: str | None, *, default: str = "/") -> str:
    """Allow only clean, relative in-app return paths; reject open redirects and auth loops."""
    if (
        not isinstance(value, str)
        or not value
        or len(value) > 2048
        or any(ord(ch) < 32 or ord(ch) == 127 for ch in value)
    ):
        return default
    if "\\" in value or unquote(value) != value:
        return default
    parsed = urlsplit(value)
    if (
        parsed.scheme
        or parsed.netloc
        or parsed.fragment
        or not value.startswith("/")
        or value.startswith("//")
    ):
        return default
    if any(part in {".", ".."} for part in parsed.path.split("/")):
        return default
    if parsed.path.startswith(("/login", "/auth-complete", "/api/", "/signature-callback")):
        return default
    if _SENSITIVE_QUERY_RE.search(parsed.query):
        return default
    return value


@dataclass(frozen=True)
class AuthorizationTransaction:
    authorization_url: str
    state: str
    nonce: str
    code_verifier: str
    code_challenge: str
    return_to: str
    redirect_uri: str
    started_at: int
    sealed_login_cookie: str


@dataclass(frozen=True)
class PendingLoginState:
    code: str
    state: str
    nonce: str
    code_verifier: str
    return_to: str
    redirect_uri: str
    started_at: int
    signing: bool


def _verify_issuer_endpoint_origin(issuer_url: str, endpoint_url: str) -> str:
    checked = checked_url(endpoint_url, allow_http_loopback=True)
    issuer_parts = urlsplit(issuer_url)
    target_parts = urlsplit(checked)
    if (target_parts.scheme.lower(), target_parts.netloc.lower()) != (
        issuer_parts.scheme.lower(),
        issuer_parts.netloc.lower(),
    ):
        raise OIDCProtocolError("OIDC endpoint origin does not match configured issuer")
    return checked


def build_authorization_request(
    config: CMCOIDCConfig,
    authorization_endpoint: str | None = None,
    *,
    return_to: str | None = None,
    login_codec: CookieSessionCodec | None = None,
    signing: bool = False,
    login_hint: str | None = None,
    now: int | None = None,
) -> AuthorizationTransaction:
    """Build a Casdoor OIDC + PKCE authorization redirect and sealed login-state cookie."""
    endpoint = _verify_issuer_endpoint_origin(
        config.issuer_url,
        authorization_endpoint or f"{config.issuer_url}/login/oauth/authorize",
    )
    if signing and (not config.signature_client_id or not config.signature_client_secret):
        raise OIDCProtocolError("Independent signature OIDC client is not configured")

    started_at = int(time.time()) if now is None else int(now)
    verifier, challenge = generate_pkce_pair()
    state = secrets.token_urlsafe(48)
    nonce = secrets.token_urlsafe(48)
    safe_target = sanitize_return_to(return_to, default=config.default_return_to)
    redirect_uri = config.signature_callback_url if signing else config.callback_url
    client_id = config.signature_client_id if signing else config.client_id

    params: dict[str, str] = {
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": " ".join(config.scopes),
        "state": state,
        "nonce": nonce,
        "code_challenge_method": "S256",
        "code_challenge": challenge,
    }
    if signing:
        params["prompt"] = "login"
        params["max_age"] = "0"
    if login_hint:
        params["login_hint"] = login_hint

    codec = login_codec or CookieSessionCodec.from_config(config, purpose="login_state")
    sealed = codec.seal(
        {
            "state": state,
            "nonce": nonce,
            "code_verifier": verifier,
            "return_to": safe_target,
            "redirect_uri": redirect_uri,
            "started_at": started_at,
            "signing": signing,
        },
        ttl_seconds=config.login_state_ttl_seconds,
        now=started_at,
    )
    return AuthorizationTransaction(
        authorization_url=f"{endpoint}?{urlencode(params)}",
        state=state,
        nonce=nonce,
        code_verifier=verifier,
        code_challenge=challenge,
        return_to=safe_target,
        redirect_uri=redirect_uri,
        started_at=started_at,
        sealed_login_cookie=sealed,
    )


def validate_authorization_callback(
    *,
    query_code: str | None,
    query_state: str | None,
    sealed_login_cookie: str | None,
    config: CMCOIDCConfig | None = None,
    login_codec: CookieSessionCodec | None = None,
    error: str | None = None,
    signing: bool = False,
    now: int | None = None,
) -> PendingLoginState:
    """Validate OIDC callback query params against the encrypted HttpOnly login-state cookie."""
    if error:
        raise OIDCStateError("Identity provider returned an authorization error")
    if not isinstance(query_code, str) or not 1 <= len(query_code) <= 4096:
        raise OIDCStateError("Missing or invalid authorization code")
    if not isinstance(query_state, str) or not 32 <= len(query_state) <= 128:
        raise OIDCStateError("Missing or invalid OIDC state parameter")

    if login_codec is None:
        if config is None:
            raise ValueError("Either login_codec or config must be provided")
        login_codec = CookieSessionCodec.from_config(config, purpose="login_state")

    try:
        stored = login_codec.unseal(sealed_login_cookie, now=now)
    except SessionError as exc:
        raise OIDCStateError("Login state cookie is missing, invalid, or expired") from exc

    cookie_state = stored.get("state")
    verifier = stored.get("code_verifier")
    nonce = stored.get("nonce")
    return_to = stored.get("return_to")
    redirect_uri = stored.get("redirect_uri")
    started_at = stored.get("started_at")

    if (
        not isinstance(cookie_state, str)
        or not secrets.compare_digest(query_state, cookie_state)
        or stored.get("signing") is not signing
        or not isinstance(verifier, str)
        or not _PKCE_VERIFIER_RE.fullmatch(verifier)
        or not isinstance(nonce, str)
        or not 16 <= len(nonce) <= 128
        or not isinstance(return_to, str)
        or not isinstance(redirect_uri, str)
        or isinstance(started_at, bool)
        or not isinstance(started_at, int)
    ):
        raise OIDCStateError("Login state verification failed")

    return PendingLoginState(
        code=query_code,
        state=query_state,
        nonce=nonce,
        code_verifier=verifier,
        return_to=sanitize_return_to(
            return_to,
            default=config.default_return_to if config else "/",
        ),
        redirect_uri=redirect_uri,
        started_at=started_at,
        signing=signing,
    )


def validate_fresh_auth_time(
    claims: Mapping[str, Any],
    *,
    started_at: int,
    max_age_seconds: int = 120,
    now: int | None = None,
) -> int:
    """Verify cryptographic auth_time for step-up GxP electronic signature (oidc_fresh)."""
    check_now = int(time.time()) if now is None else int(now)
    auth_time = claims.get("auth_time")
    if (
        isinstance(auth_time, bool)
        or not isinstance(auth_time, int)
        or auth_time < started_at
        or auth_time > check_now + 5
        or check_now - auth_time > max_age_seconds
    ):
        raise OIDCTokenError("Fresh identity authentication (auth_time) is required")
    return auth_time


def _resolve_rsa_public_key(key: Mapping[str, Any] | str | bytes) -> Any:
    if isinstance(key, Mapping):
        if key.get("kty") != "RSA" or key.get("use", "sig") != "sig" or "d" in key:
            raise OIDCTokenError("JWK must be an RSA public signing key")
        if key.get("alg", "RS256") != "RS256":
            raise OIDCTokenError("JWK algorithm must be RS256")
        modulus = key.get("n", "")
        if not isinstance(modulus, str) or not modulus:
            raise OIDCTokenError("JWK modulus missing")
        try:
            padded = modulus + "=" * (-len(modulus) % 4)
            bits = int.from_bytes(base64.urlsafe_b64decode(padded), "big").bit_length()
        except (ValueError, TypeError) as exc:
            raise OIDCTokenError("Invalid JWK modulus") from exc
        if bits < 2048:
            raise OIDCTokenError("RSA signing key must be at least 2048 bits")
        return PyJWK.from_dict(dict(key)).key
    return key


def validate_id_token(
    token: str,
    key: Mapping[str, Any] | str | bytes,
    *,
    issuer: str,
    audience: str,
    nonce: str | None = None,
    now: int | None = None,
) -> dict[str, Any]:
    """Verify RS256 OIDC JWT with pinned issuer, audience, azp, and nonce."""
    if not isinstance(token, str) or not token or len(token) > 16384:
        raise OIDCTokenError("Malformed OIDC JWT")
    try:
        header = jwt.get_unverified_header(token)
    except jwt.PyJWTError as exc:
        raise OIDCTokenError("Malformed OIDC JWT header") from exc

    if header.get("alg") != "RS256" or header.get("crit"):
        raise OIDCTokenError("Only RS256 OIDC tokens without critical extensions are accepted")

    verify_key = _resolve_rsa_public_key(key)
    check_now = int(time.time()) if now is None else int(now)

    try:
        claims = jwt.decode(
            token,
            verify_key,
            algorithms=["RS256"],
            issuer=issuer,
            audience=audience,
            options={
                "require": ["exp", "iat", "sub", "iss", "aud"],
                "verify_signature": True,
                "verify_exp": False,
                "verify_iat": False,
                "verify_iss": True,
                "verify_aud": True,
            },
        )
    except jwt.PyJWTError as exc:
        raise OIDCTokenError("OIDC token cryptographic verification failed") from exc

    iat = claims.get("iat")
    exp = claims.get("exp")
    sub = claims.get("sub")
    if (
        isinstance(iat, bool)
        or isinstance(exp, bool)
        or not isinstance(iat, int)
        or not isinstance(exp, int)
        or iat > check_now + 15
        or exp <= check_now - 15
    ):
        raise OIDCTokenError("OIDC token is expired or has invalid timestamps")

    if not isinstance(sub, str) or not 1 <= len(sub) <= 255:
        raise OIDCTokenError("OIDC token missing valid subject")

    aud = claims.get("aud")
    if isinstance(aud, list) and len(aud) > 1 and claims.get("azp") != audience:
        raise OIDCTokenError("Multi-audience token missing matching azp")
    if claims.get("azp", audience) != audience:
        raise OIDCTokenError("OIDC token azp mismatch")

    if nonce is not None:
        token_nonce = claims.get("nonce")
        if not isinstance(token_nonce, str) or not secrets.compare_digest(token_nonce, nonce):
            raise OIDCTokenError("OIDC token nonce mismatch")

    return claims


class CasdoorOIDCClient:
    """Bounded async Casdoor OIDC discovery, JWKS, and authorization-code client."""

    def __init__(self, config: CMCOIDCConfig) -> None:
        self.config = config
        self._cache: dict[str, tuple[float, Any]] = {}

    def _internal_endpoint(self, public_endpoint: str) -> str:
        verified = _verify_issuer_endpoint_origin(self.config.issuer_url, public_endpoint)
        target = urlsplit(verified)
        base = (self.config.internal_url or self.config.issuer_url).rstrip("/")
        return f"{base}{target.path}"

    async def _request_json(self, method: str, url: str, **kwargs: Any) -> dict[str, Any]:
        target = self._internal_endpoint(url)
        try:
            async with (
                asyncio.timeout(10),
                httpx.AsyncClient(trust_env=False, follow_redirects=False, timeout=5.0) as client,
                client.stream(method, target, **kwargs) as response,
            ):
                response.raise_for_status()
                buf = bytearray()
                async for chunk in response.aiter_bytes():
                    buf.extend(chunk)
                    if len(buf) > 65536:
                        raise OIDCProtocolError("OIDC provider response exceeded 64 KiB limit")
                parsed = json.loads(buf.decode("utf-8"))
                if not isinstance(parsed, dict):
                    raise OIDCProtocolError("OIDC provider returned non-object JSON")
                return parsed
        except OIDCProtocolError:
            raise
        except (httpx.HTTPError, TimeoutError, ValueError, UnicodeError) as exc:
            raise OIDCProtocolError("OIDC provider request failed") from exc

    async def discover(self) -> dict[str, Any]:
        cached = self._cache.get("discovery")
        if cached and cached[0] > time.monotonic():
            return cached[1]
        doc = await self._request_json(
            "GET", f"{self.config.issuer_url}/.well-known/openid-configuration"
        )
        if doc.get("issuer") != self.config.issuer_url:
            raise OIDCProtocolError("OIDC discovery issuer mismatch")
        for field_name in ("authorization_endpoint", "token_endpoint", "jwks_uri"):
            endpoint = doc.get(field_name)
            if not isinstance(endpoint, str):
                raise OIDCProtocolError(f"OIDC discovery missing {field_name}")
            _verify_issuer_endpoint_origin(self.config.issuer_url, endpoint)
        self._cache["discovery"] = (time.monotonic() + 300, doc)
        return doc

    async def signing_jwk(self, token: str, *, force_refresh: bool = False) -> dict[str, Any]:
        try:
            header = jwt.get_unverified_header(token)
        except jwt.PyJWTError as exc:
            raise OIDCTokenError("Invalid JWT header") from exc
        kid = header.get("kid")
        if header.get("alg") != "RS256" or not isinstance(kid, str) or not 1 <= len(kid) <= 255:
            raise OIDCTokenError("Invalid signing key identifier")

        discovery = await self.discover()
        cached = self._cache.get("jwks")
        if force_refresh or not cached or cached[0] <= time.monotonic():
            jwks_doc = await self._request_json("GET", discovery["jwks_uri"])
            keys = jwks_doc.get("keys")
            if not isinstance(keys, list) or not 1 <= len(keys) <= 20:
                raise OIDCProtocolError("Invalid JWKS key set")
            self._cache["jwks"] = (time.monotonic() + 300, keys)

        for item in self._cache["jwks"][1]:
            if isinstance(item, dict) and item.get("kid") == kid:
                _resolve_rsa_public_key(item)
                return item
        if not force_refresh:
            return await self.signing_jwk(token, force_refresh=True)
        raise OIDCTokenError("Unknown signing key identifier")

    async def exchange_code(self, pending: PendingLoginState) -> tuple[dict[str, Any], dict[str, Any]]:
        discovery = await self.discover()
        client_id = (
            self.config.signature_client_id if pending.signing else self.config.client_id
        )
        client_secret = (
            self.config.signature_client_secret if pending.signing else self.config.client_secret
        )
        body = await self._request_json(
            "POST",
            discovery["token_endpoint"],
            data={
                "grant_type": "authorization_code",
                "client_id": client_id,
                "client_secret": client_secret,
                "redirect_uri": pending.redirect_uri,
                "code": pending.code,
                "code_verifier": pending.code_verifier,
            },
        )
        id_token = body.get("id_token")
        access_token = body.get("access_token")
        if not isinstance(id_token, str) or not isinstance(access_token, str):
            raise OIDCProtocolError("Token endpoint response missing id_token or access_token")

        id_claims = validate_id_token(
            id_token,
            await self.signing_jwk(id_token),
            issuer=self.config.issuer_url,
            audience=client_id,
            nonce=pending.nonce,
        )
        access_claims = validate_id_token(
            access_token,
            await self.signing_jwk(access_token),
            issuer=self.config.issuer_url,
            audience=client_id,
        )
        if id_claims["sub"] != access_claims["sub"]:
            raise OIDCTokenError("ID token and access token subjects differ")
        if access_claims.get("isForbidden") or access_claims.get("isDeleted"):
            raise OIDCTokenError("Casdoor identity is forbidden or deleted")
        if pending.signing:
            validate_fresh_auth_time(id_claims, started_at=pending.started_at)

        effective_exp = min(int(id_claims["exp"]), int(access_claims["exp"]))
        id_claims["exp"] = effective_exp
        return id_claims, {"access_token": access_token, "expires_at": effective_exp}
