#!/usr/bin/env python3
"""
PoC：靶点 / 抗体分子主数据 —— 由 INN 链式自动预填（ChEMBL → UniProt）。

链路
  INN
   → ChEMBL /molecule/search            分子：ChEMBL ID / 同义词 / 分子类型 / 最高阶段
   → ChEMBL /mechanism?molecule_chembl_id  MoA + target_chembl_id（可能多条：双抗 / 多靶）
   → ChEMBL /target/{target_chembl_id}    组分 → UniProt accession（PROTEIN COMPLEX 会有多个组分）
   → 查重 mock dim.target（uniprot_id 锚点）命中→只建 bridge；未命中→继续
   → UniProt /uniprotkb/{acc}.json        靶点详情 → 预填 dim.target
   → 输出预填表单 JSON（人工审核后发布，不落库）

约束：只读 GET，只访问 www.ebi.ac.uk / rest.uniprot.org；仅标准库（宿主机 Python 3.9 无 httpx）；
      不改现有代码、不建表、不跑 migration。所有产物写在本目录 output/ 下。

用法：
  python3 poc/target_prefill/prefill_target.py                 # 跑全部 5 个内置用例
  python3 poc/target_prefill/prefill_target.py guselkumab ...  # 跑指定 INN
"""
from __future__ import annotations

import json
import re
import socket
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

HERE = Path(__file__).resolve().parent
OUT_DIR = HERE / "output"
MOCK_DIM_TARGET = HERE / "mock_dim_target.json"

CHEMBL_BASE = "https://www.ebi.ac.uk/chembl/api/data"
UNIPROT_BASE = "https://rest.uniprot.org/uniprotkb"
ALLOWED_HOSTS = {"www.ebi.ac.uk", "rest.uniprot.org"}

TIMEOUT_S = 30
RETRIES = 3
BACKOFF_S = 2.0
USER_AGENT = "cmab-mdm-target-prefill-poc/0.1 (read-only GET; contact: cmab-mdm)"

DEFAULT_CASES = [
    "guselkumab",
    "pembrolizumab",
    "emicizumab",
    "trastuzumab deruxtecan",
    "notarealinnxyz",
]

# 目标枚举（最小化设计）
TARGET_TYPE_ENUM = ["受体", "配体·细胞因子", "表面抗原", "酶", "其他"]
TARGET_LOCATION_ENUM = ["膜型", "可溶型", "两者都有", "胞内"]


# ----------------------------------------------------------------------------- HTTP
class FetchError(Exception):
    def __init__(self, step: str, url: str, status: Optional[int], detail: str):
        super().__init__(f"[{step}] {url} -> HTTP {status}: {detail}")
        self.step, self.url, self.status, self.detail = step, url, status, detail


class HttpLog:
    """记录每次外部调用：URL / 状态 / 耗时 / 重试，供 test_report 引用。"""

    def __init__(self) -> None:
        self.calls: List[Dict[str, Any]] = []

    def add(self, **kw: Any) -> None:
        self.calls.append(kw)


def http_get_json(step: str, url: str, log: HttpLog) -> Tuple[int, Any]:
    host = urllib.parse.urlparse(url).hostname
    if host not in ALLOWED_HOSTS:
        raise FetchError(step, url, None, f"host {host} 不在白名单 {sorted(ALLOWED_HOSTS)}")
    # 显式绕开系统代理（本机 ClashX 7890），保证是直连真实结果
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    last_err = ""
    for attempt in range(1, RETRIES + 1):
        t0 = time.time()
        req = urllib.request.Request(url, headers={"Accept": "application/json", "User-Agent": USER_AGENT})
        try:
            with opener.open(req, timeout=TIMEOUT_S) as resp:
                status = resp.getcode()
                body = resp.read()
            elapsed = round(time.time() - t0, 3)
            data = json.loads(body.decode("utf-8")) if body else None
            log.add(step=step, url=url, http_status=status, elapsed_s=elapsed, attempt=attempt, ok=True)
            return status, data
        except urllib.error.HTTPError as e:
            elapsed = round(time.time() - t0, 3)
            body = e.read().decode("utf-8", "replace")[:500]
            log.add(step=step, url=url, http_status=e.code, elapsed_s=elapsed, attempt=attempt, ok=False, error=body)
            if e.code == 404:
                return 404, None
            last_err = f"HTTP {e.code}: {body}"
            if e.code < 500 and e.code != 429:
                raise FetchError(step, url, e.code, body)
        except (urllib.error.URLError, socket.timeout, TimeoutError, ConnectionError) as e:
            elapsed = round(time.time() - t0, 3)
            last_err = f"{type(e).__name__}: {e}"
            log.add(step=step, url=url, http_status=None, elapsed_s=elapsed, attempt=attempt, ok=False, error=last_err)
        if attempt < RETRIES:
            time.sleep(BACKOFF_S * attempt)
    raise FetchError(step, url, None, f"重试 {RETRIES} 次仍失败：{last_err}")


