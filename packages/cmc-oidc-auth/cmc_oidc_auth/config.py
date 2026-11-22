"""Fail-closed OIDC configuration and production startup validation."""
from __future__ import annotations

import os
import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from urllib.parse import urlsplit


class OIDCError(Exception):
    """Base credential-free OIDC / session security error."""


class OIDCConfigError(OIDCError):
    """Raised when OIDC or session configuration violates fail-closed rules."""


_LOOPBACK_HOSTS = frozenset({"127.0.0.1", "localhost", "::1"})
_PRODUCTION_ENVS = frozenset({"production", "prod", "linux"})
_WEAK_SECRET_MARKERS = (
    "change_me",
    "change-me",
    "dev-secret",
    "__redacted",
    "placeholder",
    "default-secret",
    "example-secret",
    "insecure",
)
_ORG_PATTERN = re.compile(r"^[A-Za-z0-9_.-]{1,100}$")


def is_production_environment(env: str | None) -> bool:
    normalized = (env or "").strip().lower()
    return normalized in _PRODUCTION_ENVS


def checked_url(
    value: str,
    *,
    allow_http_loopback: bool = True,
    allow_http_internal: bool = False,
) -> str:
    """Validate an OIDC or application URL and strip trailing slashes."""
    if (
        not isinstance(value, str)
        or not value
        or len(value) > 2048
        or not value.isascii()
        or any(ord(ch) <= 32 or ord(ch) == 127 for ch in value)
    ):
        raise OIDCConfigError("OIDC URL is missing or contains invalid characters")
    try:
        parsed = urlsplit(value)
        if parsed.port is not None and parsed.port < 1:
            raise ValueError("invalid port")
    except ValueError as exc:
        raise OIDCConfigError("Invalid configured URL") from exc

    if (
        not parsed.hostname
        or parsed.username
        or parsed.password
        or parsed.query
        or parsed.fragment
        or "\\" in value
        or "%" in value
    ):
        raise OIDCConfigError("Configured URL must not contain credentials, query, fragment, or escapes")
    if any(part in {".", ".."} for part in parsed.path.split("/")):
        raise OIDCConfigError("Configured URL must not contain relative path segments")

    is_loopback = parsed.hostname.lower() in _LOOPBACK_HOSTS
    if parsed.scheme == "https":
        return value.rstrip("/")
    if parsed.scheme == "http":
        if (is_loopback and allow_http_loopback) or allow_http_internal:
            return value.rstrip("/")
        raise OIDCConfigError("OIDC requires HTTPS outside non-production loopback development")
    raise OIDCConfigError("Configured URL scheme must be https (or loopback http in development)")


def normalize_cookie_path(path: str) -> str:
    """Normalize a subsystem subpath to a strict leading-and-trailing-slash cookie Path."""
    if (
        not isinstance(path, str)
        or not path
        or len(path) > 256
        or any(ord(ch) <= 32 or ord(ch) == 127 for ch in path)
        or "\\" in path
        or "?" in path
        or "#" in path
    ):
        raise OIDCConfigError("Invalid cookie path")
    if not path.startswith("/"):
        raise OIDCConfigError("Cookie path must start with '/'")
    segments = [seg for seg in path.split("/") if seg]
    if any(seg in {".", ".."} for seg in segments):
        raise OIDCConfigError("Cookie path must not contain '.' or '..'")
    if not segments:
        return "/"
    return "/" + "/".join(segments) + "/"


def validate_secret_strength(
    secret: str,
    *,
    field_name: str = "session_secret",
    min_length: int = 32,
) -> str:
    """Fail-closed validation rejecting empty, short, repeated, or placeholder secrets."""
    if not isinstance(secret, str) or not secret.strip():
        raise OIDCConfigError(f"{field_name} must be explicitly configured")
    if len(secret) < min_length:
        raise OIDCConfigError(f"{field_name} must be at least {min_length} characters")
    lowered = secret.lower()
    if any(marker in lowered for marker in _WEAK_SECRET_MARKERS):
        raise OIDCConfigError(f"{field_name} uses a forbidden placeholder or development default")
    if len(set(secret)) < 6:
        raise OIDCConfigError(f"{field_name} has insufficient entropy")
    return secret


