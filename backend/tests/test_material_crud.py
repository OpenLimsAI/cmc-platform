"""
Material CRUD 关键路径测试（M4.1）

对齐 DM-MDM-001 V1.1 §10.1 + API-MDM-001 V1.1 §5.1.6 / §8.2
"""
import pytest


@pytest.mark.asyncio
async def test_create_material_returns_year_code(admin_client, unique_suffix):
    """编码规则 MAT-yyyyXXXXXX，年度序列"""
    resp = await admin_client.post(
        "/api/v1/materials",
        json={
            "material_name": f"pytest 物料 {unique_suffix}",
            "material_type": "candidate",
            "grade": "RUO",
            "physical_form": "liquid",
            "storage_condition": "2-8°C",
            "source_type": "internal",
            "source_name": "Pilot Plant 北区",
        },
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["code"] == 0
    data = body["data"]
    assert data["material_code"].startswith("MAT-")
    # MAT-2026 前缀（年份段）
    assert data["material_code"][4:8].isdigit()
    assert data["status"] == "active"
    assert data["material_type"] == "candidate"
    assert data["grade"] == "RUO"
    # API5 / §8.2：POST 必须设 Location 头
    assert resp.headers.get("Location") == f"/api/v1/materials/{data['material_code']}"


@pytest.mark.asyncio
async def test_get_material_after_create(admin_client, unique_suffix):
    create = await admin_client.post(
        "/api/v1/materials",
        json={
            "material_name": f"pytest get {unique_suffix}",
            "material_name_en": "test material EN",
            "material_type": "reference",
            "grade": "Reference Standard",
        },
    )
    code = create.json()["data"]["material_code"]
    detail = await admin_client.get(f"/api/v1/materials/{code}")
    assert detail.status_code == 200
    data = detail.json()["data"]
    assert data["material_code"] == code
    assert data["material_type"] == "reference"
    assert data["grade"] == "Reference Standard"
    assert data["material_name_en"] == "test material EN"
    assert data["substance_code"] is None  # 未关联物质


@pytest.mark.asyncio
async def test_list_materials_filters(admin_client, unique_suffix):
    for t, grade in [
        ("candidate", "RUO"),
        ("reference", "Reference Standard"),
        ("buffer", None),
    ]:
        await admin_client.post(
            "/api/v1/materials",
            json={
                "material_name": f"pytest list {unique_suffix} {t}",
                "material_type": t,
                "grade": grade,
            },
        )

    resp = await admin_client.get(
        "/api/v1/materials", params={"q": unique_suffix, "page_size": 50}
    )
    items = resp.json()["data"]
    assert sum(1 for it in items if unique_suffix in it["material_name"]) == 3

    only_buffer = await admin_client.get(
        "/api/v1/materials",
        params={"q": unique_suffix, "material_type": "buffer", "page_size": 50},
    )
    matched = [
        it for it in only_buffer.json()["data"]
        if unique_suffix in it["material_name"]
    ]
    assert len(matched) == 1
    assert matched[0]["material_type"] == "buffer"


@pytest.mark.asyncio
async def test_update_material_status_and_grade(admin_client, unique_suffix):
    """status 无状态机，PUT 可直接改"""
    code = (
        await admin_client.post(
            "/api/v1/materials",
            json={
                "material_name": f"pytest status {unique_suffix}",
                "material_type": "candidate",
                "status": "active",
            },
        )
    ).json()["data"]["material_code"]

    # 直接 PUT 把 status 改 quarantine（无需走状态机端点）
    resp = await admin_client.put(
        f"/api/v1/materials/{code}",
        json={
            "change_reason": "进入隔离区待检",
            "status": "quarantine",
            "grade": "GMP",
        },
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    assert data["status"] == "quarantine"
    assert data["grade"] == "GMP"


@pytest.mark.asyncio
async def test_invalid_material_type_rejected(admin_client, unique_suffix):
    resp = await admin_client.post(
        "/api/v1/materials",
        json={
            "material_name": f"pytest invalid type {unique_suffix}",
            "material_type": "imaginary",
        },
    )
    assert resp.status_code == 400  # V1.1 §4.1


@pytest.mark.asyncio
async def test_invalid_grade_rejected(admin_client, unique_suffix):
    resp = await admin_client.post(
        "/api/v1/materials",
        json={
            "material_name": f"pytest bad grade {unique_suffix}",
            "material_type": "candidate",
            "grade": "Bogus-Grade",
        },
    )
    assert resp.status_code == 400  # V1.1 §4.1


@pytest.mark.asyncio
async def test_soft_delete_excludes_from_list(admin_client, unique_suffix):
    code = (
        await admin_client.post(
            "/api/v1/materials",
            json={
                "material_name": f"pytest delete {unique_suffix}",
                "material_type": "buffer",
            },
        )
    ).json()["data"]["material_code"]

    del_resp = await admin_client.delete(
        f"/api/v1/materials/{code}",
        json={"change_reason": "pytest 软删除"},
    )
    assert del_resp.status_code == 204

    get_resp = await admin_client.get(f"/api/v1/materials/{code}")
    assert get_resp.status_code == 404
    assert get_resp.json()["code"] == 40405  # MaterialNotFoundError

    list_resp = await admin_client.get(
        "/api/v1/materials", params={"q": unique_suffix}
    )
    items = list_resp.json()["data"]
    assert all(it["material_code"] != code for it in items)


@pytest.mark.asyncio
async def test_soft_delete_requires_reason(admin_client, unique_suffix):
    code = (
        await admin_client.post(
            "/api/v1/materials",
            json={
                "material_name": f"pytest del reason {unique_suffix}",
                "material_type": "raw",
            },
        )
    ).json()["data"]["material_code"]

    resp = await admin_client.delete(f"/api/v1/materials/{code}")
    assert resp.status_code == 400  # V1.1 §4.1 缺 change_reason


@pytest.mark.asyncio
async def test_material_audit_log_entity_code(admin_client, unique_suffix):
    """audit trigger v2：entity_code = material_code"""
    code = (
        await admin_client.post(
            "/api/v1/materials",
            json={
                "material_name": f"pytest audit {unique_suffix}",
                "material_type": "candidate",
            },
        )
    ).json()["data"]["material_code"]

    logs = await admin_client.get(
        f"/api/v1/materials/{code}/audit-logs", params={"page_size": 20}
    )
    items = logs.json()["data"]
    create_logs = [it for it in items if it["action"] == "CREATE"]
    assert create_logs
    assert all(it["entity_code"] == code for it in create_logs)


@pytest.mark.asyncio
async def test_readonly_cannot_create_material(readonly_client, unique_suffix):
    """READ_ONLY_USER 缺 material:create"""
    resp = await readonly_client.post(
        "/api/v1/materials",
        json={
            "material_name": f"pytest forbidden {unique_suffix}",
            "material_type": "candidate",
        },
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_material_with_substance_ref(admin_client, unique_suffix):
    """通过 substance_code 解析 substance_id（V1.1 §10.1 物质引用）"""
    # 先建一个 substance 拿编码
    sub_resp = await admin_client.post(
        "/api/v1/substances",
        json={
            "substance_type": "mab",
            "internal_code": f"PY-MAT-SUB-{unique_suffix}",
            "preferred_name": f"pytest mat sub {unique_suffix}",
            "status": "active",
        },
    )
    assert sub_resp.status_code == 201, sub_resp.text
    sub_code = sub_resp.json()["data"]["substance_code"]

    # 关联到 material
    mat_resp = await admin_client.post(
        "/api/v1/materials",
        json={
            "material_name": f"pytest mat with sub {unique_suffix}",
            "material_type": "candidate",
            "substance_code": sub_code,
        },
    )
    assert mat_resp.status_code == 201, mat_resp.text
    mat = mat_resp.json()["data"]
    assert mat["substance_code"] == sub_code
    assert mat["substance_id"] is not None

    # filter by substance_code 命中
    list_resp = await admin_client.get(
        "/api/v1/materials", params={"substance_code": sub_code, "page_size": 50}
    )
    items = list_resp.json()["data"]
    codes = [it["material_code"] for it in items]
    assert mat["material_code"] in codes


@pytest.mark.asyncio
async def test_material_substance_not_found(admin_client, unique_suffix):
    """引用不存在的 substance_code 应 404"""
    resp = await admin_client.post(
        "/api/v1/materials",
        json={
            "material_name": f"pytest missing sub {unique_suffix}",
            "material_type": "candidate",
            "substance_code": "SUB-9999999",
        },
    )
    assert resp.status_code == 404
    assert resp.json()["code"] == 40402  # SubstanceNotFoundError
