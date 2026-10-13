"""
安全工具：密码哈希、JWT
"""
from datetime import UTC, datetime, timedelta
from typing import Any

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.core.config import settings
from app.core.exceptions import TokenExpiredError, TokenInvalidError
from app.core.jwt_keys import get_jwt_header_extras, get_signing_key, get_verifying_key

# ============== 密码哈希 ==============
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto", bcrypt__rounds=12)


def hash_password(password: str) -> str:
    """对密码进行 bcrypt 哈希"""
    return pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    """校验密码"""
    return pwd_context.verify(plain, hashed)


# ============== JWT ==============
def create_access_token(
    subject: int | str,
    extra_claims: dict[str, Any] | None = None,
    expires_minutes: int | None = None,
    expires_at: datetime | None = None,
    issued_at: datetime | None = None,
) -> str:
    """生成 Access Token（按 settings.JWT_ALGORITHM 选 HS256/RS256）"""
    expire = expires_at or datetime.now(UTC) + timedelta(
        minutes=expires_minutes or settings.ACCESS_TOKEN_EXPIRE_MINUTES
    )
    payload: dict[str, Any] = {
        "sub": str(subject),
        "type": "access",
        "exp": expire,
        "iat": issued_at or datetime.now(UTC),
    }
    if extra_claims:
        payload.update(extra_claims)
    return jwt.encode(
        payload,
        get_signing_key(),
        algorithm=settings.JWT_ALGORITHM,
        headers=get_jwt_header_extras() or None,
    )


def create_refresh_token(
    subject: int | str, jti: str, expires_at: datetime, *, issued_at: datetime | None = None,
) -> str:
    """生成 Refresh Token。到期时间由会话策略算好传入（min(空闲窗口, 硬上限)，见 session_policy）"""
    expire = expires_at
    payload = {
        "sub": str(subject),
        "type": "refresh",
        "jti": jti,
        "exp": expire,
        "iat": issued_at or datetime.now(UTC),
    }
    return jwt.encode(
        payload,
        get_signing_key(),
        algorithm=settings.JWT_ALGORITHM,
        headers=get_jwt_header_extras() or None,
    )


def decode_token(token: str, *, verify_exp: bool = True) -> dict[str, Any]:
    """解码并校验 Token。

    verify_exp=False 仅供 refresh 端点使用：refresh 的到期以 DB 行为准
    （能区分「空闲超时」与「达到硬上限」给出不同提示），JWT 签名仍照常校验。
    """
    try:
        return jwt.decode(
            token,
            get_verifying_key(),
            algorithms=[settings.JWT_ALGORITHM],
            options={"verify_exp": verify_exp},
        )
    except jwt.ExpiredSignatureError as e:
        raise TokenExpiredError() from e
    except JWTError as e:
        raise TokenInvalidError() from e
