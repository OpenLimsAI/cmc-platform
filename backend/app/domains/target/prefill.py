"""靶点预填链路（纯逻辑，无 I/O）—— 由 poc/target_prefill/prefill_target.py 移植

INN → ChEMBL molecule/search → mechanism → target(target_components[].accession)
    → 查重（主+次级 accession，由调用方注入 lookup）→ UniProt → 预填表单

PoC 实测结论（docs/decisions/2026-08-17-target-domain.md §四）在此固化：
  - UniProt 号取自 ChEMBL target_components[].accession（顶层 cross_references 是空的）
  - bridge 记录 = mechanism × target_components 笛卡尔展开
  - PROTEIN COMPLEX 用 binding_site_comment 提示 LIKELY / UNLIKELY 结合亚基
  - ADC（molecule_type 含 conjugate）：靶点定位=胞内 → payload_target，否则 antibody_target
  - 分子搜索：pref_name 精确 → 同义词精确 → NEEDS_MANUAL_PICK
  - target_type / target_location 只是启发式建议，附依据，needs_confirm 强制为真

外部 I/O（HTTP / DB）全部通过 Fetcher / lookup 回调注入，便于测试打桩。
"""
from __future__ import annotations

import json
import re
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from typing import Any, Protocol

CHEMBL_BASE = "https://www.ebi.ac.uk/chembl/api/data"
UNIPROT_BASE = "https://rest.uniprot.org/uniprotkb"
ALLOWED_HOSTS = ("www.ebi.ac.uk", "rest.uniprot.org")

CHEMBL_LICENSE = "CC BY-SA 3.0 (ChEMBL)"
UNIPROT_LICENSE = "CC BY 4.0 (UniProt)"

TARGET_TYPE_ENUM = ["受体", "配体·细胞因子", "表面抗原", "酶", "其他"]
TARGET_LOCATION_ENUM = ["膜型", "可溶型", "两者都有", "胞内"]


class Fetcher(Protocol):
    async def get_json(self, url: str, *, params: dict[str, Any] | None = None) -> tuple[int, Any]: ...


# 查重回调：accession → 已有靶点摘要 {"target_code","target_name","uniprot_id"} 或 None
Lookup = Callable[[str], Awaitable[dict[str, Any] | None]]


def now_iso() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


# ----------------------------------------------------------------------------- Step 1 分子
def pick_molecule(inn: str, molecules: list[dict[str, Any]]) -> tuple[dict[str, Any] | None, str, list[dict[str, Any]]]:
    """pref_name 精确 = INN > 同义词精确 = INN > 无（要人工挑）。返回 (选中, 依据, 候选摘要)。"""
    q = inn.strip().lower()
    cands = []
    for m in molecules:
        syn_types = {(s.get("molecule_synonym") or "").lower(): s.get("syn_type") for s in m.get("molecule_synonyms") or []}
        cands.append({
            "molecule_chembl_id": m.get("molecule_chembl_id"),
            "pref_name": m.get("pref_name"),
            "molecule_type": m.get("molecule_type"),
            "max_phase": m.get("max_phase"),
            "score": m.get("score"),
            "inn_synonym_hit": q in syn_types,
            "syn_type_of_hit": syn_types.get(q),
        })
    for m in molecules:
        if (m.get("pref_name") or "").lower() == q:
            return m, "pref_name 精确匹配 INN", cands
    for m, c in zip(molecules, cands, strict=False):
        if c["inn_synonym_hit"]:
            return m, f"同义词精确匹配 INN（syn_type={c['syn_type_of_hit']}）", cands
    return None, "无精确匹配（仅模糊命中，需人工从候选中挑选）", cands


