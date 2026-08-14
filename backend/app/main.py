from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .auth import auth_configured, require_viewer
from .config import settings
from .db import dispose_engine, init_engine
from .routers import auth, nova, overview, signals, vicell


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 防裸奔：生产要求鉴权（AUTH_REQUIRED=true）但漏配验签密钥 → 启动即报错
    if settings.auth_required and not auth_configured():
        raise RuntimeError(
            "AUTH_REQUIRED=true 但未配置 JWT 验签密钥"
            "（HS256 填 JWT_SECRET_KEY，须与 MDM 的 SECRET_KEY 一致）"
        )
    init_engine()
    yield
    await dispose_engine()


app = FastAPI(title="CMC R&D USP Dashboard API", version="0.1.0", lifespan=lifespan)

origins = [o.strip() for o in settings.dev_extra_origins.split(",") if o.strip()]
if not origins:
    origins = ["http://localhost:3000", "http://localhost:5170"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 登录接口本身不设防；全部数据接口挂 require_viewer（全站需登录 + USP 角色）
app.include_router(auth.router)
_guard = [Depends(require_viewer)]
app.include_router(signals.router, dependencies=_guard)
app.include_router(vicell.router, dependencies=_guard)
app.include_router(nova.router, dependencies=_guard)
app.include_router(overview.router, dependencies=_guard)


@app.get("/health")
async def health():
    return {"status": "ok", "env": settings.app_env}
