"""
从公司设备台账 Excel 批量导入 eqp.equipment

对标 import_materials_excel.py，但设备台账各部门表头不统一，故改为
**表头驱动**（按列标题名匹配字段，而非固定列序）。可重入。

用法：
  # dry-run，只生成报告不写库
  docker compose -f deploy/docker-compose.dev.yml exec backend \
    python -m app.scripts.import_equipment_excel \
      --xlsx /data/设备台账.xlsx \
      --dry-run --report /data/eqp_import_report.csv

  # 真跑（先 dry-run 看报告）
  docker compose -f deploy/docker-compose.dev.yml exec backend \
    python -m app.scripts.import_equipment_excel \
      --xlsx /data/设备台账.xlsx --report /data/eqp_import_report.csv

  # 指定 sheet（默认取第一个）
  ... --sheet 设备清单

行为：
  - 表头行自动探测（前 10 行内找包含「名称」类列的行）
  - equipment_code 可空：留空交由 DB 触发器自动分配 EQP-yyyyXXXXXX
  - category 归一化到 4 枚举（分析仪器/实验设备/辅助设备/其他）；
    无法识别 → 默认「其他」并在报告标 category_defaulted=Y
  - 可重入去重：
      有 code 行 → 按 code 与 DB 已有比对（已存在则跳过）
      无 code 行 → 按自然键 (name|manufacturer|serial_no) 与 DB 已有比对
    Excel 内部同样按上述键去重
  - 脏数据跳过：空 equipment_name
  - 审计 username = admin (excel-import) 可追溯
"""
from __future__ import annotations

import argparse
import asyncio
import csv
import sys
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path

import openpyxl
from loguru import logger
from sqlalchemy import select

from app.core.database import AsyncSessionLocal
from app.domains.auth.models import User
from app.domains.eqp.models import Equipment
from app.shared.audit_context import (
    audit_user_id,
    audit_username,
    set_audit_session_vars,
)

# ---------- 配置 ----------

VALID_CATEGORIES = {
    "分析仪器",
    "工艺/制备设备",
    "通用实验室设备",
    "公用工程/环境与支持系统",
    "IT/自动化与数据系统",
}
DEFAULT_CATEGORY = "通用实验室设备"  # 新体系无「其他」，无法识别时落最通用类

# category 别名 → 枚举值。命中 key（子串包含，按顺序首个命中）即归一化。
# 顺序重要：把强信号（IT/公用工程/工艺）排在通用类前，避免被泛词抢走。
CATEGORY_ALIASES: list[tuple[str, str]] = [
    # IT / 自动化与数据系统
    ("电脑", "IT/自动化与数据系统"),
    ("计算机", "IT/自动化与数据系统"),
    ("服务器", "IT/自动化与数据系统"),
    ("工作站", "IT/自动化与数据系统"),
    ("网络", "IT/自动化与数据系统"),
    ("数据库", "IT/自动化与数据系统"),
    ("采集", "IT/自动化与数据系统"),
    ("软件", "IT/自动化与数据系统"),
    ("LIMS", "IT/自动化与数据系统"),
    ("ELN", "IT/自动化与数据系统"),
    # 公用工程 / 环境与支持系统
    ("纯化水", "公用工程/环境与支持系统"),
    ("WFI", "公用工程/环境与支持系统"),
    ("HVAC", "公用工程/环境与支持系统"),
    ("空调", "公用工程/环境与支持系统"),
    ("压缩空气", "公用工程/环境与支持系统"),
    ("洁净", "公用工程/环境与支持系统"),
    ("灭菌", "公用工程/环境与支持系统"),
    ("高压灭菌", "公用工程/环境与支持系统"),
    ("冰箱", "公用工程/环境与支持系统"),
    ("超低温", "公用工程/环境与支持系统"),
    ("液氮", "公用工程/环境与支持系统"),
    ("公用", "公用工程/环境与支持系统"),
    ("环境", "公用工程/环境与支持系统"),
    # 工艺 / 制备设备
    ("反应器", "工艺/制备设备"),
    ("发酵", "工艺/制备设备"),
    ("层析", "工艺/制备设备"),
    ("色谱柱", "工艺/制备设备"),
    ("TFF", "工艺/制备设备"),
    ("超滤", "工艺/制备设备"),
    ("配液", "工艺/制备设备"),
    ("灌装", "工艺/制备设备"),
    ("制剂", "工艺/制备设备"),
    ("中试", "工艺/制备设备"),
    ("工艺", "工艺/制备设备"),
    ("生产", "工艺/制备设备"),
    # 分析仪器
    ("色谱", "分析仪器"),
    ("光谱", "分析仪器"),
    ("质谱", "分析仪器"),
    ("HPLC", "分析仪器"),
    ("UPLC", "分析仪器"),
    ("GC", "分析仪器"),
    ("酶标", "分析仪器"),
    ("Biacore", "分析仪器"),
    ("溶出", "分析仪器"),
    ("检测", "分析仪器"),
    ("分析", "分析仪器"),
    ("仪器", "分析仪器"),
    # 通用实验室设备
    ("离心", "通用实验室设备"),
    ("天平", "通用实验室设备"),
    ("pH", "通用实验室设备"),
    ("移液", "通用实验室设备"),
    ("培养箱", "通用实验室设备"),
    ("水浴", "通用实验室设备"),
    ("振荡", "通用实验室设备"),
    ("显微镜", "通用实验室设备"),
]

