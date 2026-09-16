# -*- coding: utf-8 -*-
"""v1 路由汇总；只读查询与严格登录的预览分别授权。"""
from fastapi import APIRouter, Depends

from app.api.v1 import auth, imports, meta, release, stability
from app.core.auth import require_read

api_router = APIRouter()
api_router.include_router(auth.router)
api_router.include_router(meta.router, dependencies=[Depends(require_read)])
api_router.include_router(release.router, dependencies=[Depends(require_read)])
api_router.include_router(stability.router, dependencies=[Depends(require_read)])
api_router.include_router(imports.router)
# 后续：similarity / 持久化导入，不能因新增路由绕过权限。
