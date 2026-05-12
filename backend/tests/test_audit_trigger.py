"""
审计触发器端到端验证：CREATE / UPDATE / 软删 / xref 均应自动产生 audit_log + change_history
"""
import pytest


async def _audit_logs(client, code: str):
    r = await client.get(
        f"/api/v1/substances/{code}/audit-logs",
        params={"page_size": 50, "include_children": True},
    )
    assert r.status_code == 200
    return r.json()["data"]


@pytest.mark.asyncio
async def test_create_writes_audit_log(admin_client, unique_suffix):
    code = (
        await admin_client.post(
            "/api/v1/substances",
            json={
                "substance_type": "mab",
                "internal_code": f"TEST-AUD-CR-{unique_suffix}",
                "preferred_name": "pytest audit create",
            },
        )
    ).json()["data"]["substance_code"]

    logs = await _audit_logs(admin_client, code)
    creates = [l for l in logs if l["entity_table"] == "substance" and l["action"] == "CREATE"]
    assert len(creates) == 1
    assert creates[0]["entity_code"] == code
    assert creates[0]["username"] == "admin"


@pytest.mark.asyncio
async def test_update_writes_change_history(admin_client, unique_suffix):
    code = (
        await admin_client.post(
            "/api/v1/substances",
            json={
                "substance_type": "mab",
                "internal_code": f"TEST-AUD-UP-{unique_suffix}",
                "preferred_name": "pytest audit update",
                "target": "HER2",
            },
        )
    ).json()["data"]["substance_code"]

    await admin_client.put(
        f"/api/v1/substances/{code}",
        json={"version": 1, "change_reason": "改靶点测试 audit", "target": "PD-L1"},
    )

    logs = await _audit_logs(admin_client, code)
    updates = [l for l in logs if l["entity_table"] == "substance" and l["action"] == "UPDATE"]
    assert len(updates) == 1
    assert updates[0]["reason"] == "改靶点测试 audit"

    target_change = next(
        (c for c in updates[0]["changes"] if c["field_name"] == "target"), None
    )
    assert target_change is not None
    assert target_change["old_value"] == "HER2"
    assert target_change["new_value"] == "PD-L1"

    # 触发器维护的 updated_at / version 不应进 change_history
    noise = [c for c in updates[0]["changes"] if c["field_name"] in ("updated_at", "version")]
    assert noise == []


@pytest.mark.asyncio
async def test_xref_lifecycle_audited(admin_client, unique_suffix):
    """xref 的 add/update/delete 三个动作都应产生独立审计记录"""
    code = (
        await admin_client.post(
            "/api/v1/substances",
            json={
                "substance_type": "mab",
                "internal_code": f"TEST-AUD-XR-{unique_suffix}",
                "preferred_name": "pytest audit xref",
            },
        )
    ).json()["data"]["substance_code"]

    xref_id = (
        await admin_client.post(
            f"/api/v1/substances/{code}/xrefs",
            json={"xref_type": "CAS", "xref_value": f"AUD-{unique_suffix}"},
        )
    ).json()["data"]["xref_id"]

    await admin_client.put(
        f"/api/v1/substances/{code}/xrefs/{xref_id}",
        json={"xref_value": f"AUD2-{unique_suffix}"},
    )
    await admin_client.delete(f"/api/v1/substances/{code}/xrefs/{xref_id}")

    logs = await _audit_logs(admin_client, code)
    xref_logs = [l for l in logs if l["entity_table"] == "substance_xref" and l["entity_id"] == xref_id]
    actions = sorted([l["action"] for l in xref_logs])
    assert actions == ["CREATE", "DELETE", "UPDATE"]


@pytest.mark.asyncio
async def test_audit_logs_endpoint_403_for_readonly(readonly_client, admin_client, unique_suffix):
    """readonly 无 audit:read 权限，应 403"""
    code = (
        await admin_client.post(
            "/api/v1/substances",
            json={
                "substance_type": "mab",
                "internal_code": f"TEST-AUD-403-{unique_suffix}",
                "preferred_name": "pytest audit 403",
            },
        )
    ).json()["data"]["substance_code"]

    r = await readonly_client.get(f"/api/v1/substances/{code}/audit-logs")
    assert r.status_code == 403
    assert r.json()["code"] == 40301