def extract_molecule(m: dict[str, Any]) -> dict[str, Any]:
    syns = m.get("molecule_synonyms") or []
    bio = m.get("biotherapeutic") or {}
    return {
        "chembl_id": m.get("molecule_chembl_id"),
        "pref_name": m.get("pref_name"),
        "molecule_type": m.get("molecule_type"),
        "max_phase": m.get("max_phase"),
        "first_approval": m.get("first_approval"),
        "usan_stem": m.get("usan_stem"),
        "usan_stem_definition": m.get("usan_stem_definition"),
        "synonyms": sorted({(s.get("molecule_synonym"), s.get("syn_type")) for s in syns},
                           key=lambda x: (x[1] or "", x[0] or "")),
        "research_codes": sorted({s.get("molecule_synonym") for s in syns if s.get("syn_type") == "RESEARCH_CODE"}),
        "trade_names": sorted({s.get("molecule_synonym") for s in syns if s.get("syn_type") == "TRADE_NAME"}),
        "molecule_hierarchy": m.get("molecule_hierarchy"),
        "biotherapeutic": {
            "description": bio.get("description"),
            "biocomponents": [
                {"component_id": c.get("component_id"), "component_type": c.get("component_type"),
                 "description": c.get("description"), "sequence_len": len(c.get("sequence") or "")}
                for c in (bio.get("biocomponents") or [])
            ],
        } if bio else None,
        "cross_references": [(x.get("xref_src"), x.get("xref_id")) for x in m.get("cross_references") or []],
        "atc_classifications": m.get("atc_classifications"),
    }


# ----------------------------------------------------------------------------- UniProt → 建议值
def _kw(entry: dict[str, Any], category: str) -> list[str]:
    return [k.get("name") for k in entry.get("keywords") or [] if k.get("category") == category]


_ENZYME_KW = {"Hydrolase", "Transferase", "Kinase", "Protease", "Oxidoreductase", "Lyase", "Isomerase", "Ligase",
              "Serine protease", "Metalloprotease", "Glycosidase", "Nuclease", "Phosphatase"}


def suggest_target_type(entry: dict[str, Any]) -> tuple[str, str]:
    """启发式建议 target_type（5 选 1）；返回 (值, 依据)。仅供预填，必须人工确认。"""
    mf = set(_kw(entry, "Molecular function"))
    pd = entry.get("proteinDescription") or {}
    name = ((pd.get("recommendedName") or {}).get("fullName") or {}).get("value", "") or ""
    gene = ((entry.get("genes") or [{}])[0].get("geneName") or {}).get("value", "") or ""
    hit = mf & {"Cytokine", "Growth factor", "Hormone", "Chemokine"}
    if hit:
        return "配体·细胞因子", f"UniProt keyword(Molecular function) ∈ {sorted(hit)}"
    hit = mf & {"Receptor", "G-protein coupled receptor", "Ion channel", "Transducer"}
    if hit:
        return "受体", f"UniProt keyword(Molecular function) ∈ {sorted(hit)}"
    cd_names = [c.get("value") for c in pd.get("cdAntigenNames") or []]
    if cd_names:
        # 有 CD 编号（如 PD-1=CD279）→ 表面抗原；HER2=CD340 也有 CD 号，但 Receptor 规则在前
        return "表面抗原", f"UniProt proteinDescription.cdAntigenNames={cd_names}"
    if mf & _ENZYME_KW or "EC " in json.dumps(pd.get("recommendedName") or {}):
        return "酶", f"UniProt keyword ∈ {sorted(mf & _ENZYME_KW)} 或 recommendedName 含 EC 号"
    if re.match(r"^CD\d+", gene) or "antigen" in name.lower():
        return "表面抗原", f"名称/基因名启发（gene={gene}, name={name!r}）"
    if "receptor" in name.lower():
        return "受体", f"名称启发（name={name!r}）"
    return "其他", f"无规则命中（Molecular function keywords={sorted(mf)}）"


def suggest_target_location(entry: dict[str, Any]) -> tuple[str, str]:
    """启发式建议 target_location（4 选 1）：看 SUBCELLULAR LOCATION + Cellular component keywords。"""
    locs: list[str] = []
    for c in entry.get("comments") or []:
        if c.get("commentType") == "SUBCELLULAR LOCATION":
            for sl in c.get("subcellularLocations") or []:
                v = ((sl.get("location") or {}).get("value") or "")
                t = ((sl.get("topology") or {}).get("value") or "")
                locs.append(v + (f" [{t}]" if t else ""))
    cc = set(_kw(entry, "Cellular component"))
    txt = " | ".join(locs) + " | " + " | ".join(sorted(cc))
    low = txt.lower()
    membrane = "membrane" in low
    soluble = "secreted" in low or "extracellular" in low
    intracellular_only = (not membrane and not soluble) and any(
        k in low for k in ("cytoplasm", "nucleus", "cytosol", "mitochondrion", "endoplasmic")
    )
    if membrane and soluble:
        return "两者都有", f"UniProt 定位同时含膜与分泌/胞外：{txt}"
    if membrane:
        return "膜型", f"UniProt 定位含 membrane：{txt}"
    if soluble:
        return "可溶型", f"UniProt 定位含 Secreted/extracellular：{txt}"
    if intracellular_only:
        return "胞内", f"UniProt 定位仅胞内：{txt}"
    return "膜型", f"无法判定（{txt!r}），默认膜型，需人工确认"


