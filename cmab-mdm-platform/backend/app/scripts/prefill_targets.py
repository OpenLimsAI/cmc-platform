"""靶点域批量预填脚本（离线，产出预填 JSON + 汇总表；不自动落库）

设计决策 docs/decisions/2026-08-17-target-domain.md 第 7 条：一期不做前端向导，
录入量小（50–100 条），用本脚本离线批量出预填 JSON → 人工在普通表单核对保存。

两种模式：
  1) 预填（默认）：INN 列表 → ChEMBL/UniProt → 每个 INN 一份 prefill_form.json + 原始响应存档 +
     总表 summary.md / summary.csv。查重直接查真实 tgt.target（只读，主+次级 accession）。
  2) --attach-snapshots：人工把靶点录进系统后再跑一次，把已抓取的原文按 uniprot_id 写进
     tgt.target_source_snapshot（append-only；同 target+source+source_id+fetched_at 已存在则跳过）。

用法（backend 容器内 / Linux .venv）：
  python -m app.scripts.prefill_targets --inn guselkumab pembrolizumab --out data/target_prefill
  python -m app.scripts.prefill_targets --file inns.txt --out data/target_prefill --no-proxy
  python -m app.scripts.prefill_targets --attach-snapshots --out data/target_prefill --user admin

外部调用只读 GET，只访问 www.ebi.ac.uk / rest.uniprot.org。
"""
from __future__ import annotations

import argparse
import asyncio
import csv
import json
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

from sqlalchemy import select

from app.core.database import AsyncSessionLocal, engine
from app.domains.auth.models import User
from app.domains.target.models import TargetSourceSnapshot
from app.domains.target.prefill import (
    ALLOWED_HOSTS,
    CHEMBL_BASE,
    CHEMBL_LICENSE,
    UNIPROT_BASE,
    UNIPROT_LICENSE,
    prefill_inn,
    trim_chembl_target_payload,
    trim_uniprot_payload,
)
from app.domains.target.services import TargetService
from app.shared.http_client import ExternalHttpClient


def slug(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", s.lower()).strip("_")


def dump(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2, default=str), encoding="utf-8")


# ----------------------------------------------------------------------------- 模式 1：预填
async def _db_lookup_factory():
    """返回 (lookup 回调, 关闭函数)：按 accession 查真实 tgt.target（只读）"""
    session = AsyncSessionLocal()
    svc = TargetService(session)

    async def lookup(acc: str) -> dict[str, Any] | None:
        t = await svc.find_by_accession(acc)
        if t is None:
            return None
        return {"target_code": t.target_code, "target_name": t.target_name, "uniprot_id": t.uniprot_id, "status": t.status}

    async def close() -> None:
        await session.close()

    return lookup, close


def _write_case(out_dir: Path, r: dict[str, Any]) -> None:
    case = out_dir / slug(r["inn"])
    raw = r.pop("raw", {}) or {}
    if raw.get("chembl_molecule_search") is not None:
        dump(case / "01_chembl_molecule_search.json", raw["chembl_molecule_search"])
    if raw.get("chembl_mechanism") is not None:
        dump(case / "02_chembl_mechanism.json", raw["chembl_mechanism"])
    if raw.get("chembl_mechanism_parent") is not None:
        dump(case / "02b_chembl_mechanism_parent.json", raw["chembl_mechanism_parent"])
    for tid, t in (raw.get("chembl_target") or {}).items():
        dump(case / f"03_chembl_target_{tid}.json", t)
    for acc, u in (raw.get("uniprot") or {}).items():
        dump(case / f"05_uniprot_{acc}.json", u)
    dump(case / "prefill_form.json", r.get("prefill_form"))
    dump(case / "run_result.json", r)


