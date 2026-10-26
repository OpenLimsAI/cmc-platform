"""Signed back-channel tests: fixed Casdoor v3.152 has sub even with a mismatched sid."""
import time
from uuid import uuid4

import pytest
from app.domains.auth.oidc.protocol import OIDCError, validate_logout_jwt
from cryptography.hazmat.primitives.asymmetric import rsa
from jose import jwt


def keys():
    from cryptography.hazmat.primitives import serialization
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    return (key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()),
            key.public_key().public_bytes(serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo))


def test_signed_logout_has_no_exp_and_keeps_subject_for_subject_wide_policy():
    private, public = keys()
    payload = {"iss": "http://127.0.0.1:8018", "aud": ["mdm-test"], "sub": "unchanged-sub",
               "iat": int(time.time()), "jti": str(uuid4()), "sid": "not-the-app-sid",
               "events": {"http://schemas.openid.net/event/backchannel-logout": {}}}
    token = jwt.encode(payload, private, algorithm="RS256")
    claims = validate_logout_jwt(token, public, issuer=payload["iss"], audience="mdm-test")
    assert claims["sub"] == "unchanged-sub" and "exp" not in claims


@pytest.mark.parametrize("change", [{"events": {}}, {"nonce": "not-allowed"}, {"iat": 1}, {"jti": ""},
                                      {"sub": None, "sid": None}, {"aud": "pm-client"},
                                      {"iss": "https://untrusted.test"}, {"iat": int(time.time()) + 600}])
def test_reject_untrusted_or_replay_unbounded_logout(change):
    private, public = keys()
    payload = {"iss": "http://127.0.0.1:8018", "aud": "mdm-test", "sub": "unchanged-sub",
               "iat": int(time.time()), "jti": str(uuid4()),
               "events": {"http://schemas.openid.net/event/backchannel-logout": {}}}
    payload.update(change)
    token = jwt.encode(payload, private, algorithm="RS256")
    with pytest.raises(OIDCError):
        validate_logout_jwt(token, public, issuer="http://127.0.0.1:8018", audience="mdm-test")
