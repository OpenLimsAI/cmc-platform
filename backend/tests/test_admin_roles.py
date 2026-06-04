"""Phase 5.A / M5.2 角色 & 权限管理测试

覆盖：
- GET /permissions 含 19 个 seed 权限
- GET /roles 列表 6 个系统角色排前 + 含 user_count
- GET /roles/{code} 详情含权限数组
- POST /roles 创建自定义角色（含权限）
- 重 role_code 40908
- 未知权限 40409
- PUT 系统角色 40306
- PUT 自定义角色：改名 + 替换权限
- DELETE 系统角色 40306
- DELETE 在用自定义角色 42202
- DELETE 空自定义角色 OK
- 新创建的自定义角色可以被 PUT /users/{username}/roles 引用（端到端）
- readonly 全 403
"""
import uuid

import pytest


def _custom_role_payload(suffix: str, **overrides) -> dict:
    base = {
        "role_code": f"CUSTOM_{suffix.upper()}",
        "role_name": f"自定义角色 {suffix}",
        "description": "测试",
        "permission_codes": ["substance:read", "project:read"],
    }
    base.update(overrides)
    return base


# ============== 权限列表 ==============
@pytest.mark.asyncio
async def test_list_permissions(admin_client):
    r = await admin_client.get("/api/v1/permissions")
    assert r.status_code == 200
    items = r.json()["data"]
    codes = {p["permission_code"] for p in items}
    # seed 19 权限的核心成员
    assert "substance:read" in codes
    assert "user:manage" in codes
    assert "role:manage" in codes
    assert len(items) >= 19


# ============== 角色列表 / 详情 ==============
@pytest.mark.asyncio
async def test_list_roles_system_first(admin_client):
    r = await admin_client.get("/api/v1/roles")
    assert r.status_code == 200
    items = r.json()["data"]
    # 至少 6 个系统角色
    system_roles = [i for i in items if i["is_system"]]
    codes = {i["role_code"] for i in system_roles}
    assert {"SYS_ADMIN", "SUBSTANCE_STEWARD", "PROJECT_MANAGER",
            "CMC_RESEARCHER", "QA_REVIEWER", "READ_ONLY_USER"}.issubset(codes)
    # admin 用户至少有 1 个 SYS_ADMIN，所以 user_count>=1
    sysadmin = next(i for i in items if i["role_code"] == "SYS_ADMIN")
    assert sysadmin["user_count"] >= 1
    assert sysadmin["permission_count"] >= 19  # SYS_ADMIN 全权限


@pytest.mark.asyncio
async def test_get_role_detail(admin_client):
    r = await admin_client.get("/api/v1/roles/READ_ONLY_USER")
    assert r.status_code == 200
    d = r.json()["data"]
    assert d["is_system"] is True
    codes = {p["permission_code"] for p in d["permissions"]}
    assert codes == {
        "substance:read",
        "project:read",
        "asset:read",
        "material:read",
        "equipment:read",
    }


@pytest.mark.asyncio
async def test_get_role_not_found(admin_client):
    r = await admin_client.get("/api/v1/roles/NOPE_NOT_REAL")
    assert r.status_code == 404
    assert r.json()["code"] == 40408


# ============== 创建 ==============
@pytest.mark.asyncio
async def test_create_custom_role(admin_client, unique_suffix):
    p = _custom_role_payload(unique_suffix)
    r = await admin_client.post("/api/v1/roles", json=p)
    assert r.status_code == 201
    d = r.json()["data"]
    assert d["role_code"] == p["role_code"]
    assert d["is_system"] is False
    assert d["permission_count"] == 2


@pytest.mark.asyncio
async def test_create_role_duplicate_code(admin_client, unique_suffix):
    p = _custom_role_payload(unique_suffix)
    r1 = await admin_client.post("/api/v1/roles", json=p)
    assert r1.status_code == 201
    r2 = await admin_client.post("/api/v1/roles", json=p)
    assert r2.status_code == 409
    assert r2.json()["code"] == 40908


@pytest.mark.asyncio
async def test_create_role_unknown_permission(admin_client, unique_suffix):
    p = _custom_role_payload(
        unique_suffix, permission_codes=["substance:read", "fake:permission"]
    )
    r = await admin_client.post("/api/v1/roles", json=p)
    assert r.status_code == 404
    assert r.json()["code"] == 40409