# 表头别名（规范化后） → 目标字段。规范化：去空格、转小写。
HEADER_MAP: dict[str, str] = {}


def _reg(field: str, *aliases: str) -> None:
    for a in aliases:
        HEADER_MAP[_norm_header(a)] = field


def _norm_header(s: str) -> str:
    return "".join(str(s).split()).lower().replace("（", "(").replace("）", ")")


_reg("equipment_code", "设备编码", "设备编号", "编码", "编号", "资产编号", "设备代码")
_reg("equipment_name", "设备名称", "名称", "仪器名称", "设备")
_reg("equipment_name_en", "英文名称", "设备英文名", "英文名", "englishname", "name(en)")
_reg("category", "类别", "分类", "设备类别", "设备分类", "类型")
_reg("model", "型号", "规格型号", "规格/型号", "规格", "spec", "model")
_reg("manufacturer", "生产商", "厂商", "制造商", "生产厂家", "厂家", "品牌", "manufacturer")
_reg("serial_no", "序列号", "出厂编号", "出厂序列号", "sn", "serialno", "serialnumber")
_reg("rated_power", "额定功率", "功率", "ratedpower", "power")
_reg("origin", "产地", "原产地", "生产国", "国别", "origin")
_reg("purchase_date", "购置日期", "采购日期", "购入日期", "启用日期", "购置时间")
_reg("asset_value", "资产原值", "资产价值", "原值", "金额", "价值", "采购金额")
_reg("supplier", "供应商", "供货商", "经销商", "代理商")
_reg("description", "描述", "说明", "用途", "功能描述")
_reg("notes", "备注", "remark", "remarks", "note", "notes")

# 字段长度上限（与 ORM / DB 对齐）
MAXLEN = {
    "equipment_code": 32,
    "equipment_name": 255,
    "equipment_name_en": 255,
    "category": 64,
    "model": 200,
    "manufacturer": 100,
    "serial_no": 100,
    "rated_power": 64,
    "origin": 100,
    "supplier": 200,
}


@dataclass
class ParsedRow:
    excel_row: int
    equipment_code: str | None = None
    equipment_name: str | None = None
    equipment_name_en: str | None = None
    category: str | None = None
    model: str | None = None
    manufacturer: str | None = None
    serial_no: str | None = None
    rated_power: str | None = None
    origin: str | None = None
    purchase_date: date | None = None
    asset_value: Decimal | None = None
    supplier: str | None = None
    description: str | None = None
    notes: str | None = None
    # 计算字段
    category_defaulted: bool = False
    skip_reason: str | None = None

    def natural_key(self) -> str:
        return "|".join([
            (self.equipment_name or "").lower(),
            (self.manufacturer or "").lower(),
            (self.serial_no or "").lower(),
        ])


# ---------- 解析工具 ----------

def _norm(val) -> str | None:
    if val is None:
        return None
    s = str(val).strip()
    if not s or s.upper() in ("N/A", "NA", "无", "-", "/"):
        return None
    return s


def _truncate(val: str | None, n: int) -> str | None:
    if val is None:
        return None
    return val if len(val) <= n else val[:n]


def parse_date(val) -> date | None:
    if val is None:
        return None
    if isinstance(val, datetime):
        return val.date()
    if isinstance(val, date):
        return val
    s = str(val).strip()
    if not s:
        return None
    for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%Y.%m.%d", "%Y年%m月%d日", "%Y%m%d"):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    return None


def parse_decimal(val) -> Decimal | None:
    if val is None:
        return None
    if isinstance(val, (int, float, Decimal)):
        try:
            return Decimal(str(val))
        except InvalidOperation:
            return None
    s = str(val).strip()
    # 去掉货币符号/逗号/单位
    for ch in ("¥", "￥", "$", ",", " ", "元", "万元"):
        s = s.replace(ch, "")
    if not s:
        return None
    try:
        return Decimal(s)
    except InvalidOperation:
        return None


