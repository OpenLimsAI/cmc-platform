"""账号管理审计的成功路径、字段明细、秘密排除、并发与原子回滚。"""
import asyncio
import json
import os

import asyncpg
import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.orm import selectinload
from sqlalchemy.pool import NullPool

from tests.conftest import BASE_URL, pg_connect_kwargs


@pytest.fixture(autouse=True)
def isolated_database_only():
    assert os.getenv("TEST_DB") == "cmab_test", "只能经 run_tests.sh 在隔离库执行"


def user_payload(suffix):
    return {
        "username": f"aud_{suffix}", "email": f"aud_{suffix}@test.com",
        "password": "AuditUser@2026!", "full_name": "原姓名", "department": "审计测试部",
        "role_codes": ["READ_ONLY_USER"],
    }


def role_payload(suffix):
    return {
        "role_code": f"AUD_{suffix.upper()}", "role_name": "原角色名",
        "description": "审计回归", "permission_codes": ["substance:read"],
    }


async def create_user(client, suffix):
    payload = user_payload(suffix)
    response = await client.post("/api/v1/users", json=payload)
    assert response.status_code == 201, response.text
    return payload


async def db_rows(sql, *args):
    conn = await asyncpg.connect(**pg_connect_kwargs())
    try:
        return await conn.fetch(sql, *args)
    finally:
        await conn.close()


async def stored_logs(code, table="user"):
    rows = await db_rows(
        "SELECT row_to_json(a)::text AS log, "
        "(SELECT coalesce(jsonb_agg(to_jsonb(c) ORDER BY c.history_id), '[]')::text "
        "FROM audit.change_history c WHERE c.audit_log_id=a.log_id) AS changes "
        "FROM audit.audit_log a WHERE a.entity_schema='auth' AND a.entity_table=$1 "
        "AND a.entity_code=$2 ORDER BY a.log_id", table, code,
    )
    return [{**json.loads(r["log"]), "changes": json.loads(r["changes"])} for r in rows]


def changes(log):
    return {c["field_name"]: (c["old_value"], c["new_value"]) for c in log["changes"]}


@pytest.mark.asyncio
async def test_user_create_profile_and_noop_audit(admin_client, unique_suffix):
    p = await create_user(admin_client, unique_suffix)
    code = p["username"]
    logs = await stored_logs(code)
    assert len(logs) == 1 and logs[0]["action"] == "CREATE"
    assert logs[0]["username"] == "admin" and logs[0]["request_id"]
    assert changes(logs[0])["roles"] == (None, ["READ_ONLY_USER"])
    assert changes(logs[0])["full_name"] == (None, "原姓名")
    r = await admin_client.put(f"/api/v1/users/{code}", json={"full_name": "新姓名", "department": "新部门"})
    assert r.status_code == 200, r.text
    logs = await stored_logs(code)
    assert len(logs) == 2
    assert changes(logs[-1]) == {"full_name": ("原姓名", "新姓名"), "department": ("审计测试部", "新部门")}
    r = await admin_client.put(f"/api/v1/users/{code}", json={"full_name": "新姓名"})
    assert r.status_code == 200 and len(await stored_logs(code)) == 2
    r = await admin_client.get("/api/v1/audit-logs", params={"entity_code": code, "action": "UPDATE"})
    assert r.status_code == 200 and len(r.json()["data"][0]["changes"]) == 2
    r = await admin_client.post("/api/v1/audit-logs:export", params={"entity_code": code})
    assert r.status_code == 200 and "full_name: 原姓名→新姓名" in r.text


@pytest.mark.asyncio
async def test_role_lifecycle_permissions_and_noop_audit(admin_client, unique_suffix):
    p = role_payload(unique_suffix)
    code = p["role_code"]
    r = await admin_client.post("/api/v1/roles", json=p)
    assert r.status_code == 201, r.text
    assert changes((await stored_logs(code, "role"))[0])["permissions"] == (None, ["substance:read"])
    r = await admin_client.put(f"/api/v1/roles/{code}", json={"role_name": "新角色名"})
    assert r.status_code == 200, r.text
    r = await admin_client.put(f"/api/v1/roles/{code}", json={"permission_codes": ["project:read"]})
    assert r.status_code == 200, r.text
    r = await admin_client.put(f"/api/v1/roles/{code}", json={"permission_codes": ["project:read"]})
    assert r.status_code == 200
    assert len(await stored_logs(code, "role")) == 3
    r = await admin_client.delete(f"/api/v1/roles/{code}")
    assert r.status_code == 200, r.text
    logs = await stored_logs(code, "role")
    assert [x["action"] for x in logs] == ["CREATE", "UPDATE", "PERMISSION_CHANGE", "DELETE"]
    assert changes(logs[1])["role_name"] == ("原角色名", "新角色名")
    assert changes(logs[2])["permissions"] == (["substance:read"], ["project:read"])
    assert changes(logs[-1])["permissions"] == (["project:read"], [])
    assert changes(logs[-1])["deleted_at"][1] is not None
    assert logs[-1]["extra"]["role_before"]["role_name"] == "新角色名"
    assert logs[-1]["extra"]["role_before"]["permissions"] == ["project:read"]


