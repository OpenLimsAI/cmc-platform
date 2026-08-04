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

数据源策略（2026-07-15 实测建立，2026-07-23 全量核对后修正）：
  - 月度 CSV = 主数据源，整月持续追加 → 每次内容变化存一份带时间戳的快照
  - Database\\Backup_* = 每晚覆盖，只留一份 → 必须每天抓，否则历史永久丢失
  - 逐次 CSV = **不是月度的冗余，必须一并归档**（--per-event，日常常开）
    ⚠️ 早期文档写过"月度是逐次的严格超集"，**那是错的**。7704 行全量核对结论：
    逐次独有 810 条错位行的中段检测值（月度里因通道省略而丢失、无法还原），
    月度独有试剂批号列。两者互补，谁也替代不了谁。详见 docs/source-survey-flex2.md §8

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
from collections import Counter
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple

# =========================================================
# 版本信息（变更控制用，改动逻辑请同步递增）
# =========================================================
SCRIPT_NAME = "flex2_ingest"
SCRIPT_VERSION = "v1.4.0"
SCRIPT_RELEASE_DATE = "2026-08-05"
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

# ---- 心跳（MD-005）----
# 心跳解决的是"程序根本没跑，而且不会有任何信号"这种失效：timer 被禁、服务启动失败、
# 凭据过期都不会触发任何告警。有了它，"跑了但失败"与"根本没跑"才能被区分开。
# 本机排 02:00 / 11:45 / 16:00 一天三趟，最长间隔是 16:00→次日 02:00 的 10 小时，取整 12。
HEARTBEAT_ENABLED = os.environ.get("FLEX2_HEARTBEAT_ENABLED", "1").strip() not in ("0", "false", "False", "")
EXPECTED_INTERVAL_HOURS = float(os.environ.get("FLEX2_EXPECTED_INTERVAL_HOURS", "12"))
MAX_SILENCE_HOURS = float(os.environ.get("FLEX2_MAX_SILENCE_HOURS", str(EXPECTED_INTERVAL_HOURS * 3)))

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

# 心跳模块是所有仪器共用的，住在 tools/（不在本目录，别去 flex2/ 里找）
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))
try:
    from heartbeat import write_heartbeat  # noqa: E402
except Exception:  # pragma: no cover - 心跳缺失绝不能让备份跑不起来
    write_heartbeat = None

# 本次运行各级别告警计数，写进心跳供巡检看（与 Vi-CELL 的 alerts 字段对齐）
ALERT_COUNTS: Dict[str, int] = {}


def emit_heartbeat(status: str, processed: int, failed: int) -> None:
    """
    写心跳。**绝不抛异常、绝不改变退出码**——心跳是观测手段，不是业务逻辑。

    dry-run 不写：空跑不代表真备份过，写了会让巡检误以为一切正常。
    """
    if not HEARTBEAT_ENABLED or write_heartbeat is None:
        return
    try:
        write_heartbeat(
            machine_name=MACHINE_NAME, script_name=SCRIPT_NAME,
            software_version=SCRIPT_VERSION, run_tag=RUN_TAG,
            started_at=RUN_DT.timestamp(), backup_status=status,
            files_processed=processed, files_failed=failed,
            alerts=dict(ALERT_COUNTS),
            expected_interval_hours=EXPECTED_INTERVAL_HOURS,
            max_silence_hours=MAX_SILENCE_HOURS,
            nas_state_dir=STATE_DIR, local_state_dir=LOCAL_STATE_DIR,
            log=logger,
        )
    except Exception as e:
        logger.warning(f"心跳写入异常（已忽略，不影响备份）: {e}")


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
    # 计数写进心跳，让巡检不用翻日志就知道这一趟出过几条、什么级别的告警。
    # 级别拼法历史上有 WARN / WARNING 两种，这里归一，免得心跳里出现两个键。
    key = "WARNING" if str(level).upper() in ("WARN", "WARNING") else str(level).upper()
    ALERT_COUNTS[key] = ALERT_COUNTS.get(key, 0) + 1
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
        # 预检失败也必须写心跳：否则"挂载坏了"与"程序根本没跑"在巡检看来完全一样，
        # 而这正是心跳要区分的两件事（Vi-CELL v1.4.0 测试时踩过同一个坑）。
        emit_heartbeat("FAILED", 0, 1)
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
        emit_heartbeat("FAILED", 0, 1)
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


