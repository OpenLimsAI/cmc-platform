# JWT 验签：与 MDM 契约对齐（HS256 共享密钥、type=access、exp）
import time

import pytest
from fastapi import HTTPException
from jose import jwt

from app.core import security
from app.core.config import settings

SECRET = "unit-test-secret"


@pytest.fixture()
def hs256(monkeypatch):
    monkeypatch.setattr(settings, "jwt_algorithm", "HS256")
    monkeypatch.setattr(settings, "jwt_secret_key", SECRET)
    security._verifying_key.cache_clear()
    yield
    security._verifying_key.cache_clear()


def _token(secret: str = SECRET, **overrides) -> str:
    claims = {
        "sub": "1",
        "username": "090501",
        "full_name": "张三",
        "roles": ["CMC_LIMS_ANALYST"],
        "type": "access",
        "exp": int(time.time()) + 600,
    }
    claims.update(overrides)
    return jwt.encode(claims, secret, algorithm="HS256")


def test_valid_token_returns_claims(hs256):
    claims = security.verify_access_token(_token())
    assert claims["username"] == "090501"
    assert claims["roles"] == ["CMC_LIMS_ANALYST"]


def test_expired_token_rejected(hs256):
    with pytest.raises(HTTPException) as e:
        security.verify_access_token(_token(exp=int(time.time()) - 10))
    assert e.value.status_code == 401
    assert "过期" in e.value.detail


def test_refresh_token_rejected(hs256):
    # refresh token 验签能过，但 type 不是 access，必须拒绝
    with pytest.raises(HTTPException) as e:
        security.verify_access_token(_token(type="refresh"))
    assert e.value.status_code == 401


def test_bad_signature_rejected(hs256):
    with pytest.raises(HTTPException) as e:
        security.verify_access_token(_token(secret="attacker-key"))
    assert e.value.status_code == 401


def test_unconfigured_key_means_open_mode(monkeypatch):
    monkeypatch.setattr(settings, "jwt_algorithm", "HS256")
    monkeypatch.setattr(settings, "jwt_secret_key", None)
    security._verifying_key.cache_clear()
    try:
        assert security.auth_configured() is False
        # 开放模式下不能"信任"任何令牌
        with pytest.raises(HTTPException):
            security.verify_access_token(_token())
    finally:
        security._verifying_key.cache_clear()
