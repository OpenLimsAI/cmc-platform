"""
文件: backend/tests/test_auth_audit.py
用途: 鉴权 / 角色 / 审计 关键路径(v2.0:认证为 MDM JWT,本地不建用户表)
覆盖:
    - 匿名访问写接口 → 401
    - 伪造/错误类型 token → 401
    - 无写权限角色访问写接口 → 403(物料 / 设备各一)
    - SYS_ADMIN 写接口 → 201,且产生 audit_log 行
    - 审计写入失败时业务回滚
    - operator 字段取登录用户(JWT username),不可被请求体伪造
    - 批次创建的首笔 IN 流水也单独落审计(inventory.in)
说明:
    改密/用户管理/首登强制改密已移交 MDM Portal,不在本系统测试范围。
"""
from __future__ import annotations

from datetime import date

from jose import jwt
from sqlalchemy import text

from tests.conftest import auth_headers, mint_token
from auth import MDM_JWT_ALGORITHM


# ---------------------------------------------------------------------------
# 1. 匿名 / 坏 token
# ---------------------------------------------------------------------------
def test_anon_blocked_from_write_endpoint(anon_client):
    resp = anon_client.post("/api/materials", json={
        "material_code": "Z0001", "name_cn": "x", "unit": "支",
    })
    assert resp.status_code == 401


def test_forged_token_rejected(anon_client):
    """用错误密钥签的 token → 401(MDM_SECRET_KEY 本地校验)。"""
    bad = jwt.encode(
        {"sub": "1", "username": "hacker", "roles": ["SYS_ADMIN"], "type": "access"},
        "wrong-secret-key-not-the-mdm-one-at-all!!",
        algorithm=MDM_JWT_ALGORITHM,
    )
    resp = anon_client.get(
        "/api/materials", headers={"Authorization": f"Bearer {bad}"},
    )
    assert resp.status_code == 401


def test_wrong_token_type_rejected(anon_client):
    """type != access(如 refresh token)→ 401。"""
    headers = {"Authorization": f"Bearer {mint_token(['SYS_ADMIN'], token_type='refresh')}"}
    resp = anon_client.get("/api/materials", headers=headers)
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# 2. 角色控制:无写权限角色不能写
# ---------------------------------------------------------------------------
def test_readonly_role_forbidden_from_material_write(anon_client):
    resp = anon_client.post(
        "/api/materials",
        json={"material_code": "U0001", "name_cn": "x", "unit": "支"},
        headers=auth_headers(["READ_ONLY_USER"], username="ordinary", user_id=99),
    )
    assert resp.status_code == 403
    assert "管理员" in resp.json()["detail"]


def test_warehouse_role_forbidden_from_equipment_write(anon_client):
    """库管角色可写物料但不可写设备(角色按模块隔离)。"""
    resp = anon_client.post(
        "/api/equipment",
        json={"equipment_code": "EQX-1", "name": "x", "category": "分析仪器"},
        headers=auth_headers(["CMC_WAREHOUSE_ADMIN"], username="wh", user_id=98),
    )
    assert resp.status_code == 403


# ---------------------------------------------------------------------------
# 3. SYS_ADMIN 写操作 + audit_log 落库 + operator 自动填登录用户
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


def test_material_create_rolls_back_when_audit_fails(db, monkeypatch):
    """审计写入失败时,物料也不应落库。"""
    from fastapi.testclient import TestClient
    from main import app
    from database import get_db
    import routers.material as material_router

    def _override():
        try:
            yield db
        finally:
            pass

    def _boom(*args, **kwargs):
        raise RuntimeError("audit failed")

    app.dependency_overrides[get_db] = _override
    try:
        with TestClient(app, raise_server_exceptions=False) as c:
            monkeypatch.setattr(material_router, "write_audit", _boom)
            resp = c.post(
                "/api/materials",
                json={"material_code": "AUDITFAIL", "name_cn": "不应保存", "unit": "支"},
                headers=auth_headers(["SYS_ADMIN"]),
            )
            assert resp.status_code == 500
    finally:
        app.dependency_overrides.clear()

    # 生产路径里请求结束 session 关闭,未 commit 的 flush 即被丢弃;
    # 测试与端点共用同一 session,需先 rollback 再查,模拟 session 关闭后的可见性
    db.rollback()
    row = db.execute(text(
        "SELECT 1 FROM material WHERE material_code='AUDITFAIL'"
    )).first()
    assert row is None


