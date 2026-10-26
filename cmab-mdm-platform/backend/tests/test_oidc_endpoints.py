"""Default-off HTTP compatibility contract; real Casdoor browser flow is separate."""


async def test_default_off_reports_native_recovery_without_provider(http_client):
    response = await http_client.get("/api/v1/auth/oidc/config")
    assert response.status_code == 200
    assert response.json()["data"] == {"enabled": False, "native_login_enabled": True}
    assert response.headers["cache-control"] == "no-store"


async def test_disabled_login_does_not_redirect_to_unknown_provider(http_client):
    response = await http_client.get("/api/v1/auth/oidc/login")
    assert response.status_code == 503
    assert "location" not in response.headers


async def test_failed_callback_has_fixed_local_return_no_secret_echo(http_client):
    response = await http_client.get("/api/v1/auth/oidc/callback?code=secret-code&state=not-a-valid-state")
    assert response.status_code == 303
    assert response.headers["location"] == "/mdm/login?oidc_error=disabled"
    assert "secret-code" not in str(response.headers) + response.text
    assert response.headers["referrer-policy"] == "no-referrer"


async def test_native_login_still_works_with_feature_off(admin_client):
    response = await admin_client.get("/api/v1/auth/me")
    assert response.status_code == 200 and response.json()["data"]["username"] == "admin"
