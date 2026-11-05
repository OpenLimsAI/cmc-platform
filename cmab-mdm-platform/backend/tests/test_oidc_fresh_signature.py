"""Fresh authentication is distinct from a newly issued SSO token."""
import pytest
from app.domains.auth.oidc.protocol import OIDCError


def test_signature_rejects_new_token_from_an_old_authentication():
    from app.domains.auth.oidc.protocol import validate_fresh_auth

    with pytest.raises(OIDCError):
        validate_fresh_auth({"iat": 1000, "auth_time": 900}, started_at=999, now=1001)


@pytest.mark.parametrize("claims", [{}, {"auth_time":True}, {"auth_time":1000.0}, {"auth_time":"1000"}, {"auth_time":1007}])
def test_signature_rejects_missing_malformed_or_future_authentication_time(claims):
    from app.domains.auth.oidc.protocol import validate_fresh_auth
    with pytest.raises(OIDCError):
        validate_fresh_auth(claims, started_at=999, now=1001)


def test_signature_accepts_verified_fresh_authentication_at_second_precision():
    from app.domains.auth.oidc.protocol import validate_fresh_auth
    assert validate_fresh_auth({"auth_time":999}, started_at=999, now=1001) == 999


def test_signature_accepts_one_challenge_instead_of_an_mdm_password():
    from app.domains.audit.schemas import SignatureBlock
    from pydantic import ValidationError

    block = SignatureBlock(challenge_id="a" * 64, reason="本地端到端审批确认")
    assert block.password is None and block.challenge_id == "a" * 64
    with pytest.raises(ValidationError):
        SignatureBlock(password="not-used", challenge_id="a" * 64, reason="本地端到端审批确认")


async def test_signature_challenge_api_requires_an_authenticated_session(http_client):
    response = await http_client.post("/api/v1/auth/oidc/signatures", json={
        "entity_type": "project", "entity_code": "NOT-A-REAL-PROJECT", "action": "approve",
        "comment": "未登录用户不得发起", "reason": "未登录用户不得签名",
    })
    assert response.status_code == 401


async def test_fresh_signature_mode_does_not_maintain_local_signing_passwords(monkeypatch):
    from app.core.config import settings
    from app.core.exceptions import PermissionDeniedError
    from app.domains.auth.services import AuthService

    monkeypatch.setattr(settings, "MDM_SIGNATURE_MODE", "oidc_fresh")

    class NoPasswordDatabase:
        async def execute(self, *args, **kwargs):
            pytest.fail("OIDC signing mode reached local password storage")

    with pytest.raises(PermissionDeniedError):
        await AuthService(NoPasswordDatabase()).change_password(None, "unused", "unused")
