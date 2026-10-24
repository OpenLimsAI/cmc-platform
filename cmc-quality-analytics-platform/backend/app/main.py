# -*- coding: utf-8 -*-
"""QAP 后端入口。正式鉴权配置缺失时拒绝启动，无自动建表行为。"""
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.router import api_router
from app.core.config import settings
from app.core.envelope import envelope, register_exception_handlers
from app.core.security import validate_auth_configuration


@asynccontextmanager
async def lifespan(_app: FastAPI):
    validate_auth_configuration()
    yield


app = FastAPI(title=settings.app_name, version="0.1.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
register_exception_handlers(app)
app.include_router(api_router, prefix=settings.api_v1_prefix)


@app.get("/health")
def health() -> dict:
    """公开存活检查不查询业务表、不返回数据库参数或底层异常。"""
    return envelope(data={"status": "ok"})
