"""Phase 5.A / M5.4 个人中心测试

覆盖：
- GET /auth/me/login-history 返回当前用户登录历史（不混入他人）
- 分页生效
- 未登录 401
- GET /auth/me/signatures 返回当前用户签名（不混入他人）
- 创建签名后能在 me/signatures 看到
- readonly 用户可看自己的（不需要 audit:read 权限）
"""
import pytest


# ============== 登录历史 ==============
@pytest.mark.asyncio
async def test_my_login_history_returns_self(admin_client):
    """admin 已通过 fixture 登录，应至少有 1 条成功记录"""
    r = await admin_client.get("/api/v1/auth/me/login-history?page=1&page_size=10")
    assert r.status_code == 200
    body = r.json()
    items = body["data"]
    assert len(items) >= 1
    # 所有记录 username_input 必须是 admin（service 强制 user_id 过滤）
    assert all(item["username_input"] == "admin" for item in items)
    # 至少最近一条成功（fixture 刚登录）
    assert any(item["success"] is True for item in items)


@pytest.mark.asyncio
async def test_my_login_history_isolated_between_users(admin_client, readonly_client):
    """admin 看不到 readonly 的登录历史；readonly 看不到 admin 的"""
    r_admin = await admin_client.get("/api/v1/auth/me/login-history?page_size=100")
    r_ro = await readonly_client.get("/api/v1/auth/me/login-history?page_size=100")
    assert r_admin.status_code == 200
    assert r_ro.status_code == 200

    admin_users = {item["username_input"] for item in r_admin.json()["data"]}
    ro_users = {item["username_input"] for item in r_ro.json()["data"]}
    assert "readonly" not in admin_users
    assert "admin" not in ro_users
    assert admin_users <= {"admin"}
    assert ro_users <= {"readonly"}


@pytest.mark.asyncio
async def test_my_login_history_requires_auth(http_client):
    r = await http_client.get("/api/v1/auth/me/login-history")
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_my_login_history_paginated(admin_client):
    """分页生效：page=1 + page_size=1 返回单条"""
    r = await admin_client.get("/api/v1/auth/me/login-history?page=1&page_size=1")
    assert r.status_code == 200
    body = r.json()
    assert len(body["data"]) <= 1
    assert body["meta"]["pagination"]["page_size"] == 1


# ============== 我的签名 ==============
@pytest.mark.asyncio
async def test_my_signatures_returns_self_only(admin_client, unique_suffix):
    """admin 创建一个 substance 并 approve（产生签名），应在 /me/signatures 看到"""
    # 创建 + approve（带签名）
    r1 = await admin_client.post(
        "/api/v1/substances",
        json={
            "substance_type": "mab",
            "internal_code": f"PROF-{unique_suffix}",
            "preferred_name": f"profile sig test {unique_suffix}",
        },
    )
    assert r1.status_code == 201
    code = r1.json()["data"]["substance_code"]

    r2 = await admin_client.post(
        f"/api/v1/substances/{code}:approve",
        json={
            "comment": "M5.4 profile test",
            "signature": {
                "password": "__REDACTED_SEED_PASSWORD_1__",
                "reason": "M5.4 测试个人签名记录",
            },
        },
    )
    assert r2.status_code == 200

    # /me/signatures 应能看到新签名
    r3 = await admin_client.get("/api/v1/auth/me/signatures?page_size=100")
    assert r3.status_code == 200
    sigs = r3.json()["data"]
    # 所有签名都是 admin 的（强制 user_id 过滤）
    assert all(s["username"] == "admin" for s in sigs)
    # 含刚创建的
    assert any(s["entity_code"] == code for s in sigs)


@pytest.mark.asyncio
async def test_my_signatures_readonly_user_no_signatures(readonly_client):
    """readonly 用户从未签过名，但端点可访问（无需 audit:read 权限）"""
    r = await readonly_client.get("/api/v1/auth/me/signatures")
    assert r.status_code == 200
    body = r.json()
    # 强制只看 readonly 自己；readonly 没签过名
    assert body["meta"]["pagination"]["total"] == 0
    assert body["data"] == []


@pytest.mark.asyncio
async def test_my_signatures_requires_auth(http_client):
    r = await http_client.get("/api/v1/auth/me/signatures")
    assert r.status_code == 401