def test_inventory_in_uses_login_user_as_operator(client, db, seed_material):
    """创建批次 + 入库 → inventory_txn.operator 应是 JWT 里的登录用户。"""
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


def test_batch_create_audits_initial_txn(client, db, seed_material):
    """批次创建的首笔 IN 流水也应单独落 audit_log(action=inventory.in)。"""
    mid, _code, loc = seed_material

    resp = client.post("/api/batches", json={
        "material_id": mid,
        "batch_no": "AUDIT-B2",
        "expiry_date": str(date.today().replace(year=date.today().year + 1)),
        "location_id": loc,
        "received_date": str(date.today()),
        "initial_qty": "5",
    })
    assert resp.status_code == 200, resp.json()
    batch_id = resp.json()["batch_id"]

    # batch.create 与 inventory.in 各一行
    n_batch = db.execute(text(
        "SELECT count(*) FROM audit_log WHERE action='batch.create' AND entity_id=:eid"
    ), {"eid": str(batch_id)}).scalar()
    assert n_batch == 1

    txn_id = db.execute(text(
        "SELECT txn_id FROM inventory_txn WHERE batch_id=:bid ORDER BY txn_id LIMIT 1"
    ), {"bid": batch_id}).scalar_one()
    n_txn = db.execute(text(
        "SELECT count(*) FROM audit_log WHERE action='inventory.in' AND entity_id=:eid"
    ), {"eid": str(txn_id)}).scalar()
    assert n_txn == 1


# ============ 2026-09-10 准入:实验室部门(TT*/CMC*)或 SYS_ADMIN ============
def _hdr(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def test_lab_member_department_prefix_allowed(client):
    for dept in ("TT1", "TT7", "tt5", "CMC", "CMC R&D"):
        r = client.get("/api/materials", headers=_hdr(mint_token(["READ_ONLY_USER"], department=dept)))
        assert r.status_code == 200, (dept, r.text)


def test_non_lab_department_forbidden(client):
    for dept in ("QA", "IT", "研发", ""):
        r = client.get("/api/materials", headers=_hdr(mint_token(["READ_ONLY_USER"], department=dept)))
        assert r.status_code == 403, (dept, r.text)
        assert "实验室部门" in r.json()["detail"]


def test_sys_admin_bypasses_department(client):
    r = client.get("/api/materials", headers=_hdr(mint_token(["SYS_ADMIN"], department="IT")))
    assert r.status_code == 200, r.text
    r = client.get("/api/materials", headers=_hdr(mint_token(["SYS_ADMIN"], department=None)))
    assert r.status_code == 200, r.text


def test_empty_department_gets_403_not_401(client):
    """部门为空(新令牌里 department=null)：应是 403 说明,不能被当成旧令牌 401 → 换证死循环"""
    r = client.get("/api/materials", headers=_hdr(mint_token(["READ_ONLY_USER"], department=None)))
    assert r.status_code == 401  # department=None 时 mint_token 不放该键 = 旧令牌
    import json as _json

    from jose import jwt as _jwt

    from auth import MDM_JWT_ALGORITHM, MDM_SECRET_KEY
    tok = mint_token(["READ_ONLY_USER"], department="X")
    claims = _jwt.decode(tok, MDM_SECRET_KEY, algorithms=[MDM_JWT_ALGORITHM])
    claims["department"] = None  # 键在、值为 null
    tok2 = _jwt.encode(claims, MDM_SECRET_KEY, algorithm=MDM_JWT_ALGORITHM)
    r2 = client.get("/api/materials", headers=_hdr(tok2))
    assert r2.status_code == 403, r2.text
    assert "实验室部门" in r2.json()["detail"]
    assert _json is not None


def test_legacy_token_without_department_gets_401(client):
    """旧令牌(无 department 字段)回 401,前端会去 MDM 换新令牌重放;不是 403"""
    r = client.get("/api/materials", headers=_hdr(mint_token(["CMC_WAREHOUSE_ADMIN"], department=None)))
    assert r.status_code == 401, r.text
