"""Phase 5.A / M5.1 管理员侧用户管理测试

覆盖：
- 创建用户（成功 + username 40906 + email 40907 + 不存在角色 40001）
- 列表（q / role_code / status 过滤）
- 详情 / 更新 profile / 角色分配
- lock / unlock / reset-password 三个动作
- 自我误操作保护（不能 lock/reset 自己）
- 最后一个 SYS_ADMIN 不可取消
- readonly 调用 403
- 临时密码登录 must_change_password=True，改密后清零
"""
import asyncio
import uuid

import pytest


async def _db(sql: str, *args):
    import asyncpg

    conn = await asyncpg.connect(
        host="postgres", port=5432, user="cmab_app",
        password="__REDACTED_POSTGRES_PASSWORD__", database="cmab_mdm",
    )
    try:
        return await conn.fetch(sql, *args)
    finally:
        await conn.close()


def _payload(suffix: str, **overrides) -> dict:
    base = {
        "username": f"u_{suffix}",
        "email": f"u_{suffix}@test.com",
        "password": "TestUser@2026!",
        "full_name": f"测试用户 {suffix}",
        "department": "CMC R&D",
        "title": "Scientist",
        "role_codes": ["READ_ONLY_USER"],
    }
    base.update(overrides)
    return base


# ============== 创建用户 ==============
@pytest.mark.asyncio
async def test_create_user_success(admin_client, unique_suffix):
    r = await admin_client.post("/api/v1/users", json=_payload(unique_suffix))
    assert r.status_code == 201, r.text
    data = r.json()["data"]
    assert data["username"] == f"u_{unique_suffix}"
    assert data["status"] == "active"
    assert data["force_password_change"] is False
    assert {x["role_code"] for x in data["roles"]} == {"READ_ONLY_USER"}


@pytest.mark.asyncio
async def test_create_user_duplicate_username(admin_client, unique_suffix):
    p = _payload(unique_suffix)
    r1 = await admin_client.post("/api/v1/users", json=p)
    assert r1.status_code == 201

    p2 = _payload(unique_suffix, email=f"alt_{unique_suffix}@test.com")
    r2 = await admin_client.post("/api/v1/users", json=p2)
    assert r2.status_code == 409
    body = r2.json()
    assert body["code"] == 40906
    assert body["meta"]["error"]["type"] == "username_exists"


@pytest.mark.asyncio
async def test_create_user_duplicate_email(admin_client, unique_suffix):
    p = _payload(unique_suffix)
    r1 = await admin_client.post("/api/v1/users", json=p)
    assert r1.status_code == 201

    p2 = _payload(f"alt{unique_suffix}", email=p["email"])
    r2 = await admin_client.post("/api/v1/users", json=p2)
    assert r2.status_code == 409
    assert r2.json()["code"] == 40907


@pytest.mark.asyncio
async def test_create_user_invalid_role(admin_client, unique_suffix):
    p = _payload(unique_suffix, role_codes=["NOT_A_REAL_ROLE"])
    r = await admin_client.post("/api/v1/users", json=p)
    assert r.status_code == 400
    assert r.json()["code"] == 40001


# ============== 列表 / 详情 / 更新 ==============
@pytest.mark.asyncio
async def test_list_users_basic_and_filter(admin_client, unique_suffix):
    r = await admin_client.post("/api/v1/users", json=_payload(unique_suffix))
    assert r.status_code == 201
    username = r.json()["data"]["username"]

    # 全量列表（至少含 5 内置 + 1 新）
    r_all = await admin_client.get("/api/v1/users")
    assert r_all.status_code == 200
    assert r_all.json()["meta"]["pagination"]["total"] >= 6

    # q 过滤
    r_q = await admin_client.get(f"/api/v1/users?q={username}")
    assert r_q.status_code == 200
    items = r_q.json()["data"]
    assert any(u["username"] == username for u in items)

    # role_code + q 双过滤精准定位新用户
    r_role = await admin_client.get(
        f"/api/v1/users?role_code=READ_ONLY_USER&q={username}"
    )
    assert r_role.status_code == 200
    assert any(u["username"] == username for u in r_role.json()["data"])

    # status 过滤
    r_status = await admin_client.get("/api/v1/users?status=active")
    assert r_status.status_code == 200
    assert all(u["status"] == "active" for u in r_status.json()["data"])


@pytest.mark.asyncio
async def test_update_user_profile(admin_client, unique_suffix):
    r = await admin_client.post("/api/v1/users", json=_payload(unique_suffix))
    username = r.json()["data"]["username"]

    r_put = await admin_client.put(
        f"/api/v1/users/{username}",
        json={"full_name": "改名了", "department": "QA"},
    )
    assert r_put.status_code == 200
    d = r_put.json()["data"]
    assert d["full_name"] == "改名了"
    assert d["department"] == "QA"


@pytest.mark.asyncio
async def test_assign_roles_replace(admin_client, unique_suffix):
    r = await admin_client.post(
        "/api/v1/users", json=_payload(unique_suffix, role_codes=["READ_ONLY_USER"])
    )
    username = r.json()["data"]["username"]

    r_put = await admin_client.put(
        f"/api/v1/users/{username}/roles",
        json={"role_codes": ["CMC_RESEARCHER", "QA_REVIEWER"]},
    )
    assert r_put.status_code == 200
    codes = {r["role_code"] for r in r_put.json()["data"]["roles"]}
    assert codes == {"CMC_RESEARCHER", "QA_REVIEWER"}


