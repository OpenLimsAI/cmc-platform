"""按显式模板读取 XLSX 原始单元格，保留问题行，不执行业务换算或写库。

不依赖数据库、认证设置或旧导入服务；结构校验通过也不允许发布。
模板由调用方显式提供，不从文件名、关键词或首个 sheet 猜测业务口径。
"""
from __future__ import annotations

from contextlib import ExitStack
from dataclasses import dataclass, field
from hashlib import sha256
from io import BytesIO
import math
import posixpath
import re
from typing import Any, Literal
from time import monotonic
from zipfile import BadZipFile, ZipFile

from defusedxml.ElementTree import fromstring, iterparse
from openpyxl import load_workbook
from openpyxl.utils.cell import coordinate_to_tuple, get_column_letter


@dataclass(frozen=True)
class ColumnBinding:
    field_name: str
    source_header: str
    required: bool = False


@dataclass(frozen=True)
class WorkbookTemplate:
    template_code: str
    version: str
    sheet_name: str
    header_row: int
    data_start_row: int
    columns: tuple[ColumnBinding, ...]
    label_row: int | None = None
    unmapped_columns_warning: bool = False
    label: str = "通用长表（结构预览）"

    def __post_init__(self) -> None:
        if not all((self.template_code, self.version, self.sheet_name)):
            raise ValueError("模板编号、版本与工作表名称必须明确")
        if self.header_row < 1 or self.data_start_row <= self.header_row:
            raise ValueError("数据起始行必须位于表头之后")
        if self.label_row is not None and not self.header_row < self.label_row < self.data_start_row:
            raise ValueError("中文表头行必须位于英文表头与数据之间")
        fields = [c.field_name for c in self.columns]
        headers = [c.source_header for c in self.columns]
        if any(not re.fullmatch(r"[a-z][a-z0-9_]*", f) for f in fields):
            raise ValueError("标准字段名必须为 snake_case")
        if len(set(fields)) != len(fields) or len(set(headers)) != len(headers):
            raise ValueError("模板字段和来源表头必须一一对应")
        if any(not h or h.strip() != h for h in headers):
            raise ValueError("模板表头不能为空或含首尾空格")
        if "batch_number" not in fields or "batch_id" in fields:
            raise ValueError("模板必须使用 batch_number，不得增加同义 batch_id")


@dataclass(frozen=True)
class PreviewLimits:
    max_file_bytes: int = 10 * 1024 * 1024
    max_unpacked_bytes: int = 128 * 1024 * 1024
    max_zip_entries: int = 1000
    max_row_index: int = 50_000
    max_columns: int = 256
    max_cells: int = 200_000
    max_xml_cells: int = 3_000_000
    max_parse_seconds: int = 60

    def __post_init__(self) -> None:
        if any(value < 1 for value in vars(self).values()):
            raise ValueError("解析资源限制必须为正数")


@dataclass(frozen=True)
class ValidationIssue:
    code: str
    message: str
    severity: Literal["error", "warning"] = "error"
    sheet_name: str | None = None
    row_number: int | None = None
    column_name: str | None = None
    coordinate: str | None = None


@dataclass(frozen=True)
class SourceCell:
    coordinate: str
    field_name: str | None
    source_header: str | None
    value: Any
    data_type: str
    number_format: str
    cached_value: Any = None


@dataclass(frozen=True)
class SourceRow:
    row_number: int
    cells: tuple[SourceCell, ...]


@dataclass(frozen=True)
class PreviewColumn:
    column_index: int
    source_header: str | None
    source_label: str | None
    field_name: str | None


@dataclass(frozen=True)
class WorkbookPreview:
    original_filename: str
    file_sha256: str
    byte_size: int
    template_code: str
    template_version: str
    sheet_name: str
    rows: tuple[SourceRow, ...]
    issues: tuple[ValidationIssue, ...]
    blank_row_count: int = 0
    columns: tuple[PreviewColumn, ...] = ()
    parser_version: str = field(default="xlsx_structure_v2", init=False)
    business_validation: Literal["pending"] = field(default="pending", init=False)
    can_commit: Literal[False] = field(default=False, init=False)

    @property
    def structure_valid(self) -> bool:
        return not any(issue.severity == "error" for issue in self.issues)


class _RejectedWorkbook(Exception):
    def __init__(self, code: str, message: str):
        self.code = code
        self.message = message
        super().__init__(message)