def validate_csv(data: bytes, name: str) -> Tuple[bool, int, str, Optional[str]]:
    """
    归档层结构校验：只判断"文件是否完整、可读"，不要求业务结构规整。
    返回 (可否归档, 数据行数, 说明, 告警消息或None)

    设计原则（2026-07-16 定，见 CLAUDE.md 铁律 1/5）：
    归档的天职是忠实保存底本。FLEX2 月度文件实测存在"同一文件内多种行宽"——
    某些样品未测的通道不留空占位、直接省略，使该行变短（套餐化，非损坏）。
    这类是完好数据，必须照常归档；只在检测到多行宽 / 行宽≠表头 / BOM 时**告警**
    （守铁律 1：变化必告警、不静默吞），交由 Stage 2 按套餐解析。
    只有真正损坏（非 UTF-8、无法解析、空文件、只有表头）才拒绝归档（铁律 5）。

    注意：FLEX2 每行尾部都有一个多余逗号，会产生一个空列，属正常现象。
    """
    try:
        text = data.decode("utf-8", errors="strict")
    except UnicodeDecodeError as e:
        return False, 0, f"UTF-8 解码失败（疑似损坏）: {e}", None

    if text.startswith("\ufeff"):
        had_bom = True
    else:
        had_bom = False

    try:
        rows = list(csv.reader(StringIO(text)))
    except Exception as e:
        return False, 0, f"CSV 无法解析（疑似损坏）: {e}", None

    if not rows:
        return False, 0, "空文件", None

    header_len = len(rows[0])
    data_rows = [r for r in rows[1:] if any(c.strip() for c in r)]
    if not data_rows:
        return False, 0, "只有表头、无数据行", None

    # 行宽分布：不再据此拒绝归档，只在异常时告警（守铁律 1，忠实保存底本）
    widths = Counter(len(r) for r in data_rows)
    notes: List[str] = []
    warn: Optional[str] = None
    if len(widths) > 1:
        dist = ", ".join(f"{w}列×{n}" for w, n in sorted(widths.items()))
        notes.append("多行宽")
        warn = (f"文件内存在多种行宽（{dist}；表头 {header_len} 列）——"
                f"疑为未测通道未留空占位的套餐化数据；已归档，ETL 需按行宽分套餐解析")
    elif next(iter(widths)) != header_len:
        w = next(iter(widths))
        notes.append("行宽≠表头")
        warn = f"数据行宽 {w} 与表头 {header_len} 不一致（单一套餐）；已归档，ETL 需注意"
    if had_bom:
        notes.append("BOM")
        warn = ((warn + "；") if warn else "") + "文件带 BOM（导出行为可能变更，请留意）"

    return True, len(data_rows), ("OK" if not notes else "; ".join(notes)), warn


