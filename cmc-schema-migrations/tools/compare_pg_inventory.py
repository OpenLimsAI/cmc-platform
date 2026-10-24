#!/usr/bin/env python3
"""
PostgreSQL inventory comparator
-------------------------------
Compare two `inventory_full.json` files produced by `export_postgres_inventory.py`
and emit a structural diff between them.

Typical use case: detect schema drift between two PostgreSQL instances
(e.g. Mac Docker dev DB vs Linux VM deployment DB).

Usage:
  python compare_pg_inventory.py LEFT.json RIGHT.json \
      --database cmc_data_platform \
      --left-label mac --right-label linux \
      --out diff_report.md
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

SYSTEM_SCHEMAS = {"pg_catalog", "information_schema", "pg_toast"}


# ---- generic helpers --------------------------------------------------------

def _normalize_sql(text: Optional[str]) -> str:
    """Collapse whitespace so trivial formatting differences don't count as drift."""
    if not text:
        return ""
    return re.sub(r"\s+", " ", text).strip().lower()


def _load(path: Path) -> Dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def _index_by(items: Iterable[Dict[str, Any]], *keys: str) -> Dict[Tuple, Dict[str, Any]]:
    out: Dict[Tuple, Dict[str, Any]] = {}
    for it in items:
        out[tuple(it.get(k) for k in keys)] = it
    return out


