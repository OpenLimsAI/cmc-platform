"""
ref.asset_substance link/unlink + 反向查询测试（M3.3）

对齐 DM-MDM-001 V1.0 §11.3：
  - 复合 PK (asset_id, substance_id, component_role)
  - component_role ∈ {main_component/antibody/linker/payload/excipient/impurity}
  - 软删除 deleted_at
业务规则：
  - asset.status='terminated' 禁止新建关联
  - substance.status='obsoleted' 禁止新建关联
"""
import pytest

ADMIN_PASSWORD = "__REDACTED_SEED_PASSWORD_1__"


async def _new_asset(client, suffix: str, name_suffix: str = "") -> str:
    return (
        await client.post(
            "/api/v1/assets",
            json={
                "internal_name": f"pytest asas {suffix} {name_suffix}".strip(),
                "asset_type": "adc",
            },
        )
    ).json()["data"]["asset_code"]


async def _new_substance(client, suffix: str, internal_suffix: str = "") -> str:
    payload = {
        "substance_type": "mab",
        "internal_code": f"TEST-AS-{internal_suffix or suffix}",
        "preferred_name": f"pytest as sub {suffix} {internal_suffix}",
    }
    return (
        await client.post("/api/v1/substances", json=payload)
    ).json()["data"]["substance_code"]


@pytest.mark.asyncio
async def test_link_unlink_roundtrip(admin_client, unique_suffix):
    acode = await _new_asset(admin_client, unique_suffix)
    scode = await _new_substance(admin_client, unique_suffix)

    r = await admin_client.post(
        f"/api/v1/assets/{acode}/substances",
        json={"substance_code": scode, "component_role": "antibody"},
    )
    assert r.status_code == 201, r.text
    data = r.json()["data"]
    assert data["substance_code"] == scode
    assert data["component_role"] == "antibody"
    assert data["asset_code"] == acode

    # 正向列表
    lst = await admin_client.get(f"/api/v1/assets/{acode}/substances")
    assert lst.status_code == 200
    assert len(lst.json()["data"]) == 1

    # 反向：substance → assets
    rev = await admin_client.get(f"/api/v1/substances/{scode}/assets")
    assert rev.status_code == 200
    assert any(it["asset_code"] == acode for it in rev.json()["data"])

    # unlink
    rm = await admin_client.delete(
        f"/api/v1/assets/{acode}/substances/{scode}/antibody",
        json={"change_reason": "pytest 取消组分"},
    )
    assert rm.status_code == 204

    # 默认不返回已取消
    lst2 = await admin_client.get(f"/api/v1/assets/{acode}/substances")
    assert len(lst2.json()["data"]) == 0

    # include_deleted=true 可见
    lst3 = await admin_client.get(
        f"/api/v1/assets/{acode}/substances",
        params={"include_deleted": "true"},
    )
    assert any(it["substance_code"] == scode for it in lst3.json()["data"])


@pytest.mark.asyncio
async def test_duplicate_active_role_rejected(admin_client, unique_suffix):
    acode = await _new_asset(admin_client, unique_suffix)
    scode = await _new_substance(admin_client, unique_suffix)
    payload = {"substance_code": scode, "component_role": "main_component"}

    r1 = await admin_client.post(f"/api/v1/assets/{acode}/substances", json=payload)
    assert r1.status_code == 201
    r2 = await admin_client.post(f"/api/v1/assets/{acode}/substances", json=payload)
    assert r2.status_code == 409


@pytest.mark.asyncio
async def test_different_component_roles_coexist(admin_client, unique_suffix):
    """ADC 场景：同一资产 + 同一物质可用不同 component_role 多次绑定"""
    acode = await _new_asset(admin_client, unique_suffix)
    scode = await _new_substance(admin_client, unique_suffix)
    for role in ["antibody", "linker", "payload"]:
        r = await admin_client.post(
            f"/api/v1/assets/{acode}/substances",
            json={"substance_code": scode, "component_role": role},
        )
        assert r.status_code == 201, f"{role} 失败: {r.text}"
    lst = await admin_client.get(f"/api/v1/assets/{acode}/substances")
    assert len(lst.json()["data"]) == 3


