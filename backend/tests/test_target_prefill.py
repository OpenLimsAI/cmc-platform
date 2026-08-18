"""
靶点预填链路（app.domains.target.prefill）+ 外部 HTTP 封装（app.shared.http_client）离线测试

外部调用一律 httpx.MockTransport 打桩，夹具来自 PoC 真实响应存档（tests/fixtures/target_prefill，已裁剪）。
测试不许真出网。
"""
import json
from pathlib import Path

import httpx
import pytest
from app.domains.target.prefill import (
    binding_subunit_hint,
    extract_uniprot,
    location_hint,
    pick_molecule,
    prefill_inn,
    trim_uniprot_payload,
)
from app.shared.http_client import ExternalHttpClient, ExternalHttpError

FIX = Path(__file__).parent / "fixtures" / "target_prefill"


def _load(case: str, name: str):
    return json.loads((FIX / case / name).read_text(encoding="utf-8"))


def _fixture_transport(case: str, *, fail_first_n: int = 0, fail_status: int = 500):
    """把 ChEMBL/UniProt URL 路由到夹具文件；可选让前 N 次请求先返回 fail_status（测重试）。"""
    state = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        state["n"] += 1
        if state["n"] <= fail_first_n:
            return httpx.Response(fail_status, text="boom")
        url = request.url
        path = url.path
        if path.endswith("/molecule/search.json"):
            return httpx.Response(200, json=_load(case, "01_chembl_molecule_search.json"))
        if path.endswith("/mechanism.json"):
            return httpx.Response(200, json=_load(case, "02_chembl_mechanism.json"))
        if "/target/" in path:
            tid = path.rsplit("/", 1)[-1].removesuffix(".json")
            f = FIX / case / f"03_chembl_target_{tid}.json"
            return httpx.Response(200, json=json.loads(f.read_text())) if f.exists() else httpx.Response(404)
        if url.host == "rest.uniprot.org":
            acc = path.rsplit("/", 1)[-1].removesuffix(".json")
            f = FIX / case / f"05_uniprot_{acc}.json"
            return httpx.Response(200, json=json.loads(f.read_text())) if f.exists() else httpx.Response(404)
        return httpx.Response(404)

    return httpx.MockTransport(handler), state


def _client(case: str, **kw) -> tuple[ExternalHttpClient, dict]:
    transport, state = _fixture_transport(case, **kw)
    return ExternalHttpClient({"www.ebi.ac.uk", "rest.uniprot.org"}, transport=transport, retries=3), state


async def _no_hit(_acc: str):
    return None


def _fresh_session_factory():
    """service 层单测用：每个测试自建 engine（NullPool），避免全局 engine 绑定到已关闭的 event loop"""
    from app.core.config import settings
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
    from sqlalchemy.pool import NullPool

    engine = create_async_engine(settings.DATABASE_URL, poolclass=NullPool)
    return engine, async_sessionmaker(engine, expire_on_commit=False)


# ----------------------------------------------------------------------------- http_client
@pytest.mark.asyncio
async def test_http_client_host_whitelist():
    async with ExternalHttpClient({"www.ebi.ac.uk"}, transport=httpx.MockTransport(lambda r: httpx.Response(200, json={}))) as c:
        with pytest.raises(ExternalHttpError):
            await c.get_json("https://evil.example.com/x.json")


@pytest.mark.asyncio
async def test_http_client_retries_on_5xx_then_succeeds():
    client, state = _client("notarealinnxyz", fail_first_n=2, fail_status=500)
    async with client:
        status, data = await client.get_json("https://www.ebi.ac.uk/chembl/api/data/molecule/search.json", params={"q": "x"})
    assert status == 200 and data["page_meta"]["total_count"] == 0
    assert state["n"] == 3
    assert [c["http_status"] for c in client.calls] == [500, 500, 200]


@pytest.mark.asyncio
async def test_http_client_gives_up_after_retries():
    client, _ = _client("notarealinnxyz", fail_first_n=99, fail_status=503)
    async with client:
        with pytest.raises(ExternalHttpError) as ei:
            await client.get_json("https://www.ebi.ac.uk/chembl/api/data/status.json")
    assert "重试 3 次" in str(ei.value)