def extract_uniprot(entry: dict[str, Any]) -> dict[str, Any]:
    pd = entry.get("proteinDescription") or {}
    rec = pd.get("recommendedName") or {}
    alt = [((a.get("fullName") or {}).get("value")) for a in pd.get("alternativeNames") or []]
    genes = entry.get("genes") or []
    func = ""
    for c in entry.get("comments") or []:
        if c.get("commentType") == "FUNCTION":
            func = " ".join(t.get("value", "") for t in c.get("texts") or [])
            break
    ttype, ttype_why = suggest_target_type(entry)
    tloc, tloc_why = suggest_target_location(entry)
    return {
        "uniprot_id": entry.get("primaryAccession"),
        "uniprot_entry_name": entry.get("uniProtkbId"),
        "entry_type": entry.get("entryType"),
        "secondary_accessions": entry.get("secondaryAccessions") or [],
        "recommended_name": (rec.get("fullName") or {}).get("value"),
        "short_names": [s.get("value") for s in rec.get("shortNames") or []],
        "alternative_names": alt,
        "cd_antigen_names": [c.get("value") for c in pd.get("cdAntigenNames") or []],
        "gene_symbol": ((genes[0].get("geneName") or {}).get("value")) if genes else None,
        "gene_synonyms": [s.get("value") for s in (genes[0].get("synonyms") or [])] if genes else [],
        "organism": (entry.get("organism") or {}).get("scientificName"),
        "tax_id": (entry.get("organism") or {}).get("taxonId"),
        "sequence_length": (entry.get("sequence") or {}).get("length"),
        "function_text": func[:1000],
        "entry_version": (entry.get("entryAudit") or {}).get("entryVersion"),
        "suggested_target_type": ttype, "suggested_target_type_reason": ttype_why,
        "suggested_target_location": tloc, "suggested_target_location_reason": tloc_why,
    }


def trim_uniprot_payload(entry: dict[str, Any]) -> dict[str, Any]:
    """入库快照用：只留主属性相关子集，去掉 references / uniProtKBCrossReferences / 大 features。"""
    keep_comments = {"FUNCTION", "SUBCELLULAR LOCATION", "SUBUNIT"}
    keep_features = {"Domain", "Region", "Topological domain", "Transmembrane", "Signal", "Chain"}
    return {
        "primaryAccession": entry.get("primaryAccession"),
        "secondaryAccessions": entry.get("secondaryAccessions"),
        "uniProtkbId": entry.get("uniProtkbId"),
        "entryType": entry.get("entryType"),
        "proteinDescription": entry.get("proteinDescription"),
        "genes": entry.get("genes"),
        "organism": entry.get("organism"),
        "keywords": entry.get("keywords"),
        "comments": [c for c in entry.get("comments") or [] if c.get("commentType") in keep_comments],
        "features": [f for f in entry.get("features") or [] if f.get("type") in keep_features],
        "sequence": {k: v for k, v in (entry.get("sequence") or {}).items() if k != "value"},
        "entryAudit": entry.get("entryAudit"),
    }


def trim_chembl_target_payload(t: dict[str, Any]) -> dict[str, Any]:
    comps = []
    for c in t.get("target_components") or []:
        comps.append({
            "accession": c.get("accession"),
            "component_type": c.get("component_type"),
            "component_description": c.get("component_description"),
            "relationship": c.get("relationship"),
            "target_component_synonyms": c.get("target_component_synonyms"),
            "target_component_xrefs": [
                x for x in c.get("target_component_xrefs") or []
                if x.get("xref_src_db") in ("UniProt", "HGNC", "Ensembl", "InterPro", "Pfam")
            ],
        })
    return {k: v for k, v in t.items() if k != "target_components"} | {"target_components": comps}