@pytest.mark.asyncio
async def test_assignment_lock_unlock_keep_one_log_and_field_changes(admin_client, unique_suffix):
    p = await create_user(admin_client, unique_suffix)
    code = p["username"]
    r = await admin_client.put(f"/api/v1/users/{code}/roles", json={"role_codes": ["CMC_RESEARCHER"]})
    assert r.status_code == 200, r.text
    for action in ("lock", "unlock"):
        r = await admin_client.post(f"/api/v1/users/{code}:{action}")
        assert r.status_code == 200, r.text
    logs = await stored_logs(code)
    assert len(logs) == 4
    assert changes(logs[1])["roles"] == (["READ_ONLY_USER"], ["CMC_RESEARCHER"])
    assert logs[1]["extra"]["roles_before"] == ["READ_ONLY_USER"]
    assert changes(logs[2])["status"] == ("active", "locked")
    assert changes(logs[3])["status"] == ("locked", "active")


@pytest.mark.asyncio
async def test_password_events_exclude_all_secrets(admin_client, unique_suffix):
    p = await create_user(admin_client, unique_suffix)
    code = p["username"]
    r = await admin_client.post(f"/api/v1/users/{code}:reset-password")
    assert r.status_code == 200, r.text
    temporary = r.json()["data"]["temp_password"]
    logs = await stored_logs(code)
    assert len(logs) == 2 and logs[-1]["extra"]["operation"] == "reset_password"
    assert changes(logs[-1])["force_password_change"] == (False, True)
    hashes = [(await db_rows('SELECT password_hash FROM auth."user" WHERE username=$1', code))[0][0]]
    async with AsyncClient(base_url=BASE_URL, timeout=10) as client:
        login = await client.post("/api/v1/auth/login", json={"username": code, "password": temporary})
        assert login.status_code == 200, login.text
        token = login.json()["data"]["access_token"]
        refresh = client.cookies.get("cmab_refresh_token")
        r = await client.post("/api/v1/auth/change-password", headers={"Authorization": f"Bearer {token}"},
                              json={"old_password": temporary, "new_password": "ChangedAudit@2026!"})
        assert r.status_code == 200, r.text
    hashes.append((await db_rows('SELECT password_hash FROM auth."user" WHERE username=$1', code))[0][0])
    logs = await stored_logs(code)
    assert logs[-1]["username"] == code and logs[-1]["extra"]["operation"] == "change_password"
    assert changes(logs[-1])["force_password_change"] == (True, False)
    serialized = json.dumps(logs, ensure_ascii=False)
    for secret in [p["password"], temporary, "ChangedAudit@2026!", token, refresh, *hashes]:
        if secret:
            assert secret not in serialized
    assert all(not {"password", "password_hash", "temp_password", "access_token", "refresh_token"} & set(changes(log)) for log in logs)


@pytest.mark.asyncio
async def test_rejected_operations_do_not_write_success_audit(admin_client, readonly_client, unique_suffix):
    p = await create_user(admin_client, unique_suffix)
    code = p["username"]
    r = await readonly_client.put(f"/api/v1/users/{code}", json={"full_name": "越权修改"})
    assert r.status_code == 403
    r = await admin_client.post("/api/v1/users", json=p)
    assert r.status_code == 409
    r = await admin_client.put(f"/api/v1/users/{code}/roles", json={"role_codes": ["MISSING_AUDIT_ROLE"]})
    assert r.status_code == 400
    assert len(await stored_logs(code)) == 1


@pytest.mark.asyncio
async def test_login_returns_after_refresh_and_login_audit_are_committed(admin_client, unique_suffix):
    from app.core.config import settings
    from app.core.security import decode_token
    from app.domains.auth.services import AuthService

    p = await create_user(admin_client, unique_suffix)
    engine = create_async_engine(settings.DATABASE_URL, poolclass=NullPool)
    try:
        async with async_sessionmaker(engine, expire_on_commit=False)() as db:
            _, refresh, _ = await AuthService(db).login(p["username"], p["password"], None, None)
            jti = decode_token(refresh)["jti"]
            # 不执行依赖清理或 sleep；另一连接立即可读，才允许响应把通行证交给用户。
            tokens = await db_rows("SELECT count(*) FROM auth.refresh_token WHERE jti=$1", jti)
            assert tokens[0][0] == 1
            logs = await db_rows("SELECT count(*) FROM audit.audit_log WHERE username=$1 AND action='LOGIN'", p["username"])
            assert logs[0][0] == 1
    finally:
        await engine.dispose()