def _filter_user_schemas(items: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return [it for it in items if it.get("schema_name") not in SYSTEM_SCHEMAS]


# ---- field-level comparators ------------------------------------------------

COLUMN_COMPARE_FIELDS = (
    "data_type",
    "udt_name",
    "character_maximum_length",
    "numeric_precision",
    "numeric_scale",
    "is_nullable",
    "column_default",
)

CONSTRAINT_COMPARE_FIELDS = (
    "constraint_type",
    "columns",
    "foreign_table_schema",
    "foreign_table_name",
    "foreign_columns",
)

SEQUENCE_COMPARE_FIELDS = (
    "data_type",
    "start_value",
    "minimum_value",
    "maximum_value",
    "increment",
    "cycle_option",
)


def _diff_fields(left: Dict[str, Any], right: Dict[str, Any], fields: Tuple[str, ...]) -> List[str]:
    lines: List[str] = []
    for f in fields:
        lv, rv = left.get(f), right.get(f)
        if lv != rv:
            lines.append(f"`{f}`: `{lv}` → `{rv}`")
    return lines


# Constraint "columns" / "foreign_columns" come from the exporter's SQL which
# over-joins and produces the same column repeated in non-deterministic order.
# Compare them as multisets so that ordering/repetition noise doesn't show as drift.
_MULTISET_FIELDS = {"columns", "foreign_columns"}


def _canon_multiset(val: Any) -> Any:
    if not isinstance(val, str):
        return val
    parts = [p.strip() for p in val.split(",") if p.strip()]
    return tuple(sorted(parts))


def _diff_fields_multiset(left: Dict[str, Any], right: Dict[str, Any], fields: Tuple[str, ...]) -> List[str]:
    lines: List[str] = []
    for f in fields:
        lv, rv = left.get(f), right.get(f)
        if f in _MULTISET_FIELDS:
            if _canon_multiset(lv) != _canon_multiset(rv):
                lines.append(f"`{f}`: `{lv}` → `{rv}`")
        else:
            if lv != rv:
                lines.append(f"`{f}`: `{lv}` → `{rv}`")
    return lines


# ---- per-section diffs ------------------------------------------------------

def diff_extensions(left: List[Dict], right: List[Dict]) -> Dict[str, Any]:
    lk = _index_by(left, "extname")
    rk = _index_by(right, "extname")
    only_left = sorted(set(lk) - set(rk))
    only_right = sorted(set(rk) - set(lk))
    version_diff = []
    for k in sorted(set(lk) & set(rk)):
        if lk[k].get("extversion") != rk[k].get("extversion"):
            version_diff.append((k[0], lk[k].get("extversion"), rk[k].get("extversion")))
    return {
        "only_left": [k[0] for k in only_left],
        "only_right": [k[0] for k in only_right],
        "version_diff": version_diff,
    }


def diff_schemas(left: List[Dict], right: List[Dict]) -> Dict[str, Any]:
    left = _filter_user_schemas(left)
    right = _filter_user_schemas(right)
    lk = _index_by(left, "schema_name")
    rk = _index_by(right, "schema_name")
    return {
        "only_left": [k[0] for k in sorted(set(lk) - set(rk))],
        "only_right": [k[0] for k in sorted(set(rk) - set(lk))],
        "owner_diff": [
            (k[0], lk[k].get("owner"), rk[k].get("owner"))
            for k in sorted(set(lk) & set(rk))
            if lk[k].get("owner") != rk[k].get("owner")
        ],
    }


def diff_relations(left: List[Dict], right: List[Dict]) -> Dict[str, Any]:
    left = _filter_user_schemas(left)
    right = _filter_user_schemas(right)
    lk = _index_by(left, "schema_name", "object_name")
    rk = _index_by(right, "schema_name", "object_name")
    type_diff = []
    for k in sorted(set(lk) & set(rk)):
        if lk[k].get("object_type") != rk[k].get("object_type"):
            type_diff.append((f"{k[0]}.{k[1]}", lk[k].get("object_type"), rk[k].get("object_type")))
    return {
        "only_left": [f"{k[0]}.{k[1]} ({lk[k].get('object_type')})" for k in sorted(set(lk) - set(rk))],
        "only_right": [f"{k[0]}.{k[1]} ({rk[k].get('object_type')})" for k in sorted(set(rk) - set(lk))],
        "type_diff": type_diff,
        "common_tables": sorted({k for k in set(lk) & set(rk) if lk[k].get("object_type") == "table"}),
    }


def diff_columns(left: List[Dict], right: List[Dict], common_tables: List[Tuple[str, str]]) -> Dict[str, Any]:
    left = _filter_user_schemas(left)
    right = _filter_user_schemas(right)
    common_set = set(common_tables)

    def _group_by_table(rows: List[Dict]) -> Dict[Tuple[str, str], Dict[str, Dict]]:
        by_table: Dict[Tuple[str, str], Dict[str, Dict]] = {}
        for r in rows:
            tkey = (r["schema_name"], r["table_name"])
            if tkey not in common_set:
                continue
            by_table.setdefault(tkey, {})[r["column_name"]] = r
        return by_table

    lcols = _group_by_table(left)
    rcols = _group_by_table(right)

    table_diffs: List[Dict[str, Any]] = []
    for tkey in sorted(common_set):
        lc = lcols.get(tkey, {})
        rc = rcols.get(tkey, {})
        only_left = sorted(set(lc) - set(rc))
        only_right = sorted(set(rc) - set(lc))
        changed: List[Tuple[str, List[str]]] = []
        for col in sorted(set(lc) & set(rc)):
            d = _diff_fields(lc[col], rc[col], COLUMN_COMPARE_FIELDS)
            if d:
                changed.append((col, d))
        if only_left or only_right or changed:
            table_diffs.append({
                "table": f"{tkey[0]}.{tkey[1]}",
                "only_left": [f"{c} ({lc[c].get('data_type')})" for c in only_left],
                "only_right": [f"{c} ({rc[c].get('data_type')})" for c in only_right],
                "changed": changed,
            })
    return {"table_diffs": table_diffs}


def diff_constraints(left: List[Dict], right: List[Dict]) -> Dict[str, Any]:
    left = _filter_user_schemas(left)
    right = _filter_user_schemas(right)

    def _is_synthetic(name: Optional[str]) -> bool:
        # The exporter emits synthetic CHECK names like "38477_39121_1_not_null"
        # whose number comes from the OID. Skip those — they're just NOT NULL noise.
        return bool(name and re.match(r"^\d+_\d+_\d+_not_null$", name))

    left = [r for r in left if not _is_synthetic(r.get("constraint_name"))]
    right = [r for r in right if not _is_synthetic(r.get("constraint_name"))]

    lk = _index_by(left, "schema_name", "table_name", "constraint_name")
    rk = _index_by(right, "schema_name", "table_name", "constraint_name")

    def _fmt(k):
        return f"{k[0]}.{k[1]}::{k[2]}"

    changed: List[Tuple[str, List[str]]] = []
    for k in sorted(set(lk) & set(rk)):
        d = _diff_fields_multiset(lk[k], rk[k], CONSTRAINT_COMPARE_FIELDS)
        if d:
            changed.append((_fmt(k), d))
    return {
        "only_left": [_fmt(k) for k in sorted(set(lk) - set(rk))],
        "only_right": [_fmt(k) for k in sorted(set(rk) - set(lk))],
        "changed": changed,
    }


def diff_indexes(left: List[Dict], right: List[Dict]) -> Dict[str, Any]:
    left = _filter_user_schemas(left)
    right = _filter_user_schemas(right)
    lk = _index_by(left, "schema_name", "table_name", "indexname")
    rk = _index_by(right, "schema_name", "table_name", "indexname")

    def _fmt(k):
        return f"{k[0]}.{k[1]}::{k[2]}"

    changed = []
    for k in sorted(set(lk) & set(rk)):
        if _normalize_sql(lk[k].get("indexdef")) != _normalize_sql(rk[k].get("indexdef")):
            changed.append((_fmt(k), lk[k].get("indexdef"), rk[k].get("indexdef")))
    return {
        "only_left": [_fmt(k) for k in sorted(set(lk) - set(rk))],
        "only_right": [_fmt(k) for k in sorted(set(rk) - set(lk))],
        "changed": changed,
    }


def diff_sequences(left: List[Dict], right: List[Dict]) -> Dict[str, Any]:
    left = _filter_user_schemas(left)
    right = _filter_user_schemas(right)
    lk = _index_by(left, "schema_name", "sequence_name")
    rk = _index_by(right, "schema_name", "sequence_name")
    changed = []
    for k in sorted(set(lk) & set(rk)):
        d = _diff_fields(lk[k], rk[k], SEQUENCE_COMPARE_FIELDS)
        if d:
            changed.append((f"{k[0]}.{k[1]}", d))
    return {
        "only_left": [f"{k[0]}.{k[1]}" for k in sorted(set(lk) - set(rk))],
        "only_right": [f"{k[0]}.{k[1]}" for k in sorted(set(rk) - set(lk))],
        "changed": changed,
    }


def diff_views(left: List[Dict], right: List[Dict]) -> Dict[str, Any]:
    left = _filter_user_schemas(left)
    right = _filter_user_schemas(right)
    lk = _index_by(left, "schema_name", "view_name")
    rk = _index_by(right, "schema_name", "view_name")
    changed = []
    for k in sorted(set(lk) & set(rk)):
        if _normalize_sql(lk[k].get("definition")) != _normalize_sql(rk[k].get("definition")):
            changed.append((f"{k[0]}.{k[1]}", lk[k].get("definition"), rk[k].get("definition")))
    return {
        "only_left": [f"{k[0]}.{k[1]}" for k in sorted(set(lk) - set(rk))],
        "only_right": [f"{k[0]}.{k[1]}" for k in sorted(set(rk) - set(lk))],
        "changed": changed,
    }


def diff_functions(left: List[Dict], right: List[Dict]) -> Dict[str, Any]:
    left = _filter_user_schemas(left)
    right = _filter_user_schemas(right)
    # function rows include arg signatures; key on schema+name+args to handle overloads.
    def _key(r):
        return (r.get("schema_name"), r.get("function_name") or r.get("proname") or r.get("name"),
                r.get("arguments") or r.get("argument_data_types") or "")

    def _index(rows):
        return {_key(r): r for r in rows}

    lk = _index(left)
    rk = _index(right)

    def _fmt(k):
        return f"{k[0]}.{k[1]}({k[2]})"

    body_key_candidates = ("definition", "prosrc", "source", "function_definition")

    def _body(row):
        for c in body_key_candidates:
            if c in row and row[c]:
                return _normalize_sql(row[c])
        return ""

    changed = []
    for k in sorted(set(lk) & set(rk), key=lambda x: tuple(str(p) for p in x)):
        if _body(lk[k]) != _body(rk[k]):
            changed.append(_fmt(k))
    return {
        "only_left": [_fmt(k) for k in sorted(set(lk) - set(rk), key=lambda x: tuple(str(p) for p in x))],
        "only_right": [_fmt(k) for k in sorted(set(rk) - set(lk), key=lambda x: tuple(str(p) for p in x))],
        "changed_body": changed,
    }


# ---- report rendering -------------------------------------------------------

def _bullet_list(items: List[str], empty_text: str = "*(无)*") -> str:
    if not items:
        return empty_text
    return "\n".join(f"- {it}" for it in items)


def render_markdown(diff: Dict[str, Any], db_name: str, left_label: str, right_label: str) -> str:
    out: List[str] = []
    out.append(f"# PostgreSQL 结构差异报告：`{db_name}`\n")
    out.append(f"- 左侧（{left_label}）：{diff['_meta']['left_path']}")
    out.append(f"- 右侧（{right_label}）：{diff['_meta']['right_path']}")
    out.append("")
    out.append("> 含义：")
    out.append(f"> - **只在 {left_label} 有** = 这条对象只存在于左侧，右侧没有")
    out.append(f"> - **只在 {right_label} 有** = 这条对象只存在于右侧，左侧没有")
    out.append("> - **不同** = 两边都有但属性有差异\n")

    # short summary table
    summary = diff["_summary"]
    out.append("## 0. 差异概览\n")
    out.append("| 维度 | 只在左 | 只在右 | 内容不同 |")
    out.append("|---|---:|---:|---:|")
    for label, key in [
        ("扩展", "extensions"),
        ("schema", "schemas"),
        ("表/视图/物化视图", "relations"),
        ("列（按表）", "columns"),
        ("约束", "constraints"),
        ("索引", "indexes"),
        ("序列", "sequences"),
        ("视图定义", "views"),
        ("函数", "functions"),
    ]:
        s = summary.get(key, {})
        out.append(f"| {label} | {s.get('only_left', 0)} | {s.get('only_right', 0)} | {s.get('changed', 0)} |")
    total = summary.get("total_diff_count", 0)
    out.append(f"\n**总差异条目数：{total}**\n")
    if total == 0:
        out.append("两边结构完全一致 ✅\n")
        return "\n".join(out)

    # extensions
    ext = diff["extensions"]
    out.append("## 1. 扩展 (extensions)\n")
    out.append(f"### 只在 {left_label} 有\n{_bullet_list(ext['only_left'])}\n")
    out.append(f"### 只在 {right_label} 有\n{_bullet_list(ext['only_right'])}\n")
    if ext["version_diff"]:
        out.append("### 版本不同")
        for name, lv, rv in ext["version_diff"]:
            out.append(f"- `{name}`: {left_label}=`{lv}`, {right_label}=`{rv}`")
        out.append("")

    # schemas
    sch = diff["schemas"]
    out.append("## 2. Schema\n")
    out.append(f"### 只在 {left_label} 有\n{_bullet_list(sch['only_left'])}\n")
    out.append(f"### 只在 {right_label} 有\n{_bullet_list(sch['only_right'])}\n")
    if sch["owner_diff"]:
        out.append("### Owner 不同")
        for name, lo, ro in sch["owner_diff"]:
            out.append(f"- `{name}`: {left_label}=`{lo}`, {right_label}=`{ro}`")
        out.append("")

    # relations
    rel = diff["relations"]
    out.append("## 3. 表 / 视图 / 物化视图 (relations)\n")
    out.append(f"### 只在 {left_label} 有\n{_bullet_list(rel['only_left'])}\n")
    out.append(f"### 只在 {right_label} 有\n{_bullet_list(rel['only_right'])}\n")
    if rel["type_diff"]:
        out.append("### 类型变了（比如左侧是表，右侧变成视图）")
        for name, lt, rt in rel["type_diff"]:
            out.append(f"- `{name}`: {left_label}=`{lt}`, {right_label}=`{rt}`")
        out.append("")

    # columns
    cols = diff["columns"]
    out.append("## 4. 列差异（仅两边都存在的表）\n")
    if not cols["table_diffs"]:
        out.append("*(所有共有表的列完全一致)*\n")
    for td in cols["table_diffs"]:
        out.append(f"### `{td['table']}`")
        if td["only_left"]:
            out.append(f"- 只在 {left_label} 有的列：{', '.join(td['only_left'])}")
        if td["only_right"]:
            out.append(f"- 只在 {right_label} 有的列：{', '.join(td['only_right'])}")
        for col, diffs in td["changed"]:
            out.append(f"- 列 `{col}` 属性不同：")
            for d in diffs:
                out.append(f"  - {d}")
        out.append("")

    # constraints
    cons = diff["constraints"]
    out.append("## 5. 约束\n")
    out.append(f"### 只在 {left_label} 有\n{_bullet_list(cons['only_left'])}\n")
    out.append(f"### 只在 {right_label} 有\n{_bullet_list(cons['only_right'])}\n")
    if cons["changed"]:
        out.append("### 内容不同")
        for name, diffs in cons["changed"]:
            out.append(f"- `{name}`")
            for d in diffs:
                out.append(f"  - {d}")
        out.append("")

    # indexes
    idx = diff["indexes"]
    out.append("## 6. 索引\n")
    out.append(f"### 只在 {left_label} 有\n{_bullet_list(idx['only_left'])}\n")
    out.append(f"### 只在 {right_label} 有\n{_bullet_list(idx['only_right'])}\n")
    if idx["changed"]:
        out.append("### 定义不同")
        for name, ldef, rdef in idx["changed"]:
            out.append(f"- `{name}`")
            out.append(f"  - {left_label}: `{ldef}`")
            out.append(f"  - {right_label}: `{rdef}`")
        out.append("")

    # sequences
    seq = diff["sequences"]
    out.append("## 7. 序列\n")
    out.append(f"### 只在 {left_label} 有\n{_bullet_list(seq['only_left'])}\n")
    out.append(f"### 只在 {right_label} 有\n{_bullet_list(seq['only_right'])}\n")
    if seq["changed"]:
        out.append("### 属性不同")
        for name, diffs in seq["changed"]:
            out.append(f"- `{name}`")
            for d in diffs:
                out.append(f"  - {d}")
        out.append("")

    # views
    vw = diff["views"]
    out.append("## 8. 视图定义\n")
    out.append(f"### 只在 {left_label} 有\n{_bullet_list(vw['only_left'])}\n")
    out.append(f"### 只在 {right_label} 有\n{_bullet_list(vw['only_right'])}\n")
    if vw["changed"]:
        out.append("### SQL 定义不同（已忽略空白/大小写差异）")
        for name, _ldef, _rdef in vw["changed"]:
            out.append(f"- `{name}`")
        out.append("")

    # functions
    fn = diff["functions"]
    out.append("## 9. 函数\n")
    out.append(f"### 只在 {left_label} 有\n{_bullet_list(fn['only_left'])}\n")
    out.append(f"### 只在 {right_label} 有\n{_bullet_list(fn['only_right'])}\n")
    if fn["changed_body"]:
        out.append("### 函数体不同")
        for name in fn["changed_body"]:
            out.append(f"- `{name}`")
        out.append("")

    return "\n".join(out)


# ---- top-level orchestration ------------------------------------------------

def compare_database(ldb: Dict[str, Any], rdb: Dict[str, Any]) -> Dict[str, Any]:
    relations = diff_relations(ldb.get("relations", []), rdb.get("relations", []))
    columns = diff_columns(ldb.get("columns", []), rdb.get("columns", []),
                           relations["common_tables"])
    diff = {
        "extensions": diff_extensions(ldb.get("extensions", []), rdb.get("extensions", [])),
        "schemas": diff_schemas(ldb.get("schemas", []), rdb.get("schemas", [])),
        "relations": relations,
        "columns": columns,
        "constraints": diff_constraints(ldb.get("constraints", []), rdb.get("constraints", [])),
        "indexes": diff_indexes(ldb.get("indexes", []), rdb.get("indexes", [])),
        "sequences": diff_sequences(ldb.get("sequences", []), rdb.get("sequences", [])),
        "views": diff_views(ldb.get("views", []), rdb.get("views", [])),
        "functions": diff_functions(ldb.get("functions", []), rdb.get("functions", [])),
    }
    # summary
    summary: Dict[str, Dict[str, int]] = {}

    def _counts(section: Dict[str, Any], left_key="only_left", right_key="only_right",
                changed_keys=("changed", "version_diff", "owner_diff", "type_diff", "changed_body", "table_diffs")) -> Dict[str, int]:
        only_left = len(section.get(left_key, []))
        only_right = len(section.get(right_key, []))
        changed = 0
        for ck in changed_keys:
            if ck in section:
                changed += len(section[ck])
        return {"only_left": only_left, "only_right": only_right, "changed": changed}

    for key, section in diff.items():
        summary[key] = _counts(section)
    total = sum(s["only_left"] + s["only_right"] + s["changed"] for s in summary.values())
    summary["total_diff_count"] = total
    diff["_summary"] = summary
    return diff


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("left", help="path to LEFT inventory_full.json")
    p.add_argument("right", help="path to RIGHT inventory_full.json")
    p.add_argument("--database", "-d", default="cmc_data_platform",
                   help="database name to compare (default: cmc_data_platform). Use '*' for all common databases.")
    p.add_argument("--left-label", default="left", help="label used for the LEFT side in the report")
    p.add_argument("--right-label", default="right", help="label used for the RIGHT side in the report")
    p.add_argument("--out", default=None, help="output markdown file (default: stdout)")
    p.add_argument("--json-out", default=None, help="optional path to also dump the structured diff as JSON")
    args = p.parse_args()

    left_path = Path(args.left)
    right_path = Path(args.right)
    left = _load(left_path)
    right = _load(right_path)

    ldbs = left.get("databases", {})
    rdbs = right.get("databases", {})

    if args.database == "*":
        target_dbs = sorted(set(ldbs) & set(rdbs))
        only_left_dbs = sorted(set(ldbs) - set(rdbs))
        only_right_dbs = sorted(set(rdbs) - set(ldbs))
    else:
        if args.database not in ldbs:
            print(f"ERROR: database '{args.database}' not found in LEFT file. Available: {sorted(ldbs)}", file=sys.stderr)
            return 2
        if args.database not in rdbs:
            print(f"ERROR: database '{args.database}' not found in RIGHT file. Available: {sorted(rdbs)}", file=sys.stderr)
            return 2
        target_dbs = [args.database]
        only_left_dbs = []
        only_right_dbs = []

    reports: List[str] = []
    structured: Dict[str, Any] = {"databases": {}}

    if only_left_dbs or only_right_dbs:
        reports.append("# 集群级数据库差异\n")
        if only_left_dbs:
            reports.append(f"只在 {args.left_label} 有的数据库: {', '.join(only_left_dbs)}")
        if only_right_dbs:
            reports.append(f"只在 {args.right_label} 有的数据库: {', '.join(only_right_dbs)}")
        reports.append("")

    for db in target_dbs:
        diff = compare_database(ldbs[db], rdbs[db])
        diff["_meta"] = {"left_path": str(left_path), "right_path": str(right_path)}
        structured["databases"][db] = diff
        reports.append(render_markdown(diff, db, args.left_label, args.right_label))
        reports.append("\n---\n")

    md = "\n".join(reports).rstrip()
    if args.out:
        Path(args.out).write_text(md, encoding="utf-8")
        print(f"Wrote markdown report -> {args.out}")
    else:
        print(md)

    if args.json_out:
        Path(args.json_out).write_text(json.dumps(structured, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
        print(f"Wrote JSON diff     -> {args.json_out}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
