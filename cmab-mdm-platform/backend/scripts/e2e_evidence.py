"""Allowlisted evidence from the owned synthetic fixture, never auth material."""
import hashlib
import json
import re
import subprocess
from datetime import UTC, datetime


def collect(runtime, *, stage="snapshot"):
    runtime.verify()
    spec = runtime.spec
    directory = spec.output("evidence")
    directory.mkdir(exist_ok=True)
    sql = """SELECT json_build_object(
      'projects',(SELECT json_agg(json_build_object('id',project_id,'code',project_code,'status',status,'version',version)) FROM prs.project),
      'links',(SELECT json_agg(json_build_object('mdm_project_id',project_id,'pm_project_id',pm_project_id,'created_by',created_by)) FROM prs.project_pm_link),
      'requests',(SELECT json_agg(json_build_object('request_id',request_id,'project_id',project_id,'status',status,'attempts',attempts,'pm_project_id',remote_project_id)) FROM prs.project_pm_create_request),
      'signatures',(SELECT count(*) FROM audit.e_signature),
      'status_history',(SELECT count(*) FROM prs.project_status_history),
      'link_audits',(SELECT count(*) FROM audit.audit_log WHERE entity_table='project_pm_link' AND action='CREATE'),
      'proofs',(SELECT json_object_agg(status,n) FROM (SELECT status,count(*) n FROM auth.oidc_signature_challenge GROUP BY status) a))"""
    pm_sql = """SELECT json_build_object(
      'projects',(SELECT json_agg(json_build_object('id',id,'code',code,'owner_id',owner_id,'status',status)) FROM projects),
      'receipts',(SELECT count(*) FROM mdm_project_receipts))"""
    states = {}
    for key, database, query in [("mdm", "cmab_signing_e2e", sql), ("pm", "pm_signing_e2e", pm_sql)]:
        states[key] = json.loads(runtime.docker("exec", spec.run_id + "-pg", "psql", "-U", "cmab_app", "-d", database, "-Atc", query))
    stamp = datetime.now(UTC)
    record = {"time_utc": stamp.isoformat(), "stage": stage, "synthetic_only": True, **states}
    target = directory / ("business-" + stamp.strftime("%H%M%S%f") + ".json")
    target.write_text(json.dumps(record, indent=2), encoding="utf-8")
    raw = runtime.docker("logs", spec.run_id + "-proxy").decode(errors="replace")
    safe = [row for row in raw.splitlines() if re.fullmatch(r"2026-\S+ (GET|POST|OPTIONS|DELETE|PATCH|PUT) /[^?\s]* \d{3} (\d{3}|-)", row)]
    (directory / "http-status-only.log").write_text("\n".join(safe) + "\n", encoding="utf-8")
    images = json.loads(runtime.docker("inspect", *runtime.manifest["containers"].values()))
    inventory = [{"name": item["Name"], "id": item["Id"], "image": item["Config"]["Image"],
                  "image_id": item["Image"], "created": item["Created"],
                  "ports": item["NetworkSettings"]["Ports"], "tmpfs": list(item["HostConfig"].get("Tmpfs", {}))} for item in images]
    (directory / "runtime-inventory.json").write_text(json.dumps(inventory, indent=2), encoding="utf-8")
    sources = []
    from scripts.e2e_runtime import APP
    for root in [APP.parent, runtime.pm_root]:
        if root is None:
            continue
        def call(*args, r=root):
            return subprocess.run(["git", "-C", str(r), *args], capture_output=True, text=True, check=True).stdout.strip()
        changed = set(call("diff", "--name-only").splitlines() + call("ls-files", "--others", "--exclude-standard").splitlines())
        files = []
        for name in sorted(changed):
            p = root / name
            if p.is_file() and "/docs/" not in name and p.suffix in {".py", ".ts", ".tsx", ".mjs", ".json", ".yml"}:
                files.append({"path": name, "sha256": hashlib.sha256(p.read_bytes()).hexdigest()})
        sources.append({"base_head": call("rev-parse", "HEAD"), "branch": call("branch", "--show-current"), "candidate_files": files})
    (directory / "source-manifest.json").write_text(json.dumps(sources, indent=2), encoding="utf-8")
    runtime.checkpoint("evidence_saved", business_file=target.name, http_rows=len(safe), secrets_collected=False)
    return record