@pytest.mark.asyncio
@pytest.mark.parametrize("entity", ["user", "role"])
async def test_concurrent_changes_have_a_continuous_before_after_chain(admin_client, unique_suffix, entity):
    if entity == "user":
        p = await create_user(admin_client, unique_suffix)
        code, field, initial = p["username"], "full_name", "原姓名"
        path = f"/api/v1/users/{code}"
    else:
        p = role_payload(unique_suffix)
        assert (await admin_client.post("/api/v1/roles", json=p)).status_code == 201
        code, field, initial = p["role_code"], "role_name", "原角色名"
        path = f"/api/v1/roles/{code}"
    responses = await asyncio.gather(*(admin_client.put(path, json={field: value}) for value in ("并发甲", "并发乙")))
    assert [r.status_code for r in responses] == [200, 200]
    logs = await stored_logs(code, entity)
    assert len(logs) == 3
    assert changes(logs[1])[field][0] == initial
    assert changes(logs[2])[field][0] == changes(logs[1])[field][1]
    assert {changes(logs[1])[field][1], changes(logs[2])[field][1]} == {"并发甲", "并发乙"}


async def database_state(username, role_code):
    rows = await db_rows(
        'SELECT row_to_json(u)::text FROM auth."user" u WHERE username=$1', username,
    )
    roles = await db_rows('SELECT row_to_json(r)::text FROM auth.role r WHERE role_code=$1', role_code)
    links = await db_rows(
        'SELECT row_to_json(ur)::text FROM auth.user_role ur JOIN auth."user" u USING(user_id) '
        'WHERE u.username=$1 ORDER BY ur.role_id', username,
    )
    permissions = await db_rows(
        'SELECT row_to_json(rp)::text FROM auth.role_permission rp JOIN auth.role r USING(role_id) '
        'WHERE r.role_code=$1 ORDER BY rp.permission_id', role_code,
    )
    password_history = await db_rows(
        'SELECT row_to_json(h)::text FROM auth.password_history h JOIN auth."user" u USING(user_id) '
        'WHERE u.username=$1 ORDER BY h.history_id', username,
    )
    return (rows, roles, links, permissions, password_history, await stored_logs(username), await stored_logs(role_code, "role"))


@pytest.mark.asyncio
@pytest.mark.parametrize("operation", [
    "create_user", "update_user", "assign_roles", "lock_user", "unlock_user", "reset_password",
    "create_role", "update_role", "delete_role", "change_password",
])
async def test_audit_failure_rolls_back_business_and_audit(admin_client, unique_suffix, monkeypatch, operation):
    from app.core.config import settings
    from app.domains.auth import admin_role_service, admin_service, services
    from app.domains.auth.audit_service import record_auth_change
    from app.domains.auth.models import User
    from app.domains.auth.schemas import RoleCreate, RoleUpdate, UserCreate, UserUpdate

    p = await create_user(admin_client, unique_suffix)
    rp = role_payload(unique_suffix)
    assert (await admin_client.post("/api/v1/roles", json=rp)).status_code == 201
    if operation == "unlock_user":
        assert (await admin_client.post(f"/api/v1/users/{p['username']}:lock")).status_code == 200
    if operation == "create_user":
        p = user_payload(f"new{unique_suffix}")
    if operation == "create_role":
        rp = role_payload(f"new{unique_suffix}")
    baseline = await database_state(p["username"], rp["role_code"])

    async def failing_audit(db, *args, **kwargs):
        await record_auth_change(db, *args, **kwargs)
        await db.flush()  # 日志和字段明细也已写入未提交事务，验证它们一起回滚。
        raise RuntimeError("injected audit failure")

    for module in (admin_service, admin_role_service, services):
        monkeypatch.setattr(module, "record_auth_change", failing_audit)
    engine = create_async_engine(settings.DATABASE_URL, poolclass=NullPool)
    try:
        async with async_sessionmaker(engine, expire_on_commit=False)() as db:
            actor = (await db.execute(select(User).where(User.username == "admin").options(selectinload(User.roles)))).scalar_one()
            users = admin_service.UserAdminService(db)
            roles = admin_role_service.RoleAdminService(db)
            with pytest.raises(RuntimeError, match="injected audit failure"):
                if operation == "create_user":
                    await users.create_user(UserCreate(**p), actor)
                elif operation == "update_user":
                    await users.update_user(p["username"], UserUpdate(full_name="应回滚"), actor)
                elif operation == "assign_roles":
                    await users.assign_roles(p["username"], ["CMC_RESEARCHER"], actor)
                elif operation in {"lock_user", "unlock_user", "reset_password"}:
                    await getattr(users, operation)(p["username"], actor)
                elif operation == "create_role":
                    await roles.create_role(RoleCreate(**rp), actor)
                elif operation == "update_role":
                    await roles.update_role(rp["role_code"], RoleUpdate(role_name="应回滚", permission_codes=["project:read"]), actor)
                elif operation == "delete_role":
                    await roles.delete_role(rp["role_code"], actor)
                else:
                    target = (await db.execute(select(User).where(User.username == p["username"]).options(selectinload(User.roles)))).scalar_one()
                    await services.AuthService(db).change_password(target, p["password"], "RollbackAudit@2026!")
            await db.rollback()
        assert await database_state(p["username"], rp["role_code"]) == baseline
    finally:
        await engine.dispose()
