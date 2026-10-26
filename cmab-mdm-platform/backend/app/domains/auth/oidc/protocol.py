"""Small OIDC protocol primitives; no identity binding by names or roles."""
import base64
import hashlib
import re
import secrets
import time
from urllib.parse import unquote, urlsplit

from jose import JWTError, jwt


class OIDCError(Exception):
    """A deliberately credential-free protocol failure."""


def digest(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def pkce_pair() -> tuple[str, str]:
    verifier = secrets.token_urlsafe(64)
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
    return verifier, challenge


def safe_return_to(value: str | None) -> str:
    default = "/projects"
    if not value or len(value) > 2048 or any(ord(c) < 32 or ord(c) == 127 for c in value):
        return default
    if "\\" in value or unquote(value) != value:
        return default
    parsed = urlsplit(value)
    if parsed.scheme or parsed.netloc or parsed.fragment or not value.startswith("/") or value.startswith("//"):
        return default
    if any(part in {".", ".."} for part in parsed.path.split("/")):
        return default
    if parsed.path.startswith(("/login", "/auth-complete", "/api/", "/profile/password")):
        return default
    if re.search(r"(?:^|[&?])[^=&]*(?:token|secret|cookie|authorization|code|state)[^=&]*=", parsed.query, re.I):
        return default
    return value


def validate_jwt(token, key, *, issuer, audience, nonce=None, access_token=None, logout=False):
    """Verify only pinned RS256 keys/issuer/audience; ignore untrusted key URLs."""
    try:
        if not isinstance(token, str) or len(token) > 16384:
            raise OIDCError()
        header = jwt.get_unverified_header(token)
        if header.get("alg") != "RS256" or header.get("crit"):
            raise OIDCError()
        claims = jwt.decode(token, key, algorithms=["RS256"], issuer=issuer,
                            audience=audience, access_token=access_token,
                            options={"require_exp": not logout, "require_iat": True,
                                     "require_sub": not logout, "require_aud": True,
                                     "require_iss": True, "leeway": 15})
        now = int(time.time())
        if isinstance(claims["iat"], bool) or not isinstance(claims["iat"], int) or claims["iat"] > now + 15:
            raise OIDCError()
        if not logout and (not isinstance(claims.get("sub"), str) or not claims["sub"] or len(claims["sub"]) > 255):
            raise OIDCError()
        aud = claims["aud"]
        if isinstance(aud, list) and len(aud) > 1 and claims.get("azp") != audience:
            raise OIDCError()
        if claims.get("azp", audience) != audience:
            raise OIDCError()
        if nonce is not None and (not isinstance(claims.get("nonce"), str) or not secrets.compare_digest(claims["nonce"], nonce)):
            raise OIDCError()
        return claims
    except (JWTError, ValueError, TypeError, KeyError):
        raise OIDCError("OIDC token validation failed") from None


def validate_logout_jwt(token, key, *, issuer, audience):
    claims = validate_jwt(token, key, issuer=issuer, audience=audience, logout=True)
    event = "http://schemas.openid.net/event/backchannel-logout"
    if claims.get("events") != {event: {}} or "nonce" in claims:
        raise OIDCError("Invalid logout event")
    if int(time.time()) - claims["iat"] > 300:
        raise OIDCError("Stale logout notification")
    if not isinstance(claims.get("jti"), str) or not 1 <= len(claims["jti"]) <= 255:
        raise OIDCError("Invalid logout identifier")
    if not claims.get("sub") and not claims.get("sid"):
        raise OIDCError("Logout subject or session missing")
    for name in ("sub", "sid"):
        if claims.get(name) is not None and (not isinstance(claims[name], str) or not 1 <= len(claims[name]) <= 255):
            raise OIDCError("Invalid logout target")
    return claims
