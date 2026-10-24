# 角色分级：ANALYST 查看 / CHEMIST 查看+导出 / ADMIN 全部 / SYS_ADMIN 恒放行
# 本地开放模式（system）放行一切
import asyncio

import pytest
from fastapi import HTTPException

from app.core.auth import CurrentUser, require_admin, require_export, require_view


def _user(*roles: str) -> CurrentUser:
    return CurrentUser.from_claims(
        {"sub": "1", "username": "090501", "full_name": "张三", "roles": list(roles), "type": "access"},
        token="dummy-token",
    )


@pytest.mark.parametrize(
    ("roles", "view", "export", "admin"),
    [
        ((), False, False, False),
        (("READ_ONLY",), False, False, False),          # 非本系统角色不放行
        (("CMC_LIMS_ANALYST",), True, False, False),
        (("CMC_LIMS_CHEMIST",), True, True, False),
        (("CMC_LIMS_ADMIN",), True, True, True),
        (("SYS_ADMIN",), True, True, True),             # MDM 全局管理员恒放行
        (("CMC_LIMS_ANALYST", "CMC_LIMS_ADMIN"), True, True, True),  # 多角色取并集
    ],
)
def test_role_matrix(roles, view, export, admin):
    u = _user(*roles)
    assert u.can_view is view
    assert u.can_export is export
    assert u.can_admin is admin


def test_system_open_mode_allows_everything():
    u = CurrentUser.system()
    assert u.is_system
    assert u.can_view and u.can_export and u.can_admin


def test_guards_raise_403_without_role():
    u = _user("CMC_LIMS_ANALYST")
    assert asyncio.run(require_view(user=u)) is u
    with pytest.raises(HTTPException) as e1:
        asyncio.run(require_export(user=u))
    assert e1.value.status_code == 403
    with pytest.raises(HTTPException) as e2:
        asyncio.run(require_admin(user=u))
    assert e2.value.status_code == 403


def test_from_claims_defensive_parsing():
    # roles 缺失 / 非列表都不能炸
    u1 = CurrentUser.from_claims({"sub": "1", "username": "a"}, token="t")
    assert u1.roles == ()
    u2 = CurrentUser.from_claims({"sub": "1", "username": "a", "roles": "SYS_ADMIN"}, token="t")
    assert u2.roles == ()  # 字符串不是列表，按无角色处理
    # username 缺失回退 sub
    u3 = CurrentUser.from_claims({"sub": "42"}, token="t")
    assert u3.username == "42"