def binding_subunit_hint(binding_site_comment: str | None, comp: dict[str, Any], ux: dict[str, Any] | None) -> str | None:
    """PROTEIN COMPLEX：用 mechanism.binding_site_comment 提示哪一亚基是结合亚基（LIKELY / UNLIKELY）。"""
    if not binding_site_comment:
        return None
    stop = {"subunit", "binding", "site", "the", "and", "chain"}
    tokens = {t for t in re.findall(r"[a-z0-9]+", binding_site_comment.lower()) if len(t) > 2 and t not in stop}
    hay = " ".join(filter(None, [comp.get("component_description") or "", comp.get("gene_symbol") or ""]
                          + ((ux or {}).get("short_names") or []) + ((ux or {}).get("alternative_names") or [])
                          + ((ux or {}).get("gene_synonyms") or []))).lower()
    return "LIKELY" if any(t in hay for t in tokens) else "UNLIKELY"


# ----------------------------------------------------------------------------- 主链路
async def prefill_inn(inn: str, fetcher: Fetcher, lookup: Lookup) -> dict[str, Any]:
    """跑完整链路，返回结果 dict（含 steps / warnings / prefill_form / raw）。不抛外部错误——写进 result['error']。"""
    from app.shared.http_client import ExternalHttpError

    fetched_at = now_iso()
    result: dict[str, Any] = {"inn": inn, "fetched_at": fetched_at, "steps": [], "warnings": [], "outcome": None, "raw": {}}
    steps, raw = result["steps"], result["raw"]

    def note(name: str, **kw: Any) -> None:
        steps.append({"step": name, **kw})

    try:
        # ---- Step 1: molecule search
        url = f"{CHEMBL_BASE}/molecule/search.json"
        status, data = await fetcher.get_json(url, params={"q": inn, "limit": 20})
        raw["chembl_molecule_search"] = data
        mols = (data or {}).get("molecules") or []
        total = ((data or {}).get("page_meta") or {}).get("total_count")
        if not mols:
            note("1_chembl_molecule_search", http_status=status, total_count=total, result="NO_MATCH")
            result["outcome"] = "REJECTED_NO_MOLECULE"
            result["user_message"] = f"ChEMBL 查无「{inn}」（total_count={total}）。请检查 INN 拼写；若为新分子/未收录，请走人工录入。"
            return result
        mol, why, cands = pick_molecule(inn, mols)
        note("1_chembl_molecule_search", http_status=status, total_count=total, pick_reason=why, candidates=cands[:10])
        if mol is None:
            result["outcome"] = "NEEDS_MANUAL_PICK"
            result["user_message"] = f"ChEMBL 对「{inn}」有 {total} 个模糊候选但无精确匹配，请人工从候选中选择 ChEMBL ID 后重试。"
            return result
        molecule = extract_molecule(mol)
        result["molecule"] = molecule
        if (molecule["pref_name"] or "").lower() != inn.lower():
            result["warnings"].append(f"选中分子 pref_name={molecule['pref_name']!r} 与输入 INN 不同（依据：{why}），请人工确认。")

        # ---- Step 2: mechanism（本体为空回退 parent）
        chembl_id = molecule["chembl_id"]
        status, data = await fetcher.get_json(f"{CHEMBL_BASE}/mechanism.json", params={"molecule_chembl_id": chembl_id})
        raw["chembl_mechanism"] = data
        mechs = (data or {}).get("mechanisms") or []
        parent = (molecule.get("molecule_hierarchy") or {}).get("parent_chembl_id")
        if not mechs and parent and parent != chembl_id:
            _, data2 = await fetcher.get_json(f"{CHEMBL_BASE}/mechanism.json", params={"molecule_chembl_id": parent})
            raw["chembl_mechanism_parent"] = data2
            mechs = (data2 or {}).get("mechanisms") or []
            result["warnings"].append(f"本体 {chembl_id} 无 mechanism，已回退 parent {parent} 查得 {len(mechs)} 条。")
        note("2_chembl_mechanism", http_status=status, mechanism_count=len(mechs),
             mechanisms=[{k: m.get(k) for k in ("mec_id", "mechanism_of_action", "action_type", "target_chembl_id",
                                                "binding_site_comment", "direct_interaction", "max_phase")} for m in mechs])
        if not mechs:
            result["outcome"] = "MOLECULE_ONLY_NO_MECHANISM"
            result["user_message"] = "ChEMBL 有分子记录但无 mechanism（MoA/靶点）记录，靶点需人工填写。"
            result["prefill_form"] = {"molecule": molecule, "targets_new": [], "targets_existing_hit": [], "bridge_molecule_target": []}
            return result
        if len(mechs) > 1:
            result["warnings"].append(f"该分子有 {len(mechs)} 条 mechanism 记录（多靶点/双抗/ADC），每条靶点关联均需人工确认。")

        # ---- Step 3: target → UniProt accession
        targets_by_id: dict[str, dict[str, Any]] = {}
        raw["chembl_target"] = {}
        for m in mechs:
            tid = m.get("target_chembl_id")
            if not tid:
                result["warnings"].append(f"mechanism mec_id={m.get('mec_id')} 无 target_chembl_id，跳过。")
                continue
            if tid in targets_by_id:
                continue
            status, tdata = await fetcher.get_json(f"{CHEMBL_BASE}/target/{tid}.json")
            raw["chembl_target"][tid] = tdata
            if status == 404 or not tdata:
                result["warnings"].append(f"target {tid} 404/空。")
                targets_by_id[tid] = {"target_chembl_id": tid, "http_status": status, "components": []}
                continue
            comps = [{
                "accession": c.get("accession"),
                "component_type": c.get("component_type"),
                "component_description": c.get("component_description"),
                "relationship": c.get("relationship"),
                "gene_symbol": next((s.get("component_synonym") for s in c.get("target_component_synonyms") or []
                                     if s.get("syn_type") == "GENE_SYMBOL"), None),
                "uniprot_xref": [x.get("xref_id") for x in c.get("target_component_xrefs") or [] if x.get("xref_src_db") == "UniProt"],
            } for c in tdata.get("target_components") or []]
            tt = tdata.get("target_type")
            targets_by_id[tid] = {
                "target_chembl_id": tid, "http_status": status, "pref_name": tdata.get("pref_name"),
                "target_type_chembl": tt, "organism": tdata.get("organism"), "tax_id": tdata.get("tax_id"),
                "components": comps,
            }
            if tt == "PROTEIN COMPLEX":
                result["warnings"].append(f"target {tid}（{tdata.get('pref_name')}）为 PROTEIN COMPLEX，含 {len(comps)} 个亚基；"
                                          f"以 UniProt 为锚点会拆成 {len(comps)} 条，请人工确认抗体实际结合的亚基。")
            elif tt not in ("SINGLE PROTEIN", None):
                result["warnings"].append(f"target {tid}（{tdata.get('pref_name')}）为 {tt}（ChEMBL 把 {len(comps)} 个蛋白合并为一组，"
                                          f"常见于双抗/多靶）；每个组分各建一条 bridge，请人工确认。")
            if tdata.get("tax_id") not in (9606, None):
                result["warnings"].append(f"target {tid} 物种 tax_id={tdata.get('tax_id')}（非人），请确认。")
        note("3_chembl_target", targets=list(targets_by_id.values()))

        # ---- Step 4 查重 + Step 5 UniProt
        prefill_targets: list[dict[str, Any]] = []
        bridge: list[dict[str, Any]] = []
        uniprot_cache: dict[str, dict[str, Any]] = {}
        raw["uniprot"] = {}
        dedup_log: list[dict[str, Any]] = []
        existing_hits: dict[str, dict[str, Any]] = {}
        is_adc = "conjugate" in (molecule.get("molecule_type") or "").lower()

        for m in mechs:
            tid = m.get("target_chembl_id")
            tinfo = targets_by_id.get(tid) if tid else None
            protein_comps = [c for c in (tinfo or {}).get("components") or [] if c.get("accession")]
            if not protein_comps:
                bridge.append({
                    "molecule_chembl_id": chembl_id, "molecule_inn": inn, "target_code": None, "uniprot_id": None,
                    "target_chembl_id": tid, "moa": m.get("mechanism_of_action"), "action_type": m.get("action_type"),
                    "binding_epitope_or_domain": m.get("binding_site_comment"), "chembl_mechanism_id": m.get("mec_id"),
                    "relation_role": "other", "needs_confirm": True,
                    "confirm_reason": "ChEMBL target 无蛋白组分/无 UniProt accession，需人工指定靶点",
                })
                continue
            for c in protein_comps:
                acc = c["accession"]
                # 查重：主 accession + ChEMBL 列出的次级 accession
                hit = await lookup(acc)
                if hit is None:
                    for sec in c.get("uniprot_xref") or []:
                        if sec != acc:
                            hit = await lookup(sec)
                            if hit:
                                break
                if hit:
                    dedup_log.append({"uniprot_id": acc, "hit": True, "existing_target_code": hit["target_code"]})
                    existing_hits[acc] = hit
                    target_code = hit["target_code"]
                    dedup_action = "HIT_EXISTING_TARGET_ONLY_LINK"
                else:
                    dedup_log.append({"uniprot_id": acc, "hit": False})
                    if acc not in uniprot_cache:
                        status, udata = await fetcher.get_json(f"{UNIPROT_BASE}/{acc}.json")
                        raw["uniprot"][acc] = udata
                        if status == 404 or not udata:
                            uniprot_cache[acc] = {"uniprot_id": acc, "_error": f"UniProt HTTP {status}"}
                        else:
                            ux = extract_uniprot(udata)
                            ux["_http_status"] = status
                            uniprot_cache[acc] = ux
                    ux = uniprot_cache[acc]
                    target_code = f"<NEW:{acc}>"
                    dedup_action = "NEW_TARGET_PREFILLED_FROM_UNIPROT"
                    if not any(t.get("uniprot_id") == acc for t in prefill_targets):
                        aliases = sorted({*(ux.get("short_names") or []), *(ux.get("alternative_names") or []),
                                          *(ux.get("cd_antigen_names") or []), *(ux.get("secondary_accessions") or []),
                                          *(x for x in c.get("uniprot_xref") or [] if x != acc)} - {None, ""})
                        prefill_targets.append({
                            # ---- 直接对应 POST /targets 请求体 ----
                            "target_name": ux.get("recommended_name") or c.get("component_description"),
                            "uniprot_id": acc,
                            "gene_symbol": ux.get("gene_symbol") or c.get("gene_symbol"),
                            "organism": ux.get("organism") or (tinfo or {}).get("organism"),
                            "aliases": aliases,
                            "target_type": ux.get("suggested_target_type"),
                            "target_location": ux.get("suggested_target_location"),
                            "description": (ux.get("function_text") or "")[:500] or None,
                            # ---- 审核辅助 ----
                            "_target_type_reason": ux.get("suggested_target_type_reason"),
                            "_target_location_reason": ux.get("suggested_target_location_reason"),
                            "_target_type_enum": TARGET_TYPE_ENUM,
                            "_target_location_enum": TARGET_LOCATION_ENUM,
                            "_chembl_target_id": tid,
                            "_chembl_target_pref_name": (tinfo or {}).get("pref_name"),
                            "_chembl_target_type": (tinfo or {}).get("target_type_chembl"),
                            "_uniprot_entry_version": ux.get("entry_version"),
                            "_needs_manual_confirm": True,
                            "_confirm_reason": "target_type / target_location 为启发式建议",
                        })
                needs = len(mechs) > 1 or len(protein_comps) > 1
                reasons: list[str] = []
                ttype_chembl = (tinfo or {}).get("target_type_chembl")
                subunit_hint = None
                if len(mechs) > 1:
                    reasons.append("分子有多条 mechanism（多靶/双抗/ADC）")
                if len(protein_comps) > 1:
                    if ttype_chembl == "PROTEIN COMPLEX":
                        subunit_hint = binding_subunit_hint(m.get("binding_site_comment"), c, uniprot_cache.get(acc))
                        reasons.append(f"ChEMBL target 为 PROTEIN COMPLEX，含 {len(protein_comps)} 个亚基，需确认结合亚基"
                                       + (f"（binding_site_comment 提示：{subunit_hint}）" if subunit_hint else ""))
                    else:
                        reasons.append(f"ChEMBL target 为 {ttype_chembl}，含 {len(protein_comps)} 个蛋白，双抗/多靶各建一条 bridge，需确认")
                relation_role = "antibody_target"
                if is_adc:
                    loc = (uniprot_cache.get(acc) or {}).get("suggested_target_location")
                    if loc == "胞内":
                        relation_role = "payload_target"
                        reasons.append("ADC 载荷（payload）作用靶点（UniProt 定位=胞内）")
                bridge.append({
                    # ---- 直接对应 POST /targets/{code}/molecules 请求体（substance_code 由人工填）----
                    "target_code": target_code, "uniprot_id": acc, "molecule_chembl_id": chembl_id, "molecule_inn": inn,
                    "relation_role": relation_role,
                    "moa": m.get("mechanism_of_action"), "action_type": m.get("action_type"),
                    "binding_epitope_or_domain": m.get("binding_site_comment"),
                    "chembl_mechanism_id": m.get("mec_id"), "needs_confirm": needs,
                    # ---- 审核辅助 ----
                    "_target_chembl_id": tid, "_target_pref_name_chembl": (tinfo or {}).get("pref_name"),
                    "_component_description": c.get("component_description"),
                    "_dedup_action": dedup_action, "_binding_subunit_hint": subunit_hint,
                    "_confirm_reason": "；".join(reasons) or None,
                })
        note("4_dedup_target", dedup=dedup_log)
        note("5_uniprot", fetched=[{"uniprot_id": k, "http_status": v.get("_http_status"), "error": v.get("_error")}
                                   for k, v in uniprot_cache.items()])

        result["prefill_form"] = {
            "_note": "预填表单：字段名与 POST /targets、POST /targets/{code}/molecules 请求体一致；下划线开头为审核辅助信息，不入库。",
            "molecule": molecule,
            "targets_new": prefill_targets,
            "targets_existing_hit": list(existing_hits.values()),
            "bridge_molecule_target": bridge,
        }
        hits = [d for d in dedup_log if d["hit"]]
        if hits and len(hits) == len(dedup_log):
            result["outcome"] = "OK_ALL_TARGETS_EXIST_LINK_ONLY"
        elif hits and prefill_targets:
            result["outcome"] = "OK_MIXED_HIT_LINK_AND_NEW_TARGET"
        elif prefill_targets:
            result["outcome"] = "OK_NEW_TARGET_PREFILLED"
        else:
            result["outcome"] = "OK_PARTIAL"
        return result
    except ExternalHttpError as e:
        result["outcome"] = "ERROR_EXTERNAL_CALL"
        result["error"] = {"url": e.url, "http_status": e.status, "detail": e.detail}
        return result


