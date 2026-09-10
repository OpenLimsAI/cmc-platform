"""部门管理员（DEPT_ADMIN）测试（2026-09-10；migration 0055）

覆盖：
- 迁移落地：DEPT_ADMIN + QV_ 四角色存在；白名单默认 QV_
- 部门管理员：列表只见本部门；跨部门 详情/锁定/挂角色 一律 403
- 挂 QV_ 角色成功（原有非白名单角色原样保留）+ audit_log PERMISSION_CHANGE 记录
- 挂 SYS_ADMIN / DEPT_ADMIN / 非白名单角色被拒 403
- 锁定/解锁本部门用户成功 + audit_log 记录；不能锁定持 SYS_ADMIN 的账号
- 新建用户 / 改资料 / 重置密码 403（仍只认 user:manage）
- GET /roles 只返回白名单角色；/permissions 403
- 无部门的 DEPT_ADMIN 403
- 白名单在线改（system:config）：加前缀后立刻能下放；非 admin 403；非法前缀 400
- SYS_ADMIN 不受影响：全量列表、任意角色、跨部门
"""
import asyncio
import uuid

import pytest
import pytest_asyncio

from tests.conftest import _AuthedClient, pg_connect_kwargs

PW = "Dept__REDACTED_SEED_PASSWORD_1__"


async def _db(sql: str, *args):
    import asyncpg

    conn = await asyncpg.connect(**pg_connect_kwargs())
    try:
        return await conn.fetch(sql, *args)
    finally:
        await conn.close()


async def _create(admin_client, suffix: str, *, dept: str | None, roles: list[str], tag: str):
    username = f"{tag}_{suffix}"
    r = await admin_client.post(
        "/api/v1/users",
        json={
            "username": username,
            "email": f"{username}@test.com",
            "password": PW,
            "full_name": f"{tag} {suffix}",
            "department": dept,
            "title": "Tester",
            "role_codes": roles,
        },
    )
    assert r.status_code == 201, r.text
    return username


async def _login_new_user(http_client, username: str) -> str:
    """刚创建的用户：yield 依赖的 commit 在响应之后才跑，紧接着登录可能撞上未提交 → 短重试"""
    for _ in range(10):
        resp = await http_client.post(
            "/api/v1/auth/login", json={"username": username, "password": PW}
        )
        if resp.status_code == 200:
            return resp.json()["data"]["access_token"]
        await asyncio.sleep(0.2)
    raise AssertionError(f"登录失败: {resp.text}")


@pytest_asyncio.fixture
async def dept_env(admin_client, http_client):
    """一个部门管理员 + 同部门普通用户 + 外部门用户 + 同部门 SYS_ADMIN；返回 dict"""
    suffix = uuid.uuid4().hex[:8]
    dept = f"QV_{suffix}"
    other_dept = f"OTHER_{suffix}"
    da = await _create(admin_client, suffix, dept=dept, roles=["DEPT_ADMIN"], tag="da")
    member = await _create(admin_client, suffix, dept=dept, roles=["READ_ONLY_USER"], tag="mem")
    outsider = await _create(admin_client, suffix, dept=other_dept, roles=["READ_ONLY_USER"], tag="out")
    dept_sysadmin = await _create(admin_client, suffix, dept=dept, roles=["SYS_ADMIN"], tag="sa")
    token = await _login_new_user(http_client, da)
    return {
        "suffix": suffix,
        "dept": dept,
        "da": da,
        "member": member,
        "outsider": outsider,
        "dept_sysadmin": dept_sysadmin,
        "client": _AuthedClient(http_client, token),
    }


# ============== 迁移落地 ==============
@pytest.mark.asyncio
async def test_migration_roles_and_config(admin_client):
    rows = await _db(
        "SELECT role_code, is_system FROM auth.role WHERE deleted_at IS NULL "
        "AND role_code IN ('DEPT_ADMIN','QV_ADMIN','QV_ENGINEER','QV_REVIEWER','QV_VIEWER')"
    )
    by_code = {r["role_code"]: r["is_system"] for r in rows}
    assert set(by_code) == {"DEPT_ADMIN", "QV_ADMIN", "QV_ENGINEER", "QV_REVIEWER", "QV_VIEWER"}
    assert by_code["DEPT_ADMIN"] is True

    r = await admin_client.get("/api/v1/system/dept-admin-policy")
    assert r.status_code == 200, r.text
    data = r.json()["data"]
    assert data["delegable_role_prefixes"] == ["QV_"]
    assert set(data["protected_roles"]) == {"SYS_ADMIN", "DEPT_ADMIN"}


