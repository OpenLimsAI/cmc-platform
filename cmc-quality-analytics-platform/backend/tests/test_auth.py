"""用本机合成签名验证身份边界；不连接 MDM 或任何数据库。"""
from __future__ import annotations

from dataclasses import fields
from time import time

import jwt
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.api.v1.auth import router
from app.core.auth import CurrentUser, require_import_preview, require_read
from app.core.config import Settings, get_auth_settings
from app.core.envelope import envelope, register_exception_handlers
from app.core.security import validate_auth_configuration


_TEST_KEY = "synthetic-only-qap-auth-test-signing-material-with-sufficient-length"
_VIEW_ROLE = "TEST_VIEW"
_PREVIEW_ROLE = "TEST_PREVIEW"


def config(**overrides) -> Settings:
    values = {
        "environment": "development", "auth_required": True,
        "jwt_algorithm": "HS256", "jwt_secret_key": _TEST_KEY,
        "jwt_public_key_path": None,
        "read_roles": [_VIEW_ROLE], "import_preview_roles": [_PREVIEW_ROLE],
    }
    values.update(overrides)
    return Settings(_env_file=None, **values)


def claims(**overrides) -> dict:
    values = {
        "sub": "42", "username": "TEST-0042", "full_name": "合成员工",
        "exp": int(time()) + 300, "type": "access",
        "roles": [_VIEW_ROLE, _PREVIEW_ROLE], "must_change_password": False,
    }
    values.update(overrides)
    return values


def headers(payload: dict | None = None, *, key=_TEST_KEY, algorithm="HS256") -> dict:
    return {"Authorization": "Bearer " + jwt.encode(payload or claims(), key, algorithm=algorithm)}


def client_for(auth_settings: Settings) -> TestClient:
    app = FastAPI()
    register_exception_handlers(app)
    app.dependency_overrides[get_auth_settings] = lambda: auth_settings
    app.include_router(router, prefix="/api/v1")

    @app.get("/read")
    def read(user: CurrentUser | None = Depends(require_read)):
        return envelope(data={"username": user.username if user else None})

    @app.post("/preview")
    def preview(user: CurrentUser = Depends(require_import_preview)):
        return envelope(data={"username": user.username, "can_commit": False})

    return TestClient(app)


def test_identity_and_capabilities_only_come_from_verified_claims():
    request_headers = headers()
    with client_for(config()) as client:
        response = client.get("/api/v1/auth/me", headers=request_headers)
        assert response.status_code == 200
        assert response.headers["cache-control"] == "no-store"
        assert response.json() == envelope(data={
            "username": "TEST-0042", "full_name": "合成员工", "subject": "42",
            "roles": [_VIEW_ROLE, _PREVIEW_ROLE],
            "can_read": True, "can_preview": True, "can_commit": False,
        })
        assert request_headers["Authorization"] not in response.text
        assert client.post("/preview", headers=request_headers).status_code == 200
    assert {f.name for f in fields(CurrentUser)} == {"username", "full_name", "subject", "roles"}


def test_status_is_public_and_does_not_disclose_roles_or_configuration():
    with client_for(config()) as client:
        response = client.get("/api/v1/auth/status")
    assert response.status_code == 200
    assert response.json() == envelope(data={"auth_required": True, "configured": True})
    assert _TEST_KEY not in response.text
    assert _VIEW_ROLE not in response.text


@pytest.mark.parametrize("field_name", ["exp", "sub", "username", "type", "roles"])
def test_required_claim_cannot_be_omitted(field_name):
    payload = claims()
    del payload[field_name]
    with client_for(config()) as client:
        response = client.get("/api/v1/auth/me", headers=headers(payload))
    assert response.status_code == 401
    assert response.json()["errors"][0]["code"] == "invalid_token"


@pytest.mark.parametrize("override", [
    {"exp": int(time()) - 30}, {"exp": "9999999999"}, {"exp": True},
    {"exp": float("inf")}, {"exp": float("nan")},
    {"sub": 42}, {"sub": ""}, {"username": " "}, {"username": 42},
    {"type": "refresh"}, {"roles": _VIEW_ROLE}, {"roles": [1]},
    {"roles": [""]}, {"roles": {"SYS_ADMIN": True}},
    {"full_name": {"name": "untrusted"}}, {"must_change_password": "false"},
    {"nbf": int(time()) + 3600},
])
def test_malformed_or_inactive_claims_are_rejected(override):
    with client_for(config()) as client:
        response = client.get("/api/v1/auth/me", headers=headers(claims(**override)))
    assert response.status_code == 401


@pytest.mark.parametrize("request_headers", [
    {}, {"Authorization": "Basic synthetic"}, {"Authorization": "Bearer"},
    {"Authorization": "Bearer malformed extra"}, {"Authorization": "Bearer not-a-jwt"},
    {"Authorization": "Bearer " + "x" * 16_385},
])
def test_missing_or_malformed_bearer_is_not_an_identity(request_headers):
    with client_for(config()) as client:
        assert client.get("/api/v1/auth/me", headers=request_headers).status_code == 401
        assert client.post("/preview", headers=request_headers).status_code == 401


