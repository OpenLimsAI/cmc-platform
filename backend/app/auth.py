"""统一认证：本地验签 MDM 签发的 JWT（本系统不签发令牌，只验签）。

规范见 ~/code/CLAUDE.md §8，模板抄自 rd-batch-registry backend/app/core/{security,auth}.py。
与 MDM（cmab-mdm-platform）契约：
- claims：`sub` / `username` / `full_name` / `roles` / `type="access"` / `exp`；
  不含 `iss`/`aud`，故不校验签发者/受众。
- 验签密钥靠本地配置：HS256 → JWT_SECRET_KEY（须等于 MDM 的 SECRET_KEY）；
  RS256 → JWT_PUBLIC_KEY_PATH（MDM 公钥 PEM）。MDM 无 JWKS 端点。

两种运行态（由是否配置验签密钥决定）：
- 已配密钥：全部数据接口强制 Bearer 令牌 + USP 角色，否则 401/403。
- 未配密钥（本地开发）：开放模式放行（operator 记 system）。
  **绝不解码无法验证的令牌当身份**。AUTH_REQUIRED=true 但漏配密钥则启动报错（main.py）。

本看板纯只读，鉴权只有一档：require_viewer（谁能看）。
"""
from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from fastapi import Header, HTTPException
from jose import JWTError, jwt
from jose.exceptions import ExpiredSignatureError

from .config import settings

SYSTEM_ACTOR = "system"


@lru_cache
def _verifying_key() -> str | None:
    """按算法返回验签密钥；未配置返回 None（开放模式）。"""
    algo = settings.jwt_algorithm.upper()
    if algo == "HS256":
        return settings.jwt_secret_key or None
    if algo == "RS256":
        if not settings.jwt_public_key_path:
            return None
        path = Path(settings.jwt_public_key_path)
        if not path.is_file():
            raise RuntimeError(f"RS256 公钥文件不存在：{path}")
        return path.read_text(encoding="utf-8")
    raise RuntimeError(f"不支持的 JWT_ALGORITHM：{settings.jwt_algorithm}（仅 HS256/RS256）")


def auth_configured() -> bool:
    """是否已配置验签密钥（决定接口是否强制鉴权）。"""
    return _verifying_key() is not None


def verify_access_token(token: str) -> dict:
    """验签 + 校验有效期，返回 claims；任何问题抛 401。"""
    key = _verifying_key()
    if key is None:
        raise HTTPException(status_code=401, detail="服务端未配置 JWT 验签密钥")
    try:
        claims = jwt.decode(token, key, algorithms=[settings.jwt_algorithm.upper()])
    except ExpiredSignatureError as e:
        raise HTTPException(status_code=401, detail="登录已过期，请重新登录") from e
    except JWTError as e:
        raise HTTPException(status_code=401, detail="令牌无效（验签失败）") from e
    if claims.get("type") != "access":
        raise HTTPException(status_code=401, detail="令牌类型错误（需 access 令牌）")
    # 2026-09-11：拿临时密码（管理员重置后）的人只能先去 MDM 改密码。
    # MDM 自己早就拦了，但下游本地验签、不回调 MDM，所以靠令牌里的 must_change_password 标记。
    # 用 403 不用 401：401 会被前端当成会话过期去续期，续出来的新令牌照样带这个标记，会转圈。
    if claims.get("must_change_password"):
        raise HTTPException(status_code=403, detail="请先到主数据平台（MDM）修改临时密码，再使用本系统")
    return claims


@dataclass(frozen=True)
class CurrentUser:
    username: str
    full_name: str | None = None
    roles: tuple[str, ...] = ()
    is_system: bool = False  # 本地开放模式（未配验签密钥）

    @property
    def can_view(self) -> bool:
        """开放模式放行一切；否则角色须命中查看白名单。"""
        return self.is_system or bool(set(self.roles) & settings.viewer_role_set)

    @classmethod
    def from_claims(cls, claims: dict) -> CurrentUser:
        roles = claims.get("roles") or []
        return cls(
            username=claims.get("username") or str(claims.get("sub") or SYSTEM_ACTOR),
            full_name=claims.get("full_name"),
            roles=tuple(roles) if isinstance(roles, (list, tuple)) else (),
        )


def _bearer_token(authorization: str | None) -> str | None:
    if authorization and authorization.lower().startswith("bearer "):
        return authorization[7:].strip()
    return None


async def require_viewer(authorization: str | None = Header(None)) -> CurrentUser:
    """数据接口依赖：已配验签密钥则强制有效令牌 + USP 查看角色，否则开放模式。"""
    if not auth_configured():
        if settings.auth_required:
            raise HTTPException(status_code=401, detail="服务端要求鉴权，但未配置 JWT 验签密钥")
        return CurrentUser(username=SYSTEM_ACTOR, is_system=True)
    token = _bearer_token(authorization)
    if not token:
        raise HTTPException(status_code=401, detail="需要登录（缺少 Bearer 令牌）")
    user = CurrentUser.from_claims(verify_access_token(token))
    if not user.can_view:
        raise HTTPException(
            status_code=403,
            detail="该账号没有 USP 看板查看权限，请联系管理员在 MDM Portal 分配 USP 相关角色",
        )
    return user