# ----------------------------------------------------------------------------- 单条 UniProt 预填（新建靶点页「拉取」按钮）
def build_uniprot_prefill(entry: dict[str, Any], accession: str, fetched_at: str | None = None) -> dict[str, Any]:
    """把一条 UniProt JSON 变成新建靶点表单的预填 + 依据 + 可直接落库的快照体。"""
    ux = extract_uniprot(entry)
    aliases = sorted(
        {*(ux.get("short_names") or []), *(ux.get("alternative_names") or []),
         *(ux.get("cd_antigen_names") or []), *(ux.get("gene_synonyms") or []),
         *(ux.get("secondary_accessions") or [])} - {None, ""}
    )
    fetched = fetched_at or now_iso()
    return {
        "form": {
            "target_name": ux.get("recommended_name") or ux.get("uniprot_entry_name"),
            "uniprot_id": entry.get("primaryAccession") or accession,
            "gene_symbol": ux.get("gene_symbol"),
            "organism": ux.get("organism"),
            "aliases": aliases,
            "target_type": ux.get("suggested_target_type"),
            "target_location": ux.get("suggested_target_location"),
            "description": (ux.get("function_text") or "")[:1000] or None,
        },
        "hints": {
            "target_type_reason": ux.get("suggested_target_type_reason"),
            "target_location_reason": ux.get("suggested_target_location_reason"),
            "entry_type": ux.get("entry_type"),
            "entry_version": ux.get("entry_version"),
            "tax_id": ux.get("tax_id"),
            "sequence_length": ux.get("sequence_length"),
            "is_human": ux.get("tax_id") == 9606,
        },
        "snapshot": {
            "source": "uniprot",
            "source_id": entry.get("primaryAccession") or accession,
            "source_version": str(ux.get("entry_version") or ""),
            "source_url": f"{UNIPROT_BASE}/{entry.get('primaryAccession') or accession}.json",
            "fetched_at": fetched,
            "payload": trim_uniprot_payload(entry),
            "license": UNIPROT_LICENSE,
        },
    }
