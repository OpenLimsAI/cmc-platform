"""
全局搜索 /api/v1/search 测试（M2.3 / G2-API6 V1.1 §8.3 分组结构）

API-MDM-001 V1.1 §8.3 行 1688-1721 响应：
  data: {
    query, total,
    results: {
      substance: {total, items: [...]},
      project: {total, items: [...]},
      asset: {total, items: [...]},
      material: {total, items: [...]},   -- M4.4 起加入
    }
  }
"""
import pytest


def _all_hits(payload: dict) -> list:
    """从分组结构提取所有 hits（测试方便）"""
    data = payload["data"]
    out: list = []
    for group_key in ("substance", "project", "asset", "material", "equipment"):
        out.extend(data["results"][group_key]["items"])
    return out


def _group_items(payload: dict, group: str) -> list:
    return payload["data"]["results"][group]["items"]


@pytest.mark.asyncio
async def test_search_finds_substance_by_name(admin_client, unique_suffix):
    name = f"SearchableSub {unique_suffix}"
    await admin_client.post(
        "/api/v1/substances",
        json={
            "substance_type": "mab",
            "internal_code": f"TEST-SR-{unique_suffix}",
            "preferred_name": name,
        },
    )

    resp = await admin_client.get(
        "/api/v1/search", params={"q": f"SearchableSub {unique_suffix}", "limit": 10}
    )
    assert resp.status_code == 200
    hits = _all_hits(resp.json())
    assert any(
        h["entity_type"] == "substance" and h["name"] == name for h in hits
    )


@pytest.mark.asyncio
async def test_search_finds_project_by_code(admin_client, unique_suffix):
    create = await admin_client.post(
        "/api/v1/projects",
        json={"project_name": f"pytest sr proj {unique_suffix}", "project_type": "cmc"},
    )
    pcode = create.json()["data"]["project_code"]

    resp = await admin_client.get(
        "/api/v1/search", params={"q": pcode, "limit": 5}
    )
    # G2-API6 后：每个分组内部按权重排序，code 精确命中是第一条
    proj_items = _group_items(resp.json(), "project")
    assert proj_items, "应命中 project 分组"
    assert proj_items[0]["code"] == pcode
    assert proj_items[0]["matched_field"] == "code"


@pytest.mark.asyncio
async def test_search_finds_substance_by_xref(admin_client, unique_suffix):
    """xref 命中：用 INN 值搜应能查回 substance"""
    create = await admin_client.post(
        "/api/v1/substances",
        json={
            "substance_type": "mab",
            "internal_code": f"TEST-XR-{unique_suffix}",
            "preferred_name": f"sr xref base {unique_suffix}",
        },
    )
    scode = create.json()["data"]["substance_code"]
    inn_val = f"sercaplimab{unique_suffix}"
    await admin_client.post(
        f"/api/v1/substances/{scode}/xrefs",
        json={"xref_type": "INN", "xref_value": inn_val, "is_primary": True},
    )

    resp = await admin_client.get(
        "/api/v1/search", params={"q": inn_val, "limit": 5}
    )
    hits = _all_hits(resp.json())
    match = next((h for h in hits if h["code"] == scode), None)
    assert match is not None, f"xref 搜索应命中 {scode}，实际命中 {hits}"
    assert match["matched_field"] == "xref"
    assert inn_val in (match["snippet"] or "")


@pytest.mark.asyncio
async def test_search_types_filter(admin_client, unique_suffix):
    """types=substance 只返回 substance 分组有 items，其他分组 items 为空"""
    await admin_client.post(
        "/api/v1/substances",
        json={
            "substance_type": "mab",
            "internal_code": f"TEST-TF-{unique_suffix}",
            "preferred_name": f"tf both {unique_suffix}",
        },
    )
    await admin_client.post(
        "/api/v1/projects",
        json={"project_name": f"tf both {unique_suffix}", "project_type": "cmc"},
    )
    resp = await admin_client.get(
        "/api/v1/search",
        params={"q": f"tf both {unique_suffix}", "types": "substance", "limit": 10},
    )
    data = resp.json()["data"]
    assert data["results"]["substance"]["total"] >= 1
    assert data["results"]["project"]["total"] == 0
    assert data["results"]["asset"]["total"] == 0
    assert data["results"]["material"]["total"] == 0
    assert data["results"]["equipment"]["total"] == 0


