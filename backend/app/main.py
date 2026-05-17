# FastAPI 应用入口：注册路由、异常处理器、启动/关闭事件
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.router import api_router
from app.core.config import settings
from app.core.exceptions import LIMSException, lims_exception_handler
from app.core.logging import configure_logging, logger


@asynccontextmanager
async def lifespan(app: FastAPI):
    configure_logging()
    logger.info("TT LIMS Platform 后端启动")
    yield
    logger.info("TT LIMS Platform 后端关闭")


app = FastAPI(
    title="TT LIMS Platform API",
    description="CMC 研发 LIMS 平台后端接口",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["*"],
)

app.add_exception_handler(LIMSException, lims_exception_handler)
app.include_router(api_router, prefix="/api/v1")
