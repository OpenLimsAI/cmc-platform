#!/usr/bin/env python3
"""
Scan every Postgres-flavored Docker container on this host and emit an HTML
inventory: container (instance) -> non-default databases -> schemas -> tables
-> columns. Connects via `docker exec ... psql`, so it relies on the local
trust-auth that the official postgres image enables for Unix-socket
connections (i.e. no host-side password needed).

Usage:
    python tools/scan_docker_postgres.py
    python tools/scan_docker_postgres.py --out my_report.html
    python tools/scan_docker_postgres.py --include-system-schemas
    python tools/scan_docker_postgres.py --include-default-dbs
    python tools/scan_docker_postgres.py --only rd_pg,cmab-mdm-postgres
"""
from __future__ import annotations

import argparse
import datetime as dt
import html
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

PG_IMAGE_PATTERNS = re.compile(
    r"(postgres|postgis|timescale|pgvector|supabase|citus|crunchy)",
    re.IGNORECASE,
)
EXCLUDED_DEFAULT_DBS = {"postgres", "template0", "template1"}
EXCLUDED_SYSTEM_SCHEMAS = {"pg_catalog", "information_schema", "pg_toast"}


def run(cmd: list[str], input_: str | None = None, check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(
        cmd, input=input_, capture_output=True, text=True, check=check
    )


def container_has_psql(cid: str) -> bool:
    """Probe the container to make sure psql actually runs inside it."""
    res = subprocess.run(
        ["docker", "exec", "-i", cid, "psql", "--version"],
        capture_output=True, text=True,
    )
    return res.returncode == 0 and "psql" in (res.stdout + res.stderr).lower()


def list_postgres_containers(only: set[str] | None) -> list[dict]:
    """Discover running containers whose image looks like Postgres AND that
    actually have a working psql inside (drops false positives like
    pgsty/minio which happen to match the image regex)."""
    res = run(
        ["docker", "ps", "--format", "{{.ID}}\t{{.Names}}\t{{.Image}}\t{{.Ports}}"]
    )
    out = []
    for line in res.stdout.strip().splitlines():
        parts = line.split("\t")
        if len(parts) < 3:
            continue
        cid, name, image = parts[0], parts[1], parts[2]
        ports = parts[3] if len(parts) > 3 else ""
        if only:
            if name not in only and cid not in only:
                continue
        else:
            if not PG_IMAGE_PATTERNS.search(image):
                continue
            if not container_has_psql(cid):
                print(
                    f"  跳过 {name}（{image}）：容器内没有 psql，疑似非 Postgres",
                    file=sys.stderr,
                )
                continue
        env = inspect_env(cid)
        user = env.get("POSTGRES_USER") or "postgres"
        version = env.get("PG_VERSION") or env.get("PG_MAJOR") or ""
        out.append(
            {
                "id": cid,
                "name": name,
                "image": image,
                "ports": ports,
                "user": user,
                "version": version,
            }
        )
    return out


def inspect_env(cid: str) -> dict[str, str]:
    res = run(["docker", "inspect", "--format", "{{json .Config.Env}}", cid])
    try:
        env_list = json.loads(res.stdout.strip())
    except Exception:
        return {}
    out: dict[str, str] = {}
    for e in env_list or []:
        if "=" in e:
            k, v = e.split("=", 1)
            out[k] = v
    return out


def psql_query(cid: str, user: str, db: str, sql: str) -> list[list[str]]:
    """Run a query inside the container. Returns rows split by tab."""
    res = subprocess.run(
        [
            "docker", "exec", "-i", cid,
            "psql", "-U", user, "-d", db,
            "-At", "-F", "\t",
            "--no-psqlrc",
            "-v", "ON_ERROR_STOP=1",
        ],
        input=sql,
        capture_output=True,
        text=True,
    )
    if res.returncode != 0:
        raise RuntimeError(
            f"psql failed (container={cid}, db={db}): {res.stderr.strip() or res.stdout.strip()}"
        )
    rows: list[list[str]] = []
    for line in res.stdout.splitlines():
        if line == "":
            continue
        rows.append(line.split("\t"))
    return rows


def list_databases(cid: str, user: str, include_default: bool) -> list[str]:
    sql = (
        "SELECT datname FROM pg_database "
        "WHERE datistemplate = false AND datallowconn = true "
        "ORDER BY datname;"
    )
    rows = psql_query(cid, user, "postgres", sql)
    dbs = [r[0] for r in rows]
    if not include_default:
        dbs = [d for d in dbs if d not in EXCLUDED_DEFAULT_DBS]
    return dbs


def scan_database(
    cid: str, user: str, db: str, include_system_schemas: bool
) -> dict[str, dict[str, list[dict]]]:
    """Returns {schema: {table: [{name,type,nullable,default}, ...]}}."""
    if include_system_schemas:
        schema_clause = ""
        info_clause = ""
    else:
        excl = ",".join(f"'{s}'" for s in EXCLUDED_SYSTEM_SCHEMAS)
        schema_clause = f" AND n.nspname NOT IN ({excl})"
        info_clause = f" AND table_schema NOT IN ({excl})"

    sql_schemas = (
        "SELECT n.nspname FROM pg_namespace n "
        "WHERE n.nspname NOT LIKE 'pg_temp_%' "
        "AND n.nspname NOT LIKE 'pg_toast_temp_%'"
        f"{schema_clause} "
        "ORDER BY n.nspname;"
    )
    schemas = [r[0] for r in psql_query(cid, user, db, sql_schemas)]

    sql_tables = (
        "SELECT table_schema, table_name "
        "FROM information_schema.tables "
        "WHERE table_type = 'BASE TABLE'"
        f"{info_clause} "
        "ORDER BY table_schema, table_name;"
    )
    tables = psql_query(cid, user, db, sql_tables)

    sql_columns = (
        "SELECT table_schema, table_name, column_name, "
        "       data_type, is_nullable, COALESCE(column_default, '') "
        "FROM information_schema.columns "
        "WHERE 1=1"
        f"{info_clause} "
        "ORDER BY table_schema, table_name, ordinal_position;"
    )
    columns = psql_query(cid, user, db, sql_columns)

    result: dict[str, dict[str, list[dict]]] = {s: {} for s in schemas}
    for row in tables:
        ts, tn = row[0], row[1]
        result.setdefault(ts, {})[tn] = []
    for row in columns:
        ts, tn, cn, dtp, nl, df = row[0], row[1], row[2], row[3], row[4], row[5]
        result.setdefault(ts, {}).setdefault(tn, []).append(
            {"name": cn, "type": dtp, "nullable": nl, "default": df}
        )
    return result


def scan_all(
    containers: list[dict], include_default_dbs: bool, include_system_schemas: bool
) -> list[dict]:
    snapshot = []
    for c in containers:
        entry: dict[str, Any] = dict(c)
        entry["databases"] = []
        entry["error"] = None
        try:
            dbs = list_databases(c["id"], c["user"], include_default_dbs)
        except Exception as e:
            entry["error"] = f"list_databases: {e}"
            snapshot.append(entry)
            continue
        for db in dbs:
            db_entry: dict[str, Any] = {"name": db, "schemas": {}, "error": None}
            try:
                db_entry["schemas"] = scan_database(
                    c["id"], c["user"], db, include_system_schemas
                )
            except Exception as e:
                db_entry["error"] = str(e)
            entry["databases"].append(db_entry)
        snapshot.append(entry)
    return snapshot


# ----------------------------- HTML rendering -----------------------------

CSS = """
:root {
  --fg: #1f2328;
  --muted: #57606a;
  --accent: #0969da;
  --bg: #ffffff;
  --soft: #f6f8fa;
  --border: #d0d7de;
  --chip-bg: #ddf4ff;
  --chip-fg: #0550ae;
  --warn-bg: #fff8c5;
  --warn-fg: #7d4e00;
  --err-bg: #ffebe9;
  --err-fg: #82071e;
}
* { box-sizing: border-box; }
body {
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "PingFang SC",
               "Hiragino Sans GB", "Microsoft YaHei", Arial, sans-serif;
  color: var(--fg);
  background: var(--bg);
  margin: 0;
  padding: 24px 32px 80px;
  line-height: 1.55;
}
h1 { margin: 0 0 4px; font-size: 22px; }
.meta { color: var(--muted); font-size: 13px; margin-bottom: 18px; }
.toolbar { margin: 12px 0 24px; display: flex; gap: 8px; flex-wrap: wrap; }
.btn {
  background: var(--soft); border: 1px solid var(--border);
  color: var(--fg); padding: 6px 12px; border-radius: 6px;
  cursor: pointer; font-size: 13px;
}
.btn:hover { background: #eef1f4; }
.summary-bar {
  display: flex; gap: 16px; flex-wrap: wrap;
  padding: 10px 14px; background: var(--soft);
  border: 1px solid var(--border); border-radius: 8px;
  margin-bottom: 20px; font-size: 13px;
}
.summary-bar b { color: var(--accent); }

details {
  border: 1px solid var(--border);
  border-radius: 8px;
  margin: 8px 0;
  background: var(--bg);
}
details > summary {
  cursor: pointer;
  padding: 10px 14px;
  font-weight: 600;
  list-style: none;
  display: flex;
  align-items: center;
  gap: 10px;
}
details > summary::-webkit-details-marker { display: none; }
details > summary::before {
  content: "▸"; color: var(--muted); font-size: 12px;
  display: inline-block; width: 12px;
  transition: transform .12s ease;
}
details[open] > summary::before { transform: rotate(90deg); }
details.instance > summary { background: #eaf3ff; border-radius: 8px; }
details.database > summary { background: #f6f8fa; }
details.schema   > summary { background: #fbfbfc; }
details.table    > summary { background: var(--bg); }

details.instance { border-color: #b6d7ff; }

.body { padding: 6px 14px 14px 30px; }
.chip {
  display: inline-block; font-size: 11px;
  background: var(--chip-bg); color: var(--chip-fg);
  padding: 1px 8px; border-radius: 10px; font-weight: 500;
}
.chip.muted { background: #eaeef2; color: var(--muted); }
.error {
  background: var(--err-bg); color: var(--err-fg);
  padding: 8px 12px; border-radius: 6px; font-size: 12px;
  margin: 6px 0; white-space: pre-wrap; word-break: break-all;
}
.empty {
  color: var(--muted); font-style: italic; padding: 4px 0;
}
table.cols {
  width: 100%;
  border-collapse: collapse;
  margin: 4px 0 4px;
  font-size: 13px;
}
table.cols th, table.cols td {
  text-align: left;
  padding: 5px 10px;
  border-bottom: 1px solid var(--border);
  vertical-align: top;
}
table.cols th {
  background: var(--soft);
  font-weight: 600;
  position: sticky; top: 0;
}
table.cols td.col-name { font-family: ui-monospace, SFMono-Regular, Menlo, monospace; }
table.cols td.col-type { color: var(--accent); font-family: ui-monospace, SFMono-Regular, Menlo, monospace; }
table.cols td.col-null { color: var(--muted); }
table.cols td.col-default { color: var(--muted); font-family: ui-monospace, SFMono-Regular, Menlo, monospace; white-space: pre-wrap; word-break: break-all; }
.search {
  padding: 6px 10px; border: 1px solid var(--border); border-radius: 6px;
  font-size: 13px; width: 260px;
}
.kbd {
  font-family: ui-monospace, monospace; font-size: 12px;
  background: var(--soft); border: 1px solid var(--border);
  border-radius: 4px; padding: 1px 5px; color: var(--muted);
}
"""

JS = r"""
function setAll(open) {
  document.querySelectorAll('details').forEach(d => d.open = open);
}
function filterTree(q) {
  q = (q || '').trim().toLowerCase();
  const all = Array.from(document.querySelectorAll('details, tr.col-row'));
  if (!q) {
    all.forEach(el => el.style.display = '');
    return;
  }
  // Mark elements whose own text matches
  function selfText(el) {
    if (el.tagName === 'TR') return el.textContent.toLowerCase();
    const s = el.querySelector(':scope > summary');
    return s ? s.textContent.toLowerCase() : '';
  }
  // hide everything first
  all.forEach(el => el.style.display = 'none');
  // show matched and their ancestors+descendants
  document.querySelectorAll('details, tr.col-row').forEach(el => {
    if (selfText(el).includes(q)) {
      // show self + parents
      let cur = el;
      while (cur && cur !== document.body) {
        if (cur.tagName === 'DETAILS' || cur.tagName === 'TR') {
          cur.style.display = '';
          if (cur.tagName === 'DETAILS') cur.open = true;
        }
        cur = cur.parentElement;
      }
      // show descendants of details too
      if (el.tagName === 'DETAILS') {
        el.querySelectorAll('details, tr.col-row').forEach(d => {
          d.style.display = '';
        });
      }
    }
  });
}
document.addEventListener('keydown', function (e) {
  if (e.key === '/' && document.activeElement.tagName !== 'INPUT') {
    e.preventDefault();
    const s = document.getElementById('q'); if (s) s.focus();
  }
});
"""


def esc(s: Any) -> str:
    return html.escape("" if s is None else str(s))


def render_html(snapshot: list[dict], generated_at: str, scan_opts: dict) -> str:
    total_instances = len(snapshot)
    total_dbs = sum(len(c["databases"]) for c in snapshot)
    total_schemas = 0
    total_tables = 0
    total_columns = 0
    for c in snapshot:
        for db in c["databases"]:
            total_schemas += len(db["schemas"])
            for tables in db["schemas"].values():
                total_tables += len(tables)
                for cols in tables.values():
                    total_columns += len(cols)

    parts: list[str] = []
    parts.append("<!doctype html><html lang='zh-CN'><head><meta charset='utf-8'>")
    parts.append("<title>Docker Postgres Inventory</title>")
    parts.append(f"<style>{CSS}</style></head><body>")
    parts.append("<h1>Docker Postgres 实例盘点</h1>")
    parts.append(
        f"<div class='meta'>生成时间：{esc(generated_at)} ｜ "
        f"包含默认库：{'是' if scan_opts.get('include_default_dbs') else '否'} ｜ "
        f"包含系统 schema：{'是' if scan_opts.get('include_system_schemas') else '否'}</div>"
    )
    parts.append("<div class='summary-bar'>")
    parts.append(f"<div>实例 <b>{total_instances}</b></div>")
    parts.append(f"<div>数据库 <b>{total_dbs}</b></div>")
    parts.append(f"<div>Schema <b>{total_schemas}</b></div>")
    parts.append(f"<div>表 <b>{total_tables}</b></div>")
    parts.append(f"<div>字段 <b>{total_columns}</b></div>")
    parts.append("</div>")
    parts.append("<div class='toolbar'>")
    parts.append("<button class='btn' onclick=\"setAll(true)\">全部展开</button>")
    parts.append("<button class='btn' onclick=\"setAll(false)\">全部折叠</button>")
    parts.append(
        "<input id='q' class='search' placeholder='搜索（按 / 聚焦）：实例 / 库 / schema / 表 / 字段名'"
        " oninput='filterTree(this.value)'>"
    )
    parts.append("</div>")

    if not snapshot:
        parts.append(
            "<div class='empty'>没有检测到任何 Postgres 容器。"
            "可以用 <span class='kbd'>--only &lt;container&gt;</span> 强制扫描指定容器。</div>"
        )

    for c in snapshot:
        port_str = f"端口 {esc(c['ports'])}" if c["ports"] else "（无端口映射）"
        ver = f" · {esc(c['version'])}" if c["version"] else ""
        parts.append("<details class='instance' open>")
        parts.append(
            f"<summary>🐘 {esc(c['name'])} "
            f"<span class='chip'>{esc(c['image'])}{ver}</span> "
            f"<span class='chip muted'>{port_str}</span> "
            f"<span class='chip muted'>{len(c['databases'])} 个用户库</span>"
            f"</summary>"
        )
        parts.append("<div class='body'>")
        if c["error"]:
            parts.append(f"<div class='error'>{esc(c['error'])}</div>")
        if not c["databases"] and not c["error"]:
            parts.append("<div class='empty'>没有非默认数据库。</div>")
        for db in c["databases"]:
            n_schemas = len(db["schemas"])
            n_tables = sum(len(t) for t in db["schemas"].values())
            parts.append("<details class='database'>")
            parts.append(
                f"<summary>🗄 {esc(db['name'])} "
                f"<span class='chip muted'>{n_schemas} schema · {n_tables} 表</span>"
                f"</summary>"
            )
            parts.append("<div class='body'>")
            if db["error"]:
                parts.append(f"<div class='error'>{esc(db['error'])}</div>")
            if not db["schemas"] and not db["error"]:
                parts.append("<div class='empty'>没有非系统 schema。</div>")
            for sname in sorted(db["schemas"].keys()):
                tables = db["schemas"][sname]
                parts.append("<details class='schema'>")
                parts.append(
                    f"<summary>📁 {esc(sname)} "
                    f"<span class='chip muted'>{len(tables)} 表</span></summary>"
                )
                parts.append("<div class='body'>")
                if not tables:
                    parts.append("<div class='empty'>该 schema 没有表。</div>")
                for tname in sorted(tables.keys()):
                    cols = tables[tname]
                    parts.append("<details class='table'>")
                    parts.append(
                        f"<summary>📋 {esc(tname)} "
                        f"<span class='chip muted'>{len(cols)} 字段</span></summary>"
                    )
                    parts.append("<div class='body'>")
                    if not cols:
                        parts.append("<div class='empty'>该表没有字段（或不可见）。</div>")
                    else:
                        parts.append(
                            "<table class='cols'><thead><tr>"
                            "<th>#</th><th>字段名</th><th>类型</th>"
                            "<th>可空</th><th>默认值</th></tr></thead><tbody>"
                        )
                        for i, col in enumerate(cols, start=1):
                            parts.append(
                                f"<tr class='col-row'>"
                                f"<td>{i}</td>"
                                f"<td class='col-name'>{esc(col['name'])}</td>"
                                f"<td class='col-type'>{esc(col['type'])}</td>"
                                f"<td class='col-null'>{esc(col['nullable'])}</td>"
                                f"<td class='col-default'>{esc(col['default'])}</td>"
                                f"</tr>"
                            )
                        parts.append("</tbody></table>")
                    parts.append("</div></details>")
                parts.append("</div></details>")
            parts.append("</div></details>")
        parts.append("</div></details>")

    parts.append(f"<script>{JS}</script>")
    parts.append("</body></html>")
    return "".join(parts)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--out", type=Path,
        help="HTML 输出路径。默认 inventories/docker_pg_scan_<timestamp>.html"
    )
    ap.add_argument(
        "--include-default-dbs", action="store_true",
        help="同时包含 postgres / template0 / template1 等默认库"
    )
    ap.add_argument(
        "--include-system-schemas", action="store_true",
        help="同时包含 pg_catalog / information_schema / pg_toast 等系统 schema"
    )
    ap.add_argument(
        "--only", type=str, default="",
        help="只扫描指定的容器（用逗号分隔的名称或 ID），跳过镜像名识别"
    )
    args = ap.parse_args()

    only = {x.strip() for x in args.only.split(",") if x.strip()} or None

    try:
        run(["docker", "version", "--format", "{{.Server.Version}}"])
    except Exception as e:
        print(f"无法调用 docker：{e}", file=sys.stderr)
        sys.exit(2)

    containers = list_postgres_containers(only)
    print(f"发现 {len(containers)} 个 Postgres 容器：", file=sys.stderr)
    for c in containers:
        print(f"  - {c['name']}  ({c['image']})  user={c['user']}", file=sys.stderr)

    snapshot = scan_all(
        containers,
        include_default_dbs=args.include_default_dbs,
        include_system_schemas=args.include_system_schemas,
    )

    now = dt.datetime.now()
    generated_at = now.strftime("%Y-%m-%d %H:%M:%S")
    out_path = args.out
    if out_path is None:
        inv_dir = Path(__file__).resolve().parent.parent / "inventories"
        inv_dir.mkdir(parents=True, exist_ok=True)
        out_path = inv_dir / f"docker_pg_scan_{now.strftime('%Y%m%d_%H%M%S')}.html"
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    html_text = render_html(
        snapshot, generated_at,
        scan_opts={
            "include_default_dbs": args.include_default_dbs,
            "include_system_schemas": args.include_system_schemas,
        },
    )
    out_path.write_text(html_text, encoding="utf-8")
    print(f"\n已生成报告：{out_path}", file=sys.stderr)


if __name__ == "__main__":
    main()
