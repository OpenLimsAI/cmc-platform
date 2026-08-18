"""
靶点域（tgt.target）CRUD / 取号 / 查重 / 轻档审核 / 权限 测试

0050_tgt_target：
  - target_code 由触发器取号 TGT-NNNNNN
  - uniprot_id 查重同时匹配主 + 次级 accession（aliases）
  - status draft → published → retired（:publish / :retire，需 change_reason，无电签）
  - 0051：字段对齐 UniProt 标准（keywords / subcellular_locations / cd_antigen_names…），无自定义枚举
  - 软删需 change_reason ≥5 字符
"""
import uuid

import pytest


def _payload(suffix: str, **over):
    base = {
        "target_name": f"pytest target {suffix}",
        "gene_symbol": f"GENE{suffix[:6].upper()}",
    }
    base.update(over)
    return base


def _fake_accession(suffix: str) -> str:
    """由 8 位 hex 后缀造一个合法 UniProt accession（10 位形式 [A-NR-Z][0-9]([A-Z][A-Z0-9]{2}[0-9]){2}），
    几乎不可能撞真实条目，也不易在同一轮测试内互撞。"""
    h = (suffix + "00000000")[:8].lower()

    def letter(c: str) -> str:
        return "ABCDEFGHIJKLMNRS"[int(c, 16)]  # 跳过 O/P/Q（那是另一种形式的首字母）

    def digit(c: str) -> str:
        return str(int(c, 16) % 10)

    return f"A0{letter(h[0])}{h[1:3].upper()}{digit(h[3])}{letter(h[4])}{h[5:7].upper()}{digit(h[7])}"


@pytest.mark.asyncio
async def test_create_target_auto_code_and_defaults(admin_client, unique_suffix):
    resp = await admin_client.post("/api/v1/targets", json=_payload(unique_suffix))
    assert resp.status_code == 201, resp.text
    d = resp.json()["data"]
    assert d["target_code"].startswith("TGT-")
    assert len(d["target_code"]) == len("TGT-000001")
    assert d["status"] == "draft"
    assert d["organism"] == "Homo sapiens"
    assert resp.headers.get("Location") == f"/api/v1/targets/{d['target_code']}"


@pytest.mark.asyncio
async def test_uniprot_normalized_and_deduped_by_secondary_accession(admin_client, unique_suffix):
    acc = _fake_accession(unique_suffix)
    secondary = _fake_accession(unique_suffix[::-1])
    r1 = await admin_client.post(
        "/api/v1/targets",
        json=_payload(unique_suffix, uniprot_id=acc.lower(), aliases=["alias-x", secondary]),
    )
    assert r1.status_code == 201, r1.text
    assert r1.json()["data"]["uniprot_id"] == acc  # 大写归一

    # 主 accession 重复 → 409
    r2 = await admin_client.post("/api/v1/targets", json=_payload(unique_suffix + "b", uniprot_id=acc))
    assert r2.status_code == 409, r2.text
    assert r2.json()["meta"]["error"]["type"] == "conflict"

    # 次级 accession（在 aliases 里）重复 → 409（PoC 结论：必须同时匹配主+次级）
    r3 = await admin_client.post("/api/v1/targets", json=_payload(unique_suffix + "c", uniprot_id=secondary))
    assert r3.status_code == 409, r3.text

    # 按 uniprot_id 精确过滤
    lst = await admin_client.get(f"/api/v1/targets?uniprot_id={acc.lower()}")
    assert lst.status_code == 200
    assert [t["uniprot_id"] for t in lst.json()["data"]] == [acc]


@pytest.mark.asyncio
async def test_invalid_uniprot_accession_rejected(admin_client, unique_suffix):
    r = await admin_client.post("/api/v1/targets", json=_payload(unique_suffix, uniprot_id="XYZ"))
    assert r.status_code == 400, r.text
    assert r.json()["meta"]["error"]["type"] == "validation_failed"


