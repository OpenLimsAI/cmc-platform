"""OIDC protocol unit tests; synthetic JWTs are not real browser acceptance."""
import base64
import hashlib
import time

import pytest
from app.domains.auth.oidc.protocol import (
    OIDCError,
    digest,
    pkce_pair,
    safe_return_to,
    validate_jwt,
)
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from jose import jwt


@pytest.fixture
def signed():
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    private = key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption())
    public = key.public_key().public_bytes(serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo)
    def issue(**changes):
        claims = {"iss": "http://127.0.0.1:8018", "aud": "mdm-test", "sub": "unchanged-subject", "iat": int(time.time()), "exp": int(time.time()) + 300, "nonce": "expected"}
        claims.update(changes)
        return jwt.encode(claims, private, algorithm="RS256", headers={"kid": "synthetic"})
    return issue, public


def test_pkce_and_state_are_unpredictable():
    verifier, challenge = pkce_pair()
    assert 43 <= len(verifier) <= 128
    assert challenge == base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
    assert pkce_pair()[0] != verifier
    assert digest("opaque") == hashlib.sha256(b"opaque").hexdigest()


@pytest.mark.parametrize("value", ["https://evil.test", "//evil.test", "/\\evil.test", "/%2f%2fevil.test", "/projects\nfoo", "/login", "/auth-complete", "/projects?token=private", "/projects#access_token=private"])
def test_return_target_rejects_open_redirect_and_secret_query(value):
    assert safe_return_to(value) == "/projects"


def test_return_target_keeps_only_bounded_local_route():
    assert safe_return_to("/projects/CMAB-PRJ-2026-0001?tab=pm") == "/projects/CMAB-PRJ-2026-0001?tab=pm"


def test_verified_subject_is_not_username_or_role(signed):
    issue, public = signed
    claims = validate_jwt(issue(name="admin", roles=["SYS_ADMIN"]), public, issuer="http://127.0.0.1:8018", audience="mdm-test", nonce="expected")
    assert claims["sub"] == "unchanged-subject"


@pytest.mark.parametrize("changes", [{"iss": "https://evil.test"}, {"aud": "pm-test"}, {"exp": 1}, {"nonce": "wrong"}, {"iat": int(time.time()) + 600}, {"sub": ""}])
def test_rejects_wrong_identity_context(signed, changes):
    issue, public = signed
    with pytest.raises(OIDCError):
        validate_jwt(issue(**changes), public, issuer="http://127.0.0.1:8018", audience="mdm-test", nonce="expected")


def test_rejects_wrong_signature_and_algorithm(signed):
    issue, _ = signed
    other = rsa.generate_private_key(public_exponent=65537, key_size=2048).public_key().public_bytes(serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo)
    with pytest.raises(OIDCError):
        validate_jwt(issue(), other, issuer="http://127.0.0.1:8018", audience="mdm-test", nonce="expected")
    with pytest.raises(OIDCError):
        validate_jwt(jwt.encode({"sub": "bad"}, "synthetic-only", algorithm="HS256"), other, issuer="http://127.0.0.1:8018", audience="mdm-test", nonce="expected")
