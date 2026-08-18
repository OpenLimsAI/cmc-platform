"""
ref.molecule_target 分子↔靶点关联 + tgt.target_source_snapshot 快照 测试

  - 关联 PK (molecule_id, target_id, relation_role)：同键重复 409；软删后重新关联 = 重激活
  - relation_role 枚举 antibody_target / payload_target / other（ADC 载荷靶点保留）
  - 反向查询 GET /targets/by-molecule/{substance_code}
  - 快照 append-only：POST 追加、列表不带 payload、详情带 payload
"""
import pytest


async def _new_substance(client, suffix: str) -> str:
    return (
        await client.post(
            "/api/v1/substances",
            json={
                "substance_type": "adc",
                "internal_code": f"TEST-TGT-{suffix}",
                "preferred_name": f"pytest adc {suffix}",
            },
        )
    ).json()["data"]["substance_code"]


async def _new_target(client, suffix: str, **over) -> str:
    body = {
        "target_name": f"pytest link target {suffix}",
        "target_type": "受体",
        "target_location": "膜型",
    }
    body.update(over)
    r = await client.post("/api/v1/targets", json=body)
    assert r.status_code == 201, r.text
    return r.json()["data"]["target_code"]


@pytest.mark.asyncio
async def test_link_unlink_relink_roundtrip(admin_client, unique_suffix):
    scode = await _new_substance(admin_client, unique_suffix)
    tcode = await _new_target(admin_client, unique_suffix)

    link = await admin_client.post(
        f"/api/v1/targets/{tcode}/molecules",
        json={
            "substance_code": scode,
            "relation_role": "antibody_target",
            "moa": "Receptor protein-tyrosine kinase erbB-2 binding agent",
            "action_type": "BINDING AGENT",
            "chembl_mechanism_id": 7490,
            "needs_confirm": True,
        },
    )
    assert link.status_code == 201, link.text
    d = link.json()["data"]
    assert d["substance_code"] == scode and d["target_code"] == tcode
    assert d["relation_role"] == "antibody_target"
    assert d["needs_confirm"] is True

    # 同键重复 → 409
    dup = await admin_client.post(
        f"/api/v1/targets/{tcode}/molecules",
        json={"substance_code": scode, "relation_role": "antibody_target"},
    )
    assert dup.status_code == 409, dup.text

    # 同分子不同角色（ADC 载荷）→ 允许
    payload_link = await admin_client.post(
        f"/api/v1/targets/{tcode}/molecules",
        json={"substance_code": scode, "relation_role": "payload_target", "moa": "DNA topoisomerase I inhibitor"},
    )
    assert payload_link.status_code == 201, payload_link.text

    lst = await admin_client.get(f"/api/v1/targets/{tcode}/molecules")
    assert lst.status_code == 200
    assert sorted(x["relation_role"] for x in lst.json()["data"]) == ["antibody_target", "payload_target"]

    # 反向：分子 → 靶点
    rev = await admin_client.get(f"/api/v1/targets/by-molecule/{scode}")
    assert rev.status_code == 200
    assert {x["target_code"] for x in rev.json()["data"]} == {tcode}
    assert len(rev.json()["data"]) == 2

    # 更新关联属性（人工确认）
    upd = await admin_client.put(
        f"/api/v1/targets/{tcode}/molecules/{scode}/antibody_target",
        json={"needs_confirm": False, "binding_epitope_or_domain": "domain IV", "change_reason": "人工核对结合域"},
    )
    assert upd.status_code == 200, upd.text
    assert upd.json()["data"]["needs_confirm"] is False
    assert upd.json()["data"]["binding_epitope_or_domain"] == "domain IV"

    # 取消关联（软删）→ 列表少一条
    rm = await admin_client.delete(
        f"/api/v1/targets/{tcode}/molecules/{scode}/payload_target",
        json={"change_reason": "载荷靶点业务决定不录"},
    )
    assert rm.status_code == 204, rm.text
    lst = await admin_client.get(f"/api/v1/targets/{tcode}/molecules")
    assert [x["relation_role"] for x in lst.json()["data"]] == ["antibody_target"]

    # 再次关联同键 → 重激活（201，不撞 PK）
    re_link = await admin_client.post(
        f"/api/v1/targets/{tcode}/molecules",
        json={"substance_code": scode, "relation_role": "payload_target", "notes": "重新录入"},
    )
    assert re_link.status_code == 201, re_link.text
    assert re_link.json()["data"]["notes"] == "重新录入"


@pytest.mark.asyncio
async def test_link_validation_and_404(admin_client, unique_suffix):
    tcode = await _new_target(admin_client, unique_suffix)
    r = await admin_client.post(
        f"/api/v1/targets/{tcode}/molecules",
        json={"substance_code": "SUB-9999999", "relation_role": "antibody_target"},
    )
    assert r.status_code == 404
    scode = await _new_substance(admin_client, unique_suffix)
    r = await admin_client.post(
        f"/api/v1/targets/{tcode}/molecules",
        json={"substance_code": scode, "relation_role": "not_a_role"},
    )
    assert r.status_code == 400
    r = await admin_client.get("/api/v1/targets/TGT-999999/molecules")
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_link_permission(readonly_client, admin_client, unique_suffix):
    scode = await _new_substance(admin_client, unique_suffix)
    tcode = await _new_target(admin_client, unique_suffix)
    r = await readonly_client.post(
        f"/api/v1/targets/{tcode}/molecules",
        json={"substance_code": scode, "relation_role": "antibody_target"},
    )
    assert r.status_code == 403
    r = await readonly_client.get(f"/api/v1/targets/{tcode}/molecules")
    assert r.status_code == 200


@pytest.mark.asyncio
async def test_snapshot_append_only(admin_client, readonly_client, unique_suffix):
    tcode = await _new_target(admin_client, unique_suffix)
    payload = {
        "source": "uniprot",
        "source_id": "Q15116",
        "source_version": "entryVersion=200",
        "source_url": "https://rest.uniprot.org/uniprotkb/Q15116.json",
        "fetched_at": "2026-08-17T13:30:58+00:00",
        "payload": {"primaryAccession": "Q15116", "genes": [{"geneName": {"value": "PDCD1"}}]},
        "license": "CC BY 4.0 (UniProt)",
    }
    r = await admin_client.post(f"/api/v1/targets/{tcode}/snapshots", json=payload)
    assert r.status_code == 201, r.text
    sid = r.json()["data"]["snapshot_id"]
    assert "payload" not in r.json()["data"]

    r2 = await admin_client.post(f"/api/v1/targets/{tcode}/snapshots", json={**payload, "source": "chembl_target", "source_id": "CHEMBL3307223"})
    assert r2.status_code == 201

    lst = await admin_client.get(f"/api/v1/targets/{tcode}/snapshots")
    assert lst.status_code == 200
    assert {x["source"] for x in lst.json()["data"]} == {"uniprot", "chembl_target"}
    assert all("payload" not in x for x in lst.json()["data"])

    det = await admin_client.get(f"/api/v1/targets/{tcode}/snapshots/{sid}")
    assert det.status_code == 200
    assert det.json()["data"]["payload"]["primaryAccession"] == "Q15116"

    bad = await admin_client.post(f"/api/v1/targets/{tcode}/snapshots", json={**payload, "source": "wikipedia"})
    assert bad.status_code == 400

    r = await readonly_client.post(f"/api/v1/targets/{tcode}/snapshots", json=payload)
    assert r.status_code == 403