# ----------------------------------------------------------------------------- utils
def slug(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", s.lower()).strip("_")


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def dump(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")


def load_mock_dim_target() -> Dict[str, Dict[str, Any]]:
    data = json.loads(MOCK_DIM_TARGET.read_text(encoding="utf-8"))
    return {r["uniprot_id"]: r for r in data["records"]}


# ----------------------------------------------------------------------------- Step 1 ChEMBL molecule
def pick_molecule(inn: str, molecules: List[Dict[str, Any]]) -> Tuple[Optional[Dict[str, Any]], str, List[Dict[str, Any]]]:
    """按优先级挑：pref_name 精确 = INN > 同义词(INN/USAN)精确 = INN > 无（要人工挑）。返回 (选中, 依据, 候选摘要)。"""
    q = inn.strip().lower()
    cands = []
    for m in molecules:
        syns = [(s.get("molecule_synonym") or "").lower() for s in m.get("molecule_synonyms") or []]
        syn_types = {(s.get("molecule_synonym") or "").lower(): s.get("syn_type") for s in m.get("molecule_synonyms") or []}
        cands.append({
            "molecule_chembl_id": m.get("molecule_chembl_id"),
            "pref_name": m.get("pref_name"),
            "molecule_type": m.get("molecule_type"),
            "max_phase": m.get("max_phase"),
            "score": m.get("score"),
            "inn_synonym_hit": q in syns,
            "syn_type_of_hit": syn_types.get(q),
        })
    for m, c in zip(molecules, cands):
        if (m.get("pref_name") or "").lower() == q:
            return m, "pref_name 精确匹配 INN", cands
    for m, c in zip(molecules, cands):
        if c["inn_synonym_hit"]:
            return m, f"同义词精确匹配 INN（syn_type={c['syn_type_of_hit']}）", cands
    return None, "无精确匹配（仅模糊命中，需人工从候选中挑选）", cands


def extract_molecule(m: Dict[str, Any]) -> Dict[str, Any]:
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
        "synonyms": sorted({(s.get("molecule_synonym"), s.get("syn_type")) for s in syns}, key=lambda x: (x[1] or "", x[0] or "")),
        "research_codes": sorted({s.get("molecule_synonym") for s in syns if s.get("syn_type") == "RESEARCH_CODE"}),
        "trade_names": sorted({s.get("molecule_synonym") for s in syns if s.get("syn_type") == "TRADE_NAME"}),
        "molecule_hierarchy": m.get("molecule_hierarchy"),
        "biotherapeutic": {
            "helm_notation": bio.get("helm_notation"),
            "description": bio.get("description"),
            "biocomponents": [
                {"component_id": c.get("component_id"), "component_type": c.get("component_type"),
                 "description": c.get("description"), "organism": c.get("organism"),
                 "sequence_len": len(c.get("sequence") or "")}
                for c in (bio.get("biocomponents") or [])
            ],
        } if bio else None,
        "cross_references": [(x.get("xref_src"), x.get("xref_id")) for x in m.get("cross_references") or []],
        "atc_classifications": m.get("atc_classifications"),
    }


# ----------------------------------------------------------------------------- Step 4 UniProt → dim.target 预填
def _kw(entry: Dict[str, Any], category: str) -> List[str]:
    return [k.get("name") for k in entry.get("keywords") or [] if k.get("category") == category]


def suggest_target_type(entry: Dict[str, Any]) -> Tuple[str, str]:
    """启发式建议 target_type（5 选 1）；返回 (值, 依据)。仅供预填，必须人工确认。"""
    mf = set(_kw(entry, "Molecular function"))
    name = (((entry.get("proteinDescription") or {}).get("recommendedName") or {}).get("fullName") or {}).get("value", "") or ""
    gene = ((entry.get("genes") or [{}])[0].get("geneName") or {}).get("value", "") or ""
    enz_kw = {"Hydrolase", "Transferase", "Kinase", "Protease", "Oxidoreductase", "Lyase", "Isomerase", "Ligase",
              "Serine protease", "Metalloprotease", "Glycosidase", "Nuclease", "Phosphatase"}
    if mf & {"Cytokine", "Growth factor", "Hormone", "Chemokine"}:
        return "配体·细胞因子", f"UniProt keyword(Molecular function) ∈ {sorted(mf & {'Cytokine','Growth factor','Hormone','Chemokine'})}"
    if mf & {"Receptor", "G-protein coupled receptor", "Ion channel", "Transducer"}:
        return "受体", f"UniProt keyword(Molecular function) ∈ {sorted(mf & {'Receptor','G-protein coupled receptor','Ion channel','Transducer'})}"
    cd_names = [c.get("value") for c in (entry.get("proteinDescription") or {}).get("cdAntigenNames") or []]
    if cd_names:
        # UniProt 有 CD 编号（如 PD-1=CD279）→ 表面抗原；注意 HER2=CD340 也有 CD 号，但 Receptor keyword 规则在前已优先命中"受体"
        return "表面抗原", f"UniProt proteinDescription.cdAntigenNames={cd_names}"
    if mf & enz_kw or "EC " in json.dumps((entry.get("proteinDescription") or {}).get("recommendedName") or {}):
        return "酶", f"UniProt keyword ∈ {sorted(mf & enz_kw)} 或 recommendedName 含 EC 号"
    if re.match(r"^CD\d+", gene) or "antigen" in name.lower():
        return "表面抗原", f"名称/基因名启发（gene={gene}, name={name!r}）"
    if "receptor" in name.lower():
        return "受体", f"名称启发（name={name!r}）"
    return "其他", f"无规则命中（Molecular function keywords={sorted(mf)}）"


def suggest_target_location(entry: Dict[str, Any]) -> Tuple[str, str]:
    """启发式建议 target_location（4 选 1）：看 SUBCELLULAR LOCATION + Cellular component keywords。"""
    locs: List[str] = []
    for c in entry.get("comments") or []:
        if c.get("commentType") == "SUBCELLULAR LOCATION":
            for sl in c.get("subcellularLocations") or []:
                v = ((sl.get("location") or {}).get("value") or "")
                t = ((sl.get("topology") or {}).get("value") or "")
                locs.append(v + (f" [{t}]" if t else ""))
    cc = set(_kw(entry, "Cellular component"))
    txt = " | ".join(locs) + " | " + " | ".join(sorted(cc))
    low = txt.lower()
    membrane = ("membrane" in low and "secreted" not in low.split("|")[0]) or bool(cc & {"Membrane", "Cell membrane"})
    membrane = "membrane" in low
    soluble = "secreted" in low or "extracellular" in low
    intracellular_only = (not membrane and not soluble) and any(k in low for k in ("cytoplasm", "nucleus", "cytosol", "mitochondrion", "endoplasmic"))
    if membrane and soluble:
        return "两者都有", f"UniProt 定位同时含膜与分泌/胞外：{txt}"
    if membrane:
        return "膜型", f"UniProt 定位含 membrane：{txt}"
    if soluble:
        return "可溶型", f"UniProt 定位含 Secreted/extracellular：{txt}"
    if intracellular_only:
        return "胞内", f"UniProt 定位仅胞内：{txt}"
    return "膜型", f"无法判定（{txt!r}），默认膜型，需人工确认"


def extract_uniprot(entry: Dict[str, Any]) -> Dict[str, Any]:
    pd = entry.get("proteinDescription") or {}
    rec = (pd.get("recommendedName") or {})
    alt = [((a.get("fullName") or {}).get("value")) for a in pd.get("alternativeNames") or []]
    genes = entry.get("genes") or []
    func = ""
    for c in entry.get("comments") or []:
        if c.get("commentType") == "FUNCTION":
            func = " ".join(t.get("value", "") for t in c.get("texts") or [])
            break
    domains = [
        {"type": f.get("type"), "description": f.get("description"),
         "start": ((f.get("location") or {}).get("start") or {}).get("value"),
         "end": ((f.get("location") or {}).get("end") or {}).get("value")}
        for f in entry.get("features") or []
        if f.get("type") in ("Domain", "Region", "Topological domain", "Transmembrane", "Signal", "Chain")
    ]
    ttype, ttype_why = suggest_target_type(entry)
    tloc, tloc_why = suggest_target_location(entry)
    return {
        "uniprot_id": entry.get("primaryAccession"),
        "uniprot_entry_name": entry.get("uniProtkbId"),
        "entry_type": entry.get("entryType"),
        "secondary_accessions": entry.get("secondaryAccessions"),
        "recommended_name": (rec.get("fullName") or {}).get("value"),
        "short_names": [s.get("value") for s in rec.get("shortNames") or []],
        "alternative_names": alt,
        "gene_symbol": ((genes[0].get("geneName") or {}).get("value")) if genes else None,
        "gene_synonyms": [s.get("value") for s in (genes[0].get("synonyms") or [])] if genes else [],
        "organism": (entry.get("organism") or {}).get("scientificName"),
        "tax_id": (entry.get("organism") or {}).get("taxonId"),
        "sequence_length": (entry.get("sequence") or {}).get("length"),
        "mol_weight_da": (entry.get("sequence") or {}).get("molWeight"),
        "function_text": func[:1000],
        "keywords": [(k.get("category"), k.get("name")) for k in entry.get("keywords") or []],
        "domains_and_regions": domains,
        "entry_audit": entry.get("entryAudit"),
        "suggested_target_type": ttype, "suggested_target_type_reason": ttype_why,
        "suggested_target_location": tloc, "suggested_target_location_reason": tloc_why,
    }


def binding_subunit_hint(binding_site_comment: Optional[str], comp: Dict[str, Any], ux: Optional[Dict[str, Any]]) -> Optional[str]:
    """PROTEIN COMPLEX 时用 mechanism.binding_site_comment 提示哪一亚基是结合亚基。
    例：'Alpha (p19) subunit is binding site' vs 组分 'Interleukin-23 subunit alpha' → LIKELY。"""
    if not binding_site_comment:
        return None
    tokens = {t for t in re.findall(r"[a-z0-9]+", binding_site_comment.lower()) if len(t) > 2 and t not in ("subunit", "binding", "site", "the", "and", "chain")}
    hay = " ".join(filter(None, [comp.get("component_description") or "", comp.get("gene_symbol") or ""] +
                          ((ux or {}).get("short_names") or []) + ((ux or {}).get("alternative_names") or []) +
                          ((ux or {}).get("gene_synonyms") or []))).lower()
    return "LIKELY" if any(t in hay for t in tokens) else "UNLIKELY"


# ----------------------------------------------------------------------------- pipeline
def run_case(inn: str, mock_dim: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
    case_dir = OUT_DIR / slug(inn)
    log = HttpLog()
    fetched_at = now_iso()
    result: Dict[str, Any] = {"inn": inn, "fetched_at": fetched_at, "steps": [], "warnings": [], "outcome": None}
    steps = result["steps"]

    def step_note(name: str, **kw: Any) -> None:
        steps.append({"step": name, **kw})

    try:
        # ---- Step 1: molecule search
        url = f"{CHEMBL_BASE}/molecule/search.json?{urllib.parse.urlencode({'q': inn, 'limit': 20})}"
        status, data = http_get_json("1_chembl_molecule_search", url, log)
        dump(case_dir / "01_chembl_molecule_search.json", data)
        mols = (data or {}).get("molecules") or []
        total = ((data or {}).get("page_meta") or {}).get("total_count")
        if not mols:
            step_note("1_chembl_molecule_search", http_status=status, total_count=total, result="NO_MATCH")
            result["outcome"] = "REJECTED_NO_MOLECULE"
            result["user_message"] = f"ChEMBL 查无「{inn}」（total_count={total}）。请检查 INN 拼写；若为新分子/未收录，请走人工录入。"
            return result
        mol, why, cands = pick_molecule(inn, mols)
        step_note("1_chembl_molecule_search", http_status=status, total_count=total, pick_reason=why, candidates=cands[:10])
        if mol is None:
            result["outcome"] = "NEEDS_MANUAL_PICK"
            result["user_message"] = f"ChEMBL 对「{inn}」有 {total} 个模糊候选但无精确匹配，请人工从候选中选择 ChEMBL ID 后重试。"
            return result
        molecule = extract_molecule(mol)
        result["molecule"] = molecule
        if (molecule["pref_name"] or "").lower() != inn.lower():
            result["warnings"].append(f"选中分子 pref_name={molecule['pref_name']!r} 与输入 INN 不同（依据：{why}），请人工确认。")

        # ---- Step 2: mechanism（先按本体查，空则回退 parent）
        chembl_id = molecule["chembl_id"]
        url = f"{CHEMBL_BASE}/mechanism.json?molecule_chembl_id={chembl_id}"
        status, data = http_get_json("2_chembl_mechanism", url, log)
        dump(case_dir / "02_chembl_mechanism.json", data)
        mechs = (data or {}).get("mechanisms") or []
        parent = ((molecule.get("molecule_hierarchy") or {}).get("parent_chembl_id"))
        if not mechs and parent and parent != chembl_id:
            url2 = f"{CHEMBL_BASE}/mechanism.json?molecule_chembl_id={parent}"
            status2, data2 = http_get_json("2b_chembl_mechanism_parent", url2, log)
            dump(case_dir / "02b_chembl_mechanism_parent.json", data2)
            mechs = (data2 or {}).get("mechanisms") or []
            result["warnings"].append(f"本体 {chembl_id} 无 mechanism，已回退 parent {parent} 查得 {len(mechs)} 条。")
        step_note("2_chembl_mechanism", http_status=status, mechanism_count=len(mechs),
                  mechanisms=[{k: m.get(k) for k in ("mec_id", "mechanism_of_action", "action_type", "target_chembl_id",
                                                     "binding_site_comment", "direct_interaction", "molecular_mechanism",
                                                     "disease_efficacy", "max_phase")} for m in mechs])
        if not mechs:
            result["outcome"] = "MOLECULE_ONLY_NO_MECHANISM"
            result["user_message"] = "ChEMBL 有分子记录但无 mechanism（MoA/靶点）记录，靶点需人工填写。"
            result["prefill_form"] = {"molecule": molecule, "targets": [], "bridge_molecule_target": []}
            return result
        if len(mechs) > 1:
            result["warnings"].append(f"该分子有 {len(mechs)} 条 mechanism 记录（多靶点/双特异性），每条靶点关联均需人工确认。")

        # ---- Step 3: target → UniProt accession（按 target_chembl_id 去重）
        targets_by_id: Dict[str, Dict[str, Any]] = {}
        for m in mechs:
            tid = m.get("target_chembl_id")
            if not tid:
                result["warnings"].append(f"mechanism mec_id={m.get('mec_id')} 无 target_chembl_id（{m.get('mechanism_of_action')}），跳过。")
                continue
            if tid in targets_by_id:
                continue
            url = f"{CHEMBL_BASE}/target/{tid}.json"
            status, tdata = http_get_json("3_chembl_target", url, log)
            dump(case_dir / f"03_chembl_target_{tid}.json", tdata)
            if status == 404 or not tdata:
                result["warnings"].append(f"target {tid} 404/空。")
                targets_by_id[tid] = {"target_chembl_id": tid, "http_status": status, "components": []}
                continue
            comps = []
            for c in tdata.get("target_components") or []:
                comps.append({
                    "accession": c.get("accession"),
                    "component_type": c.get("component_type"),
                    "component_description": c.get("component_description"),
                    "relationship": c.get("relationship"),
                    "gene_symbol": next((s.get("component_synonym") for s in c.get("target_component_synonyms") or []
                                         if s.get("syn_type") == "GENE_SYMBOL"), None),
                    "uniprot_xref": [x.get("xref_id") for x in c.get("target_component_xrefs") or [] if x.get("xref_src_db") == "UniProt"],
                })
            targets_by_id[tid] = {
                "target_chembl_id": tid, "http_status": status,
                "pref_name": tdata.get("pref_name"), "target_type_chembl": tdata.get("target_type"),
                "organism": tdata.get("organism"), "tax_id": tdata.get("tax_id"),
                "top_level_cross_references": tdata.get("cross_references"),
                "components": comps,
            }
            tt = tdata.get("target_type")
            if tt == "PROTEIN COMPLEX":
                result["warnings"].append(f"target {tid}（{tdata.get('pref_name')}）为 PROTEIN COMPLEX，含 {len(comps)} 个亚基；"
                                          f"dim.target 以 UniProt 为锚点会拆成 {len(comps)} 条，请人工确认抗体实际结合的亚基（可参考 mechanism.binding_site_comment）。")
            elif tt not in ("SINGLE PROTEIN", None):
                result["warnings"].append(f"target {tid}（{tdata.get('pref_name')}）为 {tt}（ChEMBL 把 {len(comps)} 个蛋白合并为一组，常见于双抗/多靶）；"
                                          f"每个组分各建一条 bridge，请人工确认。")
            if tdata.get("tax_id") not in (9606, None):
                result["warnings"].append(f"target {tid} 物种 tax_id={tdata.get('tax_id')}（非人），请确认。")
        step_note("3_chembl_target", targets=list(targets_by_id.values()))

        # ---- Step 4: dedup vs mock dim.target + Step 5 UniProt
        prefill_targets: List[Dict[str, Any]] = []
        bridge: List[Dict[str, Any]] = []
        uniprot_cache: Dict[str, Dict[str, Any]] = {}
        dedup_log: List[Dict[str, Any]] = []
        for m in mechs:
            tid = m.get("target_chembl_id")
            tinfo = targets_by_id.get(tid) if tid else None
            comps = (tinfo or {}).get("components") or []
            protein_comps = [c for c in comps if c.get("accession")]
            if not protein_comps:
                bridge.append({
                    "molecule_chembl_id": chembl_id, "molecule_inn": inn,
                    "target_code": None, "uniprot_id": None, "target_chembl_id": tid,
                    "moa": m.get("mechanism_of_action"), "action_type": m.get("action_type"),
                    "binding_site_or_domain": m.get("binding_site_comment"),
                    "needs_manual_confirm": True,
                    "confirm_reason": "ChEMBL target 无蛋白组分/无 UniProt accession，需人工指定靶点",
                })
                continue
            for c in protein_comps:
                acc = c["accession"]
                hit = mock_dim.get(acc)
                if hit:
                    dedup_log.append({"uniprot_id": acc, "hit": True, "existing_target_code": hit["target_code"]})
                    target_code = hit["target_code"]
                    dedup_action = "HIT_EXISTING_TARGET_ONLY_LINK"
                else:
                    dedup_log.append({"uniprot_id": acc, "hit": False})
                    if acc not in uniprot_cache:
                        url = f"{UNIPROT_BASE}/{acc}.json"
                        status, udata = http_get_json("5_uniprot_entry", url, log)
                        dump(case_dir / f"05_uniprot_{acc}.json", udata)
                        if status == 404 or not udata:
                            uniprot_cache[acc] = {"uniprot_id": acc, "_error": f"UniProt HTTP {status}"}
                        else:
                            ux = extract_uniprot(udata)
                            ux["_http_status"] = status
                            uniprot_cache[acc] = ux
                    ux = uniprot_cache[acc]
                    target_code = f"<NEW:{acc}>"  # 正式实现由 MDM 编码服务生成
                    dedup_action = "NEW_TARGET_PREFILLED_FROM_UNIPROT"
                    if not any(t.get("uniprot_id") == acc for t in prefill_targets):
                        prefill_targets.append({
                            "target_code": target_code,
                            "target_name": ux.get("recommended_name") or c.get("component_description"),
                            "uniprot_id": acc,
                            "target_type": ux.get("suggested_target_type"),
                            "target_type_reason": ux.get("suggested_target_type_reason"),
                            "target_type_enum": TARGET_TYPE_ENUM,
                            "target_location": ux.get("suggested_target_location"),
                            "target_location_reason": ux.get("suggested_target_location_reason"),
                            "target_location_enum": TARGET_LOCATION_ENUM,
                            "gene_symbol": ux.get("gene_symbol") or c.get("gene_symbol"),
                            "organism": ux.get("organism"),
                            "aliases": (ux.get("short_names") or []) + (ux.get("alternative_names") or []),
                            "chembl_target_id": tid,
                            "chembl_target_pref_name": (tinfo or {}).get("pref_name"),
                            "chembl_target_type": (tinfo or {}).get("target_type_chembl"),
                            "uniprot_extract": ux,
                            "raw_refs": {
                                "uniprot_raw_file": f"output/{slug(inn)}/05_uniprot_{acc}.json",
                                "chembl_target_raw_file": f"output/{slug(inn)}/03_chembl_target_{tid}.json",
                                "fetched_at": fetched_at,
                            },
                            "needs_manual_confirm": True,
                            "confirm_reason": "target_type / target_location 为启发式建议",
                        })
                needs = len(mechs) > 1 or len(protein_comps) > 1
                reasons = []
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
                role_hint = None
                if "conjugate" in (molecule.get("molecule_type") or "").lower():
                    loc = (uniprot_cache.get(acc) or {}).get("suggested_target_location") or (mock_dim.get(acc) or {}).get("target_location")
                    role_hint = "PAYLOAD_TARGET(载荷靶点，通常不建抗体-靶点关联)" if loc == "胞内" else "ANTIBODY_TARGET(抗体结合靶点)"
                    if role_hint.startswith("PAYLOAD"):
                        reasons.append("ADC 载荷（payload）作用靶点，是否录入 bridge 需业务确定")
                bridge.append({
                    "molecule_chembl_id": chembl_id, "molecule_inn": inn,
                    "target_code": target_code, "uniprot_id": acc,
                    "target_chembl_id": tid, "target_pref_name_chembl": (tinfo or {}).get("pref_name"),
                    "component_description": c.get("component_description"),
                    "moa": m.get("mechanism_of_action"), "action_type": m.get("action_type"),
                    "binding_site_or_domain": m.get("binding_site_comment"),
                    "direct_interaction": m.get("direct_interaction"),
                    "dedup_action": dedup_action,
                    "binding_subunit_hint": subunit_hint,
                    "adc_role_hint": role_hint,
                    "needs_manual_confirm": needs,
                    "confirm_reason": "；".join(reasons) or None,
                    "chembl_mechanism_raw_file": f"output/{slug(inn)}/02_chembl_mechanism.json",
                    "fetched_at": fetched_at,
                })
        step_note("4_dedup_dim_target", dedup=dedup_log)
        step_note("5_uniprot", fetched=[{"uniprot_id": k, "http_status": v.get("_http_status"), "error": v.get("_error")} for k, v in uniprot_cache.items()])

        result["prefill_form"] = {
            "_note": "预填表单：所有字段供人工审核；不自动落库。target_code=<NEW:...> 表示待编码服务分配。",
            "molecule": {
                **molecule,
                "raw_refs": {"chembl_molecule_raw_file": f"output/{slug(inn)}/01_chembl_molecule_search.json", "fetched_at": fetched_at},
            },
            "targets_new": prefill_targets,
            "targets_existing_hit": [mock_dim[d["uniprot_id"]] for d in dedup_log if d["hit"]],
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
    except FetchError as e:
        result["outcome"] = "ERROR_EXTERNAL_CALL"
        result["error"] = {"step": e.step, "url": e.url, "http_status": e.status, "detail": e.detail}
        return result
    finally:
        result["http_calls"] = log.calls
        dump(case_dir / "prefill_form.json", result.get("prefill_form"))
        dump(case_dir / "run_result.json", result)


def main(argv: List[str]) -> int:
    cases = argv[1:] or DEFAULT_CASES
    mock_dim = load_mock_dim_target()
    summary = []
    for inn in cases:
        print(f"\n===== {inn} =====")
        r = run_case(inn, mock_dim)
        pf = r.get("prefill_form") or {}
        line = {
            "inn": inn, "outcome": r["outcome"],
            "molecule_chembl_id": (r.get("molecule") or {}).get("chembl_id"),
            "molecule_type": (r.get("molecule") or {}).get("molecule_type"),
            "mechanisms": next((s.get("mechanism_count") for s in r["steps"] if s["step"] == "2_chembl_mechanism"), 0),
            "targets_new": len(pf.get("targets_new") or []),
            "targets_existing_hit": len(pf.get("targets_existing_hit") or []),
            "bridge_records": len(pf.get("bridge_molecule_target") or []),
            "bridge_needs_confirm": sum(1 for b in pf.get("bridge_molecule_target") or [] if b.get("needs_manual_confirm")),
            "warnings": r.get("warnings"),
            "http_calls": [(c["step"], c["http_status"], c["url"]) for c in r.get("http_calls", [])],
            "user_message": r.get("user_message"),
            "error": r.get("error"),
        }
        summary.append(line)
        print(json.dumps(line, ensure_ascii=False, indent=1))
    dump(OUT_DIR / "run_summary.json", {"generated_at": now_iso(), "cases": summary})
    print(f"\n产物目录：{OUT_DIR}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
