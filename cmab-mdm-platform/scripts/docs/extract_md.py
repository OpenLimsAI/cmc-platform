#!/usr/bin/env python3
"""
docx → markdown 自动派生工具（双轨文档同步基础设施）

用途：在 GxP 文档控制中，docx 是签字定稿的源头（保留 Word 修订模式追踪），
markdown 是 docx 的机器可读副本。本脚本用 pandoc 从 docx 提取 markdown，
后处理去除 pandoc 噪音（attribute id、空表格等）。

模式：
- 有本地 pandoc → 直接用（快）
- 否则 → 用 docker pandoc/core:3.1（无需本地安装）

manifest（哪些 docx 派生 markdown）：
- 仅当前有效版本（如 V1.1）；已签字归档的历史版本（V1.0）不再派生。
- 派生关系按 docx 文件命名约定推断：<name>.docx → <name>.md。

用法：
  python3 scripts/docs/extract_md.py                 # 提取全部
  python3 scripts/docs/extract_md.py <docx-path>     # 提取单个
  python3 scripts/docs/extract_md.py --check         # 输出到 .tmp/ 不覆盖（CI 用）
"""
from __future__ import annotations

import argparse
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
DOCS_DIR = REPO_ROOT / "docs"

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _blocks import restore_blocks_from_docx  # noqa: E402

# 当前有效版本的 docx 列表（其他版本不派生 markdown）
# V1.0 已签字归档；命名规范使用下划线（V1_1）匹配秘书实际产出的文件名
ACTIVE_DOCX_PATTERNS = [
    "CMAB_MDM_Portal_数据模型设计文档_V1_1.docx",
    "CMAB_MDM_Portal_架构设计文档_V1_1.docx",
    "CMAB_MDM_Portal_API接口规范_V1_1.docx",
    "CMAB_MDM_Portal_UI信息架构与线框图_V1_1.docx",
]

PANDOC_DOCKER_IMAGE = "pandoc/core:3.1"


def _pandoc_cmd_local(in_docx: Path, out_md: Path) -> list[str]:
    return [
        "pandoc",
        "-f", "docx",
        "-t", "gfm",
        "--wrap=none",
        "-o", str(out_md),
        str(in_docx),
    ]


def _pandoc_cmd_docker(in_docx: Path, out_md: Path) -> list[str]:
    """docker fallback：把 repo 挂载到 /data，所有路径用相对路径"""
    in_rel = in_docx.relative_to(REPO_ROOT)
    out_rel = out_md.relative_to(REPO_ROOT)
    return [
        "docker", "run", "--rm",
        "--user", f"{os.getuid()}:{os.getgid()}",
        "-v", f"{REPO_ROOT}:/data",
        "-w", "/data",
        PANDOC_DOCKER_IMAGE,
        "-f", "docx",
        "-t", "gfm",
        "--wrap=none",
        "-o", str(out_rel),
        str(in_rel),
    ]


def _run_pandoc(in_docx: Path, out_md: Path) -> None:
    """优先本地 pandoc，没有则 docker fallback"""
    if shutil.which("pandoc"):
        cmd = _pandoc_cmd_local(in_docx, out_md)
        mode = "local"
    elif shutil.which("docker"):
        cmd = _pandoc_cmd_docker(in_docx, out_md)
        mode = "docker"
    else:
        sys.exit(
            "ERROR: 既没有本地 pandoc 也没有 docker。\n"
            "请安装其一：\n"
            "  - macOS: brew install pandoc\n"
            "  - Linux: apt install pandoc\n"
            "  - 或确保 docker 可用（项目已依赖）"
        )
    print(f"  [{mode}] {' '.join(cmd[:4])} ... {in_docx.name}")
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        sys.exit(f"pandoc failed: {result.stderr}")


