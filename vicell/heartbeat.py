#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
heartbeat.py — 备份心跳写入（Stage 1 附属模块）

对应整改项：AUDIT-2026-08-03-data-integrity.md 的 **MD-005**
设计依据：docs/BACKUP_MONITORING_DESIGN.md

心跳解决的是备份系统最经典的失效模式：**程序根本没跑，而且不会有任何信号。**
timer 被禁用、服务启动失败、凭据过期、机器重装——这些情况下采集脚本一次都不执行，
自然也不会发告警。心跳文件把"我跑过了"这件事变成一个可被外部检查的事实。

文件位置（每台仪器一个，不共用一个文件）：
    State/<机器名>_heartbeat.json          NAS
    <本地状态目录>/<机器名>_heartbeat.json  本地兜底

**每次运行都写**（无论成败），`last_success_time` 只在成功时更新。
若只在成功时写，"连续失败三天"与"程序根本没跑"在文件上无法区分，而两者处置完全不同。

⚠️ 写入失败只记 warning，绝不影响备份结果与退出码。

依赖：仅 Python 标准库。
"""

import os
import json
import logging
import datetime as dt
from pathlib import Path
from typing import Dict, Any, Optional

MODULE_VERSION = "heartbeat v1.0.0"

logger = logging.getLogger("vicell_ingest")


def _iso(ts: Optional[float] = None) -> str:
    d = dt.datetime.fromtimestamp(ts) if ts is not None else dt.datetime.now()
    return d.astimezone().isoformat()


def _read_prev(paths) -> Dict[str, Any]:
    """读上一次的心跳，用于保留 last_success_time。NAS 优先、本地兜底。"""
    for p in paths:
        try:
            if p and Path(p).is_file():
                with open(p, encoding="utf-8") as f:
                    return json.load(f)
        except Exception:
            continue
    return {}


def _write_atomic(path: Path, obj: Dict[str, Any]) -> bool:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_name(path.name + f".tmp.{os.getpid()}")
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(obj, f, ensure_ascii=False, indent=2, sort_keys=True)
            f.flush()
            os.fsync(f.fileno())
        os.replace(str(tmp), str(path))
        return True
    except Exception:
        return False


def write_heartbeat(
    machine_name: str,
    script_name: str,
    software_version: str,
    run_tag: str,
    started_at: float,
    backup_status: str,
    files_processed: int,
    files_failed: int,
    alerts: Optional[Dict[str, int]] = None,
    expected_interval_hours: float = 24.0,
    max_silence_hours: Optional[float] = None,
    nas_state_dir: Optional[Path] = None,
    local_state_dir: Optional[Path] = None,
    enabled: bool = True,
) -> Optional[Dict[str, Any]]:
    """
    写心跳。返回写出的内容（供日志），失败返回 None。**绝不抛异常。**

    expected_interval_hours / max_silence_hours 会写进文件本身，
    这样巡检脚本是通用的——它不需要知道每台仪器的排期，新增仪器零改动。
    """
    if not enabled:
        return None
    try:
        name = f"{machine_name}_heartbeat.json"
        nas_path = (Path(nas_state_dir) / name) if nas_state_dir else None
        local_path = (Path(local_state_dir) / name) if local_state_dir else None

        prev = _read_prev([nas_path, local_path])
        now = dt.datetime.now()
        ok = str(backup_status).upper() == "SUCCESS"

        hb = {
            "machine_name": machine_name,
            "script_name": script_name,
            "software_version": software_version,
            "run_tag": run_tag,
            "last_run_time": _iso(started_at),
            "last_run_finished": _iso(now.timestamp()),
            # 失败时保留上一次的成功时刻不动——这正是区分"失败"与"没跑"的关键
            "last_success_time": _iso(now.timestamp()) if ok else prev.get("last_success_time", ""),
            "backup_status": "SUCCESS" if ok else "FAILED",
            "files_processed": int(files_processed),
            "files_failed": int(files_failed),
            "alerts": alerts or {},
            "duration_sec": round(now.timestamp() - started_at, 1),
            "expected_interval_hours": expected_interval_hours,
            "max_silence_hours": (max_silence_hours if max_silence_hours is not None
                                  else expected_interval_hours * 3),
            "heartbeat_module": MODULE_VERSION,
        }

        wrote = False
        for p in (nas_path, local_path):
            if p is not None and _write_atomic(p, hb):
                wrote = True
        if not wrote:
            logger.warning("心跳写入失败（NAS 与本地均不可写，不影响备份结果）")
            return None
        logger.info(f"心跳已写出: {backup_status}  处理 {files_processed}  失败 {files_failed}")
        return hb
    except Exception as e:
        logger.warning(f"心跳写入异常（已忽略，不影响备份）: {e}")
        return None
