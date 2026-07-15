"""
SMP-RD-NUM-001 V2.1 第二批（B1-B7）测试：
项目分类三维度 + asset_id 1:N 绑定条件必填 + approve 回填 + 受控 phase
"""
import pytest

ADMIN_PASSWORD = "__REDACTED_SEED_PASSWORD_1__"


async def _new_asset(client, suffix: str) -> int:
    resp = await client.post(
        "/api/v1/assets",
        json={"internal_name": f"pytest smp-b2 asset {suffix}", "asset_type": "mab"},
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["data"]["asset_id"]


@pytest.mark.asyncio
async def test_classification_defaults(admin_client, unique_suffix):
    """最简创建：分类三维度取 SMP-有效默认值"""
    resp = await admin_client.post(
        "/api/v1/projects",
        json={"project_name": f"pytest b2 default {unique_suffix}", "project_type": "cmc"},
    )
    assert resp.status_code == 201, resp.text
    d = resp.json()["data"]
    assert d["project_category"] == "non_asset"
    assert d["project_nature"] == "discovery"
    assert d["owning_function"] == "rd"


@pytest.mark.asyncio
async def test_asset_related_requires_asset_id(admin_client, unique_suffix):
    """SMP §7.5：asset_related 项目未给 asset_id → 400"""
    resp = await admin_client.post(
        "/api/v1/projects",
        json={
            "project_name": f"pytest b2 need-asset {unique_suffix}",
            "project_type": "cmc",
            "project_category": "asset_related",
            "project_nature": "nme",
        },
    )
    assert resp.status_code == 400, resp.text


@pytest.mark.asyncio
async def test_non_asset_rejects_asset_id(admin_client, unique_suffix):
    """SMP §8：non_asset 项目不应绑定 asset_id → 400"""
    aid = await _new_asset(admin_client, unique_suffix)
    resp = await admin_client.post(
        "/api/v1/projects",
        json={
            "project_name": f"pytest b2 non-asset {unique_suffix}",
            "project_type": "cmc",
            "project_category": "non_asset",
            "asset_id": aid,
        },
    )
    assert resp.status_code == 400, resp.text


@pytest.mark.asyncio
async def test_asset_related_with_valid_asset(admin_client, unique_suffix):
    """asset_related + 有效 asset_id → 201，详情回显分类与绑定"""
    aid = await _new_asset(admin_client, unique_suffix)
    resp = await admin_client.post(
        "/api/v1/projects",
        json={
            "project_name": f"pytest b2 ok {unique_suffix}",
            "project_type": "clinical",
            "project_phase": "p1",
            "project_category": "asset_related",
            "project_nature": "nme",
            "owning_function": "clinical",
            "asset_id": aid,
        },
    )
    assert resp.status_code == 201, resp.text
    d = resp.json()["data"]
    assert d["project_category"] == "asset_related"
    assert d["project_nature"] == "nme"
    assert d["owning_function"] == "clinical"
    assert d["asset_id"] == aid
    assert d["project_phase"] == "p1"


@pytest.mark.asyncio
async def test_bad_asset_id_rejected(admin_client, unique_suffix):
    """asset_related 指向不存在的 asset_id → 400"""
    resp = await admin_client.post(
        "/api/v1/projects",
        json={
            "project_name": f"pytest b2 bad-asset {unique_suffix}",
            "project_type": "cmc",
            "project_category": "asset_related",
            "asset_id": 999999999,
        },
    )
    assert resp.status_code == 400, resp.text


@pytest.mark.asyncio
async def test_approve_fills_approval_date(admin_client, unique_suffix):
    """SMP §10.3：approve 回填 approval_date + approval_year"""
    code = (
        await admin_client.post(
            "/api/v1/projects",
            json={"project_name": f"pytest b2 approve {unique_suffix}", "project_type": "cmc"},
        )
    ).json()["data"]["project_code"]

    resp = await admin_client.post(
        f"/api/v1/projects/{code}:approve",
        json={
            "comment": "pytest b2 审批立项回填",
            "signature": {"password": ADMIN_PASSWORD, "reason": "pytest b2 approve"},
        },
    )
    assert resp.status_code == 200, resp.text

    detail = (await admin_client.get(f"/api/v1/projects/{code}")).json()["data"]
    assert detail["approval_date"] is not None
    assert detail["approval_year"] is not None


@pytest.mark.asyncio
async def test_invalid_phase_rejected(admin_client, unique_suffix):
    """旧自由文本 phase 值（phase_1）已不再合法 → 400"""
    resp = await admin_client.post(
        "/api/v1/projects",
        json={
            "project_name": f"pytest b2 bad-phase {unique_suffix}",
            "project_type": "cmc",
            "project_phase": "phase_1",
        },
    )
    assert resp.status_code == 400, resp.text


@pytest.mark.asyncio
async def test_filter_by_category_and_nature(admin_client, unique_suffix):
    """列表按 project_category / project_nature 过滤"""
    aid = await _new_asset(admin_client, unique_suffix)
    await admin_client.post(
        "/api/v1/projects",
        json={
            "project_name": f"pytest b2 filt A {unique_suffix}",
            "project_type": "cmc",
            "project_category": "asset_related",
            "project_nature": "cmc_change",
            "regulatory_change_level": "moderate",
            "asset_id": aid,
        },
    )
    await admin_client.post(
        "/api/v1/projects",
        json={
            "project_name": f"pytest b2 filt B {unique_suffix}",
            "project_type": "cmc",
            "project_category": "non_asset",
            "project_nature": "platform",
        },
    )
    resp = await admin_client.get(
        "/api/v1/projects",
        params={"q": unique_suffix, "project_category": "asset_related", "page_size": 50},
    )
    assert resp.status_code == 200
    items = [it for it in resp.json()["data"] if unique_suffix in it["project_name"]]
    assert len(items) == 1
    assert items[0]["project_nature"] == "cmc_change"
