#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
flex2_ingest.py — Stage 1：Nova BioProfile FLEX2 数据采集与校验

职责（只做这三件事，不做 ETL）：
  1. 从 FLEX2 Bridge PC 的只读挂载点发现新增/变化的文件
  2. 复制到 NAS 原始归档区
  3. SHA-256 双向校验（读取即算 h1，回读归档算 h2，比对）

设计原则：
  - 只读源：绝不写入 FLEX2 侧
  - 幂等：可重复执行，不会重复归档相同内容
  - 解耦：本程序不解析业务字段，不入库。ETL 由 Stage 2 从 NAS 读取
  - 原子：先写临时文件再 rename，避免半截文件被 ETL 读到

数据源策略（基于 2026-07-15 实测确认）：
  - 月度 CSV = 主数据源（是逐次文件的严格超集，且独有试剂批号列）
    月度文件整月持续追加 → 每次内容变化存一份带时间戳的快照
  - Database\\Backup_* = 每晚覆盖，只留一份 → 必须每天抓，否则历史永久丢失
  - 逐次 CSV = 冷备（immutable，抓一次即可），默认不抓，--per-event 开启

依赖：Python 3.8+，仅标准库
"""

import os
import re
import sys
import csv
import json
import time
import hashlib
import logging
import argparse
import subprocess
import datetime as dt
from io import StringIO
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple

# =========================================================
# 版本信息（变更控制用，改动逻辑请同步递增）
# =========================================================
SCRIPT_NAME = "flex2_ingest"
SCRIPT_VERSION = "v1.1.0"
SCRIPT_RELEASE_DATE = "2026-07-15"
SCRIPT_OWNER = "TT Lab"

# =========================================================
# 配置（全部可用环境变量覆盖，见 flex2-ingest.env）
# =========================================================
ANALYZER_ID = os.environ.get("FLEX2_ANALYZER_ID", "T281240040C")
MACHINE_NAME = os.environ.get("FLEX2_MACHINE_NAME", f"{ANALYZER_ID}_Nova")

SRC_MOUNT = Path(os.environ.get("FLEX2_SRC_MOUNT", "/mnt/flex2"))
# NAS 共享根（TTLab_Backups）的挂载点；归档写到其下 Daily/<机器名>/
NAS_MOUNT = Path(os.environ.get("FLEX2_NAS_MOUNT", "/mnt/ttlab-backups"))

# 月度文件回溯几个月（1 = 当月+上月，跨月边界安全）
MONTHS_BACK = int(os.environ.get("FLEX2_MONTHS_BACK", "1"))

# Database 备份超过多少小时未更新则告警（它每晚跑，与做不做样品无关，是最好的健康信号）
DB_STALE_HOURS = float(os.environ.get("FLEX2_DB_STALE_HOURS", "36"))

# 告警命令：会以 ALERT_CMD "<级别>" "<消息>" 方式调用，可对接企业微信/邮件
ALERT_CMD = os.environ.get("FLEX2_ALERT_CMD", "").strip()

# 读取源文件时，若 stat 在读取前后发生变化则重试（防止读到正在追加的半截文件）
STABLE_RETRIES = int(os.environ.get("FLEX2_STABLE_RETRIES", "4"))
STABLE_WAIT_SEC = float(os.environ.get("FLEX2_STABLE_WAIT_SEC", "3"))

CHUNK = 1024 * 1024

MONTH_NAMES = [
    "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December",
]
MONTH_NUM = {name.lower(): i + 1 for i, name in enumerate(MONTH_NAMES)}

# 文件名模式（严格锚定 Analyzer ID，避免误抓别的机器或残留的 .lnk）
_AID = re.escape(ANALYZER_ID)
MONTHLY_RE = re.compile(
    rf"^(?P<kind>SampleResults|QcResults){_AID}(?P<year>\d{{4}})-(?P<month>{'|'.join(MONTH_NAMES)})\.csv$",
    re.IGNORECASE,
)
PEREVENT_RE = re.compile(
    rf"^SampleResults{_AID}(?P<year>\d{{4}})-(?P<mm>\d{{2}})-(?P<dd>\d{{2}})_(?P<hms>\d{{6}})\.csv$",
    re.IGNORECASE,
)
DBBACKUP_RE = re.compile(r"^Backup_(?P<ts>\d{4}-\d{2}-\d{2}_\d{6})$")

# =========================================================
# 派生路径
# =========================================================
SRC_RESULTS = SRC_MOUNT / "Results"
SRC_DATABASE = SRC_MOUNT / "Database"

# 数据根 = NAS 共享根 / Daily / 机器名（对齐 NAS 既有多设备约定：Daily/<机器名>/）。
# NAS 侧已建 Daily/T281240040C_Nova/{Results,Database,Report}，文件夹名镜像仪器 Export。
ARCHIVE_ROOT = NAS_MOUNT / "Daily" / MACHINE_NAME
RESULTS_ROOT = ARCHIVE_ROOT / "Results"    # 月度快照 + 逐次冷备
DATABASE_ROOT = ARCHIVE_ROOT / "Database"  # 每晚数据库备份
# Report 不产出（人工 PDF，按铁律忽略）

# 记账目录：与其它设备完全一致，放 NAS 根级、按机器名分（不塞进 Daily 的数据目录）。
STATE_DIR = NAS_MOUNT / "State"
CHECKSUM_DIR = NAS_MOUNT / "Checksums" / MACHINE_NAME
LOG_DIR = NAS_MOUNT / "Logs" / MACHINE_NAME

# state 文件名沿用既有备份脚本约定：<机器名>_backup_state.json
STATE_FILE = STATE_DIR / f"{MACHINE_NAME}_backup_state.json"

# 本地状态副本（NAS 不可达时仍留有痕迹）
LOCAL_STATE_DIR = Path(os.environ.get("FLEX2_LOCAL_STATE_DIR", str(Path(__file__).resolve().parent)))
LOCAL_STATE_FILE = LOCAL_STATE_DIR / f"{MACHINE_NAME}_backup_state.json"

RUN_DT = dt.datetime.now()
RUN_TAG = RUN_DT.strftime("%Y%m%dT%H%M%S")
NOW_STR = RUN_DT.strftime("%Y-%m-%d %H:%M:%S")

# 校验比对文件：对齐 NAS 既有备份约定，每次运行输出一个带时间戳的比对 CSV
# （文件名与列都与其它设备的 *_SHA256_Compare_*.csv 一致；空跑也留只含表头的文件）
VERSION_TAG = SCRIPT_VERSION.replace(".", "_")           # v1.1.0 -> v1_1_0
RUN_TAG_COMPAT = RUN_DT.strftime("%Y%m%d_%H%M%S")        # 既有文件名的时间戳格式
COMPARE_FILE = CHECKSUM_DIR / f"{MACHINE_NAME}_SHA256_Compare_{VERSION_TAG}_{RUN_TAG_COMPAT}.csv"
COMPARE_HEADER = [
    "Relative_Path", "Local_Path", "NAS_Path", "Change_Type",
    "Local_Size", "Local_MTime", "Local_SHA256", "NAS_SHA256", "match_status",
]

logger = logging.getLogger(SCRIPT_NAME)


# =========================================================
# 基础工具
# =========================================================
def setup_logger(log_file: Optional[Path]) -> None:
    logger.setLevel(logging.INFO)
    logger.propagate = False
    for h in logger.handlers[:]:
        logger.removeHandler(h)
        h.close()

    fmt = logging.Formatter("%(asctime)s | %(levelname)-7s | %(message)s", "%Y-%m-%d %H:%M:%S")

    ch = logging.StreamHandler(sys.stdout)
    ch.setFormatter(fmt)
    logger.addHandler(ch)

    if log_file is not None:
        try:
            log_file.parent.mkdir(parents=True, exist_ok=True)
            fh = logging.FileHandler(log_file, encoding="utf-8")
            fh.setFormatter(fmt)
            logger.addHandler(fh)
        except Exception as e:
            logger.warning(f"日志文件不可写（继续，仅控制台输出）: {e}")


def alert(level: str, message: str) -> None:
    """告警钩子。未配置 ALERT_CMD 时只写日志。"""
    logger.error(f"ALERT[{level}] {message}")
    if not ALERT_CMD:
        return
    try:
        subprocess.run([ALERT_CMD, level, f"[{MACHINE_NAME}] {message}"], timeout=30, check=False)
    except Exception as e:
        logger.warning(f"告警命令执行失败: {e}")


def sha256_bytes(data: bytes) -> str:
    h = hashlib.sha256()
    h.update(data)
    return h.hexdigest()


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(CHUNK), b""):
            h.update(chunk)
    return h.hexdigest()


def fmt_mtime(path: Path) -> str:
    """源文件修改时间，格式对齐既有比对文件（按本地时钟）。"""
    try:
        return dt.datetime.fromtimestamp(path.stat().st_mtime).strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        return ""


def is_mounted(path: Path) -> bool:
    try:
        return os.path.ismount(str(path))
    except Exception:
        return False


def preflight() -> None:
    """挂载检查。CIFS 断链是常态，静默跳过比报错危险得多。"""
    problems = []

    if not is_mounted(SRC_MOUNT):
        problems.append(f"源未挂载: {SRC_MOUNT}")
    elif not SRC_RESULTS.is_dir():
        problems.append(f"源挂载但结构异常，找不到: {SRC_RESULTS}")

    if not is_mounted(NAS_MOUNT):
        problems.append(f"NAS 未挂载: {NAS_MOUNT}")

    if problems:
        msg = "预检失败 -> " + "; ".join(problems)
        alert("CRITICAL", msg)
        raise SystemExit(2)

    # 源必须是只读的。若可写说明 ro 选项没生效，属于配置事故，宁可停也不冒险。
    probe = SRC_MOUNT / f".__ro_probe_{os.getpid()}"
    try:
        probe.touch()
    except OSError:
        logger.info(f"只读校验通过: {SRC_MOUNT} 不可写")
    except Exception as e:
        logger.warning(f"只读校验异常（继续）: {e}")
    else:
        try:
            probe.unlink()
        except Exception:
            pass
        alert("CRITICAL", f"源挂载点 {SRC_MOUNT} 可写！ro 选项未生效，已中止以保护仪器数据")
        raise SystemExit(3)


def read_source_stable(path: Path) -> bytes:
    """
    读取源文件，并确保读取期间文件没有被追加。
    月度 CSV 在整月内持续被 FLEX2 追加，直接读可能拿到半截行。
    """
    last_err = None
    for attempt in range(1, STABLE_RETRIES + 1):
        try:
            st1 = path.stat()
            with open(path, "rb") as f:
                data = f.read()
            st2 = path.stat()
            if (st1.st_size, st1.st_mtime_ns) == (st2.st_size, st2.st_mtime_ns) == (len(data), st2.st_mtime_ns):
                return data
            logger.info(f"读取期间文件发生变化，重试 {attempt}/{STABLE_RETRIES}: {path.name}")
        except Exception as e:
            last_err = e
            logger.warning(f"读取失败，重试 {attempt}/{STABLE_RETRIES}: {path.name} -> {e}")
        time.sleep(STABLE_WAIT_SEC)

    raise IOError(f"源文件读取不稳定或失败: {path} ({last_err})")


def validate_csv(data: bytes, name: str) -> Tuple[bool, int, str]:
    """
    结构校验，不解析业务字段。
    返回 (是否通过, 数据行数, 说明)

    注意：FLEX2 每行尾部都有一个多余逗号，会产生一个空列，属正常现象。
    """
    try:
        text = data.decode("utf-8", errors="strict")
    except UnicodeDecodeError as e:
        return False, 0, f"UTF-8 解码失败: {e}"

    if text.startswith("\ufeff"):
        # 实测无 BOM；出现即视为 Nova 改了导出行为，值得知道
        return False, 0, "出现了 BOM，导出行为可能已变更，请人工确认"

    try:
        rows = list(csv.reader(StringIO(text)))
    except Exception as e:
        return False, 0, f"CSV 解析失败: {e}"

    if not rows:
        return False, 0, "空文件"

    header_len = len(rows[0])
    data_rows = [r for r in rows[1:] if any(c.strip() for c in r)]

    bad = [i for i, r in enumerate(data_rows, start=2) if len(r) != header_len]
    if bad:
        return False, len(data_rows), f"列数不一致的行: {bad[:5]}（表头 {header_len} 列）"

    return True, len(data_rows), "OK"


def archive_bytes(data: bytes, dest: Path, dry_run: bool) -> Tuple[str, str]:
    """
    原子写入 NAS 并回读校验。
    返回 (源 hash, 归档 hash)。二者一致才算归档成功。
    """
    h1 = sha256_bytes(data)
    if dry_run:
        return h1, h1

    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_name(dest.name + f".part.{os.getpid()}.{RUN_TAG}")

    try:
        with open(tmp, "wb") as f:
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, dest)
    except Exception:
        try:
            tmp.unlink(missing_ok=True)
        except Exception:
            pass
        raise

    h2 = sha256_file(dest)  # 回读，不是复用内存里的 h1
    return h1, h2


def save_json_atomic(path: Path, obj: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + f".part.{os.getpid()}")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, path)


def load_state() -> Dict[str, Any]:
    for p in (STATE_FILE, LOCAL_STATE_FILE):
        try:
            if p.exists():
                with open(p, encoding="utf-8") as f:
                    st = json.load(f)
                logger.info(f"读取状态: {p}")
                return st
        except Exception as e:
            logger.warning(f"状态文件读取失败 {p}: {e}")
    logger.info("未找到既有状态，按首次运行处理")
    return {"monthly": {}, "per_event": {}, "database": {}}


def write_compare(rows: List[List[Any]], dry_run: bool) -> None:
    """
    每次运行输出一个 SHA256 比对文件，对齐 NAS 既有备份约定
    （Checksums/<机器名>/<机器名>_SHA256_Compare_<版本>_<时间戳>.csv，含 BOM）。
    即使本轮没有新增/变化文件，也写一个只含表头的文件——留下"当天确实跑过"的证据。
    """
    if dry_run:
        return
    try:
        COMPARE_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(COMPARE_FILE, "w", encoding="utf-8-sig", newline="") as f:
            w = csv.writer(f)
            w.writerow(COMPARE_HEADER)
            w.writerows(rows)
        logger.info(f"校验比对文件已写入: {COMPARE_FILE.name}（{len(rows)} 条）")
    except Exception as e:
        logger.warning(f"校验比对文件写入失败: {e}")


# =========================================================
# 采集：月度 CSV（主数据源）
# =========================================================
def wanted_months(n_back: int) -> set:
    out = set()
    y, m = RUN_DT.year, RUN_DT.month
    for _ in range(n_back + 1):
        out.add((y, m))
        m -= 1
        if m == 0:
            y, m = y - 1, 12
    return out


def ingest_monthly(state: Dict[str, Any], args, manifest: List[List[Any]]) -> Dict[str, int]:
    stats = {"checked": 0, "new_snapshot": 0, "unchanged": 0, "failed": 0}
    reg = state.setdefault("monthly", {})
    months = None if args.backfill else wanted_months(MONTHS_BACK)

    try:
        entries = sorted(p for p in SRC_RESULTS.iterdir() if p.is_file())
    except Exception as e:
        alert("CRITICAL", f"无法列出 {SRC_RESULTS}: {e}")
        stats["failed"] += 1
        return stats

    for src in entries:
        m = MONTHLY_RE.match(src.name)
        if not m:
            continue

        year = int(m.group("year"))
        mon = MONTH_NUM[m.group("month").lower()]
        if months is not None and (year, mon) not in months:
            continue

        stats["checked"] += 1
        prev = reg.get(src.name, {})

        try:
            data = read_source_stable(src)
        except Exception as e:
            alert("ERROR", f"月度文件读取失败: {src.name} -> {e}")
            stats["failed"] += 1
            continue

        h_src = sha256_bytes(data)
        if prev.get("last_sha256") == h_src:
            stats["unchanged"] += 1
            logger.info(f"未变化，跳过: {src.name}")
            continue

        ok, rows, note = validate_csv(data, src.name)
        if not ok:
            # 校验不过就不归档，避免把坏数据写进"底本"
            alert("ERROR", f"月度文件结构校验失败，未归档: {src.name} -> {note}")
            stats["failed"] += 1
            continue

        dest = (RESULTS_ROOT / "Monthly" / f"{year:04d}-{mon:02d}" /
                f"{src.stem}__snap_{RUN_TAG}.csv")
        try:
            h1, h2 = archive_bytes(data, dest, args.dry_run)
        except Exception as e:
            alert("ERROR", f"月度文件归档失败: {src.name} -> {e}")
            stats["failed"] += 1
            continue

        verify = "MATCH" if h1 == h2 else "MISMATCH"
        if verify != "MATCH":
            alert("CRITICAL", f"归档校验不一致: {dest} (源 {h1[:12]} vs 归档 {h2[:12]})")
            stats["failed"] += 1
            continue

        prev_rows = prev.get("last_data_rows")
        if isinstance(prev_rows, int) and rows < prev_rows:
            # 追加型文件行数变少 = 历史被改写，这是数据完整性事件，必须知道
            alert("CRITICAL",
                  f"月度文件行数减少（{prev_rows} -> {rows}）: {src.name}。历史记录可能被改写，请人工核查")

        stats["new_snapshot"] += 1
        logger.info(f"已归档快照: {src.name} -> {dest.name} ({rows} 行, +{rows - (prev_rows or 0)})")

        reg[src.name] = {
            "last_sha256": h_src,
            "last_size": len(data),
            "last_data_rows": rows,
            "last_archived_at": NOW_STR,
            "last_archive": str(dest.relative_to(NAS_MOUNT)) if not args.dry_run else "(dry-run)",
            "snapshot_count": int(prev.get("snapshot_count", 0)) + 1,
        }
        manifest.append([
            str(src.relative_to(SRC_MOUNT)), str(src), str(dest),
            "CHANGED" if prev.get("last_sha256") else "NEW",
            len(data), fmt_mtime(src), h1, h2,
            "Match" if verify == "MATCH" else "Mismatch",
        ])

    return stats


# =========================================================
# 采集：Database 备份（每晚覆盖，不抓就永久丢失）
# =========================================================
def ingest_database(state: Dict[str, Any], args, manifest: List[List[Any]]) -> Dict[str, int]:
    stats = {"checked": 0, "new": 0, "unchanged": 0, "failed": 0}
    reg = state.setdefault("database", {})

    if not SRC_DATABASE.is_dir():
        logger.info(f"无 Database 目录，跳过: {SRC_DATABASE}")
        return stats

    try:
        backups = sorted(p for p in SRC_DATABASE.iterdir() if p.is_dir() and DBBACKUP_RE.match(p.name))
    except Exception as e:
        alert("ERROR", f"无法列出 {SRC_DATABASE}: {e}")
        stats["failed"] += 1
        return stats

    if not backups:
        alert("WARNING", f"{SRC_DATABASE} 下没有 Backup_* 目录，备份任务可能已停止")
        return stats

    newest_mtime = 0.0

    for bdir in backups:
        stats["checked"] += 1
        try:
            files = sorted(p for p in bdir.iterdir() if p.is_file())
        except Exception as e:
            alert("ERROR", f"无法列出 {bdir}: {e}")
            stats["failed"] += 1
            continue

        newest_mtime = max(newest_mtime, bdir.stat().st_mtime)

        if bdir.name in reg and reg[bdir.name].get("status") == "ARCHIVED":
            stats["unchanged"] += 1
            logger.info(f"已归档过，跳过: {bdir.name}")
            continue

        # 备份约 23:30 跑，任务 01:00 跑；仍防御性检查是否写完
        age = time.time() - bdir.stat().st_mtime
        if age < 120:
            logger.info(f"备份目录刚更新（{age:.0f}s），本轮跳过，下轮再抓: {bdir.name}")
            continue

        entry_files = {}
        failed = False
        for src in files:
            try:
                data = read_source_stable(src)
                dest = DATABASE_ROOT / bdir.name / src.name
                h1, h2 = archive_bytes(data, dest, args.dry_run)
            except Exception as e:
                alert("ERROR", f"数据库备份归档失败: {bdir.name}/{src.name} -> {e}")
                failed = True
                break

            verify = "MATCH" if h1 == h2 else "MISMATCH"
            if verify != "MATCH":
                alert("CRITICAL", f"数据库备份校验不一致: {dest}")
                failed = True
                break

            entry_files[src.name] = {"size": len(data), "sha256": h1}
            manifest.append([
                str(src.relative_to(SRC_MOUNT)), str(src), str(dest),
                "NEW", len(data), fmt_mtime(src), h1, h2,
                "Match" if verify == "MATCH" else "Mismatch",
            ])
            logger.info(f"已归档: {bdir.name}/{src.name} ({len(data)/1048576:.1f} MB)")

        if failed:
            stats["failed"] += 1
            continue

        reg[bdir.name] = {"status": "ARCHIVED", "archived_at": NOW_STR, "files": entry_files}
        stats["new"] += 1

    # 健康信号：Database 备份每晚固定跑，与做不做样品无关。
    # 样品数据可以合理地空好几周，用它做告警只会天天误报。
    if newest_mtime > 0:
        hours = (time.time() - newest_mtime) / 3600.0
        stats["newest_age_hours"] = round(hours, 1)
        if hours > DB_STALE_HOURS:
            alert("WARNING",
                  f"最新数据库备份已 {hours:.1f} 小时未更新（阈值 {DB_STALE_HOURS}h）。"
                  f"FLEX2 可能关机、备份任务停止或共享异常")

    return stats


# =========================================================
# 采集：逐次 CSV（冷备，默认关闭）
# =========================================================
def ingest_per_event(state: Dict[str, Any], args, manifest: List[List[Any]]) -> Dict[str, int]:
    stats = {"checked": 0, "new": 0, "unchanged": 0, "failed": 0}
    if not args.per_event:
        return stats

    reg = state.setdefault("per_event", {})
    try:
        entries = sorted(p for p in SRC_RESULTS.iterdir() if p.is_file())
    except Exception as e:
        alert("ERROR", f"无法列出 {SRC_RESULTS}: {e}")
        stats["failed"] += 1
        return stats

    for src in entries:
        m = PEREVENT_RE.match(src.name)
        if not m:
            continue
        stats["checked"] += 1

        if src.name in reg:
            stats["unchanged"] += 1
            continue

        try:
            data = read_source_stable(src)
            dest = (RESULTS_ROOT / "PerEvent" / f"{m.group('year')}-{m.group('mm')}" / src.name)
            h1, h2 = archive_bytes(data, dest, args.dry_run)
        except Exception as e:
            alert("ERROR", f"逐次文件归档失败: {src.name} -> {e}")
            stats["failed"] += 1
            continue

        verify = "MATCH" if h1 == h2 else "MISMATCH"
        if verify != "MATCH":
            alert("CRITICAL", f"归档校验不一致: {dest}")
            stats["failed"] += 1
            continue

        ok, rows, note = validate_csv(data, src.name)
        if not ok:
            logger.warning(f"逐次文件结构异常（已归档，仅记录）: {src.name} -> {note}")

        reg[src.name] = {"sha256": h1, "size": len(data), "archived_at": NOW_STR}
        stats["new"] += 1
        manifest.append([
            str(src.relative_to(SRC_MOUNT)), str(src), str(dest),
            "NEW", len(data), fmt_mtime(src), h1, h2,
            "Match" if verify == "MATCH" else "Mismatch",
        ])

    return stats


# =========================================================
# 主程序
# =========================================================
def main() -> int:
    ap = argparse.ArgumentParser(description="FLEX2 Stage 1 采集与校验")
    ap.add_argument("--backfill", action="store_true",
                    help="回填所有月份（默认只处理当月+上月）")
    ap.add_argument("--per-event", action="store_true",
                    help="同时归档逐次导出文件（冷备，默认不抓）")
    ap.add_argument("--dry-run", action="store_true",
                    help="只探测和校验，不写入 NAS")
    args = ap.parse_args()

    log_file = LOG_DIR / f"{MACHINE_NAME}_ingest_{RUN_TAG}.log" if is_mounted(NAS_MOUNT) else None
    setup_logger(log_file)

    logger.info("=" * 60)
    logger.info(f"{SCRIPT_NAME} {SCRIPT_VERSION} ({SCRIPT_RELEASE_DATE}) owner={SCRIPT_OWNER}")
    logger.info(f"machine={MACHINE_NAME}  analyzer_id={ANALYZER_ID}")
    logger.info(f"src={SRC_MOUNT}  nas={NAS_MOUNT}")
    logger.info(f"mode: backfill={args.backfill} per_event={args.per_event} dry_run={args.dry_run}")
    logger.info("=" * 60)

    preflight()

    state = load_state()
    manifest: List[List[Any]] = []

    m_stats = ingest_monthly(state, args, manifest)
    d_stats = ingest_database(state, args, manifest)
    p_stats = ingest_per_event(state, args, manifest)

    write_compare(manifest, args.dry_run)

    total_failed = m_stats["failed"] + d_stats["failed"] + p_stats["failed"]
    run_status = "SUCCESS" if total_failed == 0 else "FAILED"

    state.update({
        "script_name": SCRIPT_NAME,
        "script_version": SCRIPT_VERSION,
        "script_release_date": SCRIPT_RELEASE_DATE,
        "machine_name": MACHINE_NAME,
        "analyzer_id": ANALYZER_ID,
        "source": str(SRC_MOUNT),
        "nas_target": str(ARCHIVE_ROOT),
        "last_run_time": NOW_STR,
        "last_status": run_status,
        "last_success_time": NOW_STR if run_status == "SUCCESS" else state.get("last_success_time", ""),
        "stats_monthly": m_stats,
        "stats_database": d_stats,
        "stats_per_event": p_stats,
        "updated_at": NOW_STR,
    })

    if not args.dry_run:
        for p in (LOCAL_STATE_FILE, STATE_FILE):
            try:
                save_json_atomic(p, state)
                logger.info(f"状态已写入: {p}")
            except Exception as e:
                logger.warning(f"状态写入失败 {p}: {e}")

    logger.info("-" * 60)
    logger.info(f"SUMMARY | monthly   : {m_stats}")
    logger.info(f"SUMMARY | database  : {d_stats}")
    logger.info(f"SUMMARY | per_event : {p_stats}")
    logger.info(f"SUMMARY | status    : {run_status}")
    logger.info("-" * 60)

    if run_status != "SUCCESS":
        alert("ERROR", f"本轮采集有 {total_failed} 项失败，详见日志 {log_file}")
        return 1
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except SystemExit:
        raise
    except KeyboardInterrupt:
        sys.exit(130)
    except Exception as exc:
        logging.basicConfig()
        logger.exception("未捕获异常")
        alert("CRITICAL", f"{SCRIPT_NAME} 异常终止: {exc}")
        sys.exit(4)
