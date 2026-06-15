"""
从公司 Excel「物流-物料代码表」批量导入 mm.material

用法：
  # dry-run，只生成报告不写库
  docker compose -f deploy/docker-compose.dev.yml exec backend \
    python -m app.scripts.import_materials_excel \
      --xlsx /data/物流-物料代码表20260429.xlsx \
      --dry-run --report /data/import_report.csv

  # 真跑（注意先 dry-run 看报告）
  docker compose -f deploy/docker-compose.dev.yml exec backend \
    python -m app.scripts.import_materials_excel \
      --xlsx /data/物流-物料代码表20260429.xlsx \
      --report /data/import_report.csv

行为：
  - 仅读 Sheet「物料」（Sheet 2「药/产品/原液」跳过，是产品不是物料）
  - category 直接采用 Excel「分类」列（已在 0039 枚举中含 外包材）
  - material_type 按 category 映射：见 CATEGORY_TO_TYPE
  - 色谱柱识别：name 含 色谱柱/层析柱/保护柱/亲和柱/Column 且不含排除词，
    强制覆写 material_type='column'（保留原 category）
  - 脏数据按 user 指示跳过：空 material_code、空 category、空 material_name
  - 重复 material_code：跳过并记入报告（DB 已有同 code，认为是已录入）
"""
from __future__ import annotations

import argparse
import asyncio
import csv
import re
import sys
from dataclasses import dataclass
from pathlib import Path

import openpyxl
from loguru import logger
from sqlalchemy import select

from app.core.database import AsyncSessionLocal
from app.domains.auth.models import User
from app.domains.mm.models import Material
from app.shared.audit_context import (
    audit_user_id,
    audit_username,
    set_audit_session_vars,
)

# ---------- 配置 ----------

CATEGORY_TO_TYPE: dict[str, str] = {
    "试剂": "reagent",
    "关键试剂": "reagent",
    "原辅料": "reagent",
    "一般耗材": "consumable",
    "关键耗材": "consumable",
    "内包材": "consumable",
    "外包材": "consumable",
    "劳保": "consumable",
    "自制包材": "consumable",
    "运输包装材料": "consumable",
    "工艺用水/气": "consumable",
    "标准品": "standard",
    "参比品": "standard",
    "对照品": "standard",
    "细胞种子": "standard",
}

# 色谱柱识别：name 含这些关键字 → material_type 覆写为 column
COLUMN_INCLUDE_RE = re.compile(
    r"(色谱柱|层析柱|保护柱|亲和柱|分析柱|" r"\bColumn\b)",
    re.IGNORECASE,
)
# 但排除：柱套/筛板/连接管/进样小瓶/内衬管/Kit/介质/填料/空柱筛板
COLUMN_EXCLUDE_RE = re.compile(
    r"(柱套|筛板|连接管|进样|内衬|小瓶|" r"\bkit\b|介质|填料|空柱|HMWP)",
    re.IGNORECASE,
)

# Excel 列索引（0-based）：序号,分类,代码,物料名称,级别,生产商,规格/型号,货号,单位,包装规格,备注
COL_SEQ, COL_CAT, COL_CODE, COL_NAME = 0, 1, 2, 3
COL_GRADE, COL_MFG, COL_SPEC, COL_CATALOG = 4, 5, 6, 7
COL_UNIT, COL_PKG, COL_NOTE = 8, 9, 10


@dataclass
class ParsedRow:
    excel_row: int
    code: str | None
    name: str | None
    category: str | None
    grade: str | None
    manufacturer: str | None
    spec_model: str | None
    catalog_no: str | None
    unit: str | None
    package_spec: str | None
    notes: str | None
    # 计算字段
    material_type: str | None = None
    skip_reason: str | None = None  # 非空则跳过
    is_column: bool = False


def _norm(val) -> str | None:
    """去掉前后空格、'N/A'、None → None；纯空字符串 → None"""
    if val is None:
        return None
    s = str(val).strip()
    if not s or s.upper() == "N/A":
        return None
    return s


def _truncate(val: str | None, n: int) -> str | None:
    if val is None:
        return None
    return val if len(val) <= n else val[:n]


def detect_column(name: str | None) -> bool:
    if not name:
        return False
    if COLUMN_EXCLUDE_RE.search(name):
        return False
    return bool(COLUMN_INCLUDE_RE.search(name))


def parse_row(idx: int, row: tuple) -> ParsedRow:
    code = _norm(row[COL_CODE])
    name = _norm(row[COL_NAME])
    cat = _norm(row[COL_CAT])

    pr = ParsedRow(
        excel_row=idx,
        code=code,
        name=name,
        category=cat,
        grade=_truncate(_norm(row[COL_GRADE]), 32),
        manufacturer=_truncate(_norm(row[COL_MFG]), 100),
        spec_model=_truncate(_norm(row[COL_SPEC]), 200),
        catalog_no=_truncate(_norm(row[COL_CATALOG]), 100),
        unit=_truncate(_norm(row[COL_UNIT]), 20),
        package_spec=_truncate(_norm(row[COL_PKG]), 100),
        notes=_norm(row[COL_NOTE]),
    )

    # 脏数据
    if not code:
        pr.skip_reason = "empty_code"
        return pr
    if not name:
        pr.skip_reason = "empty_name"
        return pr
    if not cat:
        pr.skip_reason = "empty_category"
        return pr

    # material_code 长度 20 上限（DB schema）
    if len(code) > 20:
        pr.skip_reason = f"code_too_long({len(code)})"
        return pr

    # category 必须在已知映射里
    if cat not in CATEGORY_TO_TYPE:
        pr.skip_reason = f"unknown_category:{cat}"
        return pr

    pr.material_type = CATEGORY_TO_TYPE[cat]

    # 色谱柱覆写
    if detect_column(name):
        pr.is_column = True
        pr.material_type = "column"

    # unit 兜底：空 → 'ea'
    if pr.unit is None:
        pr.unit = "ea"

    return pr