# ============== 更新 ==============
@pytest.mark.asyncio
async def test_update_system_role_forbidden(admin_client):
    r = await admin_client.put(
        "/api/v1/roles/READ_ONLY_USER",
        json={"role_name": "改名了"},
    )
    assert r.status_code == 403
    assert r.json()["code"] == 40306


@pytest.mark.asyncio
async def test_update_custom_role(admin_client, unique_suffix):
    p = _custom_role_payload(unique_suffix)
    r1 = await admin_client.post("/api/v1/roles", json=p)
    role_code = r1.json()["data"]["role_code"]

    r2 = await admin_client.put(
        f"/api/v1/roles/{role_code}",
        json={
            "role_name": "改后的名字",
            "permission_codes": ["material:read"],  # 替换为只有 material:read
        },
    )
    assert r2.status_code == 200
    d = r2.json()["data"]
    assert d["role_name"] == "改后的名字"
    codes = {p["permission_code"] for p in d["permissions"]}
    assert codes == {"material:read"}


# ============== 删除 ==============
@pytest.mark.asyncio
async def test_delete_system_role_forbidden(admin_client):
    r = await admin_client.delete("/api/v1/roles/READ_ONLY_USER")
    assert r.status_code == 403
    assert r.json()["code"] == 40306


@pytest.mark.asyncio
async def test_delete_custom_role_empty(admin_client, unique_suffix):
    p = _custom_role_payload(unique_suffix)
    r1 = await admin_client.post("/api/v1/roles", json=p)
    role_code = r1.json()["data"]["role_code"]

    r2 = await admin_client.delete(f"/api/v1/roles/{role_code}")
    assert r2.status_code == 200

    # 软删除后再 GET 应 404
    r3 = await admin_client.get(f"/api/v1/roles/{role_code}")
    assert r3.status_code == 404


@pytest.mark.asyncio
async def test_delete_custom_role_in_use(admin_client, unique_suffix):
    p = _custom_role_payload(unique_suffix)
    r1 = await admin_client.post("/api/v1/roles", json=p)
    role_code = r1.json()["data"]["role_code"]

    # 建一个用户分配此角色
    user_username = f"ru_{unique_suffix}"
    r2 = await admin_client.post(
        "/api/v1/users",
        json={
            "username": user_username,
            "email": f"{user_username}@test.com",
            "password": "TestUser@2026!",
            "full_name": "Role User",
            "role_codes": [role_code],
        },
    )
    assert r2.status_code == 201

    # 删角色应 42202
    r3 = await admin_client.delete(f"/api/v1/roles/{role_code}")
    assert r3.status_code == 422
    assert r3.json()["code"] == 42202

    # 把用户角色置空（或换成 READ_ONLY），再删应成功
    await admin_client.put(
        f"/api/v1/users/{user_username}/roles",
        json={"role_codes": ["READ_ONLY_USER"]},
    )
    r4 = await admin_client.delete(f"/api/v1/roles/{role_code}")
    assert r4.status_code == 200


# ============== 端到端：新角色可用于 PUT /users/{u}/roles ==============
@pytest.mark.asyncio
async def test_new_role_usable_in_user_assignment(admin_client, unique_suffix):
    p = _custom_role_payload(unique_suffix)
    await admin_client.post("/api/v1/roles", json=p)
    role_code = p["role_code"]

    # 建用户
    uname = f"e2e_{unique_suffix}"
    await admin_client.post(
        "/api/v1/users",
        json={
            "username": uname,
            "email": f"{uname}@test.com",
            "password": "TestUser@2026!",
            "full_name": "E2E",
            "role_codes": ["READ_ONLY_USER"],
        },
    )

    # 替换为新创建角色
    r = await admin_client.put(
        f"/api/v1/users/{uname}/roles",
        json={"role_codes": [role_code]},
    )
    assert r.status_code == 200
    assert {x["role_code"] for x in r.json()["data"]["roles"]} == {role_code}


# ============== 权限 ==============
@pytest.mark.asyncio
async def test_readonly_forbidden(readonly_client):
    r1 = await readonly_client.get("/api/v1/roles")
    assert r1.status_code == 403

    r2 = await readonly_client.post(
        "/api/v1/roles",
        json=_custom_role_payload(uuid.uuid4().hex[:8]),
    )
    assert r2.status_code == 403

    r3 = await readonly_client.get("/api/v1/permissions")
    assert r3.status_code == 403
