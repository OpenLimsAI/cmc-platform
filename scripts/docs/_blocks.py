"""docx 单单元格表块识别与代码围栏渲染（被 extract_md.py 的 _post_process 调用）

为什么需要这一层：
  pandoc 把 docx 单单元格 <w:tbl>（作者常用作代码 / ASCII 框图 / 提示框）
  转成 HTML <p> 后，HTML 标准会压缩连续空格，丢失 ASCII 对齐与代码缩进。
  本模块从 docx XML 直接读取 xml:space="preserve" 原文，按内容性质重建为：
    - sql / json / http / python / tsx / yaml / ts：``` 语言代码块
    - ASCII 框图（≥3 个 box-drawing 字符）：```text 代码块
    - 中文 callout（💡 / ⚠ 等 emoji 起头）：> blockquote 引用块
    - 兜底（既非语言代码也非框图也非 callout）：```text 代码块

  多单元格 HTML 表（pandoc 因合并单元格 / 列宽指定从 GFM 回落产生的）
  保留 pandoc 输出不动。

输入 / 输出顺序保证：
  按文档顺序提取 docx 中所有"单单元格 <w:tbl>"，与 pandoc 输出中所有
  "单单元格 <table>" 一一对应（已在 4 份 V1_1 文档上验证 1:1 对齐）。
"""
from __future__ import annotations

import re
import zipfile
from html.parser import HTMLParser
from pathlib import Path
from xml.etree import ElementTree as ET

W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"


# ============================================================
# HTML <table> 块定位与解析
# ============================================================

class CellCollector(HTMLParser):
    """遍历一个 <table>…</table> blob，输出每个 cell 的文本行序列。
    <br/> 与 <p> 边界视为换行；inter-paragraph whitespace 不计入。
    """

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.cells: list[list[str]] = []
        self._in_cell = False
        self._in_block = False  # 是否在 <p> 内（或 cell 顶层文本）
        self._current: list[str] = []
        self._buf: list[str] = []
        self._row_cells_count: list[int] = []
        self._this_row_cells = 0

    def _flush_line(self) -> None:
        self._current.append("".join(self._buf))
        self._buf = []

    def handle_starttag(self, tag, attrs):
        if tag == "tr":
            self._this_row_cells = 0
            return
        if tag in ("td", "th"):
            self._in_cell = True
            self._in_block = True
            self._current = []
            self._buf = []
            return
        if not self._in_cell:
            return
        if tag == "br":
            self._flush_line()
        elif tag == "p":
            self._buf = []
            self._in_block = True

    def handle_endtag(self, tag):
        if tag == "tr":
            self._row_cells_count.append(self._this_row_cells)
            return
        if tag in ("td", "th"):
            if self._buf:
                self._flush_line()
            self.cells.append(self._current)
            self._current = []
            self._in_cell = False
            self._in_block = False
            self._this_row_cells += 1
            return
        if not self._in_cell:
            return
        if tag == "p":
            if self._buf:
                self._flush_line()
            self._in_block = False

    def handle_startendtag(self, tag, attrs):
        if tag == "br" and self._in_cell:
            self._flush_line()

    def handle_data(self, data):
        if self._in_cell and self._in_block:
            self._buf.append(data)


def find_html_tables(text: str) -> list[tuple[int, int, str]]:
    """返回 [(start, end_exclusive, html_blob), …]，覆盖所有顶层 <table>…</table>
    块。前提：pandoc 把 <table> 与 </table> 各自放在行首。"""
    blocks: list[tuple[int, int, str]] = []
    i = 0
    while True:
        s = text.find("\n<table", i)
        if s == -1:
            if i == 0 and text.startswith("<table"):
                s = 0
            else:
                break
        else:
            s += 1
        e = text.find("\n</table>", s)
        if e == -1:
            break
        e += len("\n</table>")
        blocks.append((s, e, text[s:e]))
        i = e
    return blocks


def is_single_cell_block(blob: str) -> bool:
    p = CellCollector()
    p.feed(blob)
    return len(p.cells) == 1 and (
        not p._row_cells_count or max(p._row_cells_count) == 1
    )


# ============================================================
# 语言分类（用于决定 ``` 后的 fence 标签）
# ============================================================