@dataclass(frozen=True)
class CMCOIDCConfig:
    issuer_url: str
    public_url: str
    client_id: str
    client_secret: str = field(repr=False)
    session_secret: str = field(repr=False)
    organization: str = "mabpharm"
    env: str = "production"
    internal_url: str = ""
    callback_path: str = "/api/v1/auth/oidc/callback"
    signature_callback_path: str = "/signature-callback"
    default_return_to: str = "/"
    scopes: tuple[str, ...] = ("openid", "profile", "email")
    session_cookie_name: str = "cmc_oidc_session"
    login_cookie_name: str = "cmc_oidc_login"
    session_max_seconds: int = 3600
    login_state_ttl_seconds: int = 300
    signature_client_id: str = ""
    signature_client_secret: str = field(default="", repr=False)

    @property
    def is_production(self) -> bool:
        return is_production_environment(self.env)

    @property
    def origin(self) -> str:
        parsed = urlsplit(self.public_url)
        return f"{parsed.scheme.lower()}://{parsed.netloc.lower()}"

    @property
    def cookie_path(self) -> str:
        raw_path = urlsplit(self.public_url).path or "/"
        return normalize_cookie_path(raw_path)

    @property
    def secure(self) -> bool:
        return urlsplit(self.public_url).scheme.lower() == "https"

    @property
    def callback_url(self) -> str:
        suffix = self.callback_path if self.callback_path.startswith("/") else f"/{self.callback_path}"
        return f"{self.public_url.rstrip('/')}{suffix}"

    @property
    def signature_callback_url(self) -> str:
        suffix = (
            self.signature_callback_path
            if self.signature_callback_path.startswith("/")
            else f"/{self.signature_callback_path}"
        )
        return f"{self.public_url.rstrip('/')}{suffix}"

    @classmethod
    def from_env(
        cls,
        environ: Mapping[str, str] | None = None,
        *,
        prefix: str = "CMC_OIDC_",
    ) -> CMCOIDCConfig:
        source = os.environ if environ is None else environ
        env_name = (
            source.get(f"{prefix}ENV")
            or source.get("CMC_ENV")
            or source.get("APP_ENV")
            or "production"
        )
        enabled_raw = source.get(f"{prefix}ENABLED", "true").strip().lower()
        if enabled_raw not in {"1", "true", "yes", "on"}:
            raise OIDCConfigError(f"{prefix}ENABLED must be true when initializing OIDC auth")

        scopes_raw = source.get(f"{prefix}SCOPES", "openid profile email")
        scopes = tuple(part for part in scopes_raw.split() if part)

        try:
            session_max = int(source.get(f"{prefix}SESSION_MAX_SECONDS", "3600"))
            login_ttl = int(source.get(f"{prefix}LOGIN_STATE_TTL_SECONDS", "300"))
        except ValueError as exc:
            raise OIDCConfigError("Invalid integer TTL in OIDC environment configuration") from exc

        raw_cfg = cls(
            issuer_url=source.get(f"{prefix}ISSUER_URL", ""),
            public_url=source.get(f"{prefix}PUBLIC_URL", ""),
            client_id=source.get(f"{prefix}CLIENT_ID", ""),
            client_secret=source.get(f"{prefix}CLIENT_SECRET", ""),
            session_secret=source.get(f"{prefix}SESSION_SECRET", ""),
            organization=source.get(f"{prefix}ORGANIZATION", "mabpharm"),
            env=env_name,
            internal_url=source.get(f"{prefix}INTERNAL_URL", ""),
            callback_path=source.get(f"{prefix}CALLBACK_PATH", "/api/v1/auth/oidc/callback"),
            signature_callback_path=source.get(
                f"{prefix}SIGNATURE_CALLBACK_PATH", "/signature-callback"
            ),
            default_return_to=source.get(f"{prefix}DEFAULT_RETURN_TO", "/"),
            scopes=scopes,
            session_cookie_name=source.get(f"{prefix}SESSION_COOKIE_NAME", "cmc_oidc_session"),
            login_cookie_name=source.get(f"{prefix}LOGIN_COOKIE_NAME", "cmc_oidc_login"),
            session_max_seconds=session_max,
            login_state_ttl_seconds=login_ttl,
            signature_client_id=source.get(f"{prefix}SIGNATURE_CLIENT_ID", ""),
            signature_client_secret=source.get(f"{prefix}SIGNATURE_CLIENT_SECRET", ""),
        )
        return validate_startup(raw_cfg)


