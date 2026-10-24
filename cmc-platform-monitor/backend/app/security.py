import re
import jwt
from fastapi import HTTPException

# Remove URLs, credentials and business identities from excerpts before persistence.
def redact(value: str) -> str:
    value = re.sub(r'(?i)(?:postgres(?:ql)?|oracle|mysql)\S*://[^\s]+', '[连接信息已隐藏]', value)
    value = re.sub(r'(?i)(Bearer\s+)\S+', r'\1[已隐藏]', value)
    value = re.sub(r'(?i)((?:password|passwd|secret|token|api_key|dsn)\s*[=:]\s*)[^\s,;]+', r'\1[已隐藏]', value)
    value = re.sub(r'eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+', '[令牌已隐藏]', value)
    return value[:65536]

def authenticate(token: str | None, settings) -> dict:
    try:
        if not token: raise ValueError()
        c = jwt.decode(token, settings.jwt_verify_key.get_secret_value(), algorithms=[settings.jwt_algorithm],
                       options={'require': ['sub', 'exp', 'type'], 'verify_aud': False})
        if c['type'] != 'access' or not isinstance(c['sub'], str) or not c['sub'].isdigit(): raise ValueError()
        roles = c.get('roles')
        if not isinstance(roles, list) or any(not isinstance(r, str) for r in roles): raise ValueError()
    except (jwt.PyJWTError, ValueError, TypeError):
        raise HTTPException(401, '身份无效或已过期') from None
    if c.get('must_change_password') is not False:
        # MDM always emits this claim. Missing/malformed is not an implicit exemption.
        raise HTTPException(403, '请先确认MDM密码状态')
    if 'SYS_ADMIN' not in roles: raise HTTPException(403, '仅系统管理员可进入')
    return {'sub': c['sub'], 'username': c.get('username', ''), 'roles': roles}
