#!/usr/bin/env python3
"""
PostgreSQL cluster inventory exporter
-----------------------------------
Exports a full-ish architecture snapshot of a PostgreSQL instance/cluster:
- roles / role memberships
- databases
- extensions / schemas / tables / views / matviews / columns
- constraints / indexes / sequences / functions
- basic ACL / ownership metadata
- markdown summary + structured JSON + CSV tables

Designed for offline/internal environments.
Supports psycopg (v3) first, then psycopg2.

Usage examples:
  python export_postgres_inventory.py \
      --host 127.0.0.1 --port 5432 --user postgres --password xxx \
      --outdir ./pg_inventory_2026-04-14

  set PGPASSWORD=xxx
  python export_postgres_inventory.py --host 127.0.0.1 --port 5432 --user postgres --outdir .\\pg_inventory
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import os
import re
import sys
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

# ---- DB driver fallback -----------------------------------------------------
DB_DRIVER = None
try:
    import psycopg  # type: ignore
    DB_DRIVER = "psycopg"
except Exception:
    try:
        import psycopg2  # type: ignore
        from psycopg2.extras import RealDictCursor  # type: ignore
        DB_DRIVER = "psycopg2"
    except Exception:
        DB_DRIVER = None


if DB_DRIVER is None:
    print(
        "ERROR: neither psycopg (v3) nor psycopg2 is installed. Please install one of them.",
        file=sys.stderr,
    )
    sys.exit(1)


# ---- SQL helpers ------------------------------------------------------------
ROLE_SQL = """
SELECT
    r.oid,
    r.rolname,
    r.rolsuper,
    r.rolinherit,
    r.rolcreaterole,
    r.rolcreatedb,
    r.rolcanlogin,
    r.rolreplication,
    r.rolbypassrls,
    r.rolconnlimit,
    r.rolvaliduntil,
    ARRAY(
        SELECT b.rolname
        FROM pg_auth_members m
        JOIN pg_roles b ON b.oid = m.roleid
        WHERE m.member = r.oid
        ORDER BY b.rolname
    ) AS member_of
FROM pg_roles r
ORDER BY r.rolname;
"""

ROLE_MEMBERSHIP_SQL = """
SELECT
    member.rolname AS member_role,
    parent.rolname AS granted_role,
    m.admin_option
FROM pg_auth_members m
JOIN pg_roles member ON member.oid = m.member
JOIN pg_roles parent ON parent.oid = m.roleid
ORDER BY member.rolname, parent.rolname;
"""

DATABASE_SQL = """
SELECT
    d.datname,
    pg_get_userbyid(d.datdba) AS owner,
    d.encoding,
    d.datcollate,
    d.datctype,
    d.datistemplate,
    d.datallowconn,
    d.datconnlimit,
    COALESCE(pg_size_pretty(pg_database_size(d.datname)), 'N/A') AS size_pretty,
    pg_database_size(d.datname) AS size_bytes
FROM pg_database d
ORDER BY d.datname;
"""

DB_SETTINGS_SQL = """
SELECT
    datname,
    setconfig
FROM pg_db_role_setting s
LEFT JOIN pg_database d ON d.oid = s.setdatabase
WHERE s.setdatabase <> 0
ORDER BY datname;
"""

EXTENSIONS_SQL = """
SELECT
    e.extname,
    e.extversion,
    n.nspname AS schema_name
FROM pg_extension e
JOIN pg_namespace n ON n.oid = e.extnamespace
ORDER BY e.extname;
"""

SCHEMAS_SQL = """
SELECT
    n.nspname AS schema_name,
    pg_get_userbyid(n.nspowner) AS owner,
    COALESCE(obj_description(n.oid, 'pg_namespace'), '') AS comment