def validate_startup(config: CMCOIDCConfig) -> CMCOIDCConfig:
    """Fail-closed startup validator; enforces HTTPS, strong secrets, and audience separation."""
    allow_loopback_http = not config.is_production
    issuer = checked_url(config.issuer_url, allow_http_loopback=allow_loopback_http)
    public = checked_url(config.public_url, allow_http_loopback=allow_loopback_http)

    allow_internal_http = (
        allow_loopback_http
        and urlsplit(issuer).hostname in _LOOPBACK_HOSTS
    )
    internal = checked_url(
        config.internal_url or issuer,
        allow_http_loopback=allow_loopback_http,
        allow_http_internal=allow_internal_http,
    )

    if not config.client_id or not config.client_id.strip() or len(config.client_id) > 128:
        raise OIDCConfigError("client_id must be configured")
    validate_secret_strength(config.client_secret, field_name="client_secret", min_length=16)
    validate_secret_strength(config.session_secret, field_name="session_secret", min_length=32)

    if not _ORG_PATTERN.fullmatch(config.organization or ""):
        raise OIDCConfigError("A valid fixed Casdoor organization is required")

    if "openid" not in config.scopes:
        raise OIDCConfigError("OIDC scopes must include 'openid'")

    if not 60 <= config.session_max_seconds <= 86400:
        raise OIDCConfigError("session_max_seconds must be between 60 and 86400")
    if not 30 <= config.login_state_ttl_seconds <= 900:
        raise OIDCConfigError("login_state_ttl_seconds must be between 30 and 900")

    if not config.callback_path.startswith("/") or ".." in config.callback_path:
        raise OIDCConfigError("callback_path must be an absolute relative path")

    if config.signature_client_id or config.signature_client_secret:
        if not config.signature_client_id or not config.signature_client_secret:
            raise OIDCConfigError("Both signature_client_id and signature_client_secret are required")
        validate_secret_strength(
            config.signature_client_secret,
            field_name="signature_client_secret",
            min_length=16,
        )
        if config.signature_client_id == config.client_id:
            raise OIDCConfigError("signature_client_id must be an independent OIDC audience")

    normalized = CMCOIDCConfig(
        issuer_url=issuer,
        public_url=public,
        client_id=config.client_id.strip(),
        client_secret=config.client_secret,
        session_secret=config.session_secret,
        organization=config.organization,
        env=config.env,
        internal_url=internal,
        callback_path=config.callback_path,
        signature_callback_path=config.signature_callback_path,
        default_return_to=config.default_return_to,
        scopes=tuple(config.scopes),
        session_cookie_name=config.session_cookie_name,
        login_cookie_name=config.login_cookie_name,
        session_max_seconds=config.session_max_seconds,
        login_state_ttl_seconds=config.login_state_ttl_seconds,
        signature_client_id=config.signature_client_id.strip(),
        signature_client_secret=config.signature_client_secret,
    )
    _ = normalized.cookie_path
    if normalized.is_production and not normalized.secure:
        raise OIDCConfigError("Production OIDC cookies require HTTPS Secure=True")
    return normalized