@pytest.mark.asyncio
async def test_http_client_4xx_no_retry_and_404_none():
    transport = httpx.MockTransport(lambda r: httpx.Response(404 if r.url.path.endswith("gone.json") else 400, text="bad"))
    async with ExternalHttpClient({"www.ebi.ac.uk"}, transport=transport) as c:
        assert await c.get_json("https://www.ebi.ac.uk/gone.json") == (404, None)
        with pytest.raises(ExternalHttpError) as ei:
            await c.get_json("https://www.ebi.ac.uk/bad.json")
        assert ei.value.status == 400
        assert len(c.calls) == 2  # 4xx 不重试


# ----------------------------------------------------------------------------- 纯函数
def test_pick_molecule_exact_then_synonym_then_manual():
    mols = _load("trastuzumab_deruxtecan", "01_chembl_molecule_search.json")["molecules"]
    m, why, cands = pick_molecule("trastuzumab deruxtecan", mols)
    assert m["molecule_chembl_id"] == "CHEMBL4297844" and "pref_name" in why
    assert len(cands) == 18
    m, why, _ = pick_molecule("DS-8201", mols)  # 研发代号是同义词
    assert m["molecule_chembl_id"] == "CHEMBL4297844" and "同义词" in why
    m, why, _ = pick_molecule("trastuzumab something", mols)
    assert m is None and "人工" in why


def test_extract_uniprot_standard_fields():
    her2 = extract_uniprot(_load("trastuzumab_deruxtecan", "05_uniprot_P04626.json"))
    assert her2["uniprot_id"] == "P04626" and her2["gene_symbol"] == "ERBB2"
    assert her2["cd_antigen_names"] == ["CD340"] and her2["ec_numbers"] == ["2.7.10.1"]
    names = {k["name"] for k in her2["keywords"]}
    assert {"Receptor", "Kinase", "Membrane"} <= names
    assert all(k["id"].startswith("KW-") for k in her2["keywords"])
    locs = {(sl["id"], sl["location"]) for sl in her2["subcellular_locations"]}
    assert ("SL-0039", "Cell membrane") in locs
    assert any(sl["topology"] == "Single-pass type I membrane protein" for sl in her2["subcellular_locations"])
    assert her2["sequence_length"] == 1255 and her2["mol_weight"] == 137910 and len(her2["sequence_md5"]) == 32
    assert her2["_location_hint"] == "膜型"  # 仅内部用于 ADC 角色
    top1 = extract_uniprot(_load("trastuzumab_deruxtecan", "05_uniprot_P11387.json"))
    assert top1["_location_hint"] == "胞内"
    il12b = extract_uniprot(_load("guselkumab", "05_uniprot_P29460.json"))
    assert "Cytokine" in {k["name"] for k in il12b["keywords"]}
    assert location_hint(_load("guselkumab", "05_uniprot_P29460.json"))[0] == "可溶型"


def test_binding_subunit_hint():
    p40 = {"component_description": "Interleukin-12 subunit beta", "gene_symbol": "IL12B"}
    p19 = {"component_description": "Interleukin-23 subunit alpha", "gene_symbol": "IL23A"}
    c = "Alpha (p19) subunit is binding site"
    assert binding_subunit_hint(c, p19, None) == "LIKELY"
    assert binding_subunit_hint(c, p40, {"alternative_names": ["IL-12 subunit p40"]}) == "UNLIKELY"
    assert binding_subunit_hint(None, p19, None) is None


def test_trim_uniprot_payload_drops_bulk():
    u = _load("trastuzumab_deruxtecan", "05_uniprot_P04626.json")
    u["references"] = [{"x": 1}] * 50
    u["uniProtKBCrossReferences"] = [{"y": 1}] * 500
    t = trim_uniprot_payload(u)
    assert "references" not in t and "uniProtKBCrossReferences" not in t
    assert t["primaryAccession"] == "P04626"
    assert "value" not in t["sequence"]


