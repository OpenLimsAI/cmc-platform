"""使用内存合成工作簿验证预览，不访问数据库或业务文件。"""
from dataclasses import asdict, replace
from io import BytesIO
import re
from zipfile import ZipFile

from openpyxl import Workbook
import pytest

from app.services.imports.preview import (
    ColumnBinding, PreviewLimits, WorkbookTemplate, preview_workbook,
)


TEMPLATE = WorkbookTemplate(
    template_code="synthetic_test_only", version="1", sheet_name="原始数据表",
    header_row=5, data_start_row=7,
    columns=(ColumnBinding("batch_number", "批号"), ColumnBinding("result_raw", "检测值")),
)


def make_workbook(rows, *, headers=("批号", "检测值"), formula=False, percent=False):
    book = Workbook()
    sheet = book.active
    sheet.title = TEMPLATE.sheet_name
    for col, value in enumerate(headers, 1):
        sheet.cell(5, col, value)
    for row, values in enumerate(rows, 7):
        for col, value in enumerate(values, 1):
            sheet.cell(row, col, value)
    if percent:
        sheet["B7"].number_format = "0.00%"
    if formula:
        sheet["B7"] = "=1+1"
    output = BytesIO()
    book.save(output)
    book.close()
    return output.getvalue()


def replace_xml(content, name, old, new):
    output = BytesIO()
    with ZipFile(BytesIO(content)) as source, ZipFile(output, "w") as target:
        for member in source.infolist():
            data = source.read(member.filename)
            if member.filename == name:
                assert old in data
                data = data.replace(old, new)
            target.writestr(member, data)
    return output.getvalue()


def parse(content, **kwargs):
    return preview_workbook(content, filename="样例.xlsx", template=TEMPLATE, **kwargs)


def codes(preview):
    return {i.code for i in preview.issues}


def test_preserves_percentage_and_text_results_without_business_interpretation():
    content = make_workbook([("0007-abc", 0.985), ("0007-abc", "<LOD"), ("B", "符合")], percent=True)
    result = parse(content)
    assert result.structure_valid
    assert result.rows[0].cells[0].value == "0007-abc"
    assert result.rows[0].cells[1].value == 0.985  # 不能自动乘100
    assert result.rows[0].cells[1].number_format == "0.00%"
    assert result.rows[0].cells[1].coordinate == "B7"
    assert [r.cells[1].value for r in result.rows[1:]] == ["<LOD", "符合"]
    assert asdict(result)["can_commit"] is False
    assert result.business_validation == "pending"


def test_all_problem_rows_remain_and_batch_values_are_not_truncated_or_coerced():
    result = parse(make_workbook([("X" * 33, 1), (123, 2), (None, 3), (" B ", 4)]))
    assert not result.structure_valid
    assert len(result.rows) == 4
    assert [r.cells[0].value for r in result.rows] == ["X" * 33, 123, None, " B "]
    assert {"BATCH_TOO_LONG", "BATCH_MUST_BE_TEXT", "REQUIRED_VALUE_MISSING", "BATCH_WHITESPACE"} <= codes(result)
    assert {i.coordinate for i in result.issues} == {"A7", "A8", "A9", "A10"}


def test_formula_and_cached_result_preserved_but_blocked():
    content = make_workbook([("B", None)], formula=True)
    with ZipFile(BytesIO(content)) as package:
        xml = package.read("xl/worksheets/sheet1.xml")
    old = re.search(rb"<f>1\+1</f><v\s*(?:/>|>\s*</v>)", xml).group(0)
    content = replace_xml(content, "xl/worksheets/sheet1.xml", old, b"<f>1+1</f><v>2</v>")
    result = parse(content)
    cell = result.rows[0].cells[1]
    assert cell.value == "=1+1"
    assert cell.cached_value == 2
    assert "FORMULA_REQUIRES_REVIEW" in codes(result)
    assert not result.structure_valid


