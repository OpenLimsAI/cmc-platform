# v1 总路由：汇总各模块路由
from fastapi import APIRouter

from app.api.v1.admin.auth import router as admin_auth_router
from app.api.v1.admin.employees import router as admin_employees_router
from app.api.v1.admin.methods import router as admin_methods_router
from app.api.v1.lims.meta import router as meta_router
from app.api.v1.lims.samples import router as samples_router
from app.api.v1.lims.stats import router as stats_router

api_router = APIRouter()

api_router.include_router(stats_router, tags=["统计 & 健康检查"])
api_router.include_router(meta_router, tags=["元数据"])
api_router.include_router(samples_router, prefix="/lims/samples", tags=["样品"])
api_router.include_router(admin_auth_router, prefix="/admin", tags=["管理员"])
api_router.include_router(admin_methods_router, prefix="/admin/methods", tags=["管理员"])
api_router.include_router(admin_employees_router, prefix="/admin/employees", tags=["管理员"])
