# FastAPI 应用入口：注册路由、异常处理器、启动/关闭事件
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.router import api_router
from app.core import database, security
from app.core.config import settings
from app.core.exceptions import LIMSException, lims_exception_handler
from app.core.logging import configure_logging, logger


@asynccontextmanager
async def lifespan(app: FastAPI):
    configure_logging()
    # AUTH_REQUIRED=true 但没配验签密钥 → 拒绝启动，防止生产漏配把看板裸奔
    if settings.auth_required and not security.auth_configured():
        raise RuntimeError("AUTH_REQUIRED=true 但未配置 JWT_SECRET_KEY / JWT_PUBLIC_KEY_PATH")
    logger.info("CMC R&D LIMS Dashboard 后端启动")
    yield
    # 优雅关闭时归还连接池
    await database.analytics_engine.dispose()
    await database.mdm_engine.dispose()
    if database.raw_engine is not None:
        await database.raw_engine.dispose()
    logger.info("CMC R&D LIMS Dashboard 后端关闭")


app = FastAPI(
    title="CMC R&D LIMS Dashboard API",
    description="CMC 研发 LIMS 检验进度与考核看板后端（读 cmc_analytics.mart，写 cmc_analytics.mdm）",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["*"],
    # refresh token 走 HttpOnly Cookie，跨端口（5130→8030）请求必须允许携带凭据
    allow_credentials=True,
)

app.add_exception_handler(LIMSException, lims_exception_handler)
app.include_router(api_router, prefix="/api/v1")
