"""
CMAB MDM Portal - FastAPI 应用入口
"""
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from loguru import logger

from app.api.v1 import api_router
from app.core.config import settings
from app.core.database import close_db, init_db
from app.core.exceptions import AppError
from app.core.responses import error_response
from app.shared.middleware.audit_context import AuditContextMiddleware
from app.shared.middleware.request_id import RequestIDMiddleware


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用启动与关闭生命周期"""
    logger.info("=" * 60)
    logger.info(f"启动 {settings.APP_NAME}")
    logger.info(f"环境: {settings.APP_ENV}  调试: {settings.APP_DEBUG}")
    logger.info("=" * 60)

    await init_db()
    logger.info("✓ 数据库连接已就绪")

    yield

    await close_db()
    logger.info("应用已关闭")


# ============== 应用实例 ==============
app = FastAPI(
    title=settings.APP_NAME,
    version="1.0.0",
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
    expose_headers=["X-Request-ID", "X-RateLimit-Limit", "X-RateLimit-Remaining"],
)
app.add_middleware(RequestIDMiddleware)
app.add_middleware(AuditContextMiddleware)


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
        "version": "1.0.0",
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


# ============== 路由 ==============
app.include_router(api_router, prefix="/api/v1")


@app.get("/", include_in_schema=False)
async def root():
    return {
        "name": settings.APP_NAME,
        "version": "1.0.0",
        "docs": "/api/v1/docs",
    }
