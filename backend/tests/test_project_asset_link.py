"""
ref.project_asset link/unlink + 反向查询测试（M3.3）

对齐 DM-MDM-001 V1.0 §11.4：
  - 复合 PK (project_id, asset_id) — relation_type 是属性，不在 PK 内
  - 一对 (project, asset) 同时只能有一个活动 relation_type
  - 软删除 deleted_at
业务规则：
  - asset.status='terminated' 禁止新建关联
"""
import pytest

ADMIN_PASSWORD = "__REDACTED_SEED_PASSWORD_1__"


async def _new_project(client, suffix: str) -> str:
    return (
        await client.post(
            "/api/v1/projects",
            json={"project_name": f"pytest pa-link {suffix}", "project_type": "cmc"},
        )
    ).json()["data"]["project_code"]


async def _new_asset(client, suffix: str, name_suffix: str = "") -> str:
    return (
        await client.post(
            "/api/v1/assets",
            json={
                "internal_name": f"pytest pa-link asset {suffix} {name_suffix}".strip(),
                "asset_type": "mab",
            },
        )
    ).json()["data"]["asset_code"]


@pytest.mark.asyncio
async def test_link_unlink_roundtrip_from_project(admin_client, unique_suffix):
    pcode = await _new_project(admin_client, unique_suffix)
    acode = await _new_asset(admin_client, unique_suffix)

    r = await admin_client.post(
        f"/api/v1/projects/{pcode}/assets",
        json={"asset_code": acode, "relation_type": "primary"},
    )
    assert r.status_code == 201, r.text
    data = r.json()["data"]
    assert data["project_code"] == pcode
    assert data["asset_code"] == acode
    assert data["relation_type"] == "primary"

    lst = await admin_client.get(f"/api/v1/projects/{pcode}/assets")
    assert lst.status_code == 200
    assert len(lst.json()["data"]) == 1

    # 反向：asset → projects
    rev = await admin_client.get(f"/api/v1/assets/{acode}/projects")
    assert rev.status_code == 200
    assert any(it["project_code"] == pcode for it in rev.json()["data"])

    # unlink from project side
    rm = await admin_client.delete(
        f"/api/v1/projects/{pcode}/assets/{acode}",
        json={"change_reason": "pytest 取消"},
    )
    assert rm.status_code == 204

    # default 不返回
    lst2 = await admin_client.get(f"/api/v1/projects/{pcode}/assets")
    assert len(lst2.json()["data"]) == 0

    # include_deleted
    lst3 = await admin_client.get(
        f"/api/v1/projects/{pcode}/assets",
        params={"include_deleted": "true"},
    )
    assert any(it["asset_code"] == acode for it in lst3.json()["data"])


@pytest.mark.asyncio
async def test_link_from_asset_side(admin_client, unique_suffix):
    """POST /assets/{code}/projects 也能创建关联"""
    pcode = await _new_project(admin_client, unique_suffix)
    acode = await _new_asset(admin_client, unique_suffix)

    r = await admin_client.post(
        f"/api/v1/assets/{acode}/projects",
        json={"project_code": pcode, "relation_type": "supporting"},
    )
    assert r.status_code == 201, r.text
    assert r.json()["data"]["relation_type"] == "supporting"

    # 双向都能看到
    fwd = await admin_client.get(f"/api/v1/projects/{pcode}/assets")
    rev = await admin_client.get(f"/api/v1/assets/{acode}/projects")
    assert len(fwd.json()["data"]) == 1
    assert len(rev.json()["data"]) == 1


@pytest.mark.asyncio
async def test_unlink_from_asset_side(admin_client, unique_suffix):
    pcode = await _new_project(admin_client, unique_suffix)
    acode = await _new_asset(admin_client, unique_suffix)
    await admin_client.post(
        f"/api/v1/projects/{pcode}/assets",
        json={"asset_code": acode, "relation_type": "primary"},
    )
    rm = await admin_client.delete(
        f"/api/v1/assets/{acode}/projects/{pcode}",
        json={"change_reason": "pytest asset side unlink"},
    )
    assert rm.status_code == 204
    fwd = await admin_client.get(f"/api/v1/projects/{pcode}/assets")
    assert len(fwd.json()["data"]) == 0