def normalize_category(raw: str | None) -> tuple[str, bool]:
    """返回 (category, defaulted)。无法识别 → (DEFAULT_CATEGORY=通用实验室设备, True)。

    匹配既支持 category 列原值，也兼容把设备名称当 raw 传入做关键词推断
    （LIMS 无 category 来源时按 NAME 推断会用到）。英文关键词大小写不敏感。
    """
    if not raw:
        return DEFAULT_CATEGORY, True
    if raw in VALID_CATEGORIES:
        return raw, False
    up = raw.upper()
    for needle, mapped in CATEGORY_ALIASES:
        if needle.upper() in up:
            return mapped, False
    return DEFAULT_CATEGORY, True


# ---------- 表头探测 + 行解析 ----------

def detect_header(ws, scan_rows: int = 10) -> tuple[int, dict[int, str]]:
    """在前 scan_rows 行内找表头行。返回 (header_row_idx, {col_idx: field})。

    判定：该行映射出的字段里必须含 equipment_name。
    """
    for r_idx, row in enumerate(
        ws.iter_rows(min_row=1, max_row=scan_rows, values_only=True), start=1
    ):
        col_field: dict[int, str] = {}
        for c_idx, cell in enumerate(row):
            h = _norm(cell)
            if h is None:
                continue
            field = HEADER_MAP.get(_norm_header(h))
            if field and field not in col_field.values():
                col_field[c_idx] = field
        if "equipment_name" in col_field.values():
            return r_idx, col_field
    raise RuntimeError(
        "未能在前 %d 行内识别表头（需包含『设备名称/名称』列）" % scan_rows
    )


def parse_row(idx: int, row: tuple, col_field: dict[int, str]) -> ParsedRow:
    pr = ParsedRow(excel_row=idx)
    for c_idx, field in col_field.items():
        if c_idx >= len(row):
            continue
        raw = row[c_idx]
        if field == "purchase_date":
            pr.purchase_date = parse_date(raw)
        elif field == "asset_value":
            pr.asset_value = parse_decimal(raw)
        elif field in ("description", "notes"):
            setattr(pr, field, _norm(raw))
        else:
            setattr(pr, field, _truncate(_norm(raw), MAXLEN.get(field, 255)))

    if not pr.equipment_name:
        pr.skip_reason = "empty_name"
        return pr

    cat, defaulted = normalize_category(pr.category)
    pr.category = cat
    pr.category_defaulted = defaulted
    return pr


def read_excel(path: Path, sheet: str | None) -> list[ParsedRow]:
    wb = openpyxl.load_workbook(path, data_only=True)
    ws = wb[sheet] if sheet else wb[wb.sheetnames[0]]
    header_row, col_field = detect_header(ws)
    logger.info(
        f"sheet={ws.title} 表头行={header_row} 识别列="
        + ", ".join(f"{v}" for v in col_field.values())
    )
    out: list[ParsedRow] = []
    for idx, row in enumerate(
        ws.iter_rows(min_row=header_row + 1, values_only=True), start=header_row + 1
    ):
        if not any(row):
            continue
        out.append(parse_row(idx, row, col_field))
    return out


# ---------- 入库 ----------

async def get_existing(db) -> tuple[set[str], set[str]]:
    """返回 (已有 code 集, 已有自然键集)。仅未软删记录。"""
    res = await db.execute(
        select(
            Equipment.equipment_code,
            Equipment.equipment_name,
            Equipment.manufacturer,
            Equipment.serial_no,
        ).where(Equipment.deleted_at.is_(None))
    )
    codes: set[str] = set()
    nat: set[str] = set()
    for code, name, mfr, sn in res.all():
        if code:
            codes.add(code)
        nat.add("|".join([
            (name or "").lower(), (mfr or "").lower(), (sn or "").lower()
        ]))
    return codes, nat


