"""Finite controls for the owned empty fixture, never an arbitrary exec API."""
import json
import re
import time
from datetime import UTC, datetime, timedelta

ACTIONS = {"snapshot", "fault-next-link", "stop-mdm", "start-mdm", "restart-apps"}


def validate_request(value):
    if not isinstance(value, dict) or value.get("action") not in ACTIONS or not re.fullmatch(r"[a-f0-9]{32}", str(value.get("id", ""))):
        raise ValueError("Unrecognized fixture control")
    allowed = {"id", "action", "stage"}
    if value["action"] == "fault-next-link":
        allowed.add("project_code")
        if not re.fullmatch(r"CMAB-PRJ-\d{4}-\d{4,8}", str(value.get("project_code", ""))):
            raise ValueError("Fault target must be an observed synthetic project code")
    if set(value) - allowed or not re.fullmatch(r"[a-z0-9-]{1,60}", value.get("stage", "snapshot")):
        raise ValueError("Unexpected control fields")
    return value


def check_fault_target(value):
    if not isinstance(value, dict) or type(value.get("id")) is not int or value["id"] <= 0:
        raise ValueError("Missing unique synthetic project")
    if any(value.get(key) is not False for key in ["linked", "requested", "fault_exists"]):
        raise ValueError("Refusing an existing link, request or fault fixture")
    return value["id"]


def unique_process(value):
    if not isinstance(value, list) or len(value) != 1 or type(value[0]) is not int or value[0] <= 0:
        raise ValueError("No unique owned application process; do not guess")
    return value[0]


def pids(runtime, suffix, port):
    code = """import os,json
found=[]
for name in os.listdir('/proc'):
 if name.isdigit():
  try: args=open('/proc/'+name+'/cmdline','rb').read().split(b'\\0')
  except OSError: continue
  if any(x==b'uvicorn' or x.endswith(b'/uvicorn') for x in args) and PORT in args:found.append(int(name))
print(json.dumps(found))
""".replace("PORT", repr(str(port).encode()))
    return json.loads(runtime.docker("exec", runtime.spec.run_id + "-" + suffix, "python", "-c", code))


def stop(runtime, suffix, port):
    runtime.verify()
    pid = unique_process(pids(runtime, suffix, port))
    runtime.manifest.setdefault("stopped_services", {})[suffix] = {"pid": pid, "port": port}
    runtime.save()
    runtime.docker("exec", runtime.spec.run_id + "-" + suffix, "python", "-c", "import os,signal;os.kill(" + str(pid) + ",signal.SIGTERM)")
    for _ in range(25):
        if not pids(runtime, suffix, port):
            return pid
        time.sleep(.2)
    raise RuntimeError("Application stop not confirmed; do not start another process")


def start(runtime, suffix, port):
    runtime.verify()
    stopped = runtime.manifest.get("stopped_services", {})
    if suffix not in stopped or pids(runtime, suffix, port):
        raise ValueError("Start requires a confirmed stopped owned process")
    runtime.docker("exec", "-d", runtime.spec.run_id + "-" + suffix, "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", str(port), "--no-access-log", "--log-level", "error")
    del stopped[suffix]
    runtime.save()


def health(runtime):
    code = """import urllib.request,json
opener=urllib.request.build_opener(urllib.request.ProxyHandler({}));result={}
for key,url in [('mdm','http://signing-backend:8000/api/v1/health'),('pm','http://signing-backend:8001/health')]:
 try:
  with opener.open(url,timeout=1) as r:result[key]=r.status
 except Exception:result[key]=None
print(json.dumps(result))
"""
    return json.loads(runtime.docker("exec", runtime.spec.run_id + "-tools", "python", "-c", code))


def healthy(runtime):
    for _ in range(15):
        result = health(runtime)
        if all(x == 200 for x in result.values()):
            return result
        time.sleep(.2)
    raise RuntimeError("Owned application health not restored")


