"""Real HTTP/DB regression for disabling previously issued local credentials.

No provider is substituted. The second server has intentionally unavailable
OIDC configuration to verify fail-closed behavior; this is not positive SSO E2E.
"""
import asyncio
import os
import subprocess
import sys
from urllib.parse import urlsplit

import httpx
import pytest
from app.scripts.seed_data import USERS


@pytest.fixture
async def oidc_only_http():
    assert os.environ.get("TEST_DB") == "cmab_test"
    assert urlsplit(os.environ["TEST_BASE_URL"]).hostname in {"localhost", "127.0.0.1"}
    env = dict(os.environ, MDM_NATIVE_LOGIN_ENABLED="false", MDM_OIDC_ENABLED="false")
    process = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "8002"],
        env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    try:
        async with httpx.AsyncClient(base_url="http://127.0.0.1:8002", timeout=5, trust_env=False) as client:
            for _ in range(150):
                if process.poll() is not None:
                    pytest.fail("Dedicated OIDC-only HTTP server exited before readiness")
                try:
                    if (await client.get("/api/v1/health")).status_code == 200:
                        break
                except httpx.HTTPError:
                    pass
                await asyncio.sleep(0.2)
            else:
                pytest.fail("Dedicated OIDC-only HTTP server did not become ready")
            yield client
    finally:
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)


async def test_previously_issued_native_credentials_are_rejected_over_real_http(http_client, oidc_only_http):
    account = next(user for user in USERS if user["username"] == "admin")
    credentials = {"username": account["username"], "password": account["password"]}
    issued = await http_client.post("/api/v1/auth/login", json=credentials)
    assert issued.status_code == 200
    bearer = issued.json()["data"]["access_token"]
    refresh = http_client.cookies.get("cmab_refresh_token")
    assert (await http_client.get("/api/v1/auth/me", headers={"Authorization": "Bearer " + bearer})).status_code == 200

    denied_login = await oidc_only_http.post("/api/v1/auth/login", json=credentials)
    assert denied_login.status_code == 403
    assert "set-cookie" not in denied_login.headers
    denied_bearer = await oidc_only_http.get("/api/v1/auth/me", headers={"Authorization": "Bearer " + bearer})
    assert denied_bearer.status_code == 403
    oidc_only_http.cookies.set("cmab_refresh_token", refresh, path="/api/v1/auth")
    denied_refresh = await oidc_only_http.post("/api/v1/auth/refresh")
    assert denied_refresh.status_code == 403
    assert "set-cookie" not in denied_refresh.headers

    config = (await oidc_only_http.get("/api/v1/auth/oidc/config")).json()["data"]
    assert config == {"enabled": False, "native_login_enabled": False}
    unavailable = await oidc_only_http.get("/api/v1/auth/oidc/login")
    assert unavailable.status_code == 503
    assert "location" not in unavailable.headers
    assert "原生" not in unavailable.text

    # The rejected refresh did not consume/rotate the credential, and opting in
    # to SSO-only did not silently change a separate compatible deployment.
    assert (await http_client.post("/api/v1/auth/refresh")).status_code == 200
