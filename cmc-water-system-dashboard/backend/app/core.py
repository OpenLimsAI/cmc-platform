"""Fail-closed configuration and MDM access-token verification."""
from pathlib import Path
import re
from typing import Literal
import jwt
from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import model_validator, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=Path(__file__).parents[1] / '.env', extra='ignore')
    app_env: str = 'mac_dev'
    staging_data_origin: Literal['unverified','legacy_xlsx','oracle_etl'] = 'unverified'
    database_url: str
    jwt_algorithm: str = 'HS256'
    jwt_verify_key: str
    water_view_roles: str
    water_export_roles: str
    png_font_path: str = '/System/Library/Fonts/STHeiti Light.ttc'
    max_rows: int = Field(default=100000,ge=1,le=1000000)
    @model_validator(mode='after')
    def validate_config(self):
        if self.jwt_algorithm not in {'HS256', 'RS256'} or len(self.jwt_verify_key) < 32 or self.jwt_verify_key == 'CHANGE_ME':
            raise ValueError('必须配置有效的 MDM 验签配置')
        for roles in (self.view_roles, self.export_roles):
            if not roles or any(not re.fullmatch(r'[A-Z][A-Z0-9_]+', r) for r in roles):
                raise ValueError('角色白名单无效')
        if not self.export_roles <= self.view_roles:
            raise ValueError('导出角色必须包含在查看角色中')
        return self
    @property
    def view_roles(self): return set(self.water_view_roles.split(','))
    @property
    def export_roles(self): return set(self.water_export_roles.split(','))
settings = Settings()
bearer = HTTPBearer(auto_error=False)
def identity(request: Request, credentials: HTTPAuthorizationCredentials | None = Depends(bearer)) -> dict:
    try:
        if not credentials: raise ValueError()
        claims = jwt.decode(credentials.credentials, settings.jwt_verify_key, algorithms=[settings.jwt_algorithm], options={'require': ['exp','sub','type'], 'verify_aud': False})
        if claims['type'] != 'access' or not str(claims['sub']).isdigit(): raise ValueError()
        if not isinstance(claims.get('roles'), list) or any(not isinstance(r,str) for r in claims['roles']): raise ValueError()
    except (jwt.PyJWTError, ValueError, TypeError):
        raise HTTPException(401, '身份无效或已过期') from None
    if claims.get('must_change_password') is True:
        raise HTTPException(403, '请先到 MDM 修改临时密码')
    request.state.actor_id=claims['sub']
    return claims

def require_view(user: dict = Depends(identity)) -> dict:
    if not settings.view_roles.intersection(user['roles']): raise HTTPException(403, '没有制药用水查看权限')
    return user

def require_export(user: dict = Depends(require_view)) -> dict:
    if not settings.export_roles.intersection(user['roles']): raise HTTPException(403, '没有制药用水导出权限')
    return user