# ----------------------------------------------------------------------------- 全链路（离线）
@pytest.mark.asyncio
async def test_prefill_guselkumab_mixed_hit_and_complex():
    async def lookup(acc: str):
        return {"target_code": "TGT-000001", "target_name": "Interleukin-23 subunit alpha", "uniprot_id": "Q9NPF7"} if acc == "Q9NPF7" else None

    client, _ = _client("guselkumab")
    async with client:
        r = await prefill_inn("guselkumab", client, lookup)
    assert r["outcome"] == "OK_MIXED_HIT_LINK_AND_NEW_TARGET", r
    pf = r["prefill_form"]
    assert [t["target_code"] for t in pf["targets_existing_hit"]] == ["TGT-000001"]
    assert [t["uniprot_id"] for t in pf["targets_new"]] == ["P29460"]
    bridge = {b["uniprot_id"]: b for b in pf["bridge_molecule_target"]}
    assert bridge["Q9NPF7"]["target_code"] == "TGT-000001" and bridge["Q9NPF7"]["_binding_subunit_hint"] == "LIKELY"
    assert bridge["P29460"]["target_code"] == "<NEW:P29460>" and bridge["P29460"]["_binding_subunit_hint"] == "UNLIKELY"
    assert all(b["needs_confirm"] for b in bridge.values())
    assert any("PROTEIN COMPLEX" in w for w in r["warnings"])
    # 预填字段名与 API 请求体一致（UniProt 标准字段）
    new = pf["targets_new"][0]
    assert {"target_name", "uniprot_id", "gene_symbol", "aliases", "keywords", "subcellular_locations",
            "cd_antigen_names", "entry_type", "sequence_length", "uniprot_entry_version"} <= set(new)
    assert "Cytokine" in {k["name"] for k in new["keywords"]}
    # 只对未命中的 P29460 抓了 UniProt
    assert [c["url"] for c in client.calls if "uniprot" in c["url"]] == ["https://rest.uniprot.org/uniprotkb/P29460.json"]


@pytest.mark.asyncio
async def test_prefill_adc_two_mechanisms_payload_role():
    client, _ = _client("trastuzumab_deruxtecan")
    async with client:
        r = await prefill_inn("trastuzumab deruxtecan", client, _no_hit)
    assert r["outcome"] == "OK_NEW_TARGET_PREFILLED"
    assert r["molecule"]["molecule_type"] == "Antibody drug conjugate"
    roles = {b["uniprot_id"]: b["relation_role"] for b in r["prefill_form"]["bridge_molecule_target"]}
    assert roles == {"P04626": "antibody_target", "P11387": "payload_target"}
    assert len(r["prefill_form"]["targets_new"]) == 2


@pytest.mark.asyncio
async def test_prefill_bispecific_selectivity_group_expands():
    client, _ = _client("emicizumab")
    async with client:
        r = await prefill_inn("emicizumab", client, _no_hit)
    assert r["outcome"] == "OK_NEW_TARGET_PREFILLED"
    # 1 条 mechanism × 2 个组分 = 2 条 bridge
    assert len(r["steps"][1]["mechanisms"]) == 1
    assert sorted(b["uniprot_id"] for b in r["prefill_form"]["bridge_molecule_target"]) == ["P00740", "P00742"]
    assert all(b["needs_confirm"] for b in r["prefill_form"]["bridge_molecule_target"])


@pytest.mark.asyncio
async def test_prefill_secondary_accession_dedup():
    """ChEMBL 列出的次级 accession 命中库里已有靶点 → 只建关联"""
    async def lookup(acc: str):
        # P04626 的次级 accession 之一（夹具里 target_component_xrefs UniProt 列表含 Q14256）
        return {"target_code": "TGT-000042", "target_name": "HER2", "uniprot_id": "Q14256"} if acc == "Q14256" else None

    client, _ = _client("trastuzumab_deruxtecan")
    async with client:
        r = await prefill_inn("trastuzumab deruxtecan", client, lookup)
    hit = {b["uniprot_id"]: b for b in r["prefill_form"]["bridge_molecule_target"]}["P04626"]
    assert hit["target_code"] == "TGT-000042" and hit["_dedup_action"] == "HIT_EXISTING_TARGET_ONLY_LINK"


@pytest.mark.asyncio
async def test_prefill_unknown_inn_rejected():
    client, _ = _client("notarealinnxyz")
    async with client:
        r = await prefill_inn("notarealinnxyz", client, _no_hit)
    assert r["outcome"] == "REJECTED_NO_MOLECULE"
    assert "查无" in r["user_message"]
    assert len(client.calls) == 1  # 没再往下调


@pytest.mark.asyncio
async def test_prefill_external_error_is_reported_not_raised():
    client, _ = _client("guselkumab", fail_first_n=99, fail_status=500)
    async with client:
        r = await prefill_inn("guselkumab", client, _no_hit)
    assert r["outcome"] == "ERROR_EXTERNAL_CALL"
    assert r["error"]["url"].endswith("/molecule/search.json")


