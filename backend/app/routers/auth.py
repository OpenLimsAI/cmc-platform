"""登录代理：把工号+密码原样转发 MDM 换取 JWT（本地不碰密码、不建账号）。

规范见 ~/code/CLAUDE.md §8，模板抄自 rd-batch-registry backend/app/api/v1/auth.py。
额外做一步：拿到令牌后（已配验签密钥时）当场验签并检查 USP 查看角色，
没权限的账号在登录时就明确报 403，而不是登录成功后每个接口都弹错。
"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

import httpx

from ..auth import CurrentUser, auth_configured, require_viewer, verify_access_token
from ..config import settings

router = APIRouter(prefix="/api/auth", tags=["auth"])


class LoginRequest(BaseModel):
    username: str
    password: str


@router.post("/login")
async def login(req: LoginRequest):
    """转发 MDM 校验工号密码，返回 access_token 与用户信息。"""
    if not settings.mdm_base_url:
        raise HTTPException(status_code=400, detail="未配置 MDM_BASE_URL，无法登录")
    url = f"{settings.mdm_base_url.rstrip('/')}/api/v1/auth/login"
    try:
        # trust_env=False：不走本机 ClashX 代理（MDM 是内网服务）
        async with httpx.AsyncClient(timeout=8.0, trust_env=False) as client:
            resp = await client.post(url, json=req.model_dump())
    except httpx.HTTPError as e:
        raise HTTPException(status_code=502, detail=f"认证中心（MDM）不可达：{e}") from e
    if resp.status_code != 200:
        raise HTTPException(status_code=401, detail="工号或密码不对（MDM 校验未通过）")
    body = resp.json()
    data = body.get("data", body)
    token = data.get("access_token") or data.get("token")
    if not token:
        raise HTTPException(status_code=502, detail="MDM 登录返回里没有令牌")
    # 已配验签密钥时当场检查查看角色，无权限登录即拒（比进去后处处 403 友好）
    if auth_configured():
        user = CurrentUser.from_claims(verify_access_token(token))
        if not user.can_view:
            raise HTTPException(
                status_code=403,
                detail="该账号没有 USP 看板查看权限，请联系管理员在 MDM Portal 分配 USP 相关角色",
            )
    return data


@router.get("/me")
async def me(user: CurrentUser = Depends(require_viewer)):
    """当前登录人（前端启动时验令牌用）。开放模式返回 system。"""
    return {
        "username": user.username,
        "full_name": user.full_name,
        "roles": list(user.roles),
        "is_system": user.is_system,
    }