# ============== 范围：本部门 ==============
@pytest.mark.asyncio
async def test_dept_admin_list_only_own_department(dept_env):
    c = dept_env["client"]
    r = await c.get("/api/v1/users?page_size=100")
    assert r.status_code == 200, r.text
    items = r.json()["data"]
    assert items, "本部门至少应有自己"
    assert all(u["department"] == dept_env["dept"] for u in items)
    names = {u["username"] for u in items}
    assert dept_env["member"] in names
    assert dept_env["outsider"] not in names
    assert "admin" not in names

    # q 搜索也不能越出部门
    r2 = await c.get(f"/api/v1/users?q={dept_env['outsider']}")
    assert r2.status_code == 200
    assert r2.json()["data"] == []


@pytest.mark.asyncio
async def test_dept_admin_cross_department_rejected(dept_env):
    c = dept_env["client"]
    out = dept_env["outsider"]

    r = await c.get(f"/api/v1/users/{out}")
    assert r.status_code == 403, r.text
    assert r.json()["code"] == 40303

    r = await c.post(f"/api/v1/users/{out}:lock")
    assert r.status_code == 403
    assert r.json()["code"] == 40303

    r = await c.put(f"/api/v1/users/{out}/roles", json={"role_codes": ["QV_VIEWER"]})
    assert r.status_code == 403
    assert r.json()["code"] == 40303

    # 跨部门被拒不应留下审计记录
    rows = await _db(
        "SELECT 1 FROM audit.audit_log WHERE username = $1 AND entity_code = $2",
        dept_env["da"], out,
    )
    assert rows == []


# ============== 挂/摘角色：白名单 ==============
@pytest.mark.asyncio
async def test_dept_admin_assign_whitelisted_role_with_audit(dept_env):
    c = dept_env["client"]
    member = dept_env["member"]

    r = await c.put(
        f"/api/v1/users/{member}/roles",
        json={"role_codes": ["QV_ENGINEER", "QV_VIEWER"]},
    )
    assert r.status_code == 200, r.text
    codes = {x["role_code"] for x in r.json()["data"]["roles"]}
    # 原有非白名单角色 READ_ONLY_USER 不被部门管理员碰掉
    assert codes == {"READ_ONLY_USER", "QV_ENGINEER", "QV_VIEWER"}

    # 摘掉一个
    r = await c.put(f"/api/v1/users/{member}/roles", json={"role_codes": ["QV_VIEWER"]})
    assert r.status_code == 200, r.text
    codes = {x["role_code"] for x in r.json()["data"]["roles"]}
    assert codes == {"READ_ONLY_USER", "QV_VIEWER"}

    rows = await _db(
        "SELECT action, entity_schema, entity_table, change_summary, extra "
        "FROM audit.audit_log WHERE username = $1 AND entity_code = $2 "
        "AND action = 'PERMISSION_CHANGE' ORDER BY log_id",
        dept_env["da"], member,
    )
    assert len(rows) == 2
    first, second = rows
    assert (first["entity_schema"], first["entity_table"]) == ("auth", "user")
    assert "+QV_ENGINEER" in first["change_summary"]
    assert "-QV_ENGINEER" in second["change_summary"]
    import json

    extra = json.loads(second["extra"]) if isinstance(second["extra"], str) else second["extra"]
    assert extra["actor_scope"] == "department"
    assert extra["actor_department"] == dept_env["dept"]
    assert extra["removed"] == ["QV_ENGINEER"]
    assert set(extra["roles_after"]) == {"READ_ONLY_USER", "QV_VIEWER"}


@pytest.mark.asyncio
async def test_dept_admin_assign_non_whitelisted_role_rejected(dept_env):
    c = dept_env["client"]
    member = dept_env["member"]
    for bad in (["SYS_ADMIN"], ["DEPT_ADMIN"], ["CMC_RESEARCHER"], ["QV_VIEWER", "READ_ONLY_USER"]):
        r = await c.put(f"/api/v1/users/{member}/roles", json={"role_codes": bad})
        assert r.status_code == 403, (bad, r.text)
        assert r.json()["code"] == 40301, bad

    # 角色集合未变
    r = await c.get(f"/api/v1/users/{member}")
    assert r.status_code == 200
    assert {x["role_code"] for x in r.json()["data"]["roles"]} == {"READ_ONLY_USER"}


