"""
Idempotency-Key 测试（V1.1 API §3.4 + API7）

实现路径：app/shared/idempotency.py + 4 个 POST 创建端点接入
覆盖：material / substance（同 key + body 一致 / 不一致 / 无 key 不走幂等）
"""
import uuid

import pytest


@pytest.mark.asyncio
async def test_material_idem_same_key_same_body_returns_cached(
    admin_client, unique_suffix
):
    key = str(uuid.uuid4())
    body = {
        "material_name": f"idem mat {unique_suffix}",
        "material_type": "candidate",
    }
    r1 = await admin_client.post(
        "/api/v1/materials",
        json=body,
        headers={"Idempotency-Key": key},
    )
    assert r1.status_code == 201
    code1 = r1.json()["data"]["material_code"]

    # 第二次调用：返回同一物料（缓存）
    r2 = await admin_client.post(
        "/api/v1/materials",
        json=body,
        headers={"Idempotency-Key": key},
    )
    assert r2.status_code == 201
    code2 = r2.json()["data"]["material_code"]
    assert code1 == code2  # 没创建第二份


@pytest.mark.asyncio
async def test_material_idem_same_key_different_body_409(admin_client, unique_suffix):
    """API §3.4：同 key 不同 body → 40905 duplicate_request"""
    key = str(uuid.uuid4())
    body1 = {
        "material_name": f"idem orig {unique_suffix}",
        "material_type": "candidate",
    }
    body2 = {
        "material_name": f"idem changed {unique_suffix}",
        "material_type": "reference",
    }
    r1 = await admin_client.post(
        "/api/v1/materials", json=body1,
        headers={"Idempotency-Key": key},
    )
    assert r1.status_code == 201

    r2 = await admin_client.post(
        "/api/v1/materials", json=body2,
        headers={"Idempotency-Key": key},
    )
    assert r2.status_code == 409
    assert r2.json()["code"] == 40905
    assert r2.json()["meta"]["error"]["type"] == "duplicate_request"


@pytest.mark.asyncio
async def test_material_idem_no_key_normal_path(admin_client, unique_suffix):
    """无 Idempotency-Key header → 端点照常工作（不走幂等检查）"""
    body = {
        "material_name": f"no key {unique_suffix}",
        "material_type": "buffer",
    }
    r1 = await admin_client.post("/api/v1/materials", json=body)
    assert r1.status_code == 201
    code1 = r1.json()["data"]["material_code"]

    r2 = await admin_client.post("/api/v1/materials", json=body)
    assert r2.status_code == 201
    code2 = r2.json()["data"]["material_code"]
    # 没幂等键，每次都是新记录
    assert code1 != code2


@pytest.mark.asyncio
async def test_material_idem_invalid_key_400(admin_client, unique_suffix):
    """Idempotency-Key 必须是合法 UUID（防 key 注入）"""
    body = {
        "material_name": f"bad key {unique_suffix}",
        "material_type": "candidate",
    }
    r = await admin_client.post(
        "/api/v1/materials", json=body,
        headers={"Idempotency-Key": "not-a-uuid"},
    )
    assert r.status_code == 400
    assert r.json()["meta"]["error"]["type"] == "invalid_value"


@pytest.mark.asyncio
async def test_substance_idem_same_key_same_body(admin_client, unique_suffix):
    """覆盖另一个域（substance）验证 Idempotency 是统一行为"""
    key = str(uuid.uuid4())
    body = {
        "substance_type": "mab",
        "internal_code": f"IDEM-SUB-{unique_suffix}",
        "preferred_name": f"idem sub {unique_suffix}",
    }
    r1 = await admin_client.post(
        "/api/v1/substances", json=body,
        headers={"Idempotency-Key": key},
    )
    assert r1.status_code == 201
    code1 = r1.json()["data"]["substance_code"]

    r2 = await admin_client.post(
        "/api/v1/substances", json=body,
        headers={"Idempotency-Key": key},
    )
    assert r2.status_code == 201
    code2 = r2.json()["data"]["substance_code"]
    assert code1 == code2


@pytest.mark.asyncio
async def test_idem_keys_scoped_per_user(admin_client, researcher_client, unique_suffix):
    """同 Idempotency-Key 在不同 user 之间互不影响（key 命名空间含 user_id）"""
    key = str(uuid.uuid4())
    body = {
        "material_name": f"per user {unique_suffix}",
        "material_type": "candidate",
    }
    r_admin = await admin_client.post(
        "/api/v1/materials", json=body,
        headers={"Idempotency-Key": key},
    )
    assert r_admin.status_code == 201

    # researcher 用同 key + 同 body：应该新建（不是从 admin 缓存取）
    r_researcher = await researcher_client.post(
        "/api/v1/materials", json=body,
        headers={"Idempotency-Key": key},
    )
    assert r_researcher.status_code == 201
    assert r_researcher.json()["data"]["material_code"] != r_admin.json()["data"]["material_code"]
