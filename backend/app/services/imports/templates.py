"""预览用模板登记；不等于已批准的业务导入模板或字典映射。"""
from io import BytesIO

from openpyxl import Workbook
from openpyxl.comments import Comment
from openpyxl.styles import Font

from app.services.imports.preview import ColumnBinding, WorkbookTemplate

LONG_PREVIEW_TEMPLATE = WorkbookTemplate(
    template_code="qap_long_preview_v1",
    version="1",
    sheet_name="质量数据",
    header_row=1,
    data_start_row=2,
    columns=(
        ColumnBinding("source_project_ref", "project_code"),
        ColumnBinding("batch_number", "batch_number", required=True),
        ColumnBinding("source_attribute", "attribute", required=True),
        ColumnBinding("value_raw", "value", required=True),
        ColumnBinding("source_unit", "unit"),
    ),
)
FIRST_TABLE_LABELS = (
    "请验日期", "组别", "生产线代码", "项目代码", "样品类别", "原批号",
    "检验类别", "放置状态", "时间节点", "单位(次/小时/天/月/年)",
)
FIRST_TABLE_TEMPLATE = WorkbookTemplate(
    template_code="qap_first_table_v1", version="1", label="项目第一表（现有 Excel 结构）",
    sheet_name="原始数据表", header_row=5, label_row=6, data_start_row=7,
    unmapped_columns_warning=True,
    columns=tuple(ColumnBinding(name, name, required=name in {"project_id", "batch_number"}) for name in (
        "sample_submission_date", "group_id", "production_line_id", "project_id", "sample_type",
        "batch_number", "test_type", "placement_status", "timepoint", "timepoint_unit",
    )),
)
# 现有第一表是默认入口；五列草案仅保留显式兼容，不覆盖第一表契约。
TEMPLATES = {template.template_code: template for template in (FIRST_TABLE_TEMPLATE, LONG_PREVIEW_TEMPLATE)}


def template_workbook(template: WorkbookTemplate) -> bytes:
    """生成空白结构样例；不填业务规格、测量值、批准信息或身份。"""
    workbook = Workbook()
    try:
        sheet = workbook.active
        sheet.title = template.sheet_name
        for index, column in enumerate(template.columns, 1):
            sheet.cell(template.header_row, index, column.source_header)
        if template.template_code == FIRST_TABLE_TEMPLATE.template_code:
            sheet.cell(1, 1, "项目第一表结构示例：保留原文件，第5行英文、第6行中文、第7行起为数据。")
            sheet.cell(2, 1, "前十列为业务维度，不是数据库主键；K列起可保留原检测项列，映射待核对。")
            for index, label in enumerate(FIRST_TABLE_LABELS, 1):
                sheet.cell(template.label_row, index, label)
        instructions = (
            "项目源编码。此模板仅作结构预览，项目对应关系尚需业务校验。",
            "公司既有批号；请用文本填写，保留前导零，禁止重新编造或截断。",
            "来源检测项原名；此处不表示已匹配正式检测项。",
            "原始检测结果，保留数值、限定符或定性文本；不在模板里自动换算。",
            "来源单位原文；空值不表示无量纲，正式导入前仍需确认。",
        )
        if template.template_code == FIRST_TABLE_TEMPLATE.template_code:
            instructions = tuple("原Excel字段：" + name + "。保留原值，不自动转换编码、单位或批准状态。" for name in FIRST_TABLE_LABELS)
        for index, explanation in enumerate(instructions, 1):
            cell = sheet.cell(template.header_row, index)
            cell.font = Font(bold=True)
            cell.comment = Comment(explanation, "QAP")
            sheet.column_dimensions[cell.column_letter].width = 26
        sheet.freeze_panes = f"A{template.data_start_row}"
        workbook.properties.title = "QAP 结构预览空白模板（非业务批准模板）"
        output = BytesIO()
        workbook.save(output)
        return output.getvalue()
    finally:
        workbook.close()
