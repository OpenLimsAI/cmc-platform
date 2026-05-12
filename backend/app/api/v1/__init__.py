"""
API v1 路由聚合
"""
from fastapi import APIRouter

from app.api.v1 import assets, auth, projects, search, substances

api_router = APIRouter()
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(substances.router, prefix="/substances", tags=["substances"])
api_router.include_router(projects.router, prefix="/projects", tags=["projects"])
api_router.include_router(assets.router, prefix="/assets", tags=["assets"])
api_router.include_router(search.router, prefix="/search", tags=["search"])