SQL_RE = re.compile(
    r"\b(CREATE\s+(?:OR\s+REPLACE\s+)?(?:TABLE|INDEX|UNIQUE\s+INDEX|VIEW|FUNCTION|TRIGGER|SCHEMA|EXTENSION|TYPE|SEQUENCE|MATERIALIZED\s+VIEW)|"
    r"ALTER\s+(?:TABLE|DATABASE|SCHEMA|SEQUENCE)|"
    r"DROP\s+(?:TABLE|INDEX|FUNCTION|TRIGGER|TYPE|VIEW)|"
    r"COMMENT\s+ON|"
    r"INSERT\s+INTO|"
    r"GRANT\s+\w+\s+ON|"
    r"REVOKE\s+\w+\s+ON|"
    r"CONSTRAINT\s+\w+\s+(?:PRIMARY|FOREIGN|UNIQUE|CHECK)|"
    r"REFERENCES\s+\w+)",
    re.IGNORECASE,
)
SELECT_FROM_RE = re.compile(r"\bSELECT\s+.+?\bFROM\b", re.IGNORECASE | re.DOTALL)

JSON_KV_RE = re.compile(r'"\w[\w-]*"\s*:\s*')
HTTP_ROUTE_RE = re.compile(
    r"^\s*(GET|POST|PUT|DELETE|PATCH|HEAD|OPTIONS)\s+/", re.MULTILINE
)
HTTP_REQ_LINE_RE = re.compile(
    r"^\s*(GET|POST|PUT|DELETE|PATCH|HEAD|OPTIONS)\s+\S+\s+HTTP/", re.MULTILINE
)
HTTP_RESP_LINE_RE = re.compile(r"^\s*HTTP/\d(?:\.\d)?\s+\d{3}\b", re.MULTILINE)
HTTP_HEADER_RE = re.compile(
    r"^(Content-Type|Authorization|Accept|Idempotency-Key|"
    r"X-[\w-]+|Retry-After|Location|ETag|If-Match|If-None-Match|"
    r"Sunset|Deprecation|Link|Cache-Control|Set-Cookie|Cookie):\s",
    re.MULTILINE,
)
YAML_OPENAPI_RE = re.compile(
    r"^\s*(openapi|paths|components|info|servers|tags)\s*:", re.MULTILINE
)
PY_IMPORT_RE = re.compile(r"^\s*(from\s+[\w.]+\s+import\s+|import\s+[\w.]+)", re.MULTILINE)
PY_DEF_RE = re.compile(r"^\s*(async\s+def|def|class)\s+\w+", re.MULTILINE)
TS_IMPORT_RE = re.compile(
    r"^\s*import\s+(?:\{[^}]+\}|\w+|\*\s+as\s+\w+)\s+from\s+['\"]", re.MULTILINE
)
JSX_TAG_RE = re.compile(r"</?[A-Z][\w.]*\b")
TS_KW_RE = re.compile(r"\b(const|let|interface|type|export|async)\b\s+\w+")
CALLOUT_LEAD_RE = re.compile(r"^\s*[💡⚠✓✗❗📌🔒🔑📋✅❌🎯]")
ASCII_BOX_RE = re.compile(r"[┌┐└┘├┤┬┴┼─│╭╮╯╰═║]")


def _is_prose_or_diagram(body: str) -> bool:
    """callout 与 ASCII 框图应避开语言探测（不应被误判为代码）"""
    if CALLOUT_LEAD_RE.search(body[:200]):
        return True
    if len(ASCII_BOX_RE.findall(body)) >= 3:
        return True
    return False


def classify_language(lines: list[str]) -> str | None:
    """返回语言标签 (sql/json/http/yaml/python/tsx/ts) 或 None。
    None 表示内容不像具体语言代码，调用方决定走 ASCII text fence / blockquote。"""
    body = "\n".join(lines).strip()
    if not body or _is_prose_or_diagram(body):
        return None

    if SQL_RE.search(body) or SELECT_FROM_RE.search(body):
        return "sql"

    stripped = body.lstrip()
    if stripped[:1] in "{[" and len(JSON_KV_RE.findall(body)) >= 2:
        return "json"
    if "{" in body and len(JSON_KV_RE.findall(body)) >= 3:
        return "json"

    if HTTP_REQ_LINE_RE.search(body) or HTTP_RESP_LINE_RE.search(body):
        return "http"
    if len(HTTP_HEADER_RE.findall(body)) >= 2:
        return "http"
    if len(HTTP_ROUTE_RE.findall(body)) >= 1:
        return "http"

    if YAML_OPENAPI_RE.search(body):
        return "yaml"

    if body.lstrip().startswith("<") and JSX_TAG_RE.search(body):
        if "/>" in body or re.search(r"</[A-Z]\w*>", body):
            return "tsx"
    if len(JSX_TAG_RE.findall(body)) >= 2 and TS_KW_RE.search(body):
        return "tsx"
    if TS_IMPORT_RE.search(body) and (
        JSX_TAG_RE.search(body) or "interface " in body or "type " in body
    ):
        return "tsx" if JSX_TAG_RE.search(body) else "ts"
    if len(TS_IMPORT_RE.findall(body)) >= 2:
        return "ts"

    if len(PY_IMPORT_RE.findall(body)) >= 2:
        return "python"
    if PY_IMPORT_RE.search(body) and PY_DEF_RE.search(body):
        return "python"

    return None


