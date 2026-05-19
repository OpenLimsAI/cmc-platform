"""
Material Batch 关键路径测试（M4.2）

对齐 DM-MDM-001 V1.1 §10.2 + API-MDM-001 V1.1 §5.1.6 / §8.2
"""
import pytest


async def _create_material(client, suffix, **overrides):
    payload = {
        "material_code": f"BT-{suffix[:8]}",
        "material_name": f"pytest batch host {suffix}",
        "material_type": "reagent",
    }
    payload.update(overrides)
    resp = await client.post("/api/v1/materials", json=payload)
    assert resp.status_code == 201, resp.text
    return resp.json()["data"]["material_code"]


@pytest.mark.asyncio
async def test_add_batch_default_in_stock(admin_client, unique_suffix):
    code = await _create_material(admin_client, unique_suffix)
    resp = await admin_client.post(
        f"/api/v1/materials/{code}/batches",
        json={
            "batch_number": f"B-{unique_suffix}-001",
            "quantity_value": "120.5000",
            "quantity_unit": "mg",
            "manufacture_date": "2026-01-15",
            "expiry_date": "2027-01-15",
            "receive_date": "2026-02-01",
            "storage_location": "FZ-001",
            "source_batch_ref": "CDMO-2025-998",
        },
    )
    assert resp.status_code == 201, resp.text
    b = resp.json()["data"]
    assert b["batch_number"] == f"B-{unique_suffix}-001"
    assert b["status"] == "in_stock"
    assert b["quantity_unit"] == "mg"
    assert b["expiry_date"] == "2027-01-15"


@pytest.mark.asyncio
async def test_list_batches_returns_all(admin_client, unique_suffix):
    code = await _create_material(admin_client, unique_suffix)
    for i in range(3):
        await admin_client.post(
            f"/api/v1/materials/{code}/batches",
            json={
                "batch_number": f"B-{unique_suffix}-{i:03d}",
                "quantity_value": "10",
                "quantity_unit": "g",
                "receive_date": f"2026-0{i + 1}-01",
            },
        )
    resp = await admin_client.get(f"/api/v1/materials/{code}/batches")
    assert resp.status_code == 200
    items = resp.json()["data"]
    assert len(items) == 3
    # 按 receive_date 倒序：最近的 i=2 在最前
    assert items[0]["batch_number"] == f"B-{unique_suffix}-002"


@pytest.mark.asyncio
async def test_duplicate_batch_number_rejected(admin_client, unique_suffix):
    """UNIQUE (material_id, batch_number) — 44001"""
    code = await _create_material(admin_client, unique_suffix)
    await admin_client.post(
        f"/api/v1/materials/{code}/batches",
        json={"batch_number": f"DUP-{unique_suffix}"},
    )
    resp = await admin_client.post(
        f"/api/v1/materials/{code}/batches",
        json={"batch_number": f"DUP-{unique_suffix}"},
    )
    assert resp.status_code == 409
    assert resp.json()["code"] == 44001


@pytest.mark.asyncio
async def test_update_batch_status_to_depleted(admin_client, unique_suffix):
    code = await _create_material(admin_client, unique_suffix)
    create = await admin_client.post(
        f"/api/v1/materials/{code}/batches",
        json={"batch_number": f"U-{unique_suffix}", "quantity_value": "5"},
    )
    bid = create.json()["data"]["batch_id"]

    resp = await admin_client.put(
        f"/api/v1/materials/{code}/batches/{bid}",
        json={
            "change_reason": "全部出库使用完毕",
            "status": "depleted",
            "quantity_value": "0",
        },
    )
    assert resp.status_code == 200, resp.text
    b = resp.json()["data"]
    assert b["status"] == "depleted"
    # Decimal round-trip 保留输入精度（"0" → "0"；"0.0000" → "0.0000"）
    assert b["quantity_value"] in {"0", "0.0000"}


@pytest.mark.asyncio
async def test_invalid_batch_status_rejected(admin_client, unique_suffix):
    code = await _create_material(admin_client, unique_suffix)
    create = await admin_client.post(
        f"/api/v1/materials/{code}/batches",
        json={"batch_number": f"BAD-{unique_suffix}"},
    )
    bid = create.json()["data"]["batch_id"]

    resp = await admin_client.put(
        f"/api/v1/materials/{code}/batches/{bid}",
        json={"status": "frozen"},  # 不在 5 值字典内
    )
    assert resp.status_code == 400  # V1.1 §4.1 validation_failed → 400


@pytest.mark.asyncio
async def test_delete_batch_soft(admin_client, unique_suffix):
    code = await _create_material(admin_client, unique_suffix)
    create = await admin_client.post(
        f"/api/v1/materials/{code}/batches",
        json={"batch_number": f"DEL-{unique_suffix}"},
    )
    bid = create.json()["data"]["batch_id"]

    del_resp = await admin_client.delete(
        f"/api/v1/materials/{code}/batches/{bid}",
        json={"change_reason": "pytest 误录入回收"},
    )
    assert del_resp.status_code == 204

    list_resp = await admin_client.get(f"/api/v1/materials/{code}/batches")
    items = list_resp.json()["data"]
    assert all(b["batch_id"] != bid for b in items)


@pytest.mark.asyncio
async def test_batch_rename_keeps_unique(admin_client, unique_suffix):
    """重命名批号时仍校验同物料唯一"""
    code = await _create_material(admin_client, unique_suffix)
    await admin_client.post(
        f"/api/v1/materials/{code}/batches",
        json={"batch_number": f"A-{unique_suffix}"},
    )
    other = await admin_client.post(
        f"/api/v1/materials/{code}/batches",
        json={"batch_number": f"B-{unique_suffix}"},
    )
    bid_b = other.json()["data"]["batch_id"]

    resp = await admin_client.put(
        f"/api/v1/materials/{code}/batches/{bid_b}",
        json={"batch_number": f"A-{unique_suffix}"},  # 与 A 重复
    )
    assert resp.status_code == 409
    assert resp.json()["code"] == 44001


@pytest.mark.asyncio
async def test_batch_audit_parent_ref(admin_client, unique_suffix):
    """audit trigger v2 第 3 参 parent_ref 回填 material_code（详情页审计 Tab）"""
    code = await _create_material(admin_client, unique_suffix)
    await admin_client.post(
        f"/api/v1/materials/{code}/batches",
        json={"batch_number": f"AUDIT-{unique_suffix}"},
    )
    logs = await admin_client.get(
        f"/api/v1/materials/{code}/audit-logs",
        params={"page_size": 50, "include_children": "true"},
    )
    items = logs.json()["data"]
    batch_logs = [it for it in items if it["entity_table"] == "material_batch"]
    assert batch_logs
    # parent_ref 触发器把 entity_code 回填成 material_code
    assert all(it["entity_code"] == code for it in batch_logs)
