"""Explicit URLs and separate OIDC client audiences; disabled by default."""
import re
from dataclasses import dataclass, field
from urllib.parse import urlsplit

from app.core.config import settings
from app.domains.auth.oidc.protocol import OIDCError


def checked_url(value: str, *, internal=False) -> str:
    if not value or len(value) > 2048 or not value.isascii() or any(ord(c) <= 32 or ord(c) == 127 for c in value):
        raise OIDCError("OIDC URL is not configured")
    try:
        parsed = urlsplit(value)
        if parsed.port is not None and parsed.port < 1:
            raise ValueError
    except ValueError:
        raise OIDCError("Invalid configured URL") from None
    if not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment or "\\" in value or "%" in value:
        raise OIDCError("Invalid configured URL")
    if any(part in {".", ".."} for part in parsed.path.split("/")):
        raise OIDCError("Invalid configured URL")
    loopback = parsed.hostname in {"127.0.0.1", "localhost", "::1"}
    if parsed.scheme != "https" and not (parsed.scheme == "http" and (loopback or internal)):
        raise OIDCError("OIDC requires HTTPS outside isolated loopback development")
    return value.rstrip("/")


@dataclass(frozen=True)
class OIDCConfig:
    issuer: str
    public_url: str
    client_id: str
    client_secret: str = field(repr=False)
    organization: str = ""
    account_status_visible: bool = False
    internal_url: str = ""
    pm_client_id: str = ""
    pm_client_secret: str = field(default="", repr=False)
    session_max_seconds: int = 3600

    @property
    def origin(self):
        parsed = urlsplit(self.public_url)
        return f"{parsed.scheme}://{parsed.netloc}"

    @property
    def cookie_path(self):
        return (urlsplit(self.public_url).path.rstrip("/") + "/") or "/"

    @property
    def secure(self):
        return urlsplit(self.public_url).scheme == "https"

    def callback(self, delegation=False):
        return self.public_url + "/api/v1/auth/oidc/" + ("pm-callback" if delegation else "callback")


def configured() -> OIDCConfig:
    if not settings.MDM_OIDC_ENABLED:
        raise OIDCError("OIDC disabled")
    issuer = checked_url(settings.MDM_OIDC_ISSUER_URL)
    public = checked_url(settings.MDM_PUBLIC_URL)
    # Non-TLS Docker DNS is allowed only behind the explicitly loopback test issuer.
    allow_internal = urlsplit(issuer).hostname in {"127.0.0.1", "localhost", "::1"} and settings.is_development
    internal = checked_url(settings.MDM_OIDC_INTERNAL_URL or issuer, internal=allow_internal)
    if not settings.MDM_OIDC_CLIENT_ID or not settings.MDM_OIDC_CLIENT_SECRET:
        raise OIDCError("OIDC client is not configured")
    if not re.fullmatch(r"[A-Za-z0-9_.-]{1,100}", settings.MDM_OIDC_ORGANIZATION):
        raise OIDCError("A fixed identity organization is required")
    if settings.MDM_OIDC_ACCOUNT_STATUS_VISIBLE is not True:
        # Casdoor can mask Admin-only status fields as false for a self read.
        # This is an explicit deployment precondition, not runtime proof of it.
        raise OIDCError("Self-visible identity account status must be confirmed")
    return OIDCConfig(issuer=issuer, public_url=public, internal_url=internal,
                      client_id=settings.MDM_OIDC_CLIENT_ID,
                      client_secret=settings.MDM_OIDC_CLIENT_SECRET.get_secret_value(),
                      organization=settings.MDM_OIDC_ORGANIZATION,
                      account_status_visible=settings.MDM_OIDC_ACCOUNT_STATUS_VISIBLE,
                      pm_client_id=settings.MDM_OIDC_PM_CLIENT_ID,
                      pm_client_secret=settings.MDM_OIDC_PM_CLIENT_SECRET.get_secret_value() if settings.MDM_OIDC_PM_CLIENT_SECRET else "",
                      session_max_seconds=settings.MDM_OIDC_SESSION_MAX_SECONDS)