@pytest.mark.asyncio
async def test_search_respects_permissions(readonly_client, admin_client, unique_suffix):
    """readonly 同时有 substance:read 和 project:read，应能搜到两者"""
    await admin_client.post(
        "/api/v1/substances",
        json={
            "substance_type": "mab",
            "internal_code": f"TEST-PERM-{unique_suffix}",
            "preferred_name": f"perm both {unique_suffix}",
        },
    )
    await admin_client.post(
        "/api/v1/projects",
        json={"project_name": f"perm both {unique_suffix}", "project_type": "cmc"},
    )
    resp = await readonly_client.get(
        "/api/v1/search", params={"q": f"perm both {unique_suffix}", "limit": 10}
    )
    assert resp.status_code == 200
    hits = _all_hits(resp.json())
    entity_types = {h["entity_type"] for h in hits}
    assert "substance" in entity_types
    assert "project" in entity_types


@pytest.mark.asyncio
async def test_search_requires_auth(http_client):
    """未登录应 401"""
    resp = await http_client.get("/api/v1/search", params={"q": "anything"})
    assert resp.status_code == 401


# ============== M3.4 资产搜索 ==============
@pytest.mark.asyncio
async def test_search_finds_asset_by_name(admin_client, unique_suffix):
    name = f"SearchableAsset {unique_suffix}"
    await admin_client.post(
        "/api/v1/assets",
        json={"internal_name": name, "asset_type": "mab"},
    )
    resp = await admin_client.get(
        "/api/v1/search", params={"q": f"SearchableAsset {unique_suffix}", "limit": 10}
    )
    hits = _all_hits(resp.json())
    assert any(
        h["entity_type"] == "asset" and h["name"] == name for h in hits
    )


@pytest.mark.asyncio
async def test_search_finds_asset_by_code(admin_client, unique_suffix):
    """AST-XXXXXXX 精确命中应排在分组最前"""
    create = await admin_client.post(
        "/api/v1/assets",
        json={"internal_name": f"sr asset code {unique_suffix}", "asset_type": "mab"},
    )
    acode = create.json()["data"]["asset_code"]
    resp = await admin_client.get(
        "/api/v1/search", params={"q": acode, "limit": 5}
    )
    asset_items = _group_items(resp.json(), "asset")
    assert asset_items, "应命中 asset 分组"
    assert asset_items[0]["code"] == acode
    assert asset_items[0]["matched_field"] == "code"


@pytest.mark.asyncio
async def test_search_finds_asset_by_trade_name(admin_client, unique_suffix):
    """商品名应能命中且 matched_field=trade_name"""
    trade = f"Tradenamis{unique_suffix}"
    await admin_client.post(
        "/api/v1/assets",
        json={
            "internal_name": f"sr asset trade {unique_suffix}",
            "asset_type": "mab",
            "trade_name": trade,
        },
    )
    resp = await admin_client.get(
        "/api/v1/search", params={"q": trade, "limit": 5}
    )
    hits = _all_hits(resp.json())
    match = next((h for h in hits if h["entity_type"] == "asset"), None)
    assert match is not None, f"应命中资产 trade_name={trade}"
    assert match["matched_field"] == "trade_name"
    assert trade in (match["snippet"] or "")


@pytest.mark.asyncio
async def test_search_types_filter_asset_only(admin_client, unique_suffix):
    """types=asset 只返回 asset 分组有 items"""
    await admin_client.post(
        "/api/v1/substances",
        json={
            "substance_type": "mab",
            "internal_code": f"TEST-T4-{unique_suffix}",
            "preferred_name": f"t4 all {unique_suffix}",
        },
    )
    await admin_client.post(
        "/api/v1/projects",
        json={"project_name": f"t4 all {unique_suffix}", "project_type": "cmc"},
    )
    await admin_client.post(
        "/api/v1/assets",
        json={"internal_name": f"t4 all {unique_suffix}", "asset_type": "mab"},
    )
    resp = await admin_client.get(
        "/api/v1/search",
        params={"q": f"t4 all {unique_suffix}", "types": "asset", "limit": 10},
    )
    data = resp.json()["data"]
    assert data["results"]["asset"]["total"] >= 1
    assert data["results"]["substance"]["total"] == 0
    assert data["results"]["project"]["total"] == 0
    assert data["results"]["material"]["total"] == 0
    assert data["results"]["equipment"]["total"] == 0


