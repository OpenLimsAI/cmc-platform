"""
文件: backend/tests/test_auth_audit.py
用途: 鉴权 / 角色 / 审计 关键路径
覆盖:
    - 匿名访问写接口 → 401
    - user 角色访问写接口 → 403
    - admin 写接口 → 200,且产生 audit_log 行
    - 改密成功后旧 token 失效
    - 错误密码 → 401
    - operator 字段被忽略,实际写入的是登录用户
"""
from __future__ import annotations

from datetime import date

from sqlalchemy import text


def _login(client, username, password):
    return client.post("/api/auth/login", json={"username": username, "password": password})


# ---------------------------------------------------------------------------
# 1. 匿名 / 错误密码
# ---------------------------------------------------------------------------
def test_anon_blocked_from_write_endpoint(anon_client):
    resp = anon_client.post("/api/materials", json={
        "material_code": "Z0001", "name_cn": "x", "unit": "支",
    })
    assert resp.status_code == 401


def test_anon_can_login(anon_client):
    resp = _login(anon_client, "testadmin", "test_pwd_123")
    assert resp.status_code == 200
    assert resp.json()["user"]["role"] == "admin"


def test_login_wrong_password(anon_client):
    resp = _login(anon_client, "testadmin", "wrong")
    assert resp.status_code == 401
    assert "用户名或密码错误" in resp.json()["detail"]


# ---------------------------------------------------------------------------
# 2. 角色控制:user 不能写
# ---------------------------------------------------------------------------
def test_user_role_forbidden_from_write(anon_client, db):
    """建一个普通 user,登录后试图新增物料 → 403。"""
    from auth import hash_password
    from models import AppUser
    db.add(AppUser(
        username="ordinary",
        password_hash=hash_password("user_pwd_xx"),
        role="user",
        is_active=True,
        must_change_password=False,
    ))
    db.commit()

    resp = _login(anon_client, "ordinary", "user_pwd_xx")
    assert resp.status_code == 200
    token = resp.json()["access_token"]

    resp = anon_client.post(
        "/api/materials",
        json={"material_code": "U0001", "name_cn": "x", "unit": "支"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 403
    assert "管理员" in resp.json()["detail"]


# ---------------------------------------------------------------------------
# 3. admin 写操作 + audit_log 落库 + operator 自动填登录用户
# ---------------------------------------------------------------------------
def test_admin_create_material_writes_audit(client, db):
    resp = client.post("/api/materials", json={
        "material_code": "AU001", "name_cn": "审计测试物料", "unit": "支",
    })
    assert resp.status_code == 201
    new_id = resp.json()["material_id"]

    # audit_log 应有一行 material.create,entity_id = material_id(v1.2 改键)
    rows = db.execute(text(
        "SELECT username, action, entity_type, entity_id "
        "FROM audit_log WHERE action='material.create' AND entity_id=:eid"
    ), {"eid": str(new_id)}).all()
    assert len(rows) == 1
    assert rows[0][0] == "testadmin"
    assert rows[0][2] == "material"


def test_inventory_in_uses_login_user_as_operator(client, db, seed_material):
    """创建批次 + 入库 → inventory_txn.operator 应是 testadmin,不是 client 传的字段。"""
    mid, _code, loc = seed_material

    resp = client.post("/api/batches", json={
        "material_id": mid,
        "batch_no": "AUDIT-B1",
        "expiry_date": str(date.today().replace(year=date.today().year + 1)),
        "location_id": loc,
        "received_date": str(date.today()),
        "initial_qty": "10",
    })
    assert resp.status_code == 200, resp.json()

    op = db.execute(text(
        "SELECT operator FROM inventory_txn WHERE qty=10 ORDER BY txn_id DESC LIMIT 1"
    )).scalar()
    assert op == "testadmin"


# ---------------------------------------------------------------------------
# 4. 改密后旧 token 失效
# ---------------------------------------------------------------------------
def test_change_password_invalidates_old_tokens(anon_client, db):
    """临时建一个用户 → 登录拿 token → 改密 → 用旧 token 调 /me 应 401。"""
    from auth import hash_password
    from models import AppUser
    db.add(AppUser(
        username="rotateuser",
        password_hash=hash_password("first_password_8"),
        role="admin",
        is_active=True,
        must_change_password=False,
    ))
    db.commit()

    resp = _login(anon_client, "rotateuser", "first_password_8")
    assert resp.status_code == 200
    old_token = resp.json()["access_token"]

    # 用旧 token 改密
    resp = anon_client.post(
        "/api/auth/change-password",
        json={"old_password": "first_password_8", "new_password": "second_password_9"},
        headers={"Authorization": f"Bearer {old_token}"},
    )
    assert resp.status_code == 200

    # 旧 token 应失效
    resp = anon_client.get(
        "/api/users/me",
        headers={"Authorization": f"Bearer {old_token}"},
    )
    assert resp.status_code == 401

    # 用新密码可以登录
    resp = _login(anon_client, "rotateuser", "second_password_9")
    assert resp.status_code == 200


# ---------------------------------------------------------------------------
# 5. must_change_password 守卫:首次登录不能调业务接口
# ---------------------------------------------------------------------------
def test_must_change_password_blocks_business_calls(anon_client, db):
    from auth import hash_password
    from models import AppUser
    db.add(AppUser(
        username="freshie",
        password_hash=hash_password("init_password_8"),
        role="admin",
        is_active=True,
        must_change_password=True,  # 首次登录强制
    ))
    db.commit()

    resp = _login(anon_client, "freshie", "init_password_8")
    assert resp.status_code == 200
    token = resp.json()["access_token"]

    # 业务接口被拦
    resp = anon_client.get(
        "/api/materials",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 403
    assert "改密" in resp.json()["detail"]

    # /me 仍允许(让用户能查)
    resp = anon_client.get(
        "/api/users/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
