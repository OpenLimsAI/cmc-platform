# 当前用户身份与角色鉴权 —— 从验签通过的 JWT 取用户，按 MDM 角色码分级放行。
#
# LIMS 看板三角色（在 MDM /admin/roles 维护、/admin/users 给人挂角色）：
#   - CMC_LIMS_ANALYST  检验分析员   查看
#   - CMC_LIMS_CHEMIST  检验化学家   查看 + 导出
#   - CMC_LIMS_ADMIN    LIMS 管理员  查看 + 导出 + Admin 后台维护
# SYS_ADMIN（MDM 全局管理员）恒放行。
#
# 两种运行态（由是否配置验签密钥决定，见 security.auth_configured()）：
#   - 已配密钥：接口强制携带有效 Bearer 令牌，验签失败/缺令牌一律 401。
#   - 未配密钥（本地开发）：开放模式，操作人记 system，放行一切。
#     若同时 AUTH_REQUIRED=true，启动即报错（见 main.py），防生产漏配裸奔。
from dataclasses import dataclass

from fastapi import Depends, Header, HTTPException

from app.core import security
from app.core.config import settings

SYSTEM_ACTOR = "system"

# 角色分级：上级角色天然包含下级能力
VIEW_ROLES = {"SYS_ADMIN", "CMC_LIMS_ADMIN", "CMC_LIMS_CHEMIST", "CMC_LIMS_ANALYST"}
EXPORT_ROLES = {"SYS_ADMIN", "CMC_LIMS_ADMIN", "CMC_LIMS_CHEMIST"}
ADMIN_ROLES = {"SYS_ADMIN", "CMC_LIMS_ADMIN"}


def bearer_token(authorization: str | None) -> str | None:
    if authorization and authorization.lower().startswith("bearer "):
        return authorization[7:].strip()
    return None


@dataclass(frozen=True)
class CurrentUser:
    """当前操作人。`token` 为验签通过的原始令牌；开放模式（system）为 None。"""

    username: str
    sub: str | None = None
    full_name: str | None = None
    roles: tuple[str, ...] = ()
    token: str | None = None

    @property
    def is_system(self) -> bool:
        return self.token is None

    def has_any(self, roles: set[str]) -> bool:
        """本地开放模式(system)放行一切；否则看角色是否命中。"""
        return self.is_system or bool(set(self.roles) & roles)

    @property
    def can_view(self) -> bool:
        return self.has_any(VIEW_ROLES)

    @property
    def can_export(self) -> bool:
        return self.has_any(EXPORT_ROLES)

    @property
    def can_admin(self) -> bool:
        return self.has_any(ADMIN_ROLES)

    @classmethod
    def from_claims(cls, claims: dict, token: str) -> "CurrentUser":
        roles = claims.get("roles") or []
        username = claims.get("username") or claims.get("sub") or SYSTEM_ACTOR
        return cls(
            username=username,
            sub=str(claims["sub"]) if claims.get("sub") is not None else None,
            full_name=claims.get("full_name"),
            roles=tuple(roles) if isinstance(roles, (list, tuple)) else (),
            token=token,
        )

    @classmethod
    def system(cls) -> "CurrentUser":
        return cls(username=SYSTEM_ACTOR)


async def require_user(authorization: str | None = Header(None)) -> CurrentUser:
    """基础依赖：已配验签密钥则强制有效令牌，否则本地开放模式（system）。"""
    token = bearer_token(authorization)
    if security.auth_configured():
        if not token:
            raise HTTPException(status_code=401, detail="需要登录（缺少 Bearer 令牌）")
        return CurrentUser.from_claims(security.verify_access_token(token), token)
    if settings.auth_required:
        raise HTTPException(status_code=401, detail="服务端要求鉴权，但未配置 JWT 验签密钥")
    return CurrentUser.system()


async def require_view(user: CurrentUser = Depends(require_user)) -> CurrentUser:
    """看板查看：分析员及以上。"""
    if not user.can_view:
        raise HTTPException(status_code=403, detail="无查看权限：需在 MDM 分配 LIMS 看板角色")
    return user


async def require_export(user: CurrentUser = Depends(require_user)) -> CurrentUser:
    """导出：化学家及以上（预留，导出功能上线后使用）。"""
    if not user.can_export:
        raise HTTPException(status_code=403, detail="无导出权限：需「检验化学家」或以上角色")
    return user


async def require_admin(user: CurrentUser = Depends(require_user)) -> CurrentUser:
    """Admin 后台：LIMS 管理员 / SYS_ADMIN。"""
    if not user.can_admin:
        raise HTTPException(status_code=403, detail="无管理权限：需「LIMS 管理员」角色")
    return user
