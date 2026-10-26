"""
Material Batch 关键路径测试（M4.2）

对齐 DM-MDM-001 V1.1 §10.2 + API-MDM-001 V1.1 §5.1.6 / §8.2
"""
import asyncio
import json
import os

import asyncpg
import pytest

from tests.conftest import pg_connect_kwargs


@pytest.fixture(autouse=True)
def isolated_batch_database_only():
    assert os.getenv("TEST_DB") == "cmab_test", "只能经 run_tests.sh 在隔离库执行"


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


async def _batch(client, code, number):
    r = await client.post(f"/api/v1/materials/{code}/batches", json={"batch_number": number})
    assert r.status_code == 201, r.text
    return r.json()["data"]["batch_id"]


async def _remove_batch(client, code, bid):
    r = await client.delete(f"/api/v1/materials/{code}/batches/{bid}", json={"change_reason": "误录入作废，历史保留"})
    assert r.status_code == 204, r.text


async def _stored_batches(code):
    kwargs = pg_connect_kwargs()
    assert kwargs["database"] == "cmab_test"
    conn = await asyncpg.connect(**kwargs)
    try:
        rows = await conn.fetch(
            'SELECT b.batch_id, b.batch_number, b.deleted_at FROM mm.material_batch b '
            'JOIN mm.material m USING(material_id) WHERE m.material_code=$1 ORDER BY b.batch_id', code,
        )
        return [dict(row) for row in rows]
    finally:
        await conn.close()


@pytest.mark.asyncio
async def test_deleted_batch_number_can_be_recreated_with_history(admin_client, unique_suffix):
    code = await _create_material(admin_client, unique_suffix)
    number = f"REUSE-{unique_suffix}"
    old_id = await _batch(admin_client, code, number)
    await _remove_batch(admin_client, code, old_id)
    new_id = await _batch(admin_client, code, number)
    assert new_id != old_id
    rows = await _stored_batches(code)
    assert [b["batch_id"] for b in rows] == [old_id, new_id]
    assert rows[0]["deleted_at"] is not None and rows[1]["deleted_at"] is None
    r = await admin_client.get(f"/api/v1/materials/{code}/batches")
    assert [b["batch_id"] for b in r.json()["data"]] == [new_id]
    r = await admin_client.get(f"/api/v1/materials/{code}/audit-logs", params={"page_size": 100})
    logs = [x for x in r.json()["data"] if x["entity_table"] == "material_batch"]
    assert {(x["entity_id"], x["action"]) for x in logs} >= {(old_id, "CREATE"), (old_id, "DELETE"), (new_id, "CREATE")}


@pytest.mark.asyncio
async def test_rename_can_reuse_deleted_number_but_still_rejects_active_duplicate(admin_client, unique_suffix):
    code = await _create_material(admin_client, unique_suffix)
    old = await _batch(admin_client, code, "RENAME-OLD")
    other = await _batch(admin_client, code, "RENAME-OTHER")
    await _remove_batch(admin_client, code, old)
    r = await admin_client.put(f"/api/v1/materials/{code}/batches/{other}", json={"batch_number": "RENAME-OLD", "change_reason": "改正录入批号"})
    assert r.status_code == 200, r.text
    r = await admin_client.post(f"/api/v1/materials/{code}/batches", json={"batch_number": "RENAME-OLD"})
    assert r.status_code == 409 and r.json()["code"] == 44001
    rows = await _stored_batches(code)
    assert len(rows) == 2 and all(x["batch_number"] == "RENAME-OLD" for x in rows)


@pytest.mark.asyncio
async def test_different_materials_can_share_batch_number(admin_client, unique_suffix):
    a = await _create_material(admin_client, unique_suffix)
    b = await _create_material(admin_client, unique_suffix, material_code=f"BTX-{unique_suffix[:8]}")
    assert await _batch(admin_client, a, "SHARED-NUMBER") != await _batch(admin_client, b, "SHARED-NUMBER")


@pytest.mark.asyncio
async def test_repeated_delete_recreate_keeps_every_identity(admin_client, unique_suffix):
    code = await _create_material(admin_client, unique_suffix)
    identities = []
    for _ in range(3):
        bid = await _batch(admin_client, code, "REPEATED-NUMBER")
        identities.append(bid)
        await _remove_batch(admin_client, code, bid)
    identities.append(await _batch(admin_client, code, "REPEATED-NUMBER"))
    rows = await _stored_batches(code)
    assert len(set(identities)) == 4 and [r["batch_id"] for r in rows] == identities
    assert sum(r["deleted_at"] is None for r in rows) == 1