def test_duplicate_headers_and_unknown_columns_cannot_silently_overwrite():
    result = parse(make_workbook([("A", 1, 2)], headers=("批号", "批号", "extra")))
    assert {"DUPLICATE_HEADER", "UNMAPPED_COLUMN", "MISSING_COLUMN"} <= codes(result)
    assert [c.value for c in result.rows[0].cells] == ["A", 1, 2]
    assert not result.structure_valid


def test_missing_named_sheet_does_not_fall_back_to_first_sheet():
    result = preview_workbook(make_workbook([("A", 1)]), filename="a.xlsx", template=replace(TEMPLATE, sheet_name="另一表"))
    assert "SHEET_MISSING" in codes(result)
    assert not result.rows


def test_identical_file_different_name_has_same_digest_and_keeps_repeated_observations():
    content = make_workbook([("A", 1), ("A", 1)])
    first = parse(content)
    second = preview_workbook(content, filename="另一文件名.xlsx", template=TEMPLATE)
    assert first.file_sha256 == second.file_sha256
    assert len(first.rows) == 2  # 技术重复不能凭同值自动去除


def test_incorrect_dimension_does_not_hide_real_rows():
    content = make_workbook([("A", 1), ("B", 2)])
    content = replace_xml(content, "xl/worksheets/sheet1.xml", b'ref="A5:B8"', b'ref="A1:A1"')
    result = parse(content)
    assert result.structure_valid
    assert [r.row_number for r in result.rows] == [7, 8]


def test_actual_cells_beyond_limit_are_rejected_even_with_false_dimensions():
    content = make_workbook([("A", 1), ("B", 2)])
    content = replace_xml(content, "xl/worksheets/sheet1.xml", b'ref="A5:B8"', b'ref="A1:A1"')
    result = parse(content, limits=PreviewLimits(max_row_index=7))
    assert {"CELL_LIMIT_EXCEEDED", "ROW_LIMIT_EXCEEDED"} & codes(result)
    assert not result.structure_valid
    assert not result.rows


@pytest.mark.parametrize("content,filename,expected", [
    (b"not a workbook", "a.xlsx", "WORKBOOK_UNREADABLE"),
    (b"", "a.xlsx", "INVALID_FILE_SIZE"),
    (b"content", "a.xlsm", "UNSUPPORTED_FILE"),
    (b"content", "../a.xlsx", "UNSUPPORTED_FILE"),
])
def test_bad_files_are_reported_without_throwing_or_enabling_commit(content, filename, expected):
    result = preview_workbook(content, filename=filename, template=TEMPLATE)
    assert expected in codes(result)
    assert not result.structure_valid
    assert not result.can_commit


def test_resource_limits_and_blank_rows_are_explicit():
    content = make_workbook([("A", 1), (None, None), ("B", 2)])
    result = parse(content)
    assert result.blank_row_count == 1
    assert [r.row_number for r in result.rows] == [7, 9]
    assert "INVALID_FILE_SIZE" in codes(parse(content, limits=PreviewLimits(max_file_bytes=10)))
    assert "CELL_LIMIT_EXCEEDED" in codes(parse(content, limits=PreviewLimits(max_cells=3)))


def test_template_refuses_ambiguous_or_legacy_business_field():
    with pytest.raises(ValueError):
        replace(TEMPLATE, columns=(ColumnBinding("batch_id", "批号"),))
    with pytest.raises(ValueError):
        replace(TEMPLATE, columns=(ColumnBinding("batch_number", "批号"), ColumnBinding("value", "批号")))