@pytest.mark.asyncio
async def test_uniprot_standard_fields_roundtrip(admin_client, unique_suffix):
    """0051：keywords / subcellular_locations / cd_antigen_names / ec_numbers / domains 等标准字段往返"""
    body = _payload(
        unique_suffix,
        cd_antigen_names=["CD279"],
        gene_synonyms=["PD1", "SLEB2"],
        tax_id=9606,
        entry_type="UniProtKB reviewed (Swiss-Prot)",
        protein_existence="1: Evidence at protein level",
        keywords=[{"id": "KW-0675", "name": "Receptor", "category": "Molecular function"},
                  {"id": "KW-0472", "name": "Membrane", "category": "Cellular component"}],
        subcellular_locations=[{"id": "SL-0039", "location": "Cell membrane",
                                "topology": "Single-pass type I membrane protein", "topology_id": "SL-9905"}],
        ec_numbers=["2.7.10.1"],
        domains=[{"type": "Domain", "description": "Ig-like V-type", "start": 35, "end": 145}],
        sequence_length=288, mol_weight=31647, sequence_md5="ABCDEF0123456789ABCDEF0123456789",
        uniprot_entry_version=207, uniprot_fetched_at="2026-08-18T05:00:00+00:00",
    )
    r = await admin_client.post("/api/v1/targets", json=body)
    assert r.status_code == 201, r.text
    d = r.json()["data"]
    assert d["cd_antigen_names"] == ["CD279"]
    assert d["keywords"][0]["name"] == "Receptor" and d["keywords"][0]["id"] == "KW-0675"
    assert d["subcellular_locations"][0]["topology"] == "Single-pass type I membrane protein"
    assert d["ec_numbers"] == ["2.7.10.1"] and d["domains"][0]["end"] == 145
    assert d["uniprot_entry_version"] == 207 and d["uniprot_fetched_at"].startswith("2026-08-18T05:00:00")
    # 列表精简项也带 keywords / cd
    lst = await admin_client.get(f"/api/v1/targets?uniprot_id=&q=GENE{unique_suffix[:6].upper()}")
    assert lst.json()["data"][0]["cd_antigen_names"] == ["CD279"]


@pytest.mark.asyncio
async def test_bad_nested_field_rejected(admin_client, unique_suffix):
    r = await admin_client.post("/api/v1/targets", json=_payload(unique_suffix, keywords=[{"category": "x"}]))  # 缺 name
    assert r.status_code == 400
    r = await admin_client.post("/api/v1/targets", json=_payload(unique_suffix, tax_id="human"))
    assert r.status_code == 400


@pytest.mark.asyncio
async def test_update_and_soft_delete(admin_client, unique_suffix):
    code = (await admin_client.post("/api/v1/targets", json=_payload(unique_suffix))).json()["data"]["target_code"]

    upd = await admin_client.put(
        f"/api/v1/targets/{code}",
        json={"notes": "膜结合前体可脱落", "cd_antigen_names": ["CD340"], "change_reason": "pytest 补 CD 号"},
    )
    assert upd.status_code == 200, upd.text
    assert upd.json()["data"]["cd_antigen_names"] == ["CD340"]

    got = await admin_client.get(f"/api/v1/targets/{code}")
    assert got.json()["data"]["notes"] == "膜结合前体可脱落"

    # 删除原因太短 → 400
    bad = await admin_client.delete(f"/api/v1/targets/{code}", json={"change_reason": "短"})
    assert bad.status_code == 400
    ok = await admin_client.delete(f"/api/v1/targets/{code}", json={"change_reason": "pytest 清理测试数据"})
    assert ok.status_code == 204
    assert (await admin_client.get(f"/api/v1/targets/{code}")).status_code == 404


