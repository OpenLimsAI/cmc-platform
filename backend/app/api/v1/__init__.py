"""
API v1 路由聚合
"""
from fastapi import APIRouter

from app.api.v1 import (
    assets,
    auth,
    lookups,
    materials,
    projects,
    search,
    substances,
    system,
)

api_router = APIRouter()
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(substances.router, prefix="/substances", tags=["substances"])
api_router.include_router(projects.router, prefix="/projects", tags=["projects"])
api_router.include_router(assets.router, prefix="/assets", tags=["assets"])
# Phase 4.A 物料域（M4.1）
api_router.include_router(materials.router, prefix="/materials", tags=["materials"])
api_router.include_router(search.router, prefix="/search", tags=["search"])
# V1.2 评审 API11:B 部分立即做（2026-05-13）
api_router.include_router(lookups.router, prefix="/lookups", tags=["lookups"])
api_router.include_router(system.router, prefix="/system", tags=["system"])