# ============== 锁定 / 解锁 ==============
@pytest.mark.asyncio
async def test_dept_admin_lock_unlock_with_audit(dept_env):
    c = dept_env["client"]
    member = dept_env["member"]

    r = await c.post(f"/api/v1/users/{member}:lock")
    assert r.status_code == 200, r.text
    assert r.json()["data"]["status"] == "locked"

    r = await c.post(f"/api/v1/users/{member}:unlock")
    assert r.status_code == 200, r.text
    assert r.json()["data"]["status"] == "active"

    rows = await _db(
        "SELECT action, change_summary, extra FROM audit.audit_log "
        "WHERE username = $1 AND entity_code = $2 AND action = 'UPDATE' ORDER BY log_id",
        dept_env["da"], member,
    )
    assert len(rows) == 2
    assert "锁定" in rows[0]["change_summary"] and "解锁" in rows[1]["change_summary"]

    # 不能锁自己
    r = await c.post(f"/api/v1/users/{dept_env['da']}:lock")
    assert r.status_code == 403
    assert r.json()["code"] == 40305


@pytest.mark.asyncio
async def test_dept_admin_cannot_lock_sys_admin_in_same_department(dept_env):
    c = dept_env["client"]
    r = await c.post(f"/api/v1/users/{dept_env['dept_sysadmin']}:lock")
    assert r.status_code == 403, r.text
    assert r.json()["code"] == 40301
    r = await c.get(f"/api/v1/users/{dept_env['dept_sysadmin']}")
    assert r.status_code == 200
    assert r.json()["data"]["status"] == "active"


# ============== 不允许的动作 ==============
@pytest.mark.asyncio
async def test_dept_admin_forbidden_actions(dept_env):
    c = dept_env["client"]
    member = dept_env["member"]

    r = await c.post(
        "/api/v1/users",
        json={
            "username": f"new_{dept_env['suffix']}",
            "email": f"new_{dept_env['suffix']}@test.com",
            "password": PW,
            "full_name": "x",
            "department": dept_env["dept"],
        },
    )
    assert r.status_code == 403
    r = await c.put(f"/api/v1/users/{member}", json={"department": "IT"})
    assert r.status_code == 403
    r = await c.post(f"/api/v1/users/{member}:reset-password")
    assert r.status_code == 403
    r = await c.get("/api/v1/permissions")
    assert r.status_code == 403
    r = await c.post("/api/v1/roles", json={"role_code": "QV_X", "role_name": "x"})
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_dept_admin_roles_list_only_whitelisted(dept_env):
    r = await dept_env["client"].get("/api/v1/roles")
    assert r.status_code == 200, r.text
    codes = {x["role_code"] for x in r.json()["data"]}
    assert codes == {"QV_ADMIN", "QV_ENGINEER", "QV_REVIEWER", "QV_VIEWER"}


@pytest.mark.asyncio
async def test_dept_admin_without_department_rejected(admin_client, http_client, unique_suffix):
    da = await _create(admin_client, unique_suffix, dept=None, roles=["DEPT_ADMIN"], tag="nodept")
    token = await _login_new_user(http_client, da)
    c = _AuthedClient(http_client, token)
    r = await c.get("/api/v1/users")
    assert r.status_code == 403, r.text
    assert r.json()["code"] == 40301


