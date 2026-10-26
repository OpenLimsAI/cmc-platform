"""
会话策略测试（2026-09-04；migration 0054）

- 默认值 15 / 30 / 12h / 720
- 管理员可改（立即生效：下一次登录按新值签发）；非管理员 403；不合法组合 400
- 空闲超时：refresh 行 expires_at 已过 → 401 token_expired
- 硬上限：session_started_at 超过 absolute_max_hours → 401 token_expired
- 展示模式：挂 DISPLAY_MODE 角色的账号，refresh 到期按展示模式空闲时长
- /auth/session-policy：任意登录用户可读自己生效的策略
"""
import base64
import json
from datetime import UTC, datetime, timedelta

import asyncpg
import pytest
from httpx import AsyncClient

from tests.conftest import BASE_URL, pg_connect_kwargs

DEFAULTS = {
    "access_token_minutes": 15,
    "idle_timeout_minutes": 30,
    "absolute_max_hours": 12,
    "display_mode_idle_minutes": 720,
}


def _jti(refresh_jwt: str) -> str:
    payload_b64 = refresh_jwt.split(".")[1]
    payload_b64 += "=" * (-len(payload_b64) % 4)
    return json.loads(base64.urlsafe_b64decode(payload_b64))["jti"]


async def _refresh_row(jti: str):
    conn = await asyncpg.connect(**pg_connect_kwargs())
    try:
        return await conn.fetchrow(
            "SELECT expires_at, session_started_at FROM auth.refresh_token WHERE jti = $1", jti
        )
    finally:
        await conn.close()


async def _exec(sql: str, *args):
    conn = await asyncpg.connect(**pg_connect_kwargs())
    try:
        await conn.execute(sql, *args)
    finally:
        await conn.close()


async def _login(client: AsyncClient, username: str, password: str) -> tuple[str, str]:
    resp = await client.post(
        "/api/v1/auth/login", json={"username": username, "password": password}
    )
    assert resp.status_code == 200, resp.text
    return resp.json()["data"]["access_token"], resp.cookies["cmab_refresh_token"]


# ============== 读 ==============
@pytest.mark.asyncio
async def test_admin_get_policy_defaults(admin_client):
    resp = await admin_client.get("/api/v1/system/session-policy")
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    for k, v in DEFAULTS.items():
        assert data[k] == v, (k, data)
    assert "limits" in data


@pytest.mark.asyncio
async def test_non_admin_cannot_read_or_write_policy(readonly_client):
    r1 = await readonly_client.get("/api/v1/system/session-policy")
    assert r1.status_code == 403
    r2 = await readonly_client.put("/api/v1/system/session-policy", json=DEFAULTS)
    assert r2.status_code == 403


@pytest.mark.asyncio
async def test_me_session_policy(readonly_client):
    resp = await readonly_client.get("/api/v1/auth/session-policy")
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    assert data["access_token_minutes"] == DEFAULTS["access_token_minutes"]
    assert data["idle_timeout_minutes"] == DEFAULTS["idle_timeout_minutes"]
    assert data["absolute_max_hours"] == DEFAULTS["absolute_max_hours"]
    assert data["display_mode"] is False


# ============== 登录签发按策略 ==============
@pytest.mark.asyncio
async def test_login_issues_by_policy():
    async with AsyncClient(base_url=BASE_URL, timeout=10.0) as client:
        resp = await client.post(
            "/api/v1/auth/login", json={"username": "readonly", "password": "__REDACTED_SEED_PASSWORD_4__"}
        )
        assert resp.status_code == 200
        assert resp.json()["data"]["expires_in"] == 15 * 60
        # cookie max_age = 硬上限
        assert "Max-Age=43200" in resp.headers.get("set-cookie", "")
        row = await _refresh_row(_jti(resp.cookies["cmab_refresh_token"]))
        now = datetime.now(UTC)
        remain = (row["expires_at"] - now).total_seconds()
        assert 29 * 60 < remain <= 30 * 60 + 5, remain
        assert abs((row["session_started_at"] - now).total_seconds()) < 10


# ============== 改 ==============
@pytest.mark.asyncio
async def test_update_policy_rejects_inconsistent(admin_client):
    bad = {**DEFAULTS, "access_token_minutes": 60, "idle_timeout_minutes": 30}
    resp = await admin_client.put("/api/v1/system/session-policy", json=bad)
    assert resp.status_code == 400, resp.text
    bad2 = {**DEFAULTS, "idle_timeout_minutes": 2}  # 低于下限 5
    resp2 = await admin_client.put("/api/v1/system/session-policy", json=bad2)
    assert resp2.status_code == 400, resp2.text


