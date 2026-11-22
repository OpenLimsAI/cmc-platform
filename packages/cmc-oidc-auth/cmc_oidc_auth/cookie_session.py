"""Encrypted & HMAC-authenticated path-scoped cookie session codec and Origin guard."""
from __future__ import annotations

import base64
import json
import secrets
import time
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Literal
from urllib.parse import urlsplit

from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

from cmc_oidc_auth.config import (
    CMCOIDCConfig,
    OIDCConfigError,
    OIDCError,
    normalize_cookie_path,
    validate_secret_strength,
)


class SessionError(OIDCError):
    """Base error for invalid or expired cookie sessions."""


class SessionInvalidError(SessionError):
    """Raised when a session/state cookie is missing, malformed, or fails HMAC/decryption."""


class SessionExpiredError(SessionError):
    """Raised when a cryptographically valid cookie payload has passed its expiration."""


class OriginMismatchError(OIDCError):
    """Raised when a state-changing request fails same-origin Origin/Referer verification."""


MAX_COOKIE_VALUE_LENGTH = 4096
_SAFE_HTTP_METHODS = frozenset({"GET", "HEAD", "OPTIONS", "TRACE"})


@dataclass(frozen=True)
class CookieAttributes:
    name: str
    path: str
    httponly: bool = True
    samesite: Literal["lax", "strict"] = "lax"
    secure: bool = True
    max_age: int | None = None

    def __post_init__(self) -> None:
        if not self.name or any(ch.isspace() or ch in ";=" for ch in self.name):
            raise OIDCConfigError("Invalid cookie name")
        normalized = normalize_cookie_path(self.path)
        if normalized != self.path:
            object.__setattr__(self, "path", normalized)
        if self.httponly is not True:
            raise OIDCConfigError("Session cookies must enforce HttpOnly=True")
        if self.samesite not in {"lax", "strict"}:
            raise OIDCConfigError("Session cookies must use SameSite=Lax or Strict")


def _derive_fernet_key(*, secret: str, purpose: str, cookie_path: str) -> bytes:
    hkdf = HKDF(
        algorithm=hashes.SHA256(),
        length=32,
        salt=b"cmc-oidc-auth-cookie-v1",
        info=f"purpose={purpose};path={cookie_path}".encode("utf-8"),
    )
    raw_key = hkdf.derive(secret.encode("utf-8"))
    return base64.urlsafe_b64encode(raw_key)


class CookieSessionCodec:
    """Path-bound, purpose-bound Fernet (AES-128-CBC + HMAC-SHA256) cookie codec."""

    def __init__(
        self,
        secret: str,
        *,
        cookie_path: str = "/",
        purpose: str = "session",
        cookie_name: str = "cmc_oidc_session",
        default_ttl_seconds: int = 3600,
        secure: bool = True,
        samesite: Literal["lax", "strict"] = "lax",
    ) -> None:
        validate_secret_strength(secret, field_name="session_secret", min_length=32)
        if not purpose or not purpose.replace("_", "").isalnum():
            raise OIDCConfigError("Cookie codec purpose must be alphanumeric/underscore")
        if default_ttl_seconds < 1:
            raise OIDCConfigError("default_ttl_seconds must be positive")

        self.cookie_path = normalize_cookie_path(cookie_path)
        self.purpose = purpose
        self.cookie_name = cookie_name
        self.default_ttl_seconds = int(default_ttl_seconds)
        self.secure = bool(secure)
        self.samesite: Literal["lax", "strict"] = samesite
        self._fernet = Fernet(
            _derive_fernet_key(
                secret=secret,
                purpose=self.purpose,
                cookie_path=self.cookie_path,
            )
        )

    @classmethod
    def from_config(
        cls,
        config: CMCOIDCConfig,
        *,
        purpose: Literal["session", "login_state"] = "session",
    ) -> CookieSessionCodec:
        is_login = purpose == "login_state"
        return cls(
            secret=config.session_secret,
            cookie_path=config.cookie_path,
            purpose=purpose,
            cookie_name=config.login_cookie_name if is_login else config.session_cookie_name,
            default_ttl_seconds=(
                config.login_state_ttl_seconds if is_login else config.session_max_seconds
            ),
            secure=config.secure,
            samesite="lax",
        )

    def attributes(self, *, max_age: int | None = None) -> CookieAttributes:
        effective_age = self.default_ttl_seconds if max_age is None else max(1, int(max_age))
        return CookieAttributes(
            name=self.cookie_name,
            path=self.cookie_path,
            httponly=True,
            samesite=self.samesite,
            secure=self.secure,
            max_age=effective_age,
        )

    def seal(
        self,
        payload: Mapping[str, Any],
        *,
        ttl_seconds: int | None = None,
        now: int | None = None,
    ) -> str:
        if not isinstance(payload, Mapping):
            raise TypeError("Cookie payload must be a mapping")
        issued_at = int(time.time()) if now is None else int(now)
        ttl = self.default_ttl_seconds if ttl_seconds is None else int(ttl_seconds)
        if ttl < 1:
            raise ValueError("ttl_seconds must be >= 1")
        envelope = {
            "v": 1,
            "iat": issued_at,
            "exp": issued_at + ttl,
            "path": self.cookie_path,
            "purpose": self.purpose,
            "data": dict(payload),
        }
        plaintext = json.dumps(envelope, separators=(",", ":"), sort_keys=True).encode("utf-8")
        token = self._fernet.encrypt_at_time(plaintext, issued_at).decode("ascii")
        if len(token) > MAX_COOKIE_VALUE_LENGTH:
            raise OIDCConfigError("Serialized encrypted cookie exceeds 4096-byte browser limit")
        return token

    def unseal(self, token: str | None, *, now: int | None = None) -> dict[str, Any]:
        if not isinstance(token, str) or not token or len(token) > MAX_COOKIE_VALUE_LENGTH:
            raise SessionInvalidError("Missing or malformed session cookie")
        check_now = int(time.time()) if now is None else int(now)
        try:
            raw = self._fernet.decrypt(token.encode("ascii"))
            envelope = json.loads(raw.decode("utf-8"))
        except (InvalidToken, UnicodeError, ValueError, TypeError):
            raise SessionInvalidError("Session cookie failed cryptographic verification") from None

        if not isinstance(envelope, dict) or envelope.get("v") != 1:
            raise SessionInvalidError("Unsupported session envelope version")
        if (
            envelope.get("path") != self.cookie_path
            or envelope.get("purpose") != self.purpose
            or not isinstance(envelope.get("data"), dict)
        ):
            raise SessionInvalidError("Session cookie scope mismatch")

        iat = envelope.get("iat")
        exp = envelope.get("exp")
        if (
            isinstance(iat, bool)
            or isinstance(exp, bool)
            or not isinstance(iat, int)
            or not isinstance(exp, int)
        ):
            raise SessionInvalidError("Invalid session timestamps")
        if iat > check_now + 5:
            raise SessionInvalidError("Session issued_at is in the future")
        if exp <= check_now:
            raise SessionExpiredError("Session cookie has expired")
        return dict(envelope["data"])

    def set_cookie(
        self,
        response: Any,
        payload: Mapping[str, Any],
        *,
        ttl_seconds: int | None = None,
        now: int | None = None,
    ) -> str:
        ttl = self.default_ttl_seconds if ttl_seconds is None else max(1, int(ttl_seconds))
        token = self.seal(payload, ttl_seconds=ttl, now=now)
        attrs = self.attributes(max_age=ttl)
        response.set_cookie(
            key=attrs.name,
            value=token,
            max_age=attrs.max_age,
            path=attrs.path,
            secure=attrs.secure,
            httponly=attrs.httponly,
            samesite=attrs.samesite,
        )
        return token

    def clear_cookie(self, response: Any) -> None:
        attrs = self.attributes()
        response.delete_cookie(
            key=attrs.name,
            path=attrs.path,
            secure=attrs.secure,
            httponly=attrs.httponly,
            samesite=attrs.samesite,
        )