def _inspect_package(content: bytes, limits: PreviewLimits, sheet_name: str, deadline: float) -> tuple[int, int]:
    """先检查实际 XML 坐标/单元格数，不信任可能错误的 dimension 声明。"""
    with ZipFile(BytesIO(content)) as archive:
        entries = archive.infolist()
        names = [entry.filename for entry in entries]
        if len(entries) > limits.max_zip_entries or sum(e.file_size for e in entries) > limits.max_unpacked_bytes:
            raise _RejectedWorkbook("WORKBOOK_TOO_LARGE", "工作簿解压大小或条目数超过限制")
        if len(names) != len(set(names)) or any(e.flag_bits & 1 for e in entries):
            raise _RejectedWorkbook("INVALID_PACKAGE", "不支持重复文件条目或加密工作簿")
        content_types = archive.read("[Content_Types].xml")
        if b"macroEnabled" in content_types or any("vbaproject" in n.lower() for n in names):
            raise _RejectedWorkbook("MACRO_NOT_SUPPORTED", "当前只支持不含宏的 XLSX 文件")
        if any(n.startswith("xl/externalLinks/") for n in names):
            raise _RejectedWorkbook("EXTERNAL_LINK_NOT_SUPPORTED", "外部工作簿引用需先转为可核对的原始数据")
        # openpyxl 按关系文件加载工作表，不能只检查惯用目录后默许其他路径。
        types = fromstring(content_types)
        workbook_parts = [
            node.attrib.get("PartName") for node in types
            if node.attrib.get("ContentType", "").endswith("spreadsheetml.sheet.main+xml")
        ]
        if workbook_parts != ["/xl/workbook.xml"]:
            raise _RejectedWorkbook("UNSUPPORTED_PACKAGE_LAYOUT", "当前预览只支持标准 XLSX 工作簿路径")
        relationships = fromstring(archive.read("xl/_rels/workbook.xml.rels"))
        by_id = {node.attrib["Id"]: node for node in relationships}
        if len(by_id) != len(relationships):
            raise _RejectedWorkbook("INVALID_PACKAGE", "工作簿关系标识重复")
        definition = fromstring(archive.read("xl/workbook.xml"))
        namespace = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
        relation_id = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id"
        sheet_names: set[str] = set()
        used_relationships: set[str] = set()
        selected_path = None
        # 检查被 workbook 真正引用的关系，不因伪造 Type 而漏检目标。
        for node in definition.findall(f"{namespace}sheets/{namespace}sheet"):
            name, reference = node.attrib["name"], node.attrib[relation_id]
            relationship = by_id[reference]
            if name in sheet_names or reference in used_relationships:
                raise _RejectedWorkbook("INVALID_PACKAGE", "工作表名称或关系引用重复")
            sheet_names.add(name)
            used_relationships.add(reference)
            if not relationship.attrib.get("Type", "").endswith("/worksheet"):
                raise _RejectedWorkbook("UNSUPPORTED_PACKAGE_LAYOUT", "当前仅支持普通数据工作表")
            target = relationship.attrib.get("Target", "")
            resolved = posixpath.normpath(target.lstrip("/") if target.startswith("/") else "xl/" + target)
            if (relationship.attrib.get("TargetMode") == "External"
                    or not re.fullmatch(r"xl/worksheets/[^/]+\.xml", resolved)
                    or resolved not in names):
                raise _RejectedWorkbook("UNSUPPORTED_PACKAGE_LAYOUT", "工作表引用不在受支持的包内路径，无法完整校验")
            if name == sheet_name:
                selected_path = resolved
        if selected_path is None:
            raise _RejectedWorkbook("SHEET_MISSING", "找不到模板指定的工作表；不会自动改选其他工作表")
        # 其他页不作为数据读入；整个包仍受总解压大小/条目数限制。
        # 有值或公式的单元格计入业务限制，纯格式单元格只计入 XML 扫描上限。
        cell_count, xml_cells, max_column, max_row = 0, 0, 1, 1
        with archive.open(selected_path) as stream:
            current_row, previous_row, previous_column = None, 0, 0
            sheet_data = None
            for event, element in iterparse(stream, events=("start", "end")):
                if monotonic() > deadline:
                    raise _RejectedWorkbook("PARSE_TIMEOUT", "工作簿解析超过时间限制")
                tag = element.tag.rsplit("}", 1)[-1]
                if event == "start" and tag == "sheetData":
                    sheet_data = element
                if event == "start" and tag == "row":
                    # OOXML 允许省略 r，此时与 openpyxl 一致按上一行顺延。
                    current_row = int(element.attrib.get("r", str(previous_row + 1)))
                    if current_row <= previous_row:
                        raise _RejectedWorkbook("INVALID_WORKSHEET_STRUCTURE", "工作表含重复或倒序行号")
                    if current_row > limits.max_row_index:
                        raise _RejectedWorkbook("ROW_LIMIT_EXCEEDED", "工作表行号超过预览限制")
                    previous_row, previous_column = current_row, 0
                if event == "end" and tag == "c":
                    row, column = coordinate_to_tuple(element.attrib["r"])
                    if row != current_row or column <= previous_column:
                        raise _RejectedWorkbook("INVALID_WORKSHEET_STRUCTURE", "单元格坐标重复、倒序或与行号不一致")
                    previous_column = column
                    xml_cells += 1
                    if xml_cells > limits.max_xml_cells:
                        raise _RejectedWorkbook("CELL_LIMIT_EXCEEDED", "工作表 XML 单元格数超过扫描限制")
                    meaningful = any(child.tag.rsplit("}", 1)[-1] in {"v", "f", "is"} for child in element)
                    if meaningful:
                        cell_count += 1
                        max_column, max_row = max(max_column, column), max(max_row, row)
                        if row > limits.max_row_index or column > limits.max_columns or cell_count > limits.max_cells:
                            raise _RejectedWorkbook("CELL_LIMIT_EXCEEDED", "工作表有效单元格数或位置超过预览限制")
                    element.clear()
                if event == "end" and tag == "row":
                    current_row = None
                    element.clear()
                    if sheet_data is not None:
                        sheet_data.clear()
        return max_column, max_row


