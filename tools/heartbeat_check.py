#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
heartbeat_check.py — 备份心跳巡检（MD-005 的本体）

扫描 NAS `State/*_heartbeat.json`，判断每台仪器的备份是否还在正常运行。

**这个脚本必须独立于采集程序、由自己的 systemd timer 触发。**
理由：采集脚本没跑的时候，它自己不会上报"我没跑"——所以检查者不能是被检查者。

判定规则（阈值来自心跳文件自身的 max_silence_hours，因此本脚本对新增仪器零改动）：
    last_success_time 距今 > max_silence_hours   -> CRITICAL  备份可能已停止
    backup_status == FAILED                       -> ERROR     最近一次运行失败
    心跳文件缺失 / 无法解析                        -> CRITICAL  从未运行或文件损坏

退出码：0 = 全部正常；1 = 有异常（便于 systemd 或外部监控接管）

用法：
    python3 heartbeat_check.py
    python3 heartbeat_check.py --state-dir /mnt/ttlab-backups/State
    python3 heartbeat_check.py --expect C4V61257XH_ViCell --expect T281240040C_Nova

依赖：仅 Python 标准库。
"""

import os
import sys
import json
import glob
import argparse
import datetime as dt
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "vicell"))
try:
    from alerting import AlertSink  # noqa: E402
except Exception:      # 采集模块不可用时降级为只打印，不让巡检本身挂掉
    AlertSink = None

SCRIPT_VERSION = "heartbeat_check v1.0.1"

NAS_MOUNT = Path(os.environ.get("VICELL_NAS_MOUNT", "/mnt/ttlab-backups"))
DEFAULT_STATE_DIR = NAS_MOUNT / "State"
ALERT_CMD = os.environ.get("INGEST_ALERT_CMD", os.environ.get("VICELL_ALERT_CMD", "")).strip()
LOCAL_ALERT_DIR = Path(os.environ.get("INGEST_LOCAL_ALERT_DIR", "/var/lib/vicell-ingest/alerts"))


DEFAULT_MAX_SILENCE_HOURS = 72.0


def parse_iso(s):
    try:
        return dt.datetime.fromisoformat(s)
    except Exception:
        return None


def parse_hours(value, default: float):
    """
    把心跳里的小时阈值解析成正数。取不出合法数值就退回默认值。

    返回 (小时数, 是否用了默认值)。第二个值用来提醒"这个文件的阈值字段坏了"——
    退默认值可以让巡检继续，但不能让它悄悄发生。
    """
    try:
        h = float(value)
    except (TypeError, ValueError):
        return default, True
    # NaN 与非正数都不是合法阈值：NaN 参与比较恒为 False，会让超时判断永远不触发
    if h != h or h <= 0:
        return default, True
    return h, False


def check_one(name: str, hb, now):
    """检查单台仪器的心跳，返回 findings 列表。异常由调用方兜底。"""
    findings = []
    machine = str(hb.get("machine_name") or name)

    max_silence, fell_back = parse_hours(hb.get("max_silence_hours"), DEFAULT_MAX_SILENCE_HOURS)
    if fell_back:
        findings.append(("WARNING", machine,
                         f"心跳里的 max_silence_hours 不是合法数值"
                         f"（实际 {hb.get('max_silence_hours')!r}），本次按默认 "
                         f"{DEFAULT_MAX_SILENCE_HOURS:.0f}h 判定，请检查采集程序配置"))

    last_ok = parse_iso(hb.get("last_success_time") or "")
    if last_ok is None:
        findings.append(("CRITICAL", machine,
                         "心跳中没有成功记录（last_success_time 为空）——备份可能从未成功过"))
    else:
        silent_h = (now - last_ok).total_seconds() / 3600.0
        if silent_h > max_silence:
            findings.append(("CRITICAL", machine,
                             f"备份已 {silent_h:.1f} 小时未成功（阈值 {max_silence:.0f}h）"
                             f"，最近一次成功 {hb.get('last_success_time')}——备份可能已停止"))

    if str(hb.get("backup_status", "")).upper() == "FAILED":
        findings.append(("ERROR", machine,
                         f"最近一次运行失败（run_tag={hb.get('run_tag')}，"
                         f"失败 {hb.get('files_failed')} 项）"))

    return findings


def check(state_dir: Path, expected):
    """返回 (findings, checked)。findings 为 (severity, machine, message) 列表。"""
    findings = []
    files = sorted(glob.glob(str(state_dir / "*_heartbeat.json")))
    seen = set()
    now = dt.datetime.now().astimezone()

    for f in files:
        name = Path(f).name.replace("_heartbeat.json", "")
        seen.add(name)
        try:
            with open(f, encoding="utf-8") as fh:
                hb = json.load(fh)
        except Exception as e:
            findings.append(("CRITICAL", name, f"心跳文件无法解析: {e}"))
            continue

        if not isinstance(hb, dict):
            findings.append(("CRITICAL", name,
                             f"心跳文件内容不是对象（实际是 {type(hb).__name__}）——文件可能被写坏"))
            continue

        # ⚠️ 巡检自身必须最健壮（2026-08-05 加）：
        # 原来 float(max_silence_hours) 写在 try 之外，字段被写成字符串就抛 ValueError，
        # 而这里是 for 循环内部 —— 一台仪器的心跳坏掉会中断整个循环，
        # **其余仪器一台都检查不到**。监控自己失效是最坏的一类失效，
        # 所以每台单独兜底：坏的那台照样报警，其余照常检查。
        try:
            findings.extend(check_one(name, hb, now))
        except Exception as e:
            findings.append(("CRITICAL", name,
                             f"心跳内容异常、无法判定该仪器状态（其余仪器不受影响，"
                             f"请人工查看 {Path(f).name}）: {e}"))

    for name in expected or []:
        if name not in seen:
            findings.append(("CRITICAL", name,
                             f"找不到心跳文件 {name}_heartbeat.json——该仪器可能从未运行或文件已丢失"))

    return findings, sorted(seen)


def main() -> int:
    ap = argparse.ArgumentParser(description="备份心跳巡检（独立于采集程序）")
    ap.add_argument("--state-dir", default=str(DEFAULT_STATE_DIR))
    ap.add_argument("--expect", action="append", default=[],
                    help="必须存在心跳的机器名，可重复；缺失即告警")
    ap.add_argument("--quiet", action="store_true", help="只在有异常时输出")
    ap.add_argument("--version", action="store_true")
    args = ap.parse_args()

    if args.version:
        print(SCRIPT_VERSION)
        return 0

    state_dir = Path(args.state_dir)
    now = dt.datetime.now().astimezone().isoformat()

    if not state_dir.is_dir():
        print(f"[CRITICAL] 状态目录不可访问: {state_dir}（NAS 未挂载？）")
        return 1

    findings, checked = check(state_dir, args.expect)

    if not args.quiet or findings:
        print(f"{SCRIPT_VERSION}  |  {now}")
        print(f"检查目录: {state_dir}")
        print(f"检查到 {len(checked)} 台仪器: {', '.join(checked) if checked else '(无)'}")
        print("-" * 66)

    if not findings:
        if not args.quiet:
            print("结论：全部正常 ✅")
        return 0

    # 有异常：落盘 + 外呼（复用采集程序的告警通道，保证格式一致）
    sink = None
    if AlertSink is not None:
        try:
            sink = AlertSink(
                machine_name="_heartbeat", run_tag=dt.datetime.now().strftime("%Y%m%d_%H%M%S"),
                script_version=SCRIPT_VERSION,
                nas_dir=NAS_MOUNT / "Alerts" / "_heartbeat",
                local_dir=LOCAL_ALERT_DIR,
                alert_cmd=ALERT_CMD,
            )
        except Exception:
            sink = None

    for sev, machine, msg in findings:
        print(f"[{sev}] {machine}: {msg}")
        if sink is not None:
            sink.emit(sev, f"{machine}: {msg}", event_type="HEARTBEAT_STALE")
    if sink is not None:
        sink.close()

    print("-" * 66)
    print(f"结论：发现 {len(findings)} 个问题 ❌")
    return 1


if __name__ == "__main__":
    sys.exit(main())
