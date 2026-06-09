"""
从公司 Excel「物料资料2026-06-09」批量追加 mm.material（增量同步）

与 import_materials_excel.py 的区别：
  - 本脚本适配 06-09 导出的 *另一种列布局*（Sheet1，物料代码/名称/厂家/物料类型/…），
    旧脚本读的是「物料」Sheet 的 序号/分类/代码/… 布局，两者不通用。
  - 「物料类型」词表也不同（这版叫"化试",旧版叫"试剂"），见 ERP_TYPE_MAP。
  - 仅追加 DB 中尚不存在的 material_code（重复 code 跳过），因此天然只会插入新物料。

口径决议（用户 2026-06-10 确认，选项 B）：
  - 真物料 + 对照药/原研药 入库；自有成品/原液 排除（属 SRS/ARS/成品域，不是物料）
  - 化试        → category=试剂  material_type=reagent
  - 临床对照药   → category=对照品 material_type=standard
  - 原研药       → category=参比品 material_type=standard
  - 上述 3 类被改写 category 者，原 ERP 物料类型写进 notes 前缀 [ERP类型:xx] 留痕
  - 排除：原液/注射液/冻干粉针/预灌封注射剂/注射剂/预充针（自有成品）
  - 脏码 00000（二氧化碳占位）单独跳过

用法：
  docker cp "<host.xlsx>" cmab-mdm-backend:/tmp/mat0609.xlsx
  docker compose -f deploy/docker-compose.dev.yml exec backend \
    python -m app.scripts.import_materials_excel_0609 --xlsx /tmp/mat0609.xlsx --dry-run
  # 看报告无误后去掉 --dry-run 真跑
"""
from __future__ import annotations

import argparse
import asyncio
import csv
import sys
from dataclasses import dataclass
from pathlib import Path

import openpyxl
from loguru import logger
from sqlalchemy import select

from app.core.database import AsyncSessionLocal
from app.domains.auth.models import User
from app.domains.mm.models import Material
from app.scripts.import_materials_excel import _norm, _truncate, detect_column
from app.shared.audit_context import (
    audit_user_id,
    audit_username,
    set_audit_session_vars,
)

# ---------- 配置 ----------

# ERP「物料类型」→ (category, material_type)
# category 必须落在 mm.material ck_material_category 白名单内
ERP_TYPE_MAP: dict[str, tuple[str, str]] = {
    # 耗材类
    "一般耗材": ("一般耗材", "consumable"),
    "关键耗材": ("关键耗材", "consumable"),
    "内包材": ("内包材", "consumable"),
    "外包材": ("外包材", "consumable"),
    "劳保": ("劳保", "consumable"),
    "自制包材": ("自制包材", "consumable"),
    "运输包装材料": ("运输包装材料", "consumable"),
    "工艺用水/气": ("工艺用水/气", "consumable"),
    # 试剂类
    "关键试剂": ("关键试剂", "reagent"),
    "原辅料": ("原辅料", "reagent"),
    "化试": ("试剂", "reagent"),  # 本版词表差异：化试=化学试剂→试剂
    # 标准/对照类
    "标准品": ("标准品", "standard"),
    "对照品": ("对照品", "standard"),
    "参比品": ("参比品", "standard"),
    "细胞种子": ("细胞种子", "standard"),
    "临床对照药": ("对照品", "standard"),  # 决议：当对照品类物料
    "原研药": ("参比品", "standard"),  # 决议：当参比品类物料
}

# 自有成品/原液：明确不是物料，跳过
PRODUCT_TYPES = {"原液", "注射液", "冻干粉针", "预灌封注射剂", "注射剂", "预充针", "注射剂"}

# 脏占位代码
JUNK_CODES = {"00000"}

# 本 Excel 列索引（0-based）
COL_CODE, COL_NAME, COL_MFG, COL_TYPE = 0, 1, 2, 3
COL_BRAND, COL_SPEC, COL_CATALOG = 4, 5, 6
COL_NOTE, COL_UNIT = 17, 22