@pytest.mark.asyncio
async def test_search_default_returns_all_five_types(admin_client, unique_suffix):
    """缺省 types 时五种实体都应能返回（M4.4 起加 material，EQP 起加 equipment）"""
    tag = f"AllFive{unique_suffix}"
    await admin_client.post(
        "/api/v1/substances",
        json={
            "substance_type": "mab",
            "internal_code": f"TEST-A5-{unique_suffix}",
            "preferred_name": tag,
        },
    )
    await admin_client.post(
        "/api/v1/projects",
        json={"project_name": tag, "project_type": "cmc"},
    )
    await admin_client.post(
        "/api/v1/assets",
        json={"internal_name": tag, "asset_type": "mab"},
    )
    await admin_client.post(
        "/api/v1/materials",
        json={"material_code": f"A5-{unique_suffix[:7]}", "material_name": tag, "material_type": "reagent"},
    )
    await admin_client.post(
        "/api/v1/equipments",
        json={"equipment_name": tag, "category": "分析仪器"},
    )
    resp = await admin_client.get(
        "/api/v1/search", params={"q": tag, "limit": 20}
    )
    data = resp.json()["data"]
    assert data["query"] == tag
    assert data["results"]["substance"]["total"] >= 1
    assert data["results"]["project"]["total"] >= 1
    assert data["results"]["asset"]["total"] >= 1
    assert data["results"]["material"]["total"] >= 1
    assert data["results"]["equipment"]["total"] >= 1


