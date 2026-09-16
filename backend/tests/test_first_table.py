"""项目第一表原始维度契约；全部使用合成工作簿，不写业务库。"""
from io import BytesIO

import pytest
from openpyxl import Workbook, load_workbook

from app.services.imports.preview import preview_workbook
from app.services.imports.templates import FIRST_TABLE_TEMPLATE, FIRST_TABLE_LABELS, template_workbook


def fixture(project="CMAB009", reorder=False):
    names = [column.source_header for column in FIRST_TABLE_TEMPLATE.columns]
    labels = list(FIRST_TABLE_LABELS)
    values = [None, "IH", "FF1", project, "制剂", "0001-A", "振荡试验", "正置", 0, "天"]
    if reorder:
        names[0], names[3] = names[3], names[0]
        labels[0], labels[3] = labels[3], labels[0]
        values[0], values[3] = values[3], values[0]
    book = Workbook()
    sheet = book.active
    sheet.title = "原始数据表"
    for row, data in ((5, names + ["sec_monomer_pct", "peptide_map_chart"]),
                      (6, labels + ["SEC单体(％)", "肽图(图谱)"]),
                      (7, values + [0.985, "一致"]), (8, values + [0.985, "<LOD"])):
        for col, value in enumerate(data, 1):
            sheet.cell(row, col, value)
    sheet["K7"].number_format = "0.0%"
    out = BytesIO()
    book.save(out)
    book.close()
    return out.getvalue()


@pytest.mark.parametrize("reorder", [False, True])
def test_first_table_preserves_dimensions_and_all_result_cells(reorder):
    result = preview_workbook(fixture(reorder=reorder), filename="合成.xlsx", template=FIRST_TABLE_TEMPLATE)
    assert result.structure_valid and not result.can_commit
    assert len(result.rows) == 2  # 重复维度不得当重复主键丢弃
    dimensions = {c.field_name: c.value for c in result.rows[0].cells if c.field_name}
    assert dimensions == dict(sample_submission_date=None, group_id="IH", production_line_id="FF1", project_id="CMAB009",
                              sample_type="制剂", batch_number="0001-A", test_type="振荡试验", placement_status="正置",
                              timepoint=0, timepoint_unit="天")
    assert result.rows[0].cells[-2].value == 0.985
    assert result.rows[0].cells[-2].number_format == "0.0%"
    assert [r.cells[-1].value for r in result.rows] == ["一致", "<LOD"]
    assert result.columns[-2].source_label == "SEC单体(％)"
    assert result.columns[-2].source_header == "sec_monomer_pct"
    assert result.columns[-2].field_name is None  # 未批准映射，不捏造正式检测项
    assert {issue.code for issue in result.issues} == {"UNMAPPED_COLUMN"}
    assert all(issue.severity == "warning" for issue in result.issues)


@pytest.mark.parametrize("project,issue", [(7, "PROJECT_MUST_BE_TEXT"), (None, "REQUIRED_VALUE_MISSING"), (" CMAB009 ", "PROJECT_WHITESPACE")])
def test_project_identity_is_not_padded_rewritten_or_guessed(project, issue):
    result = preview_workbook(fixture(project), filename="合成.xlsx", template=FIRST_TABLE_TEMPLATE)
    assert not result.structure_valid
    assert issue in {i.code for i in result.issues}
    assert next(c for c in result.rows[0].cells if c.field_name == "project_id").value == project


def test_downloaded_first_table_has_original_layout_without_business_rows():
    content = template_workbook(FIRST_TABLE_TEMPLATE)
    with BytesIO(content) as stream:
        book = load_workbook(stream)
        sheet = book["原始数据表"]
        assert sheet["D5"].value == "project_id"
        assert sheet["D6"].value == "项目代码"
        assert sheet["H5"].value == "placement_status"
        assert sheet["J5"].value == "timepoint_unit"
        assert sheet.max_row == 6
        book.close()