def _post_process(md_path: Path, docx_path: Path) -> None:
    """
    后处理：去除 pandoc 输出的噪音 + 用 docx 原文恢复单单元格表的对齐与缩进。

    pandoc 把 docx 单单元格 <w:tbl> 转成 HTML <p> 时会按 HTML 标准压缩连续空格，
    破坏 ASCII 框图和代码缩进。restore_blocks_from_docx 直接从 docx XML
    读取 xml:space="preserve" 原文重建为代码围栏 / blockquote。

    1. 从 docx 原文恢复所有单单元格表（多单元格表保留 HTML 不动）
    2. 去除 attribute id `{#title}` `{.class}` 等（pandoc 给标题加的内部锚点）
    3. 折叠连续 3 行以上空行为 2 行
    4. 去除行尾空白
    5. 文件头加自动生成警告
    """
    text = md_path.read_text(encoding="utf-8")

    # 1) 用 docx 原文重建单单元格表（恢复 ASCII 对齐 / 代码缩进）
    text, _stats = restore_blocks_from_docx(text, docx_path)

    # 2) attribute id `{#xxx}` `{.xxx}` `{.unnumbered}` 等
    text = re.sub(r"[ \t]*\{[#.][^}]+\}", "", text)

    # 3) 多余空行
    text = re.sub(r"\n{3,}", "\n\n", text)

    # 4) 行尾空白
    text = re.sub(r"[ \t]+\n", "\n", text)

    # 5) 文件头警告（让人类知道这是派生文件）
    warning = (
        f"<!--\n"
        f"  本文件由 scripts/docs/extract_md.py 从 docx 自动派生，请勿手工修改。\n"
        f"  源文件:{md_path.with_suffix('.docx').name}\n"
        f"  重新生成:make docs-extract\n"
        f"  一致性校验:make docs-check\n"
        f"-->\n\n"
    )
    if not text.startswith("<!--"):
        text = warning + text

    md_path.write_text(text, encoding="utf-8")


def extract_one(docx_path: Path, out_md: Path) -> bool:
    """提取单个 docx → markdown。返回是否真正提取（False = docx 不存在跳过）"""
    if not docx_path.exists():
        print(f"  ⚠ 跳过：{docx_path.name} 不存在（秘书尚未产出）")
        return False
    out_md.parent.mkdir(parents=True, exist_ok=True)
    _run_pandoc(docx_path, out_md)
    _post_process(out_md, docx_path)
    print(f"  ✓ {docx_path.name} → {out_md.relative_to(REPO_ROOT)}")
    return True


def main() -> int:
    parser = argparse.ArgumentParser(description="docx → markdown 派生工具")
    parser.add_argument(
        "docx", nargs="?", help="单个 docx 文件路径；省略则批量处理 ACTIVE 列表"
    )
    parser.add_argument(
        "--check", action="store_true",
        help="输出到 .tmp/ 不覆盖原 markdown（CI 一致性校验用）",
    )
    parser.add_argument(
        "--out-dir", default=None,
        help="自定义输出目录（默认与 docx 同目录）",
    )
    args = parser.parse_args()

    if args.docx:
        docx_path = Path(args.docx).resolve()
        out_dir = Path(args.out_dir).resolve() if args.out_dir else docx_path.parent
        out_md = out_dir / docx_path.with_suffix(".md").name
        if args.check:
            out_md = REPO_ROOT / ".tmp" / "docs-check" / docx_path.with_suffix(".md").name
        extract_one(docx_path, out_md)
        return 0

    # 批量
    if args.check:
        check_dir = REPO_ROOT / ".tmp" / "docs-check"
        check_dir.mkdir(parents=True, exist_ok=True)
        out_dir = check_dir
    else:
        out_dir = DOCS_DIR

    extracted = 0
    skipped = 0
    for name in ACTIVE_DOCX_PATTERNS:
        docx_path = DOCS_DIR / name
        out_md = out_dir / Path(name).with_suffix(".md").name
        if extract_one(docx_path, out_md):
            extracted += 1
        else:
            skipped += 1
    print(f"\n完成：提取 {extracted} / 跳过 {skipped}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