def render_block(lines: list[str]) -> tuple[str, str]:
    """决定怎么渲染恢复后的 docx 段落。返回 (kind, rendered_text)。
    kind 取值：fence:<lang> / blockquote。"""
    body = "\n".join(lines).strip()
    if not body:
        return ("blockquote", "")  # 不可能落到这里：上层做了 trim

    lang = classify_language(lines)
    if lang is not None:
        return (f"fence:{lang}", f"```{lang}\n" + "\n".join(lines) + "\n```")

    if len(ASCII_BOX_RE.findall(body)) >= 3:
        return ("fence:text", "```text\n" + "\n".join(lines) + "\n```")

    if CALLOUT_LEAD_RE.search(body[:200]):
        quoted = "\n".join(
            (">" if not ln.strip() else "> " + ln) for ln in lines
        )
        return ("blockquote", quoted)

    # 兜底：作者用单单元格表对内容做视觉分组，保留为 text fence
    return ("fence:text", "```text\n" + "\n".join(lines) + "\n```")


# ============================================================
# docx 原文提取
# ============================================================

def extract_docx_single_cell_tables(docx_path: Path) -> list[list[str]]:
    """按文档顺序返回所有单单元格 <w:tbl> 的段落文本（保留 xml:space 空格）。
    每个表 → 一份行列表，已 strip 头尾空行。"""
    with zipfile.ZipFile(docx_path) as z:
        with z.open("word/document.xml") as fp:
            tree = ET.parse(fp)
    root = tree.getroot()
    result: list[list[str]] = []
    for tbl in root.iter(f"{W}tbl"):
        rows = tbl.findall(f"{W}tr")
        if len(rows) != 1:
            continue
        cells = rows[0].findall(f"{W}tc")
        if len(cells) != 1:
            continue
        lines: list[str] = []
        for p in cells[0].findall(f".//{W}p"):
            text = "".join((t.text or "") for t in p.iter(f"{W}t"))
            lines.append(text)
        while lines and not lines[0].strip():
            lines.pop(0)
        while lines and not lines[-1].strip():
            lines.pop()
        result.append(lines)
    return result


# ============================================================
# 主入口：在 pandoc 输出的 md 文本中，用 docx 原文替换所有单单元格表
# ============================================================

def restore_blocks_from_docx(md_text: str, docx_path: Path) -> tuple[str, dict]:
    """用 docx XML 原文重建 md 中所有单单元格 <table> 为代码围栏 / 引用块。
    多单元格 HTML 表保留不动。返回 (新文本, 统计)。"""
    docx_cells = extract_docx_single_cell_tables(docx_path)
    docx_iter = iter(docx_cells)
    blocks = find_html_tables(md_text)
    out_parts: list[str] = []
    cursor = 0
    stats: dict = {"total": len(blocks), "replaced": 0, "kept_html": 0, "by_kind": {}}
    for start, end, blob in blocks:
        out_parts.append(md_text[cursor:start])
        cursor = end
        if not is_single_cell_block(blob):
            out_parts.append(blob)
            stats["kept_html"] += 1
            continue
        try:
            lines = next(docx_iter)
        except StopIteration:
            out_parts.append(blob)
            stats["kept_html"] += 1  # 走兜底：docx 与 md 块数不一致
            continue
        kind, rendered = render_block(lines)
        out_parts.append(rendered)
        stats["replaced"] += 1
        stats["by_kind"][kind] = stats["by_kind"].get(kind, 0) + 1
    out_parts.append(md_text[cursor:])
    return "".join(out_parts), stats