def test_worksheet_relationship_cannot_bypass_resource_scan():
    content = make_workbook([("A", 1), ("B", 2)])
    output = BytesIO()
    with ZipFile(BytesIO(content)) as source, ZipFile(output, "w") as target:
        for member in source.infolist():
            data = source.read(member.filename)
            name = member.filename
            if name == "xl/worksheets/sheet1.xml":
                name = "xl/custom/sheet1.xml"
            if member.filename == "xl/_rels/workbook.xml.rels":
                data = data.replace(b"/xl/worksheets/sheet1.xml", b"/xl/custom/sheet1.xml")
            target.writestr(name, data)
    result = parse(output.getvalue(), limits=PreviewLimits(max_row_index=7))
    assert "UNSUPPORTED_PACKAGE_LAYOUT" in codes(result)
    assert not result.structure_valid
    assert not result.rows


@pytest.mark.parametrize("replacement", [
    b'<c r="B7" t="n"><v>1</v></c><c r="B7" t="n"><v>99</v></c>',
    b'<c r="B8" t="n"><v>1</v></c>',
])
def test_duplicate_or_misaligned_cells_cannot_silently_replace_values(replacement):
    content = make_workbook([("A", 1)])
    content = replace_xml(content, "xl/worksheets/sheet1.xml", b'<c r="B7" t="n"><v>1</v></c>', replacement)
    result = parse(content)
    assert "INVALID_WORKSHEET_STRUCTURE" in codes(result)
    assert not result.structure_valid
    assert not result.rows



def test_referenced_sheet_with_false_relationship_type_is_rejected():
    content = make_workbook([("A", 1)])
    content = replace_xml(
        content, "xl/_rels/workbook.xml.rels",
        b"relationships/worksheet", b"relationships/unknown",
    )
    result = parse(content)
    assert "UNSUPPORTED_PACKAGE_LAYOUT" in codes(result)
    assert not result.rows


def test_formatting_only_cells_do_not_consume_data_budget_or_extend_preview():
    content = make_workbook([("A", 1)])
    content = replace_xml(content, 'xl/worksheets/sheet1.xml', b'</sheetData>',
                          b'<row r="100"><c r="ZZ100" s="0" t="n"></c></row></sheetData>')
    result = parse(content, limits=PreviewLimits(max_cells=4, max_columns=2))
    assert result.structure_valid
    assert [r.row_number for r in result.rows] == [7]
    assert result.blank_row_count == 0  # Only data rows count; formatting tail is excluded.
    assert 'CELL_LIMIT_EXCEEDED' in codes(parse(content, limits=PreviewLimits(max_xml_cells=4)))


def test_unselected_sheet_is_not_read_as_data_but_package_budget_still_applies():
    book = Workbook()
    selected = book.active
    selected.title = TEMPLATE.sheet_name
    selected.append([])
    selected['A5'], selected['B5'] = '批号', '检测值'
    selected['A7'], selected['B7'] = 'A', 1
    other = book.create_sheet('说明')
    other['ZZ100'] = 'outside selected data limits'
    output = BytesIO()
    book.save(output)
    content = output.getvalue()
    result = parse(content, limits=PreviewLimits(max_cells=4, max_columns=2, max_row_index=10))
    assert result.structure_valid
    assert 'UNSELECTED_SHEET' in codes(result)
    assert 'WORKBOOK_TOO_LARGE' in codes(parse(content, limits=PreviewLimits(max_unpacked_bytes=100)))


def test_optional_row_number_is_inferred_without_changing_cell_coordinates():
    content = make_workbook([('A', 1), ('B', 2)])
    content = replace_xml(content, 'xl/worksheets/sheet1.xml', b'<row r="8">', b'<row>')
    result = parse(content)
    assert result.structure_valid
    assert result.rows[1].cells[0].coordinate == 'A8'
    assert result.rows[1].cells[0].value == 'B'


def test_parse_deadline_returns_blocking_issue(monkeypatch):
    import app.services.imports.preview as module
    ticks = iter([0, 100])
    monkeypatch.setattr(module, 'monotonic', lambda: next(ticks))
    result = parse(make_workbook([('A', 1)]))
    assert 'PARSE_TIMEOUT' in codes(result)
    assert not result.structure_valid
    assert not result.can_commit