# ============== 白名单在线改 ==============
@pytest.mark.asyncio
async def test_policy_update_takes_effect(admin_client, readonly_client, dept_env):
    c = dept_env["client"]
    member = dept_env["member"]

    # 改前：CMC_USP_ 前缀不可下放（角色由 seed_usp_roles 建，测试库可能没有；用 SYS_ 类比更稳）
    r = await c.put(f"/api/v1/users/{member}/roles", json={"role_codes": ["CMC_RESEARCHER"]})
    assert r.status_code == 403

    r = await readonly_client.put(
        "/api/v1/system/dept-admin-policy", json={"delegable_role_prefixes": ["QV_"]}
    )
    assert r.status_code == 403

    for bad in (["qv_"], ["SYS_"], ["DEPT"], ["QV-"]):
        r = await admin_client.put(
            "/api/v1/system/dept-admin-policy", json={"delegable_role_prefixes": bad}
        )
        assert r.status_code == 400, (bad, r.text)

    try:
        r = await admin_client.put(
            "/api/v1/system/dept-admin-policy",
            json={"delegable_role_prefixes": ["QV_", "CMC_RESEARCHER"], "reason": "测试"},
        )
        assert r.status_code == 200, r.text
        assert r.json()["data"]["delegable_role_prefixes"] == ["QV_", "CMC_RESEARCHER"]

        r = await c.put(f"/api/v1/users/{member}/roles", json={"role_codes": ["CMC_RESEARCHER"]})
        assert r.status_code == 200, r.text
        codes = {x["role_code"] for x in r.json()["data"]["roles"]}
        assert codes == {"READ_ONLY_USER", "CMC_RESEARCHER"}

        r = await c.get("/api/v1/roles")
        assert "CMC_RESEARCHER" in {x["role_code"] for x in r.json()["data"]}
    finally:
        r = await admin_client.put(
            "/api/v1/system/dept-admin-policy", json={"delegable_role_prefixes": ["QV_"]}
        )
        assert r.status_code == 200, r.text

    rows = await _db(
        "SELECT change_summary FROM audit.audit_log WHERE entity_code = 'dept_admin_policy' "
        "ORDER BY log_id DESC LIMIT 2"
    )
    assert len(rows) == 2


# ============== SYS_ADMIN 不受影响 ==============
@pytest.mark.asyncio
async def test_sys_admin_unaffected(admin_client, dept_env):
    member, outsider = dept_env["member"], dept_env["outsider"]

    r = await admin_client.get("/api/v1/users?page_size=100")
    assert r.status_code == 200
    names = {u["username"] for u in r.json()["data"]}
    assert {member, outsider, "admin"} <= names

    # 跨部门 + 非白名单角色 + 受保护角色 都可以
    r = await admin_client.put(
        f"/api/v1/users/{outsider}/roles", json={"role_codes": ["CMC_RESEARCHER", "QV_ADMIN"]}
    )
    assert r.status_code == 200, r.text
    assert {x["role_code"] for x in r.json()["data"]["roles"]} == {"CMC_RESEARCHER", "QV_ADMIN"}

    r = await admin_client.put(f"/api/v1/users/{member}/roles", json={"role_codes": ["DEPT_ADMIN"]})
    assert r.status_code == 200, r.text

    # SYS_ADMIN 的角色调整同样进审计（actor_scope=all）
    rows = await _db(
        "SELECT extra FROM audit.audit_log WHERE username = 'admin' AND entity_code = $1 "
        "AND action = 'PERMISSION_CHANGE' ORDER BY log_id DESC LIMIT 1",
        outsider,
    )
    assert len(rows) == 1
    import json

    extra = json.loads(rows[0]["extra"]) if isinstance(rows[0]["extra"], str) else rows[0]["extra"]
    assert extra["actor_scope"] == "all"

    r = await admin_client.post(f"/api/v1/users/{outsider}:lock")
    assert r.status_code == 200
    r = await admin_client.get("/api/v1/roles")
    assert "SYS_ADMIN" in {x["role_code"] for x in r.json()["data"]}


# ============== 令牌带部门（2026-09-10：门户/LabOps 按部门前缀判定）==============
@pytest.mark.asyncio
async def test_access_token_carries_department(admin_client, http_client, dept_env):
    import base64
    import json

    resp = await http_client.post(
        "/api/v1/auth/login", json={"username": dept_env["da"], "password": PW}
    )
    assert resp.status_code == 200, resp.text
    token = resp.json()["data"]["access_token"]
    payload_b64 = token.split(".")[1]
    payload_b64 += "=" * (-len(payload_b64) % 4)
    claims = json.loads(base64.urlsafe_b64decode(payload_b64))
    assert claims["department"] == dept_env["dept"]
    assert "DEPT_ADMIN" in claims["roles"]

    # refresh 签发的新令牌同样带部门
    r = await http_client.post("/api/v1/auth/refresh", cookies=resp.cookies)
    assert r.status_code == 200, r.text
    token2 = r.json()["data"]["access_token"]
    b64 = token2.split(".")[1]
    b64 += "=" * (-len(b64) % 4)
    assert json.loads(base64.urlsafe_b64decode(b64))["department"] == dept_env["dept"]