def _write_summary(out_dir: Path, results: list[dict[str, Any]]) -> None:
    rows: list[dict[str, Any]] = []
    md: list[str] = ["# 靶点预填汇总", "", f"生成时间：{datetime.now().isoformat(timespec='seconds')}", ""]
    for r in results:
        pf = r.get("prefill_form") or {}
        mol = r.get("molecule") or {}
        md.append(f"## {r['inn']} — {r['outcome']}")
        if r.get("user_message"):
            md.append(f"> {r['user_message']}")
        if r.get("error"):
            md.append(f"> ❌ 外部调用失败：{r['error']}")
        if mol:
            md.append(f"- 分子：{mol.get('chembl_id')} / {mol.get('pref_name')} / {mol.get('molecule_type')} / phase {mol.get('max_phase')} "
                      f"/ 研发代号 {', '.join(mol.get('research_codes') or [])} / 商品名 {', '.join(mol.get('trade_names') or [])}")
        for w in r.get("warnings") or []:
            md.append(f"- ⚠️ {w}")
        for t in pf.get("targets_existing_hit") or []:
            md.append(f"- ✅ 已有靶点命中：{t.get('target_code')} {t.get('target_name')} ({t.get('uniprot_id')}) → 只建关联")
        if pf.get("targets_new"):
            md += ["", "| 新靶点 | uniprot_id | gene | CD 号 | 分子功能关键词 | 亚细胞定位 | 条目类型 |", "|---|---|---|---|---|---|---|"]
            for t in pf["targets_new"]:
                mf = ", ".join(k["name"] for k in (t.get("keywords") or []) if k.get("category") == "Molecular function")
                locs = "; ".join(sl["location"] + (f" [{sl['topology']}]" if sl.get("topology") else "") for sl in (t.get("subcellular_locations") or []))
                md.append(f"| {t['target_name']} | {t['uniprot_id']} | {t.get('gene_symbol') or ''} | {', '.join(t.get('cd_antigen_names') or [])} | "
                          f"{mf} | {locs[:80]} | {t.get('entry_type') or ''} |")
        if pf.get("bridge_molecule_target"):
            md += ["", "| 关联 | uniprot_id | target_code | relation_role | MoA | action | 表位/域 | 需确认 | 原因 |", "|---|---|---|---|---|---|---|---|---|"]
            for b in pf["bridge_molecule_target"]:
                md.append(f"| {b.get('_target_pref_name_chembl') or ''} | {b.get('uniprot_id') or ''} | {b.get('target_code') or ''} | "
                          f"{b.get('relation_role')} | {b.get('moa') or ''} | {b.get('action_type') or ''} | {b.get('binding_epitope_or_domain') or ''} | "
                          f"{'是' if b.get('needs_confirm') else '否'} | {(b.get('_confirm_reason') or '')[:80]} |")
                rows.append({
                    "inn": r["inn"], "outcome": r["outcome"], "molecule_chembl_id": mol.get("chembl_id"),
                    "molecule_type": mol.get("molecule_type"), "target_code": b.get("target_code"),
                    "uniprot_id": b.get("uniprot_id"), "target_name_chembl": b.get("_target_pref_name_chembl"),
                    "relation_role": b.get("relation_role"), "moa": b.get("moa"), "action_type": b.get("action_type"),
                    "binding_epitope_or_domain": b.get("binding_epitope_or_domain"),
                    "needs_confirm": b.get("needs_confirm"), "confirm_reason": b.get("_confirm_reason"),
                })
        if not pf.get("bridge_molecule_target"):
            rows.append({"inn": r["inn"], "outcome": r["outcome"], "molecule_chembl_id": mol.get("chembl_id"),
                         "molecule_type": mol.get("molecule_type")})
        md.append("")
    (out_dir / "summary.md").write_text("\n".join(md), encoding="utf-8")
    fields = ["inn", "outcome", "molecule_chembl_id", "molecule_type", "target_code", "uniprot_id", "target_name_chembl",
              "relation_role", "moa", "action_type", "binding_epitope_or_domain", "needs_confirm", "confirm_reason"]
    with (out_dir / "summary.csv").open("w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)


async def run_prefill(inns: list[str], out_dir: Path, *, no_proxy: bool, timeout_s: float) -> int:
    lookup, close = await _db_lookup_factory()
    results: list[dict[str, Any]] = []
    try:
        async with ExternalHttpClient(ALLOWED_HOSTS, timeout_s=timeout_s, trust_env=not no_proxy) as client:
            for inn in inns:
                print(f"===== {inn} =====", flush=True)
                r = await prefill_inn(inn, client, lookup)
                r["http_calls"] = list(client.calls)
                client.calls.clear()
                _write_case(out_dir, r)
                pf = r.get("prefill_form") or {}
                print(f"  outcome={r['outcome']} new={len(pf.get('targets_new') or [])} "
                      f"hit={len(pf.get('targets_existing_hit') or [])} bridge={len(pf.get('bridge_molecule_target') or [])} "
                      f"warnings={len(r.get('warnings') or [])} error={r.get('error')}", flush=True)
                results.append(r)
    finally:
        await close()
    _write_summary(out_dir, results)
    print(f"\n产物目录：{out_dir}（summary.md / summary.csv / <inn>/prefill_form.json）")
    failed = [r["inn"] for r in results if r["outcome"] == "ERROR_EXTERNAL_CALL"]
    if failed:
        print(f"外部调用失败：{failed}")
        return 2
    return 0


# ----------------------------------------------------------------------------- 模式 2：回填快照
async def run_attach_snapshots(out_dir: Path, username: str) -> int:
    created = skipped = missing = 0
    async with AsyncSessionLocal() as db:
        user = (await db.execute(select(User).where(User.username == username))).scalar_one_or_none()
        if user is None:
            print(f"用户 {username} 不存在", file=sys.stderr)
            return 1
        svc = TargetService(db)
        for case in sorted(p for p in out_dir.iterdir() if p.is_dir()):
            rr = case / "run_result.json"
            if not rr.exists():
                continue
            r = json.loads(rr.read_text(encoding="utf-8"))
            fetched_at = datetime.fromisoformat(r["fetched_at"])
            mol = r.get("molecule") or {}
            mech_raw = json.loads((case / "02_chembl_mechanism.json").read_text()) if (case / "02_chembl_mechanism.json").exists() else None
            targets_raw = {p.name[len("03_chembl_target_"):-5]: json.loads(p.read_text()) for p in case.glob("03_chembl_target_*.json")}
            uniprot_raw = {p.name[len("05_uniprot_"):-5]: json.loads(p.read_text()) for p in case.glob("05_uniprot_*.json")}

            # 该 INN 涉及的每个 accession → 现在库里有没有
            accs = {b.get("uniprot_id") for b in ((r.get("prefill_form") or {}).get("bridge_molecule_target") or []) if b.get("uniprot_id")}
            for acc in sorted(accs):
                target = await svc.find_by_accession(acc)
                if target is None:
                    missing += 1
                    print(f"  [{r['inn']}] {acc} 尚未录入 tgt.target，跳过")
                    continue
                snaps: list[dict[str, Any]] = []
                if acc in uniprot_raw and uniprot_raw[acc]:
                    u = uniprot_raw[acc]
                    snaps.append({"source": "uniprot", "source_id": acc,
                                  "source_version": str(((u.get("entryAudit") or {}).get("entryVersion")) or ""),
                                  "source_url": f"{UNIPROT_BASE}/{acc}.json", "payload": trim_uniprot_payload(u), "license": UNIPROT_LICENSE})
                for tid, t in targets_raw.items():
                    if t and any(c.get("accession") == acc for c in t.get("target_components") or []):
                        snaps.append({"source": "chembl_target", "source_id": tid, "source_version": None,
                                      "source_url": f"{CHEMBL_BASE}/target/{tid}.json", "payload": trim_chembl_target_payload(t), "license": CHEMBL_LICENSE})
                if mech_raw and mol.get("chembl_id"):
                    snaps.append({"source": "chembl_mechanism", "source_id": mol["chembl_id"], "source_version": None,
                                  "source_url": f"{CHEMBL_BASE}/mechanism.json?molecule_chembl_id={mol['chembl_id']}",
                                  "payload": {"inn": r["inn"], "mechanisms": mech_raw.get("mechanisms")}, "license": CHEMBL_LICENSE})
                for s in snaps:
                    exists = (await db.execute(
                        select(TargetSourceSnapshot.snapshot_id).where(
                            TargetSourceSnapshot.target_id == target.target_id,
                            TargetSourceSnapshot.source == s["source"],
                            TargetSourceSnapshot.source_id == s["source_id"],
                            TargetSourceSnapshot.fetched_at == fetched_at,
                        )
                    )).scalar_one_or_none()
                    if exists:
                        skipped += 1
                        continue
                    db.add(TargetSourceSnapshot(target_id=target.target_id, fetched_at=fetched_at, created_by=user.user_id, **s))
                    created += 1
                    print(f"  [{r['inn']}] {target.target_code} ← {s['source']}:{s['source_id']}")
        await db.commit()
    await engine.dispose()
    print(f"snapshots created={created} skipped(exists)={skipped} targets_missing={missing}")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--inn", nargs="*", default=[], help="INN 列表")
    ap.add_argument("--file", help="每行一个 INN 的文本文件（# 开头为注释）")
    ap.add_argument("--out", default="data/target_prefill", help="产物目录")
    ap.add_argument("--no-proxy", action="store_true", help="忽略 HTTP(S)_PROXY 环境变量直连（Mac ClashX 场景）")
    ap.add_argument("--timeout", type=float, default=30.0, help="单次外部调用超时秒数")
    ap.add_argument("--attach-snapshots", action="store_true", help="回填快照模式（读 --out 目录，写 tgt.target_source_snapshot）")
    ap.add_argument("--user", default="admin", help="回填快照的操作人 username")
    args = ap.parse_args(argv)
    out_dir = Path(args.out)

    if args.attach_snapshots:
        return asyncio.run(run_attach_snapshots(out_dir, args.user))

    inns = list(args.inn)
    if args.file:
        inns += [ln.strip() for ln in Path(args.file).read_text(encoding="utf-8").splitlines()
                 if ln.strip() and not ln.strip().startswith("#")]
    if not inns:
        ap.error("请用 --inn 或 --file 给出至少一个 INN")

    async def _run() -> int:
        try:
            return await run_prefill(inns, out_dir, no_proxy=args.no_proxy, timeout_s=args.timeout)
        finally:
            await engine.dispose()

    return asyncio.run(_run())


if __name__ == "__main__":
    sys.exit(main())
