"""
文件: backend/tests/conftest.py
用途: pytest 共享 fixture
    - 用一个独立的测试库(默认: 本地 docker postgres16 中的 postgres 库),
      在里面建/清 material_mgmt schema,跑 sql/init.sql 建表
    - 每个测试拿一个 SQLAlchemy session,结束后 TRUNCATE 业务表

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
from sqlalchemy import text

from database import engine, SessionLocal  # noqa: E402  (after sys.path tweak)


@pytest.fixture(scope="session")
def _prepare_schema():
    """重建 material_mgmt schema 并跑 init.sql。
    连不上库时跳过依赖该 fixture 的测试,但纯函数测试(如 test_severity)不受影响。
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
        # 清空业务数据(unit_dict / location 的预置值保留,category_dict 也清)
        with engine.begin() as conn:
            conn.execute(text(
                "TRUNCATE inventory_txn, batch, material, import_log, category_dict "
                "RESTART IDENTITY CASCADE"
            ))


@pytest.fixture
def client(db):
    """FastAPI TestClient,DI 替换 get_db 走测试 session。"""
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
    """建一条物料 + 一个储存位置,返回 (material_code, location_id)。"""
    from models import Material, Location
    from decimal import Decimal

    loc = db.execute(text(
        "SELECT location_id FROM location WHERE name = '常温库房-A区'"
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
    return m.material_code, loc