def fault(runtime, project_code):
    runtime.verify()
    pg = runtime.spec.run_id + "-pg"
    inspected = json.loads(runtime.docker("inspect", pg))[0]
    if "/var/lib/postgresql/data" not in inspected["HostConfig"].get("Tmpfs", {}):
        raise ValueError("Faults require the new tmpfs database")
    # project_code passed the finite shape guard; no free SQL/identifier input.
    query = "SELECT json_build_object('id',p.project_id,'linked',EXISTS(SELECT 1 FROM prs.project_pm_link l WHERE l.project_id=p.project_id),'requested',EXISTS(SELECT 1 FROM prs.project_pm_create_request r WHERE r.project_id=p.project_id),'fault_exists',to_regclass('public.e2e_link_failure_once') IS NOT NULL) FROM prs.project p WHERE p.project_code='" + project_code + "'"
    raw = runtime.docker("exec", pg, "psql", "-U", "cmab_app", "-d", "cmab_signing_e2e", "-Atc", query).strip()
    project_id = check_fault_target(json.loads(raw) if raw else None)
    sql = """BEGIN;
CREATE SEQUENCE public.e2e_link_failure_once;
CREATE FUNCTION public.e2e_fail_link() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
 IF NEW.project_id = TARGET_ID THEN
  IF nextval('public.e2e_link_failure_once') = 1 THEN
   RAISE EXCEPTION 'synthetic one-shot local link commit failure';
  END IF;
 END IF;
 RETURN NEW;
END $$;
CREATE TRIGGER e2e_fail_link BEFORE INSERT ON prs.project_pm_link FOR EACH ROW EXECUTE FUNCTION public.e2e_fail_link();
COMMIT;
""".replace("TARGET_ID", str(project_id))
    runtime.docker("exec", "-i", pg, "psql", "-U", "cmab_app", "-d", "cmab_signing_e2e", "-v", "ON_ERROR_STOP=1", data=sql.encode())
    return {"fault": "first-local-link-insert", "project_id": project_id, "project_code": project_code, "storage": "owned tmpfs"}


def poll(runtime):
    """Called by the CLI host loop; browser driver supplies only finite JSON."""
    resume_at = runtime.manifest.get("resume_mdm_at")
    if resume_at and datetime.now(UTC) >= datetime.fromisoformat(resume_at):
        start(runtime, "backend", 8000)
        runtime.manifest.pop("resume_mdm_at")
        runtime.save()
        runtime.checkpoint("automatic_outage_recovery", health=healthy(runtime))
    path = runtime.spec.output("control/request.json")
    if not path.exists():
        return
    request = validate_request(json.loads(path.read_text(encoding="utf-8")))
    target = runtime.spec.output("control/" + request["id"] + ".json")
    if target.exists():
        return
    if runtime.manifest.get("control_pending"):
        raise ValueError("Previous control outcome uncertain; inspect before retry")
    runtime.manifest["control_pending"] = request
    runtime.save()
    try:
        if runtime.manifest["phase"] != "ready":
            raise ValueError("Controls require the verified owned ready fixture")
        action = request["action"]
        result = {}
        if action == "snapshot":
            from scripts.e2e_evidence import collect
            result = collect(runtime, stage=request.get("stage", "control"))
        elif action == "fault-next-link":
            result = fault(runtime, request["project_code"])
        elif action == "stop-mdm":
            result = {"old_pid": stop(runtime, "backend", 8000), "automatic_resume_seconds": 45}
            runtime.manifest["resume_mdm_at"] = (datetime.now(UTC) + timedelta(seconds=45)).isoformat()
        elif action == "start-mdm":
            if runtime.manifest.get("resume_mdm_at"):
                start(runtime, "backend", 8000)
                runtime.manifest.pop("resume_mdm_at")
            result = {"health": healthy(runtime)}
        elif action == "restart-apps":
            result = {"old_pm_pid": stop(runtime, "pm", 8001), "old_mdm_pid": stop(runtime, "backend", 8000)}
            start(runtime, "pm", 8001)
            start(runtime, "backend", 8000)
            result.update(health=healthy(runtime), database_restarted=False, idp_restarted=False)
        response = {"id": request["id"], "action": action, "status": "passed", "time_utc": datetime.now(UTC).isoformat(), "result": result}
        target.write_text(json.dumps(response, indent=2), encoding="utf-8")
        runtime.manifest["control_pending"] = None
        runtime.save()
        runtime.checkpoint("control_finished", action=action, request_id=request["id"])
    except (ValueError, RuntimeError):
        target.write_text(json.dumps({"id": request["id"], "status": "blocked", "reason": "Owned control failed; inspect state before retry"}), encoding="utf-8")
        raise
