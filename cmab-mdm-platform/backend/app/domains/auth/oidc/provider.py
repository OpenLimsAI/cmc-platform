"""Bounded OIDC HTTP and pinned provider keys; no external URLs from tokens."""
import asyncio
import base64
import json
import time
from typing import Any
from urllib.parse import urlencode, urlsplit

import httpx
from jose import JWTError, jwt

from app.domains.auth.oidc.config import OIDCConfig, checked_url
from app.domains.auth.oidc.protocol import OIDCError, validate_jwt

_CACHE: dict[tuple[str, str, str], tuple[float, Any]] = {}


class OIDCProvider:
    def __init__(self, config: OIDCConfig):
        self.config = config

    def internal(self, public):
        issuer = urlsplit(self.config.issuer)
        target = urlsplit(public)
        if (target.scheme, target.netloc) != (issuer.scheme, issuer.netloc) or target.fragment or target.query or target.username:
            raise OIDCError("Untrusted provider endpoint")
        prefix = self.config.internal_url or self.config.issuer
        return prefix + target.path

    async def request(self, method, url, *, denied_statuses=(), **kwargs):
        try:
            async with (
                asyncio.timeout(10),
                httpx.AsyncClient(trust_env=False, follow_redirects=False, timeout=5) as client,
                client.stream(method, self.internal(url), **kwargs) as response,
            ):
                if response.status_code in denied_statuses:
                    return None
                response.raise_for_status()
                data = bytearray()
                async for chunk in response.aiter_bytes():
                    data.extend(chunk)
                    if len(data) > 65536:
                        raise OIDCError("Provider response exceeds limit")
                return json.loads(data)
        except (httpx.HTTPError, TimeoutError, ValueError, TypeError):
            raise OIDCError("Identity provider unavailable") from None

    async def discovery(self):
        key = (self.config.issuer, self.config.internal_url, "discovery")
        cached = _CACHE.get(key)
        if cached and cached[0] > time.monotonic():
            return cached[1]
        body = await self.request("GET", self.config.issuer + "/.well-known/openid-configuration")
        if not isinstance(body, dict) or body.get("issuer") != self.config.issuer:
            raise OIDCError("Provider issuer mismatch")
        for name in ("authorization_endpoint", "token_endpoint", "jwks_uri"):
            checked_url(body.get(name, ""))
            self.internal(body[name])
        _CACHE[key] = (time.monotonic() + 300, body)
        return body

    async def signing_key(self, token, *, fresh=False):
        try:
            header = jwt.get_unverified_header(token)
            if header.get("alg") != "RS256" or not isinstance(header.get("kid"), str) or len(header["kid"]) > 255:
                raise OIDCError("Invalid signing key reference")
        except (JWTError, ValueError, TypeError):
            raise OIDCError("Invalid signing key reference") from None
        discovery = await self.discovery()
        key = (self.config.issuer, self.config.internal_url, "jwks")
        cached = _CACHE.get(key)
        if fresh or not cached or cached[0] <= time.monotonic():
            body = await self.request("GET", discovery["jwks_uri"])
            keys = body.get("keys") if isinstance(body, dict) else None
            if not isinstance(keys, list) or not 1 <= len(keys) <= 20:
                raise OIDCError("Invalid provider keys")
            _CACHE[key] = (time.monotonic() + 300, keys)
        for item in _CACHE[key][1]:
            if item.get("kid") == header["kid"] and item.get("kty") == "RSA" and item.get("use", "sig") == "sig" and item.get("alg", "RS256") == "RS256":
                modulus = item.get("n", "")
                try:
                    bits = int.from_bytes(base64.urlsafe_b64decode(modulus + "=" * (-len(modulus) % 4)), "big").bit_length()
                except (ValueError, TypeError):
                    raise OIDCError("Invalid provider key") from None
                if "d" in item or bits < 2048:
                    raise OIDCError("Invalid public key")
                return item
        if not fresh:
            return await self.signing_key(token, fresh=True)
        raise OIDCError("Unknown signing key")

    async def authorization_url(self, params):
        discovery = await self.discovery()
        return discovery["authorization_endpoint"] + "?" + urlencode(params)

    async def exchange(self, code, verifier, nonce, *, delegation=False):
        if not code or len(code) > 4096:
            raise OIDCError("Invalid authorization code")
        client = self.config.pm_client_id if delegation else self.config.client_id
        secret = self.config.pm_client_secret if delegation else self.config.client_secret
        discovery = await self.discovery()
        body = await self.request("POST", discovery["token_endpoint"], data={"grant_type": "authorization_code",
            "client_id": client, "client_secret": secret, "redirect_uri": self.config.callback(delegation),
            "code": code, "code_verifier": verifier})
        try:
            access = body["access_token"]
            identity = body["id_token"]
            access_claims = validate_jwt(access, await self.signing_key(access), issuer=self.config.issuer, audience=client)
            identity_claims = validate_jwt(identity, await self.signing_key(identity), issuer=self.config.issuer,
                                           audience=client, nonce=nonce, access_token=access)
            if identity_claims["sub"] != access_claims["sub"]:
                raise OIDCError("OIDC subjects differ")
            if access_claims.get("isForbidden") or access_claims.get("isDeleted"):
                raise OIDCError("Identity disabled")
            expiry = min(access_claims["exp"], identity_claims["exp"])
            identity_claims["exp"] = expiry
            return identity_claims, {"access_token": access, "expires_at": expiry}
        except (KeyError, TypeError, ValueError):
            raise OIDCError("Incomplete token response") from None

    async def verify_logout(self, token):
        from app.domains.auth.oidc.protocol import validate_logout_jwt
        key = await self.signing_key(token)
        for audience in (self.config.client_id, self.config.pm_client_id):
            if audience:
                try:
                    return validate_logout_jwt(token, key, issuer=self.config.issuer, audience=audience)
                except OIDCError:
                    pass
        raise OIDCError("Invalid logout notification")

    async def global_logout(self, access):
        discovery = await self.discovery()
        endpoint = discovery.get("introspection_endpoint", self.config.issuer + "/api/login/oauth/introspect")
        self.internal(endpoint)
        arguments = {"auth": httpx.BasicAuth(self.config.client_id, self.config.client_secret),
                     "data": {"token": access, "token_type_hint": "access_token"}}
        before = await self.request("POST", endpoint, **arguments)
        if not (isinstance(before, dict) and before.get("active") is True
                and before.get("client_id") == self.config.client_id and isinstance(before.get("sub"), str) and before["sub"]):
            raise OIDCError("Current identity cannot confirm global logout")
        body = await self.request("POST", self.config.issuer + "/api/sso-logout", params={"logoutAll": "true"},
                                  headers={"Authorization": "Bearer " + access})
        if not isinstance(body, dict) or body.get("status") != "ok":
            raise OIDCError("Global logout not confirmed")
        after = await self.request("POST", endpoint, **arguments)
        if not isinstance(after, dict) or after.get("active") is not False:
            # Casdoor 3.152/PostgreSQL can return ok while expiring zero rows.
            # Do not turn a transport success into a false global-success claim.
            raise OIDCError("Identity provider did not confirm token revocation")

    async def is_active(self, access, *, subject):
        # Back-channel delivery is best effort. A missed notification must not
        # leave a locally valid cookie usable after provider revocation.
        if not self.config.organization or self.config.account_status_visible is not True:
            raise OIDCError("Self-visible identity account status is not configured")
        discovery = await self.discovery()
        endpoint = discovery.get("introspection_endpoint", self.config.issuer + "/api/login/oauth/introspect")
        self.internal(endpoint)
        body = await self.request("POST", endpoint,
            auth=httpx.BasicAuth(self.config.client_id, self.config.client_secret),
            data={"token": access, "token_type_hint": "access_token"})
        if not (isinstance(body, dict) and body.get("active") is True
                and body.get("client_id") == self.config.client_id and body.get("sub") == subject):
            return False
        # Introspection in Casdoor 3.152.0 does not reflect a later account
        # disable/delete. Read only the verified subject with its own app token;
        # never use get-account (which can mint a token) or an admin credential.
        account = await self.request("GET", self.config.issuer + "/api/get-user",
            params={"owner": self.config.organization, "userId": subject},
            headers={"Authorization": "Bearer " + access}, denied_statuses=(401, 403, 404))
        user = account.get("data") if isinstance(account, dict) and account.get("status") == "ok" else None
        return (isinstance(user, dict) and user.get("id") == subject
                and user.get("owner") == self.config.organization
                and user.get("isForbidden") is False and user.get("isDeleted") is False)