# ----------------------------------------------------------------------------- 单条 UniProt 预填（新建页「拉取」）
def test_build_uniprot_prefill_shape():
    from app.domains.target.prefill import build_uniprot_prefill

    u = _load("guselkumab", "05_uniprot_P29460.json")
    r = build_uniprot_prefill(u, "P29460", fetched_at="2026-08-17T13:30:47+00:00")
    assert r["form"]["uniprot_id"] == "P29460" and r["form"]["gene_symbol"] == "IL12B"
    assert "Cytokine" in {k["name"] for k in r["form"]["keywords"]}
    assert r["form"]["subcellular_locations"][0]["location"] == "Secreted"
    assert "IL-12 subunit p40" in r["form"]["aliases"]
    assert r["form"]["uniprot_fetched_at"] == "2026-08-17T13:30:47+00:00"
    assert r["hints"]["is_human"] is True and r["hints"]["is_reviewed"] is True
    assert r["snapshot"]["source"] == "uniprot" and r["snapshot"]["source_id"] == "P29460"
    assert r["snapshot"]["fetched_at"] == "2026-08-17T13:30:47+00:00"
    assert "references" not in r["snapshot"]["payload"]


@pytest.mark.asyncio
async def test_service_prefill_from_uniprot_with_mock_transport():
    """service 层：MockTransport 打桩 UniProt；查重命中走 existing（不出网）"""
    from app.domains.target.services import TargetService

    entry = _load("trastuzumab_deruxtecan", "05_uniprot_P04626.json")
    transport = httpx.MockTransport(
        lambda r: httpx.Response(200, json=entry) if r.url.path.endswith("/P04626.json") else httpx.Response(404)
    )
    engine, session_factory = _fresh_session_factory()
    async with session_factory() as db:
        svc = TargetService(db)
        r = await svc.prefill_from_uniprot("p04626", transport=transport)
        assert r.accession == "P04626"
        assert r.form.target_name == "Receptor tyrosine-protein kinase erbB-2"
        assert r.form.cd_antigen_names == ["CD340"] and r.form.ec_numbers == ["2.7.10.1"]
        assert any(k.name == "Receptor" for k in r.form.keywords or [])
        assert r.snapshot.source_id == "P04626"

        from app.core.exceptions import NotFoundError
        with pytest.raises(NotFoundError):
            await svc.prefill_from_uniprot("A0A000", transport=transport)
    await engine.dispose()


@pytest.mark.asyncio
async def test_prefill_endpoint_validation_and_permission(admin_client, readonly_client):
    """HTTP 层只测不出网的分支：非法 accession → 400；只读用户 → 403"""
    r = await admin_client.get("/api/v1/targets/prefill/uniprot?accession=XYZ123")
    assert r.status_code == 400, r.text
    r = await readonly_client.get("/api/v1/targets/prefill/uniprot?accession=Q15116")
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_service_refresh_from_uniprot_overwrites_fields_and_adds_snapshot():
    """service 层：refresh-uniprot 用 MockTransport 拉新版本 → 标准字段覆盖 + 追加快照"""
    from app.domains.auth.models import User
    from app.domains.target.models import TargetSourceSnapshot
    from app.domains.target.schemas import TargetCreate
    from app.domains.target.services import TargetService
    from sqlalchemy import select

    entry = _load("guselkumab", "05_uniprot_P29460.json")
    entry["entryAudit"] = {**(entry.get("entryAudit") or {}), "entryVersion": 999}
    transport = httpx.MockTransport(
        lambda r: httpx.Response(200, json=entry) if r.url.path.endswith("/P29460.json") else httpx.Response(404)
    )
    engine, session_factory = _fresh_session_factory()
    async with session_factory() as db:
        admin = (await db.execute(select(User).where(User.username == "admin"))).scalar_one()
        svc = TargetService(db)
        created = await svc.create(TargetCreate(target_name="占位 IL12B", uniprot_id="P29460"), admin)
        assert created.keywords is None
        refreshed = await svc.refresh_from_uniprot(created.target_code, "pytest 刷新 UniProt", admin, transport=transport)
        assert refreshed.target_name == "Interleukin-12 subunit beta"
        assert refreshed.uniprot_entry_version == 999
        assert "Cytokine" in {k.name for k in refreshed.keywords or []}
        snaps = (await db.execute(
            select(TargetSourceSnapshot).where(TargetSourceSnapshot.target_id == created.target_id)
        )).scalars().all()
        assert len(snaps) == 1 and snaps[0].source_version == "999"
        await db.rollback()  # 不留数据
    await engine.dispose()
