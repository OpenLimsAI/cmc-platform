"""
SMP-RD-NUM-001 V2.1 第三批测试：
C1 §7A 上市后变更条件校验 + C3 legacy 编号
C2 §11.4-11.6 项目关系（合并/拆分/衍生）
"""
import pytest

ADMIN_PASSWORD = "__REDACTED_SEED_PASSWORD_1__"


async def _new_project(client, suffix: str, extra: dict | None = None) -> str:
    body = {"project_name": f"pytest b3 {suffix}", "project_type": "cmc"}
    if extra:
        body.update(extra)
    resp = await client.post("/api/v1/projects", json=body)
    assert resp.status_code == 201, resp.text
    return resp.json()["data"]["project_code"]


# ---------------- C1 §7A ----------------
@pytest.mark.asyncio
async def test_cmc_change_requires_level(admin_client, unique_suffix):
    """project_nature=cmc_change 未填变更级别 → 400"""
    resp = await admin_client.post(
        "/api/v1/projects",
        json={
            "project_name": f"pytest b3 cmc-change {unique_suffix}",
            "project_type": "cmc",
            "project_nature": "cmc_change",
        },
    )
    assert resp.status_code == 400, resp.text


@pytest.mark.asyncio
async def test_cmc_change_with_level_ok(admin_client, unique_suffix):
    code = await _new_project(
        admin_client,
        f"cmc-ok {unique_suffix}",
        {"project_nature": "cmc_change", "regulatory_change_level": "moderate"},
    )
    d = (await admin_client.get(f"/api/v1/projects/{code}")).json()["data"]
    assert d["regulatory_change_level"] == "moderate"


@pytest.mark.asyncio
async def test_major_coerces_pre_approval(admin_client, unique_suffix):
    """major 级未显式给 pre_approval → 服务端强制 true"""
    code = await _new_project(
        admin_client,
        f"major {unique_suffix}",
        {"project_nature": "cmc_change", "regulatory_change_level": "major"},
    )
    d = (await admin_client.get(f"/api/v1/projects/{code}")).json()["data"]
    assert d["pre_approval_required"] is True


@pytest.mark.asyncio
async def test_major_reject_pre_approval_false(admin_client, unique_suffix):
    """major 级显式 pre_approval=false → 400"""
    resp = await admin_client.post(
        "/api/v1/projects",
        json={
            "project_name": f"pytest b3 major-false {unique_suffix}",
            "project_type": "cmc",
            "project_nature": "cmc_change",
            "regulatory_change_level": "major",
            "pre_approval_required": False,
        },
    )
    assert resp.status_code == 400, resp.text


@pytest.mark.asyncio
async def test_legacy_project_id_stored(admin_client, unique_suffix):
    code = await _new_project(
        admin_client, f"legacy {unique_suffix}", {"legacy_project_id": "PRJ-2024-011"}
    )
    d = (await admin_client.get(f"/api/v1/projects/{code}")).json()["data"]
    assert d["legacy_project_id"] == "PRJ-2024-011"


# ---------------- C2 §11.4-11.6 关系 ----------------
@pytest.mark.asyncio
async def test_relationship_roundtrip(admin_client, unique_suffix):
    """A derived_from B：A 侧 outgoing，B 侧 incoming"""
    a = await _new_project(admin_client, f"rel-A {unique_suffix}")
    b = await _new_project(admin_client, f"rel-B {unique_suffix}")

    r = await admin_client.post(
        f"/api/v1/projects/{a}/relationships",
        json={"to_project_code": b, "relationship_type": "derived_from", "notes": "拆分衍生"},
    )
    assert r.status_code == 201, r.text

    a_rels = (await admin_client.get(f"/api/v1/projects/{a}/relationships")).json()["data"]
    assert len(a_rels) == 1
    assert a_rels[0]["direction"] == "outgoing"
    assert a_rels[0]["other_project_code"] == b
    assert a_rels[0]["relationship_type"] == "derived_from"

    b_rels = (await admin_client.get(f"/api/v1/projects/{b}/relationships")).json()["data"]
    assert len(b_rels) == 1
    assert b_rels[0]["direction"] == "incoming"
    assert b_rels[0]["other_project_code"] == a

    # 删除
    rid = a_rels[0]["relationship_id"]
    dr = await admin_client.delete(f"/api/v1/projects/{a}/relationships/{rid}")
    assert dr.status_code == 204, dr.text
    after = (await admin_client.get(f"/api/v1/projects/{a}/relationships")).json()["data"]
    assert len(after) == 0


@pytest.mark.asyncio
async def test_relationship_self_rejected(admin_client, unique_suffix):
    a = await _new_project(admin_client, f"rel-self {unique_suffix}")
    r = await admin_client.post(
        f"/api/v1/projects/{a}/relationships",
        json={"to_project_code": a, "relationship_type": "blocks"},
    )
    assert r.status_code == 400, r.text


@pytest.mark.asyncio
async def test_relationship_duplicate_rejected(admin_client, unique_suffix):
    a = await _new_project(admin_client, f"rel-dupA {unique_suffix}")
    b = await _new_project(admin_client, f"rel-dupB {unique_suffix}")
    body = {"to_project_code": b, "relationship_type": "depends_on"}
    r1 = await admin_client.post(f"/api/v1/projects/{a}/relationships", json=body)
    assert r1.status_code == 201, r1.text
    r2 = await admin_client.post(f"/api/v1/projects/{a}/relationships", json=body)
    assert r2.status_code == 409, r2.text
