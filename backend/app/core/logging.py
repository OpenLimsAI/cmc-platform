"""集中日志配置（P4.B-4）

支持两种 sink 模式（通过 settings.APP_LOG_FORMAT 切换）：
  - "json"（生产 / UAT）：每行一条 JSON，含 timestamp/level/logger/module/function/line/
    message + request_id + user_id + username + ip；外部 fluentbit/promtail/filebeat 直接
    抓 stderr 转发到 ELK/Splunk/Loki
  - "human"（开发）：loguru 默认彩色格式，便于本地调试

注入字段：
  - request_id / user_id / username / ip 来自 app.shared.audit_context 的 ContextVar，
    所有处理某请求的协程都自动带；非请求上下文（启动、定时任务）字段为 null/system

调用时机：app/main.py lifespan 启动时调用 `setup_logging()` 一次即可。
"""
from __future__ import annotations

import json
import sys
from typing import Any

from loguru import logger

from app.core.config import settings
from app.shared.audit_context import (
    audit_ip,
    audit_request_id,
    audit_user_id,
    audit_username,
)


def _audit_patcher(record: dict[str, Any]) -> None:
    """把 ContextVar 中的审计上下文塞到 record["extra"] 里"""
    extra = record["extra"]
    extra.setdefault("request_id", audit_request_id.get())
    extra.setdefault("user_id", audit_user_id.get())
    extra.setdefault("username", audit_username.get())
    extra.setdefault("ip", audit_ip.get())


def _json_sink(message: Any) -> None:
    """loguru 自定义 sink：把 record 序列化成单行 JSON 写到 stderr"""
    record = message.record
    payload = {
        "timestamp": record["time"].isoformat(),
        "level": record["level"].name,
        "logger": record["name"],
        "module": record["module"],
        "function": record["function"],
        "line": record["line"],
        "message": record["message"],
        # 审计上下文（_audit_patcher 注入）
        "request_id": record["extra"].get("request_id"),
        "user_id": record["extra"].get("user_id"),
        "username": record["extra"].get("username"),
        "ip": record["extra"].get("ip"),
    }
    # 应用业务字段（caller 用 logger.bind(foo="bar") 传入的）
    for k, v in record["extra"].items():
        if k not in payload and not k.startswith("_"):
            payload[k] = v
    # 异常堆栈
    if record["exception"] is not None:
        payload["exception"] = repr(record["exception"])
    sys.stderr.write(json.dumps(payload, ensure_ascii=False, default=str) + "\n")
    sys.stderr.flush()


def setup_logging() -> None:
    """初始化 loguru：清掉默认 handler，按 APP_LOG_FORMAT 装新 sink"""
    logger.remove()

    log_format = (settings.APP_LOG_FORMAT or "json").lower()
    level = (settings.APP_LOG_LEVEL or "INFO").upper()

    if log_format == "json":
        logger.add(
            _json_sink,
            level=level,
            backtrace=True,
            diagnose=False,  # 生产模式不暴露变量值
            enqueue=False,   # uvicorn worker 单进程异步即可
        )
    else:
        # human-readable 模式（dev）
        logger.add(
            sys.stderr,
            level=level,
            colorize=True,
            backtrace=True,
            # 恒 False：loguru 的 diagnose 会把栈帧局部变量打进日志，
            # 登录失败路径的局部变量里有明文密码（2026-09-10 体检发现）
            diagnose=False,
            format=(
                "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | "
                "<level>{level: <8}</level> | "
                "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan>"
                " - <level>{message}</level>"
                " | req={extra[request_id]} user={extra[user_id]}"
            ),
        )

    # 把审计上下文注入每条 record；patch 在 add() 之后调用一次即生效全局
    logger.configure(patcher=_audit_patcher)
