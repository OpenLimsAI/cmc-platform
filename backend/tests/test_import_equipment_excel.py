"""
EQP Excel 导入工具纯函数单测（不连库，进程内直接 import 模块）

覆盖：表头探测 / 行解析 / category 归一化 / 日期&金额解析 / 自然键去重信号。
入库逻辑（import_rows）依赖真实 DB，由手工 --dry-run 验证，不在此单测。
"""
from datetime import date
from decimal import Decimal

import openpyxl
import pytest

from app.scripts.import_equipment_excel import (
    detect_header,
    normalize_category,
    parse_date,
    parse_decimal,
    parse_row,
    read_excel,
    _norm,
)


def test_norm_strips_and_nulls():
    assert _norm("  abc  ") == "abc"
    assert _norm("") is None
    assert _norm("N/A") is None
    assert _norm("无") is None
    assert _norm("-") is None
    assert _norm(None) is None


@pytest.mark.parametrize("raw,expected", [
    ("2024-03-15", date(2024, 3, 15)),
    ("2024/03/15", date(2024, 3, 15)),
    ("2024.03.15", date(2024, 3, 15)),
    ("2024年3月15日", date(2024, 3, 15)),
    ("20240315", date(2024, 3, 15)),
    ("不是日期", None),
    (None, None),
])
def test_parse_date(raw, expected):
    assert parse_date(raw) == expected


@pytest.mark.parametrize("raw,expected", [
    ("¥12,345.67", Decimal("12345.67")),
    ("12345", Decimal("12345")),
    (12345.5, Decimal("12345.5")),
    ("3,000 元", Decimal("3000")),
    ("", None),
    ("abc", None),
    (None, None),
])
def test_parse_decimal(raw, expected):
    assert parse_decimal(raw) == expected


def test_normalize_category_exact():
    assert normalize_category("分析仪器") == ("分析仪器", False)
    assert normalize_category("工艺/制备设备") == ("工艺/制备设备", False)
    assert normalize_category("IT/自动化与数据系统") == ("IT/自动化与数据系统", False)


def test_normalize_category_alias():
    assert normalize_category("高效液相色谱") == ("分析仪器", False)
    assert normalize_category("生产灌装设备") == ("工艺/制备设备", False)
    assert normalize_category("公用工程") == ("公用工程/环境与支持系统", False)
    assert normalize_category("台式电脑") == ("IT/自动化与数据系统", False)
    assert normalize_category("离心机") == ("通用实验室设备", False)
    # 英文关键词大小写不敏感
    assert normalize_category("hplc system") == ("分析仪器", False)


def test_normalize_category_default():
    # 新体系无「其他」，无法识别落「通用实验室设备」并标 defaulted
    assert normalize_category("莫名其妙") == ("通用实验室设备", True)
    assert normalize_category(None) == ("通用实验室设备", True)


def _make_ws(rows: list[list]):
    wb = openpyxl.Workbook()
    ws = wb.active
    for r in rows:
        ws.append(r)
    return ws


def test_detect_header_and_parse_row():
    ws = _make_ws([
        ["公司设备台账", None, None, None],  # 标题行，无表头
        ["设备编号", "设备名称", "类别", "生产商"],
        ["EQP-OLD-001", "高效液相色谱仪", "分析", "Agilent"],
    ])
    header_row, col_field = detect_header(ws)
    assert header_row == 2
    assert set(col_field.values()) == {
        "equipment_code", "equipment_name", "category", "manufacturer"
    }
    pr = parse_row(3, ("EQP-OLD-001", "高效液相色谱仪", "分析", "Agilent"), col_field)
    assert pr.skip_reason is None
    assert pr.equipment_code == "EQP-OLD-001"
    assert pr.equipment_name == "高效液相色谱仪"
    assert pr.category == "分析仪器"  # 「分析」别名归一化
    assert pr.manufacturer == "Agilent"


def test_parse_row_empty_name_skipped():
    ws = _make_ws([["名称", "类别"], ["", "分析仪器"]])
    _, col_field = detect_header(ws)
    pr = parse_row(2, ("", "分析仪器"), col_field)
    assert pr.skip_reason == "empty_name"


def test_detect_header_requires_name():
    ws = _make_ws([["类别", "生产商"], ["分析仪器", "X"]])
    with pytest.raises(RuntimeError):
        detect_header(ws)


def test_natural_key_for_codeless_row():
    ws = _make_ws([["名称", "生产商", "序列号"], ["pH 计", "Mettler", "SN123"]])
    _, col_field = detect_header(ws)
    pr = parse_row(2, ("pH 计", "Mettler", "SN123"), col_field)
    assert pr.equipment_code is None
    assert pr.natural_key() == "ph 计|mettler|sn123"


def test_read_excel_blank_code_ok(tmp_path):
    """留空 code 行不被跳过（交触发器分配），名称必填。"""
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(["设备名称", "类别", "型号"])
    ws.append(["生物安全柜", "公用工程", "BSC-1500"])
    ws.append(["", "分析仪器", "X"])  # 空名跳过
    p = tmp_path / "eqp.xlsx"
    wb.save(p)

    rows = read_excel(p, None)
    assert len(rows) == 2
    keep = [r for r in rows if r.skip_reason is None]
    assert len(keep) == 1
    assert keep[0].equipment_name == "生物安全柜"
    assert keep[0].category == "公用工程/环境与支持系统"
    assert keep[0].equipment_code is None