@dataclass
class ParsedRow:
    excel_row: int
    code: str | None
    name: str | None
    erp_type: str | None
    category: str | None = None
    material_type: str | None = None
    manufacturer: str | None = None
    spec_model: str | None = None
    catalog_no: str | None = None
    unit: str | None = None
    notes: str | None = None
    is_column: bool = False
    skip_reason: str | None = None


def parse_row(idx: int, row: tuple) -> ParsedRow:
    code = _norm(row[COL_CODE])
    name = _norm(row[COL_NAME])
    erp_type = _norm(row[COL_TYPE])

    pr = ParsedRow(
        excel_row=idx,
        code=code,
        name=name,
        erp_type=erp_type,
        manufacturer=_truncate(_norm(row[COL_MFG]), 100),
        spec_model=_truncate(_norm(row[COL_SPEC]), 200),
        catalog_no=_truncate(_norm(row[COL_CATALOG]), 100),
        unit=_truncate(_norm(row[COL_UNIT]), 20),
        notes=_norm(row[COL_NOTE]),
    )

    if not code:
        pr.skip_reason = "empty_code"
        return pr
    if code in JUNK_CODES:
        pr.skip_reason = "junk_code"
        return pr
    if not name:
        pr.skip_reason = "empty_name"
        return pr
    if not erp_type:
        pr.skip_reason = "empty_type"
        return pr
    if len(code) > 20:
        pr.skip_reason = f"code_too_long({len(code)})"
        return pr
    if erp_type in PRODUCT_TYPES:
        pr.skip_reason = "product_not_material"
        return pr
    if erp_type not in ERP_TYPE_MAP:
        pr.skip_reason = f"unknown_type:{erp_type}"
        return pr

    category, mtype = ERP_TYPE_MAP[erp_type]
    pr.category = category
    pr.material_type = mtype

    # 改写过 category 的，原 ERP 类型写进 notes 留痕
    if category != erp_type:
        tag = f"[ERP类型:{erp_type}]"
        pr.notes = f"{tag} {pr.notes}" if pr.notes else tag

    # 色谱柱覆写（与旧脚本同逻辑）
    if detect_column(name):
        pr.is_column = True
        pr.material_type = "column"

    if pr.unit is None:
        pr.unit = "ea"

    return pr


def read_excel(path: Path) -> list[ParsedRow]:
    wb = openpyxl.load_workbook(path, data_only=True)
    ws = wb["Sheet1"]
    out: list[ParsedRow] = []
    # row1=标题, row2=表头, 数据从 row3 起
    for idx, row in enumerate(ws.iter_rows(min_row=3, values_only=True), start=3):
        if not any(row):
            continue
        out.append(parse_row(idx, row))
    return out