def _blank(value: Any) -> bool:
    return value is None or (isinstance(value, str) and not value.strip())


def preview_workbook(
    content: bytes,
    *,
    filename: str,
    template: WorkbookTemplate,
    limits: PreviewLimits = PreviewLimits(),
) -> WorkbookPreview:
    """输入字节、输出原始行和问题；不保存文件，不连接数据库，不授予导入资格。"""
    issues: list[ValidationIssue] = []
    rows: list[SourceRow] = []
    blank_rows = 0
    headers: dict[int, str] = {}
    labels: dict[int, str] = {}
    matched: dict[int, ColumnBinding] = {}

    def finish() -> WorkbookPreview:
        return WorkbookPreview(
            original_filename=filename, file_sha256=sha256(content).hexdigest(), byte_size=len(content),
            template_code=template.template_code, template_version=template.version,
            sheet_name=template.sheet_name, rows=tuple(rows), issues=tuple(issues), blank_row_count=blank_rows,
            columns=tuple(PreviewColumn(col, headers.get(col), labels.get(col), matched[col].field_name if col in matched else None)
                          for col in sorted(set(headers) | set(labels))),
        )

    def issue(code: str, message: str, row: int | None = None, col: int | None = None,
              severity: Literal["error", "warning"] = "error", header: str | None = None) -> None:
        issues.append(ValidationIssue(
            code, message, severity, template.sheet_name, row, header,
            f"{get_column_letter(col)}{row}" if col is not None and row is not None else None,
        ))

    if not filename.lower().endswith(".xlsx") or "/" in filename or "\\" in filename:
        issue("UNSUPPORTED_FILE", "请提供不含路径的 .xlsx 文件名")
        return finish()
    if not content or len(content) > limits.max_file_bytes:
        issue("INVALID_FILE_SIZE", "文件为空或超过预览大小限制")
        return finish()
    if template.data_start_row > limits.max_row_index:
        issue("TEMPLATE_OUT_OF_RANGE", "模板起始行超过预览限制")
        return finish()
    try:
        deadline = monotonic() + limits.max_parse_seconds
        max_column, max_row = _inspect_package(content, limits, template.sheet_name, deadline)
        with ExitStack() as stack:
            workbook = load_workbook(BytesIO(content), read_only=True, data_only=False, keep_links=False)
            stack.callback(workbook.close)
            cached = load_workbook(BytesIO(content), read_only=True, data_only=True, keep_links=False)
            stack.callback(cached.close)
            if template.sheet_name not in workbook.sheetnames:
                issue("SHEET_MISSING", "找不到模板指定的工作表；不会自动改选其他工作表")
                return finish()
            for name in workbook.sheetnames:
                if name != template.sheet_name:
                    issues.append(ValidationIssue("UNSELECTED_SHEET", "该工作表未按本模板解析", "warning", name))
            sheet, cached_sheet = workbook[template.sheet_name], cached[template.sheet_name]
            if sheet.sheet_state != "visible":
                issue("HIDDEN_SHEET", "模板指定的工作表处于隐藏状态", severity="warning")
            sheet.reset_dimensions()
            cached_sheet.reset_dimensions()
            bindings = {c.source_header: c for c in template.columns}
            seen_headers: set[str] = set()
            preview_cells = 0
            for row_index, (source_row, cached_row) in enumerate(zip(
                sheet.iter_rows(max_col=max_column, max_row=max_row), cached_sheet.iter_rows(max_col=max_column, max_row=max_row), strict=True,
            ), start=1):
                if monotonic() > deadline:
                    raise _RejectedWorkbook("PARSE_TIMEOUT", "工作簿解析超过时间限制")
                if row_index > limits.max_row_index:
                    raise _RejectedWorkbook("ROW_LIMIT_EXCEEDED", "实际解析行号超过预览限制")
                if row_index == template.header_row:
                    for col, cell in enumerate(source_row, start=1):
                        if _blank(cell.value):
                            continue
                        if not isinstance(cell.value, str) or cell.data_type in {"f", "e"}:
                            issue("INVALID_HEADER", "表头必须是明确的文本", row_index, col)
                            continue
                        header = cell.value.strip()
                        headers[col] = cell.value
                        if header in seen_headers:
                            issue("DUPLICATE_HEADER", "存在重复表头，不能合并或覆盖列", row_index, col, header=cell.value)
                        seen_headers.add(header)
                        if header in bindings:
                            matched[col] = bindings[header]
                        else:
                            issue("UNMAPPED_COLUMN", "此列尚未完成检测项/字段映射；原值保留，不自动导入", row_index, col,
                                  severity="warning" if template.unmapped_columns_warning else "error", header=cell.value)
                    for binding in template.columns:
                        if binding.source_header not in seen_headers:
                            issue("MISSING_COLUMN", f"缺少模板列：{binding.source_header}", row_index)
                if row_index == template.label_row:
                    for col, cell in enumerate(source_row, start=1):
                        if not _blank(cell.value):
                            labels[col] = str(cell.value)
                if row_index < template.data_start_row:
                    continue
                if all(_blank(cell.value) for cell in source_row):
                    blank_rows += 1
                    continue
                parsed: list[SourceCell] = []
                for col, (cell, cached_cell) in enumerate(zip(source_row, cached_row, strict=True), start=1):
                    binding = matched.get(col)
                    if cell.value is None and binding is None:
                        continue
                    coordinate = f"{get_column_letter(col)}{row_index}"
                    parsed.append(SourceCell(
                        coordinate, binding.field_name if binding else None, headers.get(col), cell.value,
                        cell.data_type, cell.number_format, cached_cell.value if cell.data_type == "f" else None,
                    ))
                    if col not in headers and not _blank(cell.value):
                        issue("UNNAMED_COLUMN", "有值的列没有可识别表头", row_index, col)
                    if cell.data_type == "f":
                        issue("FORMULA_REQUIRES_REVIEW", "公式及缓存值已保留，不能当作已核实结果", row_index, col)
                    elif cell.data_type == "e":
                        issue("EXCEL_CELL_ERROR", "单元格包含 Excel 错误", row_index, col)
                    if isinstance(cell.value, float) and not math.isfinite(cell.value):
                        issue("NON_FINITE_VALUE", "数值必须是有限值", row_index, col)
                    if binding and (binding.required or binding.field_name == "batch_number") and _blank(cell.value):
                        issue("REQUIRED_VALUE_MISSING", f"缺少 {binding.field_name}", row_index, col)
                    if binding and binding.field_name == "batch_number" and not _blank(cell.value):
                        if not isinstance(cell.value, str) or cell.data_type == "f":
                            issue("BATCH_MUST_BE_TEXT", "批号必须以文本提供，不能猜测前导零或计算公式", row_index, col)
                        elif len(cell.value) > 32:
                            issue("BATCH_TOO_LONG", "批号超过32字符，已保留原值且不会截断", row_index, col)
                        elif cell.value != cell.value.strip():
                            issue("BATCH_WHITESPACE", "批号含首尾空格，需核对；不会自动修改原值", row_index, col)
                    if binding and binding.field_name == "project_id" and not _blank(cell.value):
                        if not isinstance(cell.value, str) or cell.data_type == "f":
                            issue("PROJECT_MUST_BE_TEXT", "项目代码必须为文本，不能推测前导零或项目对应关系", row_index, col)
                        elif cell.value != cell.value.strip():
                            issue("PROJECT_WHITESPACE", "项目代码含首尾空格，保留原值待核对", row_index, col)
                preview_cells += len(parsed)
                if preview_cells > limits.max_cells:
                    raise _RejectedWorkbook("PREVIEW_TOO_LARGE", "含必填空格的预览单元格数超过限制")
                rows.append(SourceRow(row_index, tuple(parsed)))
            if not seen_headers:
                issue("HEADER_MISSING", "指定行没有有效表头")
            if not rows:
                issue("NO_DATA_ROWS", "指定工作表没有可预览的数据行")
    except _RejectedWorkbook as exc:
        issue(exc.code, exc.message)
    except (BadZipFile, KeyError, ValueError, TypeError, OSError):
        issue("WORKBOOK_UNREADABLE", "工作簿内容不完整或无法解析，请核对源文件")
    except Exception:
        # 包括 XML 实体/语法拒绝、损坏公式等，不泄露内部异常或静默跳行。
        issue("WORKBOOK_UNREADABLE", "工作簿解析失败，未获得完整校验结果")
    return finish()