def _normalize_origin(value: str, *, allow_path: bool = False) -> str | None:
    if not isinstance(value, str) or not value or len(value) > 2048:
        return None
    if value.strip().lower() == "null":
        return None
    try:
        parsed = urlsplit(value.strip())
        if parsed.port is not None and parsed.port < 1:
            return None
    except ValueError:
        return None
    if parsed.scheme.lower() not in {"http", "https"} or not parsed.hostname:
        return None
    if parsed.username or parsed.password:
        return None
    if not allow_path and (parsed.path not in {"", "/"} or parsed.query or parsed.fragment):
        return None
    return f"{parsed.scheme.lower()}://{parsed.netloc.lower()}"


def _get_header(headers: Mapping[str, str], name: str) -> str | None:
    direct = headers.get(name)
    if direct is not None:
        return direct
    target = name.lower()
    for key, val in headers.items():
        if key.lower() == target:
            return val
    return None


def require_same_origin(
    request_or_headers: Any,
    expected_origin: str,
    *,
    method: str | None = None,
    allow_referer_fallback: bool = True,
) -> None:
    """Verify Origin (or Referer fallback) on state-changing HTTP requests."""
    normalized_expected = _normalize_origin(expected_origin, allow_path=False)
    if not normalized_expected:
        raise OIDCConfigError("expected_origin must be a valid http(s)://host[:port] origin")

    if hasattr(request_or_headers, "headers"):
        headers = request_or_headers.headers
        effective_method = (method or getattr(request_or_headers, "method", "POST")).upper()
    elif isinstance(request_or_headers, Mapping):
        headers = request_or_headers
        effective_method = (method or "POST").upper()
    else:
        raise TypeError("request_or_headers must be a Request object or header mapping")

    if effective_method in _SAFE_HTTP_METHODS:
        return

    origin_header = _get_header(headers, "origin")
    if origin_header is not None and origin_header.strip() != "":
        candidate = _normalize_origin(origin_header, allow_path=False)
        if not candidate or not secrets.compare_digest(candidate, normalized_expected):
            raise OriginMismatchError("Cross-origin mutation blocked by Origin header mismatch")
        return

    if allow_referer_fallback:
        referer_header = _get_header(headers, "referer")
        if referer_header is not None and referer_header.strip() != "":
            candidate = _normalize_origin(referer_header, allow_path=True)
            if candidate and secrets.compare_digest(candidate, normalized_expected):
                return

    raise OriginMismatchError("State-changing request missing verified same-origin header")
