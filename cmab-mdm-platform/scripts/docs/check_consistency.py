#!/usr/bin/env python3
"""
docx ↔ markdown 一致性校验（CI 门禁）

规则：markdown 必须是 docx 的派生产物，不能被手工独立修改。
做法：重新跑 extract_md.py --check 到 .tmp/docs-check/，diff 与 git 树的 markdown。
不一致 → exit 1（CI fail），并打印 diff 引导用户修复。

修复方式：
1. 如果你**应该**改 docx：去 docx 里改 → make docs-extract
2. 如果你误改了 markdown：git checkout 还原后重新 make docs-extract
"""
from __future__ import annotations

import difflib
import os
import subprocess
import sys
from pathlib import Path

# 原型期暂停（2026-06-08 项目负责人决策）：md 为唯一工作源，docx 冻结在 V1.1，
# 不在迭代期同步 docx，故本门禁默认**非阻塞**——仍打印漂移报告但 exit 0。
# 决策与恢复时机见 docs/CMAB_MDM_Portal_设计基准偏离说明_V1.3_draft.md §3。
# 临时跑严格模式（如 GMP 闸口前预览就绪度）：DOCS_CHECK_ENFORCE=1 make docs-check
ENFORCE = os.environ.get("DOCS_CHECK_ENFORCE", "0") == "1"

REPO_ROOT = Path(__file__).resolve().parents[2]
DOCS_DIR = REPO_ROOT / "docs"
CHECK_DIR = REPO_ROOT / ".tmp" / "docs-check"

# 与 extract_md.py 保持一致的 ACTIVE 列表
ACTIVE_MD_NAMES = [
    "CMAB_MDM_Portal_数据模型设计文档_V1_1.md",
    "CMAB_MDM_Portal_架构设计文档_V1_1.md",
    "CMAB_MDM_Portal_API接口规范_V1_1.md",
    "CMAB_MDM_Portal_UI信息架构与线框图_V1_1.md",
]


def run_extract_check() -> int:
    """跑 extract_md.py --check 重新提取到 .tmp/"""
    cmd = ["python3", str(REPO_ROOT / "scripts/docs/extract_md.py"), "--check"]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print("ERROR: 重新提取失败")
        print(result.stdout)
        print(result.stderr, file=sys.stderr)
        return result.returncode
    print(result.stdout)
    return 0


def diff_pair(committed: Path, freshly_extracted: Path) -> list[str]:
    """对比 git 树 markdown vs 刚提取的 markdown；返回 unified diff 行列表（空 = 一致）"""
    if not committed.exists() and not freshly_extracted.exists():
        return []  # 两边都没有，跳过（docx 还没产出）
    if not committed.exists():
        return [f"+ {freshly_extracted.name} 是新派生文件，需要 git add"]
    if not freshly_extracted.exists():
        return [f"- {committed.name} 已存在但 docx 不存在（孤儿派生文件）"]

    a = committed.read_text(encoding="utf-8").splitlines(keepends=True)
    b = freshly_extracted.read_text(encoding="utf-8").splitlines(keepends=True)
    return list(difflib.unified_diff(
        a, b,
        fromfile=f"git: {committed.relative_to(REPO_ROOT)}",
        tofile=f"extracted: {freshly_extracted.relative_to(REPO_ROOT)}",
        n=3,
    ))


def main() -> int:
    print("=== 双轨文档一致性校验 ===\n")

    print("第 1 步：重新从 docx 提取 markdown 到 .tmp/docs-check/ ...")
    rc = run_extract_check()
    if rc != 0:
        return rc

    print("\n第 2 步：对比 git 树 markdown vs 刚提取的 markdown ...\n")
    all_ok = True
    for name in ACTIVE_MD_NAMES:
        committed = DOCS_DIR / name
        fresh = CHECK_DIR / name
        diff = diff_pair(committed, fresh)
        if not diff:
            if committed.exists():
                print(f"  ✓ {name} — 一致")
            else:
                print(f"  ⊘ {name} — 跳过（docx 与 markdown 均不存在）")
            continue

        all_ok = False
        print(f"\n  ✗ {name} — 不一致！\n")
        for line in diff[:80]:  # 限制输出长度
            print("    " + line.rstrip())
        if len(diff) > 80:
            print(f"    ... (省略 {len(diff) - 80} 行)\n")

    if not all_ok:
        print("\n" + "=" * 60)
        print("❌ docx ↔ markdown 不一致" + ("（强制模式）" if ENFORCE else ""))
        print("=" * 60)
        print(
            "\n双轨文档规则：docx 是源，markdown 是 docx 的自动派生副本。\n"
            "markdown **不能被手工修改**。\n\n"
            "修复方式：\n"
            "  A) 如果内容变更**应该**发生在 docx → 直接在 docx 改完后跑：\n"
            "     make docs-extract\n"
            "     git add docs/*.md && git commit\n\n"
            "  B) 如果是误改了 markdown → 还原后重新提取：\n"
            "     git checkout docs/*.md\n"
            "     make docs-extract\n"
        )
        if ENFORCE:
            return 1
        # 原型期暂停：报告漂移但不阻塞
        print("=" * 60)
        print(
            "⏸  原型期暂停（DOCS_CHECK_ENFORCE!=1）：md 为唯一工作源、docx 冻结 V1.1，\n"
            "   上述漂移为预期，本门禁不阻塞（exit 0）。GMP 闸口前用\n"
            "   `DOCS_CHECK_ENFORCE=1 make docs-check` 预览整合就绪度。\n"
            "   决策记录见偏离说明 V1.3_draft §3。"
        )
        print("=" * 60)
        return 0

    print("\n✓ 全部一致")
    return 0


if __name__ == "__main__":
    sys.exit(main())
