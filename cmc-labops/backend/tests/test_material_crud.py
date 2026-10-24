"""
文件: backend/tests/test_material_crud.py
用途: 物料 CRUD 关键路径测试
覆盖:
    - POST /api/materials 单条创建(category 须在 MDM 对齐白名单内)
    - 重复 material_code 拒绝
    - 单位不在字典拒绝
    - 白名单内分类若不在 category_dict 自动加入;白名单外分类 422
    - 前导 0 在创建后被严格保留(返回的 material_code 仍是 '04xxx')
    - PATCH /api/materials/{material_id} 改全部字段
"""
from __future__ import annotations

from sqlalchemy import text


def test_create_material_basic(client, db):
    resp = client.post("/api/materials", json={
        "material_code": "90001",
        "category": "一般耗材",
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
    assert body["category"] == "一般耗材"


def test_create_material_category_not_in_whitelist_rejected(client):
    """category 白名单(与 MDM 对齐的枚举)以外的值 → 422。"""
    resp = client.post("/api/materials", json={
        "material_code": "90002",
        "category": "乱填的分类",
        "name_cn": "x",
        "unit": "支",
    })
    assert resp.status_code == 422


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
        "category": "试剂",
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


def test_patch_mdm_material_identity_fields_rejected(client, db, seed_material):
    """data_source='mdm' 的物料,身份字段(名称/厂家等)本系统只读 → 400;
    运营字段(safety_stock/material_type/remark)仍可改。"""
    mid, _code, _ = seed_material
    db.execute(text("UPDATE material SET data_source='mdm' WHERE material_id=:m"), {"m": mid})
    db.commit()

    resp = client.patch(f"/api/materials/{mid}", json={"name_cn": "篡改名称"})
    assert resp.status_code == 400
    assert "MDM" in resp.json()["detail"]

    resp = client.patch(f"/api/materials/{mid}", json={"safety_stock": "66", "remark": "运营可改"})
    assert resp.status_code == 200, resp.json()
    assert resp.json()["remark"] == "运营可改"


def test_create_from_mdm_refreshes_existing_material(client, db, seed_material, monkeypatch):
    """入库解析已有物料时,应从 MDM 刷新身份快照,但保留本地运营字段。"""
    import mdm_client

    mid, code, _ = seed_material
    db.execute(text(
        "UPDATE material SET data_source='mdm', material_type='reagent', remark='本地备注' "
        "WHERE material_id=:m"
    ), {"m": mid})
    db.commit()

    def fake_get_material_by_code(query_code, token=None):
        assert query_code == code
        return {
            "material_code": code,
            "material_name": "MDM 新名称",
            "category": "细胞种子",
            "material_type": "consumable",
            "grade": "AR",
            "manufacturer": "MDM 厂家",
            "spec_model": "10mL",
            "catalog_no": "MDM-001",
            "unit": "箱",
            "package_spec": "10mL/箱",
            "hazard_class": ["易燃"],
        }

    monkeypatch.setattr(mdm_client, "get_material_by_code", fake_get_material_by_code)

    resp = client.post(f"/api/materials/from-mdm/{code}")
    assert resp.status_code == 201, resp.json()
    body = resp.json()
    assert body["material_id"] == mid
    assert body["name_cn"] == "MDM 新名称"
    assert body["category"] == "细胞种子"
    assert body["manufacturer"] == "MDM 厂家"
    assert body["unit"] == "箱"
    assert body["hazard_class"] == ["易燃"]
    assert body["material_type"] == "reagent"
    assert body["safety_stock"] == "100.00"
    assert body["remark"] == "本地备注"

    unit = db.execute(text("SELECT unit FROM unit_dict WHERE unit='箱'")).scalar_one()
    category = db.execute(text(
        "SELECT category FROM category_dict WHERE category='细胞种子'"
    )).scalar_one()
    assert unit == "箱"
    assert category == "细胞种子"


def test_create_from_mdm_existing_material_falls_back_when_mdm_missing(client, seed_material, monkeypatch):
    """MDM 查不到/不可用时,已有物料仍可继续用于入库。"""
    import mdm_client

    mid, code, _ = seed_material
    monkeypatch.setattr(mdm_client, "get_material_by_code", lambda query_code, token=None: None)

    resp = client.post(f"/api/materials/from-mdm/{code}")
    assert resp.status_code == 201, resp.json()
    body = resp.json()
    assert body["material_id"] == mid
    assert body["material_code"] == code
    assert body["name_cn"] == "测试耗材"


def test_patch_material_new_category_added_to_dict(client, db, seed_material):
    """编辑时改 category 为白名单内但字典尚无的值,应自动加入 category_dict;
    白名单外的值在 pydantic 层就被拒(见 create 的 422 测试)。"""
    mid, _code, _ = seed_material
    resp = client.patch(f"/api/materials/{mid}", json={
        "category": "细胞种子",
    })
    assert resp.status_code == 200, resp.json()
    cats = [r[0] for r in db.execute(text(
        "SELECT category FROM category_dict WHERE category = '细胞种子'"
    )).all()]
    assert cats == ["细胞种子"]
