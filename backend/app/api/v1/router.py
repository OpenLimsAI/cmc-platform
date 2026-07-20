# v1 总路由：汇总各模块路由
# 鉴权：/auth/* 与 /health 开放；其余看板读接口挂 require_view（分析员及以上）；
# admin 写接口在各自路由里逐个挂 verify_admin（= require_admin，LIMS 管理员）。
from fastapi import APIRouter, Depends

from app.api.v1.admin.employees import router as admin_employees_router
from app.api.v1.admin.methods import router as admin_methods_router
from app.api.v1.auth import router as auth_router
from app.api.v1.lims.meta import router as meta_router
from app.api.v1.lims.samples import router as samples_router
from app.api.v1.lims.stats import health_router, router as stats_router
from app.core.auth import require_view

api_router = APIRouter()

api_router.include_router(auth_router, prefix="/auth", tags=["认证"])
api_router.include_router(health_router, tags=["健康检查"])
api_router.include_router(stats_router, tags=["统计"], dependencies=[Depends(require_view)])
api_router.include_router(meta_router, tags=["元数据"], dependencies=[Depends(require_view)])
api_router.include_router(
    samples_router, prefix="/lims/samples", tags=["样品"], dependencies=[Depends(require_view)]
)
api_router.include_router(admin_methods_router, prefix="/admin/methods", tags=["管理员"])
api_router.include_router(admin_employees_router, prefix="/admin/employees", tags=["管理员"])