@pytest.mark.asyncio
async def test_search_response_structure(admin_client):
    """API6（V1.1 §8.3 行 1688-1721）：响应分组结构严格断言（含 material + equipment）"""
    resp = await admin_client.get(
        "/api/v1/search", params={"q": "SUB-", "limit": 5}
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert set(data.keys()) == {"query", "total", "results"}
    assert data["query"] == "SUB-"
    assert isinstance(data["total"], int)
    assert set(data["results"].keys()) == {
        "substance", "project", "asset", "material", "equipment", "target"
    }
    for group_key in ("substance", "project", "asset", "material", "equipment", "target"):
        group = data["results"][group_key]
        assert set(group.keys()) == {"total", "items"}
        assert isinstance(group["total"], int)
        assert isinstance(group["items"], list)
        # total 与 items 长度一致
        assert group["total"] == len(group["items"])


# ============== M4.4 物料搜索 ==============
@pytest.mark.asyncio
async def test_search_finds_material_by_name(admin_client, unique_suffix):
    name = f"SearchableMat {unique_suffix}"
    await admin_client.post(
        "/api/v1/materials",
        json={"material_code": f"SN-{unique_suffix[:7]}", "material_name": name, "material_type": "reagent"},
    )
    resp = await admin_client.get(
        "/api/v1/search", params={"q": f"SearchableMat {unique_suffix}", "limit": 10}
    )
    hits = _all_hits(resp.json())
    assert any(
        h["entity_type"] == "material" and h["name"] == name for h in hits
    )


@pytest.mark.asyncio
async def test_search_finds_material_by_code(admin_client, unique_suffix):
    """物料编码精确命中排在分组最前"""
    create = await admin_client.post(
        "/api/v1/materials",
        json={"material_code": f"SC-{unique_suffix[:7]}", "material_name": f"sr mat code {unique_suffix}", "material_type": "consumable"},
    )
    mcode = create.json()["data"]["material_code"]
    resp = await admin_client.get(
        "/api/v1/search", params={"q": mcode, "limit": 5}
    )
    mat_items = resp.json()["data"]["results"]["material"]["items"]
    assert mat_items
    assert mat_items[0]["code"] == mcode
    assert mat_items[0]["matched_field"] == "code"


@pytest.mark.asyncio
async def test_search_finds_material_by_source_name(admin_client, unique_suffix):
    """source_name 应能命中，matched_field=source_name"""
    src = f"PilotPlant{unique_suffix}"
    await admin_client.post(
        "/api/v1/materials",
        json={
            "material_code": f"SS-{unique_suffix[:7]}",
            "material_name": f"sr mat src {unique_suffix}",
            "material_type": "reagent",
            "source_name": src,
        },
    )
    resp = await admin_client.get(
        "/api/v1/search", params={"q": src, "limit": 5}
    )
    hits = _all_hits(resp.json())
    match = next((h for h in hits if h["entity_type"] == "material"), None)
    assert match is not None
    assert match["matched_field"] == "source_name"
    assert src in (match["snippet"] or "")


@pytest.mark.asyncio
async def test_search_types_filter_material_only(admin_client, unique_suffix):
    """types=material 只返回 material 分组有 items"""
    tag = f"MatOnly{unique_suffix}"
    await admin_client.post(
        "/api/v1/substances",
        json={
            "substance_type": "mab",
            "internal_code": f"TEST-MO-{unique_suffix}",
            "preferred_name": tag,
        },
    )
    await admin_client.post(
        "/api/v1/materials",
        json={"material_code": f"MO-{unique_suffix[:7]}", "material_name": tag, "material_type": "reagent"},
    )
    resp = await admin_client.get(
        "/api/v1/search",
        params={"q": tag, "types": "material", "limit": 10},
    )
    data = resp.json()["data"]
    assert data["results"]["material"]["total"] >= 1
    assert data["results"]["substance"]["total"] == 0
    assert data["results"]["project"]["total"] == 0
    assert data["results"]["asset"]["total"] == 0
    assert data["results"]["equipment"]["total"] == 0


# ============== EQP 设备搜索 ==============
@pytest.mark.asyncio
async def test_search_finds_equipment_by_name(admin_client, unique_suffix):
    name = f"SearchableEqp {unique_suffix}"
    await admin_client.post(
        "/api/v1/equipments",
        json={"equipment_name": name, "category": "分析仪器"},
    )
    resp = await admin_client.get(
        "/api/v1/search", params={"q": f"SearchableEqp {unique_suffix}", "limit": 10}
    )
    hits = _all_hits(resp.json())
    assert any(
        h["entity_type"] == "equipment" and h["name"] == name for h in hits
    )


@pytest.mark.asyncio
async def test_search_finds_equipment_by_code(admin_client, unique_suffix):
    """设备编码精确命中排在分组最前"""
    create = await admin_client.post(
        "/api/v1/equipments",
        json={"equipment_name": f"sr eqp code {unique_suffix}", "category": "通用实验室设备"},
    )
    ecode = create.json()["data"]["equipment_code"]
    resp = await admin_client.get(
        "/api/v1/search", params={"q": ecode, "limit": 5}
    )
    eqp_items = _group_items(resp.json(), "equipment")
    assert eqp_items
    assert eqp_items[0]["code"] == ecode
    assert eqp_items[0]["matched_field"] == "code"


@pytest.mark.asyncio
async def test_search_finds_equipment_by_manufacturer(admin_client, unique_suffix):
    """厂商命中，matched_field=manufacturer"""
    mfr = f"Acmefg{unique_suffix}"
    await admin_client.post(
        "/api/v1/equipments",
        json={
            "equipment_name": f"sr eqp mfr {unique_suffix}",
            "category": "分析仪器",
            "manufacturer": mfr,
        },
    )
    resp = await admin_client.get(
        "/api/v1/search", params={"q": mfr, "limit": 5}
    )
    hits = _all_hits(resp.json())
    match = next((h for h in hits if h["entity_type"] == "equipment"), None)
    assert match is not None
    assert match["matched_field"] == "manufacturer"
    assert mfr in (match["snippet"] or "")
