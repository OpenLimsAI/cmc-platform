"""
substance ↔ material 跨域反向 + 业务规则测试（M4.3）

对齐 DM-MDM-001 V1.1 §10.1 + §11.1 + API-MDM-001 V1.1 §5.1.2
"""
import pytest


async def _drive_substance_to(client, sub_code: str, target: str, password: str = "__REDACTED_SEED_PASSWORD_1__"):
    """走完 SRS 状态机：draft → registered → active → restricted? → deprecated → obsoleted

    target ∈ {registered, active, deprecated, obsoleted}
    """
    chain = ["registered", "active", "deprecated", "obsoleted"]
    actions = {
        "registered": "approve",
        "active": "activate",
        "deprecated": "deprecate",
        "obsoleted": "obsolete",
    }
    for step in chain:
        resp = await client.post(
            f"/api/v1/substances/{sub_code}:{actions[step]}",
            json={
                "comment": f"pytest 推进到 {step}",
                "signature": {
                    "password": password,
                    "meaning": "approve" if step in ("registered", "active") else "reject",
                    "reason": f"测试链路推进至 {step}",
                },
            },
        )
        assert resp.status_code == 200, f"状态机 {actions[step]} 失败: {resp.text}"
        if step == target:
            return
    if target not in chain:
        raise ValueError(f"unknown target: {target}")


@pytest.mark.asyncio
async def test_substance_materials_reverse_query(admin_client, unique_suffix):
    """GET /substances/{code}/materials 反向查询"""
    sub = await admin_client.post(
        "/api/v1/substances",
        json={
            "substance_type": "mab",
            "internal_code": f"REV-{unique_suffix}",
            "preferred_name": f"reverse query base {unique_suffix}",
        },
    )
    sub_code = sub.json()["data"]["substance_code"]

    for tag in ("A", "B"):
        await admin_client.post(
            "/api/v1/materials",
            json={
                "material_code": f"LK{tag}-{unique_suffix[:6]}",
                "material_name": f"link mat {tag} {unique_suffix}",
                "material_type": "reagent",
                "substance_code": sub_code,
            },
        )

    # 反向查询
    resp = await admin_client.get(f"/api/v1/substances/{sub_code}/materials")
    assert resp.status_code == 200
    items = resp.json()["data"]
    assert len(items) == 2
    assert all(it["substance_code"] == sub_code for it in items)


@pytest.mark.asyncio
async def test_substance_brief_includes_material_count(admin_client, unique_suffix):
    """V1.1 §6.1 UI6 要求：substance 列表项含 material_count"""
    sub = await admin_client.post(
        "/api/v1/substances",
        json={
            "substance_type": "mab",
            "internal_code": f"CNT-{unique_suffix}",
            "preferred_name": f"count base {unique_suffix}",
        },
    )
    sub_code = sub.json()["data"]["substance_code"]

    # 列表初值
    list_resp = await admin_client.get(
        "/api/v1/substances", params={"q": f"CNT-{unique_suffix}"}
    )
    item0 = [it for it in list_resp.json()["data"] if it["substance_code"] == sub_code][0]
    assert item0["material_count"] == 0

    for i in range(3):
        await admin_client.post(
            "/api/v1/materials",
            json={
                "material_code": f"CN{i}-{unique_suffix[:6]}",
                "material_name": f"cnt mat {i} {unique_suffix}",
                "material_type": "consumable",
                "substance_code": sub_code,
            },
        )

    list_resp2 = await admin_client.get(
        "/api/v1/substances", params={"q": f"CNT-{unique_suffix}"}
    )
    item3 = [it for it in list_resp2.json()["data"] if it["substance_code"] == sub_code][0]
    assert item3["material_count"] == 3


@pytest.mark.asyncio
async def test_obsoleted_substance_rejects_new_material(admin_client, unique_suffix):
    """V1.1 §11.1 业务规则：obsoleted 物质不允许新建物料引用（应用层）"""
    sub = await admin_client.post(
        "/api/v1/substances",
        json={
            "substance_type": "mab",
            "internal_code": f"OBS-{unique_suffix}",
            "preferred_name": f"obsolete base {unique_suffix}",
        },
    )
    sub_code = sub.json()["data"]["substance_code"]
    # 走状态机到 obsoleted
    await _drive_substance_to(admin_client, sub_code, "obsoleted")

    # 验证 obsoleted 后绑定被拒
    mat_resp = await admin_client.post(
        "/api/v1/materials",
        json={
            "material_code": f"FB-{unique_suffix[:7]}",
            "material_name": f"forbidden mat {unique_suffix}",
            "material_type": "reagent",
            "substance_code": sub_code,
        },
    )
    assert mat_resp.status_code == 403
    assert mat_resp.json()["code"] == 40304  # OperationNotAllowedError


@pytest.mark.asyncio
async def test_substance_materials_404_for_missing(admin_client, unique_suffix):
    """反向查询不存在的 substance 应返回 404 / 40402"""
    resp = await admin_client.get("/api/v1/substances/SUB-9999999/materials")
    assert resp.status_code == 404
    assert resp.json()["code"] == 40402


@pytest.mark.asyncio
async def test_readonly_can_query_substance_materials(readonly_client, admin_client, unique_suffix):
    """权限：material:read 即可走反向查询"""
    sub = await admin_client.post(
        "/api/v1/substances",
        json={
            "substance_type": "mab",
            "internal_code": f"RO-{unique_suffix}",
            "preferred_name": f"readonly base {unique_suffix}",
        },
    )
    sub_code = sub.json()["data"]["substance_code"]
    resp = await readonly_client.get(f"/api/v1/substances/{sub_code}/materials")
    assert resp.status_code == 200
