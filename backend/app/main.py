"""
CMAB MDM Portal - FastAPI 应用入口
"""
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from loguru import logger
from prometheus_fastapi_instrumentator import Instrumentator

from app.api.v1 import api_router
from app.core.config import settings
from app.core.database import close_db, init_db
from app.core.exceptions import AppError, RateLimitError
from app.core.logging import setup_logging
from app.core.redis_client import close_redis, init_redis
from app.core.responses import error_response
from app.shared.middleware.audit_context import AuditContextMiddleware
from app.shared.middleware.request_id import RequestIDMiddleware
from app.shared.rate_limit import RateLimitExceeded, SlowAPIMiddleware, limiter


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用启动与关闭生命周期"""
    # P4.B-4：必须先 setup_logging() 再写日志，否则用的是 loguru 默认 handler
    setup_logging()
    logger.info("=" * 60)
    logger.info(f"启动 {settings.APP_NAME}")
    logger.info(
        f"环境: {settings.APP_ENV}  调试: {settings.APP_DEBUG}  "
        f"日志格式: {settings.APP_LOG_FORMAT}"
    )
    logger.info("=" * 60)

    await init_db()
    logger.info("✓ 数据库连接已就绪")

    await init_redis()

    yield

    await close_redis()
    await close_db()
    logger.info("应用已关闭")


# ============== 应用实例 ==============
app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="生物制药主数据管理平台 / Master Data Management Portal",
    docs_url="/api/v1/docs" if settings.APP_DEBUG else None,
    redoc_url="/api/v1/redoc" if settings.APP_DEBUG else None,
    openapi_url="/api/v1/openapi.json" if settings.APP_DEBUG else None,
    lifespan=lifespan,
)

# ============== 中间件 ==============
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=[
        "X-Request-ID",
        "X-RateLimit-Limit",
        "X-RateLimit-Remaining",
        "X-RateLimit-Reset",
        "Retry-After",
        "Location",
    ],
)
app.add_middleware(RequestIDMiddleware)
app.add_middleware(AuditContextMiddleware)

# P4.B 限流：默认 300/min/user（已认证）或 300/min/IP（未认证）
# /auth/login + /auth/refresh 在路由层用装饰器单独覆写到 10/min/IP
# /health + /metrics 路径白名单，在 RateLimitExceeded handler 里宽放（slowapi 暴露
# limiter.enabled 与 path-level exempt 用于细控；这里采用最简方案：靠默认 300 兜底）
app.state.limiter = limiter
app.add_middleware(SlowAPIMiddleware)


@app.exception_handler(RateLimitExceeded)
async def rate_limit_handler(request: Request, exc: RateLimitExceeded):
    """slowapi RateLimitExceeded → V1.1 §3.5 业务错误（42901 + Retry-After + X-RateLimit-*）"""
    detail = getattr(exc, "detail", "")
    err = RateLimitError(
        message=f"请求过于频繁，请稍后重试（{detail}）" if detail else "请求过于频繁，请稍后重试"
    )
    response = JSONResponse(
        status_code=err.http_status,
        content=error_response(
            code=err.code,
            message=err.message,
            error_type=err.error_type,
            request_id=getattr(request.state, "request_id", None),
        ),
    )
    # V1.1 §3.5：429 必须带 Retry-After + X-RateLimit-*
    # slowapi 在 wrap=JSONResponse 时不会自动加，这里手动补
    try:
        limit_wrapper = getattr(exc, "limit", None)
        rate_limit_item = getattr(limit_wrapper, "limit", None) if limit_wrapper else None
        if rate_limit_item is not None:
            response.headers["X-RateLimit-Limit"] = str(rate_limit_item.amount)
            response.headers["X-RateLimit-Remaining"] = "0"
            # 窗口长度（秒），fixed-window 下次重置时间最长就是 period
            period_sec = rate_limit_item.GRANULARITY.seconds
            response.headers["Retry-After"] = str(period_sec)
    except Exception:
        pass
    return response


# ============== 全局异常 ==============
@app.exception_handler(AppError)
async def app_error_handler(request: Request, exc: AppError):
    """业务错误统一处理"""
    return JSONResponse(
        status_code=exc.http_status,
        content=error_response(
            code=exc.code,
            message=exc.message,
            error_type=exc.error_type,
            details=exc.details,
            request_id=getattr(request.state, "request_id", None),
        ),
    )


@app.exception_handler(RequestValidationError)
async def request_validation_handler(request: Request, exc: RequestValidationError):
    """Pydantic 校验错误 → V1.1 §5.5 业务格式 40001 + meta.error.details[]

    前端 axios 拦截器（client.ts）按 `meta.error.details[i].field` 反向定位 Form 字段，
    用 Antd Form.setFields 显示行级红色高亮 + 错误提示。
    """
    details: list[dict] = []
    for err in exc.errors():
        # loc 通常形如 ("body", "preferred_name") / ("body", "protein", "extinction_coefficient")
        loc = err.get("loc", ())
        # 去掉前缀 "body"，剩下的拼成点分路径供前端映射
        path_parts = [str(p) for p in loc if p not in ("body", "query", "header", "path")]
        field = ".".join(path_parts) if path_parts else None
        details.append({
            "field": field,
            "message": err.get("msg", "校验失败"),
            "type": err.get("type"),
        })

    return JSONResponse(
        status_code=400,  # V1.1 API §4.1: 40001 validation_failed → HTTP 400
        content=error_response(
            code=40001,
            message="请求体校验失败",
            error_type="validation_failed",
            details=details,
            request_id=getattr(request.state, "request_id", None),
        ),
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """未捕获异常兜底"""
    logger.exception(f"未捕获异常: {exc}")
    return JSONResponse(
        status_code=500,
        content=error_response(
            code=50001,
            message="服务器内部错误" if not settings.APP_DEBUG else str(exc),
            error_type="internal_error",
            request_id=getattr(request.state, "request_id", None),
        ),
    )


# ============== 健康检查 ==============
async def _health_payload():
    """供负载均衡和监控系统调用，无需认证"""
    return {
        "status": "healthy",
        "version": settings.APP_VERSION,
        "app": settings.APP_NAME,
    }


@app.get("/health", tags=["system"], summary="健康检查（无前缀）")
async def health_check():
    return await _health_payload()


# /api/v1 alias —— 让前端可以走统一的 /api/v1 base URL 探测健康
# （vite dev proxy 只代理 /api/*，独立 /health 在 dev 拿不到）
@app.get("/api/v1/health", tags=["system"], summary="健康检查（带前缀 alias）")
async def health_check_api():
    return await _health_payload()


# ============== Prometheus 指标（P4.B）==============
# 暴露 /metrics 端点，Prometheus scrape；含 HTTP 请求 count + latency histogram + size
# 排除 /health 与 /metrics 自身路径，避免噪声
Instrumentator(
    should_group_status_codes=True,
    should_ignore_untemplated=True,
    should_respect_env_var=False,
    should_instrument_requests_inprogress=True,
    excluded_handlers=["/health", "/api/v1/health", "/metrics"],
    inprogress_name="cmab_mdm_inprogress",
    inprogress_labels=True,
).instrument(app).expose(
    app,
    endpoint="/metrics",
    include_in_schema=False,
    tags=["system"],
)


# ============== 路由 ==============
app.include_router(api_router, prefix="/api/v1")


@app.get("/", include_in_schema=False)
async def root():
    return {
        "name": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "docs": "/api/v1/docs",
    }
