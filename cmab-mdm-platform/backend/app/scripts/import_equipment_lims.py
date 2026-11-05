"""
LIMS(SampleManager Oracle) → EQP 设备主数据 迁移工具

把 LABLIMS.INSTRUMENT 读出，清洗后写入本平台 eqp.equipment。可重入、--dry-run、CSV 报告。

设计要点（见对话整理结论）：
  - 自包含：只用 oracledb(读 Oracle) + psycopg2(写 PG)，不 import 本应用。
    用 rd-lims-etl 的 venv 跑（同时有这两个库 + Oracle instantclient）：
      /Users/qingcheng/code/rd-lims-etl/.venv/bin/python -m ...   （需在 backend 目录或加 PYTHONPATH）
    更简单：直接按文件路径跑：
      /Users/qingcheng/code/rd-lims-etl/.venv/bin/python \
        backend/app/scripts/import_equipment_lims.py --dry-run --report /tmp/lims_eqp_report.csv
  - Oracle 连接读 rd-lims-etl/.env（ORACLE_* + ORACLE_CLIENT_DIR，thick 模式连 11g）。
  - 目标 PG 默认 Mac docker（127.0.0.1:15432/cmab_mdm），可用 --pg-* 覆盖（将来指向 Linux）。
  - 字段映射：IDENTITY→code、NAME→name(中文)、CT_GGNO→model、MANUFACTURER、SERIAL_NO、
    STATUS(R→主数据 retired、设备状态 scrapped；其余 active/enabled)、DESCRIPTION→主要性能参数描述；
    category 按 NAME 关键词推断 5 类；HISTORICAL_SN/FIXED_ASSET_NO/CT_LEVEL/原始STATUS→extra。
    运营字段(校验/维护/位置/计量证书/IP 等)不迁移（归 LabOps）。
  - 占位符(N/A/未登记/0…)清洗为空；equipment_name 必填，空则跳过。
  - 可重入：按 equipment_code 与库内已有(含软删)比对，已存在则跳过。
  - 审计：写入前设 app.user_id/app.username='admin (lims-import)'，审计触发器自动记账。
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import sys
from pathlib import Path
from typing import TypedDict

import oracledb
import psycopg2
from psycopg2.extras import Json

RD_ENV = "/Users/qingcheng/code/rd-lims-etl/.env"

# ---------- category 5 类按名称推断（与 import_equipment_excel 同规则） ----------
VALID_CATEGORIES = {
    "分析仪器", "工艺/制备设备", "通用实验室设备",
    "公用工程/环境与支持系统", "IT/自动化与数据系统",
}
DEFAULT_CATEGORY = "通用实验室设备"
CATEGORY_ALIASES: list[tuple[str, str]] = [
    ("电脑", "IT/自动化与数据系统"), ("计算机", "IT/自动化与数据系统"),
    ("服务器", "IT/自动化与数据系统"), ("工作站", "IT/自动化与数据系统"),
    ("网络", "IT/自动化与数据系统"), ("数据库", "IT/自动化与数据系统"),
    ("采集", "IT/自动化与数据系统"), ("软件", "IT/自动化与数据系统"),
    ("LIMS", "IT/自动化与数据系统"), ("ELN", "IT/自动化与数据系统"),
    ("纯化水", "公用工程/环境与支持系统"), ("WFI", "公用工程/环境与支持系统"),
    ("HVAC", "公用工程/环境与支持系统"), ("空调", "公用工程/环境与支持系统"),
    ("压缩空气", "公用工程/环境与支持系统"), ("洁净", "公用工程/环境与支持系统"),
    ("灭菌", "公用工程/环境与支持系统"), ("冰箱", "公用工程/环境与支持系统"),
    ("超低温", "公用工程/环境与支持系统"), ("液氮", "公用工程/环境与支持系统"),
    ("公用", "公用工程/环境与支持系统"), ("环境", "公用工程/环境与支持系统"),
    ("反应器", "工艺/制备设备"), ("发酵", "工艺/制备设备"), ("层析", "工艺/制备设备"),
    ("色谱柱", "工艺/制备设备"), ("TFF", "工艺/制备设备"), ("超滤", "工艺/制备设备"),
    ("配液", "工艺/制备设备"), ("灌装", "工艺/制备设备"), ("制剂", "工艺/制备设备"),
    ("中试", "工艺/制备设备"), ("工艺", "工艺/制备设备"), ("生产", "工艺/制备设备"),
    ("色谱", "分析仪器"), ("光谱", "分析仪器"), ("质谱", "分析仪器"),
    ("HPLC", "分析仪器"), ("UPLC", "分析仪器"), ("GC", "分析仪器"),
    ("酶标", "分析仪器"), ("Biacore", "分析仪器"), ("溶出", "分析仪器"),
    ("电泳", "分析仪器"),
    ("离心", "通用实验室设备"), ("天平", "通用实验室设备"), ("台秤", "通用实验室设备"),
    ("pH", "通用实验室设备"), ("移液", "通用实验室设备"), ("培养箱", "通用实验室设备"),
    ("水浴", "通用实验室设备"), ("摇床", "通用实验室设备"), ("搅拌", "通用实验室设备"),
    ("振荡", "通用实验室设备"), ("显微镜", "通用实验室设备"),
    # 泛词垫底：避免「分析天平」被「分析」抢成分析仪器
    ("检测", "分析仪器"), ("分析", "分析仪器"), ("仪器", "分析仪器"),
]


def infer_category(name: str | None) -> tuple[str, bool]:
    if not name:
        return DEFAULT_CATEGORY, True
    up = name.upper()
    for kw, cat in CATEGORY_ALIASES:
        if kw.upper() in up:
            return cat, False
    return DEFAULT_CATEGORY, True


# ---------- 清洗 ----------
_PLACEHOLDERS = {"N/A", "NA", "无", "-", "/", "未登记", "未知", "待登记", "0", ""}


def clean(v, maxlen: int | None = None) -> str | None:
    if v is None:
        return None
    s = str(v).replace("\r", "").strip()
    if s.upper() in {p.upper() for p in _PLACEHOLDERS}:
        return None
    if maxlen and len(s) > maxlen:
        s = s[:maxlen]
    return s


# ---------- env ----------
def load_env(path: str) -> dict:
    cfg = {}
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                cfg[k.strip()] = v.strip()
    return cfg


def oracle_connect(cfg: dict):
    lib = cfg.get("ORACLE_CLIENT_DIR", "").strip()
    if lib and os.path.isdir(lib):
        oracledb.init_oracle_client(lib_dir=lib)
    dsn = oracledb.makedsn(
        cfg["ORACLE_HOST"], int(cfg["ORACLE_PORT"]), service_name=cfg["ORACLE_SERVICE"]
    )
    return oracledb.connect(
        user=cfg["ORACLE_USER"], password=cfg["ORACLE_PASS"], dsn=dsn
    )


# ---------- 抽取 + 映射 ----------
FETCH_SQL = """
    SELECT IDENTITY, NAME, MANUFACTURER, CT_GGNO, SERIAL_NO, STATUS,
           DESCRIPTION, HISTORICAL_SN, FIXED_ASSET_NO, CT_LEVEL
    FROM LABLIMS.INSTRUMENT
