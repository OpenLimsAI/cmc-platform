"""
文件: template/generate_template.py
用途: 用 openpyxl 生成 `物料导入模板.xlsx`
运行:
    cd template
    python generate_template.py
产出:
    template/物料导入模板.xlsx
说明:
    - 表头与导入解析器的 HEADER_MAP 对应:分类、代码、物料名称、级别、生产商、
      规格/型号、货号、单位、包装规格、备注
    - 序号 列只是给操作者参考,导入时会被忽略
    - 代码 列设置为文本格式,避免 Excel 自动去前导 0
"""
from __future__ import annotations

from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill, Border, Side
from openpyxl.utils import get_column_letter
from openpyxl.comments import Comment


HEADERS = [
    "序号", "分类", "代码", "物料名称", "级别", "生产商",
    "规格/型号", "货号", "单位", "包装规格", "备注",
]

# 字段说明(表头注释)
HEADER_COMMENTS = {
    "分类": "如:一般耗材 / 关键试剂 / 标准品 等",
    "代码": "公司物料代码(必填,纯数字时务必保留前导 0,以文本格式填写)",
    "物料名称": "中文名称(必填)",
    "级别": "可填:N/A / 分析纯 / 优级纯 等",
    "生产商": "供应商或品牌",
    "规格/型号": "如 50*33mm / 500g 等",
    "货号": "供应商货号",
    "单位": "必填,需在系统单位字典中(支/瓶/g/mL/盒/包等)",
    "包装规格": "如 100片/盒",
    "备注": "其他说明",
}

SAMPLE_ROWS = [
    [1, "一般耗材",   "42001", "PVC封膜(透明)",     "N/A", "N/A", "50*33mm",        "N/A", "张", "",        "N/A"],
    [2, "一般耗材",   "04123", "EP管 1.5mL",         "N/A", "Axygen", "1.5mL",      "MCT-150-C", "支", "500支/包", "保留前导 0 示例"],
    [3, "关键试剂",   "10567", "Tris-HCl",           "分析纯", "Sangon", "1mol/L pH8.0", "T1052", "mL", "100mL/瓶", "4℃保存"],
    [4, "标准品",     "20098", "牛血清白蛋白 BSA",   "≥98%",  "Sigma",  "冻干粉",       "A2153", "g", "5g/瓶",    "-20℃保存"],
]


def main() -> None:
    out_path = Path(__file__).parent / "物料导入模板.xlsx"

    wb = Workbook()
    ws = wb.active
    ws.title = "物料导入"

    # 表头
    header_fill = PatternFill("solid", fgColor="305496")
    header_font = Font(bold=True, color="FFFFFF", size=11)
    align_center = Alignment(horizontal="center", vertical="center", wrap_text=True)
    thin = Side(style="thin", color="999999")
    border = Border(left=thin, right=thin, top=thin, bottom=thin)

    for col_idx, h in enumerate(HEADERS, start=1):
        cell = ws.cell(row=1, column=col_idx, value=h)
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = align_center
        cell.border = border
        if h in HEADER_COMMENTS:
            cell.comment = Comment(HEADER_COMMENTS[h], "system")

    # 示例行
    for r_idx, row in enumerate(SAMPLE_ROWS, start=2):
        for c_idx, v in enumerate(row, start=1):
            cell = ws.cell(row=r_idx, column=c_idx, value=v)
            cell.alignment = Alignment(horizontal="left", vertical="center")
            cell.border = border

    # 把 "代码" 列(第3列)整列设为文本格式,保留前导 0
    code_col_letter = get_column_letter(HEADERS.index("代码") + 1)
    for cell in ws[code_col_letter]:
        cell.number_format = "@"

    # 列宽
    widths = {
        "序号": 6, "分类": 12, "代码": 14, "物料名称": 24, "级别": 12,
        "生产商": 16, "规格/型号": 18, "货号": 14, "单位": 8,
        "包装规格": 14, "备注": 28,
    }
    for col_idx, h in enumerate(HEADERS, start=1):
        ws.column_dimensions[get_column_letter(col_idx)].width = widths.get(h, 14)
    ws.row_dimensions[1].height = 26

    # 冻结表头
    ws.freeze_panes = "A2"

    # 第二个 sheet: 字段说明
    ws2 = wb.create_sheet("字段说明")
    ws2.append(["字段", "是否必填", "说明"])
    rules = [
        ("序号",     "否", "仅供阅读,导入时忽略"),
        ("分类",     "建议", "新分类导入时会自动加入字典"),
        ("代码",     "必填", "保留前导 0;请将该列保存为文本格式"),
        ("物料名称", "必填", "中文名称"),
        ("级别",     "否", "N/A 视为空"),
        ("生产商",   "否", ""),
        ("规格/型号","否", ""),
        ("货号",     "否", ""),
        ("单位",     "必填", "需在系统单位字典中(支/瓶/g/mL等);新单位可在导入时勾选自动加入"),
        ("包装规格", "否", ""),
        ("备注",     "否", ""),
    ]
    for r in rules:
        ws2.append(list(r))
    for col_idx, w in enumerate([14, 10, 60], start=1):
        ws2.column_dimensions[get_column_letter(col_idx)].width = w

    # 表头样式
    for c in ws2[1]:
        c.fill = header_fill
        c.font = header_font
        c.alignment = align_center

    wb.save(out_path)
    print(f"模板已生成: {out_path}")


if __name__ == "__main__":
    main()
