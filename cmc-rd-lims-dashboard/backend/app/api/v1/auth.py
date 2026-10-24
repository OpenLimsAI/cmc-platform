# 登录代理 —— 转发到 MDM 换取 JWT（本系统不建账号、不存密码、不签发令牌）。
#
# 对齐 labops 的接法：access_token 走 JSON 返回（前端存 localStorage），
# refresh token 以 HttpOnly Cookie 中转（与 MDM 同名 cmab_refresh_token），
# 供 /auth/refresh 无感续期（MDM access 令牌 30 分钟过期，看板常开必须续期）。
import httpx
from fastapi import APIRouter, Cookie, HTTPException, Response
from pydantic import BaseModel

from app.core.config import settings

router = APIRouter()

REFRESH_COOKIE_NAME = "cmab_refresh_token"
REFRESH_COOKIE_PATH = "/api/v1/auth"
REFRESH_COOKIE_MAX_AGE = 7 * 86400


def _mdm_url(path: str) -> str:
    if not settings.mdm_base_url:
        raise HTTPException(status_code=400, detail="未配置 MDM_BASE_URL，无法登录")
    return f"{settings.mdm_base_url.rstrip('/')}/api/v1/auth{path}"


def _set_refresh_cookie(response: Response, token: str) -> None:
    # 内网 http 环境 secure=False；上 HTTPS 后置 COOKIE_SECURE=true 即可
    response.set_cookie(
        key=REFRESH_COOKIE_NAME,
        value=token,
        max_age=REFRESH_COOKIE_MAX_AGE,
        path=REFRESH_COOKIE_PATH,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax",
    )


class LoginRequest(BaseModel):
    username: str
    password: str


@router.post("/login", summary="登录（转发到 MDM 校验并取 JWT）")
async def login(req: LoginRequest, response: Response):
    url = _mdm_url("/login")
    try:
        # trust_env=False：不走本机 ClashX 代理（MDM 是本地/内网服务）
        async with httpx.AsyncClient(timeout=8.0, trust_env=False) as client:
            resp = await client.post(url, json=req.model_dump())
    except httpx.HTTPError as e:
        raise HTTPException(status_code=502, detail=f"认证服务（MDM）不可达：{e}") from e
    if resp.status_code != 200:
        detail = "用户名或密码错误"
        try:
            body = resp.json()
            detail = body.get("detail") or body.get("message") or detail
        except Exception:
            pass
        raise HTTPException(status_code=resp.status_code, detail=detail)

    # 中转 MDM 的 refresh Cookie（HttpOnly，7 天）；access_token 照常 body 返回
    mdm_refresh = resp.cookies.get(REFRESH_COOKIE_NAME)
    if mdm_refresh:
        _set_refresh_cookie(response, mdm_refresh)

    body = resp.json()
    return body.get("data", body)


@router.post("/refresh", summary="用 HttpOnly Cookie 换新 access token")
async def refresh(
    response: Response,
    cmab_refresh_token: str | None = Cookie(default=None),
):
    if not cmab_refresh_token:
        raise HTTPException(status_code=401, detail="会话已过期，请重新登录")
    try:
        async with httpx.AsyncClient(timeout=8.0, trust_env=False) as client:
            resp = await client.post(
                _mdm_url("/refresh"),
                cookies={REFRESH_COOKIE_NAME: cmab_refresh_token},
            )
    except httpx.HTTPError as e:
        raise HTTPException(status_code=502, detail=f"认证服务（MDM）不可达：{e}") from e
    if resp.status_code != 200:
        response.delete_cookie(key=REFRESH_COOKIE_NAME, path=REFRESH_COOKIE_PATH)
        raise HTTPException(status_code=401, detail="会话已过期，请重新登录")

    # MDM 轮换了 refresh，透传新 Cookie 给浏览器
    new_refresh = resp.cookies.get(REFRESH_COOKIE_NAME)
    if new_refresh:
        _set_refresh_cookie(response, new_refresh)

    body = resp.json()
    return body.get("data", body)


@router.post("/logout", status_code=204, summary="登出（撤销 MDM refresh + 清 Cookie）")
async def logout(
    response: Response,
    cmab_refresh_token: str | None = Cookie(default=None),
):
    if cmab_refresh_token:
        try:
            async with httpx.AsyncClient(timeout=8.0, trust_env=False) as client:
                await client.post(
                    _mdm_url("/logout"),
                    cookies={REFRESH_COOKIE_NAME: cmab_refresh_token},
                )
        except httpx.HTTPError:
            pass  # best-effort，MDM 不可达也要清本地 Cookie
    response.delete_cookie(key=REFRESH_COOKIE_NAME, path=REFRESH_COOKIE_PATH)
