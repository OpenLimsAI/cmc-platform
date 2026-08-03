#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
alerting.py — 统一异常事件模型与告警落盘（Stage 1 附属模块）

对应整改项：AUDIT-2026-08-03-data-integrity.md 的 **MD-004**
设计依据：docs/BACKUP_MONITORING_DESIGN.md

解决现有 alert() 的六个问题：
  A-1 未配置 ALERT_CMD 时告警只进日志  -> 结构化事件按天落盘，NAS + 本地双写
  A-2 severity 有 CRITICAL/ERROR/WARN/WARNING 四种拼法 -> 归一化为三级
  A-3 外部命令返回非零时完全静默        -> 检查返回码并记 warning
  A-4 无限流，最坏阻塞备份 50 分钟      -> 外呼次数/单条超时/总耗时三重上限
  A-5 无结构化字段                      -> event_type / file_path / run_tag / script_version
  A-6 告警无独立留存                    -> Alerts/<机器名>/alert_YYYYMMDD.jsonl

⚠️ **本模块绝不向上抛异常。** 告警链路的任何失败都只降级为 logger.warning，
    绝不影响备份流程——这是硬约束，不是尽力而为。

依赖：仅 Python 标准库。
"""

import os
import re
import json
import time
import logging
import subprocess
import datetime as dt
from pathlib import Path
from typing import Dict, Any, List, Optional

MODULE_VERSION = "alerting v1.0.0"

# ---------- 严重度：统一为三级 ----------
SEVERITIES = ("CRITICAL", "ERROR", "WARNING")
_SEVERITY_ALIAS = {
    "CRITICAL": "CRITICAL",
    "ERROR": "ERROR",
    "WARN": "WARNING",      # 现有代码里 7 处用 WARN
    "WARNING": "WARNING",   # 现有代码里 3 处用 WARNING
}

# ---------- 事件类型 ----------
# 顺序即匹配优先级：越靠前越具体。未命中任何一条 -> UNCLASSIFIED（绝不丢事件）
_TYPE_RULES = [
    ("SHA256_MISMATCH",    ("SHA256 校验不一致", "SHA256 不一致", "校验不一致", "SHA256")),
    ("MOUNT_ERROR",        ("预检失败", "ro 选项未生效", "ro 未生效", "可写！")),
    ("NAS_UNWRITABLE",     ("NAS 未挂载", "归档写入失败", "Permission denied", "No space left")),
    ("SOURCE_UNAVAILABLE", ("源未挂载", "无法列出", "列目录失败", "列图片目录失败",
                            "源挂载但结构异常", "读取失败", "读取不稳定")),
    ("METADATA_FAILED",    ("Metadata", "metadata")),
    ("SOURCE_DELETED",     ("源端已消失",)),
    ("CONTENT_CHANGED",    ("内容发生变化", "行数减少")),
    ("STRUCTURE_ANOMALY",  ("行宽", "图片数异常", "BOM", "结构提示", "疑似损坏", "备份任务可能已停止")),
    ("COPY_FAILED",        ("归档失败", "复制失败", "未完整归档")),
    ("RUN_FAILED",         ("本次运行有", "个失败项")),
]
UNCLASSIFIED = "UNCLASSIFIED"

# 从消息里尽力提取文件路径（best-effort，提不到就留 None）
_PATH_RE = re.compile(r"(/mnt/[^\s,;'\"()]+)")

logger = logging.getLogger("vicell_ingest")


def normalize_severity(level: str) -> str:
    """归一化严重度。未知取值**原样保留**，不静默降级——宁可下游见到怪值，也不隐藏信息。"""
    return _SEVERITY_ALIAS.get(str(level).strip().upper(), str(level).strip().upper())


def classify(message: str) -> str:
    """按消息关键词归类事件。命中不了返回 UNCLASSIFIED，事件仍会被完整记录。"""
    for etype, keys in _TYPE_RULES:
        for k in keys:
            if k in message:
                return etype
    return UNCLASSIFIED


def extract_path(message: str) -> Optional[str]:
    m = _PATH_RE.search(message or "")
    return m.group(1) if m else None


def _iso_now() -> str:
    return dt.datetime.now().astimezone().isoformat()


class AlertSink:
    """
    告警落盘 + 受限外呼。

    用法：
        sink = AlertSink(machine_name=..., run_tag=..., script_version=...)
        sink.emit("CRITICAL", "SHA256 校验不一致: ...")
        counts = sink.close()      # 运行结束，返回各级别计数

    落盘：NAS `Alerts/<机器名>/alert_YYYYMMDD.jsonl` + 本地兜底目录，**两处都写**。
          NAS 不可写恰恰是要告警的场景之一，只写 NAS 等于最重要的那条告警写不进去。
    """

    def __init__(
        self,
        machine_name: str,
        run_tag: str,
        script_version: str,
        nas_dir: Optional[Path] = None,
        local_dir: Optional[Path] = None,
        alert_cmd: str = "",
        enabled: bool = True,
        max_external: int = 20,
        per_type_external_cap: int = 5,
        cmd_timeout: float = 10.0,
        external_budget_sec: float = 60.0,
    ):
        self.machine_name = machine_name
        self.run_tag = run_tag
        self.script_version = script_version
        self.nas_dir = Path(nas_dir) if nas_dir else None
        self.local_dir = Path(local_dir) if local_dir else None
        self.alert_cmd = (alert_cmd or "").strip()
        self.enabled = enabled

        # 限流参数（解决 A-4：告警绝不拖慢备份）
        self.max_external = max_external
        self.per_type_external_cap = per_type_external_cap
        self.cmd_timeout = cmd_timeout
        self.external_budget_sec = external_budget_sec

        self.counts: Dict[str, int] = {s: 0 for s in SEVERITIES}
        self.by_type: Dict[str, int] = {}
        self._external_sent = 0
        self._external_spent = 0.0
        self._suppressed = 0
        self._write_failed = 0

    # ---------------- 内部 ----------------
    def _filename(self) -> str:
        return f"alert_{dt.datetime.now().strftime('%Y%m%d')}.jsonl"

    def _append(self, directory: Path, line: str) -> bool:
        try:
            directory.mkdir(parents=True, exist_ok=True)
            # 追加写：无读-改-写，中断不会留下损坏文件
            with open(directory / self._filename(), "a", encoding="utf-8") as f:
                f.write(line + "\n")
                f.flush()
            return True
        except Exception:
            return False

    def _dispatch(self, event: Dict[str, Any]) -> None:
        """调用外部告警命令。三重上限保证不拖慢备份。"""
        if not self.alert_cmd:
            return
        if self._external_sent >= self.max_external:
            self._suppressed += 1
            return
        if self._external_spent >= self.external_budget_sec:
            self._suppressed += 1
            return
        if self.by_type.get(event["event_type"], 0) > self.per_type_external_cap:
            self._suppressed += 1
            return

        t0 = time.time()
        try:
            r = subprocess.run(
                [self.alert_cmd, event["severity"],
                 f"[{self.machine_name}] {event['message']}"],
                timeout=self.cmd_timeout, check=False,
                stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            )
            # 解决 A-3：命令跑了但失败，原来完全静默
            if r.returncode != 0:
                tail = (r.stderr or b"")[-200:].decode("utf-8", "replace").strip()
                logger.warning(f"告警命令返回非零({r.returncode})，告警可能未送达: {tail}")
        except Exception as e:
            logger.warning(f"告警命令执行失败: {e}")
        finally:
            self._external_sent += 1
            self._external_spent += time.time() - t0

    # ---------------- 对外 ----------------
    def emit(self, severity: str, message: str,
             event_type: Optional[str] = None,
             file_path: Optional[str] = None) -> None:
        """记录一条告警事件。**任何情况下都不抛异常。**"""
        if not self.enabled:
            return
        try:
            sev = normalize_severity(severity)
            etype = event_type or classify(message)
            fpath = file_path if file_path is not None else extract_path(message)

            self.counts[sev] = self.counts.get(sev, 0) + 1
            self.by_type[etype] = self.by_type.get(etype, 0) + 1

            event = {
                "event_time": _iso_now(),
                "machine_name": self.machine_name,
                "severity": sev,
                "event_type": etype,
                "file_path": fpath,
                "message": message,
                "run_tag": self.run_tag,
                "script_version": self.script_version,
            }
            line = json.dumps(event, ensure_ascii=False)

            ok = False
            for d in (self.nas_dir, self.local_dir):
                if d is not None and self._append(d, line):
                    ok = True
            if not ok:
                self._write_failed += 1
                logger.warning(f"告警落盘失败（不影响备份）: {etype} {message[:80]}")

            self._dispatch(event)
        except Exception as e:
            # 告警自身出错绝不能影响备份
            logger.warning(f"告警处理异常（已忽略，不影响备份）: {e}")

    def close(self) -> Dict[str, int]:
        """运行结束：补发汇总、返回计数。"""
        if not self.enabled:
            return dict(self.counts)
        try:
            if self._suppressed and self.alert_cmd:
                total = sum(self.counts.values())
                msg = (f"本次运行共 {total} 条告警，其中 {self._suppressed} 条因限流未外呼；"
                       f"完整记录见 Alerts/{self.machine_name}/{self._filename()}")
                logger.warning(msg)
                # 汇总本身也要受总预算约束，故直接调用而不经 emit
                if self._external_spent < self.external_budget_sec:
                    try:
                        subprocess.run([self.alert_cmd, "WARNING", f"[{self.machine_name}] {msg}"],
                                       timeout=self.cmd_timeout, check=False,
                                       stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                    except Exception:
                        pass
            if self._write_failed:
                logger.warning(f"共有 {self._write_failed} 条告警落盘失败")
        except Exception:
            pass
        return dict(self.counts)

    def summary_line(self) -> str:
        c = self.counts
        return (f"Alerts: CRITICAL {c.get('CRITICAL', 0)}  "
                f"ERROR {c.get('ERROR', 0)}  WARNING {c.get('WARNING', 0)}"
                + (f"  （{self._suppressed} 条未外呼）" if self._suppressed else ""))


# =========================================================
# 自检：验证归一化与分类规则
#   python3 alerting.py
# =========================================================
if __name__ == "__main__":
    samples = [
        ("CRITICAL", "SHA256 校验不一致，已删除坏副本: /mnt/ttlab-backups/Daily/x/a.tif"),
        ("CRITICAL", "源挂载点 /mnt/vicell 可写！ro 选项未生效，已中止以保护仪器数据"),
        ("CRITICAL", "预检失败 -> NAS 未挂载: /mnt/ttlab-backups"),
        ("CRITICAL", "归档写入失败: Data/a.txt ([Errno 13] Permission denied)"),
        ("WARN",     "图片归档失败: 009/009_34.tif ([Errno 5] Input/output error)"),
        ("WARN",     "Metadata 采集不完整（6 个文件）: 创建时间不可得"),
        ("WARN",     "Data: 源端已消失 3 项，归档区保留不动"),
        ("WARNING",  "月度文件结构提示（已归档）: 文件内存在多种行宽"),
        ("ERROR",    "月度文件读取失败: x.csv -> timeout"),
        ("WARN",     "样品图片数异常（期望 50，实际 3）: S1"),
        ("WARN",     "某种从未见过的新情况"),
    ]
    print(f"{MODULE_VERSION}\n")
    print(f"{'原severity':<10} {'归一化':<9} {'event_type':<20} 提取到的路径")
    print("-" * 88)
    for lvl, msg in samples:
        print(f"{lvl:<10} {normalize_severity(lvl):<9} {classify(msg):<20} {extract_path(msg)}")
