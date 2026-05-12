"""
Substance CRUD 关键路径测试
"""
import pytest


@pytest.mark.asyncio
async def test_create_substance_returns_code(admin_client, unique_suffix):
    resp = await admin_client.post(
        "/api/v1/substances",
        json={
            "substance_type": "mab",
            "internal_code": f"TEST-CRUD-{unique_suffix}",
            "preferred_name": f"pytest crud {unique_suffix}",
            "confidentiality": "internal",
        },
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["code"] == 0
    assert body["data"]["substance_code"].startswith("SUB-")
    assert body["data"]["status"] == "draft"
    assert body["data"]["version"] == 1


@pytest.mark.asyncio
async def test_get_substance_after_create(admin_client, unique_suffix):
    create_resp = await admin_client.post(
        "/api/v1/substances",
        json={
            "substance_type": "small_molecule",
            "internal_code": f"TEST-GET-{unique_suffix}",
            "preferred_name": "pytest get",
        },
    )
    code = create_resp.json()["data"]["substance_code"]

    get_resp = await admin_client.get(f"/api/v1/substances/{code}")
    assert get_resp.status_code == 200
    data = get_resp.json()["data"]
    assert data["substance_code"] == code
    assert data["internal_code"] == f"TEST-GET-{unique_suffix}"
    assert data["substance_type"] == "small_molecule"


@pytest.mark.asyncio
async def test_update_increments_version_exactly_one(admin_client, unique_suffix):
    """核心防回归：触发器自增 version，service 层不再 +=1，否则会变 +2"""
    code = (
        await admin_client.post(
            "/api/v1/substances",
            json={
                "substance_type": "mab",
                "internal_code": f"TEST-VER-{unique_suffix}",
                "preferred_name": "pytest version",
            },
        )
    ).json()["data"]["substance_code"]

    resp = await admin_client.put(
        f"/api/v1/substances/{code}",
        json={"version": 1, "change_reason": "测试 version 自增", "target": "PD-L1"},
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["data"]["version"] == 2
    assert resp.json()["data"]["target"] == "PD-L1"


@pytest.mark.asyncio
async def test_optimistic_lock_conflict(admin_client, unique_suffix):
    code = (
        await admin_client.post(
            "/api/v1/substances",
            json={
                "substance_type": "mab",
                "internal_code": f"TEST-LOCK-{unique_suffix}",
                "preferred_name": "pytest lock",
            },
        )
    ).json()["data"]["substance_code"]

    resp = await admin_client.put(
        f"/api/v1/substances/{code}",
        json={"version": 99, "target": "should-fail"},
    )
    assert resp.status_code == 409
    assert resp.json()["code"] == 40904
    assert resp.json()["meta"]["error"]["type"] == "version_conflict"


@pytest.mark.asyncio
async def test_duplicate_internal_code_rejected(admin_client, unique_suffix):
    ic = f"TEST-DUP-{unique_suffix}"
    await admin_client.post(
        "/api/v1/substances",
        json={"substance_type": "mab", "internal_code": ic, "preferred_name": "first"},
    )
    resp = await admin_client.post(
        "/api/v1/substances",
        json={"substance_type": "mab", "internal_code": ic, "preferred_name": "second"},
    )
    assert resp.status_code == 409
    assert resp.json()["code"] == 40902


@pytest.mark.asyncio
async def test_soft_delete_excludes_from_list(admin_client, unique_suffix):
    code = (
        await admin_client.post(
            "/api/v1/substances",
            json={
                "substance_type": "mab",
                "internal_code": f"TEST-DEL-{unique_suffix}",
                "preferred_name": f"pytest delete {unique_suffix}",
            },
        )
    ).json()["data"]["substance_code"]

    del_resp = await admin_client.delete(
        f"/api/v1/substances/{code}",
        json={"change_reason": "pytest 软删除回归测试"},
    )
    assert del_resp.status_code == 204

    # 软删后 GET 应 404
    get_resp = await admin_client.get(f"/api/v1/substances/{code}")
    assert get_resp.status_code == 404

    # 列表过滤也不应该出现
    list_resp = await admin_client.get(
        "/api/v1/substances", params={"q": unique_suffix}
    )
    items = list_resp.json()["data"]
    assert all(it["substance_code"] != code for it in items)


@pytest.mark.asyncio
async def test_soft_delete_requires_reason(admin_client, unique_suffix):
    """M2.0：DELETE 必须带 change_reason body（21 CFR Part 11 §11.10）"""
    code = (
        await admin_client.post(
            "/api/v1/substances",
            json={
                "substance_type": "mab",
                "internal_code": f"TEST-DEL-RSN-{unique_suffix}",
                "preferred_name": f"pytest delete reason {unique_suffix}",
            },
        )
    ).json()["data"]["substance_code"]

    # 缺 body
    resp = await admin_client.delete(f"/api/v1/substances/{code}")
    assert resp.status_code == 422

    # reason 太短（min_length=5）
    resp = await admin_client.delete(
        f"/api/v1/substances/{code}",
        json={"change_reason": "no"},
    )
    assert resp.status_code == 422

    # 合法 reason
    resp = await admin_client.delete(
        f"/api/v1/substances/{code}",
        json={"change_reason": "符合长度要求的理由"},
    )
    assert resp.status_code == 204
