"""H-05 强制改密权威拦截测试

覆盖：
- force_password_change=true 期间业务 API → 403 password_change_required
- /auth/me、/auth/change-password 放行
- 改密成功后业务 API 恢复正常
"""
import pytest

from tests.test_admin_users import _payload


@pytest.mark.asyncio
async def test_force_password_change_gate(admin_client, http_client, unique_suffix):
    p = _payload(unique_suffix)
    await admin_client.post("/api/v1/users", json=p)
    username = p["username"]

    r_reset = await admin_client.post(f"/api/v1/users/{username}:reset-password")
    assert r_reset.status_code == 200
    temp_pw = r_reset.json()["data"]["temp_password"]

    r_login = await http_client.post(
        "/api/v1/auth/login", json={"username": username, "password": temp_pw}
    )
    assert r_login.status_code == 200
    headers = {"Authorization": f"Bearer {r_login.json()['data']['access_token']}"}

    # 业务 API 被拦截：403 + password_change_required（不是 401）
    r_biz = await http_client.get("/api/v1/substances", headers=headers)
    assert r_biz.status_code == 403
    assert r_biz.json()["meta"]["error"]["type"] == "password_change_required"

    # /auth/me 放行（前端守卫/刷新需要读取标记）
    r_me = await http_client.get("/api/v1/auth/me", headers=headers)
    assert r_me.status_code == 200
    assert r_me.json()["data"]["force_password_change"] is True

    # /auth/change-password 放行
    new_pw = "FreshPwd@2026!!!"
    r_chg = await http_client.post(
        "/api/v1/auth/change-password",
        headers=headers,
        json={"old_password": temp_pw, "new_password": new_pw},
    )
    assert r_chg.status_code == 200

    # 改密成功后重新登录，业务 API 恢复
    r_login2 = await http_client.post(
        "/api/v1/auth/login", json={"username": username, "password": new_pw}
    )
    assert r_login2.status_code == 200
    assert r_login2.json()["data"]["user"]["must_change_password"] is False
    headers2 = {"Authorization": f"Bearer {r_login2.json()['data']['access_token']}"}
    r_biz2 = await http_client.get("/api/v1/substances", headers=headers2)
    assert r_biz2.status_code == 200
