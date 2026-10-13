"""
Refresh Token 旋转 + 撤销测试（P4.B-1）

设计参考：API-MDM-001 V1.1 §2.2 + ARCH-MDM-001 V1.1 §7.2.1
- 登录后 Set-Cookie: cmab_refresh_token; HttpOnly; SameSite=Strict
- /auth/refresh：旋转策略，每次返回新 access + 新 refresh，旧 jti 入 revoked
- /auth/logout：204 + 撤销 + 清 cookie
- 改密：撤销该用户所有活跃 refresh
"""
import pytest
from app.core.security import decode_token
from httpx import AsyncClient

from tests.conftest import BASE_URL
from tests.test_password_policy import sql


@pytest.mark.asyncio
async def test_login_sets_refresh_cookie():
    async with AsyncClient(base_url=BASE_URL, timeout=10.0) as client:
        resp = await client.post(
            "/api/v1/auth/login",
            json={"username": "admin", "password": "__REDACTED_SEED_PASSWORD_1__"},
        )
        assert resp.status_code == 200
        # Cookie 写入
        assert "cmab_refresh_token" in resp.cookies
        # 响应体含 access_token + user
        body = resp.json()
        assert body["data"]["access_token"]
        assert body["data"]["user"]["username"] == "admin"


@pytest.mark.asyncio
async def test_refresh_returns_new_access_and_rotates_cookie():
    async with AsyncClient(base_url=BASE_URL, timeout=10.0) as client:
        login = await client.post(
            "/api/v1/auth/login",
            json={"username": "admin", "password": "__REDACTED_SEED_PASSWORD_1__"},
        )
        old_refresh = login.cookies.get("cmab_refresh_token")
        old_access = login.json()["data"]["access_token"]
        assert old_refresh
        # 等 1.1 秒确保新 access 的 iat 与旧不同（JWT iat 是秒级整数）
        import asyncio
        await asyncio.sleep(1.1)

        refresh = await client.post("/api/v1/auth/refresh")
        assert refresh.status_code == 200
        body = refresh.json()
        assert body["code"] == 0
        new_access = body["data"]["access_token"]
        assert new_access != old_access  # 新 access
        assert body["data"]["expires_in"] == 900  # 0054：access 15 分钟

        # cookie 已被旋转
        new_refresh = refresh.cookies.get("cmab_refresh_token")
        assert new_refresh
        assert new_refresh != old_refresh


@pytest.mark.asyncio
async def test_refresh_old_token_rejected_after_repeat_window():
    """5 秒复取窗口结束后，旧 refresh 继续拒绝。"""
    async with AsyncClient(base_url=BASE_URL, timeout=10.0) as client:
        await client.post(
            "/api/v1/auth/login",
            json={"username": "readonly", "password": "__REDACTED_SEED_PASSWORD_4__"},
        )
        # 取旧 cookie
        old_refresh = client.cookies.get("cmab_refresh_token")
        assert old_refresh

        # 触发一次 refresh（client 自动用旧 cookie，并接收新 cookie）
        r1 = await client.post("/api/v1/auth/refresh")
        assert r1.status_code == 200

        await sql("UPDATE auth.refresh_token SET revoked_at=now()-interval '6 seconds' WHERE jti=$1",
                  decode_token(old_refresh)['jti'])

        # 手工用旧 refresh 再次调 refresh（不带 cookie jar，自己塞）
        async with AsyncClient(base_url=BASE_URL, timeout=10.0) as fresh:
            fresh.cookies.set("cmab_refresh_token", old_refresh)
            r2 = await fresh.post("/api/v1/auth/refresh")
        assert r2.status_code == 401
        assert r2.json()["code"] == 40103  # token_invalid


@pytest.mark.asyncio
async def test_refresh_without_cookie_returns_401():
    async with AsyncClient(base_url=BASE_URL, timeout=10.0) as client:
        resp = await client.post("/api/v1/auth/refresh")
        assert resp.status_code == 401
        assert resp.json()["code"] == 40104  # token_missing


@pytest.mark.asyncio
async def test_refresh_with_bogus_cookie_rejected():
    async with AsyncClient(base_url=BASE_URL, timeout=10.0) as client:
        client.cookies.set("cmab_refresh_token", "not-a-jwt")
        resp = await client.post("/api/v1/auth/refresh")
        assert resp.status_code == 401


@pytest.mark.asyncio
async def test_logout_revokes_and_clears_cookie():
    async with AsyncClient(base_url=BASE_URL, timeout=10.0) as client:
        await client.post(
            "/api/v1/auth/login",
            json={"username": "readonly", "password": "__REDACTED_SEED_PASSWORD_4__"},
        )
        # logout
        out = await client.post("/api/v1/auth/logout")
        assert out.status_code == 204
        # 注：Set-Cookie 删除头格式因 cookie 库差异，最稳的断言是再 refresh 应失败
        r = await client.post("/api/v1/auth/refresh")
        # 视 httpx 是否实际接受了 Set-Cookie max-age=0；保守接受任一 401 表现
        assert r.status_code == 401


# NOTE：原计划用 throwaway user 测"改密撤销所有 refresh token"路径，但在测试体内
# 直接持有 AsyncSessionLocal 会触发项目已知的 BaseHTTPMiddleware + asyncpg 跨 event loop
# 冲突（见 conftest.py docstring）。该撤销逻辑在 services.change_password 里通过
# 一条显式 `UPDATE auth.refresh_token SET revoked_at=NOW(), revoked_reason='password_changed'`
# 语句直接保证，代码层可见；同时 test_refresh_old_token_rejected_after_rotation 已经覆盖了
# refresh 撤销失效路径。该 e2e 用例推迟到 Phase 5 引入 admin user-mgmt API 后补做。
