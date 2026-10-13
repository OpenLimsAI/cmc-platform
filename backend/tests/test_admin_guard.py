"""最后管理员保护：确定性的真实 HTTP 并发，所有数据仅在 cmab_test。"""
import asyncio
import os

import asyncpg
import pytest
import pytest_asyncio

from tests.conftest import pg_connect_kwargs
from tests.test_admin_users import _payload


@pytest.fixture(autouse=True)
def isolated_only():
    assert os.environ.get("TEST_DB") == "cmab_test"


async def sql(query, *args):
    conn = await asyncpg.connect(**pg_connect_kwargs())
    try:
        assert await conn.fetchval("SELECT current_database()") == "cmab_test"
        return await conn.fetch(query, *args)
    finally:
        await conn.close()


@pytest_asyncio.fixture
async def admins(admin_client, http_client, unique_suffix):
    role = "MG_" + unique_suffix.upper()
    r = await admin_client.post("/api/v1/roles", json={"role_code": role, "role_name": role,
                                                       "permission_codes": ["user:manage"]})
    assert r.status_code == 201
    manager = _payload("mg" + unique_suffix, role_codes=[role])
    assert (await admin_client.post("/api/v1/users", json=manager)).status_code == 201
    login = await http_client.post("/api/v1/auth/login", json={"username": manager["username"], "password": manager["password"]})
    headers = {"Authorization": "Bearer " + login.json()["data"]["access_token"]}
    targets = []
    for suffix in ("a", "b"):
        p = _payload(suffix + unique_suffix, role_codes=["SYS_ADMIN"])
        assert (await admin_client.post("/api/v1/users", json=p)).status_code == 201
        targets.append(p)
    old = await sql('SELECT user_id,status,locked_at FROM auth."user" u WHERE EXISTS '
                    '(SELECT 1 FROM auth.user_role ur JOIN auth.role r USING(role_id) '
                    'WHERE ur.user_id=u.user_id AND r.role_code=\'SYS_ADMIN\') '
                    'AND username<>ALL($1::text[])', [p["username"] for p in targets])
    try:
        await sql('UPDATE auth."user" SET status=\'locked\' WHERE user_id=ANY($1::bigint[])', [r["user_id"] for r in old])
        yield http_client, headers, targets
    finally:
        # 即使断言失败，也恢复已有种子账号；只清本 fixture 创建的管理员身份。
        for row in old:
            await sql('UPDATE auth."user" SET status=$1,locked_at=$2 WHERE user_id=$3', row["status"], row["locked_at"], row["user_id"])
        await sql('DELETE FROM auth.user_role WHERE user_id IN (SELECT user_id FROM auth."user" WHERE username=ANY($1::text[])) '
                  'AND role_id=(SELECT role_id FROM auth.role WHERE role_code=\'SYS_ADMIN\' AND deleted_at IS NULL)',
                  [p["username"] for p in targets])


async def active_admin_count():
    return (await sql('SELECT count(DISTINCT u.user_id) FROM auth."user" u '
                      'JOIN auth.user_role ur USING(user_id) JOIN auth.role r USING(role_id) '
                      'WHERE u.status=\'active\' AND u.deleted_at IS NULL AND r.role_code=\'SYS_ADMIN\''))[0][0]


@pytest.mark.parametrize("last_operation", ["role", "lock"])
async def test_protect_last_admin_operated_by_other_manager(admins, last_operation):
    client, headers, (a, b) = admins
    assert (await client.put(f'/api/v1/users/{b["username"]}/roles', headers=headers, json={"role_codes": []})).status_code == 200
    before = (await sql('SELECT count(*) FROM audit.audit_log WHERE entity_code=$1', a["username"]))[0][0]
    if last_operation == "role":
        r = await client.put(f'/api/v1/users/{a["username"]}/roles', headers=headers, json={"role_codes": []})
    else:
        r = await client.post(f'/api/v1/users/{a["username"]}:lock', headers=headers)
    assert r.status_code == 403 and r.json()["code"] == 40304
    assert await active_admin_count() == 1
    assert before == (await sql('SELECT count(*) FROM audit.audit_log WHERE entity_code=$1', a["username"]))[0][0]


@pytest.mark.parametrize("operations", [("role", "role"), ("lock", "lock"), ("role", "lock")])
async def test_concurrent_admin_reductions_never_remove_both(admins, operations):
    client, headers, targets = admins
    async def reduce(p, operation):
        if operation == "role":
            return await client.put(f'/api/v1/users/{p["username"]}/roles', headers=headers, json={"role_codes": []})
        return await client.post(f'/api/v1/users/{p["username"]}:lock', headers=headers)
    rs = await asyncio.gather(*(reduce(p, operation) for p, operation in zip(targets, operations, strict=True)))
    assert sorted(r.status_code for r in rs) == [200, 403]
    assert await active_admin_count() == 1


async def test_last_admin_can_still_be_security_locked_after_wrong_passwords(admins):
    client, headers, (a, b) = admins
    assert (await client.put(f'/api/v1/users/{b["username"]}/roles', headers=headers, json={"role_codes": []})).status_code == 200
    for _ in range(5):
        r = await client.post("/api/v1/auth/login", json={"username": a["username"], "password": "wrong_password"})
    assert r.status_code == 423
    assert await active_admin_count() == 0


async def test_self_removal_is_protected_and_expired_password_admin_still_counts(admins):
    client, headers, (a, b) = admins
    assert (await client.put(f'/api/v1/users/{b["username"]}/roles', headers=headers, json={"role_codes": []})).status_code == 200
    login = await client.post("/api/v1/auth/login", json={"username": a["username"], "password": a["password"]})
    self_headers = {"Authorization": "Bearer " + login.json()["data"]["access_token"]}
    r = await client.put(f'/api/v1/users/{a["username"]}/roles', headers=self_headers, json={"role_codes": []})
    assert r.status_code == 403 and r.json()["code"] == 40304
    r = await client.post(f'/api/v1/users/{a["username"]}:lock', headers=self_headers)
    assert r.status_code == 403 and r.json()["code"] == 40305
    await sql('UPDATE auth."user" SET password_expires_at=now()-interval \'1 day\' WHERE username=$1', a["username"])
    r = await client.post(f'/api/v1/users/{a["username"]}:lock', headers=headers)
    assert r.status_code == 403 and r.json()["code"] == 40304