@pytest.mark.asyncio
async def test_duplicate_active_pair_rejected(admin_client, unique_suffix):
    """一对 (project, asset) 同时只允许一个活动关联（不管 relation_type）"""
    pcode = await _new_project(admin_client, unique_suffix)
    acode = await _new_asset(admin_client, unique_suffix)
    r1 = await admin_client.post(
        f"/api/v1/projects/{pcode}/assets",
        json={"asset_code": acode, "relation_type": "primary"},
    )
    assert r1.status_code == 201
    # 不同 relation_type 仍然冲突（§11.4 PK 仅含 project_id+asset_id）
    r2 = await admin_client.post(
        f"/api/v1/projects/{pcode}/assets",
        json={"asset_code": acode, "relation_type": "supporting"},
    )
    assert r2.status_code == 409


@pytest.mark.asyncio
async def test_relink_after_unlink(admin_client, unique_suffix):
    pcode = await _new_project(admin_client, unique_suffix)
    acode = await _new_asset(admin_client, unique_suffix)
    await admin_client.post(
        f"/api/v1/projects/{pcode}/assets",
        json={"asset_code": acode, "relation_type": "primary"},
    )
    await admin_client.delete(
        f"/api/v1/projects/{pcode}/assets/{acode}",
        json={"change_reason": "pytest unlink"},
    )
    # 重新绑定可以换 relation_type
    r = await admin_client.post(
        f"/api/v1/projects/{pcode}/assets",
        json={"asset_code": acode, "relation_type": "derivative"},
    )
    assert r.status_code == 201, r.text
    assert r.json()["data"]["relation_type"] == "derivative"

    lst = await admin_client.get(f"/api/v1/projects/{pcode}/assets")
    items = lst.json()["data"]
    assert len(items) == 1
    assert items[0]["relation_type"] == "derivative"


@pytest.mark.asyncio
async def test_terminated_asset_forbids_link_from_both_sides(admin_client, unique_suffix):
    """terminated 资产无论从哪一侧都不允许新建关联"""
    pcode = await _new_project(admin_client, unique_suffix)
    acode = await _new_asset(admin_client, unique_suffix)

    r = await admin_client.post(
        f"/api/v1/assets/{acode}:terminate",
        json={"change_reason": "pytest before pa link", "password": ADMIN_PASSWORD},
    )
    assert r.status_code == 200

    # 从 project 侧
    resp1 = await admin_client.post(
        f"/api/v1/projects/{pcode}/assets",
        json={"asset_code": acode, "relation_type": "primary"},
    )
    assert resp1.status_code == 400

    # 从 asset 侧
    resp2 = await admin_client.post(
        f"/api/v1/assets/{acode}/projects",
        json={"project_code": pcode, "relation_type": "primary"},
    )
    assert resp2.status_code == 400


@pytest.mark.asyncio
async def test_link_audit_inherits_project_code(admin_client, unique_suffix):
    """project_asset 触发器写 audit_log entity_code 应回填 project_code"""
    pcode = await _new_project(admin_client, unique_suffix)
    acode = await _new_asset(admin_client, unique_suffix)
    await admin_client.post(
        f"/api/v1/projects/{pcode}/assets",
        json={"asset_code": acode, "relation_type": "primary"},
    )
    logs = await admin_client.get(
        f"/api/v1/projects/{pcode}/audit-logs",
        params={"include_children": "true", "page_size": 50},
    )
    items = logs.json()["data"]
    link_creates = [
        it for it in items
        if it["entity_table"] == "project_asset" and it["action"] == "CREATE"
    ]
    assert link_creates, "应至少一条 project_asset CREATE 审计"
    assert all(it["entity_code"] == pcode for it in link_creates)