@pytest.mark.parametrize("request_headers", [
    headers(key="different-synthetic-signing-material-for-test"),
    headers(algorithm="HS384"), headers(key="", algorithm="none"),
])
def test_bad_signature_or_unapproved_algorithm_is_rejected(request_headers):
    with client_for(config()) as client:
        assert client.get("/api/v1/auth/me", headers=request_headers).status_code == 401


def test_temporary_password_returns_403_without_refresh_loop():
    with client_for(config()) as client:
        response = client.post("/preview", headers=headers(claims(must_change_password=True)))
    assert response.status_code == 403
    assert response.json()["errors"][0]["code"] == "password_change_required"


def test_sys_admin_has_all_implemented_capabilities_even_with_empty_role_lists():
    with client_for(config(read_roles=[], import_preview_roles=[])) as client:
        auth = headers(claims(roles=["SYS_ADMIN"]))
        me = client.get("/api/v1/auth/me", headers=auth)
        assert me.status_code == 200
        assert me.json()["data"]["can_read"] is True
        assert me.json()["data"]["can_preview"] is True
        assert me.json()["data"]["can_commit"] is False
        assert client.get("/read", headers=auth).status_code == 200
        assert client.post("/preview", headers=auth).status_code == 200


def test_read_and_preview_are_separate_permissions():
    with client_for(config()) as client:
        view_only = headers(claims(roles=[_VIEW_ROLE]))
        assert client.get("/read", headers=view_only).status_code == 200
        assert client.post("/preview", headers=view_only).status_code == 403
        preview_only = headers(claims(roles=[_PREVIEW_ROLE]))
        assert client.get("/read", headers=preview_only).status_code == 403
        assert client.post("/preview", headers=preview_only).status_code == 200


def test_unconfigured_development_only_allows_old_anonymous_read():
    cfg = config(auth_required=False, jwt_secret_key=None)
    validate_auth_configuration(cfg)
    with client_for(cfg) as client:
        assert client.get("/api/v1/auth/status").json()["data"] == {"auth_required": False, "configured": False}
        assert client.get("/read").json()["data"]["username"] is None
        assert client.get("/read", headers=headers()).json()["data"]["username"] is None
        assert client.get("/api/v1/auth/me").status_code == 503
        assert client.post("/preview").status_code == 503
        assert client.post("/preview", headers=headers()).status_code == 503


def test_configured_development_does_not_bypass_roles_when_required_flag_is_false():
    with client_for(config(auth_required=False)) as client:
        assert client.get("/read").status_code == 401
        assert client.get("/read", headers=headers(claims(roles=[]))).status_code == 403
        assert client.get("/api/v1/auth/status").json()["data"]["auth_required"] is True


@pytest.mark.parametrize("overrides", [
    {"auth_required": True, "jwt_secret_key": None},
    {"environment": "production", "auth_required": False, "jwt_secret_key": None},
    {"environment": "test", "auth_required": False, "jwt_secret_key": None},
    {"auth_required": False, "jwt_secret_key": ""},
    {"jwt_algorithm": "RS256", "jwt_public_key_path": "/missing/synthetic/public.pem"},
])
def test_required_or_invalid_configuration_fails_startup(overrides):
    with pytest.raises(RuntimeError):
        validate_auth_configuration(config(**overrides))


def test_rs256_uses_public_key_and_rejects_shared_secret_token(tmp_path):
    private = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    public_path = tmp_path / "synthetic-public.pem"
    public_path.write_bytes(private.public_key().public_bytes(
        serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo,
    ))
    cfg = config(jwt_algorithm="RS256", jwt_secret_key=None, jwt_public_key_path=str(public_path))
    validate_auth_configuration(cfg)
    with client_for(cfg) as client:
        assert client.get("/api/v1/auth/me", headers=headers(key=private, algorithm="RS256")).status_code == 200
        assert client.get("/api/v1/auth/me", headers=headers()).status_code == 401


@pytest.mark.parametrize("roles", [[1], [""], [" TEST_VIEW"], "TEST_VIEW"])
def test_role_configuration_is_explicit_string_list(roles):
    with pytest.raises(ValidationError):
        config(read_roles=roles)


@pytest.mark.parametrize("override,expected", [
    ({"must_change_password": True}, 403),
    ({"exp": int(time()) - 30}, 401),
])
def test_sys_admin_still_requires_valid_access_and_password_change(override, expected):
    with client_for(config()) as client:
        auth = headers(claims(roles=["SYS_ADMIN"], **override))
        assert client.get("/api/v1/auth/me", headers=auth).status_code == expected
        assert client.get("/read", headers=auth).status_code == expected
        assert client.post("/preview", headers=auth).status_code == expected


def test_admin_username_without_sys_admin_role_has_no_special_access():
    with client_for(config()) as client:
        auth = headers(claims(username="admin", roles=[]))
        assert client.get("/read", headers=auth).status_code == 403
        assert client.post("/preview", headers=auth).status_code == 403
