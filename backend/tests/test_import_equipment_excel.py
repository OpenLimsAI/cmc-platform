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
    _norm,
    detect_header,
    normalize_category,
    normalize_name,
    normalize_status,
    parse_date,
    parse_decimal,
    parse_row,
    read_excel,
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
    # 泛词垫底：「分析天平」是天平→通用，不能被「分析」抢成分析仪器
    assert normalize_category("电子分析天平") == ("通用实验室设备", False)
    assert normalize_category("分析天平") == ("通用实验室设备", False)


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
        "equipment_no", "equipment_name", "category", "manufacturer"
    }
    pr = parse_row(3, ("QC-OLD-001", "高效液相色谱仪", "分析", "Agilent"), col_field)
    assert pr.skip_reason is None
    assert pr.equipment_no == "QC-OLD-001"
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
    assert pr.equipment_no is None
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
    assert keep[0].equipment_no is None


# ============== 设备部台账适配（0057，2026-09-10）==============

def test_parse_date_year_month():
    """设备部台账「首次启用日期」只写到年月 → 取当月 1 日"""
    assert parse_date("2016.05") == date(2016, 5, 1)
    assert parse_date("2016-05") == date(2016, 5, 1)
    assert parse_date("2016年5月") == date(2016, 5, 1)
    # 完整日期不受影响
    assert parse_date("2016.05.20") == date(2016, 5, 20)


@pytest.mark.parametrize("raw,expected", [
    # 2026-09-11：一格两语言原样入库，不拆——只去掉单元格里的折行
    ("Bioreactor/\n225L生物反应器", "Bioreactor/225L生物反应器"),
    ("Nutrient Tank/\n600L补料罐", "Nutrient Tank/600L补料罐"),
    ("Ready To Process Wave25/\n波浪式生物反应器", "Ready To Process Wave25/波浪式生物反应器"),
    # 两侧都是中文（一台设备的两个规格）同样原样
    ("850L培养基罐/400L培养基罐", "850L培养基罐/400L培养基罐"),
    # 纯中文、纯英文原样；名字中间的空格保留
    ("蠕动泵", "蠕动泵"),
    ("HOT LIPS TUBE SEALER", "HOT LIPS TUBE SEALER"),
    ("液氮罐 备用", "液氮罐 备用"),
    (None, None),
])
def test_normalize_name_keeps_whole(raw, expected):
    assert normalize_name(raw) == expected


@pytest.mark.parametrize("raw,expected", [
    ("启用", "active"),
    (None, "active"),
    ("停用", "active"),  # 只有明确报废/退役才置 retired
    ("已报废", "retired"),
    ("退役", "retired"),
])
def test_normalize_status(raw, expected):
    assert normalize_status(raw) == expected


def test_category_process_beats_it_workstation():
    """「装柱工作站」「轴向压缩柱工作站」是层析工艺设备，不能被 IT 的「工作站」抢走"""
    assert normalize_category("电动装柱工作站") == ("工艺/制备设备", False)
    assert normalize_category("电动轴向压缩柱工作站") == ("工艺/制备设备", False)
    assert normalize_category("装柱站") == ("工艺/制备设备", False)
    # 真正的 IT 工作站不受影响
    assert normalize_category("数据采集工作站") == ("IT/自动化与数据系统", False)


def test_category_liquid_nitrogen_tank_stays_utility():
    """新增的工艺物料罐关键词不能抢走「液氮罐」"""
    assert normalize_category("液氮罐") == ("公用工程/环境与支持系统", False)
    assert normalize_category("600L补料罐") == ("工艺/制备设备", False)
    assert normalize_category("850L缓冲液罐") == ("工艺/制备设备", False)


def _ledger_sheet(rows: list[tuple]):
    """造一张设备部台账样式的 sheet（表头在第 4 行，前 3 行是抬头）"""
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(["泰州迈博太科药业有限公司"])
    ws.append(["生产一部  设备/设施统计台账"])
    ws.append(["编号：SMP-PES-001-F13"])
    ws.append([
        "序号", "设备名称", "别名/曾用名", "型号", "设备编号", "首次启用日期",
        "存放位置", "制造单位", "唯一编码", "出厂日期", "总功率", "总重", "设备状态",
    ])
    for r in rows:
        ws.append(r)
    return wb, ws


def test_ledger_header_detection_maps_department_columns():
    """设备部台账的列名（制造单位/唯一编码/总功率/存放位置/首次启用日期）都要认出来"""
    _, ws = _ledger_sheet([])
    header_row, col_field = detect_header(ws)
    assert header_row == 4
    fields = set(col_field.values())
    assert {
        "equipment_name", "model", "equipment_no", "commission_date",
        "room", "manufacturer", "serial_no", "rated_power", "status_raw",
    } <= fields
    # 主数据没有正式列的三项进 extra
    assert {"alias", "x_manufacture_date", "x_weight"} <= fields  # 0059：别名已转正为正式列


def test_ledger_row_roundtrip(tmp_path):
    """整行解析：名称原样（不拆）、年月日期、部门/厂区兜底、extra 收纳台账杂项"""
    wb, _ = _ledger_sheet([
        (1, "Bioreactor/\n225L生物反应器", "BR1-1;\n发酵线1", "225/150L",
         "CC1-SC-001-01", "2016.05", "3129培养间", "Bioengineering AG",
         "D3285", "2015.05", "16kW", "2150kg", "启用"),
    ])
    path = tmp_path / "ledger.xlsx"
    wb.save(path)

    rows = read_excel(path, None, default_department="生产一部", default_site="南楼")
    assert len(rows) == 1
    pr = rows[0]
    assert pr.skip_reason is None
    assert pr.equipment_name == "Bioreactor/225L生物反应器"  # 整体入库，不拆
    assert pr.equipment_name_en is None  # 台账没有独立英文名列
    assert pr.equipment_no == "CC1-SC-001-01"
    assert pr.manufacturer == "Bioengineering AG"
    assert pr.serial_no == "D3285"
    assert pr.rated_power == "16kW"
    assert pr.room == "3129培养间"
    assert pr.commission_date == date(2016, 5, 1)
    assert pr.purchase_date is None  # 启用日期 ≠ 购入日期，不能混
    # 台账没有分类列 → 按名称预归类，并标记需人工核对
    assert pr.category == "工艺/制备设备"
    assert pr.category_source == "name_guess"
    assert pr.status == "active"
    # Excel 无部门/厂区列 → 用命令行统一指定的值兜底
    assert pr.department == "生产一部"
    assert pr.site == "南楼"
    # 别名/曾用名进正式列（0059），不再塞进 extra
    assert pr.alias is not None and "BR1-1" in pr.alias
    # 主数据仍无正式列的信息进 extra，不丢
    extra = pr.build_extra()
    assert extra["source"] == "eqp_ledger_excel"
    assert extra["出厂日期"] == "2015.05"
    assert extra["总重"] == "2150kg"
    assert "别名" not in extra


def test_ledger_empty_name_skipped(tmp_path):
    wb, _ = _ledger_sheet([
        (1, None, None, None, "CC1-XX-999", None, None, None, None, None, None, None, None),
    ])
    path = tmp_path / "ledger.xlsx"
    wb.save(path)
    rows = read_excel(path, None)
    assert rows[0].skip_reason == "empty_name"