@pytest.mark.asyncio
async def test_update_policy_takes_effect_immediately(admin_client):
    new = {**DEFAULTS, "access_token_minutes": 10, "idle_timeout_minutes": 45,
           "reason": "测试：改空闲 45 分钟"}
    try:
        resp = await admin_client.put("/api/v1/system/session-policy", json=new)
        assert resp.status_code == 200, resp.text
        assert resp.json()["data"]["idle_timeout_minutes"] == 45
        assert resp.json()["data"]["updated_at"]

        async with AsyncClient(base_url=BASE_URL, timeout=10.0) as client:
            login = await client.post(
                "/api/v1/auth/login", json={"username": "readonly", "password": "__REDACTED_SEED_PASSWORD_4__"}
            )
            assert login.json()["data"]["expires_in"] == 10 * 60
            row = await _refresh_row(_jti(login.cookies["cmab_refresh_token"]))
            remain = (row["expires_at"] - datetime.now(UTC)).total_seconds()
            assert 44 * 60 < remain <= 45 * 60 + 5, remain

        # 审计留痕
        audit = await admin_client.get(
            "/api/v1/audit-logs", params={"entity_table": "system_config", "page_size": 5}
        )
        assert audit.status_code == 200
        items = audit.json()["data"]
        hit = next((i for i in items if i["entity_code"] == "session_policy"), None)
        assert hit is not None, items
        assert hit["action"] == "UPDATE" and hit["reason"] == "测试：改空闲 45 分钟"
        diffs = {c["field_name"]: (c["old_value"], c["new_value"]) for c in hit["changes"]}
        assert diffs["idle_timeout_minutes"] == (30, 45), diffs
        assert diffs["access_token_minutes"] == (15, 10), diffs
    finally:
        restore = await admin_client.put("/api/v1/system/session-policy", json=DEFAULTS)
        assert restore.status_code == 200, restore.text


# ============== 到期分支 ==============
@pytest.mark.asyncio
async def test_refresh_rejected_after_idle_timeout():
    async with AsyncClient(base_url=BASE_URL, timeout=10.0) as client:
        _, refresh = await _login(client, "readonly", "__REDACTED_SEED_PASSWORD_4__")
        await _exec(
            "UPDATE auth.refresh_token SET expires_at = NOW() - INTERVAL '1 minute' WHERE jti = $1",
            _jti(refresh),
        )
        resp = await client.post("/api/v1/auth/refresh")
        assert resp.status_code == 401, resp.text
        body = resp.json()
        assert body["meta"]["error"]["type"] == "token_expired"
        assert "未操作" in body["message"]


@pytest.mark.asyncio
async def test_refresh_rejected_after_absolute_max():
    async with AsyncClient(base_url=BASE_URL, timeout=10.0) as client:
        _, refresh = await _login(client, "readonly", "__REDACTED_SEED_PASSWORD_4__")
        started = datetime.now(UTC) - timedelta(hours=13)
        await _exec(
            "UPDATE auth.refresh_token SET session_started_at = $2 WHERE jti = $1",
            _jti(refresh), started,
        )
        resp = await client.post("/api/v1/auth/refresh")
        assert resp.status_code == 401, resp.text
        body = resp.json()
        assert body["meta"]["error"]["type"] == "token_expired"
        assert "12 小时" in body["message"]


@pytest.mark.asyncio
async def test_refresh_slides_but_capped_by_absolute_max():
    """轮换后新 refresh 的到期 = min(现在+空闲, 会话开始+硬上限)，且 session_started_at 原样传递"""
    async with AsyncClient(base_url=BASE_URL, timeout=10.0) as client:
        _, refresh = await _login(client, "readonly", "__REDACTED_SEED_PASSWORD_4__")
        # 把会话开始拨到 11h50m 前：硬上限只剩 10 分钟 < 空闲 30 分钟
        started = datetime.now(UTC) - timedelta(hours=11, minutes=50)
        await _exec(
            "UPDATE auth.refresh_token SET session_started_at = $2 WHERE jti = $1",
            _jti(refresh), started,
        )
        resp = await client.post("/api/v1/auth/refresh")
        assert resp.status_code == 200, resp.text
        row = await _refresh_row(_jti(resp.cookies["cmab_refresh_token"]))
        assert abs((row["session_started_at"] - started).total_seconds()) < 1
        remain = (row["expires_at"] - datetime.now(UTC)).total_seconds()
        assert 9 * 60 < remain <= 10 * 60 + 5, remain


# ============== 展示模式 ==============
@pytest.mark.asyncio
async def test_display_mode_role_widens_idle(admin_client):
    assign = await admin_client.put(
        "/api/v1/users/readonly/roles", json={"role_codes": ["READ_ONLY_USER", "DISPLAY_MODE"]}
    )
    assert assign.status_code == 200, assign.text
    try:
        async with AsyncClient(base_url=BASE_URL, timeout=10.0) as client:
            token, refresh = await _login(client, "readonly", "__REDACTED_SEED_PASSWORD_4__")
            row = await _refresh_row(_jti(refresh))
            remain = (row["expires_at"] - datetime.now(UTC)).total_seconds()
            assert 719 * 60 < remain <= 720 * 60 + 5, remain
            me = await client.get(
                "/api/v1/auth/session-policy", headers={"Authorization": f"Bearer {token}"}
            )
            assert me.json()["data"]["display_mode"] is True
            assert me.json()["data"]["idle_timeout_minutes"] == 720
    finally:
        restore = await admin_client.put(
            "/api/v1/users/readonly/roles", json={"role_codes": ["READ_ONLY_USER"]}
        )
        assert restore.status_code == 200, restore.text
