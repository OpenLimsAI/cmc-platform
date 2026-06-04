"""
Equipment CRUD 关键路径测试（EQP 设备主数据域）

eqp.equipment（0040_eqp_equipment）：
  - equipment_code: 留空自动生成 EQP-yyyyXXXXXX；也可手动传入沿用历史编号
  - category: 分析仪器/实验设备/辅助设备/其他
  - status: active/retired（无状态机，PUT 直接改）
  - 软删除需 change_reason ≥5 字符
"""
import pytest


@pytest.mark.asyncio
async def test_create_equipment_auto_code(admin_client, unique_suffix):
    """留空 equipment_code 自动生成 EQP- 年度序列编码"""
    resp = await admin_client.post(
        "/api/v1/equipments",
        json={
            "equipment_name": f"pytest 液相 {unique_suffix}",
            "category": "分析仪器",
            "model": "LC-2030C",
            "manufacturer": "Shimadzu",
            "serial_no": f"SN-{unique_suffix}",
        },
    )
    assert resp.status_code == 201, resp.text
    data = resp.json()["data"]
    assert data["equipment_code"].startswith("EQP-")
    assert data["status"] == "active"
    assert data["category"] == "分析仪器"
    assert resp.headers.get("Location") == f"/api/v1/equipments/{data['equipment_code']}"


@pytest.mark.asyncio
async def test_create_equipment_manual_code(admin_client, unique_suffix):
    """手动传入历史编号原样保存"""
    code = f"EQP-LEGACY-{unique_suffix[:6]}"
    resp = await admin_client.post(
        "/api/v1/equipments",
        json={
            "equipment_code": code,
            "equipment_name": f"pytest 天平 {unique_suffix}",
            "category": "实验设备",
        },
    )
    assert resp.status_code == 201, resp.text
    assert resp.json()["data"]["equipment_code"] == code


@pytest.mark.asyncio
async def test_create_equipment_duplicate_code_rejected(admin_client, unique_suffix):
    """重复设备编码应被拒绝"""
    code = f"EQP-DUP-{unique_suffix[:6]}"
    payload = {
        "equipment_code": code,
        "equipment_name": f"pytest dup {unique_suffix}",
        "category": "其他",
    }
    r1 = await admin_client.post("/api/v1/equipments", json=payload)
    assert r1.status_code == 201, r1.text
    r2 = await admin_client.post("/api/v1/equipments", json=payload)
    assert r2.status_code == 409, r2.text


@pytest.mark.asyncio
async def test_create_equipment_invalid_category_rejected(admin_client, unique_suffix):
    resp = await admin_client.post(
        "/api/v1/equipments",
        json={
            "equipment_name": f"pytest bad cat {unique_suffix}",
            "category": "不存在的分类",
        },
    )
    assert resp.status_code == 400, resp.text


@pytest.mark.asyncio
async def test_get_update_delete_equipment(admin_client, unique_suffix):
    """详情 → 更新(含 change_reason) → 软删除 → 404"""
    create = await admin_client.post(
        "/api/v1/equipments",
        json={
            "equipment_name": f"pytest lifecycle {unique_suffix}",
            "category": "辅助设备",
        },
    )
    assert create.status_code == 201, create.text
    code = create.json()["data"]["equipment_code"]

    # 详情
    got = await admin_client.get(f"/api/v1/equipments/{code}")
    assert got.status_code == 200, got.text
    assert got.json()["data"]["equipment_code"] == code

    # 更新
    upd = await admin_client.put(
        f"/api/v1/equipments/{code}",
        json={
            "manufacturer": "Mettler Toledo",
            "status": "retired",
            "change_reason": "pytest 更新测试",
        },
    )
    assert upd.status_code == 200, upd.text
    assert upd.json()["data"]["manufacturer"] == "Mettler Toledo"
    assert upd.json()["data"]["status"] == "retired"

    # 软删除（change_reason 必填 ≥5）
    short = await admin_client.delete(
        f"/api/v1/equipments/{code}", json={"change_reason": "短"}
    )
    assert short.status_code == 400, short.text

    deleted = await admin_client.delete(
        f"/api/v1/equipments/{code}", json={"change_reason": "pytest 清理测试数据"}
    )
    assert deleted.status_code == 204, deleted.text

    gone = await admin_client.get(f"/api/v1/equipments/{code}")
    assert gone.status_code == 404, gone.text


@pytest.mark.asyncio
async def test_equipment_list_filter(admin_client, unique_suffix):
    """关键词 + 分类筛选"""
    name = f"pytest filter {unique_suffix}"
    await admin_client.post(
        "/api/v1/equipments",
        json={"equipment_name": name, "category": "分析仪器"},
    )
    resp = await admin_client.get(
        "/api/v1/equipments", params={"q": unique_suffix, "category": "分析仪器"}
    )
    assert resp.status_code == 200, resp.text
    items = resp.json()["data"]
    assert any(i["equipment_name"] == name for i in items)


@pytest.mark.asyncio
async def test_equipment_readonly_cannot_write(readonly_client, unique_suffix):
    """READ_ONLY_USER 有 equipment:read 无 equipment:create"""
    listed = await readonly_client.get("/api/v1/equipments")
    assert listed.status_code == 200, listed.text

    resp = await readonly_client.post(
        "/api/v1/equipments",
        json={"equipment_name": f"pytest forbidden {unique_suffix}", "category": "其他"},
    )
    assert resp.status_code == 403, resp.text
