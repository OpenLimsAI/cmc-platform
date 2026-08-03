#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
smb_metadata.py — Windows 原始文件 metadata 采集器（Stage 1 附属模块）

对应整改项：AUDIT-2026-08-03-data-integrity.md 的 **MD-001**
设计依据：docs/DATA_INTEGRITY_METADATA_DESIGN.md

**这个模块采集的是「源端原始文件」的 metadata，不是「归档副本」的 metadata。**

背景（一句话）：Linux 挂载 CIFS 后 os.stat() 拿不到 Windows 创建时间
（statx 的 st_birthtime 返回 None，stat 命令显示的 Birth 是内核用 mtime 填的假值），
但 CIFS 客户端把它通过扩展属性 user.cifs.creationtime 暴露了出来。

⚠️ **本模块绝不修改任何文件，绝不影响复制与校验流程。**
    任何采集失败都只记录、不抛出，调用方无需 try。

依赖：仅 Python 标准库。
"""

import os
import csv
import struct
import logging
import datetime as dt
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple

COLLECTOR_NAME = "smb_metadata"
COLLECTOR_VERSION = "v1.0.0"
COLLECTOR_TAG = f"{COLLECTOR_NAME} {COLLECTOR_VERSION}"

# CIFS 客户端暴露 Windows CreationTime 的扩展属性名。
# 实测（2026-08-03，Linux cifs + Win7 SMB2.1）该属性可用，
# 取值为 8 字节小端 Windows FILETIME，解码结果与 smbclient allinfo 逐秒吻合。
CREATION_XATTR = "user.cifs.creationtime"

# Windows FILETIME 纪元（1601-01-01）到 Unix 纪元（1970-01-01）的秒差
FILETIME_EPOCH_DELTA = 11644473600
FILETIME_UNITS_PER_SEC = 10_000_000

CSV_HEADER = [
    "relative_path",
    "source_path",
    "file_name",
    "file_size",
    "creation_time_original",
    "modified_time_original",
    "access_time_original",
    "change_time_original",
    "metadata_source",
    "metadata_collected_at",
    "collector_version",
    "machine_name",
]

# metadata_source 取值
SRC_FULL = "xattr:user.cifs.creationtime+stat"   # 创建时间与 stat 四项齐全
SRC_STAT_ONLY = "stat-only"                      # xattr 不可用，仅 stat 三项
SRC_FAILED = "failed"                            # 连 stat 都失败

logger = logging.getLogger("vicell_ingest")


def _iso(ts: float) -> str:
    """Unix 时间戳 -> ISO-8601 带时区。不用无时区的本地时间串（审计 MD-013）。"""
    return dt.datetime.fromtimestamp(ts).astimezone().isoformat()


def filetime_to_epoch(raw: bytes) -> float:
    """Windows FILETIME（小端 8 字节，自 1601-01-01 起的 100 纳秒数）-> Unix 时间戳。"""
    if len(raw) < 8:
        raise ValueError(f"FILETIME 长度异常: {len(raw)} 字节")
    ft = struct.unpack("<Q", raw[:8])[0]
    return ft / FILETIME_UNITS_PER_SEC - FILETIME_EPOCH_DELTA


def read_creation_time(path) -> Optional[float]:
    """
    读源文件的 Windows 创建时间。取不到返回 None，**不抛异常**。

    取不到的常见原因（都属正常，不是故障）：
      - 挂载或内核不支持该扩展属性 -> OSError(95) Operation not supported
      - 该文件没有这个属性         -> OSError(61) No data available
    """
    try:
        return filetime_to_epoch(os.getxattr(str(path), CREATION_XATTR))
    except Exception:
        return None


class MetadataCollector:
    """
    采集器 + 结果收集器。

    用法：
        mc = MetadataCollector(machine_name, out_dir, src_root, enabled=True)
        mc.collect(src_path)          # 每归档一个文件调一次；失败不抛
        mc.flush(dry_run=False)       # 运行结束写 CSV

    设计要点：
      - **绝不抛异常**：collect() 内部全捕获，调用方不必 try。
      - **不刷屏**：13 万个文件若逐个告警会淹没日志，故按原因聚合，
        每种原因只记一次样例，运行结束给汇总。
      - **失败也写行**：metadata_source 标 stat-only / failed，缺失字段留空。
        "采集失败"这件事本身必须留痕，不能变成静默的空白。
    """

    def __init__(self, machine_name: str, out_dir: Path, src_root: Path,
                 enabled: bool = True):
        self.machine_name = machine_name
        self.out_dir = Path(out_dir)
        self.src_root = Path(src_root)
        self.enabled = enabled
        self.rows: List[List[Any]] = []
        self.stats = {"total": 0, "full": 0, "stat_only": 0, "failed": 0}
        # 原因 -> (次数, 首个样例)
        self._reasons: Dict[str, Tuple[int, str]] = {}

    # ---------- 内部 ----------
    def _note(self, reason: str, sample: str) -> None:
        n, first = self._reasons.get(reason, (0, sample))
        self._reasons[reason] = (n + 1, first)

    def _relative(self, src: Path) -> str:
        """相对路径：能相对源根就相对，否则退回绝对路径（历史源挂在别的根下）。"""
        try:
            return str(src.relative_to(self.src_root))
        except Exception:
            return str(src)

    # ---------- 对外 ----------
    def collect(self, src, relative_path: Optional[str] = None) -> None:
        """
        采集单个源文件的 metadata。**任何情况下都不抛异常、不阻断备份。**

        relative_path 可显式传入（历史源不在主挂载点下时更准确）。
        """
        if not self.enabled:
            return

        src = Path(src)
        rel = relative_path if relative_path is not None else self._relative(src)
        now = _iso(dt.datetime.now().timestamp())
        self.stats["total"] += 1

        try:
            st = os.stat(str(src))
        except Exception as e:
            # 连 stat 都失败：仍写一行，把"采集失败"记录下来
            self.stats["failed"] += 1
            self._note(f"stat 失败: {type(e).__name__}", str(src))
            self.rows.append([
                rel, str(src), src.name, "", "", "", "", "",
                SRC_FAILED, now, COLLECTOR_TAG, self.machine_name,
            ])
            return

        ctime_epoch = read_creation_time(src)
        if ctime_epoch is None:
            self.stats["stat_only"] += 1
            self._note(f"创建时间不可得（{CREATION_XATTR} 无值或不支持）", str(src))
            creation = ""
            source = SRC_STAT_ONLY
        else:
            self.stats["full"] += 1
            creation = _iso(ctime_epoch)
            source = SRC_FULL

        self.rows.append([
            rel, str(src), src.name, st.st_size,
            creation,
            _iso(st.st_mtime),
            _iso(st.st_atime),
            _iso(st.st_ctime),      # stat 语义；可靠性说明见设计文档 §2.3
            source, now, COLLECTOR_TAG, self.machine_name,
        ])

    def summary_line(self) -> str:
        s = self.stats
        return (f"Metadata: 采集 {s['total']}  完整 {s['full']}  "
                f"仅stat {s['stat_only']}  失败 {s['failed']}")

    def log_summary(self) -> None:
        """运行结束时汇总。逐文件告警会刷屏，所以按原因聚合后一次性报。"""
        if not self.enabled:
            return
        logger.info(self.summary_line())
        for reason, (n, sample) in self._reasons.items():
            # 采集失败不阻断备份，但必须以 WARNING 留痕（设计文档 §5.7）
            logger.warning(f"Metadata 采集不完整（{n} 个文件）: {reason}；样例: {sample}")

    def flush(self, dry_run: bool = False, run_tag: Optional[str] = None) -> Optional[Path]:
        """写出 Metadata CSV。写失败只告警，不影响归档结果。"""
        if not self.enabled or not self.rows:
            return None
        if dry_run:
            logger.info(f"[dry-run] 跳过 Metadata 写入（本次将有 {len(self.rows)} 行）")
            return None

        tag = run_tag or dt.datetime.now().strftime("%Y%m%d_%H%M%S")
        out = self.out_dir / f"{tag}_SMB_Metadata.csv"
        try:
            out.parent.mkdir(parents=True, exist_ok=True)
            # utf-8-sig 与 Checksums/ 下的比对文件保持一致，Excel 可直接打开
            with open(out, "w", encoding="utf-8-sig", newline="") as f:
                w = csv.writer(f)
                w.writerow(CSV_HEADER)
                w.writerows(self.rows)
            logger.info(f"Metadata 已写出（{len(self.rows)} 行）: {out}")
            return out
        except Exception as e:
            logger.warning(f"Metadata 写入失败（不影响归档）: {e}")
            return None


# =========================================================
# 自检：可独立运行，用于验证 xattr 解码与 smbclient allinfo 一致
#   python3 smb_metadata.py <文件路径> [...]
# =========================================================
if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print(f"{COLLECTOR_TAG}\n用法: python3 smb_metadata.py <文件路径> [...]")
        raise SystemExit(2)

    print(f"{COLLECTOR_TAG}  (xattr = {CREATION_XATTR})\n")
    for p in sys.argv[1:]:
        path = Path(p)
        try:
            st = os.stat(str(path))
        except Exception as e:
            print(f"{p}\n  stat 失败: {e}\n")
            continue
        ct = read_creation_time(path)
        print(f"{p}")
        print(f"  creation_time : {_iso(ct) if ct is not None else '(不可得)'}")
        print(f"  modified_time : {_iso(st.st_mtime)}")
        print(f"  access_time   : {_iso(st.st_atime)}")
        print(f"  change_time   : {_iso(st.st_ctime)}")
        print(f"  size          : {st.st_size}")
        print()
