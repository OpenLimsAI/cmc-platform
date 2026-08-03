#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
vicell_ingest.py — Stage 1：Beckman Vi-CELL XR 数据采集与校验

职责（只做这三件事，不做 ETL）：
  1. 从 Vi-CELL 工作站的只读挂载点发现新增/变化的文件
  2. 复制到 NAS 原始归档区
  3. SHA-256 双向校验（读取即算 h1，回读归档算 h2，比对）

设计原则（与 flex2_ingest.py 完全一致）：
  - 只读源：绝不写入仪器侧
  - 幂等：可重复执行，不会重复归档相同内容
  - 解耦：本程序不解析业务字段、不入库。ETL 由 Stage 2 从 NAS 读取
  - 原子：先写临时文件再 rename，避免半截文件被 ETL 读到

数据源事实（2026-08-03 实机勘察确认，详见 docs/source-survey-vicell.md）：
  - 工作站 C4V61257XH = 10.0.13.36，Win7，**只支持 SMB 2.1**（vers=2.1，不是 3.0）
  - 共享 //10.0.13.36/Vi-Cell$  =  E:\\Vi-Cell，下有 Data / Export / Images
  - Data(.txt) 与 Export(.xls) **时间段互补，谁都不是谁的超集，必须都抓**
      Export 覆盖 2021-08→2025-09 与 2026-03→今；Data 覆盖 2024-12→今
      2025-10…2026-02 这五个月**源头就只有 .txt 没有 .xls**（已核对旧目录，非文件丢失）
  - 每个样品一个文件，写完即不再变（immutable）→ 已归档的按文件名跳过，不重算哈希
  - Images/<SampleID>/*.tif，每样品固定 50 张；样品图片目录一旦生成即不再变
      → 增量只比对"目录名单"，不钻进已归档目录（这是日常性能的关键）
      ⚠️ 判断新目录**必须靠目录名，不能靠 mtime**：实测 mtime 被搬文件夹刷掉过

依赖：Python 3.8+，仅标准库
"""

import os
import sys
import json
import time
import shutil
import hashlib
import logging
import argparse
import subprocess
import datetime as dt
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
from concurrent.futures import ThreadPoolExecutor, as_completed

# =========================================================
# 版本信息（变更控制用，改动逻辑请同步递增并更新 CHANGELOG.md）
# =========================================================
SCRIPT_NAME = "vicell_ingest"
SCRIPT_VERSION = "v1.2.0"
SCRIPT_RELEASE_DATE = "2026-08-03"
SCRIPT_OWNER = "TT Lab"

# =========================================================
# 配置（全部可用环境变量覆盖，见 vicell-ingest.env.example）
# =========================================================
# 机器名沿用 NAS 既有约定 <主机名>_<厂商简称>，与 Daily/ 下现有目录一致
MACHINE_NAME = os.environ.get("VICELL_MACHINE_NAME", "C4V61257XH_ViCell")

SRC_MOUNT = Path(os.environ.get("VICELL_SRC_MOUNT", "/mnt/vicell"))
NAS_MOUNT = Path(os.environ.get("VICELL_NAS_MOUNT", "/mnt/ttlab-backups"))

# 是否归档图片。图片量大（每样品约 61 MB），首次回补耗时长，可单独关闭。
ARCHIVE_IMAGES = os.environ.get("VICELL_ARCHIVE_IMAGES", "1").strip() not in ("0", "false", "False", "")

# 单次运行最多归档多少个图片目录（0 = 不限）。用于把首次回补拆成多次跑，避免一次占满窗口。
IMAGE_DIR_LIMIT = int(os.environ.get("VICELL_IMAGE_DIR_LIMIT", "0"))

# 每个样品图片目录期望的图片数；实测恒为 50。数量对不上只告警、照常归档（对齐 FLEX2 铁律 5）。
EXPECTED_TIF_PER_SAMPLE = int(os.environ.get("VICELL_EXPECTED_TIF", "50"))

# 图片复制的并发线程数。
# 实测瓶颈不是带宽（仪器读 14 MB/s、NAS 写 103 MB/s），而是**每个文件的往返延迟**：
# 一个文件要走"读源 → 写临时 → fsync → 改时间 → rename → 回读校验"，
# 1.2 MB 的小文件里延迟占了大头，串行时链路利用率极低（实测仅约 2 MB/s）。
# 每个文件彼此独立，用线程池并发即可把延迟叠掉。别开太大——对面是台 Win7。
COPY_WORKERS = int(os.environ.get("VICELL_COPY_WORKERS", "6"))

# 告警命令：以 ALERT_CMD "<级别>" "<消息>" 调用，可对接企业微信/邮件
ALERT_CMD = os.environ.get("VICELL_ALERT_CMD", "").strip()

# 读取源文件时，若 stat 在读取前后变化则重试（防止读到正在写入的半截文件）
STABLE_RETRIES = int(os.environ.get("VICELL_STABLE_RETRIES", "4"))
STABLE_WAIT_SEC = float(os.environ.get("VICELL_STABLE_WAIT_SEC", "3"))

CHUNK = 1024 * 1024

# =========================================================
# 派生路径
# =========================================================
SRC_DATA = SRC_MOUNT / "Data"        # 每样品一个 .txt（外加 2 个 .ctl 质控品批次文件）
SRC_EXPORT = SRC_MOUNT / "Export"    # 每样品一个 .xls（真 Excel 二进制 CDFV2）
SRC_IMAGES = SRC_MOUNT / "Images"    # Images/<SampleID>/*.tif

# 归档根：对齐 NAS 既有约定 Daily/<机器名>/，子目录名沿用已存在的小写形式
ARCHIVE_ROOT = NAS_MOUNT / "Daily" / MACHINE_NAME
DATA_ROOT = ARCHIVE_ROOT / "data"
EXPORT_ROOT = ARCHIVE_ROOT / "export"
IMAGES_ROOT = ARCHIVE_ROOT / "images"
LEGACY_ROOT = ARCHIVE_ROOT / "legacy"    # 历史遗留目录，按来源目录名分开存
CONFIG_ROOT = ARCHIVE_ROOT / "config"    # 仪器配置与审计追踪

# 历史图片的原始位置（D 盘）。软件当年真正写入的地方，E:\Vi-Cell\Images 里那 1602 个
# 是 2026-07 搬文件夹时的人工副本。已全量核对：1602 个目录的文件名/大小/修改时间全等，
# 随机 40 个目录 2000 个文件逐个 SHA-256 全部一致（2026-08-03）。
# 内容既然相同，就取来源更干净的那一份——归档记录里写"取自原始位置"更经得起问。
IMAGES_ORIGIN = Path(os.environ.get("VICELL_IMAGES_ORIGIN", "/mnt/vicell-old/dimg"))

# 历史遗留目录：(挂载点, 归档子目录名, 类型)
#   samples = 下面一层是样品目录，每个目录里是图片
#   flat    = 平铺的文件
LEGACY_MOUNT = Path(os.environ.get("VICELL_LEGACY_MOUNT", "/mnt/vicell-old"))
LEGACY_SOURCES = [
    (LEGACY_MOUNT / "img2025", "XR-2025.04.27", "samples"),
    (LEGACY_MOUNT / "img2024", "2025.5.14HEK-293计数图片", "samples"),
    (LEGACY_MOUNT / "img2023", "1111", "samples"),
    (LEGACY_MOUNT / "history", "计数仪历史数据", "flat"),
]

# 仪器配置与审计追踪：只取 E:\ViCELLXR 根目录下的文件，
# 不碰它的 Data\ / Excel\ 子目录（那是搬家前的旧导出，已被现用目录完整包含）
CONFIG_SOURCE = Path(os.environ.get("VICELL_CONFIG_SOURCE", "/mnt/vicell-old/app"))

# 记账目录：NAS 根级按机器名分，与其它设备完全一致
STATE_DIR = NAS_MOUNT / "State"
CHECKSUM_DIR = NAS_MOUNT / "Checksums" / MACHINE_NAME
LOG_DIR = NAS_MOUNT / "Logs" / MACHINE_NAME

STATE_FILE = STATE_DIR / f"{MACHINE_NAME}_backup_state.json"

# 本地状态副本（NAS 不可达时仍留痕）
LOCAL_STATE_DIR = Path(os.environ.get("VICELL_LOCAL_STATE_DIR", "/var/lib/vicell-ingest"))
LOCAL_STATE_FILE = LOCAL_STATE_DIR / f"{MACHINE_NAME}_backup_state.json"

RUN_DT = dt.datetime.now()
RUN_TAG = RUN_DT.strftime("%Y%m%d_%H%M%S")
NOW_STR = RUN_DT.strftime("%Y-%m-%d %H:%M:%S")

VERSION_TAG = SCRIPT_VERSION.replace(".", "_")
COMPARE_FILE = CHECKSUM_DIR / f"{MACHINE_NAME}_SHA256_Compare_{VERSION_TAG}_{RUN_TAG}.csv"
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


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(CHUNK), b""):
            h.update(chunk)
    return h.hexdigest()


def fmt_mtime(path: Path) -> str:
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
    """挂载检查 + 只读自验。CIFS 断链是常态，静默跳过比报错危险得多。"""
    problems = []

    if not is_mounted(SRC_MOUNT):
        problems.append(f"源未挂载: {SRC_MOUNT}")
    else:
        for d in (SRC_DATA, SRC_EXPORT):
            if not d.is_dir():
                problems.append(f"源挂载但结构异常，找不到: {d}")

    if not is_mounted(NAS_MOUNT):
        problems.append(f"NAS 未挂载: {NAS_MOUNT}")

    if problems:
        alert("CRITICAL", "预检失败 -> " + "; ".join(problems))
        raise SystemExit(2)

    # 铁律 2：源必须只读。可写说明 ro 没生效，属配置事故，宁可停也不冒险。
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
        alert("CRITICAL", f"源挂载点 {SRC_MOUNT} 可写！ro 未生效，已中止以保护仪器数据")
        raise SystemExit(3)


def read_source_stable(path: Path) -> bytes:
    """读取源文件并确保读取期间没被改写。仪器正在写的样品文件可能读到半截。"""
    last_err = None
    for attempt in range(1, STABLE_RETRIES + 1):
        try:
            st1 = path.stat()
            with open(path, "rb") as f:
                data = f.read()
            st2 = path.stat()
            if (st1.st_size, st1.st_mtime_ns) == (st2.st_size, st2.st_mtime_ns) and len(data) == st2.st_size:
                return data
            logger.info(f"读取期间文件发生变化，重试 {attempt}/{STABLE_RETRIES}: {path.name}")
        except Exception as e:
            last_err = e
            logger.info(f"读取失败，重试 {attempt}/{STABLE_RETRIES}: {path.name} ({e})")
        time.sleep(STABLE_WAIT_SEC)
    raise IOError(f"源文件读取不稳定，放弃: {path} ({last_err})")


def write_atomic(dest: Path, data: bytes, mtime: Optional[float] = None) -> None:
    """
    先写临时文件再 rename，避免 ETL 读到半截文件。

    传入 mtime 时把源文件的修改时间一并带过去（在 rename 前设，保证原子）。
    这很重要：Vi-CELL 的样品文件修改时间 == 文件内部的 FileDate（已抽查核实），
    是有溯源价值的元数据，归档副本不该被写成"归档那天"。
    """
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.parent / f".{dest.name}.{os.getpid()}.tmp"
    try:
        with open(tmp, "wb") as f:
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
        if mtime is not None:
            try:
                os.utime(tmp, (mtime, mtime))
            except Exception as e:
                logger.warning(f"设置修改时间失败（继续归档）: {dest.name} ({e})")
        os.replace(str(tmp), str(dest))
    finally:
        if tmp.exists():
            try:
                tmp.unlink()
            except Exception:
                pass


# =========================================================
# 状态文件
# =========================================================
def load_state() -> Dict[str, Any]:
    for f in (STATE_FILE, LOCAL_STATE_FILE):
        try:
            if f.is_file():
                with open(f, "r", encoding="utf-8") as fh:
                    st = json.load(fh)
                logger.info(f"读取状态文件: {f}")
                return st
        except Exception as e:
            logger.warning(f"状态文件读取失败 {f}: {e}")
    logger.info("未找到状态文件，按首次运行处理")
    return {}


def default_state() -> Dict[str, Any]:
    return {
        "machine_name": MACHINE_NAME,
        "script_version": SCRIPT_VERSION,
        "last_run": "",
        # 文件名 -> {sha256, size, archived_at}
        "data_files": {},
        "export_files": {},
        # 图片目录名 -> {tif_count, archived_at}
        "image_dirs": {},
    }


def save_state(state: Dict[str, Any], dry_run: bool) -> None:
    state["machine_name"] = MACHINE_NAME
    state["script_version"] = SCRIPT_VERSION
    state["last_run"] = NOW_STR
    if dry_run:
        logger.info("[dry-run] 跳过状态文件写入")
        return
    payload = json.dumps(state, ensure_ascii=False, indent=2, sort_keys=True).encode("utf-8")
    for f in (STATE_FILE, LOCAL_STATE_FILE):
        try:
            write_atomic(f, payload)
        except Exception as e:
            logger.warning(f"状态文件写入失败 {f}: {e}")


# =========================================================
# 归档：单文件（Data / Export）
# =========================================================
def archive_flat_dir(
    src_dir: Path,
    dest_dir: Path,
    state_key: str,
    state: Dict[str, Any],
    suffixes: Tuple[str, ...],
    dry_run: bool,
    compare_rows: List[List[str]],
) -> Dict[str, int]:
    """
    归档一个平铺目录（Data 或 Export）。

    样品文件是 immutable 的：一旦写出就不再改。所以已在状态里的文件名直接跳过，
    不重新读、不重算哈希——这是日常跑得快的关键。
    若同名文件内容变了（哈希不一致），说明历史被改写，属异常：告警并另存带时间戳的版本，
    绝不覆盖已归档的底本（raw 层 append-only）。
    """
    stats = {"new": 0, "skip": 0, "changed": 0, "error": 0}
    known: Dict[str, Any] = state.setdefault(state_key, {})

    if not src_dir.is_dir():
        logger.warning(f"源目录不存在，跳过: {src_dir}")
        return stats

    names = sorted(
        p.name for p in src_dir.iterdir()
        if p.is_file() and p.suffix.lower() in suffixes
    )
    logger.info(f"{src_dir.name}: 源端 {len(names)} 个文件，已归档 {len(known)} 个")

    for name in names:
        src = src_dir / name
        rec = known.get(name)

        try:
            st = src.stat()
        except Exception as e:
            logger.warning(f"stat 失败，跳过: {name} ({e})")
            stats["error"] += 1
            continue

        # 已归档且大小一致 -> 认定未变，跳过（不读文件）
        if rec and rec.get("size") == st.st_size:
            stats["skip"] += 1
            continue

        # dry-run 只报清单，不读内容：否则首跑要把上千兆经 SMB 拉一遍才肯出结果
        if dry_run:
            ct = "CHANGED" if rec else "NEW"
            stats["changed" if rec else "new"] += 1
            logger.info(f"[dry-run] 将归档 {ct}: {src_dir.name}/{name} ({st.st_size} bytes)")
            compare_rows.append([
                f"{src_dir.name}/{name}", str(src), str(dest_dir / name), ct,
                str(st.st_size), fmt_mtime(src), "", "", "DRY_RUN",
            ])
            continue

        try:
            data = read_source_stable(src)
        except Exception as e:
            alert("WARN", f"读取失败: {src_dir.name}/{name} ({e})")
            stats["error"] += 1
            continue

        h_src = hashlib.sha256(data).hexdigest()

        if rec and rec.get("sha256") == h_src:
            # 大小变了但内容一样（几乎不可能），当作已归档
            known[name] = {"sha256": h_src, "size": len(data), "archived_at": rec.get("archived_at", NOW_STR)}
            stats["skip"] += 1
            continue

        change_type = "NEW"
        dest = dest_dir / name
        if rec:
            # 历史被改写：另存版本快照并告警，不覆盖底本
            change_type = "CHANGED"
            stem, ext = os.path.splitext(name)
            dest = dest_dir / f"{stem}.rev{RUN_TAG}{ext}"
            alert("WARN", f"历史文件内容发生变化，已另存版本快照: {src_dir.name}/{name} -> {dest.name}")
            stats["changed"] += 1
        else:
            stats["new"] += 1

        try:
            write_atomic(dest, data, mtime=st.st_mtime)
            h_nas = sha256_file(dest)
        except Exception as e:
            alert("CRITICAL", f"归档写入失败: {src_dir.name}/{name} ({e})")
            stats["error"] += 1
            continue

        ok = (h_nas == h_src)
        compare_rows.append([
            f"{src_dir.name}/{name}", str(src), str(dest), change_type,
            str(len(data)), fmt_mtime(src), h_src, h_nas, "MATCH" if ok else "MISMATCH",
        ])

        if not ok:
            # 校验不过就不算归档（铁律 5）：删掉坏副本、不写状态，下次重来
            alert("CRITICAL", f"SHA256 校验不一致，已删除坏副本: {dest}")
            try:
                dest.unlink()
            except Exception:
                pass
            stats["error"] += 1
            continue

        known[name] = {"sha256": h_src, "size": len(data), "archived_at": NOW_STR}

    return stats


# =========================================================
# 归档：图片目录（Images）
# =========================================================
def archive_sample_dirs(
    sources: List[Path],
    dest_root: Path,
    state_key: str,
    label: str,
    state: Dict[str, Any],
    dry_run: bool,
    compare_rows: List[List[str]],
    limit: int,
) -> Dict[str, int]:
    """
    归档"一层样品目录、每个目录里是图片"这种结构。

    `sources` 按**优先级**排列：样品名在多个源里都有时，取排在前面的那个。
    用于主图片集——1602 个历史样品取自 D 盘原始位置 `D:\\Vi-Cell 计数图像`，
    其余（2026-07 之后新产生的）取自现用的 `E:\\Vi-Cell\\Images`。
    两边内容已全量核对一致，选 D 盘只是为了归档记录里的来源更干净。

    增量只比对"目录名单"，已归档的目录连打开都不打开。
    依据：一个样品的图片是那次运行拍下的，之后不再增删。
    ⚠️ 判断"新目录"只能靠目录名——实测目录 mtime 被搬文件夹刷成了搬迁当天，完全不可信。
    """
    stats = {"new_dirs": 0, "skip_dirs": 0, "files": 0, "error": 0}
    known: Dict[str, Any] = state.setdefault(state_key, {})

    live = [s for s in sources if s.is_dir()]
    if not live:
        logger.warning(f"{label}: 源目录都不存在，跳过（{', '.join(str(s) for s in sources)}）")
        return stats

    # 样品名 -> 实际取用的源目录（按优先级，先到先得）
    origin: Dict[str, Path] = {}
    for s in live:
        try:
            for p in s.iterdir():
                if p.is_dir() and p.name not in origin:
                    origin[p.name] = s
        except Exception as e:
            alert("WARN", f"{label}: 列目录失败 {s} ({e})")

    all_dirs = sorted(origin)
    todo = [d for d in all_dirs if d not in known]
    stats["skip_dirs"] = len(all_dirs) - len(todo)
    src_note = "  ".join(f"{s.name}:{sum(1 for v in origin.values() if v == s)}" for s in live)
    logger.info(f"{label}: 源端 {len(all_dirs)} 个样品目录（来源分布 {src_note}），"
                f"已归档 {stats['skip_dirs']} 个，待归档 {len(todo)} 个")

    if limit > 0 and len(todo) > limit:
        logger.info(f"本次限量 {limit} 个目录（共 {len(todo)} 个待归档），其余下次继续")
        todo = todo[:limit]

    if dry_run:
        # 不逐个进目录点数：那是 len(todo) 次 SMB 往返，首跑要几分钟才肯出结果。
        # 真跑时反正要进去复制，那时再校验张数。
        stats["new_dirs"] = len(todo)
        stats["files"] = len(todo) * EXPECTED_TIF_PER_SAMPLE
        logger.info(f"[dry-run] {label}: 将归档 {len(todo)} 个目录，约 {stats['files']} 个文件"
                    f"（按每样品 {EXPECTED_TIF_PER_SAMPLE} 张估算，未逐目录核实）")
        return stats

    for dname in todo:
        sdir = origin[dname] / dname
        ddir = dest_root / dname
        try:
            files = sorted(p.name for p in sdir.iterdir() if p.is_file())
        except Exception as e:
            alert("WARN", f"列样品图片目录失败，跳过: {dname} ({e})")
            stats["error"] += 1
            continue

        if EXPECTED_TIF_PER_SAMPLE and len(files) != EXPECTED_TIF_PER_SAMPLE:
            # 只告警、照常归档（铁律 5：结构异常不等于损坏，不能因此丢数据）
            alert("WARN", f"样品图片数异常（期望 {EXPECTED_TIF_PER_SAMPLE}，实际 {len(files)}）: {dname}")

        def _copy_one(fname: str) -> Tuple[str, Optional[List[str]], Optional[str]]:
            """复制+校验单个文件。返回 (文件名, 比对行 or None, 错误信息 or None)。"""
            src = sdir / fname
            dest = ddir / fname
            try:
                src_mtime = src.stat().st_mtime
                data = read_source_stable(src)
                h_src = hashlib.sha256(data).hexdigest()
                write_atomic(dest, data, mtime=src_mtime)
                h_nas = sha256_file(dest)
            except Exception as e:
                return fname, None, str(e)

            if h_nas != h_src:
                # 校验不过就不算归档（铁律 5）：删掉坏副本，整个目录不记账
                try:
                    dest.unlink()
                except Exception:
                    pass
                return fname, None, "SHA256 不一致"

            return fname, [
                f"{label}/{dname}/{fname}", str(src), str(dest), "NEW",
                str(len(data)), fmt_mtime(src), h_src, h_nas, "MATCH",
            ], None

        dir_ok = True
        copied = 0
        # 并发复制：每个文件独立，瓶颈是往返延迟不是带宽，线程池能把延迟叠掉
        with ThreadPoolExecutor(max_workers=COPY_WORKERS) as pool:
            for fname, row, err in pool.map(_copy_one, files):
                if err:
                    lvl = "CRITICAL" if "SHA256" in err else "WARN"
                    alert(lvl, f"图片归档失败: {dname}/{fname} ({err})")
                    dir_ok = False
                    stats["error"] += 1
                    continue
                compare_rows.append(row)
                copied += 1

        if dir_ok and copied == len(files):
            # 整个目录都到齐了才记账，半截的下次重来（避免漏图片被永久跳过）
            known[dname] = {"tif_count": len(files), "source": str(origin[dname]),
                            "archived_at": NOW_STR}
            stats["new_dirs"] += 1
            stats["files"] += copied
            logger.info(f"{label}: 目录已归档 {dname}（{copied} 个文件，取自 {origin[dname].name}）")
        else:
            logger.warning(f"{label}: 目录未完整归档，本次不记账，下次重试: {dname}")

    return stats


# =========================================================
# 源端删除检测
# =========================================================
def detect_deleted(state: Dict[str, Any]) -> int:
    """
    比对"状态里已归档"与"源端现存"，报告源端已消失的文件/目录。

    只报告、绝不删除——归档区是 append-only，源端不可靠时归档可能是唯一副本。
    实例：2026-08-03 首跑发现 3 个 2026-07-02 的样品在工作站上已消失（搬文件夹时漏的），
    只有 NAS 上还有。这种事必须主动发现，不能等几个月后偶然撞见。
    """
    checks: List[Tuple[str, List[Path], Dict[str, Any]]] = [
        ("Data", [SRC_DATA], state.get("data_files", {})),
        ("Export", [SRC_EXPORT], state.get("export_files", {})),
        ("Config", [CONFIG_SOURCE], state.get("config_files", {})),
        # 图片有两个来源，只要任一边还在就不算消失
        ("Images", [IMAGES_ORIGIN, SRC_IMAGES], state.get("image_dirs", {})),
    ]
    for mnt, subdir, _kind in LEGACY_SOURCES:
        checks.append((f"legacy/{subdir}", [mnt], state.get(f"legacy::{subdir}", {})))

    total = 0
    for label, sdirs, known in checks:
        live = [d for d in sdirs if d.is_dir()]
        if not known or not live:
            continue
        present = set()
        try:
            for d in live:
                present |= {p.name for p in d.iterdir()}
        except Exception as e:
            logger.warning(f"源端删除检测跳过 {label}: {e}")
            continue
        gone = sorted(set(known) - present)
        if not gone:
            continue
        total += len(gone)
        alert("WARN", f"{label}: 源端已消失 {len(gone)} 项，归档区保留不动（前 5 个: {', '.join(gone[:5])}）")
        for g in gone:
            logger.warning(f"源端已消失（归档保留）: {label}/{g}")
    if total == 0:
        logger.info("源端删除检测: 无消失项")
    return total


# =========================================================
# 校验比对文件
# =========================================================
def write_compare(rows: List[List[str]], dry_run: bool) -> None:
    import csv
    if dry_run:
        logger.info(f"[dry-run] 跳过比对文件写入（本次将有 {len(rows)} 行）")
        return
    try:
        CHECKSUM_DIR.mkdir(parents=True, exist_ok=True)
        with open(COMPARE_FILE, "w", encoding="utf-8-sig", newline="") as f:
            w = csv.writer(f)
            w.writerow(COMPARE_HEADER)
            w.writerows(rows)
        logger.info(f"比对文件已写出（{len(rows)} 行）: {COMPARE_FILE}")
    except Exception as e:
        logger.warning(f"比对文件写入失败: {e}")


# =========================================================
# 主流程
# =========================================================
def main() -> int:
    ap = argparse.ArgumentParser(
        description=f"{SCRIPT_NAME} {SCRIPT_VERSION} — Vi-CELL XR Stage 1 归档",
    )
    ap.add_argument("--dry-run", action="store_true", help="只报告将做什么，不写任何文件")
    ap.add_argument("--no-images", action="store_true", help="本次不归档图片（只跑 Data/Export）")
    ap.add_argument("--images-only", action="store_true", help="本次只归档图片")
    ap.add_argument("--no-legacy", action="store_true", help="本次不归档历史遗留目录")
    ap.add_argument("--image-dir-limit", type=int, default=IMAGE_DIR_LIMIT,
                    help="单次最多归档多少个图片目录（0=不限），用于把首次回补拆成多次")
    ap.add_argument("--version", action="store_true", help="打印版本后退出")
    args = ap.parse_args()

    if args.version:
        print(f"{SCRIPT_NAME} {SCRIPT_VERSION} ({SCRIPT_RELEASE_DATE}) — {SCRIPT_OWNER}")
        return 0

    log_file = None if args.dry_run else LOG_DIR / f"{MACHINE_NAME}_{RUN_TAG}.log"
    setup_logger(log_file)

    logger.info("=" * 70)
    logger.info(f"{SCRIPT_NAME} {SCRIPT_VERSION} 启动 | 机器 {MACHINE_NAME} | {NOW_STR}")
    logger.info(f"源 {SRC_MOUNT} -> 归档 {ARCHIVE_ROOT}" + ("  [DRY-RUN]" if args.dry_run else ""))
    logger.info("=" * 70)

    preflight()

    state = load_state() or {}
    for k, v in default_state().items():
        state.setdefault(k, v)

    compare_rows: List[List[str]] = []
    ds = es = imgs = cfg = None
    legacy_stats: List[Tuple[str, Dict[str, int]]] = []

    if not args.images_only:
        ds = archive_flat_dir(SRC_DATA, DATA_ROOT, "data_files", state,
                              (".txt", ".ctl"), args.dry_run, compare_rows)
        es = archive_flat_dir(SRC_EXPORT, EXPORT_ROOT, "export_files", state,
                              (".xls",), args.dry_run, compare_rows)
        # 仪器配置与审计追踪：只取 ViCELLXR 根目录下的文件（几十 KB），不进它的子目录
        if CONFIG_SOURCE.is_dir():
            cfg = archive_flat_dir(CONFIG_SOURCE, CONFIG_ROOT, "config_files", state,
                                   (".txt", ".cfg", ".prf", ".ppr", ".ini", ".pdf", ".xls"),
                                   args.dry_run, compare_rows)

    if ARCHIVE_IMAGES and not args.no_images:
        # 主图片集：D 盘原始位置优先，现用 E 盘补 2026-07 之后的新样品
        imgs = archive_sample_dirs([IMAGES_ORIGIN, SRC_IMAGES], IMAGES_ROOT,
                                   "image_dirs", "Images", state,
                                   args.dry_run, compare_rows, args.image_dir_limit)

    if not args.no_legacy:
        for mnt, subdir, kind in LEGACY_SOURCES:
            if not mnt.is_dir():
                logger.info(f"历史源未挂载，跳过: {subdir}（{mnt}）")
                continue
            key = f"legacy::{subdir}"
            if kind == "samples":
                st_ = archive_sample_dirs([mnt], LEGACY_ROOT / subdir, key,
                                          f"legacy/{subdir}", state,
                                          args.dry_run, compare_rows, args.image_dir_limit)
                # 这些人工归拢的目录根部偶尔散着零星文件（实测 E:\1111 有 1 个 .xls）。
                # 只归档目录会把它们静默丢掉，所以补一趟平铺扫描。
                rs = archive_flat_dir(mnt, LEGACY_ROOT / subdir, key + "::root", state,
                                      (".txt", ".xls", ".ctl", ".csv"), args.dry_run, compare_rows)
                for k2 in ("new", "skip", "error"):
                    st_[k2] = st_.get(k2, 0) + rs[k2]
            else:
                st_ = archive_flat_dir(mnt, LEGACY_ROOT / subdir, key, state,
                                       (".txt", ".xls", ".ctl"), args.dry_run, compare_rows)
            legacy_stats.append((subdir, st_))

    deleted = detect_deleted(state)

    write_compare(compare_rows, args.dry_run)
    save_state(state, args.dry_run)

    logger.info("-" * 70)
    if ds:
        logger.info(f"Data   : 新增 {ds['new']}  跳过 {ds['skip']}  变化 {ds['changed']}  失败 {ds['error']}")
    if es:
        logger.info(f"Export : 新增 {es['new']}  跳过 {es['skip']}  变化 {es['changed']}  失败 {es['error']}")
    if cfg:
        logger.info(f"Config : 新增 {cfg['new']}  跳过 {cfg['skip']}  变化 {cfg['changed']}  失败 {cfg['error']}")
    if imgs:
        logger.info(f"Images : 新增目录 {imgs['new_dirs']}  跳过目录 {imgs['skip_dirs']}  "
                    f"文件 {imgs['files']}  失败 {imgs['error']}")
    for name, st_ in legacy_stats:
        if "new_dirs" in st_:
            root = f"  根部散落文件 {st_['new']}" if st_.get("new") else ""
            logger.info(f"legacy/{name}: 新增目录 {st_['new_dirs']}  跳过目录 {st_['skip_dirs']}  "
                        f"文件 {st_['files']}  失败 {st_['error']}{root}")
        else:
            logger.info(f"legacy/{name}: 新增 {st_['new']}  跳过 {st_['skip']}  失败 {st_['error']}")
    if deleted:
        logger.info(f"源端已消失（归档保留）: {deleted} 项")
    logger.info("-" * 70)

    errors = sum(x["error"] for x in (ds, es, cfg, imgs) if x) \
        + sum(st_["error"] for _, st_ in legacy_stats)
    if errors:
        alert("WARN", f"本次运行有 {errors} 个失败项，详见日志")
        return 1
    logger.info("完成")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except SystemExit:
        raise
    except KeyboardInterrupt:
        logger.warning("用户中断")
        sys.exit(130)
    except Exception as e:
        logger.exception(f"未捕获异常: {e}")
        alert("CRITICAL", f"脚本异常退出: {e}")
        sys.exit(1)