# ============== 动作端点 ==============
@pytest.mark.asyncio
async def test_lock_then_unlock(admin_client, http_client, unique_suffix):
    p = _payload(unique_suffix)
    await admin_client.post("/api/v1/users", json=p)
    username, password = p["username"], p["password"]

    # 先确认能登录
    r0 = await http_client.post(
        "/api/v1/auth/login", json={"username": username, "password": password}
    )
    assert r0.status_code == 200

    # lock
    r_lock = await admin_client.post(f"/api/v1/users/{username}:lock")
    assert r_lock.status_code == 200
    assert r_lock.json()["data"]["status"] == "locked"

    # 锁定后登录被拒（423）
    r_locked_login = await http_client.post(
        "/api/v1/auth/login", json={"username": username, "password": password}
    )
    assert r_locked_login.status_code == 423

    # unlock
    r_unlock = await admin_client.post(f"/api/v1/users/{username}:unlock")
    assert r_unlock.status_code == 200
    assert r_unlock.json()["data"]["status"] == "active"

    # 解锁后能再登录
    r_relogin = await http_client.post(
        "/api/v1/auth/login", json={"username": username, "password": password}
    )
    assert r_relogin.status_code == 200


@pytest.mark.asyncio
async def test_cannot_lock_self(admin_client):
    r = await admin_client.post("/api/v1/users/admin:lock")
    assert r.status_code == 403
    assert r.json()["code"] == 40305


@pytest.mark.asyncio
async def test_reset_password_flow(admin_client, http_client, unique_suffix):
    p = _payload(unique_suffix)
    await admin_client.post("/api/v1/users", json=p)
    username, old_pw = p["username"], p["password"]

    # admin 重置
    r_reset = await admin_client.post(f"/api/v1/users/{username}:reset-password")
    assert r_reset.status_code == 200
    payload = r_reset.json()["data"]
    temp_pw = payload["temp_password"]
    assert payload["force_password_change"] is True
    assert len(temp_pw) == 16

    # 旧密码不再可用
    r_old = await http_client.post(
        "/api/v1/auth/login", json={"username": username, "password": old_pw}
    )
    assert r_old.status_code == 401

    # 用临时密码登录，must_change_password=True
    r_login = await http_client.post(
        "/api/v1/auth/login", json={"username": username, "password": temp_pw}
    )
    assert r_login.status_code == 200
    body = r_login.json()["data"]
    assert body["user"]["must_change_password"] is True
    new_token = body["access_token"]

    # 用临时密码登录后改密
    new_pw = "FreshPwd@2026!!"
    r_chg = await http_client.post(
        "/api/v1/auth/change-password",
        headers={"Authorization": f"Bearer {new_token}"},
        json={"old_password": temp_pw, "new_password": new_pw},
    )
    assert r_chg.status_code == 200

    # 改密后 force_password_change 清零（验 detail）
    r_detail = await admin_client.get(f"/api/v1/users/{username}")
    assert r_detail.json()["data"]["force_password_change"] is False

    # 新密码可以正常登，旧（temp）不能用
    r_new = await http_client.post(
        "/api/v1/auth/login", json={"username": username, "password": new_pw}
    )
    assert r_new.status_code == 200
    assert r_new.json()["data"]["user"]["must_change_password"] is False

    r_temp_again = await http_client.post(
        "/api/v1/auth/login", json={"username": username, "password": temp_pw}
    )
    assert r_temp_again.status_code == 401


@pytest.mark.asyncio
async def test_cannot_reset_own_password(admin_client):
    r = await admin_client.post("/api/v1/users/admin:reset-password")
    assert r.status_code == 403
    assert r.json()["code"] == 40305


@pytest.mark.asyncio
async def test_cannot_remove_last_sys_admin(admin_client):
    """admin 自己若是唯一 SYS_ADMIN，不能取消该角色 → 40304"""
    # 先检查 admin 是不是唯一活跃 SYS_ADMIN
    rows = await _db(
        """
        SELECT COUNT(DISTINCT u.user_id) AS c FROM auth.user u
          JOIN auth.user_role ur ON ur.user_id = u.user_id
          JOIN auth.role r ON r.role_id = ur.role_id
         WHERE r.role_code = 'SYS_ADMIN'
           AND u.deleted_at IS NULL AND u.status = 'active'
        """,
    )
    if rows[0]["c"] == 1:
        # 唯一管理员，应该拒
        r = await admin_client.put(
            "/api/v1/users/admin/roles",
            json={"role_codes": ["READ_ONLY_USER"]},
        )
        assert r.status_code == 403
        assert r.json()["code"] == 40304


@pytest.mark.asyncio
async def test_readonly_forbidden(readonly_client):
    r1 = await readonly_client.get("/api/v1/users")
    assert r1.status_code == 403

    r2 = await readonly_client.post(
        "/api/v1/users",
        json=_payload(uuid.uuid4().hex[:8]),
    )
    assert r2.status_code == 403

    r3 = await readonly_client.post("/api/v1/users/admin:lock")
    assert r3.status_code == 403
