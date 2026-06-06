"""
文件: backend/tests/conftest.py
用途: pytest 共享 fixture
    - 用一个独立的测试库(默认: 本地 docker postgres16 中的 postgres 库),
      在里面建/清 material_mgmt schema,跑 sql/init.sql 建表
    - 每个测试拿一个 SQLAlchemy session,结束后 TRUNCATE 业务表
    - 认证走 MDM JWT(v2.0):测试不连真实 MDM,直接用 MDM_SECRET_KEY
      本地铸 token(claims 结构与 MDM 签发一致),auth.py 校验逻辑全覆盖

环境变量:
    DATABASE_URL_TEST  覆盖默认连接(默认 postgres@127.0.0.1:5432/postgres,无密码)

注意:
    - 千万不要把 DATABASE_URL_TEST 指向生产库
    - schema 名固定为 material_mgmt(模型里 __table_args__ 写死),
      所以测试库必须是一个独立的 PG database
"""
from __future__ import annotations

import os
import pathlib
import sys
from datetime import datetime, timedelta

# 把 backend/ 加到 sys.path,让 `import crud / models / database` 能直接走通
BACKEND_DIR = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

# 在 import database 之前覆盖 DATABASE_URL,让模块级 engine 用测试连接串
TEST_URL = os.environ.setdefault(
    "DATABASE_URL_TEST",
    "postgresql://postgres@127.0.0.1:5432/postgres",
)
os.environ["DATABASE_URL"] = TEST_URL

import pytest
from jose import jwt
from sqlalchemy import text

from database import engine, SessionLocal  # noqa: E402  (after sys.path tweak)
from auth import MDM_SECRET_KEY, MDM_JWT_ALGORITHM  # noqa: E402


def mint_token(
    roles: list[str],
    username: str = "testadmin",
    user_id: int = 1,
    token_type: str = "access",
    expires_minutes: int = 30,
) -> str:
    """本地铸一个与 MDM 签发结构一致的 JWT(测试不依赖真实 MDM 服务)。"""
    payload = {
        "sub": str(user_id),
        "username": username,
        "roles": roles,
        "type": token_type,
        "exp": datetime.utcnow() + timedelta(minutes=expires_minutes),
    }
    return jwt.encode(payload, MDM_SECRET_KEY, algorithm=MDM_JWT_ALGORITHM)


def auth_headers(roles: list[str], username: str = "testadmin", user_id: int = 1) -> dict:
    return {"Authorization": f"Bearer {mint_token(roles, username, user_id)}"}


@pytest.fixture(scope="session")
def _prepare_schema():
    """重建 material_mgmt schema 并跑 init.sql。
    连不上库时跳过依赖该 fixture 的测试,但纯函数测试(如 test_severity)不受影响。
    v2.0 起认证移交 MDM,不再需要建本地测试用户。
    """
    sql_init = (BACKEND_DIR.parent / "sql" / "init.sql").read_text(encoding="utf-8")
    try:
        raw = engine.raw_connection()
    except Exception as e:
        pytest.skip(
            f"测试库 {TEST_URL} 连不上: {e}\n"
            f"提示:设 DATABASE_URL_TEST 指向独立测试库,或用 PGPASSWORD env 提供密码。"
            f"详见 README §十五 测试。",
            allow_module_level=False,
        )
    try:
        cur = raw.cursor()
        cur.execute("DROP SCHEMA IF EXISTS material_mgmt CASCADE")
        cur.execute("CREATE SCHEMA material_mgmt")
        # init.sql 里有 SET search_path,会作用到这个 cursor,后续 DDL 都进 material_mgmt
        cur.execute(sql_init)
        raw.commit()
        cur.close()
    finally:
        raw.close()

    yield
    # 测试完保留 schema,方便用 psql 看现场;需要清理可手动 DROP


@pytest.fixture
def db(_prepare_schema):
    """每个测试一个 session;结束后 TRUNCATE 业务表保持隔离。"""
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
        with engine.begin() as conn:
            conn.execute(text(
                "TRUNCATE inventory_txn, batch, material, import_log, category_dict, audit_log "
                "RESTART IDENTITY CASCADE"
            ))


@pytest.fixture
def client(db):
    """FastAPI TestClient,DI 替换 get_db 走测试 session;
    自带 SYS_ADMIN 角色的 Bearer token(本地铸,与 MDM 签发结构一致)。
    """
    from fastapi.testclient import TestClient
    from main import app
    from database import get_db

    def _override():
        try:
            yield db
        finally:
            pass

    app.dependency_overrides[get_db] = _override
    with TestClient(app) as c:
        c.headers.update(auth_headers(["SYS_ADMIN"]))
        yield c
    app.dependency_overrides.clear()


@pytest.fixture
def anon_client(db):
    """匿名 TestClient(无 token),用于测 401 / 公开接口。"""
    from fastapi.testclient import TestClient
    from main import app
    from database import get_db

    def _override():
        try:
            yield db
        finally:
            pass

    app.dependency_overrides[get_db] = _override
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture
def seed_material(db):
    """建一条物料 + 取一个储存位置,返回 (material_id, material_code, location_id)。
    v1.2:material_code 不再唯一(TT 例外),所有 mutate 操作走 material_id。"""
    from models import Material
    from decimal import Decimal

    # v1.2 init.sql 把 2251 房间 90 个柜位作为预置,取一个稳定的位置
    loc = db.execute(text(
        "SELECT location_id FROM location WHERE name = '2251-A01-L1'"
    )).scalar_one()

    m = Material(
        material_code="42001",
        category="一般耗材",
        name_cn="测试耗材",
        unit="支",  # 已在 unit_dict 预置
        safety_stock=Decimal("100"),
        is_active=True,
    )
    db.add(m)
    db.commit()
    return m.material_id, m.material_code, loc
