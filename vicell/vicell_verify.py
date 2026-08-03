#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
vicell_verify.py — Vi-CELL 归档核对工具

回答四个问题（对应 docs/INGEST-STANDARD.md §12 的失效检测）：
  1. 有没有校验不过的？        扫全部 Checksums CSV 的 match_status
  2. 数量对得上吗？            逐类比对源端与归档的目录/文件数
  3. 内容还完好吗？            随机抽样重算 NAS 侧 SHA-256，与源端比对（防静默损坏）
  4. 时间戳对吗？              抽样比对 NAS 与源端的修改时间（必须是原始生成时间）

只读，不修改任何文件。可反复运行。

用法：
    python3 vicell_verify.py                 # 默认抽样 30 个文件
    python3 vicell_verify.py --sample 200    # 加大抽样（季度复核用）
    python3 vicell_verify.py --full-count    # 逐目录点文件数（慢，但彻底）
"""

import os
import csv
import sys
import glob
import random
import hashlib
import argparse
import datetime as dt
from pathlib import Path

MACHINE = os.environ.get("VICELL_MACHINE_NAME", "C4V61257XH_ViCell")
NAS = Path(os.environ.get("VICELL_NAS_MOUNT", "/mnt/ttlab-backups"))
SRC = Path(os.environ.get("VICELL_SRC_MOUNT", "/mnt/vicell"))
ORIGIN = Path(os.environ.get("VICELL_IMAGES_ORIGIN", "/mnt/vicell-old/dimg"))
LEGACY = Path(os.environ.get("VICELL_LEGACY_MOUNT", "/mnt/vicell-old"))
CONFIG_SRC = Path(os.environ.get("VICELL_CONFIG_SOURCE", "/mnt/vicell-old/app"))

ARCHIVE = NAS / "Daily" / MACHINE
CHECKSUMS = NAS / "Checksums" / MACHINE

# (归档子路径, 源目录列表, 类型)  类型 samples=一层样品目录 / flat=平铺文件
LAYOUT = [
    ("data", [SRC / "Data"], "flat"),
    ("export", [SRC / "Export"], "flat"),
    ("config", [CONFIG_SRC], "flat"),
    ("images", [ORIGIN, SRC / "Images"], "samples"),
    ("legacy/XR-2025.04.27", [LEGACY / "img2025"], "samples"),
    ("legacy/2025.5.14HEK-293计数图片", [LEGACY / "img2024"], "samples"),
    ("legacy/1111", [LEGACY / "img2023"], "samples"),
    ("legacy/计数仪历史数据", [LEGACY / "history"], "flat"),
]

problems = []


def say(msg=""):
    print(msg, flush=True)


def flag(msg):
    problems.append(msg)
    say(f"  ❌ {msg}")


def sha256(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for c in iter(lambda: f.read(1 << 20), b""):
            h.update(c)
    return h.hexdigest()


def check_checksum_files():
    say("=" * 66)
    say("1. 校验比对表：有没有 match_status 不是 MATCH 的")
    say("=" * 66)
    files = sorted(glob.glob(str(CHECKSUMS / "*.csv")))
    if not files:
        flag(f"找不到任何比对表: {CHECKSUMS}")
        return
    total = 0
    bad = {}
    for f in files:
        try:
            with open(f, encoding="utf-8-sig", newline="") as fh:
                for row in csv.DictReader(fh):
                    total += 1
                    st = (row.get("match_status") or "").strip()
                    if st != "MATCH":
                        bad.setdefault(st or "(空)", []).append(row.get("Relative_Path", "?"))
        except Exception as e:
            flag(f"比对表读取失败 {Path(f).name}: {e}")
    say(f"  比对表 {len(files)} 个，记录 {total} 行")
    if not bad:
        say(f"  ✅ 全部 MATCH")
    for st, items in bad.items():
        flag(f"{st}: {len(items)} 行，例如 {items[:3]}")


def count_entries(p: Path, kind: str):
    """samples -> 子目录数；flat -> 文件数"""
    if not p.is_dir():
        return None
    try:
        if kind == "samples":
            return sum(1 for x in p.iterdir() if x.is_dir())
        return sum(1 for x in p.iterdir() if x.is_file() and not x.name.startswith("."))
    except Exception:
        return None


def check_counts(full_count: bool):
    say()
    say("=" * 66)
    say("2. 数量核对：源端 vs 归档")
    say("=" * 66)
    for sub, srcs, kind in LAYOUT:
        dst = ARCHIVE / sub
        d = count_entries(dst, kind)
        names_src = set()
        for s in srcs:
            if not s.is_dir():
                continue
            try:
                if kind == "samples":
                    names_src |= {x.name for x in s.iterdir() if x.is_dir()}
                else:
                    names_src |= {x.name for x in s.iterdir()
                                  if x.is_file() and not x.name.startswith(".")}
            except Exception as e:
                flag(f"{sub}: 源端读取失败 {s} ({e})")
        n_src = len(names_src) if names_src else None

        if d is None:
            flag(f"{sub}: 归档目录不存在")
            continue
        if n_src is None:
            say(f"  {sub:34s} 归档 {d:6d}  （源端未挂载，跳过比对）")
            continue

        names_dst = set()
        try:
            names_dst = ({x.name for x in dst.iterdir() if x.is_dir()} if kind == "samples"
                         else {x.name for x in dst.iterdir()
                               if x.is_file() and not x.name.startswith(".")})
        except Exception:
            pass
        missing = names_src - names_dst          # 源端有、归档没有 → 真问题
        extra = names_dst - names_src            # 归档有、源端没有 → 源端已删（正常，append-only）

        tag = "✅" if not missing else "❌"
        say(f"  {sub:34s} 源 {n_src:6d}  归档 {d:6d}  {tag}")
        if missing:
            flag(f"{sub}: 归档缺 {len(missing)} 项，例如 {sorted(missing)[:3]}")
        if extra:
            say(f"     ↳ 归档多 {len(extra)} 项（源端已删除，归档保留是对的）"
                f"，例如 {sorted(extra)[:3]}")

        # 逐目录点文件数（可选，慢）
        if full_count and kind == "samples":
            odd = []
            for name in sorted(names_src & names_dst):
                sdir = next((s / name for s in srcs if (s / name).is_dir()), None)
                if sdir is None:
                    continue
                a = sum(1 for x in sdir.iterdir() if x.is_file())
                b = sum(1 for x in (dst / name).iterdir() if x.is_file())
                if a != b:
                    odd.append(f"{name}({a}->{b})")
            if odd:
                flag(f"{sub}: {len(odd)} 个目录文件数不一致，例如 {odd[:3]}")
            else:
                say(f"     ↳ 逐目录点数：全部一致")


def sample_files(n: int):
    """从归档里随机取 n 个文件，回到源端找对应的那一个"""
    picked = []
    for sub, srcs, kind in LAYOUT:
        dst = ARCHIVE / sub
        if not dst.is_dir():
            continue
        try:
            if kind == "samples":
                dirs = [x for x in dst.iterdir() if x.is_dir()]
                if not dirs:
                    continue
                for d in random.sample(dirs, min(len(dirs), max(2, n // 8))):
                    files = [x for x in d.iterdir() if x.is_file()]
                    if files:
                        f = random.choice(files)
                        s = next((s / d.name / f.name for s in srcs
                                  if (s / d.name / f.name).is_file()), None)
                        picked.append((f, s))
            else:
                files = [x for x in dst.iterdir() if x.is_file() and not x.name.startswith(".")]
                if not files:
                    continue
                for f in random.sample(files, min(len(files), max(2, n // 8))):
                    s = next((s / f.name for s in srcs if (s / f.name).is_file()), None)
                    picked.append((f, s))
        except Exception as e:
            flag(f"{sub}: 抽样失败 ({e})")
    return picked[:n]


def check_content_and_mtime(n: int):
    say()
    say("=" * 66)
    say(f"3+4. 抽样核对内容与时间戳（{n} 个文件）")
    say("=" * 66)
    picked = sample_files(n)
    if not picked:
        flag("没抽到任何文件")
        return
    sha_ok = sha_bad = mt_ok = mt_bad = no_src = 0
    for dstf, srcf in picked:
        if srcf is None:
            no_src += 1
            continue
        try:
            if sha256(dstf) == sha256(srcf):
                sha_ok += 1
            else:
                sha_bad += 1
                flag(f"内容不一致: {dstf}")
            if abs(dstf.stat().st_mtime - srcf.stat().st_mtime) <= 2:
                mt_ok += 1
            else:
                mt_bad += 1
                flag(f"时间戳不对: {dstf} "
                     f"(归档 {dt.datetime.fromtimestamp(dstf.stat().st_mtime)} / "
                     f"源 {dt.datetime.fromtimestamp(srcf.stat().st_mtime)})")
        except Exception as e:
            flag(f"抽查失败 {dstf}: {e}")
    say(f"  抽样 {len(picked)} 个")
    say(f"  内容 SHA-256: 一致 {sha_ok}  不一致 {sha_bad}")
    say(f"  修改时间    : 一致 {mt_ok}  不一致 {mt_bad}")
    if no_src:
        say(f"  源端已无对应文件 {no_src} 个（归档保留是对的，不算问题）")


def main():
    ap = argparse.ArgumentParser(description="Vi-CELL 归档核对（只读）")
    ap.add_argument("--sample", type=int, default=30, help="抽样文件数（默认 30）")
    ap.add_argument("--full-count", action="store_true", help="逐目录点文件数（慢）")
    ap.add_argument("--seed", type=int, default=None, help="固定随机种子便于复现")
    args = ap.parse_args()

    if args.seed is not None:
        random.seed(args.seed)

    say(f"Vi-CELL 归档核对  |  {MACHINE}  |  {dt.datetime.now():%Y-%m-%d %H:%M:%S}")
    say(f"归档: {ARCHIVE}")
    say()

    check_checksum_files()
    check_counts(args.full_count)
    check_content_and_mtime(args.sample)

    say()
    say("=" * 66)
    if problems:
        say(f"结论：发现 {len(problems)} 个问题")
        for p in problems:
            say(f"  - {p}")
        return 1
    say("结论：全部通过 ✅")
    return 0


if __name__ == "__main__":
    sys.exit(main())
