"""
全局搜索 /api/v1/search 测试（M2.3）
"""
import pytest


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
    hits = resp.json()["data"]
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
    hits = resp.json()["data"]
    assert hits[0]["entity_type"] == "project"
    assert hits[0]["code"] == pcode
    assert hits[0]["matched_field"] == "code"


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
    hits = resp.json()["data"]
    match = next((h for h in hits if h["code"] == scode), None)
    assert match is not None, f"xref 搜索应命中 {scode}，实际命中 {hits}"
    assert match["matched_field"] == "xref"
    assert inn_val in (match["snippet"] or "")


@pytest.mark.asyncio
async def test_search_types_filter(admin_client, unique_suffix):
    """types=substance 只返回 substance"""
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
    hits = resp.json()["data"]
    assert all(h["entity_type"] == "substance" for h in hits)
    assert len(hits) >= 1


@pytest.mark.asyncio
async def test_search_respects_permissions(readonly_client, admin_client, unique_suffix):
    """readonly 同时有 substance:read 和 project:read，应能搜到两者；
    但若过滤 types=project 也只返回 project。回归点是权限过滤不会误伤合法用户。"""
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
    hits = resp.json()["data"]
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
    """资产 internal_name 命中"""
    name = f"SearchableAsset {unique_suffix}"
    await admin_client.post(
        "/api/v1/assets",
        json={"internal_name": name, "asset_type": "mab"},
    )
    resp = await admin_client.get(
        "/api/v1/search", params={"q": f"SearchableAsset {unique_suffix}", "limit": 10}
    )
    hits = resp.json()["data"]
    assert any(
        h["entity_type"] == "asset" and h["name"] == name for h in hits
    )


@pytest.mark.asyncio
async def test_search_finds_asset_by_code(admin_client, unique_suffix):
    """AST-XXXXXXX 精确命中应排在最前"""
    create = await admin_client.post(
        "/api/v1/assets",
        json={"internal_name": f"sr asset code {unique_suffix}", "asset_type": "mab"},
    )
    acode = create.json()["data"]["asset_code"]
    resp = await admin_client.get(
        "/api/v1/search", params={"q": acode, "limit": 5}
    )
    hits = resp.json()["data"]
    assert hits[0]["entity_type"] == "asset"
    assert hits[0]["code"] == acode
    assert hits[0]["matched_field"] == "code"


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
    hits = resp.json()["data"]
    match = next((h for h in hits if h["entity_type"] == "asset"), None)
    assert match is not None, f"应命中资产 trade_name={trade}"
    assert match["matched_field"] == "trade_name"
    assert trade in (match["snippet"] or "")


@pytest.mark.asyncio
async def test_search_types_filter_asset_only(admin_client, unique_suffix):
    """types=asset 只返回 asset"""
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
    hits = resp.json()["data"]
    assert all(h["entity_type"] == "asset" for h in hits)
    assert len(hits) >= 1


@pytest.mark.asyncio
async def test_search_default_returns_all_three_types(admin_client, unique_suffix):
    """缺省 types 时三种实体都应能返回"""
    tag = f"AllThree{unique_suffix}"
    await admin_client.post(
        "/api/v1/substances",
        json={
            "substance_type": "mab",
            "internal_code": f"TEST-A3-{unique_suffix}",
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
    resp = await admin_client.get(
        "/api/v1/search", params={"q": tag, "limit": 20}
    )
    entity_types = {h["entity_type"] for h in resp.json()["data"]}
    assert entity_types == {"substance", "project", "asset"}
