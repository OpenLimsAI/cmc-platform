"""
API v1 路由聚合
"""
from fastapi import APIRouter

from app.api.v1 import (
    admin_audit,
    admin_roles,
    admin_users,
    assets,
    auth,
    dashboard,
    equipments,
    lookups,
    materials,
    projects,
    search,
    substances,
    system,
    targets,
)

api_router = APIRouter()
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(substances.router, prefix="/substances", tags=["substances"])
api_router.include_router(projects.router, prefix="/projects", tags=["projects"])
api_router.include_router(assets.router, prefix="/assets", tags=["assets"])
# Phase 4.A 物料域（M4.1）
api_router.include_router(materials.router, prefix="/materials", tags=["materials"])
# EQP 设备主数据域（下游 CMC LabOps Portal 的数据上游）
api_router.include_router(equipments.router, prefix="/equipments", tags=["equipments"])
# 靶点域 tgt（docs/decisions/2026-08-17-target-domain.md）
api_router.include_router(targets.router, prefix="/targets", tags=["targets"])
api_router.include_router(search.router, prefix="/search", tags=["search"])
# V1.2 评审 API11:B 部分立即做（2026-05-13）
api_router.include_router(lookups.router, prefix="/lookups", tags=["lookups"])
api_router.include_router(system.router, prefix="/system", tags=["system"])
# Phase 5.A / M5.1：管理员侧 API10 用户管理
api_router.include_router(admin_users.router, prefix="/users", tags=["admin-users"])
# Phase 5.A / M5.2：管理员侧角色 & 权限管理
api_router.include_router(admin_roles.roles_router, prefix="/roles", tags=["admin-roles"])
api_router.include_router(
    admin_roles.permissions_router, prefix="/permissions", tags=["admin-permissions"]
)
# Phase 5.A / M5.3：管理员侧全局审计 + 电子签名
api_router.include_router(
    admin_audit.audit_router, prefix="/audit-logs", tags=["admin-audit"]
)
api_router.include_router(
    admin_audit.signatures_router, prefix="/signatures", tags=["admin-signatures"]
)
# Phase 5.B：仪表盘聚合
api_router.include_router(dashboard.router, prefix="/dashboard", tags=["dashboard"])
