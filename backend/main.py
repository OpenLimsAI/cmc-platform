"""
文件: backend/main.py
用途: FastAPI 入口。注册全部路由 + CORS + 全局异常处理。
说明:
    - 启用 CORS,允许前端 Streamlit 访问
    - 所有错误统一返回中文 friendly message
"""
from __future__ import annotations

import logging

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from routers import material, batch, inventory, stock, import_data, location

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("cmc-inventory")

app = FastAPI(
    title="CMC 物料管理系统 API",
    description="部门级物料管理 MVP — 物料/批次/出入库/库存预警",
    version="0.1.0",
)

# 允许所有来源(MVP 内部使用)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(IntegrityError)
async def integrity_error_handler(_: Request, exc: IntegrityError):
    log.warning("数据完整性错误: %s", exc.orig)
    msg = str(exc.orig) if exc.orig else "数据完整性约束错误"
    # 提供常见错误的中文提示
    if "uq_batch_material_no" in msg:
        msg = "同一物料同一批号已存在,请检查批号是否重复"
    return JSONResponse(status_code=400, content={"detail": f"数据完整性错误: {msg}"})


@app.exception_handler(SQLAlchemyError)
async def sqla_error_handler(_: Request, exc: SQLAlchemyError):
    log.exception("数据库错误")
    return JSONResponse(status_code=500, content={"detail": f"数据库错误: {exc}"})


@app.exception_handler(ValueError)
async def value_error_handler(_: Request, exc: ValueError):
    return JSONResponse(status_code=400, content={"detail": str(exc)})


@app.get("/", tags=["health"])
def root():
    return {"name": "CMC 物料管理系统", "status": "ok"}


@app.get("/health", tags=["health"])
def health():
    return {"status": "ok"}


# 路由注册
app.include_router(material.router)
app.include_router(batch.router)
app.include_router(inventory.router)
app.include_router(stock.router)
app.include_router(import_data.router)
app.include_router(location.router)