async def import_rows(rows: list[ParsedRow], dry_run: bool) -> dict:
    stats = {
        "total": len(rows),
        "skipped_by_reason": {},
        "duplicated_code": 0,
        "to_insert": 0,
        "type_dist": {},
        "category_dist": {},
        "column_overwrite": 0,
        "inserted": 0,
    }

    by_code: dict[str, ParsedRow] = {}
    for pr in rows:
        if pr.skip_reason:
            stats["skipped_by_reason"][pr.skip_reason] = (
                stats["skipped_by_reason"].get(pr.skip_reason, 0) + 1
            )
            continue
        if pr.code in by_code:
            pr.skip_reason = "inner_dup_code"
            stats["skipped_by_reason"]["inner_dup_code"] = (
                stats["skipped_by_reason"].get("inner_dup_code", 0) + 1
            )
            continue
        by_code[pr.code] = pr

    async with AsyncSessionLocal() as db:
        admin_res = await db.execute(select(User).where(User.username == "admin"))
        admin = admin_res.scalar_one_or_none()
        if admin is None:
            raise RuntimeError("缺少 admin 用户，先跑 seed_data")

        token_id = audit_user_id.set(admin.user_id)
        token_name = audit_username.set("admin (excel-import-0609)")
        try:
            await set_audit_session_vars(db)
            res = await db.execute(select(Material.material_code))
            existing = {r[0] for r in res.all()}

            to_insert: list[ParsedRow] = []
            for code, pr in by_code.items():
                if code in existing:
                    stats["duplicated_code"] += 1
                    pr.skip_reason = "db_dup_code"
                    continue
                to_insert.append(pr)
                stats["type_dist"][pr.material_type] = (
                    stats["type_dist"].get(pr.material_type, 0) + 1
                )
                stats["category_dist"][pr.category] = (
                    stats["category_dist"].get(pr.category, 0) + 1
                )
                if pr.is_column:
                    stats["column_overwrite"] += 1

            stats["to_insert"] = len(to_insert)

            if dry_run:
                logger.info(f"[DRY-RUN] 将插入 {len(to_insert)} 行，未提交")
            else:
                for pr in to_insert:
                    db.add(
                        Material(
                            material_code=pr.code,
                            material_name=pr.name,
                            material_type=pr.material_type,
                            category=pr.category,
                            manufacturer=pr.manufacturer,
                            spec_model=pr.spec_model,
                            catalog_no=pr.catalog_no,
                            unit=pr.unit or "ea",
                            notes=pr.notes,
                            source_type="vendor",
                            source_name=pr.manufacturer,
                            status="active",
                            created_by=admin.user_id,
                            updated_by=admin.user_id,
                        )
                    )
                await db.commit()
                stats["inserted"] = len(to_insert)
                logger.success(f"已插入 {len(to_insert)} 条物料")
        finally:
            audit_user_id.reset(token_id)
            audit_username.reset(token_name)

    return stats


def write_report(rows: list[ParsedRow], report_path: Path) -> None:
    with report_path.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow([
            "excel_row", "decision", "skip_reason", "code", "name",
            "erp_type", "category", "material_type", "is_column",
            "unit", "manufacturer", "catalog_no", "spec_model", "notes",
        ])
        for pr in rows:
            decision = "SKIP" if pr.skip_reason else "IMPORT"
            w.writerow([
                pr.excel_row, decision, pr.skip_reason or "",
                pr.code or "", pr.name or "", pr.erp_type or "",
                pr.category or "", pr.material_type or "",
                "Y" if pr.is_column else "", pr.unit or "",
                pr.manufacturer or "", pr.catalog_no or "",
                pr.spec_model or "", pr.notes or "",
            ])


def print_stats(stats: dict) -> None:
    print("=" * 60)
    print(f"Excel 总行:   {stats['total']}")
    print(f"待插入:       {stats['to_insert']}")
    print(f"已实际插入:   {stats['inserted']}")
    print(f"DB 已有跳过:  {stats['duplicated_code']}")
    print(f"色谱柱覆写:   {stats['column_overwrite']}")
    print("\n--- 跳过原因 ---")
    for k, v in sorted(stats["skipped_by_reason"].items(), key=lambda x: -x[1]):
        print(f"  {k}: {v}")
    print("\n--- material_type 分布(待插入) ---")
    for k, v in sorted(stats["type_dist"].items(), key=lambda x: -x[1]):
        print(f"  {k}: {v}")
    print("\n--- category 分布(待插入) ---")
    for k, v in sorted(stats["category_dist"].items(), key=lambda x: -x[1]):
        print(f"  {k}: {v}")
    print("=" * 60)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--xlsx", required=True, help="Excel 路径（容器内）")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--report", default="/tmp/import_report_0609.csv")
    args = ap.parse_args()

    xlsx = Path(args.xlsx)
    if not xlsx.exists():
        logger.error(f"Excel 不存在: {xlsx}")
        return 2

    rows = read_excel(xlsx)
    logger.info(f"读到 Excel 数据行: {len(rows)}")
    stats = asyncio.run(import_rows(rows, dry_run=args.dry_run))
    write_report(rows, Path(args.report))
    logger.info(f"报告已写入: {args.report}")
    print_stats(stats)
    return 0


if __name__ == "__main__":
    sys.exit(main())