FROM pg_namespace n
WHERE n.nspname NOT LIKE 'pg_toast%'
ORDER BY n.nspname;
"""

RELATIONS_SQL = """
SELECT
    n.nspname AS schema_name,
    c.relname AS object_name,
    CASE c.relkind
        WHEN 'r' THEN 'table'
        WHEN 'p' THEN 'partitioned_table'
        WHEN 'v' THEN 'view'
        WHEN 'm' THEN 'materialized_view'
        WHEN 'f' THEN 'foreign_table'
        WHEN 'S' THEN 'sequence'
        ELSE c.relkind::text
    END AS object_type,
    pg_get_userbyid(c.relowner) AS owner,
    COALESCE(pg_total_relation_size(c.oid), 0) AS total_bytes,
    CASE WHEN c.relkind IN ('r','p','m','f') THEN pg_size_pretty(pg_total_relation_size(c.oid)) ELSE NULL END AS total_size_pretty,
    CASE WHEN c.relkind IN ('r','p','m','f') THEN c.reltuples::bigint ELSE NULL END AS estimated_rows,
    COALESCE(obj_description(c.oid, 'pg_class'), '') AS comment
FROM pg_class c
JOIN pg_namespace n ON n.oid = c.relnamespace
WHERE n.nspname NOT IN ('pg_catalog', 'information_schema')
  AND n.nspname NOT LIKE 'pg_toast%'
  AND c.relkind IN ('r','p','v','m','f','S')
ORDER BY n.nspname, c.relkind, c.relname;
"""

COLUMNS_SQL = """
SELECT
    c.table_schema AS schema_name,
    c.table_name,
    c.ordinal_position,
    c.column_name,
    c.data_type,
    c.udt_name,
    c.character_maximum_length,
    c.numeric_precision,
    c.numeric_scale,
    c.is_nullable,
    c.column_default,
    COALESCE(pg_catalog.col_description(cls.oid, c.ordinal_position), '') AS comment
FROM information_schema.columns c
JOIN pg_class cls ON cls.relname = c.table_name
JOIN pg_namespace nsp ON nsp.oid = cls.relnamespace AND nsp.nspname = c.table_schema
WHERE c.table_schema NOT IN ('pg_catalog', 'information_schema')
ORDER BY c.table_schema, c.table_name, c.ordinal_position;
"""

CONSTRAINTS_SQL = """
SELECT
    tc.table_schema AS schema_name,
    tc.table_name,
    tc.constraint_name,
    tc.constraint_type,
    string_agg(kcu.column_name, ', ' ORDER BY kcu.ordinal_position) AS columns,
    ccu.table_schema AS foreign_table_schema,
    ccu.table_name AS foreign_table_name,
    string_agg(ccu.column_name, ', ' ORDER BY kcu.ordinal_position) AS foreign_columns
FROM information_schema.table_constraints tc
LEFT JOIN information_schema.key_column_usage kcu
    ON tc.constraint_name = kcu.constraint_name
   AND tc.table_schema = kcu.table_schema
   AND tc.table_name = kcu.table_name
LEFT JOIN information_schema.constraint_column_usage ccu
    ON tc.constraint_name = ccu.constraint_name
   AND tc.table_schema = ccu.table_schema
WHERE tc.table_schema NOT IN ('pg_catalog', 'information_schema')
GROUP BY tc.table_schema, tc.table_name, tc.constraint_name, tc.constraint_type,
         ccu.table_schema, ccu.table_name
ORDER BY tc.table_schema, tc.table_name, tc.constraint_type, tc.constraint_name;
"""

CHECK_CONSTRAINTS_SQL = """
SELECT
    n.nspname AS schema_name,
    rel.relname AS table_name,
    con.conname AS constraint_name,
    pg_get_constraintdef(con.oid, true) AS definition
FROM pg_constraint con
JOIN pg_class rel ON rel.oid = con.conrelid
JOIN pg_namespace n ON n.oid = rel.relnamespace
WHERE con.contype = 'c'
  AND n.nspname NOT IN ('pg_catalog', 'information_schema')
ORDER BY n.nspname, rel.relname, con.conname;
"""

INDEXES_SQL = """
SELECT
    schemaname AS schema_name,
    tablename AS table_name,
    indexname,
    indexdef
FROM pg_indexes
WHERE schemaname NOT IN ('pg_catalog', 'information_schema')
ORDER BY schemaname, tablename, indexname;
"""

SEQUENCES_SQL = """
SELECT
    sequence_schema AS schema_name,
    sequence_name,
    data_type,
    start_value,
    minimum_value,
    maximum_value,
    increment,
    cycle_option
