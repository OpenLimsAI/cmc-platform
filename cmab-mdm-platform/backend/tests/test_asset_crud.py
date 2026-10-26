"""
Asset CRUD 关键路径测试（M3.1）

对齐 DM-MDM-001 V1.0 §8.2
"""
import pytest


@pytest.mark.asyncio
async def test_create_asset_returns_code(admin_client, unique_suffix):
    resp = await admin_client.post(
        "/api/v1/assets",
        json={
            "internal_name": f"pytest asset {unique_suffix}",
            "asset_type": "mab",
            "current_phase": "phase_2",
            "therapeutic_area": "Oncology",
        },
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["code"] == 0
    assert body["data"]["asset_code"].startswith("AST-")
    assert body["data"]["status"] == "active"  # §8.2 默认值
    assert body["data"]["current_phase"] == "phase_2"
    assert body["data"]["version"] == 1


@pytest.mark.asyncio
async def test_get_asset_after_create(admin_client, unique_suffix):
    create = await admin_client.post(
        "/api/v1/assets",
        json={
            "internal_name": f"pytest get asset {unique_suffix}",
            "asset_type": "adc",
            "trade_name": "DemoMab",
            "inn_name": "demomabavidin",
        },
    )
    code = create.json()["data"]["asset_code"]
    detail = await admin_client.get(f"/api/v1/assets/{code}")
    assert detail.status_code == 200
    data = detail.json()["data"]
    assert data["asset_code"] == code
    assert data["asset_type"] == "adc"
    assert data["trade_name"] == "DemoMab"
    assert data["inn_name"] == "demomabavidin"


@pytest.mark.asyncio
async def test_list_assets_filters(admin_client, unique_suffix):
    for t in ["mab", "adc", "small_molecule"]:
        await admin_client.post(
            "/api/v1/assets",
            json={
                "internal_name": f"pytest list {unique_suffix} {t}",
                "asset_type": t,
            },
        )

    resp = await admin_client.get(
        "/api/v1/assets", params={"q": unique_suffix, "page_size": 50}
    )
    items = resp.json()["data"]
    assert sum(1 for it in items if unique_suffix in it["internal_name"]) == 3

    mab_only = await admin_client.get(
        "/api/v1/assets",
        params={"q": unique_suffix, "asset_type": "mab", "page_size": 50},
    )
    matched = [
        it for it in mab_only.json()["data"]
        if unique_suffix in it["internal_name"]
    ]
    assert len(matched) == 1
    assert matched[0]["asset_type"] == "mab"


@pytest.mark.asyncio
async def test_update_asset_version_and_phase_change(admin_client, unique_suffix):
    """触发器：version+1；current_phase 变化时记 phase_change_at"""
    code = (
        await admin_client.post(
            "/api/v1/assets",
            json={
                "internal_name": f"pytest version {unique_suffix}",
                "asset_type": "mab",
                "current_phase": "phase_1",
            },
        )
    ).json()["data"]["asset_code"]

    resp = await admin_client.put(
        f"/api/v1/assets/{code}",
        json={
            "version": 1,
            "change_reason": "推进到 Ph2",
            "current_phase": "phase_2",
        },
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    assert data["version"] == 2
    assert data["current_phase"] == "phase_2"
    assert data["phase_change_at"] is not None


@pytest.mark.asyncio
async def test_update_asset_optimistic_lock(admin_client, unique_suffix):
    code = (
        await admin_client.post(
            "/api/v1/assets",
            json={
                "internal_name": f"pytest lock {unique_suffix}",
                "asset_type": "mab",
            },
        )
    ).json()["data"]["asset_code"]

    resp = await admin_client.put(
        f"/api/v1/assets/{code}",
        json={"version": 99, "trade_name": "should-fail"},
    )
    assert resp.status_code == 409
    assert resp.json()["code"] == 40904


@pytest.mark.asyncio
async def test_invalid_asset_type_rejected(admin_client, unique_suffix):
    resp = await admin_client.post(
        "/api/v1/assets",
        json={
            "internal_name": f"pytest invalid {unique_suffix}",
            "asset_type": "invented",
        },
    )
    # V1.1 §4.1：40001 validation_failed → HTTP 400
    assert resp.status_code == 400
    assert resp.json()["code"] == 40001


@pytest.mark.asyncio
async def test_invalid_phase_rejected_by_check(admin_client, unique_suffix):
    """Pydantic 在 schema 层先拦下；如绕过 schema DB CHECK 也兜底"""
    resp = await admin_client.post(
        "/api/v1/assets",
        json={
            "internal_name": f"pytest bad phase {unique_suffix}",
            "asset_type": "mab",
            "current_phase": "not-a-phase",
        },
    )
    assert resp.status_code == 400
    assert resp.json()["code"] == 40001


@pytest.mark.asyncio
async def test_soft_delete_excludes_from_list(admin_client, unique_suffix):
    code = (
        await admin_client.post(
            "/api/v1/assets",
            json={
                "internal_name": f"pytest delete {unique_suffix}",
                "asset_type": "mab",
            },
        )
    ).json()["data"]["asset_code"]

    del_resp = await admin_client.delete(
        f"/api/v1/assets/{code}",
        json={"change_reason": "pytest 软删除"},
    )
    assert del_resp.status_code == 204

    get_resp = await admin_client.get(f"/api/v1/assets/{code}")
    assert get_resp.status_code == 404

    list_resp = await admin_client.get("/api/v1/assets", params={"q": unique_suffix})
    items = list_resp.json()["data"]
    assert all(it["asset_code"] != code for it in items)


@pytest.mark.asyncio
async def test_soft_delete_requires_reason(admin_client, unique_suffix):
    code = (
        await admin_client.post(
            "/api/v1/assets",
            json={
                "internal_name": f"pytest del reason {unique_suffix}",
                "asset_type": "mab",
            },
        )
    ).json()["data"]["asset_code"]

    resp = await admin_client.delete(f"/api/v1/assets/{code}")
    assert resp.status_code == 400  # V1.1 §4.1 validation_failed → 400


@pytest.mark.asyncio
async def test_asset_audit_log_entity_code(admin_client, unique_suffix):
    """audit trigger v2：entity_code = asset_code"""
    code = (
        await admin_client.post(
            "/api/v1/assets",
            json={
                "internal_name": f"pytest audit {unique_suffix}",
                "asset_type": "mab",
            },
        )
    ).json()["data"]["asset_code"]

    logs = await admin_client.get(
        f"/api/v1/assets/{code}/audit-logs", params={"page_size": 20}
    )
    items = logs.json()["data"]
    create_logs = [it for it in items if it["action"] == "CREATE"]
    assert create_logs
    assert all(it["entity_code"] == code for it in create_logs)


@pytest.mark.asyncio
async def test_readonly_cannot_create_asset(readonly_client, unique_suffix):
    """READ_ONLY_USER 缺 asset:create"""
    resp = await readonly_client.post(
        "/api/v1/assets",
        json={
            "internal_name": f"pytest forbidden {unique_suffix}",
            "asset_type": "mab",
        },
    )
    assert resp.status_code == 403
