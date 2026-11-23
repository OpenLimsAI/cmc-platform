"""
文件: backend/main.py
用途: FastAPI 入口。注册全部路由 + CORS + 全局异常处理。
"""
from __future__ import annotations

from contextlib import asynccontextmanager
import logging

from fastapi import FastAPI, Request, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.exc import DataError, IntegrityError, SQLAlchemyError

from routers import (
    admin_router, auth_router, batch, dashboard, equipment,
    intake, inventory, location, material, stock, storage,
)
from auth import (
    CORS_ALLOWED_HEADERS,
    CORS_ALLOWED_METHODS,
    require_lab_member,
    resolve_cors_origins,
    validate_auth_startup,
    validate_cors_startup,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("cmc-labops")


@asynccontextmanager
async def lifespan(_: FastAPI):
    validate_auth_startup()
    validate_cors_startup()
    yield


def create_app() -> FastAPI:
    application = FastAPI(
        title="CMC LabOps Portal API",
        description="CMC 部门运营平台 — 物料库存(物料/批次/出入库/预警) + 仪器设备(台账/校验/维护/维修)",
        version="0.2.0",
        lifespan=lifespan,
    )

    application.add_middleware(
        CORSMiddleware,
        allow_origins=resolve_cors_origins(),
        allow_credentials=False,
        allow_methods=CORS_ALLOWED_METHODS,
        allow_headers=CORS_ALLOWED_HEADERS,
    )

    @application.exception_handler(IntegrityError)
    async def integrity_error_handler(_: Request, exc: IntegrityError):
        log.warning("数据完整性错误: %s", exc.orig)
        msg = str(exc.orig) if exc.orig else "数据完整性约束错误"
        if "uq_batch_material_no" in msg:
            msg = "同一物料同一批号已存在,请检查批号是否重复"
        return JSONResponse(status_code=400, content={"detail": f"数据完整性错误: {msg}"})

    @application.exception_handler(DataError)
    async def data_error_handler(_: Request, exc: DataError):
        # 典型:字符串超过列宽、数值超范围。是用户输入问题,给 400 和可读提示,不当成服务器故障
        log.warning("数据格式/长度错误: %s", exc.orig)
        return JSONResponse(status_code=400, content={"detail": f"数据格式或长度不合法: {exc.orig}"})

    @application.exception_handler(SQLAlchemyError)
    async def sqla_error_handler(_: Request, exc: SQLAlchemyError):
        log.exception("数据库错误")
        return JSONResponse(status_code=500, content={"detail": f"数据库错误: {exc}"})

    @application.exception_handler(ValueError)
    async def value_error_handler(_: Request, exc: ValueError):
        return JSONResponse(status_code=400, content={"detail": str(exc)})

    @application.get("/", tags=["health"])
    def root():
        return {"name": "CMC LabOps Portal", "status": "ok"}

    @application.get("/health", tags=["health"])
    def health():
        return {"status": "ok"}

    # auth_router 内部各 endpoint 自己控制鉴权（登录是匿名）
    application.include_router(auth_router.router)

    # 业务路由统一要求：登录 + 实验室部门（TT*/CMC*）或 SYS_ADMIN（2026-09-10 负责人；见 auth.require_lab_member）
    _authed = [Depends(require_lab_member)]
    application.include_router(material.router,      dependencies=_authed)
    application.include_router(batch.router,         dependencies=_authed)
    application.include_router(inventory.router,     dependencies=_authed)
    application.include_router(stock.router,         dependencies=_authed)
    application.include_router(location.router,      dependencies=_authed)
    application.include_router(storage.router,       dependencies=_authed)
    application.include_router(intake.router,        dependencies=_authed)
    application.include_router(equipment.router,     dependencies=_authed)
    application.include_router(equipment.mdm_router, dependencies=_authed)
    application.include_router(dashboard.router,     dependencies=_authed)
    application.include_router(admin_router.router,  dependencies=_authed)
    return application


app = create_app()