"""


def map_row(r: dict) -> dict:
    name = clean(r["NAME"], 255)
    # IDENTITY 是 LIMS 业务编号 → 设备编号(equipment_no)；设备ID 由本平台另行系统生成
    eq_no = clean(r["IDENTITY"], 64)
    fixed_asset_no = clean(r["FIXED_ASSET_NO"], 64)
    cat, defaulted = infer_category(name)
    raw_status = (r["STATUS"] or "").strip().upper()
    status = "retired" if raw_status == "R" else "active"
    equipment_status = "scrapped" if raw_status == "R" else "enabled"

    extra = {"source": "lims", "lims_status": raw_status or None}
    for src, key in [("HISTORICAL_SN", "historical_sn"), ("CT_LEVEL", "ct_level")]:
        val = clean(r[src])
        if val:
            extra[key] = val

    skip = None
    if not eq_no:
        skip = "empty_no"
    elif not name:
        skip = "empty_name"

    return {
        "equipment_no": eq_no,
        "fixed_asset_no": fixed_asset_no,
        "equipment_name": name,
        "category": cat,
        "category_defaulted": defaulted,
        "manufacturer": clean(r["MANUFACTURER"], 100),
        "model": clean(r["CT_GGNO"], 200),
        "serial_no": clean(r["SERIAL_NO"], 100),
        "status": status,
        "equipment_status": equipment_status,
        "description": clean(r["DESCRIPTION"]),
        "extra": {k: v for k, v in extra.items() if v is not None},
        "skip_reason": skip,
    }


# ---------- 入库 ----------
# 设备ID(equipment_code) 留空 → 触发器系统生成；按设备编号 equipment_no 去重
INSERT_SQL = """
    INSERT INTO eqp.equipment
      (equipment_no, fixed_asset_no, equipment_name, category, manufacturer,
       model, serial_no, status, equipment_status, has_workstation, description, extra,
       created_by, updated_by)
    VALUES
      (%(equipment_no)s, %(fixed_asset_no)s, %(equipment_name)s, %(category)s,
       %(manufacturer)s, %(model)s, %(serial_no)s, %(status)s, %(equipment_status)s, FALSE,
       %(description)s, %(extra)s,
       %(uid)s, %(uid)s)
