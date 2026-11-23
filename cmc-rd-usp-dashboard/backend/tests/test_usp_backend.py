"""CMC R&D USP Dashboard 后端单元测试（鉴权、启动防裸奔护栏、通道字典降级与批号解析）。"""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone
import time

from fastapi import HTTPException
from fastapi.testclient import TestClient
from jose import jwt
import pytest

from app import auth as auth_mod
from app import channel_dict, db
from app.config import settings
from app.main import app
from app.routers.signals import parse_batch_name

TEST_SECRET = "usp-unit-test-hs256-secret-key-at-least-32-chars"


def _mint_token(secret: str = TEST_SECRET, **overrides) -> str:
    claims = {
        "sub": "101",
        "username": "090501",
        "full_name": "测试研究员",
        "roles": ["CMC_USP_RESEARCHER"],
        "type": "access",
        "exp": int(time.time()) + 600,
    }
    claims.update(overrides)
    return jwt.encode(claims, secret, algorithm="HS256")


@pytest.fixture
def configured_hs256(monkeypatch):
    monkeypatch.setattr(settings, "jwt_algorithm", "HS256")
    monkeypatch.setattr(settings, "jwt_secret_key", TEST_SECRET)
    monkeypatch.setattr(settings, "auth_required", True)
    monkeypatch.setattr(
        settings,
        "raw_database_url",
        "postgresql+asyncpg://test:test@127.0.0.1:1/isolated",
    )
    monkeypatch.setattr(settings, "analytics_database_url", "")
    monkeypatch.setattr(settings, "manual_write_database_url", "")
    auth_mod._verifying_key.cache_clear()
    yield
    auth_mod._verifying_key.cache_clear()


def test_verify_access_token_accepts_valid_hs256_token(configured_hs256):
    claims = auth_mod.verify_access_token(_mint_token())
    assert claims["username"] == "090501"
    assert claims["roles"] == ["CMC_USP_RESEARCHER"]


def test_verify_access_token_rejects_expired_refresh_forged_and_temp_password(configured_hs256):
    with pytest.raises(HTTPException) as exp_err:
        auth_mod.verify_access_token(_mint_token(exp=int(time.time()) - 15))
    assert exp_err.value.status_code == 401

    with pytest.raises(HTTPException) as refresh_err:
        auth_mod.verify_access_token(_mint_token(type="refresh"))
    assert refresh_err.value.status_code == 401

    with pytest.raises(HTTPException) as sig_err:
        auth_mod.verify_access_token(_mint_token(secret="wrong-secret-key-0000000000000000"))
    assert sig_err.value.status_code == 401

    with pytest.raises(HTTPException) as pwd_err:
        auth_mod.verify_access_token(_mint_token(must_change_password=True))
    assert pwd_err.value.status_code == 403


@pytest.mark.parametrize(
    ("roles", "allowed"),
    [
        ([], False),
        (["READ_ONLY_USER"], False),
        (["CMC_LIMS_ANALYST"], False),
        (["SYS_ADMIN"], True),
        (["CMC_USP_RESEARCHER"], True),
        (["CMC_USP_MANAGER"], True),
        (["CMC_USP_OPERATOR"], True),
    ],
)
def test_viewer_role_matrix(roles, allowed):
    user = auth_mod.CurrentUser.from_claims({"sub": "1", "username": "u1", "roles": roles})
    assert user.can_view is allowed


def test_open_mode_vs_auth_required_without_key(monkeypatch):
    monkeypatch.setattr(settings, "jwt_algorithm", "HS256")
    monkeypatch.setattr(settings, "jwt_secret_key", "")
    auth_mod._verifying_key.cache_clear()
    try:
        monkeypatch.setattr(settings, "auth_required", False)
        open_user = asyncio.run(auth_mod.require_viewer(None))
        assert open_user.is_system is True
        assert open_user.can_view is True

        monkeypatch.setattr(settings, "auth_required", True)
        with pytest.raises(HTTPException) as err:
            asyncio.run(auth_mod.require_viewer(None))
        assert err.value.status_code == 401

        with pytest.raises(RuntimeError, match="AUTH_REQUIRED=true"):
            with TestClient(app):
                pass
    finally:
        auth_mod._verifying_key.cache_clear()


def test_http_health_and_auth_me_guards(configured_hs256):
    with TestClient(app) as client:
        health = client.get("/health")
        assert health.status_code == 200
        assert health.json()["status"] == "ok"

        no_token = client.get("/api/auth/me")
        assert no_token.status_code == 401

        forbidden_token = _mint_token(roles=["CMC_LIMS_ANALYST"])
        forbidden = client.get(
            "/api/auth/me",
            headers={"Authorization": f"Bearer {forbidden_token}"},
        )
        assert forbidden.status_code == 403

        ok_token = _mint_token(roles=["CMC_USP_MANAGER"])
        ok_resp = client.get(
            "/api/auth/me",
            headers={"Authorization": f"Bearer {ok_token}"},
        )
        assert ok_resp.status_code == 200
        assert ok_resp.json() == {
            "username": "090501",
            "full_name": "测试研究员",
            "roles": ["CMC_USP_MANAGER"],
            "is_system": False,
        }


def test_channel_dict_graceful_fallback_without_analytics_engine(monkeypatch):
    monkeypatch.setattr(db, "_analytics_engine", None)
    monkeypatch.setattr(channel_dict, "_cache", {})
    monkeypatch.setattr(channel_dict, "_cache_at", 0.0)
    assert asyncio.run(channel_dict.get_channel_dict(force=True)) == {}


@pytest.mark.parametrize(
    ("procname", "starttime", "expected"),
    [
        ("016_R2605_A2", None, ("016", 2026, "R2605")),
        ("007-26003-B1", None, ("007", 2026, "26003")),
        (
            "test610",
            datetime(2025, 6, 10, tzinfo=timezone.utc),
            (None, 2025, None),
        ),
    ],
)
def test_parse_batch_name(procname, starttime, expected):
    assert parse_batch_name(procname, starttime) == expected