FROM information_schema.sequences
WHERE sequence_schema NOT IN ('pg_catalog', 'information_schema')
ORDER BY sequence_schema, sequence_name;
"""

FUNCTIONS_SQL = """
SELECT
    n.nspname AS schema_name,
    p.proname AS function_name,
    pg_get_function_identity_arguments(p.oid) AS arguments,
    pg_get_function_result(p.oid) AS return_type,
    l.lanname AS language,
    pg_get_userbyid(p.proowner) AS owner,
    CASE WHEN p.prokind = 'a' THEN 'aggregate'
         WHEN p.prokind = 'w' THEN 'window'
         WHEN p.prokind = 'p' THEN 'procedure'
         ELSE 'function' END AS routine_type,
    COALESCE(obj_description(p.oid, 'pg_proc'), '') AS comment
FROM pg_proc p
JOIN pg_namespace n ON n.oid = p.pronamespace
JOIN pg_language l ON l.oid = p.prolang
WHERE n.nspname NOT IN ('pg_catalog', 'information_schema')
ORDER BY n.nspname, p.proname, arguments;
"""

TABLE_PRIVS_SQL = """
SELECT
    table_schema AS schema_name,
    table_name,
    grantee,
    privilege_type,
    is_grantable
FROM information_schema.table_privileges
WHERE table_schema NOT IN ('pg_catalog', 'information_schema')
ORDER BY table_schema, table_name, grantee, privilege_type;
"""

SCHEMA_PRIVS_SQL = """
SELECT
    n.nspname AS schema_name,
    r.rolname AS owner,
    COALESCE(n.nspacl::text, '') AS acl_text
FROM pg_namespace n
JOIN pg_roles r ON r.oid = n.nspowner
WHERE n.nspname NOT IN ('pg_catalog', 'information_schema')
  AND n.nspname NOT LIKE 'pg_toast%'
ORDER BY n.nspname;
"""

VIEWS_SQL = """
SELECT
    schemaname AS schema_name,
    viewname AS view_name,
    definition
FROM pg_views
WHERE schemaname NOT IN ('pg_catalog', 'information_schema')
ORDER BY schemaname, viewname;
"""

MATVIEWS_SQL = """
SELECT
    schemaname AS schema_name,
    matviewname AS materialized_view_name,
    definition