async def import_rows(
    rows: list[ParsedRow], dry_run: bool, sheet: str | None
) -> dict:
    stats: dict = {
        "total": len(rows),
        "skipped_by_reason": {},
        "duplicated": 0,
        "category_defaulted": 0,
        "to_insert": 0,
        "category_dist": {},
        "inserted": 0,
    }

    async with AsyncSessionLocal() as db:
        admin_res = await db.execute(select(User).where(User.username == "admin"))
        admin = admin_res.scalar_one_or_none()
        if admin is None:
            raise RuntimeError("缺少 admin 用户，先跑 seed_data")

        token_id = audit_user_id.set(admin.user_id)
        token_name = audit_username.set("admin (excel-import)")
        try:
            await set_audit_session_vars(db)
            existing_codes, existing_nat = await get_existing(db)

            seen_codes: set[str] = set()
            seen_nat: set[str] = set()
            to_insert: list[ParsedRow] = []

            for pr in rows:
                if pr.skip_reason:
                    _bump(stats["skipped_by_reason"], pr.skip_reason)
                    continue
                if pr.category_defaulted:
                    stats["category_defaulted"] += 1

                # 去重：有 code 走 code，无 code 走自然键
                if pr.equipment_code:
                    if pr.equipment_code in existing_codes:
                        stats["duplicated"] += 1
                        pr.skip_reason = "db_dup_code"
                        continue
                    if pr.equipment_code in seen_codes:
                        pr.skip_reason = "inner_dup_code"
                        _bump(stats["skipped_by_reason"], "inner_dup_code")
                        continue
                    seen_codes.add(pr.equipment_code)
                else:
                    nk = pr.natural_key()
                    if nk in existing_nat:
                        stats["duplicated"] += 1
                        pr.skip_reason = "db_dup_natural_key"
                        continue
                    if nk in seen_nat:
                        pr.skip_reason = "inner_dup_natural_key"
                        _bump(stats["skipped_by_reason"], "inner_dup_natural_key")
                        continue
                    seen_nat.add(nk)

                to_insert.append(pr)
                _bump(stats["category_dist"], pr.category)

            stats["to_insert"] = len(to_insert)

            if dry_run:
                logger.info(f"[DRY-RUN] 将插入 {len(to_insert)} 行，未提交")
            else:
                for pr in to_insert:
                    db.add(
                        Equipment(
                            # 留空 → 触发器分配 EQP-yyyyXXXXXX
                            equipment_code=pr.equipment_code or None,
                            equipment_name=pr.equipment_name,
                            equipment_name_en=pr.equipment_name_en,
                            category=pr.category,
                            model=pr.model,
                            manufacturer=pr.manufacturer,
                            serial_no=pr.serial_no,
                            rated_power=pr.rated_power,
                            origin=pr.origin,
                            purchase_date=pr.purchase_date,
                            asset_value=pr.asset_value,
                            supplier=pr.supplier,
                            status="active",
                            description=pr.description,
                            notes=pr.notes,
                            created_by=admin.user_id,
                            updated_by=admin.user_id,
                        )
                    )
                await db.commit()
                stats["inserted"] = len(to_insert)
                logger.success(f"已插入 {len(to_insert)} 条设备")
        finally:
            audit_user_id.reset(token_id)
            audit_username.reset(token_name)

    return stats


def _bump(d: dict, k: str) -> None:
    d.setdefault(k, 0)
    d[k] += 1


def write_report(rows: list[ParsedRow], report_path: Path) -> None:
    with report_path.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow([
            "excel_row", "decision", "skip_reason",
            "equipment_code", "equipment_name", "category", "category_defaulted",
            "model", "manufacturer", "serial_no",
            "purchase_date", "asset_value", "supplier", "notes",
        ])
        for pr in rows:
            decision = "SKIP" if pr.skip_reason else "IMPORT"
            w.writerow([
                pr.excel_row, decision, pr.skip_reason or "",
                pr.equipment_code or "", pr.equipment_name or "", pr.category or "",
                "Y" if pr.category_defaulted else "",
                pr.model or "", pr.manufacturer or "", pr.serial_no or "",
                pr.purchase_date.isoformat() if pr.purchase_date else "",
                str(pr.asset_value) if pr.asset_value is not None else "",
                pr.supplier or "", pr.notes or "",
            ])


def print_stats(stats: dict) -> None:
    print("=" * 60)
    print(f"Excel 数据行: {stats['total']}")
    print(f"待插入:       {stats['to_insert']}")
    print(f"已实际插入:   {stats['inserted']}")
    print(f"已存在跳过:   {stats['duplicated']}")
    print(f"category 默认为『其他』: {stats['category_defaulted']}")
    print()
    print("--- 跳过原因 ---")
    for k, v in sorted(stats["skipped_by_reason"].items(), key=lambda x: -x[1]):
        print(f"  {k}: {v}")
    print()
    print("--- category 分布（待插入）---")
    for k, v in sorted(stats["category_dist"].items(), key=lambda x: -x[1]):
        print(f"  {k}: {v}")
    print("=" * 60)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--xlsx", required=True, help="Excel 路径（容器内）")
    ap.add_argument("--sheet", default=None, help="Sheet 名（默认第一个）")
    ap.add_argument("--dry-run", action="store_true", help="只生成报告不写库")
    ap.add_argument("--report", default="/tmp/eqp_import_report.csv", help="CSV 报告路径")
    args = ap.parse_args()

    xlsx = Path(args.xlsx)
    if not xlsx.exists():
        logger.error(f"Excel 不存在: {xlsx}")
        return 2

    rows = read_excel(xlsx, args.sheet)
    logger.info(f"读到数据行: {len(rows)}")

    stats = asyncio.run(import_rows(rows, dry_run=args.dry_run, sheet=args.sheet))
    write_report(rows, Path(args.report))
    logger.info(f"报告已写入: {args.report}")
    print_stats(stats)
    return 0


if __name__ == "__main__":
    sys.exit(main())
