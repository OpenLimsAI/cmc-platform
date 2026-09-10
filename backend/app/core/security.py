# JWT 验签 —— 校验 MDM 签发的 access token（本系统不签发令牌，只验签）。
#
# 与 MDM（cmab-mdm-platform）契约对齐（同 rd-batch-registry 的接法）：
#   - 库：python-jose；算法 HS256（dev 共享密钥）/ RS256（prod 公钥）。
#   - claims：sub(用户id) / username / full_name / roles / type="access" / exp / iat。
#     MDM 不放 iss/aud，故此处不校验签发者/受众。
#   - MDM 未暴露 JWKS 端点，验签密钥靠本地配置：
#     HS256 → JWT_SECRET_KEY（须等于 MDM 的 SECRET_KEY）；RS256 → JWT_PUBLIC_KEY_PATH（MDM 公钥 PEM）。
#
# 「未配置验签密钥」是合法的本地开发态：此时 auth_configured() 为 False，
# 调用方据此走开放模式（操作人记 system），而不是信任无法验证的令牌身份。
from functools import lru_cache
from pathlib import Path

from fastapi import HTTPException
from jose import JWTError, jwt
from jose.exceptions import ExpiredSignatureError

from app.core.config import settings


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
        raise HTTPException(status_code=401, detail="令牌已过期，请重新登录") from e
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
