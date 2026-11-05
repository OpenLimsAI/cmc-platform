"""
Material CRUD 关键路径测试（M4.1 v2）

物料身份注册表改造后（0038_mm_material_v2）：
  - material_code: 用户手动输入（max 20 chars）
  - material_type: reagent/consumable/standard/column
  - category: 公司分类体系 14 值扁平枚举
  - grade: 自由文本
  - 新增 7 个字段
"""
import pytest

from tests.conftest import current_version


@pytest.mark.asyncio
async def test_create_material_with_user_code(admin_client, unique_suffix):
    """物料编码由用户输入，原样保存"""
    mat_code = f"R-{unique_suffix[:8]}"
    resp = await admin_client.post(
        "/api/v1/materials",
        json={
            "material_code": mat_code,
            "material_name": f"pytest 物料 {unique_suffix}",
            "material_type": "reagent",
            "category": "试剂",
            "grade": "GR",
            "unit": "瓶",
            "manufacturer": "Sigma-Aldrich",
            "catalog_no": "P5368",
            "physical_form": "liquid",
            "storage_condition": "2-8°C",
            "source_type": "vendor",
            "source_name": "Sigma-Aldrich",
        },
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["code"] == 0
    data = body["data"]
    assert data["material_code"] == mat_code
    assert data["status"] == "active"
    assert data["material_type"] == "reagent"
    assert data["category"] == "试剂"
    assert data["grade"] == "GR"
    assert data["unit"] == "瓶"
    assert data["manufacturer"] == "Sigma-Aldrich"
    assert data["catalog_no"] == "P5368"
    assert resp.headers.get("Location") == f"/api/v1/materials/{mat_code}"


@pytest.mark.asyncio
async def test_create_material_duplicate_code_rejected(admin_client, unique_suffix):
    """重复物料编码应被拒绝"""
    mat_code = f"DUP-{unique_suffix[:6]}"
    await admin_client.post(
        "/api/v1/materials",
        json={
            "material_code": mat_code,
            "material_name": f"pytest dup1 {unique_suffix}",
            "material_type": "reagent",
        },
    )
    resp = await admin_client.post(
        "/api/v1/materials",
        json={
            "material_code": mat_code,
            "material_name": f"pytest dup2 {unique_suffix}",
            "material_type": "reagent",
        },
    )
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_create_material_code_required(admin_client, unique_suffix):
    """不传 material_code 应 400"""
    resp = await admin_client.post(
        "/api/v1/materials",
        json={
            "material_name": f"pytest no code {unique_suffix}",
            "material_type": "reagent",
        },
    )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_get_material_after_create(admin_client, unique_suffix):
    mat_code = f"S-{unique_suffix[:8]}"
    create = await admin_client.post(
        "/api/v1/materials",
        json={
            "material_code": mat_code,
            "material_name": f"pytest get {unique_suffix}",
            "material_name_en": "test material EN",
            "material_type": "standard",
            "category": "参比品",
            "grade": "USP Reference Standard",
            "unit": "瓶",
        },
    )
    code = create.json()["data"]["material_code"]
    assert code == mat_code
    detail = await admin_client.get(f"/api/v1/materials/{code}")
    assert detail.status_code == 200
    data = detail.json()["data"]
    assert data["material_code"] == mat_code
    assert data["material_type"] == "standard"
    assert data["category"] == "参比品"
    assert data["grade"] == "USP Reference Standard"
    assert data["material_name_en"] == "test material EN"
    assert data["substance_code"] is None


@pytest.mark.asyncio
async def test_list_materials_filters(admin_client, unique_suffix):
    for idx, (t, cat) in enumerate([
        ("reagent", "试剂"),
        ("standard", "标准品"),
        ("consumable", "一般耗材"),
    ]):
        await admin_client.post(
            "/api/v1/materials",
            json={
                "material_code": f"LF{idx}-{unique_suffix[:6]}",
                "material_name": f"pytest list {unique_suffix} {t}",
                "material_type": t,
                "category": cat,
            },
        )

    resp = await admin_client.get(
        "/api/v1/materials", params={"q": unique_suffix, "page_size": 50}
    )
    items = resp.json()["data"]
    assert sum(1 for it in items if unique_suffix in it["material_name"]) == 3

    only_consumable = await admin_client.get(
        "/api/v1/materials",
        params={"q": unique_suffix, "material_type": "consumable", "page_size": 50},
    )
    matched = [
        it for it in only_consumable.json()["data"]
        if unique_suffix in it["material_name"]
    ]
    assert len(matched) == 1
    assert matched[0]["material_type"] == "consumable"


@pytest.mark.asyncio
async def test_list_materials_category_filter(admin_client, unique_suffix):
    """category 过滤"""
    await admin_client.post(
        "/api/v1/materials",
        json={
            "material_code": f"CE-{unique_suffix[:7]}",
            "material_name": f"pytest cat {unique_suffix} critical",
            "material_type": "reagent",
            "category": "关键试剂",
        },
    )
    await admin_client.post(
        "/api/v1/materials",
        json={
            "material_code": f"CB-{unique_suffix[:7]}",
            "material_name": f"pytest cat {unique_suffix} general",
            "material_type": "reagent",
            "category": "试剂",
        },
    )
    resp = await admin_client.get(
        "/api/v1/materials",
        params={"q": unique_suffix, "category": "关键试剂", "page_size": 50},
    )
    matched = [it for it in resp.json()["data"] if unique_suffix in it["material_name"]]
    assert len(matched) == 1
    assert matched[0]["category"] == "关键试剂"


@pytest.mark.asyncio
async def test_update_material_status_and_grade(admin_client, unique_suffix):
    """status 无状态机，PUT 可直接改；grade 自由文本"""
    code = (
        await admin_client.post(
            "/api/v1/materials",
            json={
                "material_code": f"US-{unique_suffix[:7]}",
                "material_name": f"pytest status {unique_suffix}",
                "material_type": "reagent",
                "status": "active",
            },
        )
    ).json()["data"]["material_code"]

    resp = await admin_client.put(
        f"/api/v1/materials/{code}",
        json={"version": await current_version(admin_client, f"/api/v1/materials/{code}"), **{
            "change_reason": "进入隔离区待检",
            "status": "quarantine",
            "grade": "ACS Reagent Grade",
        }},
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    assert data["status"] == "quarantine"
    assert data["grade"] == "ACS Reagent Grade"


@pytest.mark.asyncio
async def test_invalid_material_type_rejected(admin_client, unique_suffix):
    resp = await admin_client.post(
        "/api/v1/materials",
        json={
            "material_code": f"IT-{unique_suffix[:7]}",
            "material_name": f"pytest invalid type {unique_suffix}",
            "material_type": "imaginary",
        },
    )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_invalid_category_rejected(admin_client, unique_suffix):
    """非法 category 值应被 Pydantic validator 拒绝"""
    resp = await admin_client.post(
        "/api/v1/materials",
        json={
            "material_code": f"IC-{unique_suffix[:7]}",
            "material_name": f"pytest bad cat {unique_suffix}",
            "material_type": "column",
            "category": "不存在的分类",
        },
    )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_hazard_class_round_trip(admin_client, unique_suffix):
    """hazard_class TEXT[] 存取"""
    resp = await admin_client.post(
        "/api/v1/materials",
        json={
            "material_code": f"HZ-{unique_suffix[:7]}",
            "material_name": f"pytest hazard {unique_suffix}",
            "material_type": "reagent",
            "category": "关键试剂",
            "hazard_class": ["危化品", "易燃"],
        },
    )
    assert resp.status_code == 201, resp.text
    code = resp.json()["data"]["material_code"]
    detail = await admin_client.get(f"/api/v1/materials/{code}")
    assert set(detail.json()["data"]["hazard_class"]) == {"危化品", "易燃"}


@pytest.mark.asyncio
async def test_invalid_hazard_class_rejected(admin_client, unique_suffix):
    resp = await admin_client.post(
        "/api/v1/materials",
        json={
            "material_code": f"IH-{unique_suffix[:7]}",
            "material_name": f"pytest bad hazard {unique_suffix}",
            "material_type": "reagent",
            "hazard_class": ["假的分类"],
        },
    )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_unit_defaults_to_ea(admin_client, unique_suffix):
    """不传 unit 时默认 ea"""
    resp = await admin_client.post(
        "/api/v1/materials",
        json={
            "material_code": f"UD-{unique_suffix[:7]}",
            "material_name": f"pytest unit default {unique_suffix}",
            "material_type": "consumable",
        },
    )
    assert resp.status_code == 201, resp.text
    code = resp.json()["data"]["material_code"]
    detail = await admin_client.get(f"/api/v1/materials/{code}")
    assert detail.json()["data"]["unit"] == "ea"


@pytest.mark.asyncio
async def test_soft_delete_excludes_from_list(admin_client, unique_suffix):
    code = (
        await admin_client.post(
            "/api/v1/materials",
            json={
                "material_code": f"SD-{unique_suffix[:7]}",
                "material_name": f"pytest delete {unique_suffix}",
                "material_type": "consumable",
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
    assert get_resp.json()["code"] == 40405

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
                "material_code": f"SR-{unique_suffix[:7]}",
                "material_name": f"pytest del reason {unique_suffix}",
                "material_type": "consumable",
            },
        )
    ).json()["data"]["material_code"]

    resp = await admin_client.delete(f"/api/v1/materials/{code}")
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_material_audit_log_entity_code(admin_client, unique_suffix):
    """audit trigger v2：entity_code = material_code"""
    code = (
        await admin_client.post(
            "/api/v1/materials",
            json={
                "material_code": f"AU-{unique_suffix[:7]}",
                "material_name": f"pytest audit {unique_suffix}",
                "material_type": "reagent",
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
            "material_code": f"RO-{unique_suffix[:7]}",
            "material_name": f"pytest forbidden {unique_suffix}",
            "material_type": "reagent",
        },
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_material_with_substance_ref(admin_client, unique_suffix):
    """通过 substance_code 解析 substance_id"""
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

    mat_resp = await admin_client.post(
        "/api/v1/materials",
        json={
            "material_code": f"MS-{unique_suffix[:7]}",
            "material_name": f"pytest mat with sub {unique_suffix}",
            "material_type": "standard",
            "category": "参比品",
            "substance_code": sub_code,
        },
    )
    assert mat_resp.status_code == 201, mat_resp.text
    mat = mat_resp.json()["data"]
    assert mat["substance_code"] == sub_code
    assert mat["substance_id"] is not None

    list_resp = await admin_client.get(
        "/api/v1/materials", params={"substance_code": sub_code, "page_size": 50}
    )
    assert list_resp.status_code == 200, list_resp.text
    items = list_resp.json()["data"]
    codes = [it["material_code"] for it in items]
    assert mat["material_code"] in codes


@pytest.mark.asyncio
async def test_material_substance_not_found(admin_client, unique_suffix):
    """引用不存在的 substance_code 应 404"""
    resp = await admin_client.post(
        "/api/v1/materials",
        json={
            "material_code": f"MN-{unique_suffix[:7]}",
            "material_name": f"pytest missing sub {unique_suffix}",
            "material_type": "reagent",
            "substance_code": "SUB-9999999",
        },
    )
    assert resp.status_code == 404
    assert resp.json()["code"] == 40402


@pytest.mark.asyncio
async def test_search_by_manufacturer_and_catalog(admin_client, unique_suffix):
    """关键字搜索覆盖 manufacturer / catalog_no"""
    await admin_client.post(
        "/api/v1/materials",
        json={
            "material_code": f"SM-{unique_suffix[:7]}",
            "material_name": f"pytest search {unique_suffix}",
            "material_type": "reagent",
            "manufacturer": f"XYZFIRM-{unique_suffix}",
            "catalog_no": f"CAT-{unique_suffix}",
        },
    )
    for kw in [f"XYZFIRM-{unique_suffix}", f"CAT-{unique_suffix}"]:
        resp = await admin_client.get(
            "/api/v1/materials", params={"q": kw, "page_size": 50}
        )
        matched = [it for it in resp.json()["data"] if unique_suffix in it["material_name"]]
        assert len(matched) >= 1, f"关键字 '{kw}' 未命中"
