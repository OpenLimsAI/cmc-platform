"""
文件: backend/tests/test_auth_hardening.py
用途: Wave 0 认证安全加固单元测试（不依赖外部 PostgreSQL 即可独立运行）
覆盖:
    - APP_ENV=production / CMC_ENV=production 时缺省、过短或使用开发默认 MDM_SECRET_KEY 均 fail-closed
    - FastAPI lifespan 启动与 get_current_user 验签在生产环境均强制拦截弱密钥
    - 生产环境显式配置高强度 32+ 字符密钥时正常放行
    - LABOPS_DISABLE_LEGACY_PASSWORD_PROXY=true（以及 LABOPS_SIGNATURE_MODE=oidc_fresh）时，
      /api/auth/login 与 verify_reviewer 均在发起任何外部 HTTP 请求前直接返回 403，零明文密码外发
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import HTTPException
from fastapi.testclient import TestClient
import httpx
from jose import jwt
import pytest

import auth
from database import get_db
from main import app, create_app

STRONG_PROD_KEY = "prod-hs256-signing-key-9x8c7v6b5n4m3l2k1j0h"


@pytest.mark.parametrize("env_var", ["APP_ENV", "CMC_ENV"])
@pytest.mark.parametrize(
    "bad_secret",
    [
        None,
        "",
        "short-key",
        auth.DEV_DEFAULT_MDM_SECRET_KEY,
        "please-CHANGE-ME-in-prod-0123456789abcdef",
        "__REDACTED_MDM_SECRET_KEY_VALUE_32_CHARS__",
    ],
)
def test_production_env_fails_closed_on_missing_or_weak_secret(monkeypatch, env_var, bad_secret):
    monkeypatch.delenv("APP_ENV", raising=False)
    monkeypatch.delenv("CMC_ENV", raising=False)
    monkeypatch.setenv(env_var, "production")
    if bad_secret is None:
        monkeypatch.delenv("MDM_SECRET_KEY", raising=False)
    else:
        monkeypatch.setenv("MDM_SECRET_KEY", bad_secret)

    with pytest.raises(RuntimeError, match="MDM_SECRET_KEY"):
        auth.validate_auth_startup()

    with pytest.raises(RuntimeError, match="MDM_SECRET_KEY"):
        auth.get_current_user("Bearer dummy.jwt.token")

    with pytest.raises(RuntimeError, match="MDM_SECRET_KEY"):
        with TestClient(app):
            pass


def test_disallowed_jwt_algorithm_fails_closed(monkeypatch):
    monkeypatch.setenv("MDM_JWT_ALGORITHM", "none")
    with pytest.raises(RuntimeError, match="MDM_JWT_ALGORITHM"):
        auth.resolve_mdm_signing_config()


@pytest.mark.parametrize("env_var", ["APP_ENV", "CMC_ENV"])
def test_production_env_accepts_strong_explicit_secret(monkeypatch, env_var):
    monkeypatch.delenv("APP_ENV", raising=False)
    monkeypatch.delenv("CMC_ENV", raising=False)
    monkeypatch.setenv(env_var, "production")
    monkeypatch.setenv("MDM_SECRET_KEY", STRONG_PROD_KEY)
    monkeypatch.setenv("LABOPS_CORS_ORIGINS", "https://www.openlims.ai")

    token = jwt.encode(
        {
            "sub": "7",
            "username": "lab_admin",
            "roles": ["SYS_ADMIN"],
            "department": "CMC",
            "type": "access",
            "exp": datetime.now(timezone.utc) + timedelta(minutes=15),
        },
        STRONG_PROD_KEY,
        algorithm="HS256",
    )
    with TestClient(app) as c:
        resp = c.get("/api/users/me", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200
        assert resp.json() == {"user_id": 7, "username": "lab_admin", "roles": ["SYS_ADMIN"]}


def test_non_production_default_cors_origins_are_explicit_localhost_without_wildcard(monkeypatch):
    monkeypatch.delenv("APP_ENV", raising=False)
    monkeypatch.delenv("CMC_ENV", raising=False)
    monkeypatch.delenv("LABOPS_CORS_ORIGINS", raising=False)

    expected = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:5100",
        "http://127.0.0.1:5100",
    ]
    origins = auth.resolve_cors_origins()
    assert origins == expected
    assert "*" not in origins

    monkeypatch.setenv("LABOPS_CORS_ORIGINS", "  ,  ")
    assert auth.resolve_cors_origins() == expected

    monkeypatch.delenv("LABOPS_CORS_ORIGINS", raising=False)
    with TestClient(create_app()) as c:
        ok_preflight = c.options(
            "/health",
            headers={
                "Origin": "http://localhost:5100",
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "Authorization, Content-Type",
            },
        )
        assert ok_preflight.status_code == 200
        assert ok_preflight.headers.get("access-control-allow-origin") == "http://localhost:5100"
        allowed_methods = {
            m.strip()
            for m in ok_preflight.headers.get("access-control-allow-methods", "").split(",")
            if m.strip()
        }
        assert allowed_methods == {"GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"}

        blocked_preflight = c.options(
            "/health",
            headers={
                "Origin": "https://evil.example.com",
                "Access-Control-Request-Method": "GET",
            },
        )
        assert "access-control-allow-origin" not in blocked_preflight.headers


def test_custom_labops_cors_origins_parsing(monkeypatch):
    monkeypatch.delenv("APP_ENV", raising=False)
    monkeypatch.delenv("CMC_ENV", raising=False)
    monkeypatch.setenv(
        "LABOPS_CORS_ORIGINS",
        " https://www.openlims.ai , http://localhost:1234 , , https://portal.example.org ",
    )
    assert auth.resolve_cors_origins() == [
        "https://www.openlims.ai",
        "http://localhost:1234",
        "https://portal.example.org",
    ]


@pytest.mark.parametrize("env_var", ["APP_ENV", "CMC_ENV"])
@pytest.mark.parametrize(
    "bad_cors",
    [
        None,
        "",
        "   ,   ",
        "*",
        "https://www.openlims.ai, *",
    ],
)
def test_production_env_fails_closed_on_missing_or_wildcard_cors(monkeypatch, env_var, bad_cors):
    monkeypatch.delenv("APP_ENV", raising=False)
    monkeypatch.delenv("CMC_ENV", raising=False)
    monkeypatch.setenv(env_var, "production")
    monkeypatch.setenv("MDM_SECRET_KEY", STRONG_PROD_KEY)
    if bad_cors is None:
        monkeypatch.delenv("LABOPS_CORS_ORIGINS", raising=False)
    else:
        monkeypatch.setenv("LABOPS_CORS_ORIGINS", bad_cors)

    with pytest.raises(RuntimeError, match="LABOPS_CORS_ORIGINS"):
        auth.resolve_cors_origins()

    with pytest.raises(RuntimeError, match="LABOPS_CORS_ORIGINS"):
        create_app()

    with pytest.raises(RuntimeError, match="LABOPS_CORS_ORIGINS"):
        with TestClient(app):
            pass


@pytest.mark.parametrize("env_var", ["APP_ENV", "CMC_ENV"])
def test_production_env_accepts_explicit_https_cors_origins(monkeypatch, env_var):
    monkeypatch.delenv("APP_ENV", raising=False)
    monkeypatch.delenv("CMC_ENV", raising=False)
    monkeypatch.setenv(env_var, "production")
    monkeypatch.setenv("MDM_SECRET_KEY", STRONG_PROD_KEY)
    monkeypatch.setenv("LABOPS_CORS_ORIGINS", "https://www.openlims.ai, https://cmc.openlims.ai")

    assert auth.resolve_cors_origins() == [
        "https://www.openlims.ai",
        "https://cmc.openlims.ai",
    ]
    with TestClient(create_app()) as c:
        allowed = c.get("/health", headers={"Origin": "https://www.openlims.ai"})
        assert allowed.status_code == 200
        assert allowed.headers.get("access-control-allow-origin") == "https://www.openlims.ai"

        disallowed = c.get("/health", headers={"Origin": "http://localhost:5173"})
        assert disallowed.status_code == 200
        assert "access-control-allow-origin" not in disallowed.headers


@pytest.mark.parametrize(
    "flag_env",
    [
        {"LABOPS_DISABLE_LEGACY_PASSWORD_PROXY": "true"},
        {"LABOPS_DISABLE_LEGACY_PASSWORD_PROXY": "1"},
        {"LABOPS_SIGNATURE_MODE": "oidc_fresh"},
    ],
)
def test_disable_legacy_password_proxy_blocks_login_and_verify_reviewer_without_network(
    monkeypatch, flag_env
):
    for k, v in flag_env.items():
        monkeypatch.setenv(k, v)

    http_calls: list[tuple[str, object]] = []

    class ForbiddenClient:
        def __init__(self, *args, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def post(self, url, **kwargs):
            http_calls.append((url, kwargs))
            raise AssertionError("Plaintext password proxy must never call outbound HTTP when disabled")

    monkeypatch.setattr(httpx, "Client", ForbiddenClient)

    # 1. verify_reviewer 直接抛 403 且零网络请求
    with pytest.raises(HTTPException) as exc_info:
        auth.verify_reviewer("reviewer_a", "SuperSecretPlaintext!")
    assert exc_info.value.status_code == 403
    assert "oidc_fresh" in exc_info.value.detail
    assert http_calls == []

    # 2. POST /api/auth/login 直接返回 403 且零网络请求
    class DummyDB:
        def commit(self):
            pass

        def rollback(self):
            pass

    app.dependency_overrides[get_db] = lambda: DummyDB()
    try:
        with TestClient(app) as c:
            resp = c.post(
                "/api/auth/login",
                json={"username": "operator_a", "password": "SuperSecretPlaintext!"},
            )
            assert resp.status_code == 403
            assert "OIDC" in resp.json()["detail"]
            assert http_calls == []
    finally:
        app.dependency_overrides.clear()
