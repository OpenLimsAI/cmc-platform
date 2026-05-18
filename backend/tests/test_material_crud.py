"""
文件: backend/tests/test_material_crud.py
用途: 物料 CRUD 关键路径测试
覆盖:
    - POST /api/materials 单条创建
    - 重复 material_code 拒绝
    - 单位不在字典拒绝
    - 新分类自动加入 category_dict
    - 前导 0 在创建后被严格保留(返回的 material_code 仍是 '04xxx')
    - PATCH /api/materials/{material_id} 改全部字段
"""
from __future__ import annotations

from sqlalchemy import text


def test_create_material_basic(client, db):
    resp = client.post("/api/materials", json={
        "material_code": "90001",
        "category": "测试新分类",
        "name_cn": "测试物料",
        "unit": "支",
        "spec_model": "S-001",
        "safety_stock": "10",
    })
    assert resp.status_code == 201, resp.json()
    body = resp.json()
    assert body["material_code"] == "90001"
    assert body["name_cn"] == "测试物料"
    assert body["is_active"] is True

    # 新分类应自动入字典
    cats = [r[0] for r in db.execute(text(
        "SELECT category FROM category_dict WHERE category = '测试新分类'"
    )).all()]
    assert cats == ["测试新分类"], "新分类应自动加入 category_dict"


def test_create_material_preserves_leading_zero(client):
    """前导 0 必须严格保留,不能被强转 int 截断。"""
    resp = client.post("/api/materials", json={
        "material_code": "04321",
        "name_cn": "前导零物料",
        "unit": "支",
    })
    assert resp.status_code == 201
    assert resp.json()["material_code"] == "04321"


def test_create_material_duplicate_rejected(client, seed_material):
    _mid, code, _ = seed_material  # 已有 42001
    resp = client.post("/api/materials", json={
        "material_code": code,
        "name_cn": "重复物料",
        "unit": "支",
    })
    assert resp.status_code == 400
    assert "已存在" in resp.json()["detail"]


def test_create_material_unknown_unit_rejected(client):
    resp = client.post("/api/materials", json={
        "material_code": "90099",
        "name_cn": "未知单位物料",
        "unit": "不存在的单位",
    })
    assert resp.status_code == 400
    assert "单位" in resp.json()["detail"]


def test_tt_internal_code_allows_duplicates(client, db):
    """'TT内部物料' 保留 code 允许多条共存(v1.2 新规)。"""
    for name in ("内部物料 A", "内部物料 B"):
        resp = client.post("/api/materials", json={
            "material_code": "TT内部物料",
            "name_cn": name,
            "unit": "支",
        })
        assert resp.status_code == 201, resp.json()

    rows = db.execute(text(
        "SELECT material_id, name_cn FROM material WHERE material_code='TT内部物料'"
    )).all()
    assert len(rows) == 2
    # material_id 不同
    assert rows[0][0] != rows[1][0]


def test_hazard_class_persisted_and_validated(client, db):
    """危化品分类多选可写入;非法值返 422。"""
    resp = client.post("/api/materials", json={
        "material_code": "HZ001", "name_cn": "危化品测试", "unit": "瓶",
        "hazard_class": ["危化品", "易燃"],
    })
    assert resp.status_code == 201
    assert sorted(resp.json()["hazard_class"]) == sorted(["危化品", "易燃"])

    # 非法字面值应被 pydantic 拒绝
    resp = client.post("/api/materials", json={
        "material_code": "HZ002", "name_cn": "x", "unit": "瓶",
        "hazard_class": ["乱填的"],
    })
    assert resp.status_code == 422


def test_patch_material_all_fields(client, seed_material):
    """PATCH 应支持所有字段;None 显式传入会清空(name_cn 必填字段除外)。"""
    mid, _code, _ = seed_material
    resp = client.patch(f"/api/materials/{mid}", json={
        "category": "新分类",
        "manufacturer": "Sigma",
        "spec_model": "5g",
        "catalog_no": "C-001",
        "package_spec": "5g/瓶",
        "hazard_class": ["剧毒品"],
        "remark": "已更新",
    })
    assert resp.status_code == 200, resp.json()
    body = resp.json()
    assert body["manufacturer"] == "Sigma"
    assert body["spec_model"] == "5g"
    assert body["hazard_class"] == ["剧毒品"]
    assert body["remark"] == "已更新"


def test_patch_material_new_category_added_to_dict(client, db, seed_material):
    """编辑时改 category 为新值,应自动加入 category_dict(与新增物料行为一致)。"""
    mid, _code, _ = seed_material
    resp = client.patch(f"/api/materials/{mid}", json={
        "category": "通过编辑新增的分类",
    })
    assert resp.status_code == 200
    cats = [r[0] for r in db.execute(text(
        "SELECT category FROM category_dict WHERE category = '通过编辑新增的分类'"
    )).all()]
    assert cats == ["通过编辑新增的分类"]