@pytest.mark.asyncio
@pytest.mark.parametrize("operation", ["create", "rename"])
async def test_concurrent_duplicate_batch_writes_return_one_conflict(admin_client, unique_suffix, operation):
    code = await _create_material(admin_client, unique_suffix)
    path = f"/api/v1/materials/{code}/batches"
    if operation == "create":
        requests = [admin_client.post(path, json={"batch_number": "CONCURRENT"}) for _ in range(2)]
    else:
        ids = [await _batch(admin_client, code, number) for number in ("ORIGINAL-A", "ORIGINAL-B")]
        requests = [admin_client.put(f"{path}/{bid}", json={"batch_number": "CONCURRENT", "change_reason": "并发改号验证"}) for bid in ids]
    responses = await asyncio.gather(*requests)
    assert sorted(r.status_code for r in responses) == ([201, 409] if operation == "create" else [200, 409])
    assert next(r for r in responses if r.status_code == 409).json()["code"] == 44001
    rows = await _stored_batches(code)
    assert sum(r["batch_number"] == "CONCURRENT" and r["deleted_at"] is None for r in rows) == 1


@pytest.mark.asyncio
async def test_migration_refuses_downgrade_after_reuse_without_changing_data(admin_client, unique_suffix):
    from pathlib import Path
    from runpy import run_path

    from alembic.operations import Operations
    from alembic.runtime.migration import MigrationContext
    from app.core.config import settings
    from sqlalchemy import create_engine, text

    code = await _create_material(admin_client, unique_suffix)
    old = await _batch(admin_client, code, "DOWNGRADE-REUSE")
    await _remove_batch(admin_client, code, old)
    await _batch(admin_client, code, "DOWNGRADE-REUSE")
    migration = run_path(str(Path(__file__).parents[1] / "alembic/versions/2026_10_13_0100_0063_mm_batch_partial_unique.py"))
    engine = create_engine(settings.DATABASE_URL_SYNC)
    assert engine.url.database == "cmab_test"
    try:
        with engine.connect() as connection, connection.begin():
            before = connection.execute(text("SELECT row_to_json(b)::text FROM mm.material_batch b ORDER BY batch_id")).scalars().all()
            with Operations.context(MigrationContext.configure(connection)), pytest.raises(RuntimeError, match="拒绝恢复全表唯一约束"):
                migration["downgrade"]()
            after = connection.execute(text("SELECT row_to_json(b)::text FROM mm.material_batch b ORDER BY batch_id")).scalars().all()
            assert after == before
            assert connection.execute(text("SELECT to_regclass('mm.uq_material_batch_active') IS NOT NULL")).scalar_one()
    finally:
        engine.dispose()


@pytest.mark.asyncio
async def test_migration_clean_downgrade_and_upgrade_preserve_sample(admin_client, unique_suffix):
    from pathlib import Path
    from runpy import run_path

    from alembic.operations import Operations
    from alembic.runtime.migration import MigrationContext
    from app.core.config import settings
    from sqlalchemy import create_engine, text

    code = await _create_material(admin_client, unique_suffix)
    bid = await _batch(admin_client, code, "DOWNGRADE-UNIQUE")
    migration = run_path(str(Path(__file__).parents[1] / "alembic/versions/2026_10_13_0100_0063_mm_batch_partial_unique.py"))
    engine = create_engine(settings.DATABASE_URL_SYNC)
    assert engine.url.database == "cmab_test"
    try:
        with engine.connect() as connection:
            transaction = connection.begin()
            try:
                # 只在隔离库未提交事务中排除其他用例的复用样本；finally 恢复全部。
                connection.execute(text("LOCK TABLE mm.material_batch IN ACCESS EXCLUSIVE MODE"))
                connection.execute(text("DELETE FROM mm.material_batch WHERE batch_id != :id"), {"id": bid})
                before = connection.execute(text("SELECT row_to_json(b)::text FROM mm.material_batch b WHERE batch_id=:id"), {"id": bid}).scalar_one()
                with Operations.context(MigrationContext.configure(connection)):
                    migration["downgrade"]()
                    constraint = connection.execute(text("SELECT count(*) FROM pg_constraint WHERE conrelid='mm.material_batch'::regclass AND conname='uq_material_batch'")).scalar_one()
                    assert constraint == 1
                    migration["upgrade"]()
                after = connection.execute(text("SELECT row_to_json(b)::text FROM mm.material_batch b WHERE batch_id=:id"), {"id": bid}).scalar_one()
                assert json.loads(after) == json.loads(before)
                assert connection.execute(text("SELECT to_regclass('mm.uq_material_batch_active') IS NOT NULL")).scalar_one()
            finally:
                transaction.rollback()
    finally:
        engine.dispose()