FROM pg_matviews
WHERE schemaname NOT IN ('pg_catalog', 'information_schema')
ORDER BY schemaname, matviewname;
"""


# ---- DB connector -----------------------------------------------------------
class DBClient:
    def __init__(self, dsn: Dict[str, Any]):
        self.dsn = dsn

    def connect(self, dbname: str):
        params = dict(self.dsn)
        params["dbname"] = dbname
        if DB_DRIVER == "psycopg":
            return psycopg.connect(**params)
        return psycopg2.connect(cursor_factory=RealDictCursor, **params)

    def fetch_all(self, dbname: str, sql: str) -> List[Dict[str, Any]]:
        with self.connect(dbname) as conn:
            with conn.cursor() as cur:
                cur.execute(sql)
                rows = cur.fetchall()
                if DB_DRIVER == "psycopg":
                    cols = [d.name for d in cur.description]
                    return [dict(zip(cols, row)) for row in rows]
                return [dict(row) for row in rows]


# ---- Serialization helpers --------------------------------------------------
def sanitize_filename(name: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", name)


def ensure_jsonable(obj: Any) -> Any:
    if isinstance(obj, (dt.date, dt.datetime)):
        return obj.isoformat()
    if isinstance(obj, bytes):
        return obj.decode("utf-8", errors="replace")
    if isinstance(obj, (list, tuple)):
        return [ensure_jsonable(x) for x in obj]
    if isinstance(obj, dict):
        return {str(k): ensure_jsonable(v) for k, v in obj.items()}
    return obj


def write_csv(path: Path, rows: List[Dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        with path.open("w", newline="", encoding="utf-8-sig") as f:
            f.write("")
        return
    headers: List[str] = []
    for row in rows:
        for key in row.keys():
            if key not in headers:
                headers.append(key)
    with path.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=headers)
        writer.writeheader()
        for row in rows:
            writer.writerow({k: ensure_jsonable(row.get(k)) for k in headers})


# ---- Collection logic -------------------------------------------------------
def collect_cluster_inventory(client: DBClient, maintenance_db: str) -> Dict[str, Any]:
    roles = client.fetch_all(maintenance_db, ROLE_SQL)
    role_memberships = client.fetch_all(maintenance_db, ROLE_MEMBERSHIP_SQL)
    databases = client.fetch_all(maintenance_db, DATABASE_SQL)
    db_settings = client.fetch_all(maintenance_db, DB_SETTINGS_SQL)
    return {
        "roles": roles,
        "role_memberships": role_memberships,
        "databases": databases,
        "db_settings": db_settings,
    }


def collect_one_database(client: DBClient, dbname: str) -> Dict[str, Any]:
    return {
        "extensions": client.fetch_all(dbname, EXTENSIONS_SQL),
        "schemas": client.fetch_all(dbname, SCHEMAS_SQL),
        "relations": client.fetch_all(dbname, RELATIONS_SQL),
        "columns": client.fetch_all(dbname, COLUMNS_SQL),
        "constraints": client.fetch_all(dbname, CONSTRAINTS_SQL),
        "check_constraints": client.fetch_all(dbname, CHECK_CONSTRAINTS_SQL),
        "indexes": client.fetch_all(dbname, INDEXES_SQL),
        "sequences": client.fetch_all(dbname, SEQUENCES_SQL),
        "functions": client.fetch_all(dbname, FUNCTIONS_SQL),
        "table_privileges": client.fetch_all(dbname, TABLE_PRIVS_SQL),
        "schema_privileges": client.fetch_all(dbname, SCHEMA_PRIVS_SQL),
        "views": client.fetch_all(dbname, VIEWS_SQL),
        "materialized_views": client.fetch_all(dbname, MATVIEWS_SQL),
    }


def make_summary(cluster: Dict[str, Any], dbs: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
    summary: Dict[str, Any] = {
        "generated_at": dt.datetime.now().isoformat(timespec="seconds"),
        "database_count": len(cluster.get("databases", [])),
        "role_count": len(cluster.get("roles", [])),
        "login_role_count": sum(1 for r in cluster.get("roles", []) if r.get("rolcanlogin")),
        "superuser_count": sum(1 for r in cluster.get("roles", []) if r.get("rolsuper")),
        "databases": [],
    }
    for db_meta in cluster.get("databases", []):
        name = db_meta["datname"]
        if name not in dbs:
            continue
        inv = dbs[name]
        relations = inv.get("relations", [])
        summary["databases"].append(
            {
                "datname": name,
                "owner": db_meta.get("owner"),
                "size_pretty": db_meta.get("size_pretty"),
                "schema_count": len(inv.get("schemas", [])),
                "table_like_count": sum(1 for x in relations if x.get("object_type") in ("table", "partitioned_table", "foreign_table")),
                "view_count": sum(1 for x in relations if x.get("object_type") == "view"),
                "materialized_view_count": sum(1 for x in relations if x.get("object_type") == "materialized_view"),
                "sequence_count": sum(1 for x in relations if x.get("object_type") == "sequence"),
                "column_count": len(inv.get("columns", [])),
                "index_count": len(inv.get("indexes", [])),
                "function_count": len(inv.get("functions", [])),
                "constraint_count": len(inv.get("constraints", [])) + len(inv.get("check_constraints", [])),
                "extension_count": len(inv.get("extensions", [])),
            }
        )
    return summary


def generate_markdown(summary: Dict[str, Any], cluster: Dict[str, Any], dbs: Dict[str, Dict[str, Any]], conn_info: Dict[str, Any]) -> str:
    lines: List[str] = []
    lines.append("# PostgreSQL 架构盘点报告")
    lines.append("")
    lines.append("## 1. 导出元信息")
    lines.append("")
    lines.append(f"- 生成时间：{summary['generated_at']}")
    lines.append(f"- 主机：{conn_info.get('host')}")
    lines.append(f"- 端口：{conn_info.get('port')}")
    lines.append(f"- 维护库：{conn_info.get('maintenance_db')}")
    lines.append(f"- 驱动：{conn_info.get('driver')}")
    lines.append("")
    lines.append("## 2. 集群级总览")
    lines.append("")
    lines.append(f"- 数据库数量：{summary['database_count']}")
    lines.append(f"- 角色数量：{summary['role_count']}")
    lines.append(f"- 可登录账户数量：{summary['login_role_count']}")
    lines.append(f"- 超级用户数量：{summary['superuser_count']}")
    lines.append("")
    lines.append("### 2.1 数据库清单")
    lines.append("")
    lines.append("| 数据库 | Owner | 大小 | Schema数 | 表类对象数 | 视图数 | 物化视图数 | 序列数 | 列数 | 索引数 | 函数数 | 约束数 | 扩展数 |")
    lines.append("|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|")
    for db in summary["databases"]:
        lines.append(
            f"| {db['datname']} | {db.get('owner','')} | {db.get('size_pretty','')} | {db['schema_count']} | {db['table_like_count']} | {db['view_count']} | {db['materialized_view_count']} | {db['sequence_count']} | {db['column_count']} | {db['index_count']} | {db['function_count']} | {db['constraint_count']} | {db['extension_count']} |"
        )
    lines.append("")
    lines.append("### 2.2 角色与账户")
    lines.append("")
    lines.append("| Role | Login | Superuser | CreateDB | CreateRole | Replication | Member Of |")
    lines.append("|---|---|---|---|---|---|---|")
    for r in cluster.get("roles", []):
        member_of = ", ".join(r.get("member_of") or [])
        lines.append(
            f"| {r['rolname']} | {bool(r.get('rolcanlogin'))} | {bool(r.get('rolsuper'))} | {bool(r.get('rolcreatedb'))} | {bool(r.get('rolcreaterole'))} | {bool(r.get('rolreplication'))} | {member_of} |"
        )
    lines.append("")

    for db_meta in summary["databases"]:
        dbname = db_meta["datname"]
        inv = dbs[dbname]
        lines.append(f"## 3. 数据库：`{dbname}`")
        lines.append("")
        lines.append(f"- Owner：{db_meta.get('owner','')}")
        lines.append(f"- 大小：{db_meta.get('size_pretty','')}")
        lines.append(f"- Schema 数：{db_meta.get('schema_count',0)}")
        lines.append("")

        schemas = inv.get("schemas", [])
        if schemas:
            lines.append("### 3.1 Schema 清单")
            lines.append("")
            lines.append("| Schema | Owner | Comment |")
            lines.append("|---|---|---|")
            for x in schemas:
                comment = str(x.get("comment") or "").replace("\n", " ")
                lines.append(f"| {x['schema_name']} | {x.get('owner','')} | {comment} |")
            lines.append("")

        rels = inv.get("relations", [])
        if rels:
            lines.append("### 3.2 关系对象清单")
            lines.append("")
            lines.append("| Schema | 对象名 | 类型 | Owner | 大小 | 估算行数 | Comment |")
            lines.append("|---|---|---|---|---:|---:|---|")
            for x in rels:
                comment = str(x.get("comment") or "").replace("\n", " ")
                lines.append(
                    f"| {x.get('schema_name','')} | {x.get('object_name','')} | {x.get('object_type','')} | {x.get('owner','')} | {x.get('total_size_pretty','') or ''} | {x.get('estimated_rows','') or ''} | {comment} |"
                )
            lines.append("")

        lines.append("### 3.3 重点说明")
        lines.append("")
        lines.append("- 详细字段、索引、约束、权限、函数、视图定义已分别导出到 `csv/` 和 `inventory_full.json`。")
        lines.append("- 若要给大模型快速理解，优先提供本 Markdown 报告 + `inventory_full.json`。")
        lines.append("")

    lines.append("## 4. 建议的长期管理方式")
    lines.append("")
    lines.append("1. 每次数据库结构有明显变化后，重新运行一次导出脚本。")
    lines.append("2. 将输出目录按日期归档，例如 `pg_inventory_2026-04-14`。")
    lines.append("3. 若今后要做数据库治理，建议在此基础上再补一份“业务含义字典”，说明每个核心表是做什么的。")
    lines.append("4. 若要与我继续讨论，建议直接上传：本 Markdown 报告、`inventory_full.json`，以及你认为关键的几个 CSV。")
    lines.append("")
    return "\n".join(lines)


# ---- Main -------------------------------------------------------------------
def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Export PostgreSQL architecture inventory")
    parser.add_argument("--host", default=os.getenv("PGHOST", "127.0.0.1"))
    parser.add_argument("--port", type=int, default=int(os.getenv("PGPORT", "5432")))
    parser.add_argument("--user", default=os.getenv("PGUSER", "postgres"))
    parser.add_argument("--password", default=os.getenv("PGPASSWORD"))
    parser.add_argument("--maintenance-db", default=os.getenv("PGDATABASE", "postgres"))
    parser.add_argument("--outdir", required=True)
    parser.add_argument("--include-databases", nargs="*", default=None, help="Optional allowlist of databases")
    parser.add_argument("--exclude-databases", nargs="*", default=["template0"], help="Optional denylist of databases")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    outdir = Path(args.outdir).resolve()
    outdir.mkdir(parents=True, exist_ok=True)
    csv_dir = outdir / "csv"
    csv_dir.mkdir(exist_ok=True)

    dsn = {
        "host": args.host,
        "port": args.port,
        "user": args.user,
    }
    if args.password:
        dsn["password"] = args.password

    client = DBClient(dsn)

    cluster = collect_cluster_inventory(client, args.maintenance_db)
    raw_dbs = [x["datname"] for x in cluster["databases"] if x.get("datallowconn")]

    selected_dbs: List[str] = []
    for dbname in raw_dbs:
        if args.include_databases and dbname not in args.include_databases:
            continue
        if args.exclude_databases and dbname in args.exclude_databases:
            continue
        selected_dbs.append(dbname)

    databases: Dict[str, Dict[str, Any]] = {}
    errors: List[Dict[str, str]] = []
    for dbname in selected_dbs:
        try:
            databases[dbname] = collect_one_database(client, dbname)
        except Exception as exc:
            errors.append({"database": dbname, "error": str(exc)})

    summary = make_summary(cluster, databases)

    payload = {
        "meta": {
            "generated_at": summary["generated_at"],
            "host": args.host,
            "port": args.port,
            "maintenance_db": args.maintenance_db,
            "driver": DB_DRIVER,
            "selected_databases": selected_dbs,
            "errors": errors,
        },
        "cluster": cluster,
        "databases": databases,
        "summary": summary,
    }

    (outdir / "inventory_full.json").write_text(
        json.dumps(ensure_jsonable(payload), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    markdown = generate_markdown(
        summary,
        cluster,
        databases,
        {
            "host": args.host,
            "port": args.port,
            "maintenance_db": args.maintenance_db,
            "driver": DB_DRIVER,
        },
    )
    (outdir / "inventory_report.md").write_text(markdown, encoding="utf-8")

    write_csv(csv_dir / "cluster_roles.csv", cluster.get("roles", []))
    write_csv(csv_dir / "cluster_role_memberships.csv", cluster.get("role_memberships", []))
    write_csv(csv_dir / "cluster_databases.csv", cluster.get("databases", []))
    write_csv(csv_dir / "cluster_db_settings.csv", cluster.get("db_settings", []))
    write_csv(csv_dir / "summary_databases.csv", summary.get("databases", []))
    write_csv(csv_dir / "errors.csv", errors)

    for dbname, inv in databases.items():
        db_prefix = sanitize_filename(dbname)
        for key, rows in inv.items():
            write_csv(csv_dir / f"{db_prefix}__{key}.csv", rows)

    print(f"Inventory exported to: {outdir}")
    if errors:
        print("Some databases could not be scanned:")
        for err in errors:
            print(f"  - {err['database']}: {err['error']}")


if __name__ == "__main__":
    main()