"""


class ImportStats(TypedDict):
    total: int
    to_insert: int
    inserted: int
    category_defaulted: int
    skipped: dict[str, int]
    cat_dist: dict[str, int]
    status_dist: dict[str, int]


def run(rows: list[dict], pg: dict, dry_run: bool) -> ImportStats:
    stats: ImportStats = {"total": len(rows), "to_insert": 0, "inserted": 0,
             "category_defaulted": 0, "skipped": {}, "cat_dist": {}, "status_dist": {}}

    conn = psycopg2.connect(
        host=pg["host"], port=pg["port"], dbname=pg["db"],
        user=pg["user"], password=pg["password"],
    )
    conn.autocommit = False
    cur = conn.cursor()

    cur.execute("SELECT user_id FROM auth.\"user\" WHERE username='admin'")
    row = cur.fetchone()
    if not row:
        raise SystemExit("目标库缺少 admin 用户，先 seed")
    uid = row[0]

    # 审计上下文（session 级，false=非 local）
    cur.execute("SELECT set_config('app.user_id', %s, false)", (str(uid),))
    cur.execute("SELECT set_config('app.username', 'admin (lims-import)', false)")
    cur.execute("SELECT set_config('app.change_reason', 'LIMS 设备主数据迁移', false)")

    # 已有设备编号（含软删），按业务编号去重；设备ID 系统生成不参与
    cur.execute("SELECT equipment_no FROM eqp.equipment WHERE equipment_no IS NOT NULL")
    existing = {x[0] for x in cur.fetchall()}

    seen: set[str] = set()
    for pr in rows:
        if pr["category_defaulted"]:
            stats["category_defaulted"] += 1
        if pr["skip_reason"]:
            stats["skipped"][pr["skip_reason"]] = stats["skipped"].get(pr["skip_reason"], 0) + 1
            continue
        no = pr["equipment_no"]
        if no in existing:
            pr["skip_reason"] = "db_dup_no"
            stats["skipped"]["db_dup_no"] = stats["skipped"].get("db_dup_no", 0) + 1
            continue
        if no in seen:
            pr["skip_reason"] = "inner_dup_no"
            stats["skipped"]["inner_dup_no"] = stats["skipped"].get("inner_dup_no", 0) + 1
            continue
        seen.add(no)
        stats["cat_dist"][pr["category"]] = stats["cat_dist"].get(pr["category"], 0) + 1
        stats["status_dist"][pr["status"]] = stats["status_dist"].get(pr["status"], 0) + 1
        if not dry_run:
            cur.execute(INSERT_SQL, {
                "equipment_no": no, "fixed_asset_no": pr["fixed_asset_no"],
                "equipment_name": pr["equipment_name"],
                "category": pr["category"], "manufacturer": pr["manufacturer"],
                "model": pr["model"], "serial_no": pr["serial_no"],
                "status": pr["status"], "equipment_status": pr["equipment_status"],
                "description": pr["description"],
                "extra": Json(pr["extra"]) if pr["extra"] else None, "uid": uid,
            })
        stats["to_insert"] += 1

    if dry_run:
        conn.rollback()
    else:
        conn.commit()
        stats["inserted"] = stats["to_insert"]
    cur.close()
    conn.close()
    return stats


def write_report(rows: list[dict], path: Path) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["decision", "skip_reason", "equipment_no", "fixed_asset_no",
                    "equipment_name", "category", "category_defaulted", "master_status",
                    "equipment_status",
                    "manufacturer", "model", "serial_no", "extra"])
        for pr in rows:
            w.writerow([
                "SKIP" if pr["skip_reason"] else "IMPORT", pr["skip_reason"] or "",
                pr["equipment_no"] or "", pr["fixed_asset_no"] or "",
                pr["equipment_name"] or "", pr["category"],
                "Y" if pr["category_defaulted"] else "", pr["status"],
                pr["equipment_status"],
                pr["manufacturer"] or "", pr["model"] or "", pr["serial_no"] or "",
                json.dumps(pr["extra"], ensure_ascii=False),
            ])


def print_stats(stats: ImportStats, dry_run: bool) -> None:
    print("=" * 60)
    print(f"LIMS INSTRUMENT 行: {stats['total']}")
    print(f"待插入:            {stats['to_insert']}")
    print(f"已实际插入:        {stats['inserted']}{'  (dry-run 未写)' if dry_run else ''}")
    print(f"category 推断为默认(通用实验室设备且无关键词命中): {stats['category_defaulted']}")
    print("\n--- 跳过原因 ---")
    for k, v in sorted(stats["skipped"].items(), key=lambda x: -x[1]):
        print(f"  {k}: {v}")
    print("\n--- category 分布(待插入) ---")
    for k, v in sorted(stats["cat_dist"].items(), key=lambda x: -x[1]):
        print(f"  {k}: {v}")
    print("\n--- status 分布(待插入) ---")
    for k, v in sorted(stats["status_dist"].items(), key=lambda x: -x[1]):
        print(f"  {k}: {v}")
    print("=" * 60)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--report", default="/tmp/lims_eqp_report.csv")
    ap.add_argument("--oracle-env", default=RD_ENV)
    ap.add_argument("--pg-host", default=os.getenv("PG_HOST", "127.0.0.1"))
    ap.add_argument("--pg-port", default=os.getenv("PG_PORT", "15432"))
    ap.add_argument("--pg-db", default=os.getenv("PG_DB", "cmab_mdm"))
    ap.add_argument("--pg-user", default=os.getenv("PG_USER", "cmab_app"))
    ap.add_argument("--pg-pass", default=os.getenv("PG_PASS", "__REDACTED_POSTGRES_PASSWORD__"))
    args = ap.parse_args()

    cfg = load_env(args.oracle_env)
    print(f"读取 Oracle: {cfg['ORACLE_USER']}@{cfg['ORACLE_HOST']}/{cfg['ORACLE_SERVICE']}")
    oconn = oracle_connect(cfg)
    ocur = oconn.cursor()
    ocur.execute(FETCH_SQL)
    cols = [d[0] for d in ocur.description]
    raw = [dict(zip(cols, r, strict=True)) for r in ocur.fetchall()]
    oconn.close()
    print(f"LIMS 读到 {len(raw)} 行")

    rows = [map_row(r) for r in raw]

    pg = {"host": args.pg_host, "port": args.pg_port, "db": args.pg_db,
          "user": args.pg_user, "password": args.pg_pass}
    print(f"目标 PG: {pg['user']}@{pg['host']}:{pg['port']}/{pg['db']}"
          f"{'  [DRY-RUN]' if args.dry_run else ''}")
    stats = run(rows, pg, args.dry_run)
    write_report(rows, Path(args.report))
    print(f"报告: {args.report}")
    print_stats(stats, args.dry_run)
    return 0


if __name__ == "__main__":
    sys.exit(main())