def archive_bytes(data: bytes, dest: Path, dry_run: bool) -> Tuple[str, str]:
    """
    原子写入 NAS 并回读校验。
    返回 (源 hash, 归档 hash)。二者一致才算归档成功。
    """
    h1 = sha256_bytes(data)
    if dry_run:
        return h1, h1

    # ---- append-only 守卫（2026-08-05 加）----
    # 归档区 append-only 这条铁律，原来完全靠 state 记账来保证：state 说"没归档过"
    # 就直接写。可是 state 丢了、回退了、或读到旧副本时，NAS 上明明已有同名文件，
    # 底本就会被静默覆盖——没有 .rev 快照、没有告警，谁也发现不了。
    # 这道守卫直接问 NAS 本身，不依赖任何记账，所以 state 出问题也仍然成立。
    if dest.exists():
        try:
            existing = sha256_file(dest)
        except Exception as e:
            logger.warning(f"已存在的归档无法回读校验（继续按新文件处理）: {dest} ({e})")
            existing = None
        if existing == h1:
            # 内容完全一样：不必重写，省一次 NAS 往返，也避免无谓改动底本
            logger.info(f"归档已存在且内容一致，跳过写入: {dest.name}")
            return h1, existing
        if existing is not None:
            stem, ext = os.path.splitext(dest.name)
            dest = dest.with_name(f"{stem}.rev{RUN_TAG}{ext}")
            alert("CRITICAL",
                  f"归档区已有同名文件且内容不同，但记账里没有它——state 可能丢失或回退。"
                  f"已另存版本快照、原件保留: {dest.name}")

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

        ok, rows, note, warn = validate_csv(data, src.name)
        if not ok:
            # 只有真损坏（非 UTF-8/无法解析/空）才不归档（铁律 5）
            alert("ERROR", f"月度文件疑似损坏，未归档: {src.name} -> {note}")
            stats["failed"] += 1
            continue
        if warn:
            # 结构异常但完好（多行宽/BOM 等）：照常归档，只告警（铁律 1，不静默吞）
            alert("WARNING", f"月度文件结构提示（已归档）: {src.name} -> {warn}")

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

        # 备份约 23:30 跑，任务 02:00 跑；仍防御性检查是否写完
        age = time.time() - bdir.stat().st_mtime
        if age < 120:
            logger.info(f"备份目录刚更新（{age:.0f}s），本轮跳过，下轮再抓: {bdir.name}")
            continue

        # ⚠️ 空目录绝不能记账（2026-08-05 加）。原来 files 为空时下面的 for 循环
        # 直接不执行，failed 保持 False，于是走到最后写下 status: ARCHIVED、files: {}，
        # 这个目录从此被永久跳过——哪怕备份程序后来把文件补进去也再不会抓。
        # 目录建了却是空的，本身就说明备份任务没跑成，该报警而不是记完成。
        if not files:
            alert("WARNING", f"备份目录是空的，本次不记账（备份任务可能中途失败）: {bdir.name}")
            stats["failed"] += 1
            continue

        prev = reg.get(bdir.name) or {}
        prev_files: Dict[str, Any] = prev.get("files") or {}
        if prev.get("status") == "ARCHIVED":
            # 不再无条件跳过：核对一下源端文件名单，看有没有归档之后才出现的文件。
            # 备份分两次写完、或上次抓的时候还缺文件，都会落到这里。
            missing = [p for p in files if p.name not in prev_files]
            if not missing:
                stats["unchanged"] += 1
                logger.info(f"已归档过，跳过: {bdir.name}（{len(prev_files)} 个文件）")
                continue
            alert("WARNING",
                  f"已归档的备份目录又出现 {len(missing)} 个新文件，补抓: {bdir.name} "
                  f"({', '.join(p.name for p in missing[:5])})")
            files = missing   # 只补新增的，已归档的不重读、不覆盖

        entry_files = dict(prev_files)   # 保留已归档的记账，补抓时不能丢
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

        ok, rows, note, warn = validate_csv(data, src.name)
        if not ok:
            logger.warning(f"逐次文件疑似损坏（已归档，仅记录）: {src.name} -> {note}")
        elif warn:
            logger.info(f"逐次文件结构提示: {src.name} -> {warn}")

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

    # 心跳放在告警之后：这样这一趟的告警计数是完整的。
    # dry-run 不写——空跑没有真备份，写了会让巡检误以为一切正常。
    if not args.dry_run:
        processed = (m_stats.get("new_snapshot", 0) + d_stats.get("new", 0)
                     + p_stats.get("new", 0))
        emit_heartbeat(run_status, processed, total_failed)

    return 1 if run_status != "SUCCESS" else 0


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
        # 崩溃也要写心跳：否则这次运行在巡检看来等于"从没跑过"，
        # 而"崩了"与"没跑"的处置完全不同——这正是心跳存在的意义。
        emit_heartbeat("FAILED", 0, 1)
        sys.exit(4)
