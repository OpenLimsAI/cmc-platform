import hashlib
import hmac

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel

from app.core.config import settings

router = APIRouter()


def _compute_token() -> str:
    return hashlib.sha256(f"lims_admin:{settings.admin_password}".encode()).hexdigest()


async def verify_admin(x_admin_token: str = Header(..., alias="x-admin-token")):
    # 恒定时间比较，避免 token 校验的时序侧信道
    if not hmac.compare_digest(x_admin_token, _compute_token()):
        raise HTTPException(status_code=401, detail="Unauthorized")


class AuthRequest(BaseModel):
    password: str


class AuthResponse(BaseModel):
    token: str


@router.post("/auth", response_model=AuthResponse)
async def authenticate(body: AuthRequest):
    if not hmac.compare_digest(body.password, settings.admin_password):
        raise HTTPException(status_code=401, detail="密码错误")
    return AuthResponse(token=_compute_token())