def read_excel(path: Path) -> list[ParsedRow]:
    wb = openpyxl.load_workbook(path, data_only=True)
    ws = wb["物料"]
    out: list[ParsedRow] = []
    for idx, row in enumerate(ws.iter_rows(min_row=2, values_only=True), start=2):
        if not any(row):
            continue
        out.append(parse_row(idx, row))
    return out


async def get_existing_codes(db) -> set[str]:
    res = await db.execute(select(Material.material_code))
    return {r[0] for r in res.all()}


async def import_rows(rows: list[ParsedRow], dry_run: bool) -> dict:
    """执行导入。返回统计 dict。"""
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

    # 第一遍：按 material_code 唯一性聚合（防 Excel 内部重复）
    by_code: dict[str, ParsedRow] = {}
    inner_dup = 0
    for pr in rows:
        if pr.skip_reason:
            stats["skipped_by_reason"].setdefault(pr.skip_reason, 0)
            stats["skipped_by_reason"][pr.skip_reason] += 1
            continue
        if pr.code in by_code:
            inner_dup += 1
            stats["skipped_by_reason"].setdefault("inner_dup_code", 0)
            stats["skipped_by_reason"]["inner_dup_code"] += 1
            pr.skip_reason = "inner_dup_code"
            continue
        by_code[pr.code] = pr

    async with AsyncSessionLocal() as db:
        # 系统操作者 → audit GUC
        admin_res = await db.execute(select(User).where(User.username == "admin"))
        admin = admin_res.scalar_one_or_none()
        if admin is None:
            raise RuntimeError("缺少 admin 用户，先跑 seed_data")

        token_id = audit_user_id.set(admin.user_id)
        token_name = audit_username.set("admin (excel-import)")
        try:
            await set_audit_session_vars(db)
            existing = await get_existing_codes(db)

            to_insert: list[ParsedRow] = []
            for code, pr in by_code.items():
                if code in existing:
                    stats["duplicated_code"] += 1
                    pr.skip_reason = "db_dup_code"
                    continue
                to_insert.append(pr)
                stats["type_dist"].setdefault(pr.material_type, 0)
                stats["type_dist"][pr.material_type] += 1
                stats["category_dist"].setdefault(pr.category, 0)
                stats["category_dist"][pr.category] += 1
                if pr.is_column:
                    stats["column_overwrite"] += 1

            stats["to_insert"] = len(to_insert)

            if dry_run:
                logger.info(f"[DRY-RUN] 将插入 {len(to_insert)} 行，未提交")
            else:
                # 批量插入
                for pr in to_insert:
                    db.add(
                        Material(
                            material_code=pr.code,
                            material_name=pr.name,
                            material_type=pr.material_type,
                            category=pr.category,
                            grade=pr.grade,
                            manufacturer=pr.manufacturer,
                            spec_model=pr.spec_model,
                            catalog_no=pr.catalog_no,
                            unit=pr.unit or "ea",
                            package_spec=pr.package_spec,
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
            "excel_row", "decision", "skip_reason",
            "code", "name", "category", "material_type", "is_column",
            "grade", "unit", "manufacturer", "catalog_no",
            "spec_model", "package_spec", "notes",
        ])
        for pr in rows:
            decision = "SKIP" if pr.skip_reason else "IMPORT"
            w.writerow([
                pr.excel_row, decision, pr.skip_reason or "",
                pr.code or "", pr.name or "", pr.category or "",
                pr.material_type or "", "Y" if pr.is_column else "",
                pr.grade or "", pr.unit or "", pr.manufacturer or "",
                pr.catalog_no or "", pr.spec_model or "",
                pr.package_spec or "", pr.notes or "",
            ])


def print_stats(stats: dict) -> None:
    print("=" * 60)
    print(f"Excel 总行: {stats['total']}")
    print(f"待插入:     {stats['to_insert']}")
    print(f"已实际插入: {stats['inserted']}")
    print(f"DB 已有同 code 跳过: {stats['duplicated_code']}")
    print(f"色谱柱覆写 (type=column): {stats['column_overwrite']}")
    print()
    print("--- 跳过原因 ---")
    for k, v in sorted(stats["skipped_by_reason"].items(), key=lambda x: -x[1]):
        print(f"  {k}: {v}")
    print()
    print("--- material_type 分布 ---")
    for k, v in sorted(stats["type_dist"].items(), key=lambda x: -x[1]):
        print(f"  {k}: {v}")
    print()
    print("--- category 分布 ---")
    for k, v in sorted(stats["category_dist"].items(), key=lambda x: -x[1]):
        print(f"  {k}: {v}")
    print("=" * 60)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--xlsx", required=True, help="Excel 路径（容器内）")
    ap.add_argument("--dry-run", action="store_true", help="只生成报告不写库")
    ap.add_argument("--report", default="/tmp/import_report.csv", help="CSV 报告路径")
    args = ap.parse_args()

    xlsx = Path(args.xlsx)
    if not xlsx.exists():
        logger.error(f"Excel 不存在: {xlsx}")
        return 2

    rows = read_excel(xlsx)
    logger.info(f"读到 Excel 行: {len(rows)}")

    stats = asyncio.run(import_rows(rows, dry_run=args.dry_run))
    write_report(rows, Path(args.report))
    logger.info(f"报告已写入: {args.report}")
    print_stats(stats)
    return 0


if __name__ == "__main__":
    sys.exit(main())