@pytest.mark.asyncio
async def test_relink_after_unlink(admin_client, unique_suffix):
    acode = await _new_asset(admin_client, unique_suffix)
    scode = await _new_substance(admin_client, unique_suffix)
    payload = {"substance_code": scode, "component_role": "excipient"}
    r1 = await admin_client.post(f"/api/v1/assets/{acode}/substances", json=payload)
    assert r1.status_code == 201
    rm = await admin_client.delete(
        f"/api/v1/assets/{acode}/substances/{scode}/excipient",
        json={"change_reason": "pytest unlink"},
    )
    assert rm.status_code == 204
    r2 = await admin_client.post(f"/api/v1/assets/{acode}/substances", json=payload)
    assert r2.status_code == 201, r2.text
    lst = await admin_client.get(f"/api/v1/assets/{acode}/substances")
    assert len(lst.json()["data"]) == 1


@pytest.mark.asyncio
async def test_invalid_component_role_rejected(admin_client, unique_suffix):
    acode = await _new_asset(admin_client, unique_suffix)
    scode = await _new_substance(admin_client, unique_suffix)
    r = await admin_client.post(
        f"/api/v1/assets/{acode}/substances",
        json={"substance_code": scode, "component_role": "vehicle"},  # 不在枚举
    )
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_terminated_asset_forbids_new_link(admin_client, unique_suffix):
    """terminated 资产禁止新建组分关联（业务规则）"""
    acode = await _new_asset(admin_client, unique_suffix)
    scode = await _new_substance(admin_client, unique_suffix)
    # terminate the asset
    r = await admin_client.post(
        f"/api/v1/assets/{acode}:terminate",
        json={
            "comment": "pytest terminate before link",
            "signature": {"password": ADMIN_PASSWORD, "reason": "pytest terminate 签名"},
        },
    )
    assert r.status_code == 200
    # 再绑定应被拒
    resp = await admin_client.post(
        f"/api/v1/assets/{acode}/substances",
        json={"substance_code": scode, "component_role": "antibody"},
    )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_obsoleted_substance_forbids_new_link(admin_client, unique_suffix):
    """obsoleted 物质禁止参与资产组分关联"""
    acode = await _new_asset(admin_client, unique_suffix)
    scode = await _new_substance(admin_client, unique_suffix)
    for action in ["approve", "activate", "deprecate", "obsolete"]:
        r = await admin_client.post(
            f"/api/v1/substances/{scode}:{action}",
            json={
                "comment": f"pytest 推 {action}",
                "signature": {"password": ADMIN_PASSWORD, "reason": f"pytest {action} 签名"},
            },
        )
        assert r.status_code == 200
    resp = await admin_client.post(
        f"/api/v1/assets/{acode}/substances",
        json={"substance_code": scode, "component_role": "antibody"},
    )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_unlinked_record_exposes_deleted_by(admin_client, unique_suffix):
    """R6（DEV-MDM-001 V1.2 Batch F）：unlink 后 include_deleted=true 列表项应暴露 deleted_by。"""
    acode = await _new_asset(admin_client, unique_suffix)
    scode = await _new_substance(admin_client, unique_suffix)
    await admin_client.post(
        f"/api/v1/assets/{acode}/substances",
        json={"substance_code": scode, "component_role": "antibody"},
    )
    unlink_resp = await admin_client.delete(
        f"/api/v1/assets/{acode}/substances/{scode}/antibody",
        json={"change_reason": "pytest unlink for deleted_by 暴露"},
    )
    assert unlink_resp.status_code == 204

    list_resp = await admin_client.get(
        f"/api/v1/assets/{acode}/substances",
        params={"include_deleted": "true"},
    )
    items = list_resp.json()["data"]
    soft_deleted = [it for it in items if it["substance_code"] == scode and it["deleted_at"]]
    assert soft_deleted, "include_deleted=true 时应能看到刚 unlink 的记录"
    assert soft_deleted[0]["deleted_by"] is not None, "schema 暴露 deleted_by 后应非空"


@pytest.mark.asyncio
async def test_link_audit_inherits_asset_code(admin_client, unique_suffix):
    """ref.asset_substance 触发器写 audit_log 时 entity_code 应回填 asset_code"""
    acode = await _new_asset(admin_client, unique_suffix)
    scode = await _new_substance(admin_client, unique_suffix)
    await admin_client.post(
        f"/api/v1/assets/{acode}/substances",
        json={"substance_code": scode, "component_role": "main_component"},
    )
    logs = await admin_client.get(
        f"/api/v1/assets/{acode}/audit-logs",
        params={"include_children": "true", "page_size": 50},
    )
    items = logs.json()["data"]
    link_creates = [
        it for it in items
        if it["entity_table"] == "asset_substance" and it["action"] == "CREATE"
    ]
    assert link_creates, "应至少一条 asset_substance CREATE 审计"
    assert all(it["entity_code"] == acode for it in link_creates), (
        f"audit entity_code 应回填 asset_code={acode}"
    )