@pytest.mark.asyncio
async def test_publish_retire_lifecycle(admin_client, unique_suffix):
    code = (await admin_client.post("/api/v1/targets", json=_payload(unique_suffix))).json()["data"]["target_code"]

    # 原因太短
    r = await admin_client.post(f"/api/v1/targets/{code}:publish", json={"change_reason": "ok"})
    assert r.status_code == 400
    r = await admin_client.post(f"/api/v1/targets/{code}:publish", json={"change_reason": "人工核对完成，发布"})
    assert r.status_code == 200, r.text
    assert r.json()["data"]["status"] == "published"
    # 已发布再发布 → 403 operation_not_allowed
    r = await admin_client.post(f"/api/v1/targets/{code}:publish", json={"change_reason": "重复发布应被拒"})
    assert r.status_code == 403, r.text
    assert r.json()["meta"]["error"]["type"] == "operation_not_allowed"
    r = await admin_client.post(f"/api/v1/targets/{code}:retire", json={"change_reason": "靶点合并到别的记录"})
    assert r.status_code == 200
    assert r.json()["data"]["status"] == "retired"
    # retired 可重新发布
    r = await admin_client.post(f"/api/v1/targets/{code}:publish", json={"change_reason": "误退役，恢复发布"})
    assert r.status_code == 200
    assert r.json()["data"]["status"] == "published"


@pytest.mark.asyncio
async def test_list_filters_and_search(admin_client, unique_suffix):
    await admin_client.post(
        "/api/v1/targets",
        json=_payload(
            unique_suffix,
            aliases=[f"ALIAS{unique_suffix}"],
            entry_type="UniProtKB reviewed (Swiss-Prot)",
            keywords=[{"id": "KW-0202", "name": "Cytokine", "category": "Molecular function"}],
            subcellular_locations=[{"id": "SL-0243", "location": "Secreted"}],
        ),
    )
    r = await admin_client.get(f"/api/v1/targets?q=ALIAS{unique_suffix}")
    assert r.status_code == 200
    assert r.json()["meta"]["pagination"]["total"] == 1
    base = f"/api/v1/targets?q=pytest+target+{unique_suffix}"
    assert (await admin_client.get(f"{base}&keyword=Cytokine")).json()["meta"]["pagination"]["total"] == 1
    assert (await admin_client.get(f"{base}&keyword=Cytokine&keyword_category=Molecular+function")).json()["meta"]["pagination"]["total"] == 1
    assert (await admin_client.get(f"{base}&keyword=Receptor")).json()["meta"]["pagination"]["total"] == 0
    assert (await admin_client.get(f"{base}&location=Secreted")).json()["meta"]["pagination"]["total"] == 1
    assert (await admin_client.get(f"{base}&location=Nucleus")).json()["meta"]["pagination"]["total"] == 0
    assert (await admin_client.get(f"{base}&entry_type=Swiss-Prot&status=draft")).json()["meta"]["pagination"]["total"] == 1


@pytest.mark.asyncio
async def test_permissions(researcher_client, readonly_client, admin_client, unique_suffix):
    # 研究员：可建可改，不能发布
    r = await researcher_client.post("/api/v1/targets", json=_payload(unique_suffix))
    assert r.status_code == 201, r.text
    code = r.json()["data"]["target_code"]
    r = await researcher_client.post(f"/api/v1/targets/{code}:publish", json={"change_reason": "研究员不该能发布"})
    assert r.status_code == 403
    # 只读：能看不能建
    r = await readonly_client.get(f"/api/v1/targets/{code}")
    assert r.status_code == 200
    r = await readonly_client.post("/api/v1/targets", json=_payload(unique_suffix + "ro"))
    assert r.status_code == 403
    r = await readonly_client.put(f"/api/v1/targets/{code}", json={"notes": "x"})
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_idempotency_key_replay(admin_client, unique_suffix):
    body = _payload(unique_suffix)
    headers = {"Idempotency-Key": str(uuid.uuid4())}
    r1 = await admin_client.post("/api/v1/targets", json=body, headers=headers)
    r2 = await admin_client.post("/api/v1/targets", json=body, headers=headers)
    assert r1.status_code == 201 and r2.status_code in (200, 201)
    assert r1.json()["data"]["target_code"] == r2.json()["data"]["target_code"]
